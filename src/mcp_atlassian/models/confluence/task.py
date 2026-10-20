"""
Confluence task models.
This module provides the Pydantic model for Confluence inline tasks (the
checkbox items on a page), as served by the v2 tasks API.
"""

import logging
from typing import Any

from ..base import ApiModel
from ..constants import CONFLUENCE_DEFAULT_ID, EMPTY_STRING

logger = logging.getLogger(__name__)


class ConfluenceTask(ApiModel):
    """
    Model representing a Confluence inline task.
    """

    id: str = CONFLUENCE_DEFAULT_ID
    local_id: str = EMPTY_STRING
    space_id: str | None = None
    page_id: str | None = None
    blog_post_id: str | None = None
    status: str = "incomplete"
    body: str = EMPTY_STRING
    created_by: str | None = None
    assigned_to: str | None = None
    completed_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    due_at: str | None = None
    completed_at: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], **kwargs: Any) -> "ConfluenceTask":
        """
        Create a ConfluenceTask from a v2 task object.

        Args:
            data: The task data from the Confluence v2 API
            **kwargs: ``body_override`` replaces the body text (for example,
                after converting storage format to markdown)

        Returns:
            A ConfluenceTask instance
        """
        if not data:
            return cls()

        body_override = kwargs.get("body_override")
        if body_override is not None:
            body = str(body_override)
        else:
            raw_body = data.get("body") or {}
            storage = raw_body.get("storage") if isinstance(raw_body, dict) else None
            body = str(storage.get("value") or "") if isinstance(storage, dict) else ""

        def _opt(key: str) -> str | None:
            value = data.get(key)
            return str(value) if value not in (None, "") else None

        return cls(
            id=str(data.get("id", CONFLUENCE_DEFAULT_ID)),
            local_id=str(data.get("localId") or EMPTY_STRING),
            space_id=_opt("spaceId"),
            page_id=_opt("pageId"),
            blog_post_id=_opt("blogPostId"),
            status=str(data.get("status") or "incomplete"),
            body=body,
            created_by=_opt("createdBy"),
            assigned_to=_opt("assignedTo"),
            completed_by=_opt("completedBy"),
            created_at=_opt("createdAt"),
            updated_at=_opt("updatedAt"),
            due_at=_opt("dueAt"),
            completed_at=_opt("completedAt"),
        )

    def to_simplified_dict(self) -> dict[str, Any]:
        """Convert to simplified dictionary for API response, dropping empty fields."""
        result: dict[str, Any] = {
            "id": self.id,
            "local_id": self.local_id,
            "status": self.status,
            "body": self.body,
        }
        for key in (
            "page_id",
            "blog_post_id",
            "space_id",
            "assigned_to",
            "created_by",
            "completed_by",
            "created_at",
            "updated_at",
            "due_at",
            "completed_at",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result
