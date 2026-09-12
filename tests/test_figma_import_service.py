import pytest

from app.services.figma_import_service import FigmaImportError, FigmaImportService

service = FigmaImportService()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.figma.com/file/abc123XYZ/My-Prototype?node-id=1-2",
        "https://www.figma.com/design/abc123XYZ/My-Prototype",
        "https://www.figma.com/proto/abc123XYZ/My-Prototype?starting-point-node-id=1%3A2",
    ],
)
def test_extract_file_key_handles_every_url_shape(url):
    assert FigmaImportService.extract_file_key(url) == "abc123XYZ"


def test_extract_file_key_rejects_a_non_figma_url():
    with pytest.raises(FigmaImportError):
        FigmaImportService.extract_file_key("https://example.com/not-figma")


def _document() -> dict:
    return {
        "document": {
            "children": [
                {
                    "type": "CANVAS",
                    "id": "0:1",
                    "name": "Page 1",
                    "children": [
                        {
                            "type": "FRAME",
                            "id": "1:1",
                            "name": "Home",
                            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 390, "height": 844},
                            "children": [
                                {
                                    "type": "INSTANCE",
                                    "id": "1:2",
                                    "name": "CTA Button",
                                    "absoluteBoundingBox": {
                                        "x": 20,
                                        "y": 720,
                                        "width": 350,
                                        "height": 56,
                                    },
                                    "transitionNodeID": "2:1",
                                },
                                {
                                    "type": "TEXT",
                                    "id": "1:3",
                                    "name": "Title",
                                    "characters": "Welcome",
                                    "absoluteBoundingBox": {
                                        "x": 20,
                                        "y": 100,
                                        "width": 300,
                                        "height": 40,
                                    },
                                },
                                {
                                    "type": "TEXT",
                                    "id": "1:4",
                                    "name": "Hidden helper text",
                                    "visible": False,
                                    "absoluteBoundingBox": {
                                        "x": 0,
                                        "y": 0,
                                        "width": 1,
                                        "height": 1,
                                    },
                                },
                            ],
                        },
                        {
                            "type": "SECTION",
                            "id": "3:0",
                            "name": "Confirmation flow",
                            "children": [
                                {
                                    "type": "FRAME",
                                    "id": "2:1",
                                    "name": "Confirm",
                                    "absoluteBoundingBox": {
                                        "x": 500,
                                        "y": 0,
                                        "width": 390,
                                        "height": 844,
                                    },
                                    "children": [
                                        {
                                            "type": "TEXT",
                                            "id": "2:2",
                                            "name": "Success message",
                                            "characters": "Added to cart",
                                            "absoluteBoundingBox": {
                                                "x": 520,
                                                "y": 40,
                                                "width": 300,
                                                "height": 30,
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ]
        }
    }


def test_parse_document_finds_every_screen_including_ones_nested_in_a_section():
    result = service.parse_document(_document())

    screen_ids = {screen.node_id for screen in result.screens}
    assert screen_ids == {"1:1", "2:1"}


def test_parse_document_skips_invisible_nodes():
    result = service.parse_document(_document())
    home = next(s for s in result.screens if s.node_id == "1:1")

    element_ids = {e.node_id for e in home.elements}
    assert "1:4" not in element_ids


def test_parse_document_detects_the_transition_hotspot():
    result = service.parse_document(_document())
    home = next(s for s in result.screens if s.node_id == "1:1")
    cta = next(e for e in home.elements if e.node_id == "1:2")

    assert cta.transition_to_node_id == "2:1"
    assert cta.interactable is True
    assert cta.semantic_role == "primary_action"


def test_parse_document_leaves_plain_text_non_interactive_and_roleless():
    result = service.parse_document(_document())
    home = next(s for s in result.screens if s.node_id == "1:1")
    title = next(e for e in home.elements if e.node_id == "1:3")

    assert title.text == "Welcome"
    assert title.interactable is False
    assert title.semantic_role is None


def test_bbox_is_relative_to_the_enclosing_screens_own_origin_not_absolute():
    result = service.parse_document(_document())
    confirm = next(s for s in result.screens if s.node_id == "2:1")
    message = next(e for e in confirm.elements if e.node_id == "2:2")

    # Confirm's own origin is (500, 0); the message's absolute box is
    # (520, 40, 300x30) -> relative to the screen it should be (20, 40, 320, 70).
    assert message.bbox == [20, 40, 320, 70]


def test_screen_dimensions_come_from_its_own_bounding_box():
    result = service.parse_document(_document())
    home = next(s for s in result.screens if s.node_id == "1:1")

    assert (home.width, home.height) == (390, 844)
