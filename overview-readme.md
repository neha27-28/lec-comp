# Lecture Companion

## Current Project Status

**Project:** Lecture Companion — An Offline Slide & Speech Extraction Tool for Educational Videos

**Status Date:** 23 September 2026

**Implementation Work Completed To Date:** Neeta Chahar

**Current Stage:** Core foundation, video ingestion, frame extraction, substantial OCR-free slide detection, slide deduplication, and PDF slide export are implemented. Backend/frontend integration is currently being completed. Speech processing, slide–speech linking, search, playback, security hardening, evaluation and release preparation remain pending.

---

# 1. Project Status Overview

| Status                       | Meaning                                                                                                            |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 🟢 **Completed**             | Functionality has been implemented and is working as an independent or integrated component.                       |
| 🟡 **Partially Implemented** | A functional foundation exists, but integration, validation, hardening or final workflow is still being completed. |
| 🔴 **Pending**               | The functionality has not yet been implemented.                                                                    |
| ⚪ **Future Enhancement**     | Not required for the current MVP and planned for a later version.                                                  |

---

# 2. Completed Work

|  # | Component                              | What Has Been Completed                                                                                                                          | Status |
| -: | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | :----: |
|  1 | Git Repository                         | Project repository, source structure, Git history and `.gitignore` established.                                                                  |   🟢   |
|  2 | Backend Structure                      | Python backend with FastAPI and service modules created.                                                                                         |   🟢   |
|  3 | FastAPI API                            | Root, health-check and processing endpoints established.                                                                                         |   🟢   |
|  4 | Local Video Upload                     | Backend accepts uploaded video files and creates job-specific local directories.                                                                 |   🟢   |
|  5 | Job Management Foundation              | Unique processing job IDs are generated for video-processing requests.                                                                           |   🟢   |
|  6 | YouTube Ingestion                      | `yt-dlp` integrated for downloading individual YouTube videos locally.                                                                           |   🟢   |
|  7 | FFmpeg Integration                     | FFmpeg integrated into the backend processing pipeline.                                                                                          |   🟢   |
|  8 | Frame Extraction                       | Video frames can be extracted locally using FFmpeg at a configurable sampling rate. Current pipeline uses 3 FPS for slide detection experiments. |   🟢   |
|  9 | Slide Detector                         | Substantial OCR-free slide-detection implementation created in `slide_detector.py`.                                                              |   🟢   |
| 10 | Image Preprocessing                    | Frames are resized and converted into suitable representations for visual comparison.                                                            |   🟢   |
| 11 | Multi-Signal Visual Analysis           | Pixel, edge, histogram and structural differences are combined to detect visual transitions.                                                     |   🟢   |
| 12 | Patch-Based / Structural Similarity    | Structural similarity analysis is used to distinguish slide changes from minor frame variation.                                                  |   🟢   |
| 13 | Adaptive Thresholding                  | Transition thresholds are calculated dynamically from the visual-change distribution.                                                            |   🟢   |
| 14 | Transition Recovery                    | A secondary recovery threshold is used to recover subtle transitions that may not cross the stronger threshold.                                  |   🟢   |
| 15 | Temporal Confirmation                  | Candidate transitions are confirmed using persistence and temporal evidence rather than a single-frame difference.                               |   🟢   |
| 16 | Logical Slide Grouping                 | Consecutive frames are grouped into logical slide appearances.                                                                                   |   🟢   |
| 17 | Visibility Analysis                    | Detector evaluates how consistently slide content remains visible across frames.                                                                 |   🟢   |
| 18 | Sharpness Analysis                     | Laplacian-based sharpness scoring is used to avoid poor representative frames.                                                                   |   🟢   |
| 19 | Best-View Selection                    | A strong representative frame is selected for each logical slide appearance.                                                                     |   🟢   |
| 20 | Complementary View Selection           | Additional slide information can be retained where a second view provides genuinely new visible content.                                         |   🟢   |
| 21 | pHash Calculation                      | Perceptual hashing is implemented for slide-level visual comparison.                                                                             |   🟢   |
| 22 | pHash-Based Deduplication              | pHash is actively used as part of duplicate-slide detection.                                                                                     |   🟢   |
| 23 | SSIM + Edge Duplicate Verification     | Potential duplicates are further checked using structural similarity and edge similarity rather than relying on pHash alone.                     |   🟢   |
| 24 | Revisited-Slide Recognition Foundation | Previously seen visually equivalent slides can be associated through the slide-level duplicate detection mechanism.                              |   🟢   |
| 25 | Unique Slide Generation                | Detector maintains unique slide records while preserving slide appearances/occurrences.                                                          |   🟢   |
| 26 | Slide Image Generation                 | Representative slide images are saved to the job-specific slide directory.                                                                       |   🟢   |
| 27 | PDF Slide Generation                   | Unique extracted slides can be assembled into a PDF containing the slide images.                                                                 |   🟢   |
| 28 | PDF Download Endpoint                  | Backend provides a job-specific endpoint for downloading the generated lecture-slides PDF.                                                       |   🟢   |
| 29 | React Frontend                         | React/Vite frontend application created.                                                                                                         |   🟢   |
| 30 | Tailwind / Styling Foundation          | Frontend styling and project visual theme established.                                                                                           |   🟢   |
| 31 | Local Upload Interface                 | UI for selecting a local lecture video has been created.                                                                                         |   🟢   |
| 32 | YouTube Interface                      | UI for entering a YouTube lecture URL has been created.                                                                                          |   🟢   |
| 33 | Initial Product UI                     | Product title, tagline, local-processing messaging and introductory interface implemented.                                                       |   🟢   |
| 34 | Visual Identity                        | Warm Ivory, Charcoal, Sage, Dusty Rose and neutral visual language established.                                                                  |   🟢   |
| 35 | Frontend PDF Download UI               | Frontend has been prepared to expose the generated slides PDF after processing.                                                                  |   🟢   |
| 36 | Standalone Detector Testing            | Detector can be executed independently against an extracted frame directory for evaluation/debugging.                                            |   🟢   |

