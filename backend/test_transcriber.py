from pathlib import Path

from services.transcriber import transcribe_audio


BASE_DIR = Path(__file__).resolve().parent

AUDIO_FILE = (
    BASE_DIR
    / "data"
    / "audio"
    / "4c674654.wav"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "results"
    / "4c674654_transcript.json"
)


if __name__ == "__main__":

    print("=" * 70)
    print("LECTURE COMPANION — TRANSCRIPTION TEST")
    print("=" * 70)

    result = transcribe_audio(
        audio_path=str(AUDIO_FILE),
        output_path=str(OUTPUT_FILE),
    )

    print()
    print("=" * 70)
    print("TEST FINISHED")
    print("=" * 70)

    print(f"Audio     : {AUDIO_FILE}")
    print(f"Transcript: {OUTPUT_FILE}")
    print(f"Segments  : {len(result['segments'])}")