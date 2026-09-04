# E1-06 Incremental Changed/Unchanged/Deleted Source Detection

This document is the **E1-06 deliverable**. It defines
the contract for the `compute_checksum` and
`diff_sources` operations that turn a fresh filesystem
scan into a 3-way classification the runtime can use
to drive *incremental* ingestion: only re-process the
files whose content actually changed.

## Why this contract exists

The E1-05 `scan_repo` returns a list of repo-relative
POSIX paths. The runtime needs to know *which of those
paths are new*, *which are unchanged since the last
sync*, and *which persisted sources have disappeared
from disk* — without re-reading every file. A full
re-ingest on every change is O(total corpus) and
defeats the local-first / context-efficient
acceptance target the roadmap lists; an incremental
diff is O(changed set).

The state of the art today (E1-05 + E1-02) is that
every `KnowledgeSource` row carries a `checksum`
(content hash) and a `last_sync` (sync timestamp).
E1-06 closes the loop: a function that compares a
fresh scan against the persisted rows and returns a
`SourceDiff` whose four buckets are the input to the
runtime's incremental ingestion loop.

## Canonical location

`compute_checksum` and `SourceDiff` live in
`paw.knowledge.source` (the existing module that owns
`KnowledgeSource` and `KnowledgeSourceManager`). The
new function `diff_sources` lives in the same module.
A small `compute_checksum` helper is added to
`paw.knowledge.checksum` (a new tiny module) so the
hashing logic is shared between `diff_sources` and the
future E1-08 bounded tree view.

## `compute_checksum` contract

```python
def compute_checksum(file_path: str | Path) -> str:
    """Return the SHA-256 hex digest of ``file_path``'s
    content.

    The file is read in 64 KiB chunks; a 1 GiB file
    takes ~250 ms on a modern disk and the memory
    footprint stays bounded. The function returns a
    lowercase 64-character hex string; an empty file
    returns the SHA-256 of the empty string
    (``e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855``).

    The function refuses to follow symlinks; a symlink
    path raises ``ValueError`` (the same fail-closed
    posture the E1-05 scanner takes). Non-existent
    files raise ``FileNotFoundError``. A directory path
    raises ``ValueError`` (a directory's "content" is
    not a single hash).
    """
```

The function is pure: same file content → same hash.
The contract test pins (a) deterministic output, (b)
the empty-file hash, (c) symlink rejection, (d)
non-existent file, (e) directory path.

## `SourceDiff` shape

```python
@dataclass(frozen=True)
class SourceDiff:
    """The 3-way classification of a fresh scan against
    the persisted source rows.

    Each bucket is a list; the lists are non-overlapping
    (a path is in exactly one bucket). The total length
    of ``unchanged + changed + new`` equals the number
    of files in the fresh scan; the total length of
    ``unchanged + changed + deleted`` equals the number
    of sources in the persisted set the caller asked
    about.
    """
    new: list[DiffNew]            # on disk, not in DB
    changed: list[DiffChanged]     # on disk + in DB, checksum differs
    unchanged: list[DiffUnchanged] # on disk + in DB, checksum same
    deleted: list[DiffDeleted]     # in DB, not on disk
```

Each bucket is a small dataclass that carries the
information the ingestion loop needs without forcing
the caller to re-read the DB or the disk:

| Bucket | Dataclass | Fields |
|---|---|---|
| `new` | `DiffNew` | `path: str`, `sha256: str` |
| `changed` | `DiffChanged` | `source: KnowledgeSource` (old row), `new_sha256: str` |
| `unchanged` | `DiffUnchanged` | `source: KnowledgeSource` |
| `deleted` | `DiffDeleted` | `source: KnowledgeSource` |

`new_sha256` is the freshly-computed hash; the caller
stores it back via `KnowledgeSourceManager.update_checksum`
(added in E1-06) when the new chunks land.

## `diff_sources` signature

```python
async def diff_sources(
    scan_paths: list[str],
    persisted: list[KnowledgeSource],
) -> SourceDiff:
    """Classify ``scan_paths`` against ``persisted``.

    The function reads the file content for every
    *new* path (to compute the SHA-256 the caller will
    store back) and for every *changed* path (to know
    what changed). The function does **not** read
    unchanged files — that is the incremental
    optimization. The function is deterministic:
    same input → same output bucket membership, same
    hashes.

    The matching is by ``source.path`` (the persisted
    row's ``path`` field); a path that is in
    ``scan_paths`` but not in any persisted row's
    ``path`` is ``new``; a persisted row whose ``path``
    is not in ``scan_paths`` is ``deleted``; a
    persisted row whose ``path`` is in ``scan_paths``
    is ``changed`` (if the on-disk SHA differs from
    the persisted ``checksum``) or ``unchanged``
    (if the SHA matches).
    """
```

`scan_paths` is the result of `scan_repo` (E1-05):
already-filtered, already-deterministic, already-sorted
repo-relative POSIX paths. The diff function does not
re-walk; it accepts the list as-is.

`persisted` is the caller's snapshot of the relevant
`KnowledgeSource` rows (typically the rows whose
`path` is in `scan_paths`; the function does not
require this but the caller's query is more efficient
when it is).

## Manager additions

`KnowledgeSourceManager` gains two small methods that
the incremental loop calls after the diff:

- `update_checksum(source_id, new_sha256, *, last_sync=None)`
  — atomically writes the new checksum (and an
  optional `last_sync` timestamp) and clears any
  `invalidated_at` whose reason was
  `checksum_mismatch`. The new checksum is the input
  the diff function returns; the caller is the
  ingestion loop, not the diff function itself.
- `mark_path_missing(source_id)` — calls
  `mark_invalid(source_id, "path_missing")` (the
  E1-02 closed reason set) so the deleted-bucket
  ingestion loop has a one-liner.

## Negative cases

| Case | What the test does | Expected result |
|---|---|---|
| Empty scan + empty persisted | Both inputs are empty. | All four buckets are `[]`; `len(SourceDiff) == 0`. |
| Empty scan + non-empty persisted | Three persisted sources, scan finds nothing. | All three sources land in `deleted`; `new` / `changed` / `unchanged` are `[]`. |
| Non-empty scan + empty persisted | Three scan paths, no persisted rows. | All three land in `new` with their SHA-256. |
| One changed file | Persisted row with `checksum=old`; scan finds same path with new content. | The row is in `changed`; `new_sha256` is the new SHA; other rows in `unchanged` stay in `unchanged`. |
| One unchanged file | Persisted row with `checksum=matching`; scan finds same path. | The row is in `unchanged`; the file is *not* re-read. |
| Mixed: new + changed + unchanged + deleted | Four persisted rows; scan finds three of them (one unchanged, one changed, one new). | One `deleted`, one `new`, one `changed`, one `unchanged`. |
| Determinism | Two calls with the same inputs. | The two `SourceDiff` instances are equal (same bucket membership, same hashes). |

## Phase 4 sync contract

This document is the **source of truth** for E1-06.
The companion contract test
`tests/test_e1_06_source_diff_contract.py` enforces
the cases above plus the `compute_checksum` contract.

A later E1 item that adds another diff bucket (e.g.
"renamed") must update both this spec and the contract
test in the same change.