from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_FPS = 3.0


class SlideSpeechLinkingError(Exception):
    """Raised when slide/transcript data cannot be linked safely."""


def _load_json(path: str | Path) -> dict[str, Any]:
    """
    Load and validate a JSON object.
    """
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"JSON file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise SlideSpeechLinkingError(
            f"Invalid JSON file: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise SlideSpeechLinkingError(
            f"Expected JSON object in {path}"
        )

    return data


def _clean_word_text(word: str) -> str:
    """
    Normalize Whisper word text without destroying punctuation.
    """
    return " ".join(str(word).split())


def _word_midpoint(word: dict[str, Any]) -> float:
    """
    Return the temporal midpoint of a Whisper word.

    Midpoint assignment is useful for boundary cases:
    if a word overlaps a slide boundary, the word is assigned
    to whichever slide contains the majority of its duration.
    """
    start = float(word["start"])
    end = float(word["end"])

    if end < start:
        raise SlideSpeechLinkingError(
            f"Invalid word timing: {word}"
        )

    return start + ((end - start) / 2.0)


def _word_belongs_to_interval(
    word: dict[str, Any],
    interval_start: float,
    interval_end: float,
) -> bool:
    """
    Determine whether a word belongs to a slide occurrence.

    We use the word midpoint rather than requiring the complete
    word to fit inside the slide interval. This prevents speech
    near slide boundaries from being incorrectly discarded.
    """
    midpoint = _word_midpoint(word)

    return (
        midpoint >= interval_start
        and midpoint < interval_end
    )


def _build_segment_text(words: list[dict[str, Any]]) -> str:
    """
    Reconstruct text from selected Whisper words.

    Whisper already attaches punctuation to many words, so joining
    with spaces preserves the original transcript reasonably well.
    """
    if not words:
        return ""

    text = " ".join(
        _clean_word_text(word["word"])
        for word in words
        if _clean_word_text(word["word"])
    )

    return " ".join(text.split())


