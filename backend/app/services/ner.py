"""Named entity recognition: spaCy (transformer) + GLiNER for custom types.

Models are heavyweight to load (~1 GB total) so they live as module-level
singletons in the Celery worker process. The pattern is: import once,
load on first use, reuse forever within that process.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


# spaCy types we accept verbatim. Anything else from spaCy is dropped.
_SPACY_KEEP = {"PERSON", "ORG", "GPE", "DATE", "EVENT"}

# Map GLiNER lowercase labels (configured in settings) to canonical types.
_GLINER_TYPE_MAP = {
    "concept": "CONCEPT",
    "tool": "TOOL",
    "method": "METHOD",
    "metric": "METRIC",
}


@dataclass(frozen=True)
class ExtractedEntity:
    name: str
    type: str
    char_start: int
    char_end: int
    source: str  # "spacy" or "gliner"


# ---------------------------------------------------------------------------
# Lazy model loaders
# ---------------------------------------------------------------------------

_spacy_nlp = None
_gliner_model = None


def _load_spacy():
    global _spacy_nlp
    if _spacy_nlp is None:
        import spacy

        settings = get_settings()
        log.info("ner.spacy.loading", model=settings.spacy_model)
        _spacy_nlp = spacy.load(settings.spacy_model)
        log.info("ner.spacy.loaded")
    return _spacy_nlp


def _load_gliner():
    global _gliner_model
    if _gliner_model is None:
        from gliner import GLiNER

        settings = get_settings()
        log.info("ner.gliner.loading", model=settings.gliner_model)
        _gliner_model = GLiNER.from_pretrained(settings.gliner_model)
        log.info("ner.gliner.loaded")
    return _gliner_model


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _run_spacy(text: str) -> list[ExtractedEntity]:
    nlp = _load_spacy()
    doc = nlp(text)
    out: list[ExtractedEntity] = []
    for ent in doc.ents:
        if ent.label_ not in _SPACY_KEEP:
            continue
        name = (ent.text or "").strip()
        if not name or len(name) > 512:
            continue
        out.append(
            ExtractedEntity(
                name=name,
                type=ent.label_,
                char_start=int(ent.start_char),
                char_end=int(ent.end_char),
                source="spacy",
            )
        )
    return out


def _run_gliner(text: str) -> list[ExtractedEntity]:
    settings = get_settings()
    labels = settings.gliner_labels
    if not labels:
        return []
    model = _load_gliner()
    raw = model.predict_entities(text, labels, threshold=0.5)
    out: list[ExtractedEntity] = []
    for r in raw:
        label = (r.get("label") or "").strip().lower()
        canonical = _GLINER_TYPE_MAP.get(label)
        if not canonical:
            continue
        name = (r.get("text") or "").strip()
        if not name or len(name) > 512:
            continue
        try:
            start = int(r["start"])
            end = int(r["end"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(
            ExtractedEntity(
                name=name,
                type=canonical,
                char_start=start,
                char_end=end,
                source="gliner",
            )
        )
    return out


def _overlap(a: ExtractedEntity, b: ExtractedEntity) -> bool:
    return a.char_start < b.char_end and b.char_start < a.char_end


def extract_entities(text: str) -> list[ExtractedEntity]:
    """Run spaCy + GLiNER, then merge with spaCy taking precedence on overlap.

    Returns deterministic ordering: by char_start, then char_end.
    """
    spacy_ents = _run_spacy(text)
    gliner_ents = _run_gliner(text)

    merged = list(spacy_ents)
    for g in gliner_ents:
        if not any(_overlap(g, s) for s in spacy_ents):
            merged.append(g)

    merged.sort(key=lambda e: (e.char_start, e.char_end))
    return merged


__all__ = ["ExtractedEntity", "extract_entities"]
