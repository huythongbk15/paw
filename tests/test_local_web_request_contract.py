"""Request identity and reconnect semantics for the local web surface.

Two rules the surface has to honour, both from the B-23..B-26 contract:

* a request key must resolve to the **durable operation identity** the
  runtime already records, so a retry, a double click and a reconnect are
  all the *same* operation - and there is no new in-memory dedup map
  claiming restart safety it cannot have;
* a disconnect is **neither a completion nor a cancellation**. A
  reconnect inspects the durable task; it never re-runs an effect, and
  it never marks a task finished because the browser went away.
"""

from __future__ import annotations

import pytest

from paw.web import (
    ReconnectAction,
    ReconnectPolicy,
    RequestKeyPolicy,
    WebRequest,
    WebRequestKeyError,
)


# ── 1. The request key ──────────────────────────────────────────────────


class TestTheRequestKey:
    def test_a_valid_key_is_accepted(self):
        policy = RequestKeyPolicy()
        assert policy.validate("req-key-0001") == "req-key-0001"

    def test_a_missing_key_is_refused(self):
        with pytest.raises(WebRequestKeyError) as exc:
            RequestKeyPolicy().validate(None)
        assert exc.value.code == "web.request_key_missing"

    def test_an_empty_key_is_refused(self):
        with pytest.raises(WebRequestKeyError) as exc:
            RequestKeyPolicy().validate("   ")
        assert exc.value.code == "web.request_key_missing"

    def test_a_short_key_is_refused(self):
        with pytest.raises(WebRequestKeyError) as exc:
            RequestKeyPolicy().validate("abc")
        assert exc.value.code == "web.request_key_too_short"

    def test_a_long_key_is_refused(self):
        with pytest.raises(WebRequestKeyError) as exc:
            RequestKeyPolicy().validate("x" * 200)
        assert exc.value.code == "web.request_key_too_long"

    def test_a_malformed_key_is_refused(self):
        for key in ("has space here", "semi;colon", "quote'xyz", "new\nline"):
            with pytest.raises(WebRequestKeyError) as exc:
                RequestKeyPolicy().validate(key)
            assert exc.value.code == "web.request_key_malformed", key

    def test_a_refusal_never_echoes_the_key(self):
        """A key is application-supplied text; it may carry something."""
        with pytest.raises(WebRequestKeyError) as exc:
            RequestKeyPolicy().validate("has secret value here")
        assert "secret value" not in str(exc.value)


# ── 2. The operation identity ───────────────────────────────────────────


class TestTheOperationIdentity:
    def test_the_same_key_gives_the_same_identity(self):
        policy = RequestKeyPolicy()
        first = policy.operation_identity("task-1", "req-key-0001")
        second = policy.operation_identity("task-1", "req-key-0001")
        assert first == second

    def test_a_different_key_gives_a_different_identity(self):
        policy = RequestKeyPolicy()
        assert policy.operation_identity("task-1", "req-key-0001") != \
            policy.operation_identity("task-1", "req-key-0002")

    def test_a_different_task_gives_a_different_identity(self):
        policy = RequestKeyPolicy()
        assert policy.operation_identity("task-1", "req-key-0001") != \
            policy.operation_identity("task-2", "req-key-0001")

    def test_the_identity_carries_the_task_and_the_key(self):
        identity = RequestKeyPolicy().operation_identity("task-1", "req-key-0001")
        assert "task-1" in identity
        assert "req-key-0001" in identity


# ── 3. The reconnect rules ──────────────────────────────────────────────


class TestTheReconnect:
    def test_a_running_task_is_inspected(self):
        """A disconnect is not a completion: the work is still running."""
        assert ReconnectPolicy().action_for("running") is ReconnectAction.INSPECT

    def test_a_completed_task_is_reported(self):
        assert ReconnectPolicy().action_for("completed") is ReconnectAction.COMPLETED

    def test_a_failed_task_is_reported(self):
        assert ReconnectPolicy().action_for("failed") is ReconnectAction.FAILED

    def test_a_cancelled_task_is_reported_as_failed(self):
        assert ReconnectPolicy().action_for("cancelled") is ReconnectAction.FAILED

    def test_a_task_waiting_for_a_human_is_reported_as_such(self):
        assert ReconnectPolicy().action_for("running", waiting_for_approval=True) \
            is ReconnectAction.AWAIT_APPROVAL

    def test_an_unknown_status_is_inspected_not_assumed_complete(self):
        """An unfamiliar status must not be read as success."""
        for status in ("", "wat", "something-new"):
            assert ReconnectPolicy().action_for(status) is ReconnectAction.INSPECT


class TestWhatMayBeRetried:
    def test_only_a_failed_task_may_be_retried(self):
        policy = ReconnectPolicy()
        for status in ("running", "completed", "paused"):
            action = policy.action_for(status)
            assert policy.may_retry(action, same_request_key=True) is False, status

    def test_a_failed_task_is_retried_only_with_the_same_key(self):
        policy = ReconnectPolicy()
        action = policy.action_for("failed")
        assert policy.may_retry(action, same_request_key=True) is True
        assert policy.may_retry(action, same_request_key=False) is False

    def test_a_disconnect_is_never_a_retry(self):
        """The client going away is not a failure of the work."""
        policy = ReconnectPolicy()
        action = policy.action_for("running")
        assert policy.may_retry(action, same_request_key=True) is False


# ── 4. The request shape ───────────────────────────────────────────────


class TestTheRequest:
    def test_a_mutation_is_recognised(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert WebRequest(method=method, path="/x").is_mutation is True
        for method in ("GET", "HEAD", "OPTIONS"):
            assert WebRequest(method=method, path="/x").is_mutation is False

    def test_a_body_defaults_to_empty(self):
        assert WebRequest(method="GET", path="/x").body == {}
