import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    evidence_count: int


class GraphEdge(BaseModel):
    id: uuid.UUID
    src: uuid.UUID
    dst: uuid.UUID
    relation: str
    confidence: float


class GraphPayload(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class EntityChunkEvidence(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page: Optional[int] = None
    snippet: str


class EntityNeighbor(BaseModel):
    entity_id: uuid.UUID
    name: str
    type: str
    relation: str
    confidence: float
    direction: str  # "out" or "in"


class EntityDetail(BaseModel):
    id: uuid.UUID
    name: str
    canonical_name: str
    type: str
    evidence_count: int
    aliases: List[str] = Field(default_factory=list)
    evidence: List[EntityChunkEvidence] = Field(default_factory=list)
    neighbors: List[EntityNeighbor] = Field(default_factory=list)


class EdgeDetail(BaseModel):
    id: uuid.UUID
    src_id: uuid.UUID
    dst_id: uuid.UUID
    src_name: str
    dst_name: str
    relation: str
    confidence: float
    evidence_chunk_id: uuid.UUID
    evidence_document_id: uuid.UUID
    evidence_page: Optional[int] = None
    evidence_snippet: str
    justification: str
