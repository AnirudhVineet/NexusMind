"""Tests for workflow evaluation — Phase 4 Track F.

Covers: evaluate_workflows with mocked DB session and Celery.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.workflows import evaluate_workflows


def _mock_workflow(
    wid: uuid.UUID | None = None,
    trigger: str = "document_ingested",
    conditions: dict | None = None,
    action_type: str = "mark_tag",
    enabled: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=wid or uuid.uuid4(),
        user_id=uuid.uuid4(),
        trigger_event=trigger,
        conditions=conditions or {},
        action_type=action_type,
        action_config={},
        enabled=enabled,
        last_run_at=None,
        run_count=0,
    )


class TestEvaluateWorkflows:
    """Test workflow matching and action enqueuing."""

    def test_matching_workflow_is_triggered(self):
        wf = _mock_workflow(trigger="document_ingested")
        user_id = uuid.uuid4()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [wf]
        session.execute.return_value = mock_result

        with patch("app.services.workflows.WorkflowRun") as MockRun, \
             patch("app.services.workflows.celery_app") as mock_celery:
            MockRun.return_value = SimpleNamespace(id=uuid.uuid4())
            matched = evaluate_workflows(session, "document_ingested", {}, user_id)

        assert len(matched) == 1
        assert matched[0] == wf.id
        mock_celery.send_task.assert_called_once()

    def test_non_matching_event_type_skipped(self):
        wf = _mock_workflow(trigger="contradiction_detected")
        user_id = uuid.uuid4()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No match
        session.execute.return_value = mock_result

        with patch("app.services.workflows.celery_app"):
            matched = evaluate_workflows(session, "document_ingested", {}, user_id)

        assert matched == []

    def test_condition_failure_skips_workflow(self):
        wf = _mock_workflow(
            trigger="document_ingested",
            conditions={"topic_in": ["quantum"]},
        )
        user_id = uuid.uuid4()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [wf]
        session.execute.return_value = mock_result

        with patch("app.services.workflows.celery_app") as mock_celery:
            matched = evaluate_workflows(
                session, "document_ingested", {"topic": "biology"}, user_id
            )

        assert matched == []
        mock_celery.send_task.assert_not_called()

    def test_run_count_incremented(self):
        wf = _mock_workflow(trigger="document_ingested")
        wf.run_count = 5
        user_id = uuid.uuid4()

        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [wf]
        session.execute.return_value = mock_result

        with patch("app.services.workflows.WorkflowRun") as MockRun, \
             patch("app.services.workflows.celery_app"):
            MockRun.return_value = SimpleNamespace(id=uuid.uuid4())
            evaluate_workflows(session, "document_ingested", {}, user_id)

        assert wf.run_count == 6
        assert wf.last_run_at is not None
