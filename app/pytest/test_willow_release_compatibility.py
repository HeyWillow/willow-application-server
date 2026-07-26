import pytest

from app.internal.was import is_willow_release_compatible


@pytest.mark.parametrize(
    ("version", "compatible"),
    [
        ("0.4.3", True),
        ("v0.4.3", True),
        ("0.5.0-alpha.1", True),
        ("0.5.0-alpha.99", True),
        ("0.5.0-beta.0", False),
        ("0.5.0-beta.1", False),
        ("0.5.0", False),
        ("0.5.0-rc.1", False),
        ("1.0.0", False),
        ("local", True),
        ("development", True),
    ],
)
def test_is_willow_release_compatible(version, compatible):
    assert is_willow_release_compatible(version) is compatible
