#!/usr/bin/env python3
"""Flesch–Kincaid grade for the visible layer of a page.

Formula (Kincaid, Fishburne, Rogers & Chissom, 1975, Naval Technical
Training Command Research Branch Report R-8-75), as commonly stated:

    grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59

Syllables are counted with a documented vowel-group approximation
(consecutive vowels = one syllable; a final silent 'e' is dropped
when the word has another syllable; at least one syllable per word).
This is an approximation, not a dictionary count.

The visible layer is the page text after removing <script>, <style>,
and every <details> block (Sources, and any other closed-or-open
details, including nested ones). Tags are then stripped.
"""
from __future__ import annotations

import re
from pathlib import Path

VOWELS = set("aeiouy")


def count_syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    if not w:
        return 0
    count = 0
    prev = False
    for ch in w:
        is_v = ch in VOWELS
        if is_v and not prev:
            count += 1
        prev = is_v
    if w.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?]+", text)
    return [p.strip() for p in parts if re.search(r"[A-Za-z]", p or "")]


def words_of(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", text or "")


def flesch_kincaid(text: str) -> dict:
    words = words_of(text)
    sents = split_sentences(text)
    n_w, n_s = len(words), len(sents)
    n_y = sum(count_syllables(w) for w in words)
    if n_w == 0 or n_s == 0:
        return {
            "grade": None,
            "words": n_w,
            "sentences": n_s,
            "syllables": n_y,
            "words_per_sentence": None,
            "syllables_per_word": None,
        }
    wps = n_w / n_s
    spw = n_y / n_w
    grade = 0.39 * wps + 11.8 * spw - 15.59
    return {
        "grade": round(grade, 2),
        "words": n_w,
        "sentences": n_s,
        "syllables": n_y,
        "words_per_sentence": round(wps, 2),
        "syllables_per_word": round(spw, 2),
    }


def _strip_details(html: str) -> str:
    """Remove <details>…</details> blocks, innermost first."""
    pat = re.compile(
        r"<details\b[^>]*>(?:(?!<details\b).)*?</details>",
        flags=re.I | re.S,
    )
    prev = None
    while prev != html:
        prev = html
        html = pat.sub("", html)
    return html


def visible_text(html: str, *, also_drop_selectors: bool = False) -> str:
    text = html
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = _strip_details(text)
    if also_drop_selectors:
        # Optional: legal chrome, for a secondary score.
        text = re.sub(r'<div class="notice"[^>]*>.*?</div>', " ", text, flags=re.I | re.S)
        text = re.sub(r"<footer\b[^>]*>.*?</footer>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<nav\b[^>]*>.*?</nav>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<header\b[^>]*>.*?</header>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#?\w+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def score_file(path: Path, body_only: bool = False) -> dict:
    html = path.read_text(encoding="utf-8")
    text = visible_text(html, also_drop_selectors=body_only)
    result = flesch_kincaid(text)
    result["path"] = str(path)
    result["body_only"] = body_only
    return result
