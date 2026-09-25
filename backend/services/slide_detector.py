from __future__ import annotations

from pathlib import Path
from typing import Optional
import math
import shutil

import cv2
import numpy as np
from PIL import Image
import imagehash
from skimage.metrics import structural_similarity

# ============================================================
# CONFIGURATION
# ============================================================

# Frames are currently extracted at 2 FPS.
# The detector itself does not depend on a specific video FPS,
# but these values are expressed in extracted-frame units.

LOW_RES = (256, 144)

# Temporal comparison distances.
# Comparing farther apart helps detect subtle slide changes.
SHORT_GAP = 2
MEDIUM_GAP = 5
LONG_GAP = 10

# Minimum number of extracted frames between independent
# transitions. This prevents animation/noise from generating
# dozens of slides.
MIN_TRANSITION_GAP = 3

# How many frames after a transition should show the new slide.
PERSISTENCE_FRAMES = 3

# Duplicate detection
PHASH_DISTANCE = 5
DUPLICATE_SSIM = 0.92

# Maximum number of frames sampled while selecting
# representative images.
MAX_REPRESENTATIVE_SAMPLES = 12


# ============================================================
# IMAGE HELPERS
# ============================================================


def _load_frame(
    path: Path, max_width: int | None = None, max_height: int | None = None
) -> Optional[np.ndarray]:
    """
    Load a frame as BGR image.

    When max_width/max_height are provided, the image is
    immediately downscaled to prevent unnecessary memory usage.
    """

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        return None

    if max_width is not None and max_height is not None:

        height, width = image.shape[:2]

        scale = min(max_width / width, max_height / height, 1.0)

        if scale < 1.0:

            new_width = max(1, int(width * scale))

            new_height = max(1, int(height * scale))

            image = cv2.resize(
                image, (new_width, new_height), interpolation=cv2.INTER_AREA
            )

    return image


def _resize_gray(image: np.ndarray) -> np.ndarray:
    """
    Convert image to grayscale and resize to a small common size.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    return cv2.resize(gray, LOW_RES, interpolation=cv2.INTER_AREA)


def _resize_color(image: np.ndarray) -> np.ndarray:
    """
    Resize image while preserving color information.
    """
    return cv2.resize(image, LOW_RES, interpolation=cv2.INTER_AREA)


# ============================================================
# VISUAL FEATURES
# ============================================================


def _pixel_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Mean absolute grayscale difference.
    """
    a = _resize_gray(frame_a).astype(np.float32) / 255.0
    b = _resize_gray(frame_b).astype(np.float32) / 255.0

    return float(np.mean(np.abs(a - b)))


def _edge_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Difference between edge maps.

    Useful when the background remains almost identical but
    text/diagrams change.
    """
    a = _resize_gray(frame_a)
    b = _resize_gray(frame_b)

    edges_a = cv2.Canny(a, 50, 150)
    edges_b = cv2.Canny(b, 50, 150)

    return float(
        np.mean(np.abs(edges_a.astype(np.float32) - edges_b.astype(np.float32))) / 255.0
    )


def _histogram_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Compare HSV color distributions.

    Helps detect slides whose structure changes less than
    their overall color/content distribution.
    """
    a = cv2.cvtColor(_resize_color(frame_a), cv2.COLOR_BGR2HSV)

    b = cv2.cvtColor(_resize_color(frame_b), cv2.COLOR_BGR2HSV)

    hist_a = cv2.calcHist([a], [0, 1], None, [32, 32], [0, 180, 0, 256])

    hist_b = cv2.calcHist([b], [0, 1], None, [32, 32], [0, 180, 0, 256])

    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)

    distance = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA)

    return float(distance)


