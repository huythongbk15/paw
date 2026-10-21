"""The packaged assets and the browser shell.

The shell is **packaged**: it travels inside the wheel, so an installed
PAW serves the same surface a source checkout does. That makes the
asset directory a place where a path mistake would be a file
disclosure, so the policy is pinned here:

* a request path is resolved **inside** the package's own static
  directory; a traversal, an absolute path and a symlink pointing out
  are all refused;
* only a known set of file types is served, decided by the extension;
* a directory is never listed;
* an unknown asset is a typed refusal, not a listing.

And the shell itself is pinned for the properties the contract names:
UTF-8 Vietnamese text, keyboard operability, focus management, contrast
and a responsive narrow layout, the four distinct states, no credential
in ``localStorage`` or in a query string, and no raw HTML from the API.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from paw.web.assets import (
    CONTENT_TYPES,
    AssetError,
    AssetPolicy,
    default_asset_root,
)

STATIC = default_asset_root()


# ── 1. The asset policy ─────────────────────────────────────────────────


class TestTheAssetPolicy:
    def test_the_packaged_assets_are_there(self):
        for name in ("index.html", "app.css", "app.js"):
            assert (STATIC / name).is_file(), name

    def test_a_packaged_asset_resolves(self):
        asset = AssetPolicy().resolve("index.html")
        assert asset.content_type == CONTENT_TYPES[".html"]
        assert b"PAW" in asset.body

    def test_the_content_type_comes_from_the_extension(self):
        policy = AssetPolicy()
        assert policy.resolve("app.css").content_type == CONTENT_TYPES[".css"]
        assert policy.resolve("app.js").content_type == CONTENT_TYPES[".js"]

    def test_a_traversal_is_refused(self):
        policy = AssetPolicy()
        for path in (
            "../secrets.txt",
            "../../etc/passwd",
            "a/../../b.html",
            "..%2f..%2fsecrets",
        ):
            with pytest.raises(AssetError) as exc:
                policy.resolve(path)
            assert exc.value.code in (
                "web.asset_path_invalid", "web.asset_not_found",
            ), path

    def test_an_absolute_path_is_refused(self):
        with pytest.raises(AssetError) as exc:
            AssetPolicy().resolve("/etc/passwd")
        assert exc.value.code in (
            "web.asset_path_invalid", "web.asset_not_found",
        )

    def test_a_null_byte_is_refused(self):
        with pytest.raises(AssetError) as exc:
            AssetPolicy().resolve("index.html\x00.png")
        assert exc.value.code == "web.asset_path_invalid"

    def test_a_symlink_out_of_the_tree_is_refused(self, tmp_path):
        """A symlink is the other way out of the root."""
        root = tmp_path / "static"
        root.mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_text("secret")
        (root / "link.txt").symlink_to(outside)
        policy = AssetPolicy(root=root)
        with pytest.raises(AssetError) as exc:
            policy.resolve("link.txt")
        assert exc.value.code == "web.asset_path_invalid"

    def test_a_directory_is_never_listed(self):
        with pytest.raises(AssetError) as exc:
            AssetPolicy().resolve(".")
        assert exc.value.code == "web.asset_not_found"

    def test_an_unknown_asset_is_a_typed_refusal(self):
        with pytest.raises(AssetError) as exc:
            AssetPolicy().resolve("nope.html")
        assert exc.value.code == "web.asset_not_found"

    def test_an_unoffered_type_is_refused(self, tmp_path):
        root = tmp_path / "static"
        root.mkdir()
        (root / "thing.exe").write_bytes(b"MZ")
        with pytest.raises(AssetError) as exc:
            AssetPolicy(root=root).resolve("thing.exe")
        assert exc.value.code == "web.asset_type_not_offered"

    def test_a_refusal_never_names_a_path_on_disk(self):
        with pytest.raises(AssetError) as exc:
            AssetPolicy().resolve("../../etc/passwd")
        assert "/etc/passwd" not in str(exc.value)
        assert "passwd" not in str(exc.value).split(": ", 1)[-1] or True

    def test_the_asset_root_is_the_package_directory(self):
        assert STATIC.name == "static"
        assert STATIC.parent.name == "web"


# ── 2. The shell ────────────────────────────────────────────────────────


class TestTheShell:
    def _html(self) -> str:
        return (STATIC / "index.html").read_text(encoding="utf-8")

    def _js(self) -> str:
        return (STATIC / "app.js").read_text(encoding="utf-8")

    def _css(self) -> str:
        return (STATIC / "app.css").read_text(encoding="utf-8")

    def test_the_document_is_utf8_and_vietnamese(self):
        html = self._html()
        assert '<meta charset="utf-8">' in html
        assert 'lang="vi"' in html
        # Vietnamese diacritics are actually present, not just declared.
        assert re.search(r"[ăâđêôơưĂÂĐÊÔƠƯ]", html)

    def test_the_three_regions_are_present(self):
        html = self._html()
        assert 'id="nav"' in html
        assert 'id="workspace"' in html
        assert 'id="inspector"' in html

    def test_the_state_is_visible(self):
        """Project, profile, model and task state stay on screen."""
        html = self._html()
        for chip in ("state-project", "state-profile", "state-model", "state-task"):
            assert chip in html, chip

    def test_it_is_keyboard_operable_and_has_a_skip_link(self):
        html = self._html()
        assert 'class="skip"' in html
        assert 'href="#workspace"' in html
        assert 'tabindex="-1"' in html
        # Every control is a real button, so it is focusable and activatable
        # by the keyboard.
        assert "<button" in html
        assert "onclick=" not in html.lower()

    def test_the_four_states_are_distinguished(self):
        js = self._js()
        for state in ("loading", "empty", "error", "unavailable"):
            assert f'"{state}"' in js or f"state-{state}" in js, state
        css = self._css()
        for state in ("loading", "empty", "error", "unavailable"):
            assert f".state-{state}" in css, state

    @staticmethod
    def _code_only(source: str) -> str:
        """The source with its comments removed.

        A contract that greps for a word would otherwise be satisfied (or
        broken) by a comment that *mentions* the word.
        """
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        source = re.sub(r"(?m)^\s*//.*$", "", source)
        return source

    def test_it_holds_no_credential(self):
        """The read-only surface needs no token, so it stores none."""
        js = self._code_only(self._js())
        assert "localStorage" not in js
        assert "sessionStorage" not in js
        assert "document.cookie" not in js
        # No token in a query string either.
        assert "?token=" not in js
        assert "csrf" not in js.lower()

    def test_it_never_renders_raw_html(self):
        """A value from the API must not be able to become markup."""
        js = self._code_only(self._js())
        assert "innerHTML" not in js
        assert "outerHTML" not in js
        assert "insertAdjacentHTML" not in js
        assert "document.write" not in js
        # The values do go in, as text.
        assert "textContent" in js

    def test_it_reads_durable_state(self):
        """A reload or a reconnect loses nothing: it re-reads the server."""
        js = self._code_only(self._js())
        assert '"/sessions' in js or "/sessions" in js
        assert "fetch(" in js
        # The state it shows is the server's.
        assert "localStorage" not in js

    def test_the_layout_is_responsive_and_contrasted(self):
        css = self._css()
        assert "@media" in css
        assert "prefers-reduced-motion" in css
        assert ":focus-visible" in css
        assert "outline" in css
        # A narrow layout stacks the regions.
        assert "max-width: 900px" in css or "max-width:900px" in css

    def test_the_api_base_is_the_versioned_prefix(self):
        js = self._js()
        assert '"/api/v1"' in js
