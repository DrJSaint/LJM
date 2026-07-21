from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st
from PIL import Image


APP_TITLE = "LJM Renderer Demo"
APP_SUBTITLE = "Upload a Word document and generate LJM and/or MLO assets from the existing pipeline."

REPO_ROOT = Path(__file__).resolve().parent
PIPELINE_SCRIPT = REPO_ROOT / "python scripts" / "make_student_journey_map.py"

DEFAULTS = {
    "render_target": "both",
    "layout_mode": "flex-height",
    "output_type": "png",
    "mlo_header_size": 52,
    "mlo_code_size": 52,
    "mlo_title_size": 37,
    "mlo_desc_size": 37,
    "mlo_line_spacing": 8,
    "mlo_header_line_gap": 0,
}

PDF_PAGE_BG = (247, 241, 232)


def init_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("last_results", None)
    st.session_state.setdefault("last_message", "")
    st.session_state.setdefault("work_dir", None)
    st.session_state.setdefault("last_input_name", "ljm_output")


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
    target = input_dir / uploaded_file.name
    with target.open("wb") as handle:
        shutil.copyfileobj(uploaded_file, handle)
    return target


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
    ]

    if st.session_state["output_type"] == "png":
        command.append("--no-pdf")

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
        raise RuntimeError(f"Pipeline failed with exit code {completed.returncode}")

    base_name = input_path.stem
    results: dict[str, Path] = {}

    review = output_dir / f"{base_name}_review.txt"
    data = output_dir / f"{base_name}_data.json"
    ljm_png = output_dir / f"{base_name}.png"
    mlo_png = output_dir / f"{base_name}_mlos.png"
    pdf = output_dir / f"{base_name}.pdf"

    if review.exists():
        results["review"] = review
    if data.exists():
        results["data"] = data
    if ljm_png.exists():
        results["ljm_png"] = ljm_png
    if mlo_png.exists():
        results["mlo_png"] = mlo_png
    if pdf.exists():
        results["pdf"] = pdf

    if st.session_state["output_type"] == "pdf":
        pdf_target = output_dir / f"{base_name}_combined.pdf"
        png_pages: list[Path] = []
        if st.session_state["render_target"] in ("mlo", "both") and mlo_png.exists():
            png_pages.append(mlo_png)
        if st.session_state["render_target"] in ("ljm", "both") and ljm_png.exists():
            png_pages.append(ljm_png)
        if png_pages:
            build_multipage_pdf(png_pages, pdf_target)
            results["pdf"] = pdf_target

    return results


def file_bytes(path: Path) -> bytes:
    return path.read_bytes()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    with st.sidebar:
        st.header("Options")
        st.session_state["render_target"] = st.radio(
            "Render target",
            options=["ljm", "mlo", "both"],
            index=["ljm", "mlo", "both"].index(st.session_state["render_target"]),
            format_func=lambda value: {"ljm": "LJM", "mlo": "MLO", "both": "Both"}[value],
        )
        st.session_state["layout_mode"] = st.radio(
            "Layout mode",
            options=["flex-height", "standard", "fit-fixed"],
            index=["flex-height", "standard", "fit-fixed"].index(st.session_state["layout_mode"]),
            format_func=lambda value: {"flex-height": "Flexi-height", "standard": "Fixed", "fit-fixed": "Fixed + fit"}[value],
        )
        st.session_state["output_type"] = st.radio(
            "Download type",
            options=["png", "pdf"],
            index=["png", "pdf"].index(st.session_state["output_type"]),
            format_func=lambda value: "PNG(s)" if value == "png" else "PDF (single file)",
        )
        st.caption("PDF output is assembled from the generated PNGs.")

        if False:
            with st.expander("Advanced MLO controls", expanded=False):
                st.session_state["mlo_header_size"] = st.number_input("Header size", min_value=20, max_value=120, value=int(st.session_state["mlo_header_size"]))
                st.session_state["mlo_code_size"] = st.number_input("Code size", min_value=20, max_value=120, value=int(st.session_state["mlo_code_size"]))
                st.session_state["mlo_title_size"] = st.number_input("Title size", min_value=20, max_value=120, value=int(st.session_state["mlo_title_size"]))
                st.session_state["mlo_desc_size"] = st.number_input("Description size", min_value=20, max_value=120, value=int(st.session_state["mlo_desc_size"]))
                st.session_state["mlo_line_spacing"] = st.number_input("Description line spacing", min_value=0, max_value=30, value=int(st.session_state["mlo_line_spacing"]))
                st.session_state["mlo_header_line_gap"] = st.number_input("Header line gap", min_value=0, max_value=30, value=int(st.session_state["mlo_header_line_gap"]))

    uploaded_file = st.file_uploader("Upload a Learner Journey Map Word document", type=["docx"])

    col1, col2 = st.columns([1, 1])
    with col1:
        generate = st.button("Generate assets", type="primary", disabled=uploaded_file is None)
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

        if st.session_state["output_type"] == "png" and st.session_state["render_target"] in ("ljm", "both") and "ljm_png" in results:
            st.download_button(
                "Download LJM PNG",
                data=file_bytes(results["ljm_png"]),
                file_name=f"{base_name}.png",
                mime="image/png",
            )

        if st.session_state["output_type"] == "png" and st.session_state["render_target"] in ("mlo", "both") and "mlo_png" in results:
            st.download_button(
                "Download MLO PNG",
                data=file_bytes(results["mlo_png"]),
                file_name=f"{base_name}_mlos.png",
                mime="image/png",
            )

        if st.session_state["output_type"] == "pdf" and "pdf" in results:
            st.download_button(
                "Download PDF",
                data=file_bytes(results["pdf"]),
                file_name=f"{base_name}_combined.pdf",
                mime="application/pdf",
            )


if __name__ == "__main__":
    main()