def _structural_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    SSIM-based structural difference.

    Used on already downscaled images, so it remains relatively
    inexpensive.
    """
    a = _resize_gray(frame_a)
    b = _resize_gray(frame_b)

    score = structural_similarity(a, b)

    return float(1.0 - score)


# ============================================================
# COMBINED CHANGE SCORE
# ============================================================


def _visual_change(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Compute a normalized combined visual-change score.

    Multiple signals are intentionally combined rather than
    relying on a single threshold.
    """

    pixel = _pixel_difference(frame_a, frame_b)
    edge = _edge_difference(frame_a, frame_b)
    histogram = _histogram_difference(frame_a, frame_b)
    structural = _structural_difference(frame_a, frame_b)

    # The weights deliberately favor structure and edges because
    # lecture slides often keep the same background/template.
    score = 0.30 * pixel + 0.25 * edge + 0.15 * histogram + 0.30 * structural

    return float(score)


# ============================================================
# ADAPTIVE THRESHOLD
# ============================================================


def _robust_threshold(scores: np.ndarray) -> float:
    """
    Calculate an adaptive threshold from the video's own score
    distribution.

    MAD = Median Absolute Deviation.

    This avoids assuming that every YouTube lecture has the same
    visual-change characteristics.
    """

    valid = scores[np.isfinite(scores)]

    if len(valid) == 0:
        return float("inf")

    median = float(np.median(valid))

    mad = float(np.median(np.abs(valid - median)))

    # Robust z-score style threshold.
    robust_threshold = median + 5.0 * max(mad, 1e-5)

    # Also use a percentile guard.
    percentile_threshold = float(np.percentile(valid, 96))

    # We don't want the threshold to become excessively high.
    threshold = min(robust_threshold, percentile_threshold)

    return float(threshold)


# ============================================================
# LOCAL PEAK DETECTION
# ============================================================


def _is_local_peak(scores: np.ndarray, index: int, radius: int = 3) -> bool:
    """
    Check whether a score is a local maximum.
    """

    start = max(0, index - radius)
    end = min(len(scores), index + radius + 1)

    neighbourhood = scores[start:end]

    return scores[index] >= np.max(neighbourhood)


# ============================================================
# TRANSITION DETECTION
# ============================================================


def _calculate_transition_scores(
    frame_files: list[Path],
) -> tuple[np.ndarray, list[np.ndarray]]:
    """
    Calculate multi-scale visual-change scores.

    Instead of only comparing adjacent frames:

        frame[i] vs frame[i-1]

    we compare:

        i vs i-2
        i vs i-5
        i vs i-10

    This is important for:
    - gradual transitions
    - fade transitions
    - animations
    - subtle text changes
    """

    frame_count = len(frame_files)

    short_scores = np.zeros(frame_count, dtype=np.float32)
    medium_scores = np.zeros(frame_count, dtype=np.float32)
    long_scores = np.zeros(frame_count, dtype=np.float32)

    cache: dict[int, np.ndarray] = {}
    # as repeatedly loading frames from disk can be slow, we cache a limited number of frames in memory
    MAX_CACHE_SIZE = 20

    def get_frame(index: int) -> Optional[np.ndarray]:

        if index < 0 or index >= frame_count:
            return None

        if index not in cache:

            image = _load_frame(frame_files[index], max_width=640, max_height=360)

            if image is None:
                return None

            cache[index] = image

            if len(cache) > MAX_CACHE_SIZE:
                oldest_key = next(iter(cache))
                del cache[oldest_key]

        return cache[index]

    for i in range(frame_count):

        current = get_frame(i)

        if current is None:
            continue

        if i >= SHORT_GAP:
            previous = get_frame(i - SHORT_GAP)

            if previous is not None:
                short_scores[i] = _visual_change(previous, current)

        if i >= MEDIUM_GAP:
            previous = get_frame(i - MEDIUM_GAP)

            if previous is not None:
                medium_scores[i] = _visual_change(previous, current)

        if i >= LONG_GAP:
            previous = get_frame(i - LONG_GAP)

            if previous is not None:
                long_scores[i] = _visual_change(previous, current)

    # Combined temporal score.
    #
    # Short gap catches abrupt changes.
    # Medium gap catches normal transitions.
    # Long gap catches gradual transitions.
    combined = 0.25 * short_scores + 0.40 * medium_scores + 0.35 * long_scores

    return combined, [short_scores, medium_scores, long_scores]


