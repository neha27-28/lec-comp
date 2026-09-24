from pathlib import Path

from services.audio_processor import extract_audio


BASE_DIR = Path(__file__).resolve().parent

VIDEO_DIR = BASE_DIR / "data" / "input" / "4c674654"
AUDIO_DIR = BASE_DIR / "data" / "audio"

VIDEO_PATH = next(VIDEO_DIR.glob("*.mp4"))
AUDIO_PATH = AUDIO_DIR / "4c674654.wav"


def main():
    print(f"Video: {VIDEO_PATH}")

    extract_audio(
        video_path=str(VIDEO_PATH),
        output_path=str(AUDIO_PATH),
    )

    print()
    print("Audio extraction completed successfully.")
    print(f"Output: {AUDIO_PATH}")


if __name__ == "__main__":
    main()