---

# 3. Partially Implemented

|  # | Component                      | What Exists Currently                                                                                   | What Is Still Required                                                                                            | Status |
| -: | ------------------------------ | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | :----: |
|  1 | Slide Extraction Pipeline      | FFmpeg frame extraction and the substantial slide detector are implemented.                             | Complete the API-level integration and verify the final end-to-end processing path.                               |   🟡   |
|  2 | API–Slide Detector Integration | `/process` contains the slide-processing integration and has reached the detector stage during testing. | Resolve the current detector-call interface mismatch and complete successful integrated execution.                |   🟡   |
|  3 | PDF Pipeline                   | PDF generation and download endpoint are implemented.                                                   | Verify PDF generation consistently after successful integrated slide detection.                                   |   🟡   |
|  4 | Frontend–Backend Integration   | React processing controls and FastAPI processing endpoint exist.                                        | Complete and verify the full request → processing → result → PDF workflow.                                        |   🟡   |
|  5 | Local Processing               | Video ingestion, download, frame extraction and slide extraction are local.                             | Extend the local pipeline through transcription, linking, database, search and playback.                          |   🟡   |
|  6 | YouTube Processing             | `yt-dlp` download mechanism exists.                                                                     | Add strict URL validation, resource limits and security hardening.                                                |   🟡   |
|  7 | Security                       | Basic CORS and local-processing foundations exist.                                                      | Implement full validation, subprocess protection, resource controls, host validation and security testing.        |   🟡   |
|  8 | Testing                        | Standalone detector testing exists and detector can be tested independently.                            | Build automated unit, integration, end-to-end and security tests.                                                 |   🟡   |
|  9 | Open-Source Structure          | Git repository and `.gitignore` exist.                                                                  | Add final license, README, contribution guidelines, security policy, code of conduct and release structure.       |   🟡   |
| 10 | UI/UX                          | Initial interface, upload controls and processing interface exist.                                      | Add robust processing states, errors, slide results, transcript results, search and playback workflow.            |   🟡   |
| 11 | Timestamp Handling             | Slide occurrences and timestamps are generated by the detector.                                         | Persist timestamps and connect them to transcript/search/playback records.                                        |   🟡   |
| 12 | Slide Accuracy Evaluation      | Detector has undergone iterative OCR-free visual improvements and manual inspection.                    | Build a manually annotated ground-truth dataset and calculate formal Precision, Recall, F1 and duplicate metrics. |   🟡   |

