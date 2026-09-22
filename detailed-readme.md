Lecture Companion
Current Implementation Status
Project: Lecture Companion — An Offline Slide & Speech Extraction Tool for Educational Videos
Current Status: Under Active Development
Status Date: 22 September 2026
Implementation Work to Date: Neeta Chahar

1. Project Overview
Lecture Companion is designed as a privacy-preserving, locally executed tool for studying recorded lectures.

The intended final system accepts either a YouTube lecture URL or a locally stored lecture video and processes it on the user's own machine. It extracts the actual slides shown during the lecture, transcribes the instructor's speech, associates the spoken explanation with the slide displayed at that time, and provides a searchable interface that allows the user to retrieve the original slide and jump directly to the corresponding point in the video.

The project is deliberately designed to avoid cloud processing of lecture content. Video, audio, extracted slides, transcripts, and generated metadata are intended to remain on the user's device.

The current implementation has completed the project foundation and a substantial slide-detection pipeline. The transcription, slide–speech linking, persistent storage, search, playback integration, security hardening, evaluation, and final open-source release layers remain under development.


2. Current Development Status
The project is divided into three broad categories:

Completed — functionality has been implemented in the current repository.
Partially Implemented — a foundation or component exists, but it is not yet fully integrated or production-ready.
Pending — the functionality has not yet been implemented.
Features are classified according to the actual current implementation, not merely according to what is described in the project proposal.

3. Completed
3.1 Project Repository
The Git repository and basic project structure have been established.

Current structure:

lecture-companion/
│
├── backend/
│ ├── main.py
│ ├── requirements.txt
│ │
│ ├── services/
│ │ ├── downloader.py
│ │ ├── slide_detector.py
│ │ └── video_processor.py
│ │
│ └── test_slide_detector.py
│
├── frontend/
│ ├── package.json
│ ├── package-lock.json
│ ├── vite.config.js
│ ├── eslint.config.js
│ ├── index.html
│ │
│ └── src/
│ ├── App.jsx
│ ├── App.css
│ ├── index.css
│ └── main.jsx
│
└── .gitignore

Status: Completed


3.2 Backend Foundation
A Python-based FastAPI backend has been created.

The current backend exposes:

GET /
GET /health
POST /process

The root endpoint confirms that the Lecture Companion API is running.

The health endpoint provides a basic health check.

This establishes the initial backend service that will eventually orchestrate the complete processing pipeline.

Status: Completed


3.3 Frontend Foundation
The frontend has been established using:

React
Vite
Tailwind CSS

The current interface contains:

application title
project tagline
local-processing indicator
YouTube URL input
local video upload
selected-file display
Process Lecture button
"How it works" section
conceptual product explanation
The current conceptual sections are:

01 — Exact slides
02 — Search naturally
03 — Process locally

Status: Completed


3.4 Visual Design Foundation
The initial visual identity has been implemented using the selected design direction.

The current theme includes:

Warm Ivory
Charcoal
Sage
Dusty Rose
Dove / light neutral

The corresponding frontend theme includes:

warm-ivory
charcoal
sage
dusty-rose
dove

This establishes the visual language of the application.

The final UI will require additional refinement once the complete processing and search workflow is available.

Status: Completed — Design Foundation


3.5 Local Video Upload
The backend accepts locally uploaded video files through the processing endpoint.

A unique job ID is generated for each processing request.

Job-specific directories are created for local processing:

backend/data/input/<job_id>/
backend/data/frames/<job_id>/

The uploaded video is stored locally for subsequent processing.

Status: Completed


3.6 YouTube Video Ingestion
yt-dlp has been integrated for YouTube-based video ingestion.

The current flow is:

YouTube URL
↓
yt-dlp
↓
Local video file

The downloader currently:

creates the required output directory
downloads a single video
disables playlist downloading
requests video/audio
merges to MP4 where possible
returns the downloaded file path
The basic ingestion mechanism is therefore operational.

Further security hardening and robust URL validation remain necessary before considering this component production-ready.

Status: Completed — Basic Implementation


3.7 FFmpeg Frame Extraction
FFmpeg has been integrated into the processing pipeline.

The current processing flow includes:

Video
↓
FFmpeg
↓
Frame extraction
↓
frame_000001.jpg
frame_000002.jpg
frame_000003.jpg
...

The backend extracts frames at a specified sampling rate and reports the number of frames extracted.

The current processing response includes:

job_id
video
frames_extracted

Status: Completed


4. Slide Detection — Completed Foundation
The slide-detection component is currently the most substantial processing component implemented in the project.

The implementation is located in:

backend/services/slide_detector.py

