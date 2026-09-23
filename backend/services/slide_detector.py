from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


# ---------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------

def _load_gray(frame_path: Path, size=(640, 360)):
    image = cv2.imread(str(frame_path))

    if image is None:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)

    return gray


def _load_small_blurred(frame_path: Path, size=(160, 90)):
    image = cv2.imread(str(frame_path))

    if image is None:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    gray = cv2.resize(
        gray,
        size,
        interpolation=cv2.INTER_AREA,
    )

    gray = cv2.GaussianBlur(
        gray,
        (5, 5),
        0,
    )

    return gray.astype(np.int16)


# ---------------------------------------------------------
# Patch-based SSIM
# ---------------------------------------------------------

def _patch_ssim(
    image_a,
    image_b,
    rows=6,
    cols=8,
):
    """
    Calculate SSIM separately for multiple patches.

    This prevents a moving teacher from dominating
    the similarity calculation.
    """

    height, width = image_a.shape

    patch_height = height // rows
    patch_width = width // cols

    scores = []

    for row in range(rows):
        for col in range(cols):

            y1 = row * patch_height
            y2 = (row + 1) * patch_height

            x1 = col * patch_width
            x2 = (col + 1) * patch_width

            patch_a = image_a[y1:y2, x1:x2]
            patch_b = image_b[y1:y2, x1:x2]

            score = ssim(
                patch_a,
                patch_b,
                data_range=255,
            )

            scores.append(score)

    # Median is deliberately used instead of mean.
    #
    # A teacher may cover several patches.
    # We don't want those patches to decide the entire result.

    return float(np.median(scores))


# ---------------------------------------------------------
# Same-slide similarity
# ---------------------------------------------------------

def _frame_similarity(
    frame_a: Path,
    frame_b: Path,
):
    image_a = _load_gray(frame_a)
    image_b = _load_gray(frame_b)

    if image_a is None or image_b is None:
        return 0.0

    return _patch_ssim(image_a, image_b)


# ---------------------------------------------------------
# Frame sampling
# ---------------------------------------------------------

def _sample_frames(
    frame_files,
    max_samples=10,
):
    """
    Select evenly distributed reference frames.

    This keeps processing reasonable even if a slide
    remains on screen for several minutes.
    """

    if len(frame_files) <= max_samples:
        return frame_files

    indexes = np.linspace(
        0,
        len(frame_files) - 1,
        max_samples,
        dtype=int,
    )

    return [
        frame_files[index]
        for index in indexes
    ]


# ---------------------------------------------------------
# Visibility analysis
# ---------------------------------------------------------

def _visibility_mask(
    candidate_path,
    reference_files,
    reference_cache,
    tolerance=12,
):
    """
    Estimate which regions of a frame are visible
    rather than being covered by a moving object.

    A pixel is considered stable if it matches the
    same location in other frames.

    Moving teacher -> inconsistent pixels
    Static slide  -> consistent pixels
    """

    candidate = reference_cache.get(candidate_path)

    if candidate is None:

        candidate = _load_small_blurred(
            candidate_path
        )

        if candidate is None:
            return None

        reference_cache[candidate_path] = candidate

    matches = np.zeros(
        candidate.shape,
        dtype=np.uint8,
    )

    comparison_count = 0

    for reference_path in reference_files:

        if reference_path == candidate_path:
            continue

        reference = reference_cache.get(reference_path)

        if reference is None:
            reference = _load_small_blurred(
                reference_path
            )

            if reference is None:
                continue

            reference_cache[reference_path] = reference

        difference = np.abs(
            candidate.astype(np.int16)
            - reference.astype(np.int16)
        )

        matches += (
            difference <= tolerance
        ).astype(np.uint8)

        comparison_count += 1

    if comparison_count == 0:
        return np.ones_like(
            candidate,
            dtype=bool,
        )

    # A pixel only needs to agree with a few other frames.
    #
    # This is important because the teacher may be moving
    # throughout the group.

    required_matches = max(
        1,
        int(np.ceil(comparison_count * 0.25)),
    )

    mask = matches >= required_matches

    # Remove tiny isolated regions.

    kernel = np.ones(
        (3, 3),
        dtype=np.uint8,
    )

    mask = cv2.morphologyEx(
        mask.astype(np.uint8),
        cv2.MORPH_OPEN,
        kernel,
    )

    return mask.astype(bool)


# ---------------------------------------------------------
# Sharpness
# ---------------------------------------------------------

def _sharpness_score(frame_path):
    """
    Measures how sharp the frame is.

    This helps avoid selecting a motion-blurred frame.
    """

    image = cv2.imread(str(frame_path))

    if image is None:
        return 0.0

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    gray = cv2.resize(
        gray,
        (640, 360),
        interpolation=cv2.INTER_AREA,
    )

    return float(
        cv2.Laplacian(
            gray,
            cv2.CV_64F,
        ).var()
    )


