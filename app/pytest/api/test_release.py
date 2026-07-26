import json
import unittest

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.pytest.mock import mock_releases_willow


client = TestClient(app)


mock_releases_was = [{
    "name": "0.0.0-mock.0",
    "tag_name": "0.0.0-mock.0",
    "latest": True,
    "was_compatible": True,
    "assets": [
        {
            "browser_download_url": "bogus",
            "platform": "ESP32-S3-BOX-3",
            "was_url": "http://was.local/api/ota?version=0.0.0-mock.0&platform=ESP32-S3-BOX-3",
            "cached": True
        }
    ]
}]


class TestRelease(unittest.TestCase):
    def test_get_release(self):
        with patch("app.routers.release.get_releases_willow", return_value=mock_releases_willow):
            with patch("app.routers.release.get_was_url", return_value=None):
                response = client.get("/api/release?type=was")

                assert response.status_code == 500

        with patch("app.routers.release.get_releases_willow", return_value=mock_releases_willow):
            response = client.get("/api/release?type=willow")

            assert response.status_code == 200
            assert json.loads(response.content) == mock_releases_willow

            with patch("app.routers.release.get_was_url", return_value="ws://was.local/ws"):
                with patch("app.routers.release.os.path.isfile", return_value=True):
                    response = client.get("/api/release?type=was")

                assert response.status_code == 200
                assert json.loads(response.content) == mock_releases_was

    def test_incompatible_releases_are_not_offered(self):
        releases = [
            {
                "name": "0.5.0",
                "tag_name": "0.5.0",
                "latest": True,
                "prerelease": False,
                "assets": [{
                    "browser_download_url": "bogus",
                    "platform": "ESP32-S3-BOX-3",
                }],
            },
            {
                "name": "0.4.3",
                "tag_name": "0.4.3",
                "latest": False,
                "prerelease": False,
                "assets": [{
                    "browser_download_url": "bogus",
                    "platform": "ESP32-S3-BOX-3",
                }],
            },
        ]

        with patch("app.routers.release.get_releases_willow", return_value=releases):
            with patch("app.routers.release.get_was_url", return_value="ws://was.local/ws"):
                response = client.get("/api/release?type=was")

        assert response.status_code == 200
        response_releases = json.loads(response.content)

        incompatible = response_releases[0]
        assert incompatible["was_compatible"] is False
        assert incompatible["latest"] is False
        assert "was_url" not in incompatible["assets"][0]

        compatible = response_releases[1]
        assert compatible["was_compatible"] is True
        assert compatible["latest"] is True
        assert compatible["assets"][0]["was_url"] == (
            "http://was.local/api/ota?version=0.4.3&platform=ESP32-S3-BOX-3"
        )
