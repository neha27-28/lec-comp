"""
services/downloader.py
----------------------

Secure YouTube video downloader for Lecture Companion.

Responsibilities:
- Download a single YouTube video using yt-dlp
- Accept only HTTPS YouTube URLs
- Prevent playlist downloads
- Preserve the real YouTube video title
- Detect suspicious Unicode/confusable characters in titles
- Sanitize titles before using them as filesystem names
- Keep downloaded files inside the requested job directory
- Enforce a 4 GB maximum download size
- Apply network timeouts and limited retries
- Avoid shell execution
- Return the downloaded video path

The original YouTube title is NOT silently modified for display.
Only the filesystem/storage representation is sanitized.
"""

from pathlib import Path
from urllib.parse import urlparse
import logging
import re
import unicodedata

import yt_dlp


logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

MAX_DOWNLOAD_SIZE = 4 * 1024 * 1024 * 1024  # 4 GB

SOCKET_TIMEOUT = 30
DOWNLOAD_RETRIES = 2

ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mkv",
    ".mov",
}


# -------------------------------------------------------------------
# Unicode / filename security
# -------------------------------------------------------------------

# Characters that can be used to manipulate how text is displayed.
#
# This includes:
# - bidirectional override/control characters
# - zero-width characters
# - invisible formatting characters
#
# We detect these rather than silently changing the user's title.
DANGEROUS_UNICODE_CHARS = {
    "\u061c",  # Arabic Letter Mark
    "\u200b",  # Zero Width Space
    "\u200c",  # Zero Width Non-Joiner
    "\u200d",  # Zero Width Joiner
    "\u200e",  # Left-to-Right Mark
    "\u200f",  # Right-to-Left Mark
    "\u202a",  # Left-to-Right Embedding
    "\u202b",  # Right-to-Left Embedding
    "\u202c",  # Pop Directional Formatting
    "\u202d",  # Left-to-Right Override
    "\u202e",  # Right-to-Left Override
    "\u2060",  # Word Joiner
    "\u2061",  # Function Application
    "\u2062",  # Invisible Times
    "\u2063",  # Invisible Separator
    "\u2064",  # Invisible Plus
    "\u2066",  # Left-to-Right Isolate
    "\u2067",  # Right-to-Left Isolate
    "\u2068",  # First Strong Isolate
    "\u2069",  # Pop Directional Isolate
    "\u206a",  # Deprecated Arabic Letter Mark
    "\u206b",
    "\u206c",
    "\u206d",
    "\u206e",
    "\u206f",
    "\ufeff",  # Zero Width No-Break Space / BOM
}


def detect_suspicious_unicode(text: str) -> list[str]:
    """
    Detect potentially dangerous Unicode characters.

    This does NOT reject normal non-English text.

    Examples of legitimate content that remains allowed:
        Hindi
        Arabic
        Japanese
        Chinese
        accented Latin characters

    The function specifically looks for invisible/control characters
    that can make filenames or titles visually misleading.
    """

    if not text:
        return []

    found = []

    for char in text:
        if char in DANGEROUS_UNICODE_CHARS:
            found.append(
                f"U+{ord(char):04X} ({unicodedata.name(char, 'UNKNOWN')})"
            )

    return found


def sanitize_filename(name: str, fallback: str = "lecture") -> str:
    """
    Convert an untrusted title into a safe filesystem filename.

    Important:
    - The original title is NOT changed in application metadata/UI.
    - This function is ONLY for the filesystem representation.
    """

    if not name:
        return fallback

    # Unicode normalization.
    #
    # NFC preserves readable Unicode while avoiding some equivalent
    # Unicode representations.
    name = unicodedata.normalize("NFC", name)

    # Remove dangerous invisible/bidirectional characters from the
    # STORAGE representation.
    name = "".join(
        char
        for char in name
        if char not in DANGEROUS_UNICODE_CHARS
    )

    # Windows-invalid filename characters:
    # < > : " / \ | ? *
    name = re.sub(r'[<>:"/\\|?*]', "_", name)

    # Remove ASCII control characters.
    name = "".join(
        char
        for char in name
        if ord(char) >= 32
    )

    # Collapse whitespace.
    name = re.sub(r"\s+", " ", name).strip()

    # Prevent accidental "." / ".." filenames.
    if name in {".", ".."}:
        name = fallback

    # Windows does not allow filenames ending in a space or period.
    name = name.rstrip(" .")

    if not name:
        name = fallback

    # Avoid Windows reserved device names.
    stem_upper = Path(name).stem.upper()

    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    if stem_upper in reserved_names:
        name = f"_{name}"

    # Keep filenames manageable.
    #
    # This is a storage limit only. The original title is still
    # preserved separately.
    max_name_length = 180

    if len(name) > max_name_length:
        name = name[:max_name_length].rstrip(" .")

    return name


