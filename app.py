from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
from PIL import Image


APP_TITLE = "LJM MLO Renderer"
APP_SUBTITLE = "Upload your Learner Journey Map to generate student-facing PDFs and images for Blackboard."

REPO_ROOT = Path(__file__).resolve().parent
PIPELINE_SCRIPT = REPO_ROOT / "python scripts" / "make_student_journey_map.py"

WEEK_COUNT_OPTIONS = ["10 weeks", "12 weeks", "Custom"]
WEEK_COUNT_VALUES = {"10 weeks": 10, "12 weeks": 12}

DEFAULTS = {
    "render_target": "both",
    "layout_mode": "flex-height",
    "week1": date(2026, 9, 21),
    "week_count_choice": "12 weeks",
    "expected_weeks_custom": 12,
    "mlo_header_size": 52,
    "mlo_code_size": 52,
    "mlo_title_size": 37,
    "mlo_desc_size": 37,
    "mlo_line_spacing": 8,
    "mlo_header_line_gap": 0,
}

PDF_PAGE_BG = (255, 255, 255)
STALE_WORK_DIR_MAX_AGE_SECONDS = 2 * 60 * 60  # 2 hours


def cleanup_stale_work_dirs() -> None:
    # This app is public (Streamlit Community Cloud): uploaded docs and generated
    # PNGs/PDFs land in a per-session temp dir that's only otherwise removed by the
    # hidden "Reset workspace" button, so nothing else clears them. Sweep anything
    # untouched for a while so uploads don't accumulate indefinitely on the host.
    current = st.session_state.get("work_dir")
    now = time.time()
    for path in Path(tempfile.gettempdir()).glob("ljm_streamlit_*"):
        if str(path) == current:
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age > STALE_WORK_DIR_MAX_AGE_SECONDS:
            shutil.rmtree(path, ignore_errors=True)


def init_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("last_results", None)
    st.session_state.setdefault("last_message", "")
    st.session_state.setdefault("work_dir", None)
    st.session_state.setdefault("last_input_name", "ljm_output")
    st.session_state.setdefault("last_uploaded_file_id", None)

    if not st.session_state.get("stale_cleanup_done"):
        cleanup_stale_work_dirs()
        st.session_state["stale_cleanup_done"] = True


def ensure_work_dir() -> Path:
    work_dir = st.session_state.get("work_dir")
    if work_dir:
        path = Path(work_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    path = Path(tempfile.mkdtemp(prefix="ljm_streamlit_"))
    st.session_state["work_dir"] = str(path)
    return path


def save_uploaded_file(uploaded_file, work_dir: Path) -> Path:
    input_dir = work_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(uploaded_file.name).name
    target = input_dir / safe_name
    with target.open("wb") as handle:
        shutil.copyfileobj(uploaded_file, handle)
    return target


def resolve_week1() -> date:
    picked = st.session_state["week1"]
    return picked - timedelta(days=picked.weekday())


def resolve_expected_weeks() -> int:
    choice = st.session_state["week_count_choice"]
    if choice in WEEK_COUNT_VALUES:
        return WEEK_COUNT_VALUES[choice]
    return int(st.session_state["expected_weeks_custom"])


def build_command(input_path: Path, output_dir: Path) -> list[str]:
    base_name = input_path.stem
    command = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
        "--base-name",
        base_name,
        "--render-target",
        st.session_state["render_target"],
        "--layout-mode",
        st.session_state["layout_mode"],
        "--week1",
        resolve_week1().isoformat(),
        "--expected-weeks",
        str(resolve_expected_weeks()),
        "--no-pdf",
    ]

    command.extend([
        "--mlo-header-size",
        str(st.session_state["mlo_header_size"]),
        "--mlo-code-size",
        str(st.session_state["mlo_code_size"]),
        "--mlo-title-size",
        str(st.session_state["mlo_title_size"]),
        "--mlo-desc-size",
        str(st.session_state["mlo_desc_size"]),
        "--mlo-line-spacing",
        str(st.session_state["mlo_line_spacing"]),
        "--mlo-header-line-gap",
        str(st.session_state["mlo_header_line_gap"]),
    ])

    return command


def build_multipage_pdf(png_paths: list[Path], pdf_path: Path) -> None:
    images: list[Image.Image] = []
    for png_path in png_paths:
        with Image.open(png_path) as image:
            has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
            if has_alpha:
                rgba = image.convert("RGBA")
                page = Image.new("RGB", rgba.size, PDF_PAGE_BG)
                page.paste(rgba, mask=rgba.split()[-1])
            else:
                page = image.convert("RGB")
            images.append(page)

    if not images:
        raise ValueError("No PNG files available to build the PDF.")

    first, rest = images[0], images[1:]
    first.save(pdf_path, save_all=True, append_images=rest)


