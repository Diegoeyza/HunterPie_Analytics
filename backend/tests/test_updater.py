"""Updater logic: version compare, sums parsing, asset selection, trust."""
from app import updater


def test_parse_version_handles_tags_and_suffixes():
    assert updater.parse_version("v1.0.10") == (1, 0, 10)
    assert updater.parse_version("1.0.5") == (1, 0, 5)
    assert updater.parse_version("release 1.2") == (1, 2)
    assert updater.parse_version("nightly") == ()


def test_is_newer_is_numeric_not_lexical():
    assert updater.is_newer("v1.0.10", "1.0.9") is True
    assert updater.is_newer("1.0.5", "1.0.5") is False
    assert updater.is_newer("1.0.2", "1.0.10") is False
    assert updater.is_newer("2.0", "1.9.9") is True


def test_parse_sums_accepts_binary_and_plain_forms():
    text = (
        "e2334465a72d83609d5ce660754e24c090e9ded5ba606ab4d0524c84aa852343  HuntDumper-0.9.3.zip\n"
        "BF5E37ED879DB581BE48470C13376280554AD6B37DF082B5B6E511099A6EC23A *HunterPieAnalytics-Setup-1.0.5.exe\n"
        "\n"
        "garbage line\n"
    )
    sums = updater.parse_sums(text)
    assert sums["HuntDumper-0.9.3.zip"] == "e2334465a72d83609d5ce660754e24c090e9ded5ba606ab4d0524c84aa852343"
    assert sums["HunterPieAnalytics-Setup-1.0.5.exe"] == "bf5e37ed879db581be48470c13376280554ad6b37df082b5b6e511099a6ec23a"


def _release(tag: str, names: list[str]) -> dict:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/x/y/releases/tag/{tag}",
        "assets": [
            {"name": n, "browser_download_url": f"https://github.com/dl/{n}", "size": 100}
            for n in names
        ],
    }


def test_select_assets_finds_setup_and_sums_only():
    rel = _release("v1.0.6", [
        "HuntDumper-0.9.3.zip",
        "HunterPieAnalytics-Setup-1.0.6.exe",
        "SHA256SUMS.txt",
    ])
    picked = updater.select_assets(rel)
    assert picked is not None
    assert picked["name"] == "HunterPieAnalytics-Setup-1.0.6.exe"
    assert picked["sums_url"].endswith("SHA256SUMS.txt")


def test_select_assets_none_when_no_installer():
    assert updater.select_assets(_release("v1.0.6", ["HuntDumper-0.9.3.zip"])) is None


def test_describe_update_flags_newer_only():
    rel = _release("v1.0.6", ["HunterPieAnalytics-Setup-1.0.6.exe", "SHA256SUMS.txt"])
    newer = updater.describe_update(rel, "1.0.5", sha256="abc")
    assert newer["update_available"] is True
    assert newer["latest"] == "1.0.6"
    assert newer["sha256"] == "abc"

    same = updater.describe_update(rel, "1.0.6", sha256="abc")
    assert same["update_available"] is False
    assert same["latest"] == "1.0.6"


def test_describe_update_without_release_is_safe():
    info = updater.describe_update(None, "1.0.6")
    assert info["update_available"] is False
    assert info["latest"] is None
    assert info["current"] == "1.0.6"


def test_describe_update_ignores_release_without_installer():
    rel = _release("v1.0.6", ["HuntDumper-0.9.3.zip"])
    assert updater.describe_update(rel, "1.0.5")["update_available"] is False


def test_is_trusted_url():
    assert updater.is_trusted_url("https://github.com/x/y/releases/download/v1/S.exe")
    assert updater.is_trusted_url(
        "https://objects.githubusercontent.com/abc?response-content-disposition=1")
    assert not updater.is_trusted_url("https://evil.example.com/S.exe")
    assert not updater.is_trusted_url("http://github.com.evil.example/S.exe")