def _link_words_to_occurrence(
    occurrence: dict[str, Any],
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Assign Whisper words to one slide occurrence.

    Each transcript segment may be split across slide boundaries.
    Only words whose midpoint falls inside the slide occurrence
    are retained.
    """
    start_time = float(occurrence["start_time"])
    end_time = float(occurrence["end_time"])

    linked_segments: list[dict[str, Any]] = []

    for segment in segments:
        segment_id = segment.get("id")

        words = segment.get("words", [])

        if not isinstance(words, list):
            continue

        selected_words = []

        for word in words:
            if not isinstance(word, dict):
                continue

            if "start" not in word or "end" not in word:
                continue

            if "word" not in word:
                continue

            if _word_belongs_to_interval(
                word,
                start_time,
                end_time,
            ):
                selected_words.append(word)

        if not selected_words:
            continue

        selected_words.sort(
            key=lambda word: float(word["start"])
        )

        text = _build_segment_text(selected_words)

        if not text:
            continue

        linked_segments.append(
            {
                "segment_id": segment_id,
                "start": float(selected_words[0]["start"]),
                "end": float(selected_words[-1]["end"]),
                "text": text,
                "words": [
                    {
                        "word": _clean_word_text(word["word"]),
                        "start": float(word["start"]),
                        "end": float(word["end"]),
                    }
                    for word in selected_words
                ],
            }
        )

    return linked_segments


def _prepare_slide_occurrences(
    slides: list[dict[str, Any]],
    fps: float,
) -> list[dict[str, Any]]:
    """
    Convert detector frame intervals into chronological
    slide occurrences in seconds.
    """
    if fps <= 0:
        raise ValueError("FPS must be greater than zero.")

    occurrences: list[dict[str, Any]] = []

    for slide in slides:
        slide_id = slide.get("slide_id")

        if slide_id is None:
            raise SlideSpeechLinkingError(
                f"Slide is missing slide_id: {slide}"
            )

        representative_path = slide.get(
            "representative_path"
        )

        raw_occurrences = slide.get(
            "occurrences",
            [],
        )

        if not isinstance(raw_occurrences, list):
            raise SlideSpeechLinkingError(
                f"Invalid occurrences for slide {slide_id}"
            )

        for occurrence in raw_occurrences:
            if (
                "start_frame" not in occurrence
                or "end_frame" not in occurrence
            ):
                raise SlideSpeechLinkingError(
                    f"Occurrence missing frame boundaries: "
                    f"{occurrence}"
                )

            start_frame = int(
                occurrence["start_frame"]
            )
            end_frame = int(
                occurrence["end_frame"]
            )

            if start_frame < 0:
                raise SlideSpeechLinkingError(
                    f"Negative start frame: {occurrence}"
                )

            if end_frame < start_frame:
                raise SlideSpeechLinkingError(
                    f"Invalid frame interval: {occurrence}"
                )

            start_time = start_frame / fps

            # end_frame is inclusive in the detector.
            end_time = (end_frame + 1) / fps

            occurrences.append(
                {
                    "slide_id": slide_id,
                    "representative_path": representative_path,
                    "appearance_index": occurrence.get(
                        "appearance_index"
                    ),
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )

    occurrences.sort(
        key=lambda item: (
            item["start_time"],
            item["end_time"],
            item["slide_id"],
        )
    )

    return occurrences


def _validate_timeline(
    occurrences: list[dict[str, Any]],
) -> None:
    """
    Verify that chronological slide occurrences do not overlap.

    Adjacent intervals are expected because one slide ends when
    the next slide begins.
    """
    for previous, current in zip(
        occurrences,
        occurrences[1:],
    ):
        previous_end = previous["end_time"]
        current_start = current["start_time"]

        if current_start < previous_end:
            raise SlideSpeechLinkingError(
                "Overlapping slide occurrences detected: "
                f"Slide {previous['slide_id']} "
                f"({previous['start_time']:.3f}-"
                f"{previous_end:.3f}) overlaps "
                f"Slide {current['slide_id']} "
                f"({current_start:.3f}-"
                f"{current['end_time']:.3f})"
            )


def link_slides_to_speech(
    slides: list[dict[str, Any]],
    transcript: dict[str, Any],
    fps: float = DEFAULT_FPS,
) -> dict[str, Any]:
    """
    Link logical slide occurrences with Whisper speech.

    Parameters
    ----------
    slides:
        Output returned by detect_slides().

    transcript:
        JSON object produced by the Lecture Companion
        transcriber. Expected structure:

        {
            "segments": [
                {
                    "id": 0,
                    "start": ...,
                    "end": ...,
                    "text": ...,
                    "words": [...]
                }
            ]
        }

    fps:
        Actual frame extraction rate.

    Returns
    -------
    dict
        Complete slide/speech linking result.
    """
    if not isinstance(slides, list):
        raise SlideSpeechLinkingError(
            "slides must be a list."
        )

    segments = transcript.get("segments")

    if not isinstance(segments, list):
        raise SlideSpeechLinkingError(
            "Transcript does not contain a valid 'segments' list."
        )

    occurrences = _prepare_slide_occurrences(
        slides,
        fps,
    )

    _validate_timeline(occurrences)

    # ---------------------------------------------------------
    # Link speech to every chronological occurrence
    # ---------------------------------------------------------

    for occurrence in occurrences:
        linked_segments = _link_words_to_occurrence(
            occurrence,
            segments,
        )

        occurrence["speech_segments"] = linked_segments

        occurrence["speech_text"] = " ".join(
            segment["text"]
            for segment in linked_segments
        ).strip()

    # ---------------------------------------------------------
    # Aggregate occurrences under their logical slide ID
    # ---------------------------------------------------------

    slide_map: dict[Any, dict[str, Any]] = {}

    for slide in slides:
        slide_id = slide["slide_id"]

        slide_map[slide_id] = {
            "slide_id": slide_id,
            "representative_path": slide.get(
                "representative_path"
            ),
            "occurrences": [],
            "speech_text": "",
        }

    for occurrence in occurrences:
        slide_id = occurrence["slide_id"]

        if slide_id not in slide_map:
            slide_map[slide_id] = {
                "slide_id": slide_id,
                "representative_path": occurrence.get(
                    "representative_path"
                ),
                "occurrences": [],
                "speech_text": "",
            }

        slide_map[slide_id]["occurrences"].append(
            {
                "appearance_index": occurrence[
                    "appearance_index"
                ],
                "start_frame": occurrence[
                    "start_frame"
                ],
                "end_frame": occurrence[
                    "end_frame"
                ],
                "start_time": round(
                    occurrence["start_time"],
                    3,
                ),
                "end_time": round(
                    occurrence["end_time"],
                    3,
                ),
                "speech_text": occurrence[
                    "speech_text"
                ],
                "speech_segments": occurrence[
                    "speech_segments"
                ],
            }
        )

    # ---------------------------------------------------------
    # Build aggregated logical-slide speech
    # ---------------------------------------------------------

    for slide in slide_map.values():
        occurrence_texts = [
            occurrence["speech_text"]
            for occurrence in slide["occurrences"]
            if occurrence["speech_text"]
        ]

        slide["speech_text"] = " ".join(
            occurrence_texts
        ).strip()

    ordered_slides = sorted(
        slide_map.values(),
        key=lambda slide: slide["slide_id"],
    )

    return {
        "fps": fps,
        "slide_count": len(ordered_slides),
        "appearance_count": len(occurrences),
        "slides": ordered_slides,
    }


def link_from_files(
    slides_json_path: str | Path,
    transcript_json_path: str | Path,
    output_json_path: str | Path,
    fps: float = DEFAULT_FPS,
) -> dict[str, Any]:
    """
    Load detector/transcript JSON files, link them, and save
    the resulting JSON.
    """
    slides_data = _load_json(slides_json_path)
    transcript_data = _load_json(transcript_json_path)

    slides = slides_data.get("slides")

    if not isinstance(slides, list):
        raise SlideSpeechLinkingError(
            "Slides JSON does not contain a valid 'slides' list."
        )

    result = link_slides_to_speech(
        slides=slides,
        transcript=transcript_data,
        fps=fps,
    )

    output_path = Path(output_json_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return result