"""Tests for the ConfluenceTask model."""

from mcp_atlassian.models.confluence import ConfluenceTask


def test_from_api_response_maps_fields_and_drops_empty():
    """v2 task fields map to snake_case; empty ones are omitted from output."""
    task = ConfluenceTask.from_api_response(
        {
            "id": "t1",
            "localId": "7",
            "spaceId": "120193605",
            "pageId": "1",
            "status": "complete",
            "body": {"storage": {"value": "<p>Do it</p>"}},
            "assignedTo": "",
            "completedBy": "712020:abc",
            "completedAt": "2026-10-20T21:00:00.000Z",
        }
    )

    assert task.id == "t1"
    assert task.local_id == "7"
    assert task.body == "<p>Do it</p>"
    assert task.assigned_to is None
    simplified = task.to_simplified_dict()
    assert simplified["completed_by"] == "712020:abc"
    assert "assigned_to" not in simplified
    assert "due_at" not in simplified


def test_body_override_and_empty_response():
    """A body override replaces the storage body; empty data gives defaults."""
    task = ConfluenceTask.from_api_response(
        {"id": "t1", "body": {"storage": {"value": "<p>x</p>"}}}, body_override="x"
    )
    assert task.body == "x"
    assert ConfluenceTask.from_api_response({}).status == "incomplete"