# -------------------------------------------------------------------
# YouTube URL validation
# -------------------------------------------------------------------

def _validate_youtube_url(url: str) -> str:
    """
    Validate a YouTube URL defensively.

    main.py already performs this validation before calling the
    downloader, but downloader.py must remain safe if called directly.
    """

    if not isinstance(url, str):
        raise ValueError("YouTube URL must be a string.")

    url = url.strip()

    if not url:
        raise ValueError("YouTube URL cannot be empty.")

    parsed = urlparse(url)

    # HTTPS only.
    if parsed.scheme.lower() != "https":
        raise ValueError("Only HTTPS YouTube URLs are allowed.")

    # Reject credentials.
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")

    # Reject explicitly supplied ports.
    if parsed.port is not None:
        raise ValueError("URLs containing explicit ports are not allowed.")

    hostname = (parsed.hostname or "").lower().rstrip(".")

    # Important:
    # We compare against an explicit ASCII allow-list instead of
    # accepting arbitrary Unicode domains.
    if hostname not in ALLOWED_HOSTS:
        raise ValueError("Only YouTube URLs are allowed.")

    # Basic path validation.
    if hostname in {"youtu.be", "www.youtu.be"}:
        if not parsed.path or parsed.path == "/":
            raise ValueError("Invalid YouTube video URL.")

    elif hostname in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
    }:
        if not (
            parsed.path.startswith("/watch")
            or parsed.path.startswith("/shorts/")
            or parsed.path.startswith("/embed/")
        ):
            raise ValueError("Invalid YouTube video URL.")

    return url


# -------------------------------------------------------------------
# Output directory validation
# -------------------------------------------------------------------

def _validate_output_directory(output_dir: str | Path) -> Path:
    """
    Validate and create the download directory.
    """

    output_path = Path(output_dir).resolve()

    output_path.mkdir(parents=True, exist_ok=True)

    if not output_path.is_dir():
        raise ValueError(
            "Download output path is not a directory."
        )

    return output_path


# -------------------------------------------------------------------
# Path containment
# -------------------------------------------------------------------

def _ensure_inside_directory(
    file_path: Path,
    parent_directory: Path,
) -> Path:
    """
    Ensure file_path remains inside parent_directory.
    """

    file_path = file_path.resolve()
    parent_directory = parent_directory.resolve()

    try:
        file_path.relative_to(parent_directory)
    except ValueError as exc:
        raise RuntimeError(
            "Downloaded file escaped the requested output directory."
        ) from exc

    return file_path


# -------------------------------------------------------------------
# Download
# -------------------------------------------------------------------