---

# 4. Pending Work

|  # | Component                        | What Needs To Be Built                                                                                                               | Status |
| -: | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | :----: |
|  1 | Audio Extraction                 | Extract lecture audio locally using FFmpeg.                                                                                          |   🔴   |
|  2 | Audio Conversion                 | Convert audio into the format required by the selected Whisper pipeline, including 16 kHz mono processing where required.            |   🔴   |
|  3 | Whisper Integration              | Run a local Whisper model and generate timestamped speech segments.                                                                  |   🔴   |
|  4 | Timestamped Transcript           | Store transcript segments with start/end timestamps.                                                                                 |   🔴   |
|  5 | Slide–Speech Linking             | Associate transcript segments with the slide displayed during the corresponding time interval.                                       |   🔴   |
|  6 | Boundary Handling                | Handle transcript segments crossing slide boundaries using the defined overlap/majority-duration and tolerance logic.                |   🔴   |
|  7 | SQLite Database                  | Create persistent local storage for videos, slides, transcript segments, links and processing jobs.                                  |   🔴   |
|  8 | Database Schema                  | Implement tables such as `videos`, `slides`, `segments`, `slide_segments` and `processing_jobs`.                                     |   🔴   |
|  9 | FTS5                             | Add SQLite FTS5 full-text search.                                                                                                    |   🔴   |
| 10 | BM25 Search Ranking              | Use FTS5/BM25 ranking for relevant lecture-content retrieval.                                                                        |   🔴   |
| 11 | Search Engine                    | Implement keyword and natural-language retrieval over linked lecture content.                                                        |   🔴   |
| 12 | Search Results                   | Return matching slide, associated explanation/transcript and timestamp.                                                              |   🔴   |
| 13 | Slide Result Interface           | Display the actual extracted slide associated with a search result.                                                                  |   🔴   |
| 14 | Transcript/Explanation Interface | Display the speech associated with the selected slide.                                                                               |   🔴   |
| 15 | Video Player                     | Add local lecture-video playback.                                                                                                    |   🔴   |
| 16 | Jump-to-Timestamp                | Seek the video directly to the relevant timestamp when a result is selected.                                                         |   🔴   |
| 17 | Active Slide Tracking            | Highlight the currently active slide/transcript while the video is playing.                                                          |   🔴   |
| 18 | Lecture History/Library          | Provide a local view of previously processed lectures.                                                                               |   🔴   |
| 19 | Slide Detection Evaluation       | Calculate Precision, Recall, F1, duplicate rate and related metrics against manually annotated ground truth.                         |   🔴   |
| 20 | Transcription Evaluation         | Calculate Word Error Rate (WER).                                                                                                     |   🔴   |
| 21 | Search Evaluation                | Calculate Precision@k and MAP using manually judged search results.                                                                  |   🔴   |
| 22 | Linking Evaluation               | Measure slide–speech linking accuracy against labelled examples.                                                                     |   🔴   |
| 23 | Performance Benchmarking         | Measure processing time, CPU, RAM, storage, transcription time and search latency.                                                   |   🔴   |
| 24 | Automated Testing                | Build comprehensive unit, integration and end-to-end tests.                                                                          |   🔴   |
| 25 | Security Testing                 | Test malformed files, malicious URLs, path traversal, command injection, XSS, resource exhaustion and localhost API exposure.        |   🔴   |
| 26 | Threat Model                     | Document assets, attackers, attack surfaces, trust boundaries and mitigations.                                                       |   🔴   |
| 27 | Security Hardening               | Implement validation, resource limits, safe subprocess execution, path protection, strict CORS/host validation and related controls. |   🔴   |
| 28 | Dependency Security              | Add dependency scanning and automated vulnerability monitoring.                                                                      |   🔴   |
| 29 | SAST / CodeQL                    | Add static security analysis to CI.                                                                                                  |   🔴   |
| 30 | Secret Scanning                  | Add secret detection and repository security controls.                                                                               |   🔴   |
| 31 | Resource Controls                | Add upload limits, duration limits, processing timeouts and job/resource controls.                                                   |   🔴   |
| 32 | Subprocess Hardening             | Secure FFmpeg and `yt-dlp` execution and prevent unsafe command construction.                                                        |   🔴   |
| 33 | Final README                     | Create complete installation, architecture, usage, development and project-status documentation.                                     |   🔴   |
| 34 | `SECURITY.md`                    | Document the security model, reporting procedure and security practices.                                                             |   🔴   |
| 35 | `CONTRIBUTING.md`                | Document contribution workflow and development standards.                                                                            |   🔴   |
| 36 | `CODE_OF_CONDUCT.md`             | Add open-source community guidelines.                                                                                                |   🔴   |
| 37 | MIT License                      | Add the selected open-source license.                                                                                                |   🔴   |
| 38 | CI/CD                            | Create automated build, test and security-check workflows.                                                                           |   🔴   |
| 39 | GitHub Pages                     | Deploy finalized project documentation/website.                                                                                      |   🔴   |
| 40 | Release Packaging                | Prepare reproducible releases/installable versions.                                                                                  |   🔴   |
| 41 | Final Documentation              | Complete architecture, methodology, security, testing and user documentation.                                                        |   🔴   |
| 42 | Final Demo                       | Prepare complete ingestion → extraction → search → playback demonstration.                                                           |   🔴   |
| 43 | Final Report Integration         | Integrate implementation results, evaluation metrics, screenshots and findings into the academic report.                             |   🔴   |