def run_pipeline(uploaded_file) -> dict[str, Path]:
    work_dir = ensure_work_dir()
    input_path = save_uploaded_file(uploaded_file, work_dir)
    st.session_state["last_input_name"] = input_path.stem
    output_dir = work_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    command = build_command(input_path, output_dir)
    completed = subprocess.run(command, capture_output=True, text=True)

    st.session_state["last_message"] = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")

    if completed.returncode != 0:
        stderr_lines = [line for line in completed.stderr.strip().splitlines() if line]
        reason = stderr_lines[-1] if stderr_lines else ""
        if reason.startswith("[FAIL] "):
            reason = reason[len("[FAIL] "):]
        if not reason:
            reason = f"Something went wrong while generating (exit code {completed.returncode}). Please try again."
        raise RuntimeError(reason)

    base_name = input_path.stem
    results: dict[str, Path] = {}

    review = output_dir / f"{base_name}_review.txt"
    data = output_dir / f"{base_name}_data.json"
    ljm_png = output_dir / f"{base_name}.png"
    mlo_png = output_dir / f"{base_name}_mlos.png"

    if review.exists():
        results["review"] = review
    if data.exists():
        results["data"] = data
    if ljm_png.exists():
        results["ljm_png"] = ljm_png
    if mlo_png.exists():
        results["mlo_png"] = mlo_png

    png_pages: list[Path] = []
    if st.session_state["render_target"] in ("mlo", "both") and mlo_png.exists():
        png_pages.append(mlo_png)
    if st.session_state["render_target"] in ("ljm", "both") and ljm_png.exists():
        png_pages.append(ljm_png)
    if png_pages:
        pdf_target = output_dir / f"{base_name}_combined.pdf"
        build_multipage_pdf(png_pages, pdf_target)
        results["pdf"] = pdf_target

    return results


def file_bytes(path: Path) -> bytes:
    return path.read_bytes()