def download_video(
    url: str,
    output_dir: str,
) -> str:
    """
    Download one YouTube video securely.

    Returns:
        Absolute path of the downloaded video.
    """

    # ---------------------------------------------------------------
    # Validate URL and output directory
    # ---------------------------------------------------------------

    url = _validate_youtube_url(url)
    output_path = _validate_output_directory(output_dir)

    logger.info(
        "Starting YouTube download into %s",
        output_path,
    )

    # ---------------------------------------------------------------
    # First retrieve metadata.
    #
    # We use this to preserve the REAL YouTube title while creating
    # a safe filesystem representation.
    # ---------------------------------------------------------------

    try:
        metadata_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": SOCKET_TIMEOUT,
        }

        with yt_dlp.YoutubeDL(metadata_opts) as ydl:
            info = ydl.extract_info(
                url,
                download=False,
            )

    except yt_dlp.utils.DownloadError as exc:
        logger.exception(
            "Could not retrieve YouTube metadata."
        )
        raise RuntimeError(
            "The YouTube video information could not be retrieved."
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected error retrieving YouTube metadata."
        )
        raise RuntimeError(
            "An unexpected error occurred while reading the YouTube video."
        ) from exc

    if not info:
        raise RuntimeError(
            "YouTube did not return video information."
        )

    # ---------------------------------------------------------------
    # Reject playlist metadata defensively.
    # ---------------------------------------------------------------

    if info.get("_type") == "playlist":
        raise ValueError(
            "Playlist downloads are not allowed."
        )

    # ---------------------------------------------------------------
    # Preserve the REAL title.
    # ---------------------------------------------------------------

    original_title = info.get("title") or "Lecture"

    if not isinstance(original_title, str):
        original_title = "Lecture"

    original_title = original_title.strip()

    if not original_title:
        original_title = "Lecture"

    # Detect suspicious Unicode.
    suspicious_unicode = detect_suspicious_unicode(
        original_title
    )

    if suspicious_unicode:
        logger.warning(
            "YouTube title contains suspicious Unicode characters: %s",
            suspicious_unicode,
        )

    # ---------------------------------------------------------------
    # Generate safe filesystem name.
    #
    # The original title remains untouched in metadata.
    # ---------------------------------------------------------------

    safe_title = sanitize_filename(
        original_title,
        fallback="lecture",
    )

    # We don't know the final container until yt-dlp finishes.
    # MP4 is preferred because Lecture Companion already supports it.
    output_template = str(
        output_path / f"{safe_title}.%(ext)s"
    )

    # ---------------------------------------------------------------
    # Download configuration
    # ---------------------------------------------------------------

    ydl_opts = {
        # Video + audio.
        "format": "bv*+ba/b",

        # Never download playlists.
        "noplaylist": True,

        # Safe title-based output path.
        "outtmpl": output_template,

        # Prefer MP4 after merging.
        "merge_output_format": "mp4",

        # Network limits.
        "socket_timeout": SOCKET_TIMEOUT,
        "retries": DOWNLOAD_RETRIES,

        # Don't resume a potentially malicious/stale partial file.
        "continuedl": False,

        # Only download the actual video.
        "writethumbnail": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "writedescription": False,
        "writeinfojson": False,

        # Reduce console noise.
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    # ---------------------------------------------------------------
    # Download
    # ---------------------------------------------------------------

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    except yt_dlp.utils.DownloadError as exc:
        logger.exception("yt-dlp download failed.")
        raise RuntimeError(
            "The video could not be downloaded."
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected error during YouTube download."
        )
        raise RuntimeError(
            "An unexpected error occurred while downloading the video."
        ) from exc

    # ---------------------------------------------------------------
    # Locate generated video files.
    # ---------------------------------------------------------------

    video_files = [
        path.resolve()
        for path in output_path.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in ALLOWED_VIDEO_EXTENSIONS
        )
    ]

    if not video_files:
        raise RuntimeError(
            "Download completed but no video file was produced."
        )

    # ---------------------------------------------------------------
    # Validate every candidate stays inside the job directory.
    # ---------------------------------------------------------------

    safe_video_files = []

    for video_file in video_files:
        try:
            safe_video_file = _ensure_inside_directory(
                video_file,
                output_path,
            )
            safe_video_files.append(safe_video_file)

        except RuntimeError:
            logger.warning(
                "Ignoring video file outside output directory: %s",
                video_file,
            )

    if not safe_video_files:
        raise RuntimeError(
            "No valid downloaded video remained inside the job directory."
        )

    # Normally there should be exactly one file because noplaylist=True.
    safe_video_files.sort()

    video_path = safe_video_files[0]

    # ---------------------------------------------------------------
    # File validation
    # ---------------------------------------------------------------

    if not video_path.is_file():
        raise RuntimeError(
            "Downloaded video file does not exist."
        )

    file_size = video_path.stat().st_size

    if file_size <= 0:
        raise RuntimeError(
            "Downloaded video file is empty."
        )

    # 4 GB maximum.
    if file_size > MAX_DOWNLOAD_SIZE:

        logger.warning(
            "Downloaded video exceeded 4 GB: %s bytes",
            file_size,
        )

        try:
            video_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "Could not remove oversized downloaded file."
            )

        raise RuntimeError(
            "Downloaded video exceeds the 4 GB size limit."
        )

    # ---------------------------------------------------------------
    # Final path containment check.
    # ---------------------------------------------------------------

    video_path = _ensure_inside_directory(
        video_path,
        output_path,
    )

    logger.info(
        "YouTube download completed: %s (%.2f MB)",
        video_path.name,
        file_size / (1024 * 1024),
    )

    return str(video_path)