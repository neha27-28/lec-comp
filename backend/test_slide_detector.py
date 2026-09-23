from pathlib import Path
import argparse

from services.slide_detector import detect_slides


def main() -> None:

    parser = argparse.ArgumentParser(
        description="Run Lecture Companion slide detection."
    )

    parser.add_argument(
        "frames_dir",
        type=Path,
        help="Directory containing extracted frames.",
    )

    parser.add_argument(
        "slides_dir",
        type=Path,
        help="Directory where detected slides will be saved.",
    )

    parser.add_argument(
        "--fps",
        type=float,
        default=2.0,
        help="Frame extraction rate. Default: 2.0",
    )

    args = parser.parse_args()

    slides = detect_slides(
        frames_dir=args.frames_dir,
        output_dir=args.slides_dir,
        fps=args.fps,
    )

    print()
    print("Slide detection completed!")
    print(f"Unique slides detected: {len(slides)}")

    for slide in slides:

        print()
        print(f"Slide {slide['slide_number']}")

        print(f"Image: {slide['image_path']}")

        print(f"Timestamp: " f"{slide.get('timestamp', 0.0):.2f}s")

        print(f"Occurrences: " f"{len(slide['occurrences'])}")


if __name__ == "__main__":
    main()