It contains actual processing logic rather than being a placeholder.


4.1 Frame Loading and Preprocessing
Frames are loaded, converted to grayscale, and resized before similarity analysis.

Status: Completed


4.2 Patch-Based SSIM
Instead of treating the entire frame as a single image region, the implementation divides frames into:

6 × 8 patches

SSIM is calculated across these patches and the median similarity is used.

This approach is intended to reduce the effect of temporary movement, such as an instructor moving across part of the slide.

Status: Completed


4.3 Frame Sampling
The detector can select a limited number of reference frames from a group.

The current default supports:

Maximum 10 reference frames

Status: Completed


### 4.4 Slide Grouping and Transition Detection

The detector groups consecutive frames into logical slide segments.

Similarity between frames is used to determine whether the current frame still belongs to the same slide or represents a transition to a new slide.

The implementation considers both:

* similarity with the immediately preceding frame
* similarity with a previous reference/lookback frame

This helps distinguish an actual slide transition from temporary visual changes such as:

* instructor movement
* cursor movement
* minor frame noise
* compression artefacts

The resulting groups represent logical slide intervals rather than individual video frames.

**Status: Completed**

---

### 4.5 Visibility Analysis

The detector analyses the visibility of slide regions across multiple frames within a logical slide group.

This allows the system to estimate which portions of the slide remain visible while the instructor or other foreground elements move across the screen.

The visibility information is subsequently used when selecting representative slide views.

The objective is to avoid selecting a frame in which an important portion of the slide is temporarily obscured.

**Status: Completed**

---

### 4.6 Sharpness Analysis

Image sharpness is calculated using the variance of the Laplacian.

This provides a measure of how clearly the slide is visible in a particular frame.

The sharpness score is used as one of the factors when selecting a representative frame, helping the detector avoid frames that are temporarily blurred because of motion or transition effects.

**Status: Completed**

---

### 4.7 Best Representative View Selection

For each logical slide group, the detector evaluates candidate frames and selects a representative view based on the available visual information.

The selection considers factors including:

* slide visibility
* image sharpness
* frame position
* visual stability

The objective is to retain a frame that provides the clearest available representation of the slide.

**Status: Completed**

---

### 4.8 Complementary View Selection

The detector can select an additional view when a second frame contains slide information that is not sufficiently represented in the primary view.

For example, when an instructor is standing in front of one side of a slide, one frame may clearly expose the left side while another frame may expose the right side.

The system therefore attempts to select complementary views rather than simply selecting the two frames with the highest individual scores.

This is intended to preserve more of the original visual slide content.

**Status: Completed**

---

### 4.9 Timestamp Generation

The detector converts frame positions into timestamps using the video's frame rate.

Each detected logical slide can therefore be associated with the point in the lecture at which it appears.

The timestamp information will later be used to construct slide intervals and connect the slide to the corresponding transcript segments.

**Status: Completed — Slide-Level Timestamp Foundation**

---

### 4.10 Slide Image Output

The detector saves selected slide views as image files.

The generated output follows the slide-level structure rather than storing every sampled frame.

Conceptually:

```text
slide_001.jpg
slide_002.jpg
slide_003.jpg
...
```

Additional views can also be stored when the complementary-view logic determines that they contain useful additional information.

The detector returns information associated with each detected slide, including:

* slide number
* image path
* representative frame
* timestamp
* available views
* visibility information

**Status: Completed**

---

### 4.11 Standalone Slide Detector Test

A standalone test script has been created:

```text
backend/test_slide_detector.py
```

The script invokes the slide detector and reports information such as:

* number of logical slides detected
* slide number
* generated image path
* timestamp
* number of selected views
* visibility information

This provides an initial way to manually validate the slide-detection pipeline independently from the rest of the application.

**Status: Completed — Basic Manual Test**

---

# 5. Partially Implemented Components

The following components have a foundation in the current implementation but are not yet complete or fully integrated.

---

## 5.1 Slide Extraction Pipeline Integration

The frame extraction pipeline and slide detector have both been implemented.

However, the current `/process` endpoint does not yet execute the complete sequence:

```text
Video
↓
Frame Extraction
↓
Slide Detection
↓
Slide Output
```

The slide detector currently exists as a substantial processing component that still needs to be connected to the main API workflow.

**Status: Partially Implemented**

---

## 5.2 Frontend–Backend Integration

The React frontend contains the required initial controls for:

* YouTube URL input
* local video upload
* processing initiation

However, the frontend is not yet fully connected to the FastAPI processing endpoint.

The final interaction is intended to become:

