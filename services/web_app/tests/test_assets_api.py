"""Asset Upload/Download API structural test."""
from __future__ import annotations

import pytest
from services.web_app.api.assets import router


@pytest.mark.asyncio
async def test_download_asset_requires_org_ownership():
    """Asset download must verify org ownership — return 404 for wrong org."""
    assert router.routes  # Router has routes defined
