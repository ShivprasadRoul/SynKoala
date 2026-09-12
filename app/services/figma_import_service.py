"""Fetches and parses a Figma prototype's document tree into the Stimulus
Engine's shapes (planning/05-stimulus-engine.md). Unlike `VisionProvider`
(`app/agents/providers/vision_provider.py`), this needs no model call at all —
Figma's REST API already returns ground-truth element bounding boxes/types/text,
and real navigation edges (`transitionNodeID`), for a file the connected
account can view. `semantic_role`/`interactable` are the one thing Figma
doesn't give directly; both are a best-effort heuristic here, same "not
free data" caveat noted when the VisionProvider path was built.

Owns Figma's file/image REST endpoints (its own external call, separate from
`FigmaOAuthService`, which owns Figma's *token* endpoints — different part of
Figma's API, same "a Service may make its own external calls" allowance as
`StimulusService` calling Supabase Storage).
"""

import asyncio
import re
from dataclasses import dataclass, field

import httpx

FIGMA_API_BASE = "https://api.figma.com/v1"
FIGMA_MAX_RETRIES = 5
FIGMA_RATE_LIMIT_HARD_CUTOFF_SECONDS = 60
FIGMA_IMAGE_BATCH_SIZE = 50

# Frames, component instances, and components are the "screens" a prototype
# navigates between; SECTION nodes are a pure organizational wrapper in
# Figma's UI and get flattened rather than treated as a screen themselves.
_SCREEN_NODE_TYPES = {"FRAME", "INSTANCE", "COMPONENT"}

_INTERACTIVE_NODE_TYPES = {"INSTANCE", "COMPONENT"}
_INTERACTIVE_NAME_KEYWORDS = (
    "button",
    "btn",
    "cta",
    "link",
    "input",
    "field",
    "tab",
    "toggle",
    "checkbox",
    "radio",
    "menu",
    "nav",
)

# Best-effort layer-name/text heuristic — Figma has no semantic_role concept,
# so this is deliberately approximate, same as the VisionProvider's prompt-
# driven guess for screenshot-sourced stimuli. First match wins.
_ROLE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "primary_action",
        ("cta", "buy", "add to cart", "checkout", "submit", "continue", "confirm", "primary"),
    ),
    ("search", ("search",)),
    ("navigation", ("nav", "menu", "tab bar", "back")),
    ("help", ("help", "info", "faq", "support")),
    ("confirmation", ("success", "confirmation", "thank you", "done")),
]

_FILE_KEY_PATTERN = re.compile(r"figma\.com/(?:file|design|proto)/([a-zA-Z0-9]+)/")


class FigmaImportError(Exception):
    pass


class FigmaRateLimitError(FigmaImportError):
    pass


@dataclass
class ParsedElement:
    node_id: str
    name: str
    type: str
    text: str | None
    bbox: list[int]  # [x1, y1, x2, y2], relative to the enclosing screen's own origin
    interactable: bool
    semantic_role: str | None
    transition_to_node_id: str | None  # set only if this node itself is a hotspot


@dataclass
class ParsedScreen:
    node_id: str
    name: str
    width: int
    height: int
    elements: list[ParsedElement] = field(default_factory=list)


@dataclass
class ParsedDocument:
    screens: list[ParsedScreen] = field(default_factory=list)


def _infer_interactable(node: dict) -> bool:
    if node.get("transitionNodeID"):
        return True
    if node.get("type") in _INTERACTIVE_NODE_TYPES:
        return True
    name = (node.get("name") or "").lower()
    return any(keyword in name for keyword in _INTERACTIVE_NAME_KEYWORDS)


def _infer_semantic_role(node: dict) -> str | None:
    haystack = f"{node.get('name', '')} {node.get('characters', '')}".lower()
    for role, keywords in _ROLE_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return role
    return None


def _bbox_relative_to(node: dict, origin_x: float, origin_y: float) -> list[int]:
    box = node.get("absoluteBoundingBox") or {"x": origin_x, "y": origin_y, "width": 0, "height": 0}
    x, y = box.get("x", origin_x), box.get("y", origin_y)
    return [
        round(x - origin_x),
        round(y - origin_y),
        round(x - origin_x + box.get("width", 0)),
        round(y - origin_y + box.get("height", 0)),
    ]


