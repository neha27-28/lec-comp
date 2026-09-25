# Lecture Companion — Threat Model

**Version:** 1.0  
**Date:** 25 September 2026  
**Method:** STRIDE-oriented threat modelling  
**Scope:** Current local Lecture Companion MVP

---

## 1. Purpose

Lecture Companion is a local-first educational video processing application. A user provides either a local lecture video or a YouTube lecture URL. The application processes the lecture on the user's machine, extracts frames and unique slides, extracts audio, transcribes speech locally with Whisper, links speech to slide intervals, stores structured information in SQLite, provides FTS5/BM25 search, and allows the user to jump the video to a relevant timestamp.

The intended architecture keeps lecture processing local rather than uploading lecture content to a third-party processing service.

This threat model identifies the assets, trust boundaries, attack surfaces, threats, implemented controls, and residual risks relevant to that architecture.

---

## 2. System Boundary

### In scope

- React/Vite frontend
- FastAPI local backend
- Local video upload
- YouTube URL ingestion through `yt-dlp`
- FFmpeg frame extraction
- Slide detection and deduplication
- Local audio extraction
- Local Whisper transcription
- Slide–speech linking
- SQLite and FTS5/BM25 search
- Generated slide images
- Generated PDF
- Local lecture video playback
- Job-specific storage directories
- Backend API endpoints

### Out of scope

- Security of YouTube itself
- Security of the user's operating system
- Security of the user's browser
- Security of third-party network infrastructure
- Security of the upstream lecture/video publisher
- Cloud deployment security
- Multi-user authentication/authorization
- Public internet exposure of the local API
- Protection against a fully compromised host operating system

---

## 3. Security Objectives

The main security objectives are:

1. **Confidentiality** — lecture videos, transcripts, extracted slides and generated PDFs should remain local and should not be unintentionally exposed.
2. **Integrity** — attackers should not be able to alter processing paths, generated files, database references or API behavior through untrusted input.
3. **Availability** — malicious or pathological videos/requests should not be able to consume uncontrolled local resources.
4. **Isolation** — files belonging to one processing job should remain inside that job's storage area.
5. **Input safety** — filenames, paths, URLs, search queries and processing parameters must be validated before use.
6. **Process safety** — FFmpeg and other subprocesses must not receive attacker-controlled shell syntax.
7. **Local-processing privacy** — the application should not require lecture content to be uploaded to a cloud processing service.

---

## 4. Assets

| ID | Asset | Security property |
|---|---|---|
| A1 | Original lecture video | Confidentiality, integrity |
| A2 | Extracted video frames | Confidentiality, integrity |
| A3 | Extracted slide images | Confidentiality, integrity |
| A4 | Generated slide PDF | Confidentiality, integrity |
| A5 | Extracted lecture audio | Confidentiality |
| A6 | Whisper transcript | Confidentiality, integrity |
| A7 | Slide–speech/timestamp mappings | Confidentiality, integrity |
| A8 | SQLite database | Confidentiality, integrity, availability |
| A9 | Job identifiers and job directories | Isolation, integrity |
| A10 | Search results | Confidentiality, integrity |
| A11 | Processing resources: CPU, RAM, disk | Availability |
| A12 | FFmpeg/yt-dlp subprocess execution | Integrity, availability |
| A13 | Local API | Integrity, availability |

---

## 5. Trust Boundaries

### TB-1 — User/browser → local FastAPI API

The browser supplies:

- YouTube URLs
- uploaded files
- search queries

These values are untrusted.

### TB-2 — YouTube/network → local downloader

Downloaded content originates outside the application and must be treated as untrusted input even when the URL itself passes validation.

### TB-3 — Uploaded/downloaded video → media-processing tools

The video is parsed by FFmpeg and related media tooling. Media files are complex inputs and represent a significant attack surface.

### TB-4 — Application → filesystem

The application creates input, frame, slide, PDF and audio files. A path or filename mistake can cross the intended job boundary.

### TB-5 — Application → SQLite

Processing-derived data enters the local database and search index. Database operations must not allow malformed user input to alter database behavior.

### TB-6 — Local API → browser-served generated files

Generated video, slides and PDFs are returned through API endpoints. File serving must remain constrained to the intended job directory.

---

## 6. Data Flow

