"""
main.py
-------

Lecture Companion FastAPI backend.

Security responsibilities:
- Validate uploaded video files
- Enforce a 4 GB upload limit
- Prevent filename/path traversal
- Validate YouTube URLs
- Validate job IDs and search queries
- Restrict CORS to the local frontend
- Keep generated files inside job directories
- Avoid exposing internal exception details
- Validate downloaded video paths and sizes
- Preserve the project's 3 FPS slide-analysis pipeline
"""

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from services.slide_detector import detect_slides
from services.pdf_generator import create_slides_pdf
from services.video_processor import extract_frames
from services.downloader import download_video
from services.audio_processor import extract_audio
from services.transcriber import transcribe_audio
from services.slide_speech_linker import link_slides_to_speech

from database import (
    initialize_database,
    save_job,
    save_linked_slides,
    search_lecture,
    update_job_performance,
)

from pathlib import Path
from urllib.parse import urlparse

import logging
import os
import re
import subprocess
import threading
import time
import uuid

import psutil



# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Lecture Companion API",
)


# ============================================================
# SECURITY CONFIGURATION
# ============================================================

# Maximum uploaded/downloaded lecture size.
# 4 GB intentionally supports long lecture videos.
MAX_UPLOAD_SIZE = 4 * 1024 * 1024 * 1024

# Upload is written in bounded chunks.
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB

# Maximum search query length.
MAX_SEARCH_QUERY_LENGTH = 200

# IMPORTANT:
# Lecture Companion deliberately uses 3 FPS for slide detection.
PROCESSING_FPS = 3.0

# Supported local video formats.
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".mkv",
}

# Accepted YouTube hosts.
ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
    ],
    allow_headers=[
        "Content-Type",
    ],
)


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "data" / "input"
FRAMES_DIR = BASE_DIR / "data" / "frames"
SLIDES_DIR = BASE_DIR / "data" / "slides"
PDF_DIR = BASE_DIR / "data" / "pdfs"
AUDIO_DIR = BASE_DIR / "data" / "audio"


for directory in [
    INPUT_DIR,
    FRAMES_DIR,
    SLIDES_DIR,
    PDF_DIR,
    AUDIO_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

initialize_database()


# ============================================================
# HELPERS
# ============================================================

def validate_job_id(job_id: str) -> str:
    """
    Validate the generated 8-character hexadecimal job ID.
    """

    if not re.fullmatch(
        r"[0-9a-f]{8}",
        job_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID.",
        )

    return job_id


def validate_search_query(query: str) -> str:
    """
    Validate and normalize a search query.
    """

    query = query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Search query cannot exceed "
                f"{MAX_SEARCH_QUERY_LENGTH} characters."
            ),
        )

    return query


def validate_youtube_url(url: str) -> str:
    """
    Validate that the supplied URL belongs to YouTube.

    Only HTTPS URLs are accepted.
    """

    url = url.strip()

    if not url:
        raise HTTPException(
            status_code=400,
            detail="YouTube URL cannot be empty.",
        )

    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL.",
        ) from exc

    if parsed.scheme.lower() != "https":
        raise HTTPException(
            status_code=400,
            detail="Only HTTPS YouTube URLs are allowed.",
        )

    hostname = (
        parsed.hostname or ""
    ).lower()

    if hostname not in ALLOWED_YOUTUBE_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Only YouTube URLs are supported.",
        )

    # Reject embedded username/password.
    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL.",
        )

    # Reject explicit ports.
    try:
        if parsed.port is not None:
            raise HTTPException(
                status_code=400,
                detail="Invalid YouTube URL.",
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL.",
        ) from exc

    if not parsed.path:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL.",
        )

    return url


def sanitize_filename(
    filename: str,
) -> str:
    """
    Convert an untrusted filename into a safe local filename.

    This is used for both uploaded filenames and
    lecture-derived PDF names.
    """

    filename = Path(
        filename or ""
    ).name

    if not filename:
        return "lecture"

    # Keep only safe filename characters.
    filename = re.sub(
        r"[^A-Za-z0-9._ -]",
        "_",
        filename,
    )

    # Prevent traversal-style sequences.
    filename = filename.replace(
        "..",
        "_",
    )

    # Remove problematic leading/trailing characters.
    filename = filename.strip(
        " ."
    )

    if not filename:
        return "lecture"

    return filename


