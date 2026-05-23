from pydantic import BaseModel


class Argument(BaseModel):
    claim: str
    evidence_chunk_ids: list[str]
    stance: str  # "supporting" | "opposing" | "neutral"


class ResearchBrief(BaseModel):
    topic: str
    executive_summary: str
    key_arguments: list[Argument]
    evidence_table: list[dict]
    counterarguments: list[Argument]
    knowledge_gaps: list[str]
    recommended_reading: list[dict]
    confidence: float
    evidence_band: str | None = None
