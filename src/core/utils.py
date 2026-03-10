"""
core/utils.py - Name matching and similarity utilities for ReAnimate Tool.
Used for automatic joint mapping between source and target rigs.
"""

import re
from difflib import SequenceMatcher

SIDE_PATTERNS = {
    "L": ["^l_", "_l$", "left", "lf"],
    "R": ["^r_", "_r$", "right", "rt"]
}


def normalize_name(name: str) -> str:
    """Strip namespaces and return a lowercase name for comparison."""
    return name.split(":")[-1].lower()


def detect_side(name: str):
    """
    Detect left/right side from a joint name.

    Returns:
        tuple: (cleaned name, side str 'L'/'R' or None)
    """
    clean = name.split("|")[-1].split(":")[-1].lower()
    for side, patterns in SIDE_PATTERNS.items():
        for p in patterns:
            if re.search(p, clean):
                return clean, side
    return clean, None


def similarity(a: str, b: str) -> float:
    """Return a 0–1 similarity score between two joint names."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def get_best_match(source_name: str, target_list: list):
    """
    Find the best matching target joint for a given source joint name.

    Scores are based on string similarity with side-matching bonuses/penalties.

    Args:
        source_name (str): Source joint name.
        target_list (list): List of candidate target joint names.

    Returns:
        tuple: (best matching target name, score float)
    """
    src_clean, src_side = detect_side(source_name)
    best_score, best_target = -999.0, ""

    for tgt in target_list:
        tgt_clean, tgt_side = detect_side(tgt)
        score = similarity(src_clean, tgt_clean)
        if src_side and tgt_side:
            score += 0.25 if src_side == tgt_side else -0.50
        if score > best_score:
            best_score, best_target = score, tgt

    return best_target, best_score