from pathlib import Path
from typing import Any
import json
import whisper
import torch


# ============================================================
# Configuration
# ============================================================

# English lecture:
#   small.en -> better accuracy than base while remaining
#   practical on CPU.
#
# If your lectures can contain Hindi/Hinglish, change this to:
#   "small"
#
MODEL_NAME = "small.en"

# CPU is currently being used because torch.cuda.is_available()
# is False on this machine.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# CPU must use FP32.
FP16 = DEVICE == "cuda"


# ============================================================
# Model loading
# ============================================================

_model = None


def get_model():
    """
    Load Whisper once and reuse it.

    Loading Whisper for every request would be extremely slow,
    so the model is cached in memory.
    """
    global _model

    if _model is None:
        print(f"Loading Whisper model: {MODEL_NAME}")
        print(f"Device: {DEVICE}")

        _model = whisper.load_model(
            MODEL_NAME,
            device=DEVICE
        )

        print("Whisper model loaded successfully.")

    return _model


# ============================================================
# Text cleanup
# ============================================================

def clean_text(text: str) -> str:
    """
    Normalize Whisper text slightly without changing its meaning.
    """
    if not text:
        return ""

    text = " ".join(text.split())

    return text.strip()


# ============================================================
# Main transcription function
# ============================================================

def transcribe_audio(
    audio_path: str,
    output_path: str | None = None,
) -> dict[str, Any]:

    audio_file = Path(audio_path)

    if not audio_file.exists():
        raise FileNotFoundError(
            f"Audio file does not exist: {audio_file}"
        )

    model = get_model()

    print()
    print("=" * 70)
    print("Starting Whisper transcription")
    print("=" * 70)
    print(f"Audio : {audio_file}")
    print(f"Model : {MODEL_NAME}")
    print(f"Device: {DEVICE}")
    print()

    # --------------------------------------------------------
    # Initial prompt
    # --------------------------------------------------------
    #
    # This helps Whisper understand that this is educational /
    # technical speech. It can improve recognition of technical
    # vocabulary without forcing the transcript to contain it.
    #
    initial_prompt = (
        "This is an educational lecture. "
        "The speaker may discuss computer science, "
        "programming, algorithms, software development, "
        "data structures, mathematics, and technical concepts."
    )

    # --------------------------------------------------------
    # Transcription
    # --------------------------------------------------------

    result = model.transcribe(
        str(audio_file),

        # Explicitly transcribe rather than translate.
        task="transcribe",

        # For English lectures this avoids unnecessary language
        # ambiguity.
        language="en",

        # Produce word-level timing information.
        word_timestamps=True,

        # More robust decoding.
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),

        # Whisper's silence detection.
        no_speech_threshold=0.6,

        # Avoid getting trapped in repetitive decoding loops.
        #
        # This is particularly useful for long lecture recordings.
        condition_on_previous_text=False,

        # Help with technical vocabulary.
        initial_prompt=initial_prompt,

        # CPU cannot use FP16.
        fp16=FP16,

        # Don't print Whisper's own progress lines.
        verbose=False,
    )

    # ========================================================
    # Normalize the result into our own stable data structure
    # ========================================================

    segments = []

    for index, segment in enumerate(result.get("segments", [])):

        text = clean_text(segment.get("text", ""))

        if not text:
            continue

        words = []

        for word in segment.get("words", []):
            word_text = clean_text(word.get("word", ""))

            if not word_text:
                continue

            words.append({
                "word": word_text,
                "start": float(word["start"]),
                "end": float(word["end"]),
            })

        normalized_segment = {
            "id": index,
            "start": float(segment["start"]),
            "end": float(segment["end"]),
            "text": text,
            "words": words,
        }

        segments.append(normalized_segment)

    transcription = {
        "audio_file": str(audio_file),
        "model": MODEL_NAME,
        "device": DEVICE,
        "language": result.get("language", "en"),
        "text": clean_text(result.get("text", "")),
        "segments": segments,
    }

    # ========================================================
    # Optional JSON output
    # ========================================================

    if output_path is not None:

        output_file = Path(output_path)

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with output_file.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                transcription,
                file,
                indent=2,
                ensure_ascii=False
            )

        print()
        print(f"Transcript saved to:")
        print(output_file)

    # ========================================================
    # Summary
    # ========================================================

    print()
    print("=" * 70)
    print("TRANSCRIPTION COMPLETE")
    print("=" * 70)
    print(f"Language : {transcription['language']}")
    print(f"Segments : {len(segments)}")
    print()

    for segment in segments:
        print(
            f"[{segment['start']:8.2f} - "
            f"{segment['end']:8.2f}] "
            f"{segment['text']}"
        )

    return transcription