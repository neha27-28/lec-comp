from pathlib import Path
import json

from services.slide_detector import detect_slides
from services.slide_speech_linker import link_slides_to_speech


# ============================================================
# CONFIGURATION
# ============================================================

JOB_ID = "4c674654"
FPS = 3.0

FRAMES_DIR = Path("data/frames") / JOB_ID
SLIDES_DIR = Path("data/slides") / JOB_ID
TRANSCRIPT_PATH = (
    Path("data/results")
    / f"{JOB_ID}_transcript.json"
)
OUTPUT_PATH = (
    Path("data/results")
    / f"{JOB_ID}_slide_speech.json"
)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 60)
    print("LECTURE COMPANION - SLIDE/SPEECH LINKER")
    print("=" * 60)

    # --------------------------------------------------------
    # Validate input paths
    # --------------------------------------------------------

    if not FRAMES_DIR.is_dir():
        raise FileNotFoundError(
            f"Frames directory not found: {FRAMES_DIR}"
        )

    if not TRANSCRIPT_PATH.is_file():
        raise FileNotFoundError(
            f"Transcript not found: {TRANSCRIPT_PATH}"
        )

    print(f"Frames directory : {FRAMES_DIR}")
    print(f"Transcript       : {TRANSCRIPT_PATH}")
    print(f"FPS              : {FPS}")

    # --------------------------------------------------------
    # Run slide detector
    # --------------------------------------------------------

    print()
    print("Running slide detector...")

    slides = detect_slides(
        frames_dir=str(FRAMES_DIR),
        output_dir=str(SLIDES_DIR),
    )

    print(
        f"Detected {len(slides)} unique slides."
    )

    # --------------------------------------------------------
    # Load Whisper transcript
    # --------------------------------------------------------

    print()
    print("Loading Whisper transcript...")

    with TRANSCRIPT_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        transcript = json.load(file)

    segments = transcript.get("segments", [])

    print(
        f"Loaded {len(segments)} transcript segments."
    )

    # --------------------------------------------------------
    # Link slides and speech
    # --------------------------------------------------------

    print()
    print("Linking slides with speech...")

    result = link_slides_to_speech(
        slides=slides,
        transcript=transcript,
        fps=FPS,
    )

    # --------------------------------------------------------
    # Save result
    # --------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "job_id": JOB_ID,
                **result,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_occurrences = result[
        "appearance_count"
    ]

    slides_with_speech = sum(
        1
        for slide in result["slides"]
        if slide["speech_text"]
    )

    print()
    print("=" * 60)
    print("LINKING COMPLETED")
    print("=" * 60)

    print(
        f"Unique slides       : "
        f"{result['slide_count']}"
    )

    print(
        f"Slide appearances   : "
        f"{total_occurrences}"
    )

    print(
        f"Transcript segments : "
        f"{len(segments)}"
    )

    print(
        f"Slides with speech  : "
        f"{slides_with_speech}"
    )

    print()
    print(
        f"Output saved to:\n"
        f"{OUTPUT_PATH}"
    )

    # --------------------------------------------------------
    # Preview
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("LINKING PREVIEW")
    print("=" * 60)

    for slide in result["slides"]:

        print()
        print(
            f"Slide {slide['slide_id']} "
            f"({len(slide['occurrences'])} occurrences)"
        )

        for occurrence in slide["occurrences"]:

            text = occurrence["speech_text"]

            if len(text) > 180:
                text = text[:180] + "..."

            print(
                f"  "
                f"{occurrence['start_time']:.2f}s → "
                f"{occurrence['end_time']:.2f}s"
            )

            if text:
                print(
                    f"    Speech: {text}"
                )
            else:
                print(
                    "    Speech: [no speech detected]"
                )


if __name__ == "__main__":
    main()