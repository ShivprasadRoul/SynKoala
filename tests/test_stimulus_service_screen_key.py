from app.services.stimulus_service import _slugify_filename


def test_slugify_filename_strips_extension_and_normalizes():
    assert _slugify_filename("Launch Screen.png") == "launch_screen"


def test_slugify_filename_collapses_punctuation_and_repeated_separators():
    assert _slugify_filename("Create with email (unfilled)-1.png") == "create_with_email_unfilled_1"


def test_slugify_filename_handles_missing_or_empty_filename():
    assert _slugify_filename(None) is None
    assert _slugify_filename("") is None
    assert _slugify_filename(".png") is None


# --- real image dimensions captured at upload (fixes a real coordinate bug:
# get_pixel_heatmap/the results UI both used to fall back to a guessed
# 390x844 whenever width/height were null, silently misplacing every
# coordinate on a screenshot of any other size) ---


def test_image_dimensions_reads_a_real_png():
    import io

    from PIL import Image

    from app.services.stimulus_service import _image_dimensions

    buf = io.BytesIO()
    Image.new("RGB", (750, 1334)).save(buf, format="PNG")

    assert _image_dimensions(buf.getvalue()) == (750, 1334)


def test_image_dimensions_returns_none_for_unreadable_bytes():
    from app.services.stimulus_service import _image_dimensions

    assert _image_dimensions(b"not an image") is None
