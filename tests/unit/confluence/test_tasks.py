"""Unit tests for the TasksMixin class."""

from unittest.mock import MagicMock, patch

import pytest

from mcp_atlassian.confluence.config import ConfluenceConfig
from mcp_atlassian.confluence.tasks import TasksMixin

TASK = {
    "id": "task-1",
    "localId": "7",
    "spaceId": "120193605",
    "pageId": "1289158692",
    "status": "incomplete",
    "body": {"storage": {"value": "<p>Write the <b>handoff</b></p>"}},
    "createdBy": "712020:abc",
    "assignedTo": "712020:def",
    "createdAt": "2026-10-20T20:00:00.000Z",
    "dueAt": "2026-10-24",
}


class TestTasksMixin:
    """Tests for TasksMixin on Cloud."""

    @pytest.fixture
    def tasks_mixin(self, oauth_confluence_client):
        """Create a TasksMixin configured for Cloud OAuth."""
        with patch(
            "mcp_atlassian.confluence.tasks.ConfluenceClient.__init__"
        ) as mock_init:
            mock_init.return_value = None
            mixin = TasksMixin()
            mixin.confluence = oauth_confluence_client.confluence
            mixin.config = oauth_confluence_client.config
            mixin.preprocessor = oauth_confluence_client.preprocessor
            mixin.preprocessor.process_html_content.return_value = (
                "<p>Write the <b>handoff</b></p>",
                "Write the **handoff**",
            )
            return mixin

    def test_get_tasks_renders_body_as_markdown(self, tasks_mixin):
        """Tasks come from the adapter with their bodies converted."""
        with patch(
            "mcp_atlassian.confluence.tasks.ConfluenceV2Adapter"
        ) as adapter_class:
            adapter = MagicMock()
            adapter_class.return_value = adapter
            adapter.get_tasks.return_value = [TASK]

            tasks = tasks_mixin.get_tasks(page_id="1289158692", status="incomplete")

        adapter.get_tasks.assert_called_once_with(
            page_id="1289158692",
            space_id=None,
            status="incomplete",
            assigned_to=None,
            limit=100,
        )
        assert len(tasks) == 1
        task = tasks[0]
        assert task.id == "task-1"
        assert task.local_id == "7"
        assert task.body == "Write the **handoff**"
        assert task.assigned_to == "712020:def"
        assert task.to_simplified_dict()["due_at"] == "2026-10-24"
        assert "completed_at" not in task.to_simplified_dict()

    def test_update_task(self, tasks_mixin):
        """Completing a task returns the updated model."""
        with patch(
            "mcp_atlassian.confluence.tasks.ConfluenceV2Adapter"
        ) as adapter_class:
            adapter = MagicMock()
            adapter_class.return_value = adapter
            adapter.update_task.return_value = {**TASK, "status": "complete"}

            task = tasks_mixin.update_task("task-1", "complete")

        adapter.update_task.assert_called_once_with("task-1", "complete")
        assert task.status == "complete"

    @pytest.mark.parametrize("status", ["done", "open", ""])
    def test_bad_status_is_rejected(self, tasks_mixin, status):
        """Only complete and incomplete are accepted."""
        with pytest.raises(ValueError, match="status must be one of"):
            tasks_mixin.update_task("task-1", status)
        with pytest.raises(ValueError, match="status must be one of"):
            tasks_mixin.get_tasks(status=status)

    def test_server_dc_is_rejected(self, tasks_mixin):
        """Server/Data Center has no tasks API."""
        tasks_mixin.config = ConfluenceConfig(
            url="https://confluence.example.com",
            auth_type="basic",
            username="user",
            api_token="token",
        )
        with pytest.raises(ValueError, match="only available for Confluence Cloud"):
            tasks_mixin.get_tasks()
