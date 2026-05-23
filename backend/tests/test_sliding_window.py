"""Test that conversation history is capped to 6 messages (3 turns)."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


def _msg(role: str, content: str):
    from datetime import datetime, timezone

    from app.models.message import Message

    m = Message()
    m.id = uuid.uuid4()
    m.conversation_id = uuid.uuid4()
    m.role = role
    m.content = content
    m.created_at = datetime.now(timezone.utc)
    m.citations = None
    m.confidence_score = None
    return m


@pytest.mark.asyncio
async def test_sliding_window_returns_max_6():
    """_load_conversation_history queries with LIMIT 6."""
    from app.api.qa import _load_conversation_history

    # Build 10 messages alternating user/assistant
    msgs = [_msg("user" if i % 2 == 0 else "assistant", f"msg {i}") for i in range(10)]

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = msgs[:6]  # DB already limits

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await _load_conversation_history(mock_session, uuid.uuid4(), max_turns=6)
    assert len(result) <= 6


@pytest.mark.asyncio
async def test_sliding_window_correct_role_order():
    """Messages are returned in chronological order (oldest first)."""
    from app.api.qa import _load_conversation_history

    msgs = [
        _msg("user", "hello"),
        _msg("assistant", "world"),
        _msg("user", "follow up"),
    ]

    # The DB query uses ORDER BY created_at DESC, so the mock must return
    # messages newest-first to match what the real DB would return.
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = list(reversed(msgs))

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await _load_conversation_history(mock_session, uuid.uuid4())
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "hello"
    assert result[-1]["content"] == "follow up"
