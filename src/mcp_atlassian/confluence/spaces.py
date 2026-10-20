"""Module for Confluence space operations."""

import logging
from typing import Any, cast

import requests

from .client import ConfluenceClient
from .v2_adapter import ConfluenceV2Adapter

logger = logging.getLogger("mcp-atlassian")


class SpacesMixin(ConfluenceClient):
    """Mixin for Confluence space operations."""

    @property
    def _v2_adapter(self) -> ConfluenceV2Adapter | None:
        """Get the v2 API adapter for Cloud OAuth, where v1 space reads are gone."""
        if self.config.auth_type == "oauth" and self.config.is_cloud:
            return ConfluenceV2Adapter(
                session=self.confluence._session, base_url=self.confluence.url
            )
        return None

    def get_space_details(self, space_key: str) -> dict[str, Any]:
        """Get a space by key.

        Args:
            space_key: The space key, for example ``DEV`` or ``~accountid``.

        Returns:
            The space's id, key, name, type, status, homepage id and plain-text
            description. The numeric id is what the v2 space endpoints take.

        Raises:
            ValueError: If the space is not found or the request fails.
        """
        v2_adapter = self._v2_adapter
        if v2_adapter:
            return v2_adapter.get_space_by_key(space_key)

        space = self.confluence.get_space(
            space_key, expand="description.plain,homepage"
        )
        if not isinstance(space, dict) or not space.get("key"):
            raise ValueError(f"Space with key '{space_key}' not found")
        homepage = space.get("homepage") or {}
        description = space.get("description") or {}
        plain = description.get("plain") if isinstance(description, dict) else None
        return {
            "id": str(space.get("id", "")),
            "key": str(space.get("key", "")),
            "name": str(space.get("name") or ""),
            "type": str(space.get("type") or ""),
            "status": str(space.get("status") or ""),
            "homepage_id": str(homepage["id"]) if homepage.get("id") else None,
            "description": (
                str(plain.get("value") or "") if isinstance(plain, dict) else ""
            ),
        }

    def get_spaces(self, start: int = 0, limit: int = 10) -> dict[str, object]:
        """
        Get all available spaces.

        Args:
            start: The starting index for pagination
            limit: Maximum number of spaces to return

        Returns:
            Dictionary containing space information with results and metadata
        """
        spaces = self.confluence.get_all_spaces(start=start, limit=limit)
        # Cast the return value to the expected type
        return cast(dict[str, object], spaces)

    def get_user_contributed_spaces(self, limit: int = 250) -> dict:
        """
        Get spaces the current user has contributed to.

        Args:
            limit: Maximum number of results to return

        Returns:
            Dictionary of space keys to space information
        """
        try:
            # Use CQL to find content the user has contributed to
            cql = "contributor = currentUser() order by lastmodified DESC"
            results = self.confluence.cql(cql=cql, limit=limit)

            # Extract and deduplicate spaces
            spaces = {}
            for result in results.get("results", []):
                space_key = None
                space_name = None

                # Try to extract space from container
                if "resultGlobalContainer" in result:
                    container = result.get("resultGlobalContainer", {})
                    space_name = container.get("title")
                    display_url = container.get("displayUrl", "")
                    if display_url and "/spaces/" in display_url:
                        space_key = display_url.split("/spaces/")[1].split("/")[0]

                # Try to extract from content expandable
                if (
                    not space_key
                    and "content" in result
                    and "_expandable" in result["content"]
                ):
                    expandable = result["content"].get("_expandable", {})
                    space_path = expandable.get("space", "")
                    if space_path and space_path.startswith("/rest/api/space/"):
                        space_key = space_path.split("/rest/api/space/")[1]

                # Try to extract from URL
                if not space_key and "url" in result:
                    url = result.get("url", "")
                    if url and url.startswith("/spaces/"):
                        space_key = url.split("/spaces/")[1].split("/")[0]

                # Only add if we found a space key and it's not already in our results
                if space_key and space_key not in spaces:
                    # Add some defaults if we couldn't extract all fields
                    space_name = space_name or f"Space {space_key}"
                    spaces[space_key] = {"key": space_key, "name": space_name}

            return spaces

        except KeyError as e:
            logger.error(f"Missing key in Confluence spaces data: {str(e)}")
            return {}
        except ValueError as e:
            logger.error(f"Invalid value in Confluence spaces: {str(e)}")
            return {}
        except TypeError as e:
            logger.error(f"Type error when processing Confluence spaces: {str(e)}")
            return {}
        except requests.RequestException as e:
            logger.error(f"Network error when fetching spaces: {str(e)}")
            return {}
        except Exception as e:  # noqa: BLE001 - Intentional fallback with logging
            logger.error(f"Unexpected error fetching Confluence spaces: {str(e)}")
            logger.debug("Full exception details for Confluence spaces:", exc_info=True)
            return {}
