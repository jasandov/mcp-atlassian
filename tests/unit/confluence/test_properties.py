"""Unit tests for the PropertiesMixin class."""

from unittest.mock import MagicMock, patch

import pytest

from mcp_atlassian.confluence.properties import PropertiesMixin


class TestPropertiesMixin:
    """Tests for PropertiesMixin on the v1 path (basic auth)."""

    @pytest.fixture
    def properties_mixin(self, confluence_client):
        """Create a PropertiesMixin instance for testing."""
        with patch(
            "mcp_atlassian.confluence.properties.ConfluenceClient.__init__"
        ) as mock_init:
            mock_init.return_value = None
            mixin = PropertiesMixin()
            mixin.confluence = confluence_client.confluence
            mixin.config = confluence_client.config
            mixin.preprocessor = confluence_client.preprocessor
            return mixin

    def test_get_page_properties_flattens_and_filters(self, properties_mixin):
        """v1 results are flattened and an optional key filter applied."""
        properties_mixin.confluence.get_page_properties.return_value = {
            "results": [
                {
                    "id": 1,
                    "key": "owner",
                    "value": {"team": "fde"},
                    "version": {"number": 2},
                },
                {"id": 2, "key": "status", "value": "draft", "version": {"number": 1}},
            ]
        }

        assert properties_mixin.get_page_properties("123") == [
            {"id": "1", "key": "owner", "value": {"team": "fde"}, "version": 2},
            {"id": "2", "key": "status", "value": "draft", "version": 1},
        ]
        assert properties_mixin.get_page_properties("123", key="status") == [
            {"id": "2", "key": "status", "value": "draft", "version": 1}
        ]

    def test_set_page_property_creates_when_absent(self, properties_mixin):
        """A new key is created with POST."""
        properties_mixin.confluence.get_page_properties.return_value = {"results": []}
        properties_mixin.confluence.set_page_property.return_value = {
            "id": 9,
            "key": "owner",
            "value": "fde",
            "version": {"number": 1},
        }

        result = properties_mixin.set_page_property("123", "owner", "fde")

        properties_mixin.confluence.set_page_property.assert_called_once_with(
            "123", {"key": "owner", "value": "fde"}
        )
        properties_mixin.confluence.update_page_property.assert_not_called()
        assert result == {"id": "9", "key": "owner", "value": "fde", "version": 1}

    def test_set_page_property_updates_at_next_version(self, properties_mixin):
        """An existing key is updated with the version incremented."""
        properties_mixin.confluence.get_page_properties.return_value = {
            "results": [
                {"id": 9, "key": "owner", "value": "fde", "version": {"number": 4}}
            ]
        }
        properties_mixin.confluence.update_page_property.return_value = {
            "id": 9,
            "key": "owner",
            "value": "ops",
            "version": {"number": 5},
        }

        result = properties_mixin.set_page_property("123", "owner", "ops")

        properties_mixin.confluence.update_page_property.assert_called_once_with(
            "123", {"key": "owner", "value": "ops", "version": {"number": 5}}
        )
        assert result["version"] == 5

    def test_delete_page_property(self, properties_mixin):
        """Delete returns True when the key existed, False otherwise."""
        properties_mixin.confluence.get_page_properties.return_value = {
            "results": [
                {"id": 9, "key": "owner", "value": "fde", "version": {"number": 1}}
            ]
        }
        assert properties_mixin.delete_page_property("123", "owner") is True
        properties_mixin.confluence.delete_page_property.assert_called_once_with(
            "123", "owner"
        )

        properties_mixin.confluence.get_page_properties.return_value = {"results": []}
        assert properties_mixin.delete_page_property("123", "nope") is False


class TestPropertiesMixinCloudOAuth:
    """On Cloud OAuth every operation goes through the v2 adapter."""

    @pytest.fixture
    def properties_mixin(self, oauth_confluence_client):
        """Create a PropertiesMixin configured for Cloud OAuth."""
        with patch(
            "mcp_atlassian.confluence.properties.ConfluenceClient.__init__"
        ) as mock_init:
            mock_init.return_value = None
            mixin = PropertiesMixin()
            mixin.confluence = oauth_confluence_client.confluence
            mixin.config = oauth_confluence_client.config
            mixin.preprocessor = oauth_confluence_client.preprocessor
            return mixin

    def test_routes_through_adapter(self, properties_mixin):
        """List, set and delete call the adapter and never the v1 library."""
        with patch(
            "mcp_atlassian.confluence.properties.ConfluenceV2Adapter"
        ) as adapter_class:
            adapter = MagicMock()
            adapter_class.return_value = adapter
            adapter.get_page_properties.return_value = [{"key": "owner"}]
            adapter.set_page_property.return_value = {"key": "owner", "version": 2}
            adapter.delete_page_property.return_value = True

            assert properties_mixin.get_page_properties("1", key="owner") == [
                {"key": "owner"}
            ]
            assert properties_mixin.set_page_property("1", "owner", "fde") == {
                "key": "owner",
                "version": 2,
            }
            assert properties_mixin.delete_page_property("1", "owner") is True

        adapter.get_page_properties.assert_called_once_with("1", key="owner")
        adapter.set_page_property.assert_called_once_with("1", "owner", "fde")
        adapter.delete_page_property.assert_called_once_with("1", "owner")
        properties_mixin.confluence.get_page_properties.assert_not_called()
        properties_mixin.confluence.set_page_property.assert_not_called()
        properties_mixin.confluence.delete_page_property.assert_not_called()
