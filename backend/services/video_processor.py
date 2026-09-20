import subprocess
from pathlib import Path


def extract_frames(video_path: str, output_dir: str, fps: float = 1.0):
    """
    Extract frames from a video using FFmpeg.

    Args:
        video_path: Path to the input video.
        output_dir: Directory where frames will be saved.
        fps: Number of frames to extract per second.
    """

    video = Path(video_path)
    output = Path(output_dir)

    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video}")

    output.mkdir(parents=True, exist_ok=True)

    output_pattern = output / "frame_%06d.jpg"

    command = [
        "ffmpeg",
        "-i",
        str(video),
        "-vf",
        f"fps={fps}",
        str(output_pattern),
        "-y",
    ]

    subprocess.run(command, check=True)

    print(f"Frames extracted to: {output}")