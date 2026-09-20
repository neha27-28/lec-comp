from pathlib import Path
import yt_dlp


def download_video(url: str, output_dir: str) -> str:
    """
    Download a YouTube video and return the local file path.
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_template = str(output_path / "%(title)s.%(ext)s")

    ydl_opts = {
        "format": "bv*+ba/b",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        downloaded_file = ydl.prepare_filename(info)

        # If video/audio were merged into MP4,
        # the final extension may be .mp4
        final_file = Path(downloaded_file).with_suffix(".mp4")

        if final_file.exists():
            return str(final_file)

        return downloaded_file