def get_upload_extension(
    filename: str,
) -> str:
    """
    Validate the uploaded video extension.
    """

    safe_name = sanitize_filename(
        filename
    )

    extension = Path(
        safe_name
    ).suffix.lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported video format. "
                "Supported formats: MP4, WebM, MOV and MKV."
            ),
        )

    return extension


def ensure_inside_directory(
    path: Path,
    parent: Path,
) -> Path:
    """
    Ensure that path remains inside parent.
    """

    path = path.resolve()
    parent = parent.resolve()

    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path.",
        ) from exc

    return path


def validate_existing_file(
    path: Path,
    parent: Path | None = None,
) -> Path:
    """
    Validate that a path exists and is a file.

    If parent is provided, also ensure the file remains
    inside that directory.
    """

    path = path.resolve()

    if parent is not None:
        ensure_inside_directory(
            path,
            parent,
        )

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Requested file was not found.",
        )

    return path


def save_uploaded_video(
    video: UploadFile,
    destination: Path,
) -> Path:
    """
    Save an uploaded video using bounded chunked writes.

    Enforces the 4 GB maximum.
    """

    extension = get_upload_extension(
        video.filename or ""
    )

    destination = destination.with_suffix(
        extension
    )

    total_bytes = 0

    try:

        with destination.open(
            "wb"
        ) as buffer:

            while True:

                chunk = video.file.read(
                    UPLOAD_CHUNK_SIZE
                )

                if not chunk:
                    break

                total_bytes += len(
                    chunk
                )

                if total_bytes > MAX_UPLOAD_SIZE:

                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Uploaded video exceeds "
                            "the maximum allowed size of 4 GB."
                        ),
                    )

                buffer.write(
                    chunk
                )

    except HTTPException:

        try:
            destination.unlink(
                missing_ok=True
            )
        except OSError:
            logger.exception(
                "Could not remove oversized upload: %s",
                destination,
            )

        raise

    except Exception:

        try:
            destination.unlink(
                missing_ok=True
            )
        except OSError:
            logger.exception(
                "Could not remove failed upload: %s",
                destination,
            )

        logger.exception(
            "Failed to save uploaded video."
        )

        raise HTTPException(
            status_code=500,
            detail="Could not save uploaded video.",
        )

    finally:

        try:
            video.file.close()
        except Exception:
            pass

    if total_bytes == 0:

        destination.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=400,
            detail="Uploaded video is empty.",
        )

    logger.info(
        "Uploaded video saved: %s bytes",
        total_bytes,
    )

    return destination


def validate_video_size(
    video_path: Path,
) -> None:
    """
    Ensure a video does not exceed the configured
    maximum size.
    """

    try:
        size = video_path.stat().st_size
    except OSError as exc:

        logger.exception(
            "Could not determine video size."
        )

        raise HTTPException(
            status_code=500,
            detail="Could not determine video size.",
        ) from exc

    if size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "Video exceeds the maximum allowed size of 4 GB."
            ),
        )

    if size <= 0:
        raise HTTPException(
            status_code=400,
            detail="Video file is empty.",
        )



# ============================================================
# PERFORMANCE / BENCHMARK HELPERS
# ============================================================


def get_video_duration_seconds(video_path: Path) -> float | None:
    """
    Read the source video duration using ffprobe.

    This is benchmark metadata only; failure to read duration does
    not prevent lecture processing.
    """

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
        duration = float(completed.stdout.strip())
        if duration < 0:
            return None
        return duration
    except Exception:
        logger.warning(
            "Could not determine video duration for %s",
            video_path,
            exc_info=True,
        )
        return None


class MemoryMonitor:
    """Sample current-process RSS and retain the observed peak."""

    def __init__(self, interval_seconds: float = 0.1):
        self.interval_seconds = interval_seconds
        self.process = psutil.Process(os.getpid())
        self.peak_bytes = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        while not self._stop_event.is_set():
            try:
                rss = self.process.memory_info().rss
                self.peak_bytes = max(self.peak_bytes, rss)
            except (psutil.Error, OSError):
                pass
            self._stop_event.wait(self.interval_seconds)

    def start(self) -> None:
        try:
            self.peak_bytes = self.process.memory_info().rss
        except (psutil.Error, OSError):
            self.peak_bytes = 0

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._sample,
            name="lecture-companion-memory-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> float | None:
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=1.0)

        try:
            self.peak_bytes = max(
                self.peak_bytes,
                self.process.memory_info().rss,
            )
        except (psutil.Error, OSError):
            pass

        if self.peak_bytes <= 0:
            return None

        return round(self.peak_bytes / (1024 * 1024), 2)


