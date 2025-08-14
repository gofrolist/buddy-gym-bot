"""
Regex patterns for parsing workout tracking commands.
"""

import re

# Matches: <exercise> <weight>x<reps> [rpeX], e.g. "bench 100x5 rpe8"
TRACK_RE = re.compile(
    r"^(?P<ex>.+?)\s+(?P<w>\d+(?:\.\d+)?)x(?P<r>\d+)(?:\s*rpe(?P<rpe>\d+(?:\.\d+)?))?$",
    re.IGNORECASE,
)