---

# 5. Current End-to-End Architecture Status

| Pipeline Stage                     | Status | Current Situation                                                             |
| ---------------------------------- | :----: | ----------------------------------------------------------------------------- |
| YouTube URL input                  |   🟢   | Implemented                                                                   |
| Local video upload                 |   🟢   | Implemented                                                                   |
| Video ingestion                    |   🟢   | Basic implementation complete                                                 |
| `yt-dlp` download                  |   🟢   | Implemented                                                                   |
| FFmpeg processing                  |   🟢   | Implemented                                                                   |
| Frame extraction                   |   🟢   | Implemented; currently tested at 3 FPS                                        |
| Frame preprocessing                |   🟢   | Implemented                                                                   |
| Multi-signal visual analysis       |   🟢   | Implemented                                                                   |
| SSIM / structural analysis         |   🟢   | Implemented                                                                   |
| Visibility analysis                |   🟢   | Implemented                                                                   |
| Sharpness analysis                 |   🟢   | Implemented                                                                   |
| Adaptive transition threshold      |   🟢   | Implemented                                                                   |
| Recovery transition detection      |   🟢   | Implemented                                                                   |
| Logical slide grouping             |   🟢   | Implemented                                                                   |
| Best-view selection                |   🟢   | Implemented                                                                   |
| Complementary-view selection       |   🟢   | Implemented                                                                   |
| pHash calculation                  |   🟢   | Implemented                                                                   |
| pHash duplicate detection          |   🟢   | Implemented                                                                   |
| SSIM + edge duplicate verification |   🟢   | Implemented                                                                   |
| Revisited-slide recognition        |   🟢   | Detector-level recognition implemented                                        |
| Unique slide output                |   🟢   | Implemented                                                                   |
| Slide image generation             |   🟢   | Implemented                                                                   |
| Slide PDF generation               |   🟢   | Implemented                                                                   |
| PDF download endpoint              |   🟢   | Implemented                                                                   |
| API → detector integration         |   🟡   | Integration exists but final execution still requires correction/verification |
| Persistent slide storage           |   🟡   | Job-level filesystem storage exists; database persistence pending             |
| Audio extraction                   |   🔴   | Not implemented                                                               |
| Whisper transcription              |   🔴   | Not implemented                                                               |
| Timestamped transcript             |   🔴   | Not implemented                                                               |
| Slide–speech linking               |   🔴   | Not implemented                                                               |
| SQLite                             |   🔴   | Not implemented                                                               |
| FTS5                               |   🔴   | Not implemented                                                               |
| BM25                               |   🔴   | Not implemented                                                               |
| Search                             |   🔴   | Not implemented                                                               |
| Search results                     |   🔴   | Not implemented                                                               |
| Slide + explanation display        |   🔴   | Not implemented                                                               |
| Video player                       |   🔴   | Not implemented                                                               |
| Jump to timestamp                  |   🔴   | Not implemented                                                               |
| Active slide tracking              |   🔴   | Not implemented                                                               |
| Evaluation framework               |   🔴   | Not implemented                                                               |
| Security hardening                 |   🟡   | Requirements identified; implementation pending                               |
| Automated testing                  |   🟡   | Standalone detector testing exists; complete test suite pending               |
| Final documentation                |   🔴   | Pending                                                                       |
| Open-source release preparation    |   🟡   | Repository foundation exists; release files/process pending                   |

