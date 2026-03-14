"""Project CRUD API structural test."""
from __future__ import annotations

import pytest
from services.web_app.api.projects import router


def test_project_router_has_routes():
    route_paths = [r.path for r in router.routes]
    assert "/api/projects/" in route_paths  # POST / (create) + GET / (list)
    assert "/api/projects/{project_id}" in route_paths  # GET/PATCH/DELETE detail


def test_project_router_has_source_upload():
    route_paths = [r.path for r in router.routes]
    assert "/api/projects/{project_id}/sources" in route_paths
