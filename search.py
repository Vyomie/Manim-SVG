"""Fuzzy search engine for SVG assets using meta.json descriptions."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Lightweight fuzzy helpers (no external dependency required)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Lowercase and split text into alphanumeric tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _ngrams(text: str, n: int = 3) -> set:
    """Return character-level n-grams for a string."""
    s = text.lower()
    return {s[i : i + n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}


def _trigram_similarity(a: str, b: str) -> float:
    """Sørensen–Dice coefficient on character trigrams."""
    sa, sb = _ngrams(a, 3), _ngrams(b, 3)
    if not sa or not sb:
        return 0.0
    return 2 * len(sa & sb) / (len(sa) + len(sb))


def _token_set_score(query_tokens: List[str], target_tokens: List[str]) -> float:
    """Score based on how many query tokens appear (exactly or fuzzily) in target."""
    if not query_tokens:
        return 0.0
    hits = 0.0
    for qt in query_tokens:
        best = 0.0
        for tt in target_tokens:
            if qt == tt:
                best = 1.0
                break
            if qt in tt or tt in qt:
                best = max(best, 0.85)
            else:
                best = max(best, _trigram_similarity(qt, tt))
        hits += best
    return hits / len(query_tokens)


# ---------------------------------------------------------------------------
# Search index
# ---------------------------------------------------------------------------

@dataclass
class _Entry:
    filename: str
    description: str
    name_tokens: List[str] = field(default_factory=list)
    desc_tokens: List[str] = field(default_factory=list)


class SVGIndex:
    """In-memory search index built from a meta.json file."""

    def __init__(self, meta_path: str | Path):
        meta_path = Path(meta_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            raw: dict = json.load(f)

        self.assets_dir = meta_path.parent
        self.entries: List[_Entry] = []

        for filename, info in raw.items():
            if info.get("status") != "success":
                continue
            desc = info.get("description", "")
            # derive a readable name from the filename (strip id suffix & extension)
            name_part = re.sub(r"_\d+\.svg$", "", filename).replace("-", " ").replace("_", " ")
            entry = _Entry(
                filename=filename,
                description=desc,
                name_tokens=_tokenize(name_part),
                desc_tokens=_tokenize(desc),
            )
            self.entries.append(entry)

    # ---- public API --------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Return the *top_k* best matches for *query*.

        Each result is a dict with keys:
            filename, description, score, path
        """
        q_tokens = _tokenize(query)
        scored = []
        for entry in self.entries:
            # Name match is weighted higher (× 2) because it's the concise label
            name_score = _token_set_score(q_tokens, entry.name_tokens)
            desc_score = _token_set_score(q_tokens, entry.desc_tokens)
            combined = 0.55 * name_score + 0.45 * desc_score
            scored.append((combined, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, entry in scored[:top_k]:
            results.append(
                {
                    "filename": entry.filename,
                    "description": entry.description,
                    "score": round(score, 4),
                    "path": str(self.assets_dir / entry.filename),
                }
            )
        return results

    def best_match(self, query: str) -> Optional[dict]:
        """Return the single best match, or *None* if the index is empty."""
        results = self.search(query, top_k=1)
        return results[0] if results else None
