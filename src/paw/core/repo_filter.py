"""PAW Core — deterministic include/exclude rules for repository files (E1-04).

The ``RepoFilter`` is the single owner of the rule schema
and the matching algorithm. ``ContextCompiler`` consults
it when assembling repository candidates; the E1-08
bounded tree view and the E1-17 manifest inspection use
the same object so a reviewer can reproduce "which
files are eligible" byte-for-byte.

The filter is a pure function over a closed set of
inputs. Two calls with the same input list and the same
``RepoFilter`` produce the same output list, in the same
order, byte-identical. The contract test pins that.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

# Default exclude patterns shipped with PAW. The contract
# test pins the literal set; adding a new default-exclude
# is a change-control surface.
SAFE_DEFAULT_EXCLUDES: tuple[str, ...] = (
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    "*.pyc",
    "*.tmp",
    "*.pyo",
    "*.swp",
)


def _is_safe_pattern(pattern: str) -> bool:
    """True iff ``pattern`` is a non-empty repository-relative
    POSIX glob (no leading ``/``, no ``..`` segments).

    The check is the construction-time hardening for the
    adversarial cases the Architecture lists. A pattern
    that is empty, absolute, or escapes the repo is a
    contract violation the constructor must reject.
    """
    if not pattern:
        return False
    if pattern.startswith("/"):
        return False
    if pattern == ".":
        return False
    # ``PurePosixPath`` treats ``..`` as a normal part;
    # walk the parts and reject any literal "..".
    parts = PurePosixPath(pattern).parts
    return not any(part == ".." for part in parts)


def _is_safe_rel_path(rel_path: str) -> bool:
    """True iff ``rel_path`` is a non-empty repository-relative
    POSIX path (no leading ``/``, no ``..`` segments, not
    ``.`` or ``./``). Used by ``match`` to fail-closed on
    untrusted input."""
    if not rel_path:
        return False
    if rel_path.startswith("/"):
        return False
    if rel_path == "." or rel_path.startswith("./"):
        return False
    parts = PurePosixPath(rel_path).parts
    return not any(part == ".." for part in parts)


def _pattern_matches(pattern: str, full_path: str, parts: tuple[str, ...]) -> bool:
    """True iff ``pattern`` matches ``full_path`` either
    directly (``fnmatch`` against the full string) or as a
    path-component match (when the pattern has no ``/``,
    ``fnmatch`` is also tried against each component).

    The two-mode match is what makes the safe-default
    excludes behave like directory-component filters: a
    path like ``src/__pycache__/foo.py`` is rejected by
    the ``__pycache__`` pattern because ``__pycache__``
    is one of the path's components.
    """
    if fnmatch.fnmatch(full_path, pattern):
        return True
    if "/" not in pattern:
        for component in parts:
            if fnmatch.fnmatch(component, pattern):
                return True
    return False


@dataclass(frozen=True)
class RepoFilter:
    """Deterministic include/exclude matcher for repository files.

    Frozen so the object is hashable; the contract test
    asserts that two ``RepoFilter`` instances with the same
    field values compare equal and produce the same
    ``filter_paths`` output.
    """

    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    max_files: int = 200
    max_depth: int = 8

    def __post_init__(self) -> None:
        if self.max_files <= 0:
            raise ValueError(
                f"RepoFilter.max_files must be > 0; got {self.max_files}"
            )
        if self.max_depth <= 0:
            raise ValueError(
                f"RepoFilter.max_depth must be > 0; got {self.max_depth}"
            )
        for pat in self.include_patterns:
            if not _is_safe_pattern(pat):
                raise ValueError(
                    f"RepoFilter include pattern is unsafe: {pat!r} "
                    f"(must be non-empty, repo-relative, no '..')"
                )
        for pat in self.exclude_patterns:
            if not _is_safe_pattern(pat):
                raise ValueError(
                    f"RepoFilter exclude pattern is unsafe: {pat!r} "
                    f"(must be non-empty, repo-relative, no '..')"
                )

    @classmethod
    def safe_default(cls) -> RepoFilter:
        """Return the fail-closed default filter.

        Rejects the common build-output / VCS / venv
        directories and a small set of binary / temp
        extensions. The exact set is pinned by the
        contract test; the runtime uses this when the
        context plan sets ``include_repo=True`` but does
        not provide an explicit ``RepoFilter``.
        """
        return cls(exclude_patterns=SAFE_DEFAULT_EXCLUDES)

    def match(self, rel_path: str) -> bool:
        """Return True iff ``rel_path`` is eligible.

        The function never raises on input; untrusted or
        malformed paths return ``False`` (fail-closed).
        Excludes are evaluated after includes; a path that
        matches any exclude pattern is rejected regardless
        of includes.

        For an exclude or include pattern that does not
        contain a ``/``, the matcher also tries a
        path-component match: the pattern is matched
        against each path component individually. This is
        what makes the safe-default excludes
        (``__pycache__``, ``.git``, ``.venv``,
        ``node_modules``) reject a path that contains the
        pattern as any directory component, not only when
        the pattern matches the full path string.
        """
        if not _is_safe_rel_path(rel_path):
            return False
        # Depth check (path parts, not counting the empty
        # leading part from a relative POSIX path).
        parts = PurePosixPath(rel_path).parts
        if len(parts) > self.max_depth:
            return False
        # Include check: empty includes mean "match all".
        if self.include_patterns and not any(
            _pattern_matches(pat, rel_path, parts) for pat in self.include_patterns
        ):
            return False
        # Exclude check: any match rejects.
        return all(
            not _pattern_matches(pat, rel_path, parts) for pat in self.exclude_patterns
        )

    def filter_paths(self, paths: Iterable[str]) -> list[str]:
        """Apply ``match`` to every path and return the survivors.

        The result is sorted lexicographically by
        ``pathlib.PurePosixPath`` (so the ordering is
        deterministic across runs and platforms), capped
        at ``max_files`` entries. A single ``ValueError`` is
        raised if the input contains a duplicate path; the
        dedup is the reviewer's expectation and a
        duplicate is a contract violation worth surfacing.
        """
        seen: set[str] = set()
        out: list[str] = []
        for p in paths:
            if p in seen:
                raise ValueError(
                    f"RepoFilter.filter_paths received duplicate path: {p!r}"
                )
            seen.add(p)
            if self.match(p):
                out.append(p)
        out.sort(key=lambda s: (PurePosixPath(s).parts, s))
        return out[: self.max_files]


__all__ = ["SAFE_DEFAULT_EXCLUDES", "RepoFilter"]