def _candidate_transitions(frame_files: list[Path], scores: np.ndarray) -> list[int]:
    """
    Find transition candidates using two visual-signal tiers.

    Tier 1 catches strong transitions.

    Tier 2 deliberately recovers weaker transitions that can occur when
    two lecture slides use the same template, background, or color palette.

    The recovery tier is still subjected to temporal confirmation later,
    so lowering the candidate threshold does not automatically create
    a new slide.
    """

    strong_threshold = _robust_threshold(scores)

    valid = scores[np.isfinite(scores)]

    if len(valid) == 0:
        return []

    median = float(np.median(valid))
    mad = float(np.median(np.abs(valid - median)))

    recovery_threshold = median + 3.0 * max(mad, 1e-5)
    recovery_percentile = float(np.percentile(valid, 92))

    # Use the less aggressive of the two recovery guards, but never let
    # the recovery threshold fall below the normal robust baseline.
    recovery_threshold = max(
        median + 2.2 * max(mad, 1e-5),
        min(recovery_threshold, recovery_percentile),
    )

    print(f"Adaptive transition threshold: {strong_threshold:.5f}")
    print(f"Recovery transition threshold: {recovery_threshold:.5f}")

    candidates: list[int] = []

    for i in range(LONG_GAP, len(scores)):

        is_strong = scores[i] >= strong_threshold
        is_recovery = scores[i] >= recovery_threshold

        if not (is_strong or is_recovery):
            continue

        radius = 3 if is_strong else 2

        if not _is_local_peak(scores, i, radius=radius):
            continue

        # Avoid multiple detections around the same transition.
        if candidates:
            if i - candidates[-1] < MIN_TRANSITION_GAP:

                if scores[i] > scores[candidates[-1]]:
                    candidates[-1] = i

                continue

        candidates.append(i)

    return candidates


# ============================================================
# TEMPORAL CONFIRMATION
# ============================================================


def _confirm_transition(
    frame_files: list[Path], candidate: int, scores: np.ndarray
) -> bool:
    """
    Confirm that a detected transition represents a persistent
    visual change rather than a transient animation/noise spike.
    """

    if candidate <= 0:
        return False

    reference_index = max(0, candidate - MEDIUM_GAP)

    reference = _load_frame(frame_files[reference_index])

    if reference is None:
        return False

    persistent_count = 0

    for offset in range(0, PERSISTENCE_FRAMES):

        index = candidate + offset

        if index >= len(frame_files):
            break

        current = _load_frame(frame_files[index])

        if current is None:
            continue

        change = _visual_change(reference, current)

        # Compare with adaptive score distribution indirectly.
        # A strong local score should remain visible for multiple
        # frames if this is a real slide change.
        if change >= scores[candidate] * 0.45:
            persistent_count += 1

    return persistent_count >= 2


# ============================================================
# GROUPING
# ============================================================


def _group_frames(frame_files: list[Path]) -> tuple[list[list[Path]], dict]:
    """
    Divide the video into logical slide appearances.
    """

    print("Calculating multi-scale visual changes...")

    scores, scale_scores = _calculate_transition_scores(frame_files)

    candidates = _candidate_transitions(frame_files, scores)

    confirmed: list[int] = []

    for candidate in candidates:

        if _confirm_transition(frame_files, candidate, scores):
            confirmed.append(candidate)

    # Build logical groups.
    groups: list[list[Path]] = []

    boundaries = [0] + confirmed + [len(frame_files)]

    for start, end in zip(boundaries[:-1], boundaries[1:]):

        group = frame_files[start:end]

        if group:
            groups.append(group)

    stats = {
        "candidate_transitions": len(candidates),
        "confirmed_transitions": len(confirmed),
        "change_scores": scores,
        "short_scores": scale_scores[0],
        "medium_scores": scale_scores[1],
        "long_scores": scale_scores[2],
    }

    return groups, stats