```text
                    ┌──────────────────────┐
                    │   User / Browser     │
                    └──────────┬───────────┘
                               │
                    URL / Video / Search
                               │
                         [ TB-1 ]
                               │
                               ▼
                    ┌──────────────────────┐
                    │    FastAPI API       │
                    │ Input validation      │
                    │ Job isolation         │
                    └───────┬──────────────┘
                            │
             ┌──────────────┴───────────────┐
             │                              │
             ▼                              ▼
      Local upload                    YouTube URL
             │                              │
             │                         yt-dlp
             │                              │
             └──────────────┬───────────────┘
                            │
                         Video
                            │
                         [ TB-3 ]
                            │
                            ▼
                         FFmpeg
                            │
                    Extracted frames
                            │
                            ▼
                    Slide detection
                            │
                     Slide images
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
        PDF generation              Audio extraction
                                            │
                                            ▼
                                         Whisper
                                            │
                                      Transcript +
                                       timestamps
                                            │
                            ┌───────────────┘
                            ▼
                    Slide–speech linking
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
                  Slide + speech + time
                            │
                            ▼
                     Video playback
```

---

# 7. STRIDE Threat Analysis

## 7.1 Spoofing

### T-S1 — Forged job identifier

**Threat:** An attacker attempts to access another job by guessing or manipulating a job ID.

**Impact:** Unauthorized access to another lecture's video, slides or PDF.

**Current controls:**
- Job IDs are generated as 8-character hexadecimal identifiers.
- API endpoints validate the expected job-ID format.
- Requested files are resolved inside the corresponding job directory.

**Residual risk:** The identifier is not an authentication mechanism. If the application is exposed to untrusted users, stronger authorization and unguessable identifiers would be required.

**Status:** Mitigated for the intended single-user local MVP; not a substitute for multi-user authorization.

---

### T-S2 — Malicious YouTube URL masquerading as an allowed URL

**Threat:** An attacker supplies a URL that visually resembles YouTube but points to another host.

**Current controls:**
- HTTPS is required.
- Hostname is checked against an explicit YouTube allowlist.
- Embedded username/password is rejected.
- Explicit ports are rejected.
- Non-YouTube hosts and subdomains are rejected.

**Status:** Mitigated.

---

## 7.2 Tampering

### T-T1 — Path traversal through filenames

**Threat:** A crafted filename attempts to write or read outside the intended job directory.

**Impact:** File overwrite, unauthorized file access or data corruption.

**Current controls:**
- Filenames are sanitized.
- Path components are normalized.
- `..` traversal sequences are neutralized.
- Resolved paths are checked with `relative_to()` against the intended parent directory.
- Generated and served files are constrained to job directories.

**Status:** Mitigated.

---

### T-T2 — Manipulation of FFmpeg command execution

**Threat:** Attacker-controlled input is inserted into a shell command.

**Impact:** Command injection or arbitrary command execution.

**Current controls:**
- FFmpeg commands are constructed as argument lists.
- `shell=False` is used.
- User input is not interpreted as shell syntax.
- FPS is validated before being inserted into the command.
- Output paths are generated internally.

**Status:** Mitigated for the identified command-injection path.

---

### T-T3 — Unauthorized modification of generated lecture artifacts

**Threat:** A request attempts to cause the application to serve a file outside the current job.

**Current controls:**
- Job ID validation.
- Filename validation for slide images.
- File existence checks.
- Parent-directory containment checks.
- PDF files are resolved from the job-specific PDF directory.

**Status:** Mitigated.

---

## 7.3 Repudiation

### T-R1 — Lack of processing traceability

**Threat:** A processing failure or unexpected result cannot be diagnosed.

**Current controls:**
- Structured application logging.
- Stage-level timing measurements.
- Performance metadata stored with the job.
- Errors are logged internally while generic errors are returned to the client.

**Status:** Partially mitigated.

**Residual risk:** The current MVP is not an audit logging system. It does not provide tamper-resistant security audit trails.

---

## 7.4 Information Disclosure

### T-I1 — Lecture data exposed through path manipulation

**Threat:** A user requests another job's generated video, slide, PDF or other file.

**Current controls:**
- Job ID validation.
- Path containment checks.
- Explicit filename validation.
- Generated files remain under job-specific directories.

**Status:** Mitigated.

---

### T-I2 — Internal exception details exposed to the frontend

**Threat:** Stack traces, filesystem paths or implementation details are returned to users.

**Current controls:**
- Internal exceptions are logged server-side.
- API responses use generic error messages for unexpected failures.
- Validation failures return controlled messages.

**Status:** Mitigated.

---

### T-I3 — Lecture content sent to external processing services

**Threat:** Private lecture material is unintentionally uploaded to a third-party processing service.

**Current architecture:**
- Frame extraction is local.
- Audio extraction is local.
- Whisper transcription is local.
- SQLite storage is local.

**Important distinction:** YouTube ingestion necessarily retrieves content from YouTube when a YouTube URL is supplied. This is different from uploading the user's processed lecture content to a third-party AI processing service.

**Status:** Mitigated by architecture for processing; network-originated YouTube content remains an explicit input path.

---

### T-I4 — Search query or transcript leakage

**Threat:** Search results reveal lecture information outside the intended local application context.

