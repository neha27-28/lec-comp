from __future__ import annotations

import logging
import subprocess
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

# Maximum time FFmpeg is allowed to run during audio extraction.
#
# This is a resource-exhaustion safeguard.
# It is NOT a lecture-duration limit.
#
# Example:
# A 2-hour lecture can still be processed normally if FFmpeg
# finishes extracting its audio within this time.
FFMPEG_TIMEOUT_SECONDS = 60 * 60  # 1 hour


# Supported input video formats.
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".mkv",
}


# Audio output must be WAV.
REQUIRED_OUTPUT_EXTENSION = ".wav"


logger = logging.getLogger(__name__)


# ============================================================
# PATH VALIDATION
# ============================================================

def _validate_video_path(
    video_path: str | Path,
) -> Path:
    """
    Validate the input video path.

    Security properties:
    - resolves the path
    - requires the path to exist
    - requires a regular file
    - restricts supported video extensions
    """

    path = Path(video_path).resolve()

    if not path.exists():
        raise FileNotFoundError(
            "Input video does not exist."
        )

    if not path.is_file():
        raise ValueError(
            "Input video path is not a file."
        )

    if path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError(
            "Unsupported video format."
        )

    return path


def _validate_output_path(
    output_path: str | Path,
) -> Path:
    """
    Validate the destination WAV path.

    The parent directory is created if necessary.
    """

    path = Path(output_path).resolve()

    if path.suffix.lower() != REQUIRED_OUTPUT_EXTENSION:
        raise ValueError(
            "Audio output must use the .wav extension."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not path.parent.is_dir():
        raise ValueError(
            "Audio output directory is not valid."
        )

    return path


def _ensure_inside_directory(
    path: Path,
    parent: Path,
) -> Path:
    """
    Ensure a generated output path remains inside its
    intended directory.

    Prevents path traversal / directory escape.
    """

    path = path.resolve()
    parent = parent.resolve()

    try:
        path.relative_to(parent)

    except ValueError as exc:
        raise RuntimeError(
            "Audio output path escaped the job directory."
        ) from exc

    return path


# ============================================================
# AUDIO OUTPUT VALIDATION
# ============================================================

def _validate_generated_audio(
    audio_path: Path,
) -> None:
    """
    Verify that FFmpeg produced a valid non-empty WAV file.
    """

    if not audio_path.exists():
        raise RuntimeError(
            "FFmpeg completed but the audio file was not created."
        )

    if not audio_path.is_file():
        raise RuntimeError(
            "Generated audio path is not a file."
        )

    if audio_path.stat().st_size <= 0:
        raise RuntimeError(
            "Generated audio file is empty."
        )


# ============================================================
# PARTIAL OUTPUT CLEANUP
# ============================================================

def _cleanup_partial_audio(
    audio_path: Path,
) -> None:
    """
    Remove an incomplete WAV file after a failed FFmpeg run.
    """

    try:
        if audio_path.exists():
            audio_path.unlink()

    except OSError:
        logger.warning(
            "Could not remove partial audio file: %s",
            audio_path,
        )


# ============================================================
# MAIN AUDIO EXTRACTION
# ============================================================

def extract_audio(
    video_path: str,
    output_path: str,
) -> str:
    """
    Extract audio from a lecture video using FFmpeg.

    Output format:
        WAV
        PCM signed 16-bit
        16 kHz
        mono

    Parameters
    ----------
    video_path:
        Path to the source video.

    output_path:
        Path where the extracted WAV file will be stored.

    Returns
    -------
    str
        Absolute path to the generated WAV file.

    Raises
    ------
    FileNotFoundError
        If the input video does not exist.

    ValueError
        If the input/output paths are invalid.

    RuntimeError
        If FFmpeg fails, times out, or produces an invalid file.
    """

    # --------------------------------------------------------
    # 1. Validate input
    # --------------------------------------------------------

    video = _validate_video_path(
        video_path
    )

    # --------------------------------------------------------
    # 2. Validate output
    # --------------------------------------------------------

    audio = _validate_output_path(
        output_path
    )

    audio = _ensure_inside_directory(
        audio,
        audio.parent,
    )

    # --------------------------------------------------------
    # 3. Prevent stale output
    # --------------------------------------------------------

    if audio.exists():
        try:
            audio.unlink()

        except OSError as exc:
            raise RuntimeError(
                "Could not replace existing audio output."
            ) from exc

    # --------------------------------------------------------
    # 4. Build controlled FFmpeg command
    # --------------------------------------------------------
    #
    # Security properties:
    #
    # - command is a list, not a shell string
    # - shell=False
    # - no user-controlled FFmpeg flags
    # - input path is passed as one argument
    # - output path is validated internally
    # - audio parameters are fixed
    #
    # --------------------------------------------------------

    command = [
        "ffmpeg",

        # Hide FFmpeg startup banner.
        "-hide_banner",

        # Report only errors.
        "-loglevel",
        "error",

        # Input video.
        "-i",
        str(video),

        # Disable video processing.
        "-vn",

        # Convert audio to mono.
        "-ac",
        "1",

        # Whisper-compatible sampling rate.
        "-ar",
        "16000",

        # 16-bit PCM WAV.
        "-c:a",
        "pcm_s16le",

        # Controlled output path.
        str(audio),

        # Allow replacement of the controlled output file.
        "-y",
    ]

    # --------------------------------------------------------
    # 5. Execute FFmpeg
    # --------------------------------------------------------

    try:

        subprocess.run(
            command,
            check=True,
            shell=False,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

    except subprocess.TimeoutExpired as exc:

        _cleanup_partial_audio(
            audio
        )

        logger.error(
            "FFmpeg audio extraction timed out for %s",
            video,
        )

        raise RuntimeError(
            "Audio extraction timed out."
        ) from exc

    except subprocess.CalledProcessError as exc:

        _cleanup_partial_audio(
            audio
        )

        logger.error(
            "FFmpeg audio extraction failed for %s: %s",
            video,
            exc.stderr.strip()
            if exc.stderr
            else "No FFmpeg error output.",
        )

        raise RuntimeError(
            "FFmpeg could not extract audio from the video."
        ) from exc

    except OSError as exc:

        _cleanup_partial_audio(
            audio
        )

        logger.error(
            "Could not execute FFmpeg: %s",
            exc,
        )

        raise RuntimeError(
            "FFmpeg could not be executed."
        ) from exc

    # --------------------------------------------------------
    # 6. Validate generated audio
    # --------------------------------------------------------

    try:

        _validate_generated_audio(
            audio
        )

    except Exception:

        _cleanup_partial_audio(
            audio
        )

        raise

    # --------------------------------------------------------
    # 7. Log successful extraction
    # --------------------------------------------------------

    logger.info(
        "Audio extraction completed: %s",
        audio,
    )

    return str(audio)