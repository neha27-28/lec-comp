from pathlib import Path
import subprocess


def extract_audio(video_path: str, output_path: str) -> str:
    """
    Extract lecture audio from a video and normalize it for Whisper.

    Output:
        16 kHz, mono, PCM WAV
    """

    video_file = Path(video_path)
    audio_file = Path(output_path)

    if not video_file.exists():
        raise FileNotFoundError(f"Video not found: {video_file}")

    audio_file.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-i",
        str(video_file),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio_file),
        "-y",
    ]

    subprocess.run(command, check=True)

    if not audio_file.exists():
        raise RuntimeError("Audio extraction failed.")

    print(f"Audio extracted to: {audio_file}")

    return str(audio_file)