# Lecture Companion

> **Turn long lectures into something you can actually find.**

Lecture Companion is a **local-first educational video processing tool** that transforms long lectures into searchable, timestamped study material.

Instead of manually scrubbing through a lecture, a user can provide a **YouTube lecture URL or a local video**, process it on their own machine, search for a topic, see the relevant slide and spoken explanation, and jump directly to the corresponding moment in the lecture.

> **Deployment note:** Lecture Companion is currently designed as a **local, single-user application**. The current backend should not be exposed directly to the public internet without adding authentication, authorization, rate limiting, stronger process isolation, and deployment-level controls.

The core idea is:

```text
Lecture Video
     ↓
Extract Frames
     ↓
Detect Unique Slides
     ↓
Extract Audio
     ↓
Local Whisper Transcription
     ↓
Link Speech ↔ Slides
     ↓
Store Locally
     ↓
Search
     ↓
Slide + Explanation + Timestamp
     ↓
Jump to the Lecture
```

---

## Table of Contents

- [Why Lecture Companion?](#why-lecture-companion)
- [Core Idea](#core-idea)
- [Key Features](#key-features)
- [What Makes It Different](#what-makes-it-different)
- [Architecture](#architecture)
- [End-to-End Pipeline](#end-to-end-pipeline)
- [Slide Detection Pipeline](#slide-detection-pipeline)
- [Speech Processing](#speech-processing)
- [Slide–Speech Linking](#slide-speech-linking)
- [Search](#search)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Using Lecture Companion](#using-lecture-companion)
- [API Overview](#api-overview)
- [Output Structure](#output-structure)
- [Performance Benchmarking](#performance-benchmarking)
- [Security](#security)
- [Current Limitations](#current-limitations)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

# Why Lecture Companion?

Long educational videos contain multiple layers of information:

- visual slides,
- spoken explanations,
- timestamps,
- repeated concepts,
- examples,
- demonstrations,
- and transitions between topics.

Traditional video playback makes this information difficult to navigate.

A student may remember:

> "The professor explained selection sort somewhere around the middle."

But finding that explanation manually requires scanning the recording.

Lecture Companion converts the lecture into a searchable relationship:

```text
Search term
    ↓
Spoken explanation
    ↓
Relevant slide
    ↓
Timestamp
    ↓
Exact point in video
```

This makes the lecture behave more like a searchable study document while retaining the original video.

---

# Core Idea

Lecture Companion is designed around a **slide–speech relationship**, not just transcript generation.

For example:

```text
Search:
"selection sort"

        ↓

Transcript match:
"The selection sort algorithm..."

        ↓

Associated slide:
Slide 8

        ↓

Timestamp:
05:28

        ↓

Click result

        ↓

Video jumps to:
05:28
```

The important output is therefore not simply:

```text
"text + timestamp"
```

but:

```text
"slide + spoken explanation + timestamp + original video"
```

---

# Key Features

## 1. Local Video Upload

Users can select a lecture video directly from their computer.

Supported video formats include:

- `.mp4`
- `.webm`
- `.mov`
- `.mkv`

The backend stores uploaded material inside a job-specific local directory.

---

## 2. YouTube Lecture Ingestion

A user can provide a YouTube lecture URL.

The application:

1. validates the URL,
2. verifies that it belongs to an allowed YouTube hostname,
3. downloads the video locally using `yt-dlp`,
4. validates the downloaded file,
5. continues with the local processing pipeline.

Only HTTPS YouTube URLs are accepted by the current backend.

---

## 3. Frame Extraction

FFmpeg is used to extract video frames.

The current slide-analysis pipeline intentionally uses:

```text
3 FPS
```

This means the detector samples approximately three frames per second.

The project deliberately retains 3 FPS because lower sampling was found insufficient for the intended slide-transition detection behavior.

---

## 4. OCR-Free Slide Detection

Lecture Companion does not depend on OCR to identify slides.

The slide detector uses visual information from frames, including:

- visual transition analysis,
- structural similarity,
- temporal transition confirmation,
- adaptive/recovery thresholds,
- visibility analysis,
- sharpness-based representative-frame selection,
- complementary-view selection,
- pHash-based duplicate detection,
- SSIM-based duplicate verification,
- edge-based similarity,
- logical slide grouping,
- revisited-slide recognition.

The objective is to identify the actual slide views displayed during the lecture while avoiding unnecessary duplicate images.

---

## 5. Revisited-Slide Recognition

Lectures frequently return to an earlier slide.

For example:

```text
Slide 1
Slide 2
Slide 3
Slide 2
Slide 4
```

The system should recognize that the second occurrence of Slide 2 is a revisit rather than an entirely new unique slide.

This allows the application to distinguish:

```text
unique slides
```

from:

```text
slide appearances
```

---

## 6. Representative Slide Selection

A slide may appear across many frames.

Instead of storing every frame as a separate slide, the system selects representative views.

The detector considers factors such as:

- visibility,
- sharpness,
- visual similarity,
- slide continuity,
- duplicate relationships.

---

## 7. Slide PDF Generation

The unique extracted slides can be assembled into a PDF.

The generated PDF uses the lecture-derived filename.

For example:

```text
Operating Systems Lecture 05.mp4
```

produces:

```text
Operating Systems Lecture 05.pdf
```

---

## 8. Local Audio Extraction

Audio is extracted locally from the lecture video.

The audio-processing pipeline prepares audio for Whisper transcription.

The current implementation converts audio to:

```text
Mono
16 kHz
PCM WAV
```

---

## 9. Local Whisper Transcription

Whisper is used locally to generate timestamped speech segments.

The current transcription configuration uses:

```text
Model: small.en
Language: English
Word timestamps: enabled
```

The application automatically uses:

```text
CUDA
```

when a CUDA-capable PyTorch environment is available; otherwise it falls back to CPU.

The transcript contains timestamped segments and word-level timing information.

---

## 10. Slide–Speech Linking

Transcript segments are associated with slide intervals.

Conceptually:

```text
Slide 8
05:20 ─────────────────── 05:47

Speech:
"The selection sort algorithm..."
```

The resulting record can therefore associate:

```text
Slide 8
+
spoken explanation
+
05:20
```

This is one of the central components of Lecture Companion.

---

## 11. SQLite Persistence

Lecture information is stored locally in SQLite.

The database stores structured relationships involving:

- jobs,
- slides,
- slide occurrences,
- speech segments,
- timestamps,
- slide–speech relationships,
- performance metadata.

The application does not require a remote database server.

---

## 12. FTS5 / BM25 Search

Search is implemented using SQLite FTS5 and BM25-style ranking.

This allows users to search lecture content instead of manually scanning the video.

Example:

```text
selection sort
```

can return multiple matching speech segments associated with different slide appearances.

---

## 13. Timestamp-Based Playback

Search results contain timestamp information.

Selecting a result:

1. identifies the relevant timestamp,
2. sets the video player's current time,
3. starts playback,
4. brings the video into view.

This creates the complete:

```text
Search → Understand → Jump
```

workflow.

---

## 14. Local Processing

Lecture Companion is designed around local processing.

The intended architecture is:

```text
User Machine
│
├── React frontend
├── FastAPI backend
├── FFmpeg
├── Whisper
├── SQLite
└── Lecture data
```

Lecture content does not need to be uploaded to a third-party AI processing service for the core processing pipeline.

When a YouTube URL is supplied, the application necessarily retrieves the source video from YouTube. After retrieval, the processing pipeline remains local.

---

# What Makes It Different?

A transcript alone answers:

> "What was said?"

A slide extractor answers:

> "Which slides were shown?"

Lecture Companion combines them:

> "What was said while this slide was being shown, and where can I jump to it?"

The central relationship is:

```text
                 ┌──────────────┐
                 │   Lecture    │
                 └──────┬───────┘
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
       Visual stream          Audio stream
             │                     │
             ▼                     ▼
      Slide detection           Whisper
             │                     │
             ▼                     ▼
       Slide intervals      Speech segments
             │                     │
             └──────────┬──────────┘
                        ▼
                Slide–Speech Link
                        │
                        ▼
                     Search
                        │
                        ▼
              Slide + Speech + Time
```

---

# Architecture

## High-Level Architecture

```text
                         USER
                          │
                          ▼
                 ┌─────────────────┐
                 │ React / Vite UI │
                 └────────┬────────┘
                          │ HTTP
                          ▼
                 ┌─────────────────┐
                 │   FastAPI API   │
                 └────────┬────────┘
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
     Local Upload      YouTube          Search API
                          │
                       yt-dlp
                          │
          └───────────────┼────────────────┘
                          ▼
                       Video
                          │
                       FFmpeg
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
        Video Frames                Audio
             │                         │
             ▼                         ▼
      Slide Detector                Whisper
             │                         │
             ▼                         ▼
      Slide Intervals          Transcript Segments
             │                         │
             └────────────┬────────────┘
                          ▼
                 Slide–Speech Linker
                          │
                          ▼
                       SQLite
                          │
                       FTS5/BM25
                          │
                          ▼
                    Search Results
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
          Slide                   Timestamp
             │                         │
             └────────────┬────────────┘
                          ▼
                    Video Player
```

---

# End-to-End Pipeline

The current processing workflow is:

```text
1. Receive YouTube URL or local video
                    ↓
2. Validate input
                    ↓
3. Create isolated job directories
                    ↓
4. Save or download lecture
                    ↓
5. Validate final video
                    ↓
6. Extract frames at 3 FPS
                    ↓
7. Detect slide transitions
                    ↓
8. Group slide appearances
                    ↓
9. Select representative views
                    ↓
10. Detect duplicates/revisited slides
                    ↓
11. Generate unique slide images
                    ↓
12. Generate slide PDF
                    ↓
13. Extract audio
                    ↓
14. Transcribe locally with Whisper
                    ↓
15. Link transcript segments to slides
                    ↓
16. Save structured data in SQLite
                    ↓
17. Build/search FTS5 index
                    ↓
18. Return slide + speech + timestamp data
                    ↓
19. User searches for a topic
                    ↓
20. User selects a result
                    ↓
21. Video jumps to the corresponding timestamp
```

---

# Slide Detection Pipeline

The slide detector is intentionally more sophisticated than a simple "compare every frame to the previous frame" approach.

## Stage 1 — Frame Sampling

Frames are extracted at:

```text
3 FPS
```

---

## Stage 2 — Visual Transition Analysis

The detector looks for meaningful changes between frames.

---

## Stage 3 — Structural Similarity

SSIM is used to determine how structurally similar frames are.

This helps distinguish:

```text
same slide
```

from:

```text
new slide
```

---

## Stage 4 — Edge Similarity

Edge information provides another structural signal.

This is useful when visual appearance changes slightly but the underlying slide structure remains similar.

---

## Stage 5 — pHash Deduplication

Perceptual hashing helps identify visually similar slide images even when they are not pixel-identical.

---

## Stage 6 — Temporal Confirmation

Candidate transitions are not treated as isolated frame differences.

Temporal evidence helps confirm whether a change represents a genuine slide transition.

---

## Stage 7 — Logical Grouping

Frames belonging to the same slide appearance are grouped together.

---

## Stage 8 — Representative Frame Selection

The detector selects a useful representative frame based on visual quality and slide visibility.

---

## Stage 9 — Revisited Slide Recognition

Previously seen slides can be recognized when the lecture returns to them.

---

# Speech Processing

The audio pipeline is:

```text
Lecture Video
     ↓
FFmpeg
     ↓
16 kHz Mono PCM WAV
     ↓
Whisper
     ↓
Timestamped transcript
     ↓
Slide–Speech Linker
```

The current Whisper configuration uses:

```text
Model: small.en
Task: transcription
Language: English
Word timestamps: enabled
```

The model uses GPU execution when CUDA is available and CPU otherwise.

---

# Slide–Speech Linking

A lecture can be represented as a timeline:

```text
00:00 ─────────────────────────────────────────────── 10:00

Slide 1
████████

          Slide 2
          █████████████

                         Slide 3
                         █████████████████

Speech
████████████████████████████████████████████████████
```

The linker associates transcript segments with the slide interval during which they occur.

The resulting data can then answer:

```text
"What was being explained on Slide 3?"
```

and:

```text
"Where in the lecture was that explanation?"
```

---

# Search

The backend exposes a search endpoint for completed lecture jobs.

The search layer uses SQLite FTS5/BM25.

Example:

```text
Query:
"selection sort"
```

Possible result:

```text
Slide 8
05:28
"The selection sort algorithm..."
```

The frontend converts this into an interactive result.

Selecting it moves the video to the relevant timestamp.

---

# Project Structure

A simplified repository structure is:

```text
lecture-companion/
│
├── backend/
│   │
│   ├── main.py
│   ├── database.py
│   ├── requirements.txt
│   │
│   ├── services/
│   │   ├── video_processor.py
│   │   ├── downloader.py
│   │   ├── slide_detector.py
│   │   ├── audio_processor.py
│   │   ├── transcriber.py
│   │   ├── slide_speech_linker.py
│   │   └── pdf_generator.py
│   │
│   ├── data/
│   │   ├── input/
│   │   ├── frames/
│   │   ├── slides/
│   │   ├── audio/
│   │   └── pdfs/
│   │
│   └── lecture_companion.db
│
├── frontend/
│   │
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   │
│   ├── package.json
│   └── ...
│
├── README.md
└── ...
```

> The exact repository may contain additional development, configuration and generated files. The structure above focuses on the application components.

---

# Technology Stack

## Frontend

- React
- Vite
- Tailwind CSS

## Backend

- Python
- FastAPI
- Uvicorn

## Video Processing

- FFmpeg
- yt-dlp

## Computer Vision / Slide Detection

- OpenCV-based image processing
- SSIM
- pHash
- Edge similarity
- Frame analysis

## Speech Processing

- Whisper
- PyTorch

## Storage

- SQLite
- SQLite FTS5
- BM25 ranking

## PDF

- ReportLab

## Monitoring / Benchmarking

- Python timing instrumentation
- psutil

---

# Requirements

Before running Lecture Companion, install:

### Required software

- Python
- Node.js and npm
- FFmpeg

The backend additionally requires the Python packages listed in:

```text
backend/requirements.txt
```

The frontend dependencies are defined by:

```text
frontend/package.json
```

---

# Installation

## 1. Clone the repository

```bash
git clone https://github.com/neha27-28/lec-comp.git
cd lec-comp
```

---

## 2. Backend setup

Move into the backend directory:

```bash
cd backend
```

Create a virtual environment:

### Windows

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

---

## 3. Verify FFmpeg

FFmpeg must be available in the system PATH.

Verify:

```powershell
ffmpeg -version
```

Also verify:

```powershell
ffprobe -version
```

Both commands should return installed-version information.

---

## 4. Frontend setup

Open another terminal.

Move to the frontend:

```powershell
cd frontend
```

Install dependencies:

```powershell
npm install
```

---

# Running the Application

Lecture Companion runs as a local web application with two processes.

## Terminal 1 — Backend

From:

```text
backend/
```

run:

```powershell
uvicorn main:app --reload
```

The FastAPI backend runs on:

```text
http://127.0.0.1:8000
```

---

## Terminal 2 — Frontend

From:

```text
frontend/
```

run:

```powershell
npm run dev
```

The Vite development server normally runs on:

```text
http://localhost:5173
```

or:

```text
http://127.0.0.1:5173
```

Open the displayed frontend URL in your browser.

---

# Using Lecture Companion

## Option A — YouTube Lecture

1. Open the frontend.
2. Paste a YouTube lecture URL.
3. Start processing.
4. Wait for local processing to complete.
5. Search for a concept.
6. Review the returned slide and speech.
7. Click the result.
8. The video jumps to the relevant timestamp.

---

## Option B — Local Lecture Video

1. Open the frontend.
2. Select a local lecture video.
3. Start processing.
4. Wait for extraction and transcription.
5. Search the processed lecture.
6. Select a result.
7. Jump directly to the relevant point in the video.

---

# Processing Logs

The backend uses INFO-level logging.

During frame extraction, progress logging can show information such as:

```text
frame=1
frame=2
frame=3
...
```

and media-processing progress can expose timing information such as:

```text
time=00:00:01
time=00:00:02
time=00:00:03
...
```

Stage-level processing logs are intended to make long local processing runs easier to monitor.

---

# API Overview

## Health Check

```http
GET /
```

Returns a basic API status message.

---

## Health

```http
GET /health
```

Returns:

```json
{
  "status": "ok"
}
```

---

## Process Lecture

```http
POST /process
```

Accepts either:

- a YouTube URL, or
- a local uploaded video.

The request must not provide both simultaneously.

The endpoint performs the complete processing pipeline.

---

## Search

```http
GET /jobs/{job_id}/search?q={query}
```

Searches the processed lecture using the local search index.

The backend currently limits search queries to:

```text
200 characters
```

---

## Serve Slide

```http
GET /jobs/{job_id}/slides/{filename}
```

Returns a generated slide image.

The backend validates the job ID and requested filename before serving the file.

---

## Download PDF

```http
GET /jobs/{job_id}/slides.pdf
```

Returns the generated slide PDF.

The downloaded filename is derived from the lecture filename.

---

## Serve Video

```http
GET /jobs/{job_id}/video
```

Returns the original locally stored lecture video for playback.

---

# Output Structure

Each processing job receives an isolated job identifier.

Conceptually:

```text
backend/data/
│
├── input/
│   └── <job_id>/
│       └── lecture.mp4
│
├── frames/
│   └── <job_id>/
│       ├── frame_000001.jpg
│       ├── frame_000002.jpg
│       └── ...
│
├── slides/
│   └── <job_id>/
│       ├── slide_001.jpg
│       ├── slide_002.jpg
│       └── ...
│
├── audio/
│   └── <job_id>/
│       └── lecture_audio.wav
│
└── pdfs/
    └── <job_id>/
        └── <lecture-name>.pdf
```

The exact number of generated files depends on the lecture and detector output.

---

# Performance Benchmarking

Performance is treated as a separate engineering concern because lecture processing is computationally expensive.

The application records benchmark metadata including:

- video size,
- video duration,
- processing FPS,
- Whisper model,
- processing device,
- download time,
- frame extraction time,
- slide detection time,
- PDF generation time,
- audio extraction time,
- transcription time,
- slide–speech linking time,
- database storage time,
- total processing time,
- frames extracted,
- unique slides,
- slide appearances,
- transcript segments,
- transcript words,
- PDF size,
- processing ratio,
- peak memory.

## Processing Ratio

The project uses:

```text
Processing Ratio =
Total Processing Time / Lecture Duration
```

Example:

```text
Lecture duration = 40 minutes
Processing time  = 12 minutes

Processing ratio = 12 / 40
                 = 0.30
```

A lower ratio means less processing time relative to lecture duration.

---

# Security

Lecture Companion has been hardened around the major application-level attack surfaces.

## Input Protection

- Supported video extensions are allowlisted.
- Upload size is limited to 4 GB.
- Uploads use bounded 1 MB chunks.
- Search queries are limited to 200 characters.
- YouTube URLs require HTTPS.
- YouTube hostnames are explicitly allowlisted.
- Embedded credentials in URLs are rejected.
- Explicit URL ports are rejected.

---

## Filesystem Protection

The backend:

- sanitizes filenames,
- rejects traversal-style paths,
- resolves paths before use,
- checks that generated paths remain inside their intended directories,
- isolates files by processing job,
- validates files before serving them.

---

## Subprocess Protection

FFmpeg commands use controlled argument arrays and:

```python
shell=False
```

User input is not directly interpreted as shell syntax.

---

## Resource Protection

The current design includes:

- 4 GB input limit,
- bounded upload writes,
- validated FPS,
- 3 FPS processing configuration,
- maximum generated-frame protection,
- cleanup of partial frame output,
- file validation,
- performance monitoring.

---

## CORS

The local backend currently permits the intended local frontend origins:

```text
http://localhost:5173
http://127.0.0.1:5173
```

The application is designed as a **trusted local single-user application**, not as a public multi-user service. The current security controls reduce application-level risks within that scope; they do not make the current backend suitable for direct public-internet exposure.

---


# Privacy Model

Lecture Companion is intentionally designed around local processing.

## Local

The following are processed/stored locally:

- uploaded lecture videos,
- downloaded lecture videos after retrieval,
- extracted frames,
- slide images,
- audio,
- Whisper transcripts,
- slide–speech relationships,
- SQLite data,
- generated PDFs.

## Network-dependent

The primary external dependency is YouTube when the user supplies a YouTube URL.

The application retrieves the source lecture from YouTube and then processes the downloaded material locally.

## Important Scope

"Local processing" does not mean that a YouTube source is never contacted.

It means that the core processing pipeline does not require sending lecture content to a third-party AI processing service.

---


# Current Limitations

## 1. English-focused transcription

The current Whisper configuration uses:

```text
small.en
language="en"
```

Therefore, the current configuration is optimized for English lectures.

---

## 2. Resource-intensive processing

Lecture processing can be computationally expensive, particularly:

- frame extraction,
- slide detection,
- Whisper transcription.

Performance depends on:

- video resolution,
- lecture duration,
- number of visual transitions,
- CPU,
- RAM,
- GPU availability,
- storage speed.

---

## 3. Slide–speech inference is temporal

The system links speech to slide intervals based on timing.

Therefore, if a lecturer says:

> "As you can see on the previous slide..."

while the previous slide is no longer visible, purely time-based linking may not perfectly capture that semantic reference.

---

## 4. Webcam overlays

If a lecturer's webcam significantly covers a slide, the visible slide region may become harder to detect or represent accurately.

---

## 5. Local storage usage

Processing can generate:

- source video,
- frames,
- slide images,
- audio,
- PDF,
- database records.

Long lectures therefore consume local disk space.

---

## 6. Single-user architecture

The current application is intended for a trusted local user.

It is not designed as a public multi-user service with:

- accounts,
- authentication,
- authorization,
- tenant isolation,
- distributed storage,
- public API rate limiting.

---

# Troubleshooting

## Backend does not start

Verify that the virtual environment is activated:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then reinstall dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run:

```powershell
uvicorn main:app --reload
```

---

## `ffmpeg` is not recognized

Run:

```powershell
ffmpeg -version
```

If Windows cannot find the command, install FFmpeg and add its executable directory to the system PATH.

Also verify:

```powershell
ffprobe -version
```

---

## `reportlab` import error

Install:

```powershell
python -m pip install reportlab
```

Then verify:

```powershell
python -c "import reportlab; print(reportlab.Version)"
```

---

## Whisper is slow

Whisper performance depends strongly on the available hardware.

Check whether PyTorch detects CUDA:

```powershell
python -c "import torch; print(torch.cuda.is_available())"
```

If it returns:

```text
False
```

Whisper will run on CPU under the current configuration.

---

## Frontend cannot connect to backend

Verify that the backend is running:

```text
http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

Then verify that the frontend is running on the expected Vite development port.

---

## Search returns no results

Check:

1. processing completed successfully,
2. the correct job is loaded,
3. the search query is not empty,
4. the query is within the 200-character limit,
5. transcript data exists for the lecture.

---


# Contributing

For development work:

1. Create a feature branch.
2. Keep changes scoped to the feature being worked on.
3. Do not commit generated lecture data.
4. Do not commit private lecture videos, transcripts or extracted frames.
5. Test the complete local workflow after backend changes.
6. Update documentation when architecture or security behavior changes.
7. Keep security-sensitive path and subprocess handling conservative.

A typical workflow is:

```bash
git checkout -b feature/<name>

# make changes

git status
git diff

git add .
git commit -m "Describe the change"

git push origin feature/<name>
```

---


# Project Philosophy

Lecture Companion is built around a simple idea:

> **Don't make students search the lecture. Make the lecture searchable.**

The project combines:

```text
Visual understanding
        +
Speech understanding
        +
Temporal alignment
        +
Local search
        +
Direct playback
```

to turn a long lecture recording into a navigable learning resource.

---

## Final Workflow

```text
                  LECTURE COMPANION
                         │
                         ▼
              YouTube / Local Video
                         │
                         ▼
                  Local Ingestion
                         │
                         ▼
                    FFmpeg
                         │
                         ▼
                 Frame Extraction
                     3 FPS
                         │
                         ▼
              Slide Detection Engine
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       SSIM            pHash         Edge Analysis
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                Slide Grouping
                         │
                         ▼
              Revisited Recognition
                         │
                         ▼
                Unique Slide Set
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
         PDF Generation        Audio Extraction
                                      │
                                      ▼
                                   Whisper
                                      │
                                      ▼
                            Timestamped Speech
                                      │
                         ┌────────────┘
                         ▼
                 Slide–Speech Linking
                         │
                         ▼
                      SQLite
                         │
                      FTS5/BM25
                         │
                         ▼
                       Search
                         │
                         ▼
              Slide + Speech + Time
                         │
                         ▼
                  Video Timestamp
                         │
                         ▼
                    Learn Faster
```

**Lecture Companion — Search. Learn. Revise.**