# ============================================================
# REPRESENTATIVE FRAME SELECTION
# ============================================================


def _visibility_score(image: np.ndarray) -> float:
    """
    Estimate how clearly slide content is visible.

    Downscale first so representative-frame selection does not
    require processing full-resolution lecture frames.
    """

    small = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)

    return float(np.mean(edges > 0))


def _sharpness_score(image: np.ndarray) -> float:
    """
    Estimate image sharpness on a reduced-size frame.
    """

    small = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _select_representative_frame(group: list[Path]) -> Path:
    """
    Select the clearest frame from a logical slide interval.
    """

    if len(group) <= MAX_REPRESENTATIVE_SAMPLES:
        samples = group
    else:
        indexes = np.linspace(0, len(group) - 1, MAX_REPRESENTATIVE_SAMPLES, dtype=int)

        samples = [group[i] for i in indexes]

    best_path = samples[0]
    best_score = -float("inf")

    for path in samples:

        image = _load_frame(path, max_width=640, max_height=360)

        if image is None:
            continue

        visibility = _visibility_score(image)

        sharpness = math.log1p(_sharpness_score(image))

        score = 0.60 * visibility + 0.40 * sharpness

        if score > best_score:
            best_score = score
            best_path = path

    return best_path


# ============================================================
# HASH / DUPLICATE DETECTION
# ============================================================


def _calculate_phash(image_path: Path) -> imagehash.ImageHash:

    with Image.open(image_path) as image:
        return imagehash.phash(image)


def _slide_ssim(image_a: Path, image_b: Path) -> float:

    a = _load_frame(image_a, max_width=640, max_height=360)

    b = _load_frame(image_b, max_width=640, max_height=360)

    if a is None or b is None:
        return 0.0

    a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)

    b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

    a = cv2.resize(a, (384, 216), interpolation=cv2.INTER_AREA)

    b = cv2.resize(b, (384, 216), interpolation=cv2.INTER_AREA)

    return float(structural_similarity(a, b))


def _edge_similarity(image_a: Path, image_b: Path) -> float:
    """
    Compare structural edge maps.

    This is intentionally used as a second guard for duplicate detection.
    Two slides can have similar global appearance while containing
    different diagrams or text blocks.
    """

    a = _load_frame(image_a, max_width=640, max_height=360)
    b = _load_frame(image_b, max_width=640, max_height=360)

    if a is None or b is None:
        return 0.0

    a = _resize_gray(a)
    b = _resize_gray(b)

    edges_a = cv2.Canny(a, 50, 150).astype(np.float32) / 255.0
    edges_b = cv2.Canny(b, 50, 150).astype(np.float32) / 255.0

    difference = float(np.mean(np.abs(edges_a - edges_b)))

    return 1.0 - difference


def _find_duplicate_slide(
    representative: Path, unique_slides: list[dict]
) -> Optional[int]:

    current_hash = _calculate_phash(representative)

    for index, slide in enumerate(unique_slides):

        existing_hash = slide["_phash"]

        distance = current_hash - existing_hash

        if distance > PHASH_DISTANCE:
            continue

        existing_path = Path(slide["_representative_path"])

        similarity = _slide_ssim(representative, existing_path)

        if similarity < DUPLICATE_SSIM:
            continue

        edge_similarity = _edge_similarity(representative, existing_path)

        # Require both global structural similarity and local/layout
        # similarity before declaring two slides to be the same.
        if edge_similarity >= 0.90:
            return index

    return None


# ============================================================
# FINAL OCR-FREE DUPLICATE POLICY
# ============================================================

# A slide is merged with an existing unique slide only when:
#
# 1. pHash is close,
# 2. SSIM is very high,
# 3. edge/layout similarity is also high.
#
# This deliberately favors recall of genuinely different slides
# over aggressive duplicate merging.


# ============================================================
# SAVE SLIDE
# ============================================================


def _save_slide_image(
    representative: Path, output_dir: Path, slide_number: int
) -> Path:

    output_dir.mkdir(parents=True, exist_ok=True)

    destination = output_dir / f"slide_{slide_number:03d}.jpg"

    shutil.copy2(representative, destination)

    return destination


