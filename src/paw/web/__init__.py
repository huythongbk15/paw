"""PAW local web surface.

The local web adapter is a **presentation adapter** over the existing
application services. It is not a second agent core, not a second
runtime and not a new orchestration authority: the browser reaches the
same Task, decision, Plan, policy gate, executors, ledger and
checkpoints that the CLI and the TUI reach.

Nothing in here is imported by ``paw.core``. The security boundary in
:mod:`paw.web.security` is transport-agnostic on purpose, so its rules
are provable without standing up a server and the HTTP framework stays
an open decision (see ``docs/adr/0001-local-web-adapter.md``).
"""

from .requests import (
    ReconnectAction,
    ReconnectPolicy,
    RequestKeyPolicy,
    WebRequest,
    WebRequestKeyError,
)
from .security import (
    LocalWebGuard,
    WebSecurityCode,
    WebSecurityConfig,
    WebSecurityError,
    default_allowed_hosts,
)

__all__ = [
    "LocalWebGuard",
    "ReconnectAction",
    "ReconnectPolicy",
    "RequestKeyPolicy",
    "WebRequest",
    "WebRequestKeyError",
    "WebSecurityCode",
    "WebSecurityConfig",
    "WebSecurityError",
    "default_allowed_hosts",
]
