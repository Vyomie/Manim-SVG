"""
manim_svg – query-based SVG asset loader for Manim
===================================================

Usage
-----
    from manim import *
    from manim_svg import ManimSVG

    class MyScene(Scene):
        def construct(self):
            car = ManimSVG("red car facing right")
            self.play(FadeIn(car))

The function performs a fuzzy search over the bundled SVG asset
catalogue (``meta.json``) and returns the closest match as a
``SVGMobject`` ready for use in any Manim scene.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from .search import SVGIndex

# ---------------------------------------------------------------------------
# Resolve the default assets directory (next to this file)
# ---------------------------------------------------------------------------
_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_ASSETS_DIR = _PACKAGE_DIR / "assets"
_DEFAULT_META = _DEFAULT_ASSETS_DIR / "meta.json"

# Allow overriding via environment variable
_CUSTOM_ASSETS = os.environ.get("MANIM_SVG_ASSETS")
if _CUSTOM_ASSETS:
    _META_PATH = Path(_CUSTOM_ASSETS) / "meta.json"
else:
    _META_PATH = _DEFAULT_META

# Lazy-loaded singleton index
_index: Optional[SVGIndex] = None


def _get_index() -> SVGIndex:
    global _index
    if _index is None:
        if not _META_PATH.exists():
            raise FileNotFoundError(
                f"meta.json not found at {_META_PATH}.\n"
                "Place meta.json and your SVG files inside the package's "
                "'assets/' folder, or set the MANIM_SVG_ASSETS environment "
                "variable to a directory that contains both."
            )
        _index = SVGIndex(_META_PATH)
    return _index


def reload_index(meta_path: Optional[str] = None) -> None:
    """Force-reload the search index (useful after adding new SVGs).

    Parameters
    ----------
    meta_path : str, optional
        Path to a different ``meta.json``.  When *None* the default
        location is used.
    """
    global _index, _META_PATH
    if meta_path is not None:
        _META_PATH = Path(meta_path)
    _index = SVGIndex(_META_PATH)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ManimSVG(
    query: str,
    *,
    height: Optional[float] = 2.0,
    width: Optional[float] = None,
    color: Optional[str] = None,
    fill_color: Optional[str] = None,
    stroke_color: Optional[str] = None,
    stroke_width: Optional[float] = None,
    top_k: int = 1,
    verbose: bool = False,
    **kwargs,
):
    """Return an ``SVGMobject`` for the best match to *query*.

    Parameters
    ----------
    query : str
        Natural-language description such as ``"red car facing right"``.
    height : float, optional
        Target height of the mobject (default ``2.0``).
    width : float, optional
        Target width — if set, takes priority over *height*.
    color / fill_color / stroke_color / stroke_width :
        Passed through to ``SVGMobject`` / applied after creation.
    top_k : int
        How many candidates to search (only the best is returned as a
        mobject; set ``verbose=True`` to see all).
    verbose : bool
        Print the matched filename and score.
    **kwargs :
        Forwarded to ``SVGMobject.__init__``.

    Returns
    -------
    SVGMobject
    """
    # Import manim lazily so the search module can work standalone
    try:
        from manim import SVGMobject
    except ImportError:
        raise ImportError(
            "Manim is required to create SVGMobject instances.\n"
            "Install it with:  pip install manim"
        )

    index = _get_index()
    results = index.search(query, top_k=max(top_k, 1))

    if not results:
        raise ValueError("No SVG assets found — is meta.json empty?")

    best = results[0]

    if verbose:
        for r in results:
            print(f"  [{r['score']:.3f}]  {r['filename']}")

    svg_path = best["path"]
    if not Path(svg_path).exists():
        raise FileNotFoundError(
            f"SVG file not found: {svg_path}\n"
            f"(matched from query: '{query}' → {best['filename']})"
        )

    mob = SVGMobject(svg_path, **kwargs)

    # Sizing
    if width is not None:
        mob.width = width
    elif height is not None:
        mob.height = height

    # Optional styling
    if color is not None:
        mob.set_color(color)
    if fill_color is not None:
        mob.set_fill(fill_color)
    if stroke_color is not None:
        mob.set_stroke(color=stroke_color)
    if stroke_width is not None:
        mob.set_stroke(width=stroke_width)

    # Attach metadata for introspection
    mob.svg_query = query
    mob.svg_filename = best["filename"]
    mob.svg_score = best["score"]
    mob.svg_description = best["description"]

    return mob


def search_svg(query: str, top_k: int = 5) -> List[dict]:
    """Search the SVG catalogue without creating a Manim mobject.

    Useful for browsing available assets or debugging queries.

    Returns
    -------
    list[dict]
        Each dict has keys: ``filename``, ``description``, ``score``, ``path``.
    """
    return _get_index().search(query, top_k=top_k)


__all__ = ["ManimSVG", "search_svg", "reload_index"]
