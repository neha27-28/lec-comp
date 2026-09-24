from fastapi import FastAPI, UploadFile, File, Form, HTTPException
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
)

from pathlib import Path
import shutil
import uuid
import re


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(title="Lecture Companion API")


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    # --------------------------------------------------------
    # 1. Validate input
    # --------------------------------------------------------

    if not lecture_url.strip() and video is None:
        raise HTTPException(
            status_code=400,
            detail="Please provide a lecture URL or upload a video.",
        )

    # --------------------------------------------------------
    # 2. Create unique job
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

    # --------------------------------------------------------
    # 3. Save / download video
    # --------------------------------------------------------

    if video is not None:

        if not video.filename:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file has no filename.",
            )

        video_path = job_input_dir / video.filename

        with video_path.open("wb") as buffer:
            shutil.copyfileobj(
                video.file,
                buffer,
            )

    else:

        try:
            video_path = Path(
                download_video(
                    url=lecture_url.strip(),
                    output_dir=str(job_input_dir),
                )
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Could not download the YouTube video: {exc}"
                ),
            )

    # --------------------------------------------------------
    # 4. Save initial job information
    # --------------------------------------------------------

    try:
        save_job(
            job_id=job_id,
            video_filename=video_path.name,
            video_path=str(video_path),
            fps=3.0,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save job information: {exc}",
        )

    # --------------------------------------------------------
    # 5. Extract frames
    # --------------------------------------------------------

    try:

        extract_frames(
            video_path=str(video_path),
            output_dir=str(job_frames_dir),
            fps=3,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not extract video frames: {exc}",
        )

    # --------------------------------------------------------
    # 6. Detect slides
    # --------------------------------------------------------

    try:

        slides = detect_slides(
            frames_dir=str(job_frames_dir),
            output_dir=str(job_slides_dir),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not detect slides: {exc}",
        )

    # --------------------------------------------------------
    # 7. Generate PDF
    # --------------------------------------------------------

    pdf_path = job_pdf_dir / "lecture_slides.pdf"

    try:

        create_slides_pdf(
            slides=slides,
            output_path=pdf_path,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Slides were extracted, "
                f"but PDF could not be generated: {exc}"
            ),
        )

    # --------------------------------------------------------
    # 8. Extract audio
    # --------------------------------------------------------

    audio_path = job_audio_dir / "lecture_audio.wav"

    try:

        extract_audio(
            video_path=str(video_path),
            output_path=str(audio_path),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not extract audio: {exc}",
        )

    # --------------------------------------------------------
    # 9. Transcribe audio using Whisper
    # --------------------------------------------------------

    try:

        transcript = transcribe_audio(
            audio_path=str(audio_path),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not transcribe audio: {exc}",
        )

    # --------------------------------------------------------
    # 10. Link slides with speech
    # --------------------------------------------------------

    try:

        linked_slides_result = link_slides_to_speech(
            slides=slides,
            transcript=transcript,
            fps=3.0,
        )
        linked_slides = linked_slides_result.get("slides", [])

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Slides and speech were extracted, "
                f"but linking failed: {exc}"
            ),
        )

    # --------------------------------------------------------
    # 11. Save linked data into SQLite
    # --------------------------------------------------------

    try:

        save_linked_slides(
            job_id=job_id,
            linked_slides=linked_slides,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Processing completed, "
                f"but database storage failed: {exc}"
            ),
        )

    # --------------------------------------------------------
    # 12. Count extracted frames
    # --------------------------------------------------------

    frame_count = len(
        list(job_frames_dir.glob("*.jpg"))
    )

    # --------------------------------------------------------
    # 13. Prepare slides for frontend
    # --------------------------------------------------------

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

        filename = Path(
            representative_path
        ).name

        frontend_slides.append(
            {
                "slide_number": index,

                "slide_id": slide.get(
                    "slide_id",
                    index,
                ),

                "image_url": (
                    f"/jobs/{job_id}/slides/{filename}"
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

    # --------------------------------------------------------
    # 14. Return complete processing result
    # --------------------------------------------------------

    return {

        "status": "success",

        "job_id": job_id,

        "video": (
            video.filename
            if video is not None
            else video_path.name
        ),

        "frames_extracted": frame_count,

        "slides_detected": len(
            linked_slides
        ),

        "transcript_segments": len(
            transcript.get(
                "segments",
                []
            )
        ),

        "slides": frontend_slides,

        "pdf_available": True,

        "pdf_filename": "lecture_slides.pdf",

        "pdf_url": (
            f"/jobs/{job_id}/slides.pdf"
        ),

        "message": (
            "Video processed, slides extracted, "
            "audio transcribed, speech linked to slides, "
            "and data saved successfully."
        ),
    }


# ============================================================
# SEARCH LECTURE
# ============================================================

@app.get("/jobs/{job_id}/search")
def search_job(
    job_id: str,
    q: str,
):

    # Validate job ID
    if not re.fullmatch(
        r"[0-9a-f]{8}",
        job_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID.",
        )

    if not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    try:

        results = search_lecture(
            job_id=job_id,
            query=q.strip(),
        )

        return {
            "status": "success",
            "job_id": job_id,
            "query": q.strip(),
            "results": results,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {exc}",
        )


# ============================================================
# SERVE SLIDE IMAGE
# ============================================================

@app.get("/jobs/{job_id}/slides/{filename}")
def get_slide_image(
    job_id: str,
    filename: str,
):

    # --------------------------------------------------------
    # Validate job ID
    # --------------------------------------------------------

    if not re.fullmatch(
        r"[0-9a-f]{8}",
        job_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID.",
        )

    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not re.fullmatch(
        r"[\w.-]+\.jpg",
        filename,
        re.IGNORECASE,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid slide filename.",
        )

    # --------------------------------------------------------
    # Locate slide
    # --------------------------------------------------------

    slide_path = (
        SLIDES_DIR
        / job_id
        / filename
    )

    if not slide_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Slide image not found.",
        )

    # --------------------------------------------------------
    # Return image
    # --------------------------------------------------------

    return FileResponse(
        path=slide_path,
        media_type="image/jpeg",
    )


# ============================================================
# DOWNLOAD SLIDES PDF
# ============================================================

@app.get("/jobs/{job_id}/slides.pdf")
def download_slides_pdf(
    job_id: str,
):

    if not re.fullmatch(
        r"[0-9a-f]{8}",
        job_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID.",
        )

    pdf_path = (
        PDF_DIR
        / job_id
        / "lecture_slides.pdf"
    )

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Slides PDF not found.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename="lecture_slides.pdf",
    )


# ============================================================
# SERVE ORIGINAL VIDEO
# ============================================================

@app.get("/jobs/{job_id}/video")
def get_video(
    job_id: str,
):

    if not re.fullmatch(
        r"[0-9a-f]{8}",
        job_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID.",
        )

    job_input_dir = INPUT_DIR / job_id

    if not job_input_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    video_files = [
        path
        for path in job_input_dir.iterdir()
        if path.is_file()
        and path.suffix.lower()
        in {
            ".mp4",
            ".webm",
            ".mov",
            ".mkv",
        }
    ]

    if not video_files:
        raise HTTPException(
            status_code=404,
            detail="Video file not found.",
        )

    video_path = video_files[0]

    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }

    return FileResponse(
        path=video_path,
        media_type=media_types.get(
            video_path.suffix.lower(),
            "application/octet-stream",
        ),
    )