# ---------------------------------------------------------
# Timestamp
# ---------------------------------------------------------

def _frame_timestamp(
    frame_path: Path,
    fps: float,
):
    frame_number = int(
        frame_path.stem.split("_")[1]
    )

    return round(
        (frame_number - 1) / fps,
        2,
    )


# ---------------------------------------------------------
# Select best views
# ---------------------------------------------------------

def _select_best_views(
    frame_files,
    max_views=2,
    min_view_gain=0.04,
):
    """
    Select the best representation of one logical slide.

    The selection is coverage-aware:

    1. Pick the strongest single frame using visible slide area
       plus image sharpness.
    2. Look for a second frame that reveals NEW slide regions
       hidden in the first frame.
    3. Do not require the second frame to have nearly the same
       visibility as the first frame. A lower-visibility frame
       can still be valuable if it exposes a different part
       of the slide.
    4. Keep only the second frame when its additional coverage
       is meaningful.

    This is intentionally presenter-agnostic. It does not assume
    that the teacher is on the left or right side of the screen.
    """

    if len(frame_files) == 1:
        return [
            {
                "frame": frame_files[0],
                "visibility": 1.0,
                "sharpness_normalized": 1.0,
                "mask": None,
            }
        ]

    reference_files = _sample_frames(
        frame_files,
        max_samples=10,
    )

    cache = {}
    candidates = []

    # ---------------------------------------------------------
    # Analyze every candidate frame
    # ---------------------------------------------------------

    for frame_file in frame_files:

        mask = _visibility_mask(
            frame_file,
            reference_files,
            cache,
            tolerance=12,
        )

        if mask is None:
            continue

        visibility = float(mask.mean())
        sharpness = _sharpness_score(frame_file)

        candidates.append(
            {
                "frame": frame_file,
                "visibility": visibility,
                "sharpness": sharpness,
                "mask": mask,
            }
        )

    if not candidates:
        return [
            {
                "frame": frame_files[0],
                "visibility": 1.0,
                "sharpness_normalized": 1.0,
                "mask": None,
            }
        ]

    # ---------------------------------------------------------
    # Normalize sharpness
    # ---------------------------------------------------------

    sharpness_values = np.array(
        [
            candidate["sharpness"]
            for candidate in candidates
        ],
        dtype=float,
    )

    minimum = sharpness_values.min()
    maximum = sharpness_values.max()

    if maximum > minimum:

        for candidate in candidates:
            candidate["sharpness_normalized"] = (
                candidate["sharpness"] - minimum
            ) / (
                maximum - minimum
            )

    else:

        for candidate in candidates:
            candidate["sharpness_normalized"] = 1.0

    # ---------------------------------------------------------
    # First view: strongest individual frame
    # ---------------------------------------------------------
    #
    # Visibility is still the main signal, but sharpness helps
    # avoid choosing a motion-blurred frame when two frames have
    # similar coverage.
    # ---------------------------------------------------------

    for candidate in candidates:

        candidate["score"] = (
            0.85 * candidate["visibility"]
            + 0.15 * candidate["sharpness_normalized"]
        )

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    best = candidates[0]
    selected = [best]

    # ---------------------------------------------------------
    # Second view: maximize NEW coverage
    # ---------------------------------------------------------
    #
    # This is the important change.
    #
    # We do NOT simply choose the second-highest visibility frame.
    # We search for the frame that contributes the largest amount
    # of previously uncovered slide area.
    #
    # Example:
    #
    #   Frame A -> 90% visible, mostly left side
    #   Frame B -> 88% visible, also mostly left side
    #   Frame C -> 70% visible, mostly right side
    #
    # The correct pair is A + C because C contributes much more
    # new information.
    # ---------------------------------------------------------

    if max_views >= 2 and len(candidates) > 1:

        covered = best["mask"].copy()
        best_gain = 0.0
        second = None

        for candidate in candidates[1:]:

            candidate_mask = candidate["mask"]

            # Regions visible in this candidate but NOT already
            # visible in the primary frame.
            new_regions = (
                candidate_mask
                & ~covered
            )

            gain = float(new_regions.mean())

            # A candidate must contribute meaningful new coverage.
            if gain < min_view_gain:
                continue

            # Avoid selecting an extremely poor / mostly obstructed
            # frame unless it genuinely adds substantial coverage.
            #
            # This is deliberately a soft quality guard rather than
            # the old "75% of best visibility" rule.
            quality_floor = max(
                0.30,
                best["visibility"] * 0.45,
            )

            if candidate["visibility"] < quality_floor:
                continue

            # Prefer candidates that add more coverage, while using
            # sharpness as a small tie-breaker.
            candidate["gain_score"] = (
                0.85 * gain
                + 0.15 * candidate["sharpness_normalized"]
            )

            if candidate["gain_score"] > best_gain:
                best_gain = candidate["gain_score"]
                second = candidate

        if second is not None:
            selected.append(second)

    return selected


