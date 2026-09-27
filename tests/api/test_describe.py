"""Unit tests for DescribeManager.describe_part_studio's API-call budget.

describe_part_studio fires up to 6 independent reads per call (features,
entities, bbox, mass properties, a multi-view render, a FeatureScript face-area
probe). Rendering defaults to 4 views and there's no way to skip the render or
mass-properties reads even when the caller only wants the feature tree — this
tests the fix: iso-only by default, and skip_renders/skip_mass_properties
that avoid firing those requests at all (not just discarding the result).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from onshape_mcp.api.describe import DescribeManager


def _make_manager(*, client=None, **overrides):
    client = client if client is not None else MagicMock()
    entities = MagicMock()
    entities.list_entities = AsyncMock(return_value={"bodies": []})
    renderer = MagicMock()
    renderer.render_part_studio_views = AsyncMock(return_value=[])
    measurements = MagicMock()
    measurements.mass_properties_part_studio = AsyncMock(return_value={})
    featurescript = MagicMock()
    featurescript.get_bounding_box = AsyncMock(return_value={})
    featurescript.evaluate = AsyncMock(return_value={})
    partstudio = MagicMock()
    partstudio.get_features = AsyncMock(return_value={})

    mocks = dict(
        entities=entities,
        renderer=renderer,
        measurements=measurements,
        featurescript=featurescript,
        partstudio=partstudio,
    )
    mocks.update(overrides)
    return DescribeManager(client, **mocks), mocks


class TestDescribePartStudioApiBudget:
    @pytest.mark.asyncio
    async def test_default_views_is_iso_only(self):
        mgr, mocks = _make_manager()

        await mgr.describe_part_studio("d", "w", "e")

        mocks["renderer"].render_part_studio_views.assert_awaited_once()
        _, kwargs = mocks["renderer"].render_part_studio_views.await_args
        assert kwargs["views"] == ["iso"]

    @pytest.mark.asyncio
    async def test_explicit_views_still_honored(self):
        mgr, mocks = _make_manager()

        await mgr.describe_part_studio("d", "w", "e", views=["top", "front"])

        _, kwargs = mocks["renderer"].render_part_studio_views.await_args
        assert kwargs["views"] == ["top", "front"]

    @pytest.mark.asyncio
    async def test_skip_renders_never_calls_renderer(self):
        mgr, mocks = _make_manager()

        snap = await mgr.describe_part_studio("d", "w", "e", skip_renders=True)

        mocks["renderer"].render_part_studio_views.assert_not_awaited()
        assert snap.views == []

    @pytest.mark.asyncio
    async def test_skip_mass_properties_never_calls_measurements(self):
        mgr, mocks = _make_manager()

        snap = await mgr.describe_part_studio("d", "w", "e", skip_mass_properties=True)

        mocks["measurements"].mass_properties_part_studio.assert_not_awaited()
        assert snap.raw["mass_properties"] == {}

    @pytest.mark.asyncio
    async def test_default_still_renders_and_measures(self):
        """Skip flags must be opt-in — default behavior stays a full snapshot."""
        mgr, mocks = _make_manager()

        await mgr.describe_part_studio("d", "w", "e")

        mocks["renderer"].render_part_studio_views.assert_awaited_once()
        mocks["measurements"].mass_properties_part_studio.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reports_client_call_count(self):
        client = MagicMock()
        client.call_count = 17
        mgr, _ = _make_manager(client=client)

        snap = await mgr.describe_part_studio("d", "w", "e")

        assert snap.raw["api_calls_this_session"] == 17
        assert "17" in snap.structured_text
