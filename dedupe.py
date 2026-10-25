import json
import re
from pathlib import Path
from typing import Iterable


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _word_overlap(a: str, b: str) -> float:
    a_tokens = _normalize_text(a).split()
    b_tokens = _normalize_text(b).split()
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(set(a_tokens) & set(b_tokens))
    return overlap / max(len(set(a_tokens)), len(set(b_tokens)))


def is_duplicate(new_text: str, existing_text: str) -> bool:
    if not new_text or not existing_text:
        return False
    new_norm = _normalize_text(new_text)
    existing_norm = _normalize_text(existing_text)
    if not new_norm or not existing_norm:
        return False
    if new_norm == existing_norm:
        return True
    if _word_overlap(new_text, existing_text) > 0.8:
        return True
    return False


def load_used_content(output_root: Path | str) -> set[str]:
    output_root = Path(output_root)
    used: set[str] = set()
    if not output_root.exists():
        return used

    for captions_file in sorted(output_root.glob("*/captions.json")):
        try:
            payload = json.loads(captions_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        for item in payload.get("cards", []):
            for key in ("line", "body"):
                value = item.get(key)
                if value:
                    used.add(_normalize_text(value))
        # Also remember engagement prompts and reel lines so nothing repeats.
        for item in payload.get("engagement", []):
            value = item.get("prompt")
            if value:
                used.add(_normalize_text(value))
        for item in payload.get("video_reels", []):
            value = item.get("line")
            if value:
                used.add(_normalize_text(value))
        for item in payload.get("reflections", []):
            value = item.get("essay")
            if value:
                used.add(_normalize_text(value))
    return used


def _is_duplicate_any(text: str, used_content: set[str]) -> bool:
    if not text:
        return False
    for existing in used_content:
        if text == existing or is_duplicate(text, existing):
            return True
    return False


def ensure_unique_items(items: Iterable[dict], used_content: set[str], key: str, generator_func, *, attempts: int = 8):
    unique_items = []
    for item in items:
        candidate = item.get(key, "")
        candidate_norm = _normalize_text(candidate)
        if candidate and _is_duplicate_any(candidate_norm, used_content):
            print(f"  duplicate detected for {key}; requesting replacement")
            for attempt in range(attempts):
                replacement = generator_func()
                replacement_value = replacement.get(key, "") if isinstance(replacement, dict) else ""
                replacement_norm = _normalize_text(replacement_value)
                if replacement_value and not _is_duplicate_any(replacement_norm, used_content):
                    item = replacement
                    candidate = replacement_value
                    candidate_norm = replacement_norm
                    print(f"    replacement found after {attempt + 1} attempt(s)")
                    break
            else:
                raise RuntimeError(f"Unable to generate a unique {key} after {attempts} attempts")
        if candidate:
            used_content.add(candidate_norm)
        unique_items.append(item)
    return unique_items
