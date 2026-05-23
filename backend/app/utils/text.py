import re

import ftfy


_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = ftfy.fix_text(s)
    s = s.replace("\x00", "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _WS.sub(" ", s)
    s = _BLANKS.sub("\n\n", s)
    return s.strip()


def word_count(s: str) -> int:
    if not s:
        return 0
    return len(s.split())