**Current controls:**
- Local API architecture.
- Search query length limited to 200 characters.
- Results are returned only for the requested job.

**Residual risk:** There is no user authentication because the application is designed for local single-user operation.

**Status:** Acceptable for intended deployment; requires authentication if exposed to multiple users.

---

## 7.5 Denial of Service

### T-D1 — Oversized video upload

**Threat:** An attacker uploads an extremely large file to consume disk space.

**Current controls:**
- Maximum upload/download size: 4 GB.
- Upload is written in bounded 1 MB chunks.
- File size is validated after ingestion.
- Empty files are rejected.

**Status:** Mitigated within configured resource limits.

---

### T-D2 — Excessive frame generation

**Threat:** A long video combined with high frame sampling generates an excessive number of frames.

**Current controls:**
- Processing FPS is validated.
- Current pipeline intentionally uses 3 FPS.
- Maximum generated frame count is 100,000.
- Estimated frame count is checked where video duration is available.
- Final generated frame count is checked.
- Partial frames are cleaned up on failure.

**Status:** Mitigated.

---

### T-D3 — Malicious or pathological media file

**Threat:** A malformed video causes excessive CPU/memory consumption or crashes a media-processing stage.

**Current controls:**
- Input format allowlist.
- File-size limits.
- FFmpeg executed as a controlled subprocess.
- Generated frame count limits.
- Partial-output cleanup.
- No artificial lecture-duration restriction is imposed.

**Residual risk:** FFmpeg and media parsing remain a high-complexity attack surface. A fully hardened multi-tenant deployment would require stronger process isolation, resource quotas and potentially sandboxing.

**Status:** Partially mitigated.

---

### T-D4 — Expensive Whisper transcription

**Threat:** A very long lecture consumes significant CPU/RAM/GPU time during transcription.

**Current controls:**
- Maximum input video size.
- Local resource monitoring.
- Performance benchmarking.
- Whisper model/device are recorded in performance metadata.

**Residual risk:** There is no hard transcription-time or CPU quota in the current local MVP.

**Status:** Partially mitigated.

---

### T-D5 — Repeated search requests

**Threat:** A client sends excessive search requests to consume local resources.

**Current controls:**
- Query length limited to 200 characters.
- Search operates against local SQLite/FTS5 data.

**Residual risk:** No explicit rate limiter exists in the local MVP.

**Status:** Acceptable for intended single-user local deployment; rate limiting would be required for public exposure.

---

## 7.6 Elevation of Privilege

### T-E1 — Command injection through media-processing parameters

**Threat:** Crafted input causes execution of arbitrary OS commands.

**Current controls:**
- No shell execution.
- Controlled subprocess argument arrays.
- Validated FPS.
- Internally generated output paths.

**Status:** Mitigated for the identified attack path.

---

### T-E2 — Filesystem escape

**Threat:** Crafted paths allow the application to read/write outside its data directories.

**Current controls:**
- Path normalization.
- Directory containment validation.
- Sanitized filenames.
- Job-specific storage.

**Status:** Mitigated.

---

## 8. Threat Summary

| ID | Threat | Category | Primary impact | Current status |
|---|---|---|---|---|
| T-S1 | Forged/guessed job ID | Spoofing | Information disclosure | Mitigated for local MVP |
| T-S2 | Malicious YouTube URL | Spoofing | External input abuse | Mitigated |
| T-T1 | Path traversal | Tampering | File compromise | Mitigated |
| T-T2 | FFmpeg command injection | Tampering/Elevation | OS command execution | Mitigated |
| T-T3 | Unauthorized generated-file access | Tampering | Data compromise | Mitigated |
| T-R1 | Insufficient audit trace | Repudiation | Diagnostic/audit weakness | Partial |
| T-I1 | Cross-job file disclosure | Information disclosure | Privacy breach | Mitigated |
| T-I2 | Exception disclosure | Information disclosure | Information leakage | Mitigated |
| T-I3 | External processing exposure | Information disclosure | Privacy breach | Mitigated by local architecture |
| T-I4 | Search/transcript leakage | Information disclosure | Privacy breach | Acceptable for local MVP |
| T-D1 | Oversized upload | DoS | Disk exhaustion | Mitigated |
| T-D2 | Excessive frame generation | DoS | Disk/CPU exhaustion | Mitigated |
| T-D3 | Malicious media | DoS | CPU/RAM/process abuse | Partial |
| T-D4 | Expensive transcription | DoS | CPU/RAM/GPU exhaustion | Partial |
| T-D5 | Search flooding | DoS | Local resource exhaustion | Partial |
| T-E1 | Command injection | Elevation | Code execution | Mitigated |
| T-E2 | Filesystem escape | Elevation | Host file access | Mitigated |

---

# 9. Security Controls Implemented

