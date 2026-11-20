"""E2E Verification Test for BRIDGES React Application."""

import urllib.request
import re
import json
import pytest

BASE_URL = "http://127.0.0.1:8000"


def test_react_app_entrypoint():
    """Verify that /app serves the compiled React application entrypoint."""
    req = urllib.request.Request(f"{BASE_URL}/app")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        content = response.read().decode("utf-8")
        assert '<div id="root"></div>' in content
        assert "BRIDGES" in content
        assert "Plus Jakarta Sans" in content


def test_react_app_assets_load():
    """Verify that JS and CSS asset bundles referenced in index.html load with 200 OK."""
    req = urllib.request.Request(f"{BASE_URL}/app")
    with urllib.request.urlopen(req) as response:
        html = response.read().decode("utf-8")

    matches = re.findall(r'src=["\']([^"\']+)["\']|href=["\']([^"\']+)["\']', html)
    asset_urls = []
    for m in matches:
        path = m[0] or m[1]
        if path.startswith("/assets") or "assets/" in path:
            asset_urls.append(path)

    assert len(asset_urls) >= 2, f"Expected at least JS and CSS bundles, found: {asset_urls}"

    for asset_path in asset_urls:
        full_url = f"{BASE_URL}{asset_path}"
        with urllib.request.urlopen(full_url) as asset_res:
            assert asset_res.status == 200
            data = asset_res.read()
            assert len(data) > 1000, f"Asset {asset_path} is suspiciously small ({len(data)} bytes)"


def test_react_spa_routing():
    """Verify SPA deep links are handled properly without 404."""
    routes = ["/app/dashboard", "/app/shipments", "/app/exceptions", "/app/war_room", "/app/claims"]
    for r in routes:
        req = urllib.request.Request(f"{BASE_URL}{r}")
        with urllib.request.urlopen(req) as response:
            assert response.status == 200
            content = response.read().decode("utf-8")
            assert '<div id="root"></div>' in content


def test_api_auth_for_react_login():
    """Verify authentication endpoint used by React login form."""
    data = json.dumps({"email": "admin@controltower.corp", "password": "Password123!"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        res_json = json.loads(response.read().decode("utf-8"))
        assert res_json["success"] is True
        assert "access_token" in res_json["data"]