```text
React Frontend
      ↓
POST /process
      ↓
FastAPI
      ↓
Processing Pipeline
      ↓
Results
      ↓
React Interface
```

The current frontend therefore represents the application interface foundation rather than the completed application workflow.

**Status: Partially Implemented**

---

## 5.3 YouTube Ingestion

The basic `yt-dlp` ingestion mechanism is operational.

However, before it can be considered production-ready, the implementation requires additional controls including:

* URL validation
* controlled download behaviour
* resource limits
* error handling
* security hardening
* protection against malicious or unexpected inputs

**Status: Partially Implemented — Basic Functionality Complete**

---

## 5.4 Security

Basic application configuration and local-processing design are already present.

However, complete security implementation has not yet been performed.

The final system will require security controls across:

* uploaded files
* YouTube URLs
* filesystem paths
* FFmpeg execution
* `yt-dlp` execution
* API endpoints
* database queries
* frontend inputs
* local resources
* dependencies

Security testing will also be required before the project is considered complete.

**Status: Partially Implemented — Major Work Pending**

---

## 5.5 Testing

A standalone slide-detector test is currently available.

However, a complete automated testing framework does not yet exist.

The final project requires testing across:

```text
Unit Tests
↓
Integration Tests
↓
End-to-End Tests
↓
Security Tests
↓
Performance Tests
```

**Status: Partially Implemented**

---

# 6. Pending Components

The following components have not yet been implemented in the current repository.

---

## 6.1 Perceptual Hashing and Duplicate Detection

The project requirements include pHash-based duplicate detection.

Although the image-hashing dependency is present, the active slide-detection implementation does not yet perform the final pHash-based comparison.

The intended functionality is:

```text
Slide 3
↓
Slide 4
↓
Slide 5
↓
Slide 3 appears again
↓
pHash comparison
↓
Recognise existing Slide 3
```

This will prevent a previously displayed slide from incorrectly becoming a completely new slide record.

**Status: Pending**

**Why pending:** The current implementation has focused on frame-level and logical-slide detection first. pHash-based slide-level deduplication is the next layer to be integrated.

---

## 6.2 Backend Integration of Slide Detection

The main `/process` endpoint currently performs video ingestion and frame extraction.

The final processing endpoint must additionally invoke the slide detector and return or persist the detected slide information.

The intended flow is:

```text
Input Video
↓
Ingestion
↓
FFmpeg
↓
Frame Extraction
↓
Slide Detection
↓
Unique Slide Images
↓
Slide Metadata
```

**Status: Pending**

**Why pending:** The slide detector was developed as a separate processing component first and now needs to be integrated into the main application pipeline.

---

## 6.3 Audio Extraction

The system needs to extract the audio track from the lecture video using FFmpeg.

The intended transcription pipeline is:

```text
Video
↓
FFmpeg
↓
Audio
↓
16 kHz Mono WAV
↓
Whisper
```

**Status: Pending**

**Why pending:** The transcription subsystem has not yet been integrated.

---

## 6.4 Local Whisper Transcription

The project requires locally executed Whisper transcription.

The intended output is a set of timestamped transcript segments:

```text
start_time
end_time
text
```

The processing must occur on the student's own machine.

**Status: Pending**

**Why pending:** Speech transcription is the next major processing layer after the slide-extraction pipeline.

---

## 6.5 Slide–Speech Linking

This is one of the core modules of Lecture Companion.

The intended logic is:

```text
Slide 7
24:10 → 27:45

Transcript segments
24:12 → ...
24:40 → ...
26:15 → ...
```

All relevant transcript segments occurring during the slide's active interval will be associated with that slide.

The system will also need to handle transcript segments that cross a slide boundary using the defined overlap/majority-duration logic and a small tolerance window.

**Status: Pending**

**Why pending:** This module requires both finalized slide intervals and timestamped Whisper transcript segments.

---

## 6.6 SQLite Database

The project requires a local SQLite database to persist:

* videos
* slides
* transcript segments
* slide–speech relationships
* processing metadata

The database is intended to remain entirely local.

**Status: Pending**

**Why pending:** The database schema depends on the final structure of the slide, transcript and linking outputs.

---

## 6.7 FTS5 / Search

The final system requires searchable lecture content.

The planned architecture is:

```text
SQLite
↓
FTS5
↓
Full-text search
↓
BM25 relevance ranking
```

The baseline search may use SQLite `LIKE`, with FTS5/BM25 providing the more complete search implementation.

**Status: Pending**

**Why pending:** Search requires transcript data and slide–speech relationships to exist in the database first.

---

## 6.8 Search Results Interface

The final search result should contain:

```text
Actual Slide
+
Spoken Explanation
+
Timestamp
+
Jump-to-Video action
```

For example:

```text
Search: "explain overfitting"

Result:
────────────────────────
[Actual Slide Image]

Overfitting occurs when...

24:10

[Jump to lecture]
────────────────────────
```

**Status: Pending**

**Why pending:** The result interface depends on the completion of transcription, linking, database and search.

---

## 6.9 Video Playback and Timestamp Navigation

The final frontend must contain an embedded video player.

When a user selects a search result, the player should seek directly to the stored timestamp.

The intended interaction is:

```text
Search
↓
Result
↓
Timestamp
↓
Click
↓
Video.currentTime = timestamp
↓
Lecture jumps to exact moment
```

**Status: Pending**

**Why pending:** This requires the final timestamped slide/transcript records and frontend playback integration.

---

## 6.10 Evaluation

The project will require quantitative evaluation rather than simply demonstrating that the application runs.

The planned metrics are:

| Subsystem            | Metrics                                            |
| -------------------- | -------------------------------------------------- |
| Slide Detection      | Precision, Recall, F1, duplicate rate              |
| Transcription        | Word Error Rate (WER)                              |
| Search               | Precision@k, MAP                                   |
| Slide–Speech Linking | Linking accuracy                                   |
| System Performance   | Processing time, resource usage and search latency |

**Status: Pending**

**Why pending:** These measurements require the final processing pipeline and representative test data.

---

## 6.11 Security Hardening

The final open-source project requires security controls across the complete application.

Areas requiring implementation and testing include:

| Security Area   | Required Work                                                     |
| --------------- | ----------------------------------------------------------------- |
| File Uploads    | File type validation, size limits and safe storage                |
| File Paths      | Path traversal protection and filename sanitisation               |
| YouTube URLs    | URL validation and controlled download behaviour                  |
| FFmpeg          | Safe subprocess execution and resource limits                     |
| yt-dlp          | Safe invocation and resource controls                             |
| API             | Request validation, error handling and controlled endpoints       |
| CORS            | Strict allowed origins                                            |
| Host Validation | Restrict unexpected Host headers                                  |
| Database        | Parameterised queries and safe data handling                      |
| Frontend        | Input validation and protection against unsafe rendering          |
| Resources       | Processing timeouts, file limits and resource exhaustion controls |
| Dependencies    | Version control and vulnerability scanning                        |
| Repository      | Secret scanning and security checks                               |
| Testing         | Security-focused test cases and attack-surface validation         |

**Status: Pending**

**Why pending:** Security hardening must be performed against the complete integrated application rather than only the current individual components.

---

## 6.12 Automated Testing

The current project contains a standalone slide-detector test.

The final system requires automated testing for:

```text
Video ingestion
Slide extraction
pHash deduplication
Transcription
Slide–speech linking
Database operations
Search
API endpoints
Frontend behaviour
Security
```

**Status: Pending**

**Why pending:** Most of these modules have not yet been implemented.

---

## 6.13 Open-Source Release Preparation

The repository will require the following before the final open-source release:

| File / Component      |   Status   |
| --------------------- | :--------: |
| README.md             | 🔴 Pending |
| LICENSE               | 🔴 Pending |
| SECURITY.md           | 🔴 Pending |
| CONTRIBUTING.md       | 🔴 Pending |
| CODE_OF_CONDUCT.md    | 🔴 Pending |
| Issue templates       | 🔴 Pending |
| Pull request template | 🔴 Pending |
| CI workflow           | 🔴 Pending |
| Security scanning     | 🔴 Pending |
| Release documentation | 🔴 Pending |

**Status: Pending**

---

# 7. Overall Current Status

| Project Area                       |          Status          |
| ---------------------------------- | :----------------------: |
| Repository & project structure     |       🟢 Completed       |
| FastAPI backend foundation         |       🟢 Completed       |
| React frontend foundation          |       🟢 Completed       |
| Initial visual design              |       🟢 Completed       |
| Local video ingestion              |       🟢 Completed       |
| YouTube ingestion                  |  🟡 Basic implementation |
| FFmpeg frame extraction            |       🟢 Completed       |
| SSIM-based slide analysis          |       🟢 Completed       |
| Logical slide grouping             |       🟢 Completed       |
| Visibility analysis                |       🟢 Completed       |
| Sharpness analysis                 |       🟢 Completed       |
| Best-view selection                |       🟢 Completed       |
| Complementary-view selection       |       🟢 Completed       |
| Slide timestamps                   |       🟢 Completed       |
| pHash deduplication                |        🔴 Pending        |
| Revisited-slide recognition        |        🔴 Pending        |
| API integration of slide detection |        🔴 Pending        |
| Frontend–backend integration       |        🔴 Pending        |
| Audio extraction                   |        🔴 Pending        |
| Whisper transcription              |        🔴 Pending        |
| Slide–speech linking               |        🔴 Pending        |
| SQLite database                    |        🔴 Pending        |
| FTS5/BM25 search                   |        🔴 Pending        |
| Search results                     |        🔴 Pending        |
| Video player                       |        🔴 Pending        |
| Jump-to-timestamp                  |        🔴 Pending        |
| Evaluation                         |        🔴 Pending        |
| Automated testing                  | 🟡 Partially implemented |
| Security hardening                 |    🟡 Foundation only    |
| Open-source documentation          |        🔴 Pending        |
| Final release                      |        🔴 Pending        |