def _elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)


# ============================================================
# BASIC ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "message": "Lecture Companion API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# ============================================================
# PROCESS LECTURE
# ============================================================

@app.post("/process")
async def process_lecture(
    lecture_url: str = Form(default=""),
    video: UploadFile | None = File(default=None),
):
    """
    Process a lecture from either:
    - a YouTube URL
    - a local uploaded video
    """

    lecture_url = lecture_url.strip()

    # --------------------------------------------------------
    # 1. Validate input source
    # --------------------------------------------------------

    if not lecture_url and video is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Please provide a YouTube URL "
                "or upload a video."
            ),
        )

    if lecture_url and video is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide either a YouTube URL "
                "or a video upload, not both."
            ),
        )

    # --------------------------------------------------------
    # 2. Create isolated job directories
    # --------------------------------------------------------

    job_id = uuid.uuid4().hex[:8]

    job_input_dir = INPUT_DIR / job_id
    job_frames_dir = FRAMES_DIR / job_id
    job_slides_dir = SLIDES_DIR / job_id
    job_pdf_dir = PDF_DIR / job_id
    job_audio_dir = AUDIO_DIR / job_id

    for directory in [
        job_input_dir,
        job_frames_dir,
        job_slides_dir,
        job_pdf_dir,
        job_audio_dir,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    try:

        logger.info("============================================================")
        logger.info("LECTURE PROCESSING STARTED: job=%s", job_id)
        logger.info("============================================================")

        # ----------------------------------------------------
        # 3. Save / download video
        # ----------------------------------------------------

        download_time_sec = None

        if video is not None:

            extension = get_upload_extension(
                video.filename or ""
            )

            # Never use the user-provided filename as a path.
            upload_destination = (
                job_input_dir / "lecture"
            ).with_suffix(
                extension
            )

            video_path = save_uploaded_video(
                video=video,
                destination=upload_destination,
            )

        else:

            validated_url = validate_youtube_url(
                lecture_url
            )

            try:

                download_start = time.perf_counter()

                downloaded_path = download_video(
                    url=validated_url,
                    output_dir=str(
                        job_input_dir
                    ),
                )

                download_time_sec = _elapsed(download_start)

            except Exception:

                logger.exception(
                    "YouTube download failed for job %s",
                    job_id,
                )

                raise HTTPException(
                    status_code=500,
                    detail=(
                        "Could not download "
                        "the YouTube video."
                    ),
                )

            video_path = Path(
                downloaded_path
            ).resolve()

            # Downloader output must remain inside
            # this job's input directory.
            ensure_inside_directory(
                video_path,
                job_input_dir,
            )

            if (
                video_path.suffix.lower()
                not in ALLOWED_VIDEO_EXTENSIONS
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Downloaded file is not "
                        "a supported video."
                    ),
                )

        # ----------------------------------------------------
        # 4. Validate final video
        # ----------------------------------------------------

        video_path = validate_existing_file(
            video_path,
            job_input_dir,
        )

        validate_video_size(
            video_path
        )

        # ----------------------------------------------------
        # Start core processing benchmark
        # ----------------------------------------------------

        processing_start = time.perf_counter()
        memory_monitor = MemoryMonitor()
        memory_monitor.start()

        video_size_bytes = video_path.stat().st_size
        video_duration_sec = get_video_duration_seconds(
            video_path
        )

        # ----------------------------------------------------
        # 5. Save initial job information
        # ----------------------------------------------------

        try:

            save_job(
                job_id=job_id,
                video_filename=video_path.name,
                video_path=str(
                    video_path
                ),
                fps=PROCESSING_FPS,
            )

        except Exception:

            logger.exception(
                "Could not save job information for %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Could not save job information.",
            )

        # ----------------------------------------------------
        # 6. Extract frames
        # ----------------------------------------------------

        try:

            logger.info("STAGE 6: Starting frame extraction for job %s", job_id)
            stage_start = time.perf_counter()

            extract_frames(
                video_path=str(
                    video_path
                ),
                output_dir=str(
                    job_frames_dir
                ),
                fps=PROCESSING_FPS,
            )

            frame_extraction_time_sec = _elapsed(stage_start)
            logger.info("STAGE 6: Frame extraction completed for job %s in %.3f sec", job_id, frame_extraction_time_sec)

        except ValueError as exc:

            logger.warning(
                "Frame extraction rejected for job %s: %s",
                job_id,
                exc,
            )

            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

        except Exception:

            logger.exception(
                "Frame extraction failed for job %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Could not extract video frames.",
            )

        # ----------------------------------------------------
        # 7. Detect slides
        # ----------------------------------------------------

        try:

            logger.info("STAGE 7: Starting slide detection for job %s", job_id)
            stage_start = time.perf_counter()

            slides = detect_slides(
                frames_dir=str(
                    job_frames_dir
                ),
                output_dir=str(
                    job_slides_dir
                ),
            )

            slide_detection_time_sec = _elapsed(stage_start)
            logger.info("STAGE 7: Slide detection completed for job %s in %.3f sec", job_id, slide_detection_time_sec)

        except Exception:

            logger.exception(
                "Slide detection failed for job %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Could not detect slides.",
            )

        # ----------------------------------------------------
        # 8. Generate PDF
        #
        # IMPORTANT:
        # PDF filename is derived from the actual video
        # filename/title.
        # ----------------------------------------------------

        pdf_filename = (
            f"{sanitize_filename(video_path.stem)}.pdf"
        )

        pdf_path = (
            job_pdf_dir / pdf_filename
        )

        try:

            logger.info("STAGE 8: Starting PDF generation for job %s", job_id)
            stage_start = time.perf_counter()

            create_slides_pdf(
                slides=slides,
                output_path=pdf_path,
            )

            pdf_generation_time_sec = _elapsed(stage_start)
            logger.info("STAGE 8: PDF generation completed for job %s in %.3f sec", job_id, pdf_generation_time_sec)

        except Exception:

            logger.exception(
                "PDF generation failed for job %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Slides were extracted, "
                    "but the PDF could not be generated."
                ),
            )

        # ----------------------------------------------------
        # 9. Extract audio
        # ----------------------------------------------------

        audio_path = (
            job_audio_dir /
            "lecture_audio.wav"
        )

        try:

            logger.info("STAGE 9: Starting audio extraction for job %s", job_id)
            stage_start = time.perf_counter()

            extract_audio(
                video_path=str(
                    video_path
                ),
                output_path=str(
                    audio_path
                ),
            )

            audio_extraction_time_sec = _elapsed(stage_start)
            logger.info("STAGE 9: Audio extraction completed for job %s in %.3f sec", job_id, audio_extraction_time_sec)

        except Exception:

            logger.exception(
                "Audio extraction failed for job %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Could not extract lecture audio.",
            )

        # ----------------------------------------------------
        # 10. Whisper transcription
        # ----------------------------------------------------

        try:

            logger.info("STAGE 10: Starting Whisper transcription for job %s", job_id)
            stage_start = time.perf_counter()

            transcript = transcribe_audio(
                audio_path=str(
                    audio_path
                ),
            )

            transcription_time_sec = _elapsed(stage_start)
            logger.info("STAGE 10: Whisper transcription completed for job %s in %.3f sec", job_id, transcription_time_sec)

        except Exception:

            logger.exception(
                "Transcription failed for job %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Could not transcribe lecture audio.",
            )

        # ----------------------------------------------------
        # 11. Link slides with speech
        # ----------------------------------------------------

        try:

            logger.info("STAGE 11: Starting slide-speech linking for job %s", job_id)
            stage_start = time.perf_counter()

            linked_slides_result = (
                link_slides_to_speech(
                    slides=slides,
                    transcript=transcript,
                    fps=PROCESSING_FPS,
                )
            )

            slide_speech_linking_time_sec = _elapsed(stage_start)
            logger.info("STAGE 11: Slide-speech linking completed for job %s in %.3f sec", job_id, slide_speech_linking_time_sec)

            linked_slides = (
                linked_slides_result.get(
                    "slides",
                    [],
                )
            )

        except Exception:

            logger.exception(
                "Slide-speech linking failed for job %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Slides and speech were extracted, "
                    "but linking failed."
                ),
            )

        # ----------------------------------------------------
        # 12. Save linked data
        # ----------------------------------------------------

        try:

            logger.info("STAGE 12: Saving linked data for job %s", job_id)
            stage_start = time.perf_counter()

            save_linked_slides(
                job_id=job_id,
                linked_slides=linked_slides,
            )

            database_storage_time_sec = _elapsed(stage_start)
            logger.info("STAGE 12: Database storage completed for job %s in %.3f sec", job_id, database_storage_time_sec)

        except Exception:

            logger.exception(
                "Database storage failed for job %s",
                job_id,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Processing completed, "
                    "but database storage failed."
                ),
            )

        # ----------------------------------------------------
        # 13. Count extracted frames
        # ----------------------------------------------------

        frame_count = len(
            list(
                job_frames_dir.glob(
                    "*.jpg"
                )
            )
        )

        # ----------------------------------------------------
        # 14. Prepare frontend slides
        # ----------------------------------------------------

        frontend_slides = []

        for index, slide in enumerate(
            linked_slides,
            start=1,
        ):

            representative_path = slide.get(
                "representative_path"
            )

            if not representative_path:
                continue

            representative_path = Path(
                representative_path
            ).resolve()

            try:

                ensure_inside_directory(
                    representative_path,
                    job_slides_dir,
                )

            except HTTPException:

                logger.warning(
                    "Ignoring slide outside "
                    "job directory: %s",
                    representative_path,
                )

                continue

            filename = (
                representative_path.name
            )

            frontend_slides.append(
                {
                    "slide_number": index,
                    "slide_id": slide.get(
                        "slide_id",
                        index,
                    ),
                    "image_url": (
                        f"/jobs/{job_id}/slides/"
                        f"{filename}"
                    ),
                    "representative_path": str(
                        representative_path
                    ),
                    "occurrences": slide.get(
                        "occurrences",
                        [],
                    ),
                    "speech_text": slide.get(
                        "speech_text",
                        "",
                    ),
                }
            )

        # ----------------------------------------------------
        # 15. Final benchmark metrics
        # ----------------------------------------------------

        transcript_segments = transcript.get(
            "segments",
            [],
        ) if isinstance(transcript, dict) else []

        transcript_words = 0
        for segment in transcript_segments:
            words = segment.get("words", []) if isinstance(segment, dict) else []
            transcript_words += len(words) if isinstance(words, list) else 0

        slide_appearances = sum(
            len(slide.get("occurrences", []))
            for slide in linked_slides
        )

        pdf_size_bytes = pdf_path.stat().st_size if pdf_path.is_file() else None

        total_processing_time_sec = _elapsed(
            processing_start
        )

        processing_ratio = None
        if video_duration_sec and video_duration_sec > 0:
            processing_ratio = round(
                total_processing_time_sec / video_duration_sec,
                4,
            )

        peak_memory_mb = memory_monitor.stop()

        performance = {
            "video_size_bytes": video_size_bytes,
            "video_duration_sec": video_duration_sec,
            "processing_fps": PROCESSING_FPS,
            "whisper_model": transcript.get("model") if isinstance(transcript, dict) else None,
            "device": transcript.get("device") if isinstance(transcript, dict) else None,
            "download_time_sec": download_time_sec,
            "frame_extraction_time_sec": frame_extraction_time_sec,
            "slide_detection_time_sec": slide_detection_time_sec,
            "pdf_generation_time_sec": pdf_generation_time_sec,
            "audio_extraction_time_sec": audio_extraction_time_sec,
            "transcription_time_sec": transcription_time_sec,
            "slide_speech_linking_time_sec": slide_speech_linking_time_sec,
            "database_storage_time_sec": database_storage_time_sec,
            "total_processing_time_sec": total_processing_time_sec,
            "frames_extracted": frame_count,
            "unique_slides": len(linked_slides),
            "slide_appearances": slide_appearances,
            "transcript_segments": len(transcript_segments),
            "transcript_words": transcript_words,
            "pdf_size_bytes": pdf_size_bytes,
            "processing_ratio": processing_ratio,
            "peak_memory_mb": peak_memory_mb,
        }

        try:
            update_job_performance(
                job_id=job_id,
                metrics=performance,
            )
        except Exception:
            logger.exception(
                "Could not save performance metrics for job %s",
                job_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Processing completed, but performance metadata could not be saved.",
            )

        # ----------------------------------------------------
        # 16. Return complete result
        # ----------------------------------------------------

        # Only the user-relevant benchmark fields are returned to the UI.
        frontend_performance = {
            "video_duration_sec": video_duration_sec,
            "total_processing_time_sec": total_processing_time_sec,
            "processing_ratio": processing_ratio,
            "frames_extracted": frame_count,
            "unique_slides": len(linked_slides),
            "slide_appearances": slide_appearances,
            "transcript_segments": len(transcript_segments),
            "video_size_bytes": video_size_bytes,
        }

        logger.info("============================================================")
        logger.info("LECTURE PROCESSING COMPLETED: job=%s total_time=%.3f sec", job_id, total_processing_time_sec)
        logger.info("============================================================")

        return {
            "status": "success",

            "job_id": job_id,

            "video": video_path.name,

            "frames_extracted": frame_count,

            "slides_detected": len(
                linked_slides
            ),

            "transcript_segments": len(transcript_segments),

            "performance": frontend_performance,

            "slides": frontend_slides,

            "pdf_url": (
                f"/jobs/{job_id}/slides.pdf"
            ),

            # IMPORTANT:
            # This is the actual filename that the
            # browser should use for the download.
            "pdf_filename": pdf_filename,

            "video_url": (
                f"/jobs/{job_id}/video"
            ),

            "pdf_available": True,

            "message": (
                "Video processed, slides extracted, "
                "audio transcribed, speech linked to slides, "
                "and data saved successfully."
            ),
        }

    except HTTPException:
        try:
            if "memory_monitor" in locals():
                memory_monitor.stop()
        except Exception:
            pass
        raise

    except Exception:

        try:
            if "memory_monitor" in locals():
                memory_monitor.stop()
        except Exception:
            pass

        logger.exception(
            "Unexpected processing error for job %s",
            job_id,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "An unexpected error occurred "
                "while processing the lecture."
            ),
        )


