"""Module for Confluence inline task operations (Cloud only)."""

import logging

from ..models.confluence import ConfluenceTask
from .client import ConfluenceClient
from .v2_adapter import ConfluenceV2Adapter

logger = logging.getLogger("mcp-atlassian")

TASK_STATUSES = ("complete", "incomplete")


class TasksMixin(ConfluenceClient):
    """Mixin for Confluence inline tasks, the checkbox items on a page.

    Tasks are served by the v2 API only, so this is Confluence Cloud only.
    Any Cloud auth mode works; the v2 base URL follows the client's URL on
    OAuth and the configured site URL otherwise.
    """

    def _tasks_v2_adapter(self) -> ConfluenceV2Adapter:
        """Get the v2 adapter for tasks, or raise on Server/Data Center."""
        if not self.config.is_cloud:
            msg = (
                "Confluence tasks are only available for Confluence Cloud. "
                "Server/Data Center has no tasks API."
            )
            raise ValueError(msg)
        base_url = (
            self.confluence.url if self.config.auth_type == "oauth" else self.config.url
        )
        return ConfluenceV2Adapter(session=self.confluence._session, base_url=base_url)

    def _task_from_api(self, data: dict) -> ConfluenceTask:
        """Build a task model, converting the storage body to markdown."""
        raw_body = data.get("body") or {}
        storage = raw_body.get("storage") if isinstance(raw_body, dict) else None
        body = str(storage.get("value") or "") if isinstance(storage, dict) else ""
        markdown = body
        if body:
            try:
                _, markdown = self.preprocessor.process_html_content(
                    body, confluence_client=self.confluence
                )
            except Exception as e:  # noqa: BLE001 - keep the raw body on failure
                logger.debug(f"Could not convert task body to markdown: {e}")
                markdown = body
        return ConfluenceTask.from_api_response(data, body_override=markdown.strip())

    def get_tasks(
        self,
        *,
        page_id: str | None = None,
        space_id: str | None = None,
        status: str | None = None,
        assigned_to: str | None = None,
        limit: int = 100,
    ) -> list[ConfluenceTask]:
        """List inline tasks.

        Args:
            page_id: Only tasks on this page.
            space_id: Only tasks in this space (numeric space id).
            status: ``complete`` or ``incomplete``.
            assigned_to: Only tasks assigned to this account id.
            limit: Maximum number of tasks to return.

        Returns:
            ConfluenceTask models, bodies as markdown.

        Raises:
            ValueError: On Server/Data Center, on a bad status, or if the
                request fails.
        """
        if status is not None and status not in TASK_STATUSES:
            msg = f"status must be one of {TASK_STATUSES}, got '{status}'"
            raise ValueError(msg)
        adapter = self._tasks_v2_adapter()
        tasks = adapter.get_tasks(
            page_id=page_id,
            space_id=space_id,
            status=status,
            assigned_to=assigned_to,
            limit=limit,
        )
        return [self._task_from_api(task) for task in tasks]

    def update_task(self, task_id: str, status: str) -> ConfluenceTask:
        """Mark an inline task complete or incomplete.

        Args:
            task_id: The task id, as returned by get_tasks.
            status: ``complete`` or ``incomplete``.

        Returns:
            The updated ConfluenceTask.

        Raises:
            ValueError: On Server/Data Center, on a bad status, or if the
                request fails.
        """
        if status not in TASK_STATUSES:
            msg = f"status must be one of {TASK_STATUSES}, got '{status}'"
            raise ValueError(msg)
        adapter = self._tasks_v2_adapter()
        return self._task_from_api(adapter.update_task(task_id, status))
