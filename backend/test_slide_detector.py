from pathlib import Path
import argparse

from services.slide_detector import detect_slides


FPS = 3.0


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

    args = parser.parse_args()

    slides = detect_slides(
        frames_dir=args.frames_dir,
        output_dir=args.slides_dir,
    )

    print()
    print("=" * 60)
    print("SLIDE TIMELINE")
    print("=" * 60)

    for slide in slides:

        print()
        print(f"Slide {slide['slide_id']}")
        print(f"Image: {slide['representative_path']}")
        print(f"Occurrences: {len(slide['occurrences'])}")

        for occurrence in slide["occurrences"]:

            start_frame = occurrence["start_frame"]
            end_frame = occurrence["end_frame"]

            start_time = start_frame / FPS
            end_time = (end_frame + 1) / FPS

            print(
                f"  Occurrence {occurrence['appearance_index']}: "
                f"{start_time:.2f}s → {end_time:.2f}s "
                f"({start_frame} → {end_frame})"
            )


if __name__ == "__main__":
    main()