# ============================================================
# SEARCH LECTURE
# ============================================================

@app.get("/jobs/{job_id}/search")
def search_job(
    job_id: str,
    q: str,
):
    """
    Search transcript content for a completed job.
    """

    validate_job_id(
        job_id
    )

    query = validate_search_query(
        q
    )

    try:

        results, result_count = search_lecture(
            job_id=job_id,
            query=query,
        )

        return {
            "status": "success",
            "job_id": job_id,
            "query": query,
            "result_count": result_count,
            "results": results,
        }

    except Exception as exc:

        logger.exception(
            "Search failed for job %s",
            job_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Search failed.",
        ) from exc


# ============================================================
# SERVE SLIDE IMAGE
# ============================================================

@app.get(
    "/jobs/{job_id}/slides/{filename}"
)
def get_slide_image(
    job_id: str,
    filename: str,
):
    """
    Serve an extracted slide image safely.
    """

    validate_job_id(
        job_id
    )

    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+\.jpg",
        filename,
        re.IGNORECASE,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid slide filename.",
        )

    job_slides_dir = (
        SLIDES_DIR / job_id
    )

    slide_path = (
        job_slides_dir / filename
    )

    slide_path = validate_existing_file(
        slide_path,
        job_slides_dir,
    )

    return FileResponse(
        path=slide_path,
        media_type="image/jpeg",
    )


