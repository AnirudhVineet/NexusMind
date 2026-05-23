"""Tests for conversation CRUD endpoints — Phase 3.2."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_conv(user_id=None):
    from datetime import datetime, timezone

    from app.models.conversation import Conversation

    c = Conversation()
    c.id = uuid.uuid4()
    c.user_id = user_id or uuid.uuid4()
    c.title = "Test conversation"
    c.created_at = datetime.now(timezone.utc)
    c.messages = []
    return c


@pytest.mark.asyncio
async def test_list_conversations_returns_summaries():
    """list_conversations returns a list of ConversationSummary."""
    from app.api.conversations import list_conversations

    user = MagicMock()
    user.id = uuid.uuid4()

    # Mock session.execute to return conversations with message count
    conv = _make_conv(user.id)
    mock_result = MagicMock()
    mock_result.all.return_value = [(conv, 3)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await list_conversations(
        page=1, page_size=20, current_user=user, session=mock_session
    )
    assert len(result) == 1
    assert result[0].message_count == 3
    assert result[0].id == conv.id


@pytest.mark.asyncio
async def test_delete_conversation_not_found():
    """delete_conversation raises NotFoundError when conversation not owned."""
    from app.api.conversations import delete_conversation
    from app.core.exceptions import NotFoundError

    user = MagicMock()
    user.id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(NotFoundError):
        await delete_conversation(uuid.uuid4(), user, mock_session)


@pytest.mark.asyncio
async def test_rename_conversation_updates_title():
    """rename_conversation sets a new title on the conversation."""
    from app.api.conversations import RenameRequest, get_conversation, rename_conversation

    user = MagicMock()
    user.id = uuid.uuid4()
    conv = _make_conv(user.id)

    # First call returns conv; second call (inside get_conversation) returns detail
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv

    # get_conversation makes another execute call for messages
    empty_msgs = MagicMock()
    empty_msgs.scalars.return_value.all.return_value = []

    call_count = 0

    async def side_effect(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return mock_result
        return empty_msgs

    mock_session = AsyncMock()
    mock_session.execute = side_effect
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    body = RenameRequest(title="New title")
    await rename_conversation(conv.id, body, user, mock_session)
    assert conv.title == "New title"
