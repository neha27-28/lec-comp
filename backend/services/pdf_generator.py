"""
services/pdf_generator.py
-------------------------

Secure PDF generation for Lecture Companion.

Responsibilities:
- Validate slide image paths
- Validate output PDF path
- Prevent unsafe output paths
- Preserve slide aspect ratio
- Generate landscape A4 PDF
- Clean up incomplete PDFs after failure

The PDF filename is decided by main.py.
This module only generates the PDF at the supplied path.
"""

from pathlib import Path
import logging

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


# ============================================================
# PATH VALIDATION
# ============================================================

def _validate_output_path(
    output_path: str | Path,
) -> Path:
    """
    Validate and prepare the PDF output path.
    """

    path = Path(
        output_path
    ).resolve()

    if path.suffix.lower() != ".pdf":
        raise ValueError(
            "PDF output path must end with .pdf."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not path.parent.is_dir():
        raise ValueError(
            "PDF output directory is invalid."
        )

    return path


def _validate_slide_path(
    slide_path: str | Path,
) -> Path:
    """
    Validate an extracted slide image.
    """

    path = Path(
        slide_path
    ).resolve()

    if not path.exists():
        raise ValueError(
            f"Slide image does not exist: {path.name}"
        )

    if not path.is_file():
        raise ValueError(
            f"Slide path is not a file: {path.name}"
        )

    if path.suffix.lower() not in (
        SUPPORTED_IMAGE_EXTENSIONS
    ):
        raise ValueError(
            f"Unsupported slide image format: {path.name}"
        )

    return path


# ============================================================
# IMAGE VALIDATION
# ============================================================

def _get_image_dimensions(
    image_path: Path,
) -> tuple[int, int]:
    """
    Read image dimensions safely.
    """

    try:

        with Image.open(
            image_path
        ) as image:

            width, height = image.size

    except Exception as exc:

        raise ValueError(
            f"Could not read slide image: "
            f"{image_path.name}"
        ) from exc

    if width <= 0 or height <= 0:
        raise ValueError(
            f"Invalid slide dimensions: "
            f"{image_path.name}"
        )

    return width, height


# ============================================================
# IMAGE SCALING
# ============================================================

def _fit_image_to_page(
    image_width: int,
    image_height: int,
    page_width: float,
    page_height: float,
) -> tuple[
    float,
    float,
    float,
    float,
]:
    """
    Calculate centered dimensions while preserving
    the original image aspect ratio.

    Returns:
        x, y, width, height
    """

    margin = 24

    available_width = (
        page_width -
        (2 * margin)
    )

    available_height = (
        page_height -
        (2 * margin)
    )

    scale = min(
        available_width / image_width,
        available_height / image_height,
    )

    draw_width = (
        image_width * scale
    )

    draw_height = (
        image_height * scale
    )

    x = (
        page_width -
        draw_width
    ) / 2

    y = (
        page_height -
        draw_height
    ) / 2

    return (
        x,
        y,
        draw_width,
        draw_height,
    )


# ============================================================
# PDF GENERATION
# ============================================================

def create_slides_pdf(
    slides: list,
    output_path: str | Path,
) -> str:
    """
    Generate a PDF containing the extracted unique slides.

    The caller decides the final PDF filename.

    Parameters
    ----------
    slides:
        List of slide records returned by the slide detector.

    output_path:
        Complete destination path of the generated PDF.

    Returns
    -------
    str
        Absolute path to the generated PDF.
    """

    output_path = _validate_output_path(
        output_path
    )

    if not slides:
        raise ValueError(
            "No slides were provided for PDF generation."
        )

    slide_paths = []

    for slide in slides:

        if isinstance(
            slide,
            str,
        ):
            slide_path = slide

        elif isinstance(
            slide,
            dict,
        ):
            slide_path = (
                slide.get(
                    "representative_path"
                )
                or slide.get(
                    "image_path"
                )
            )

        else:
            slide_path = None

        if not slide_path:

            logger.warning(
                "Skipping slide without an image path."
            )

            continue

        slide_paths.append(
            _validate_slide_path(
                slide_path
            )
        )

    if not slide_paths:
        raise ValueError(
            "No valid slide images were found."
        )

    logger.info(
        "Generating slides PDF: %s slides -> %s",
        len(slide_paths),
        output_path.name,
    )

    # Remove any previous PDF.
    try:

        output_path.unlink(
            missing_ok=True
        )

    except OSError:

        logger.exception(
            "Could not remove existing PDF: %s",
            output_path,
        )

        raise

    try:

        pdf = canvas.Canvas(
            str(output_path),
            pagesize=landscape(A4),
        )

        for slide_path in slide_paths:

            image_width, image_height = (
                _get_image_dimensions(
                    slide_path
                )
            )

            (
                x,
                y,
                draw_width,
                draw_height,
            ) = _fit_image_to_page(
                image_width=image_width,
                image_height=image_height,
                page_width=PAGE_WIDTH,
                page_height=PAGE_HEIGHT,
            )

            image = ImageReader(
                str(slide_path)
            )

            pdf.drawImage(
                image,
                x,
                y,
                width=draw_width,
                height=draw_height,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )

            pdf.showPage()

        pdf.save()

    except Exception:

        logger.exception(
            "PDF generation failed."
        )

        # Remove incomplete PDF.
        try:

            output_path.unlink(
                missing_ok=True
            )

        except OSError:

            logger.exception(
                "Could not remove incomplete PDF: %s",
                output_path,
            )

        raise

    # --------------------------------------------------------
    # Final output validation
    # --------------------------------------------------------

    if not output_path.is_file():

        raise RuntimeError(
            "PDF generation completed but "
            "the output file was not created."
        )

    if output_path.stat().st_size <= 0:

        output_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "Generated PDF is empty."
        )

    logger.info(
        "Slides PDF generated successfully: %s",
        output_path,
    )

    return str(
        output_path
    )