# ============================================================
# DOWNLOAD SLIDES PDF
# ============================================================

@app.get(
    "/jobs/{job_id}/slides.pdf"
)
def download_slides_pdf(
    job_id: str,
):
    """
    Return the generated lecture-specific PDF.

    The URL remains stable:
        /jobs/{job_id}/slides.pdf

    The actual downloaded filename is dynamic.
    """

    validate_job_id(
        job_id
    )

    job_pdf_dir = (
        PDF_DIR / job_id
    )

    if not job_pdf_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Slides PDF not found.",
        )

    # The job should contain the generated PDF.
    pdf_files = list(
        job_pdf_dir.glob(
            "*.pdf"
        )
    )

    if not pdf_files:
        raise HTTPException(
            status_code=404,
            detail="Slides PDF not found.",
        )

    # There should normally be exactly one PDF.
    # Select the first generated PDF.
    pdf_path = pdf_files[0]

    pdf_path = validate_existing_file(
        pdf_path,
        job_pdf_dir,
    )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )


# ============================================================
# SERVE VIDEO
# ============================================================

@app.get(
    "/jobs/{job_id}/video"
)
def get_video(
    job_id: str,
):
    """
    Serve the original lecture video.
    """

    validate_job_id(
        job_id
    )

    job_input_dir = (
        INPUT_DIR / job_id
    )

    if not job_input_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Lecture video not found.",
        )

    candidate_files = []

    for extension in ALLOWED_VIDEO_EXTENSIONS:

        candidate_files.extend(
            job_input_dir.glob(
                f"*{extension}"
            )
        )

    if not candidate_files:
        raise HTTPException(
            status_code=404,
            detail="Lecture video not found.",
        )

    video_path = sorted(
        candidate_files
    )[0]

    video_path = validate_existing_file(
        video_path,
        job_input_dir,
    )

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=video_path.name,
    )