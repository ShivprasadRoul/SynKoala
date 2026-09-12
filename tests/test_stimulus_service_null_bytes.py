from app.services.stimulus_service import _strip_null_bytes


def test_strip_null_bytes_from_a_plain_string():
    assert _strip_null_bytes("back\x00button") == "backbutton"


def test_strip_null_bytes_recurses_into_dicts_and_lists():
    value = {
        "elements": [
            {"id": "back_button", "text": "\x00", "bbox": [1, 2, 3, 4]},
            {"id": "cta", "text": "Continue", "bbox": [1, 2, 3, 4]},
        ]
    }
    cleaned = _strip_null_bytes(value)
    assert cleaned["elements"][0]["text"] == ""
    assert cleaned["elements"][1]["text"] == "Continue"
    assert cleaned["elements"][0]["bbox"] == [1, 2, 3, 4]  # non-strings pass through untouched


def test_strip_null_bytes_leaves_clean_values_unchanged():
    assert _strip_null_bytes("Continue") == "Continue"
    assert _strip_null_bytes(None) is None
    assert _strip_null_bytes(True) is True