---

# 6. What the Current Application Can Actually Do

| Capability                                                   | Current Reality                     |
| ------------------------------------------------------------ | ----------------------------------- |
| Open the React application                                   | ✅ Yes                               |
| Start the FastAPI backend                                    | ✅ Yes                               |
| Upload a local video                                         | ✅ Yes                               |
| Provide a YouTube URL                                        | ✅ Yes                               |
| Download a YouTube video using `yt-dlp`                      | ✅ Yes                               |
| Extract video frames using FFmpeg                            | ✅ Yes                               |
| Extract frames at 3 FPS for slide analysis                   | ✅ Yes                               |
| Run the slide detector independently                         | ✅ Yes                               |
| Detect visual slide transitions                              | ✅ Yes                               |
| Group frames into logical slides                             | ✅ Yes                               |
| Calculate slide timestamps                                   | ✅ Yes                               |
| Select representative slide views                            | ✅ Yes                               |
| Select complementary views                                   | ✅ Yes                               |
| Compare slides using pHash                                   | ✅ Yes                               |
| Verify duplicates using pHash + SSIM + edge similarity       | ✅ Yes                               |
| Recognize previously seen/revisited slides at detector level | ✅ Yes                               |
| Save unique slide images                                     | ✅ Yes                               |
| Generate a unique-slides PDF                                 | ✅ Yes                               |
| Download the generated slides PDF                            | 🟡 Integration verification pending |
| Automatically transcribe lecture speech                      | ❌ No                                |
| Link speech to slides                                        | ❌ No                                |
| Store final lecture data in SQLite                           | ❌ No                                |
| Search lecture content                                       | ❌ No                                |
| Display transcript/explanation results                       | ❌ No                                |
| Jump to an exact lecture timestamp                           | ❌ No                                |
| Process an entire lecture end-to-end                         | 🟡 Core pipeline under integration  |
| Provide the final Lecture Companion workflow                 | ❌ Not yet                           |

---

# 7. Current Project Position

| Area                        | Current Position                           |
| --------------------------- | ------------------------------------------ |
| Repository                  | 🟢 Established                             |
| Backend                     | 🟢 Foundation established                  |
| Frontend                    | 🟢 Foundation established                  |
| Video ingestion             | 🟢 Implemented                             |
| Frame processing            | 🟢 Implemented                             |
| Slide detection             | 🟢 Substantial implementation completed    |
| Slide deduplication         | 🟢 Implemented                             |
| Revisited-slide recognition | 🟢 Detector-level implementation completed |
| Slide PDF generation        | 🟢 Implemented                             |
| Backend integration         | 🟡 Under completion/testing                |
| Transcription               | 🔴 Pending                                 |
| Slide–speech linking        | 🔴 Pending                                 |
| Database                    | 🔴 Pending                                 |
| Search                      | 🔴 Pending                                 |
| Playback integration        | 🔴 Pending                                 |
| Security                    | 🟡 Foundation/requirements only            |
| Testing                     | 🟡 Manual/standalone detector testing      |
| Evaluation                  | 🔴 Pending                                 |
| Documentation               | 🔴 Pending                                 |
| Open-source release         | 🟡 Repository foundation exists            |
| Final product               | 🔴 Under development                       |

---

# 8. Why the Project Is Not Yet Complete