---

# 8. Development Timeline

| Date                            | Contributor      | Work                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **20 September 2026**           | **Neeta Chahar** | Initial Lecture Companion implementation: backend structure, FastAPI API, local video handling, YouTube ingestion, `yt-dlp`, FFmpeg frame extraction, React/Vite frontend, initial UI and project configuration.                                                                                                                                                      |
| **22 September 2026**           | **Neeta Chahar** | Improved slide complementary-view selection and implemented the substantial slide-detection functionality including SSIM-based analysis, patch-based similarity, visibility analysis, sharpness scoring, logical slide grouping, timestamp calculation, representative-frame selection, complementary-view selection, slide output generation and standalone testing. |
| **22 September 2026 — Current** | **Neeta Chahar** | Current project state documented. Core ingestion and slide-detection foundation are implemented; transcription, linking, database, search, playback, security hardening, evaluation and final open-source preparation remain.                                                                                                                                         |

---

# 9. Next Development Sequence

The next implementation stages are planned in the following order:

```text
pHash Deduplication
        ↓
Slide Pipeline Integration
        ↓
Frontend ↔ Backend Integration
        ↓
Audio Extraction
        ↓
Whisper Transcription
        ↓
Slide–Speech Linking
        ↓
SQLite Storage
        ↓
FTS5 / BM25 Search
        ↓
Search Results UI
        ↓
Video Player
        ↓
Exact Timestamp Navigation
        ↓
Security Hardening
        ↓
Automated Testing
        ↓
Evaluation
        ↓
Documentation
        ↓
Open-Source Release
```

---

# 10. Definition of the Final Project

The project will be considered functionally complete when the following workflow works end-to-end:

| Step | Expected Result                                                                                               |
| ---: | ------------------------------------------------------------------------------------------------------------- |
|    1 | User provides a YouTube URL or local lecture video.                                                           |
|    2 | Video is processed locally.                                                                                   |
|    3 | Frames are extracted.                                                                                         |
|    4 | Unique slides are detected.                                                                                   |
|    5 | Duplicate/revisited slides are recognised.                                                                    |
|    6 | Slide timestamps are generated.                                                                               |
|    7 | Audio is extracted locally.                                                                                   |
|    8 | Speech is transcribed locally using Whisper.                                                                  |
|    9 | Transcript segments receive timestamps.                                                                       |
|   10 | Transcript segments are associated with the correct slide.                                                    |
|   11 | Slides, transcript and relationships are stored locally.                                                      |
|   12 | User searches for a topic.                                                                                    |
|   13 | Relevant slide and explanation are returned.                                                                  |
|   14 | Relevant timestamp is displayed.                                                                              |
|   15 | User selects the result.                                                                                      |
|   16 | Video jumps directly to the corresponding lecture moment.                                                     |
|   17 | The complete workflow operates locally without uploading lecture content to a third-party processing service. |
|   18 | The system passes functional, security, performance and evaluation testing.                                   |

---

# 11. Current Project Statement

> **Lecture Companion has currently completed its project foundation, including the FastAPI backend, React frontend, local video ingestion, YouTube ingestion, FFmpeg frame extraction, and a substantial SSIM-based slide-detection pipeline with visibility, sharpness, logical-slide grouping, timestamp and complementary-view analysis.**
>
> **The project is currently moving from the slide-extraction foundation toward the complete slide–speech retrieval system. The remaining core implementation consists of pHash-based duplicate recognition, integrated slide processing, local Whisper transcription, slide–speech linking, SQLite/FTS5 storage and search, timestamp-based playback, security hardening, automated testing, quantitative evaluation and final open-source preparation.**
>
> **All implementation work completed in the repository to date has been carried out by Neeta Chahar, with recorded implementation milestones on 20 September 2026 and 22 September 2026.**
