from app.models.annotation import ANNOTATION_COLORS, Annotation
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.entity import ENTITY_TYPES, ChunkEntity, Entity, EntityAlias
from app.models.entity_edge import RELATION_TYPES, EntityEdge
from app.models.flashcard import Flashcard, FlashcardReview
from app.models.message import Message
from app.models.task_run import TaskRun
from app.models.topic import TOPIC_SOURCES, DocumentTag, TopicTag
from app.models.user import User
# Phase 4 models
from app.models.user_event import UserEvent, ALLOWED_EVENT_TYPES
from app.models.research_brief import ResearchBrief
from app.models.chunk_topic import ChunkTopic
from app.models.generated_content import GeneratedContent
# Phase 5 models
from app.models.media_job import MediaJob, JOB_TYPES, JOB_STATUSES
from app.models.media_asset import MediaAsset, ASSET_TYPES, SOURCE_KINDS, LICENSES
from app.models.voice import UserVoicePreference, BriefNarration
from app.models.share_link import ShareLink, TARGET_TYPES as SHARE_TARGET_TYPES
from app.models.brandkit import BrandKit
from app.models.generation_metric import GenerationMetric

__all__ = [
    "User",
    "Document",
    "Chunk",
    "Annotation",
    "ANNOTATION_COLORS",
    "Conversation",
    "Message",
    "Entity",
    "EntityAlias",
    "ChunkEntity",
    "EntityEdge",
    "TopicTag",
    "DocumentTag",
    "TaskRun",
    "Flashcard",
    "FlashcardReview",
    "ENTITY_TYPES",
    "RELATION_TYPES",
    "TOPIC_SOURCES",
    # Phase 4
    "UserEvent",
    "ALLOWED_EVENT_TYPES",
    "ResearchBrief",
    "ChunkTopic",
    "GeneratedContent",
    # Phase 5
    "MediaJob",
    "JOB_TYPES",
    "JOB_STATUSES",
    "MediaAsset",
    "ASSET_TYPES",
    "SOURCE_KINDS",
    "LICENSES",
    "UserVoicePreference",
    "BriefNarration",
    "ShareLink",
    "SHARE_TARGET_TYPES",
    "BrandKit",
    "GenerationMetric",
]
