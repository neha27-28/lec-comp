"""
services/video_processor.py
---------------------------

Secure frame extraction for Lecture Companion.

Responsibilities:
- Validate the input video path
- Validate the output directory
- Prevent output path traversal
- Validate FPS
- Use FFmpeg without shell execution
- Prevent uncontrolled frame extraction
- Avoid unnecessary audio processing
- Control generated frame format/quality
- Detect and handle FFmpeg failures
- Clean up partial frames after failure

No artificial lecture-duration limit is imposed here.
No fixed FFmpeg timeout is imposed here.

Resource limits are based on the requested frame extraction rate
and generated frame count rather than an arbitrary lecture duration.
"""

from pathlib import Path
import logging
import math
import subprocess


logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

# Lecture Companion currently uses approximately 1 FPS.
# Allow some flexibility, but prevent absurd frame extraction rates.
MIN_FPS = 0.1
MAX_FPS = 3.0
DEFAULT_FPS = 3.0

# Maximum number of frames we will allow FFmpeg to generate in one job.
#
# This is intentionally large enough for long lectures:
#
# 2 hours × 2 FPS = 14,400 frames
#
# The limit is a safety guard against pathological input/configuration,
# not a lecture-duration limit.
MAX_FRAME_COUNT = 100_000

# JPEG quality.
#
# FFmpeg uses lower numbers for better quality.
JPEG_QUALITY = 4

# Expected frame naming format.
FRAME_PATTERN = "frame_%06d.jpg"

# Allowed input video formats.
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".mkv",
}


# -------------------------------------------------------------------
# Path validation
# -------------------------------------------------------------------

def _validate_video_path(video_path: str | Path) -> Path:
    """
    Validate the input video path.
    """

    path = Path(video_path).resolve()

    if not path.exists():
        raise ValueError("Input video does not exist.")

    if not path.is_file():
        raise ValueError("Input video path is not a file.")

    if path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError(
            "Unsupported video format."
        )

    return path


def _validate_output_directory(
    output_dir: str | Path,
) -> Path:
    """
    Validate and create the output directory.
    """

    output_path = Path(output_dir).resolve()

    output_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not output_path.is_dir():
        raise ValueError(
            "Frame output path is not a directory."
        )

    return output_path


def _ensure_inside_directory(
    path: Path,
    parent: Path,
) -> Path:
    """
    Ensure a generated path remains inside the intended directory.
    """

    path = path.resolve()
    parent = parent.resolve()

    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise RuntimeError(
            "Frame output path escaped the job directory."
        ) from exc

    return path


# -------------------------------------------------------------------
# FPS validation
# -------------------------------------------------------------------

def _validate_fps(fps: float) -> float:
    """
    Validate the frame extraction rate.

    Prevents:
    - zero FPS
    - negative FPS
    - NaN
    - infinity
    - excessively high FPS
    """

    try:
        fps = float(fps)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "FPS must be a valid number."
        ) from exc

    if not math.isfinite(fps):
        raise ValueError(
            "FPS must be finite."
        )

    if fps < MIN_FPS:
        raise ValueError(
            f"FPS must be at least {MIN_FPS}."
        )

    if fps > MAX_FPS:
        raise ValueError(
            f"FPS cannot exceed {MAX_FPS}."
        )

    return fps


# -------------------------------------------------------------------
# Frame count protection
# -------------------------------------------------------------------

def _validate_frame_count(
    fps: float,
    duration_seconds: float | None,
) -> None:
    """
    Estimate the number of frames that FFmpeg may generate.

    If duration information is unavailable, the check is skipped here
    and FFmpeg is still constrained by the validated FPS.

    This is NOT a lecture-duration limit.

    It is a resource-exhaustion protection mechanism.
    """

    if duration_seconds is None:
        return

    try:
        duration_seconds = float(duration_seconds)
    except (TypeError, ValueError):
        return

    if not math.isfinite(duration_seconds):
        return

    if duration_seconds <= 0:
        return

    estimated_frames = math.ceil(
        duration_seconds * fps
    )

    if estimated_frames > MAX_FRAME_COUNT:
        raise ValueError(
            "Video would generate too many frames "
            "at the requested extraction rate."
        )


# -------------------------------------------------------------------
# Partial frame cleanup
# -------------------------------------------------------------------

def _cleanup_partial_frames(
    output_dir: Path,
) -> None:
    """
    Remove frames generated by a failed FFmpeg operation.
    """

    try:
        for frame in output_dir.glob("frame_*.jpg"):
            try:
                frame.unlink()
            except OSError:
                logger.warning(
                    "Could not remove partial frame: %s",
                    frame,
                )

    except OSError:
        logger.exception(
            "Could not inspect frame directory during cleanup."
        )


# -------------------------------------------------------------------
# FFmpeg progress output
# -------------------------------------------------------------------

def _emit_ffmpeg_progress(line: str) -> None:
    """Emit compact live frame/time progress from FFmpeg."""
    line = line.strip()
    if not line or "=" not in line:
        return
    key, value = line.split("=", 1)
    if key == "frame":
        print(f"frame={value}", flush=True)
    elif key == "out_time":
        print(f"time={value}", flush=True)


# -------------------------------------------------------------------
# Main frame extraction
# -------------------------------------------------------------------