| Remaining Area       | Reason                                                                                                                                                |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend integration  | The slide detector is implemented, but the current `/process` workflow still needs final interface correction and successful end-to-end verification. |
| PDF integration      | PDF generation and download functionality exist, but final integrated verification depends on successful processing completion.                       |
| Whisper              | Speech transcription is the next major processing layer and has not yet been implemented.                                                             |
| Slide–speech linking | Linking requires finalized slide intervals and timestamped transcript segments.                                                                       |
| SQLite               | Persistent structured storage has not yet been introduced.                                                                                            |
| FTS5/BM25            | Search depends on transcript storage and slide–speech relationships.                                                                                  |
| Video playback       | Exact timestamp playback depends on persistent timestamp records and frontend video integration.                                                      |
| Evaluation           | Formal metrics require representative manually annotated lecture data.                                                                                |
| Security hardening   | Security controls need to be applied to the complete integrated application.                                                                          |
| Automated testing    | Full tests need to cover the integrated system rather than only individual components.                                                                |
| Documentation        | Final documentation should reflect actual implementation, measured performance and security controls.                                                 |
| Release              | Packaging should occur after functionality, testing and security checks are complete.                                                                 |

---

# 9. Development Timeline

| Date                            | Contributor      | Work Completed                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **20 September 2026**           | **Neeta Chahar** | Initial Lecture Companion implementation: backend structure, FastAPI API, local upload handling, YouTube ingestion, `yt-dlp` downloader, FFmpeg frame extraction, React/Vite frontend, initial UI, project styling and configuration.                                                                                                                                                          |
| **22 September 2026**           | **Neeta Chahar** | Improved slide complementary-view selection and implemented the substantial OCR-free slide-detection functionality including multi-signal visual comparison, structural similarity, visibility analysis, sharpness scoring, logical slide grouping, timestamp calculation, best-frame selection, complementary second-view selection, slide output generation and standalone detector testing. |
| **23 September 2026**           | **Neeta Chahar** | Added final OCR-free slide-detection improvements: stricter duplicate verification using pHash + SSIM + edge similarity, recovery-threshold transition detection and improved candidate-transition recovery. FFmpeg slide-analysis sampling was increased to 3 FPS for experimentation.                                                                                                        |
| **23 September 2026**           | **Neeta Chahar** | Implemented slide PDF generation from unique extracted slides and added backend PDF download support. Frontend PDF-download integration was prepared.                                                                                                                                                                                                                                          |
| **23 September 2026 — Current** | **Neeta Chahar** | Current repository state: ingestion, frame extraction, substantial slide detection, duplicate/revisited-slide recognition, slide image generation and PDF generation are implemented. Backend integration is being finalized. Whisper, slide–speech linking, SQLite, FTS5/BM25, search, playback, security hardening, evaluation and release preparation remain.                               |

---

# 10. Next Development Stage

| Priority | Next Component           | Objective                                                                                     |
| -------: | ------------------------ | --------------------------------------------------------------------------------------------- |
|        1 | Pipeline Integration     | Correct and complete frame extraction → slide detection → slide output → PDF through FastAPI. |
|        2 | Integration Verification | Run the complete local processing workflow successfully on representative lectures.           |
|        3 | Audio Pipeline           | Extract and prepare audio for local transcription.                                            |
|        4 | Whisper                  | Generate timestamped local transcripts.                                                       |
|        5 | Slide–Speech Linking     | Associate transcript segments with slide intervals.                                           |
|        6 | SQLite                   | Persist videos, slides, transcripts, timestamps and links.                                    |
|        7 | FTS5/BM25                | Implement searchable lecture content.                                                         |
|        8 | Search API               | Retrieve relevant slide/transcript/timestamp records.                                         |
|        9 | Results UI               | Display actual slide + explanation + timestamp.                                               |
|       10 | Video Playback           | Implement exact timestamp seeking.                                                            |
|       11 | Active Slide Tracking    | Synchronize the current slide with video playback.                                            |
|       12 | Security                 | Harden the complete integrated application.                                                   |
|       13 | Testing & Evaluation     | Validate extraction, transcription, linking and search using measurable metrics.              |
|       14 | Documentation            | Document final architecture, setup, methodology, security and contribution workflow.          |
|       15 | Release                  | Prepare final open-source release and demonstration.                                          |

---

# 11. Important Scope Decision

