from __future__ import annotations

from pathlib import Path

from PIL import Image


def create_slides_pdf(
    slides: list[dict],
    output_path: str | Path,
) -> Path:
    """
    Create a PDF containing one page per unique slide.

    The current slide detector returns the saved unique-slide image
    under "representative_path". The fallback to "image_path" keeps
    this helper compatible with an older detector interface.
    """

    output_path = Path(output_path)

    if not slides:
        raise ValueError("Cannot create a PDF because no slides were detected.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    images: list[Image.Image] = []

    try:
        for slide in slides:
            image_value = slide.get("representative_path") or slide.get("image_path")

            if not image_value:
                raise KeyError(
                    "Slide result contains neither 'representative_path' nor 'image_path'."
                )

            image_path = Path(image_value)

            if not image_path.exists():
                raise FileNotFoundError(f"Slide image not found: {image_path}")

            image = Image.open(image_path).convert("RGB")
            images.append(image)

        images[0].save(
            output_path,
            format="PDF",
            save_all=True,
            append_images=images[1:],
            resolution=150.0,
        )

    finally:
        for image in images:
            image.close()

    return output_path
