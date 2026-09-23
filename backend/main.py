from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from services.slide_detector import detect_slides
from services.pdf_generator import create_slides_pdf
from services.video_processor import extract_frames
from services.downloader import download_video

from pathlib import Path
import shutil
import uuid
import re

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


INPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FRAMES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SLIDES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PDF_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# BASIC ENDPOINTS
# ============================================================


@app.get("/")
def root():
    return {"message": "Lecture Companion API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ============================================================
# PROCESS LECTURE
# ============================================================


@app.post("/process")
async def process_lecture(
    lecture_url: str = Form(default=""),
    video: UploadFile | None = File(default=None),
):
    """
    Process a lecture supplied either as:

    1. YouTube URL
    2. Uploaded video

    Current pipeline:

    video
        ↓
    frame extraction
        ↓
    slide detection
        ↓
    unique slide images
        ↓
    slide PDF generation
    """

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if not lecture_url.strip() and video is None:
        raise HTTPException(
            status_code=400,
            detail=("Please provide a lecture URL " "or upload a video."),
        )

    # --------------------------------------------------------
    # Create unique processing job
    # --------------------------------------------------------

    job_id = uuid.uuid4().hex[:8]

    job_input_dir = INPUT_DIR / job_id
    job_frames_dir = FRAMES_DIR / job_id
    job_slides_dir = SLIDES_DIR / job_id
    job_pdf_dir = PDF_DIR / job_id

    job_input_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    job_frames_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    job_slides_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    job_pdf_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # CASE 1: Uploaded video
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

    # --------------------------------------------------------
    # CASE 2: YouTube URL
    # --------------------------------------------------------

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
                detail=("Could not download the YouTube video: " f"{exc}"),
            )

    # --------------------------------------------------------
    # Extract frames
    # --------------------------------------------------------

    extract_frames(
        video_path=str(video_path),
        output_dir=str(job_frames_dir),
        fps=3,
    )

    # --------------------------------------------------------
    # Detect logical slides
    # --------------------------------------------------------

    slides = detect_slides(
        frames_dir=str(job_frames_dir),
        output_dir=str(job_slides_dir),
        #fps=2.0,
    )

    # --------------------------------------------------------
    # Generate PDF containing unique slides
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
                "Slides were extracted, but the PDF " f"could not be generated: {exc}"
            ),
        )

    # --------------------------------------------------------
    # Count extracted frames
    # --------------------------------------------------------

    frame_count = len(list(job_frames_dir.glob("*.jpg")))

    # --------------------------------------------------------
    # Return processing result
    # --------------------------------------------------------

    return {
        "status": "success",
        "job_id": job_id,
        "video": (video.filename if video is not None else video_path.name),
        "frames_extracted": frame_count,
        "slides_detected": len(slides),
        "slides": slides,
        "pdf_available": True,
        "pdf_filename": "lecture_slides.pdf",
        "pdf_url": (f"/jobs/{job_id}/slides.pdf"),
        "message": (
            "Video processed, unique slides extracted, "
            "and PDF generated successfully."
        ),
    }


# ============================================================
# DOWNLOAD SLIDES PDF
# ============================================================


@app.get("/jobs/{job_id}/slides.pdf")
def download_slides_pdf(job_id: str):

    # Job IDs are generated internally as 8 hexadecimal
    # characters. Reject anything else before touching
    # the filesystem.
    if not re.fullmatch(
        r"[0-9a-f]{8}",
        job_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID.",
        )

    pdf_path = PDF_DIR / job_id / "lecture_slides.pdf"

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