class FigmaImportService:
    @staticmethod
    def extract_file_key(prototype_url: str) -> str:
        match = _FILE_KEY_PATTERN.search(prototype_url)
        if not match:
            raise FigmaImportError(f"Could not find a Figma file key in {prototype_url!r}")
        return match.group(1)

    async def _get(self, access_token: str, path: str, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(FIGMA_MAX_RETRIES):
                response = await client.get(
                    f"{FIGMA_API_BASE}{path}", headers=headers, params=params
                )
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 10))
                    if retry_after > FIGMA_RATE_LIMIT_HARD_CUTOFF_SECONDS:
                        raise FigmaRateLimitError("Figma rate limit exceeded the retry budget")
                    await asyncio.sleep(retry_after)
                    continue
                if response.status_code >= 500:
                    await asyncio.sleep(2**attempt)
                    continue
                raise FigmaImportError(
                    f"Figma API error {response.status_code} for {path}: {response.text}"
                )
        raise FigmaImportError(f"Figma API retries exhausted for {path}")

    async def fetch_document(self, access_token: str, file_key: str) -> dict:
        """No `depth` param — fetches the whole tree. Figma's `depth` param
        would truncate nodes organized inside a `SECTION` (a common pattern in
        larger files), which would need a second `/files/:key/nodes` fetch to
        re-expand; skipping `depth` entirely avoids that complexity at the
        cost of a bigger payload for very large files, an acceptable
        trade-off at this product's MVP scale (PRD §7: 50-100 participants,
        not enterprise-scale design systems)."""
        return await self._get(access_token, f"/files/{file_key}", {})

    async def fetch_image_urls(
        self, access_token: str, file_key: str, node_ids: list[str]
    ) -> dict[str, str]:
        images: dict[str, str] = {}
        for i in range(0, len(node_ids), FIGMA_IMAGE_BATCH_SIZE):
            batch = node_ids[i : i + FIGMA_IMAGE_BATCH_SIZE]
            result = await self._get(access_token, f"/images/{file_key}", {"ids": ",".join(batch)})
            images.update(result.get("images") or {})
        return images

    def parse_document(self, document: dict) -> ParsedDocument:
        pages = document.get("document", {}).get("children", [])
        screens: list[ParsedScreen] = []
        for page in pages:
            if page.get("type") != "CANVAS":
                continue
            screens.extend(self._collect_screens(page.get("children", [])))
        return ParsedDocument(screens=screens)

    def _collect_screens(self, nodes: list[dict]) -> list[ParsedScreen]:
        screens = []
        for node in nodes:
            if node.get("visible", True) is False:
                continue
            if node.get("type") == "SECTION":
                screens.extend(self._collect_screens(node.get("children", [])))
            elif node.get("type") in _SCREEN_NODE_TYPES:
                screens.append(self._build_screen(node))
        return screens

    def _build_screen(self, node: dict) -> ParsedScreen:
        box = node.get("absoluteBoundingBox") or {"x": 0, "y": 0, "width": 0, "height": 0}
        origin_x, origin_y = box.get("x", 0), box.get("y", 0)
        return ParsedScreen(
            node_id=node["id"],
            name=node.get("name") or node["id"],
            width=round(box.get("width", 0)),
            height=round(box.get("height", 0)),
            elements=self._collect_elements(node.get("children", []), origin_x, origin_y),
        )

    def _collect_elements(
        self, nodes: list[dict], origin_x: float, origin_y: float
    ) -> list[ParsedElement]:
        elements = []
        for node in nodes:
            if node.get("visible", True) is False:
                continue
            elements.append(
                ParsedElement(
                    node_id=node["id"],
                    name=node.get("name") or node["id"],
                    type=node.get("type", "UNKNOWN"),
                    text=node.get("characters"),
                    bbox=_bbox_relative_to(node, origin_x, origin_y),
                    interactable=_infer_interactable(node),
                    semantic_role=_infer_semantic_role(node),
                    transition_to_node_id=node.get("transitionNodeID"),
                )
            )
            elements.extend(self._collect_elements(node.get("children", []), origin_x, origin_y))
        return elements
