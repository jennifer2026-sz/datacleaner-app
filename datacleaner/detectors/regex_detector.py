"""Regex-based PII detector — fast first pass."""

from datacleaner.detectors.patterns import get_all_patterns


def detect_pii_regex(text: str) -> list[dict]:
    """Run all regex patterns against text.

    Returns list of: {"category": str, "type": str, "match": str, "start": int, "end": int}
    """
    patterns = get_all_patterns()
    detections = []

    for name, pattern in patterns.items():
        category, ptype = name.split("/", 1)
        for match in pattern.finditer(text):
            detections.append({
                "category": category,
                "type": ptype,
                "match": match.group(),
                "start": match.start(),
                "end": match.end(),
                "method": "regex",
            })

    # Sort by position
    detections.sort(key=lambda d: d["start"])
    return detections


def get_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Check if two spans overlap."""
    return max(a_start, b_start) < min(a_end, b_end)
