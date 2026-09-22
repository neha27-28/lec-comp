from services.slide_detector import detect_slides


frames_dir = "data/frames/c2d1d098"

slides_dir = "data/slides/c2d1d098"


slides = detect_slides(

    frames_dir=frames_dir,

    slides_dir=slides_dir,

    fps=1.0,

    change_threshold=0.62,

    max_views=2,

    min_view_gain=0.04,

)


print("\nSlide detection completed!")

print(
    f"Logical slides detected: {len(slides)}"
)


for slide in slides:

    print(
        f"\nSlide {slide['slide_number']}: "
        f"{slide['image_path']}"
    )

    print(
        f"  Timestamp: "
        f"{slide['timestamp']}s"
    )

    print(
        f"  Number of views: "
        f"{len(slide['views'])}"
    )

    for view in slide["views"]:

        print(
            f"    View: {view['image_path']} "
            f"| timestamp={view['timestamp']}s "
            f"| visibility={view['visibility']}"
        )