def build_zip(results: dict[str, Path], base_name: str) -> bytes:
    names = {
        "pdf": f"{base_name}_combined.pdf",
        "mlo_png": f"{base_name}_mlos.png",
        "ljm_png": f"{base_name}.png",
        "review": f"{base_name}_review.txt",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for key, filename in names.items():
            if key in results:
                archive.write(results[key], arcname=filename)
    return buffer.getvalue()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    # Scoped to just the file uploader's own button, not buttons elsewhere in the app.
    # Also scoped to the primary button inside st.columns (the "Generate" button) so it
    # doesn't affect the other primary button ("Download all as ZIP"), which isn't in a column.
    st.markdown(
        """
        <style>
        div[data-testid="stFileUploader"] button:hover {
            background-color: #195C4D !important;
            border-color: #195C4D !important;
            color: #E7F95D !important;
        }
        div[data-testid="stColumn"] button[data-testid="stBaseButton-primary"]:not(:disabled),
        div[data-testid="stColumn"] button[data-testid="stBaseButton-primary"]:not(:disabled) p {
            color: #E7F95D !important;
        }
        /* Pull "LJM height options" up closer to the divider above it. */
        section[data-testid="stSidebar"] hr {
            margin-bottom: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(APP_TITLE)
    st.subheader(APP_SUBTITLE)

    with st.sidebar:
        if False:
            st.session_state["render_target"] = st.radio(
                "Render target",
                options=["ljm", "mlo", "both"],
                index=["ljm", "mlo", "both"].index(st.session_state["render_target"]),
                format_func=lambda value: {"ljm": "LJM", "mlo": "MLO", "both": "Both"}[value],
            )
        st.subheader("Term Start Picker")
        st.session_state["week1"] = st.date_input("Term start (Week 1 Monday)", value=st.session_state["week1"])
        snapped_monday = resolve_week1()
        snapped_friday = snapped_monday + timedelta(days=4)
        st.caption(f"Week 1 will run Mon {snapped_monday:%d %b %Y} – Fri {snapped_friday:%d %b %Y}.")

        st.session_state["week_count_choice"] = st.radio(
            "Number of teaching weeks",
            options=WEEK_COUNT_OPTIONS,
            index=WEEK_COUNT_OPTIONS.index(st.session_state["week_count_choice"]),
            horizontal=True,
        )
        if st.session_state["week_count_choice"] == "Custom":
            st.session_state["expected_weeks_custom"] = st.number_input(
                "Custom week count",
                min_value=1,
                max_value=30,
                value=int(st.session_state["expected_weeks_custom"]),
            )
        st.caption("A 2-week Easter break is inserted automatically if the term covers it.")

        st.divider()

        st.subheader("LJM height options")
        st.session_state["layout_mode"] = st.radio(
            "Layout mode",
            options=["flex-height", "standard", "fit-fixed"],
            index=["flex-height", "standard", "fit-fixed"].index(st.session_state["layout_mode"]),
            format_func=lambda value: {"flex-height": "Flexi-height", "standard": "Fixed", "fit-fixed": "Fixed + fit"}[value],
        )
        st.caption("PDF, PNGs, and the review text are all generated together.")

        if False:
            with st.expander("Advanced MLO controls", expanded=False):
                st.session_state["mlo_header_size"] = st.number_input("Header size", min_value=20, max_value=120, value=int(st.session_state["mlo_header_size"]))
                st.session_state["mlo_code_size"] = st.number_input("Code size", min_value=20, max_value=120, value=int(st.session_state["mlo_code_size"]))
                st.session_state["mlo_title_size"] = st.number_input("Title size", min_value=20, max_value=120, value=int(st.session_state["mlo_title_size"]))
                st.session_state["mlo_desc_size"] = st.number_input("Description size", min_value=20, max_value=120, value=int(st.session_state["mlo_desc_size"]))
                st.session_state["mlo_line_spacing"] = st.number_input("Description line spacing", min_value=0, max_value=30, value=int(st.session_state["mlo_line_spacing"]))
                st.session_state["mlo_header_line_gap"] = st.number_input("Header line gap", min_value=0, max_value=30, value=int(st.session_state["mlo_header_line_gap"]))

    uploaded_file = st.file_uploader("Drag and drop your Learner Journey Map here, or click Upload to browse.", type=["docx"])

    current_file_id = uploaded_file.file_id if uploaded_file is not None else None
    if current_file_id != st.session_state["last_uploaded_file_id"]:
        st.session_state["last_results"] = None
        st.session_state["last_message"] = ""
        st.session_state["last_uploaded_file_id"] = current_file_id

    col1, col2 = st.columns([1, 1])
    with col1:
        generate = st.button("Generate PDF and PNGs", type="primary", disabled=uploaded_file is None)
    with col2:
        if False:
            if st.button("Reset workspace"):
                st.session_state["last_results"] = None
                st.session_state["last_message"] = ""
                work_dir = st.session_state.get("work_dir")
                if work_dir:
                    shutil.rmtree(Path(work_dir), ignore_errors=True)
                st.session_state["work_dir"] = None
                st.rerun()

    if generate and uploaded_file is not None:
        with st.spinner("Running the renderer..."):
            try:
                results = run_pipeline(uploaded_file)
                st.session_state["last_results"] = results
                st.success("Rendering complete.")
            except Exception as exc:
                st.session_state["last_results"] = None
                st.error(str(exc))

    if False:
        if st.session_state.get("last_message"):
            with st.expander("Pipeline log", expanded=False):
                st.text(st.session_state["last_message"])

    results = st.session_state.get("last_results") or {}
    if results:
        st.subheader("Downloads")
        base_name = st.session_state.get("last_input_name", "ljm_output")

        st.download_button(
            "Download all as ZIP",
            data=build_zip(results, base_name),
            file_name=f"{base_name}_assets.zip",
            mime="application/zip",
            type="primary",
        )

        if "pdf" in results:
            st.download_button(
                "Download PDF",
                data=file_bytes(results["pdf"]),
                file_name=f"{base_name}_combined.pdf",
                mime="application/pdf",
            )

        if "mlo_png" in results:
            st.download_button(
                "Download MLO PNG",
                data=file_bytes(results["mlo_png"]),
                file_name=f"{base_name}_mlos.png",
                mime="image/png",
            )

        if "ljm_png" in results:
            st.download_button(
                "Download LJM PNG",
                data=file_bytes(results["ljm_png"]),
                file_name=f"{base_name}.png",
                mime="image/png",
            )

        if "review" in results:
            st.download_button(
                "Download review text",
                data=file_bytes(results["review"]),
                file_name=f"{base_name}_review.txt",
                mime="text/plain",
            )

        if False:
            if "data" in results:
                st.download_button(
                    "Download JSON data",
                    data=file_bytes(results["data"]),
                    file_name=f"{base_name}_data.json",
                    mime="application/json",
                )


if __name__ == "__main__":
    main()