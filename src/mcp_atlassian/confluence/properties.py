"""Module for Confluence content property operations."""

import logging
from typing import Any

from .client import ConfluenceClient
from .v2_adapter import ConfluenceV2Adapter

logger = logging.getLogger("mcp-atlassian")


class PropertiesMixin(ConfluenceClient):
    """Mixin for Confluence page content properties.

    Content properties are JSON values stored against a page under a key.
    Cloud OAuth goes through the v2 API, where v1 content reads are gone;
    other auth modes use the v1 content property endpoints.
    """

    @property
    def _v2_adapter(self) -> ConfluenceV2Adapter | None:
        """Get the v2 API adapter for Cloud OAuth."""
        if self.config.auth_type == "oauth" and self.config.is_cloud:
            return ConfluenceV2Adapter(
                session=self.confluence._session, base_url=self.confluence.url
            )
        return None

    @staticmethod
    def _normalize_v1_property(data: dict[str, Any]) -> dict[str, Any]:
        """Flatten a v1 content property to id, key, value and version number."""
        version = data.get("version") or {}
        return {
            "id": str(data.get("id", "")),
            "key": str(data.get("key", "")),
            "value": data.get("value"),
            "version": version.get("number") if isinstance(version, dict) else None,
        }

    def get_page_properties(
        self, page_id: str, key: str | None = None
    ) -> list[dict[str, Any]]:
        """List a page's content properties.

        Args:
            page_id: The ID of the page.
            key: Optional property key to filter on.

        Returns:
            Properties as dicts with id, key, value and version number.

        Raises:
            ValueError: If the request fails.
        """
        v2_adapter = self._v2_adapter
        if v2_adapter:
            return v2_adapter.get_page_properties(page_id, key=key)

        response = self.confluence.get_page_properties(page_id)
        results = response.get("results", []) if isinstance(response, dict) else []
        properties = [
            self._normalize_v1_property(item)
            for item in results
            if isinstance(item, dict)
        ]
        if key:
            properties = [prop for prop in properties if prop["key"] == key]
        return properties

    def set_page_property(self, page_id: str, key: str, value: Any) -> dict[str, Any]:
        """Create or update a page content property.

        Args:
            page_id: The ID of the page.
            key: The property key.
            value: The JSON-serialisable value to store.

        Returns:
            The stored property as a dict with id, key, value and version.

        Raises:
            ValueError: If the request fails.
        """
        v2_adapter = self._v2_adapter
        if v2_adapter:
            return v2_adapter.set_page_property(page_id, key, value)

        existing = self.get_page_properties(page_id, key=key)
        data: dict[str, Any] = {"key": key, "value": value}
        if existing:
            data["version"] = {"number": int(existing[0].get("version") or 0) + 1}
            response = self.confluence.update_page_property(page_id, data)
        else:
            response = self.confluence.set_page_property(page_id, data)
        if not isinstance(response, dict):
            raise ValueError(f"Unexpected response setting property '{key}'")
        return self._normalize_v1_property(response)

    def delete_page_property(self, page_id: str, key: str) -> bool:
        """Delete a page content property by key.

        Args:
            page_id: The ID of the page.
            key: The property key.

        Returns:
            True if a property was deleted, False if none had that key.

        Raises:
            ValueError: If the request fails.
        """
        v2_adapter = self._v2_adapter
        if v2_adapter:
            return v2_adapter.delete_page_property(page_id, key)

        if not self.get_page_properties(page_id, key=key):
            return False
        self.confluence.delete_page_property(page_id, key)
        return True