| Feature                           | Decision                                              |
| --------------------------------- | ----------------------------------------------------- |
| Primary application               | Local Web Application                                 |
| Processing location               | User's own machine                                    |
| Cloud video processing            | Not part of the intended architecture                 |
| Browser extension                 | Future enhancement, not part of the current MVP       |
| Public project website            | GitHub Pages                                          |
| Optional frontend demonstration   | Vercel                                                |
| Actual lecture-processing backend | Local only                                            |
| Open-source model                 | Yes                                                   |
| Planned license                   | MIT                                                   |
| Primary differentiator            | Local, private, free slide–speech retrieval           |
| Final core output                 | Original slide + spoken explanation + exact timestamp |

---

# 12. Current Definition of Done

The project will be considered functionally complete when the following workflow works end-to-end:

| Step | Required Result                                                                                   |
| ---: | ------------------------------------------------------------------------------------------------- |
|    1 | User provides a YouTube URL or local lecture video.                                               |
|    2 | Video is stored and processed locally.                                                            |
|    3 | Frames are extracted.                                                                             |
|    4 | Unique slides are detected.                                                                       |
|    5 | Duplicate/revisited slides are recognized.                                                        |
|    6 | Slide timestamps are generated.                                                                   |
|    7 | Audio is extracted locally.                                                                       |
|    8 | Speech is transcribed locally using Whisper.                                                      |
|    9 | Transcript segments receive timestamps.                                                           |
|   10 | Transcript segments are linked to the appropriate slide.                                          |
|   11 | Lecture information is stored locally in SQLite.                                                  |
|   12 | FTS5/BM25 provides searchable lecture content.                                                    |
|   13 | User searches for a topic.                                                                        |
|   14 | System returns the actual extracted slide.                                                        |
|   15 | System displays the associated spoken explanation.                                                |
|   16 | System displays the relevant timestamp.                                                           |
|   17 | User selects the result.                                                                          |
|   18 | Video jumps directly to that moment.                                                              |
|   19 | Complete workflow operates without uploading lecture content to a third-party processing service. |
|   20 | System passes functional, performance, security and evaluation testing.                           |

---

# 13. Current Project Statement

> **The current implementation has established the Lecture Companion foundation, including local video ingestion, YouTube downloading, FFmpeg frame extraction, React/FastAPI application structure, and a substantial OCR-free slide-detection pipeline.**

> **The slide detector now includes multi-signal visual transition analysis, adaptive and recovery thresholds, temporal transition confirmation, logical slide grouping, visibility analysis, sharpness-based representative-frame selection, complementary-view selection, pHash-based duplicate detection, SSIM and edge-based duplicate verification, revisited-slide recognition, unique slide output and slide PDF generation.**

> **The current integration stage is focused on completing and verifying the FastAPI processing workflow and PDF delivery. The remaining major development areas are local Whisper transcription, slide–speech linking, SQLite persistence, FTS5/BM25 search, search-result presentation, timestamp-based video playback, security hardening, automated testing, quantitative evaluation and final open-source release preparation.**

> **Implementation work completed in the repository to date is attributed to Neeta Chahar, with implementation milestones recorded from 20 September 2026 through 23 September 2026.**

---

# 14. Current Status

**Lecture Companion is currently at the foundation + advanced slide-detection + initial output-integration stage.**

The current processing direction is:

```text
YouTube URL / Local Video
          ↓
     Local Ingestion
          ↓
        FFmpeg
          ↓
   Frame Extraction
       (3 FPS)
          ↓
 Multi-Signal Slide Detection
          ↓
 Logical Slide Grouping
          ↓
 Representative View Selection
          ↓
 pHash + SSIM + Edge Deduplication
          ↓
 Revisited-Slide Recognition
          ↓
 Unique Slide Images
          ↓
      Slides PDF
          ↓
   [CURRENT INTEGRATION STAGE]
          ↓
     Audio Extraction
          ↓
        Whisper
          ↓
 Timestamped Transcript
          ↓
 Slide–Speech Linking
          ↓
        SQLite
          ↓
     FTS5 / BM25
          ↓
        Search
          ↓
 Slide + Explanation + Timestamp
          ↓
 Exact Timestamp Playback
```

**This document reflects the actual implementation state as of 23 September 2026 and should be updated whenever a module moves from pending to partially implemented or completed.**