# ============================================================
# MAIN DETECTOR
# ============================================================


def detect_slides(
    frames_dir: str | Path, output_dir: str | Path | None = None
) -> list[dict]:

    frames_dir = Path(frames_dir)

    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")

    frame_files = sorted(frames_dir.glob("*.jpg"))

    if not frame_files:
        frame_files = sorted(frames_dir.glob("*.png"))

    if not frame_files:
        raise ValueError(f"No frame images found in {frames_dir}")

    print()
    print("=" * 40)
    print("LECTURE COMPANION - SLIDE DETECTION")
    print("=" * 40)
    print(f"Input frames: {len(frame_files)}")
    print()

    if output_dir is None:
        output_dir = frames_dir.parent / "slides"

    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # 1. Detect logical slide appearances
    # --------------------------------------------------------

    groups, stats = _group_frames(frame_files)

    print(f"Candidate transitions: " f"{stats['candidate_transitions']}")

    print(f"Confirmed transitions: " f"{stats['confirmed_transitions']}")

    print(f"Logical slide appearances: " f"{len(groups)}")

    # --------------------------------------------------------
    # 2. Representative frame per appearance
    # --------------------------------------------------------

    appearances = []

    for appearance_index, group in enumerate(groups):

        representative = _select_representative_frame(group)

        appearances.append(
            {
                "appearance_index": appearance_index,
                "start_frame": frame_files.index(group[0]),
                "end_frame": frame_files.index(group[-1]),
                "representative_path": representative,
                "frame_count": len(group),
            }
        )

    # --------------------------------------------------------
    # 3. Global duplicate detection
    # --------------------------------------------------------

    unique_slides: list[dict] = []

    for appearance in appearances:

        representative = appearance["representative_path"]

        duplicate_index = _find_duplicate_slide(representative, unique_slides)

        if duplicate_index is None:

            slide_number = len(unique_slides) + 1

            saved_path = _save_slide_image(representative, output_dir, slide_number)

            slide = {
                "slide_id": slide_number,
                "representative_path": str(saved_path),
                "_representative_path": str(representative),
                "_phash": _calculate_phash(representative),
                "occurrences": [],
            }

            unique_slides.append(slide)

            duplicate_index = len(unique_slides) - 1

        unique_slides[duplicate_index]["occurrences"].append(
            {
                "appearance_index": appearance["appearance_index"],
                "start_frame": appearance["start_frame"],
                "end_frame": appearance["end_frame"],
                "frame_count": appearance["frame_count"],
            }
        )

    # --------------------------------------------------------
    # 4. Clean internal fields
    # --------------------------------------------------------

    results = []

    for slide in unique_slides:

        cleaned = {
            key: value for key, value in slide.items() if not key.startswith("_")
        }

        results.append(cleaned)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 40)
    print("Slide Detection")
    print("=" * 40)

    print(f"Input frames: " f"{len(frame_files)}")

    print(f"Candidate transitions: " f"{stats['candidate_transitions']}")

    print(f"Confirmed transitions: " f"{stats['confirmed_transitions']}")

    print(f"Logical slide appearances: " f"{len(groups)}")

    print(f"Unique slides: " f"{len(results)}")

    print(f"Slide output directory: " f"{output_dir}")

    print("=" * 40)

    return results


# ============================================================
# DEBUG / DIRECT TEST
# ============================================================

if __name__ == "__main__":

    # Existing extracted-frame dataset.
    # This allows us to test the detector without downloading
    # the YouTube video or running FFmpeg again.

    TEST_JOB_ID = "b739d6db"

    BASE_DIR = Path(__file__).resolve().parents[1]

    FRAMES_DIR = BASE_DIR / "data" / "frames" / TEST_JOB_ID

    SLIDES_DIR = BASE_DIR / "data" / "slides" / TEST_JOB_ID

    detect_slides(FRAMES_DIR, SLIDES_DIR)
