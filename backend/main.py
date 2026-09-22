from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware


from pathlib import Path
import shutil
import uuid

from services.video_processor import extract_frames
from services.downloader import download_video


app = FastAPI(title="Lecture Companion API")


# Allow our React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "data" / "input"
FRAMES_DIR = BASE_DIR / "data" / "frames"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


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


@app.post("/process")
async def process_lecture(
    lecture_url: str = Form(default=""),
    video: UploadFile | None = File(default=None)
):
    """
    Process a lecture supplied either as:
    1. YouTube URL
    2. Uploaded video

    Current stage:
    - Save the video locally
    - Extract frames using FFmpeg

    Slide detection, transcription and search
    will be added in later stages.
    """

    # We need either a URL or an uploaded file
    if not lecture_url.strip() and video is None:
        raise HTTPException(
            status_code=400,
            detail="Please provide a lecture URL or upload a video."
        )

    # Create a unique ID for this processing job
    job_id = uuid.uuid4().hex[:8]

    job_input_dir = INPUT_DIR / job_id
    job_frames_dir = FRAMES_DIR / job_id

    job_input_dir.mkdir(parents=True, exist_ok=True)
    job_frames_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------
    # CASE 1: Uploaded video
    # --------------------------------------------------

    if video is not None:

        # Basic validation
        if not video.filename:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file has no filename."
            )

        video_path = job_input_dir / video.filename

        with video_path.open("wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

    # --------------------------------------------------
    # CASE 2: YouTube URL
    # --------------------------------------------------

    else:
        try:
            video_path = Path(
                download_video(
                    url=lecture_url.strip(),
                    output_dir=str(job_input_dir)
                    
                )
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Could not download the YouTube video: {str(e)}"
            )

    # --------------------------------------------------
    # Extract frames
    # --------------------------------------------------

    extract_frames(
        video_path=str(video_path),
        output_dir=str(job_frames_dir),
        fps=2
    )

    frame_count = len(list(job_frames_dir.glob("*.jpg")))

    return {
        "status": "success",
        "job_id": job_id,
        "video": video.filename if video is not None else video_path.name,
        "frames_extracted": frame_count,
        "message": "Video saved locally and frames extracted successfully."
    }