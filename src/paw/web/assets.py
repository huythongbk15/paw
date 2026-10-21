"""The packaged asset policy.

The browser shell is **packaged**: it travels inside the wheel, so an
installed PAW serves the same surface a source checkout does. That makes
the asset directory a place where a path mistake would be a file
disclosure, so the policy is explicit:

* the asset root is the package's own ``static`` directory, resolved
  once;
* a request path is resolved **inside** that root, and anything that
  escapes - ``..``, an absolute path, a symlink pointing out - is
  refused rather than clamped;
* only a known set of file types is served, and the type is decided by
  the extension, never by the request;
* a directory is never listed;
* an unknown asset is a typed refusal, not a directory listing.

The shell is same-origin and carries no credential: the read-only
surface needs no CSRF token, so the browser holds none - not in
``localStorage``, not in a cookie, not in a query string.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "AssetError",
    "AssetPolicy",
    "AssetResult",
    "default_asset_root",
]

# The file types the shell is made of. A request for anything else is
# refused - the policy is an allowlist, not a denylist.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}

# A request path segment that could escape the root.
_ESCAPING = ("..", "\x00")


class AssetError(Exception):
    """A request for an asset that is not offered.

    The code is stable and safe to show; it never names a path on disk.
    """

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message or code.replace('.', ' ')}")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self).split(": ", 1)[-1]}


@dataclass(frozen=True)
class AssetResult:
    """An asset that may be served."""

    path: Path
    content_type: str
    body: bytes

    @property
    def etag(self) -> str:
        """A content hash, so the browser can revalidate cheaply."""
        import hashlib

        return hashlib.sha256(self.body).hexdigest()[:32]


def default_asset_root() -> Path:
    """The packaged static directory."""
    return Path(__file__).resolve().parent / "static"


@dataclass(frozen=True)
class AssetPolicy:
    """Where the assets live and what may be served."""

    root: Path | None = None

    def asset_root(self) -> Path:
        """The resolved asset root."""
        if self.root is not None:
            return Path(self.root).resolve()
        return default_asset_root()

    def resolve(self, request_path: str) -> AssetResult:
        """Resolve a request path to an asset, or refuse it.

        The path is treated as a *request path*, not a filesystem path:
        it is split on ``/``, every segment is checked, and the result
        must still be inside the root once resolved - which also catches a
        symlink that points out of the tree.
        """
        root = self.asset_root()
        raw = (request_path or "").lstrip("/")
        if not raw:
            raw = "index.html"
        if any(marker in raw for marker in _ESCAPING):
            raise AssetError("web.asset_path_invalid", "the asset path is not valid")
        segments = [part for part in raw.split("/") if part]
        if not segments:
            raise AssetError("web.asset_not_found", "no such asset")
        candidate = root.joinpath(*segments)
        try:
            resolved = candidate.resolve()
        except OSError:
            raise AssetError("web.asset_not_found", "no such asset") from None
        try:
            resolved.relative_to(root)
        except ValueError:
            # The resolved path is outside the root: a traversal or a
            # symlink that points out of the tree.
            raise AssetError("web.asset_path_invalid", "the asset path is not valid") from None
        if resolved.is_dir():
            # A directory is never listed.
            raise AssetError("web.asset_not_found", "no such asset")
        if not resolved.is_file():
            raise AssetError("web.asset_not_found", "no such asset")
        content_type = CONTENT_TYPES.get(resolved.suffix.lower())
        if content_type is None:
            raise AssetError("web.asset_type_not_offered", "that asset type is not served")
        try:
            body = resolved.read_bytes()
        except OSError:
            raise AssetError("web.asset_not_found", "no such asset") from None
        return AssetResult(path=resolved, content_type=content_type, body=body)