def extract_frames(
    video_path: str,
    output_dir: str,
    fps: float = DEFAULT_FPS,
    duration_seconds: float | None = None,
) -> list[str]:
    """
    Extract frames from a lecture video using FFmpeg.

    Parameters
    ----------
    video_path:
        Path to the source video.

    output_dir:
        Directory where extracted frames will be stored.

    fps:
        Frames per second.

    duration_seconds:
        Optional known duration of the video.

        This is used ONLY to estimate whether the requested FPS would
        create an excessive number of frames.

        It is NOT used as a maximum-duration restriction.

    Returns
    -------
    list[str]
        Paths to generated frame files.
    """

    # ---------------------------------------------------------------
    # Validate input
    # ---------------------------------------------------------------

    video = _validate_video_path(video_path)

    output_path = _validate_output_directory(
        output_dir
    )

    fps = _validate_fps(fps)

    # ---------------------------------------------------------------
    # Resource guard
    # ---------------------------------------------------------------

    _validate_frame_count(
        fps=fps,
        duration_seconds=duration_seconds,
    )

    # ---------------------------------------------------------------
    # Controlled output pattern
    # ---------------------------------------------------------------

    output_pattern = output_path / FRAME_PATTERN

    output_pattern = _ensure_inside_directory(
        output_pattern,
        output_path,
    )

    # ---------------------------------------------------------------
    # FFmpeg command
    # ---------------------------------------------------------------
    #
    # Important security properties:
    #
    # - command is a list, not a shell string
    # - shell=False
    # - no user-controlled FFmpeg flags
    # - audio is disabled
    # - frame rate is validated before insertion
    # - output pattern is generated internally
    #

    command = [
        "ffmpeg",

        # Don't display the FFmpeg startup banner.
        "-hide_banner",

        # Only report errors.
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-nostats",

        # Input video.
        "-i",
        str(video),

        # No audio processing.
        "-an",

        # Controlled frame rate.
        "-vf",
        f"fps={fps:g}",

        # JPEG output.
        "-q:v",
        str(JPEG_QUALITY),

        # Controlled output path.
        str(output_pattern),

        # Overwrite existing files.
        "-y",
    ]

    logger.info(
        "Starting frame extraction: video=%s fps=%s",
        video.name,
        fps,
    )

    # ---------------------------------------------------------------
    # Run FFmpeg
    # ---------------------------------------------------------------

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            bufsize=1,
        )

        if process.stdout is not None:
            for line in process.stdout:
                _emit_ffmpeg_progress(line)

        stderr_output = process.stderr.read() if process.stderr is not None else ""
        return_code = process.wait()

        class _FFmpegResult:
            def __init__(self, returncode: int, stderr: str):
                self.returncode = returncode
                self.stderr = stderr

        result = _FFmpegResult(return_code, stderr_output)

    except FileNotFoundError as exc:
        logger.exception(
            "FFmpeg executable was not found."
        )

        _cleanup_partial_frames(
            output_path
        )

        raise RuntimeError(
            "FFmpeg is not installed or is not available in PATH."
        ) from exc

    except OSError as exc:
        logger.exception(
            "Operating system error while starting FFmpeg."
        )

        _cleanup_partial_frames(
            output_path
        )

        raise RuntimeError(
            "FFmpeg could not be started."
        ) from exc

    # ---------------------------------------------------------------
    # FFmpeg failed
    # ---------------------------------------------------------------

    if result.returncode != 0:

        stderr = (
            result.stderr.strip()
            if result.stderr
            else "No FFmpeg error details available."
        )

        logger.error(
            "FFmpeg frame extraction failed "
            "(return code %s): %s",
            result.returncode,
            stderr,
        )

        _cleanup_partial_frames(
            output_path
        )

        raise RuntimeError(
            "Frame extraction failed."
        )

    # ---------------------------------------------------------------
    # Collect generated frames
    # ---------------------------------------------------------------

    frame_files = sorted(
        path.resolve()
        for path in output_path.glob(
            "frame_*.jpg"
        )
        if path.is_file()
    )

    # ---------------------------------------------------------------
    # Verify every generated frame is inside output directory
    # ---------------------------------------------------------------

    safe_frames = []

    for frame in frame_files:

        try:
            safe_frame = _ensure_inside_directory(
                frame,
                output_path,
            )

            safe_frames.append(
                safe_frame
            )

        except RuntimeError:
            logger.warning(
                "Ignoring frame outside output directory: %s",
                frame,
            )

    # ---------------------------------------------------------------
    # Verify output
    # ---------------------------------------------------------------

    if not safe_frames:
        raise RuntimeError(
            "FFmpeg completed but no frames were generated."
        )

    # ---------------------------------------------------------------
    # Final resource guard
    # ---------------------------------------------------------------

    if len(safe_frames) > MAX_FRAME_COUNT:

        logger.warning(
            "Frame extraction generated too many frames: %s",
            len(safe_frames),
        )

        _cleanup_partial_frames(
            output_path
        )

        raise RuntimeError(
            "Frame extraction exceeded the maximum allowed frame count."
        )

    logger.info(
        "Frame extraction completed: %s frames",
        len(safe_frames),
    )

    return [
        str(frame)
        for frame in safe_frames
    ]