The current security-hardening baseline includes:

- 4 GB maximum video size
- bounded 1 MB upload chunks
- supported video-extension allowlist
- HTTPS-only YouTube URLs
- explicit YouTube hostname allowlist
- rejection of credentials in YouTube URLs
- rejection of explicit URL ports
- sanitized filenames
- path traversal protection
- job-specific directories
- job-ID validation
- search query limit of 200 characters
- controlled FFmpeg argument arrays
- `shell=False`
- validated processing FPS
- 3 FPS processing configuration retained intentionally
- maximum generated-frame protection
- partial-frame cleanup
- safe generated-file serving
- restricted local CORS origins
- generic client-facing errors
- server-side exception logging
- PDF path validation
- downloaded-video path validation
- performance/resource monitoring

---

# 10. Residual Risks

The following risks remain because they are outside the intended MVP security boundary or would require substantially stronger isolation:

### R1 — Local host compromise

If the operating system is already compromised, the application cannot guarantee confidentiality of locally stored lectures.

### R2 — Media parser vulnerabilities

FFmpeg and other media libraries process attacker-controlled media. Keeping them behind controlled subprocess execution reduces application-level risk but does not mathematically eliminate vulnerabilities in the underlying parser.

### R3 — Resource exhaustion during Whisper

Large but permitted lectures can still consume substantial CPU/RAM/GPU resources.

### R4 — No authentication

The local application assumes a trusted single-user environment. It is not designed as a multi-user server.

### R5 — No encrypted local storage

Lecture videos, transcripts, slides and PDFs are stored as ordinary local files/SQLite data. Filesystem encryption is therefore delegated to the operating system/device.

### R6 — YouTube dependency

When a YouTube URL is supplied, the application depends on external network availability and the behavior of YouTube/`yt-dlp`.

---

# 11. Risk Treatment

| Risk | Treatment |
|---|---|
| Path traversal | Mitigate |
| Command injection | Mitigate |
| Cross-job file access | Mitigate |
| Oversized uploads | Mitigate |
| Excessive frame generation | Mitigate |
| Unsafe YouTube URLs | Mitigate |
| Information leakage through errors | Mitigate |
| Malicious media parser behavior | Reduce / monitor |
| Whisper resource exhaustion | Reduce / benchmark |
| Search flooding | Accept for local MVP |
| Missing authentication | Accept within local-only scope |
| Host compromise | Out of scope |
| Encrypted storage | Delegate to host OS |

---

# 12. Security Testing Alignment

The threat model maps directly to the security tests performed for the current MVP.

### URL validation tests

Rejected:

```text
https://www.google.com
https://example.com/lecture.mp4
http://youtube.com/watch?v=dQw4w9WgXcQ
https://user:password@youtube.com/watch?v=dQw4w9WgXcQ
https://youtube.com:8080/watch?v=dQw4w9WgXcQ
https://youtube.com.example.com/watch?v=dQw4w9WgXcQ
```

Accepted for validation:

```text
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4wWgXcQ
```

These tests specifically exercise the YouTube URL validation threat identified in T-S2.

---

# 13. Security Posture

For the intended **single-user local deployment**, the current security posture can be summarized as:

```text
                 UNTRUSTED INPUT
                       │
          ┌────────────┴────────────┐
          │                         │
       Video                    YouTube URL
          │                         │
          └────────────┬────────────┘
                       ▼
              Input Validation
                       │
                       ▼
                Job Isolation
                       │
                       ▼
             Controlled Processing
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        FFmpeg      Whisper       SQLite
          │            │            │
          └────────────┼────────────┘
                       ▼
                Local Artifacts
                       │
                       ▼
                 Local Frontend
```

The principal security strategy is **local processing + strict input validation + filesystem isolation + controlled subprocess execution + bounded resource consumption**.

The main remaining risks are associated with resource-intensive processing, complex media parsing, lack of authentication in the intentionally single-user architecture, and the security of the host operating system itself.

---

# 14. Conclusion

The Lecture Companion threat model identifies the application's principal attack surfaces around untrusted video files, YouTube URLs, filenames and paths, FFmpeg execution, generated artifacts, search input and resource-intensive processing.

The implemented controls substantially reduce the most relevant application-level risks for the intended local MVP, particularly path traversal, unsafe URL handling, command injection, uncontrolled frame generation, oversized uploads and cross-job file access.

The remaining risks are primarily environmental or architectural: host compromise, media-parser vulnerabilities, resource exhaustion during expensive processing, and the absence of authentication for a deployment that is intentionally designed around a trusted local user.

For the current project scope, these residual risks should be documented rather than expanded into unnecessary features. A future multi-user or public deployment would require a new threat-model iteration with authentication, authorization, rate limiting, stronger process isolation, resource quotas and deployment/network controls.
