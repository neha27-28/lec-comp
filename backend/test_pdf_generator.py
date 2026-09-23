from pathlib import Path
import tempfile

from PIL import Image, ImageDraw

from services.pdf_generator import create_slides_pdf


def create_test_slide(
    path: Path,
    number: int,
) -> None:

    image = Image.new(
        "RGB",
        (1280, 720),
        "white",
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (100, 100),
        f"Lecture Companion - Test Slide {number}",
        fill="black",
    )

    image.save(
        path,
        format="JPEG",
    )


def main() -> None:

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(temp_dir)

        slide_1 = temp_path / "slide_001.jpg"
        slide_2 = temp_path / "slide_002.jpg"
        slide_3 = temp_path / "slide_003.jpg"

        create_test_slide(
            slide_1,
            1,
        )

        create_test_slide(
            slide_2,
            2,
        )

        create_test_slide(
            slide_3,
            3,
        )

        slides = [
            {
                "slide_number": 1,
                "image_path": str(slide_1),
            },
            {
                "slide_number": 2,
                "image_path": str(slide_2),
            },
            {
                "slide_number": 3,
                "image_path": str(slide_3),
            },
        ]

        output_pdf = temp_path / "lecture_slides.pdf"

        result = create_slides_pdf(
            slides=slides,
            output_path=output_pdf,
        )

        assert result.exists()
        assert result.stat().st_size > 0

        print()
        print("PDF generator test passed.")
        print(f"PDF created at: {result}")
        print(f"PDF size: {result.stat().st_size} bytes")


if __name__ == "__main__":
    main()
