from app.services.stimulus_service import _slugify_filename


def test_slugify_filename_strips_extension_and_normalizes():
    assert _slugify_filename("Launch Screen.png") == "launch_screen"


def test_slugify_filename_collapses_punctuation_and_repeated_separators():
    assert _slugify_filename("Create with email (unfilled)-1.png") == "create_with_email_unfilled_1"


def test_slugify_filename_handles_missing_or_empty_filename():
    assert _slugify_filename(None) is None
    assert _slugify_filename("") is None
    assert _slugify_filename(".png") is None