# ---------------------------------------------------------
# MAIN SLIDE DETECTOR
# ---------------------------------------------------------

def detect_slides(
    frames_dir: str,
    slides_dir: str,
    fps: float = 1.0,

    # Main logical-slide threshold
    # changed it so that it is more sensitive to slide changes
    change_threshold: float = 0.70,

    # Number of alternate views
    max_views: int = 2,

    # How much additional area second view
    # must reveal
    min_view_gain: float = 0.04,
):
    frames_path = Path(frames_dir)
    slides_path = Path(slides_dir)

    if not frames_path.exists():
        raise FileNotFoundError(
            f"Frames directory not found: {frames_path}"
        )

    slides_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame_files = sorted(
        frames_path.glob("frame_*.jpg")
    )

    if not frame_files:
        raise FileNotFoundError(
            "No extracted frames found."
        )

    # -----------------------------------------------------
    # Remove old detector output
    # -----------------------------------------------------

    for old_file in slides_path.glob(
        "slide_*.jpg"
    ):
        old_file.unlink()

    # -----------------------------------------------------
    # GROUP FRAMES INTO LOGICAL SLIDES
    # -----------------------------------------------------

    groups = []

    current_group = [
        frame_files[0]
    ]

    previous_frame = frame_files[0]

    # At 2 FPS, 6 frames represent approximately 3 seconds.
    # We use multiple historical frames so that temporary
    # presenter movement does not look like a slide change.
    lookback_offsets = [2, 4, 6]

    for index in range(
        1,
        len(frame_files),
    ):

        current_frame = frame_files[index]

        # -------------------------------------------------
        # Compare with immediately previous frame
        # -------------------------------------------------

        similarity_previous = _frame_similarity(
            previous_frame,
            current_frame,
        )

        # -------------------------------------------------
        # Compare with several older frames
        # -------------------------------------------------

        historical_similarities = []

        for offset in lookback_offsets:

            if index >= offset:

                historical_frame = frame_files[index - offset]

                similarity = _frame_similarity(
                    historical_frame,
                    current_frame,
                )

                historical_similarities.append(
                    similarity
                )

        # -------------------------------------------------
        # Detect persistent visual change
        # -------------------------------------------------

        low_similarity_count = sum(
            similarity < change_threshold
            for similarity in historical_similarities
        )

        # A slide change should differ from the immediately
        # previous frame AND from most of the recent history.
        #
        # This makes the detector less sensitive to temporary
        # presenter movement or occlusion.

        actual_slide_change = (
            similarity_previous < change_threshold
            and
            low_similarity_count >= 2
        )

        if actual_slide_change:

            groups.append(
                current_group
            )

            current_group = []

        current_group.append(
            current_frame
        )

        previous_frame = current_frame

    if current_group:
        groups.append(
            current_group
        )

    # -----------------------------------------------------
    # CREATE BEST REPRESENTATION OF EACH GROUP
    # -----------------------------------------------------

    slides = []

    for slide_number, group in enumerate(
        groups,
        start=1,
    ):

        selected_views = _select_best_views(
            group,
            max_views=max_views,
            min_view_gain=min_view_gain,
        )

        view_paths = []

        for view_index, selected in enumerate(
            selected_views,
            start=1,
        ):

            source_frame = selected["frame"]

            image = cv2.imread(
                str(source_frame)
            )

            if image is None:
                continue

            if view_index == 1:

                output_name = (
                    f"slide_{slide_number:03d}.jpg"
                )

            else:

                output_name = (
                    f"slide_{slide_number:03d}"
                    f"_view{view_index}.jpg"
                )

            output_path = (
                slides_path / output_name
            )

            cv2.imwrite(
                str(output_path),
                image,
            )

            view_paths.append(
                {
                    "image_path": str(
                        output_path
                    ),
                    "frame": source_frame.name,
                    "timestamp": _frame_timestamp(
                        source_frame,
                        fps,
                    ),
                    "visibility": round(
                        selected["visibility"],
                        4,
                    ),
                }
            )

        if not view_paths:
            continue

        # First view is the primary representation.

        primary = view_paths[0]

        slides.append(
            {
                "slide_number": slide_number,
                "image_path": primary[
                    "image_path"
                ],
                "frame": primary["frame"],
                "timestamp": primary[
                    "timestamp"
                ],
                "views": view_paths,
            }
        )

    return slides