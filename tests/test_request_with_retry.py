"""
util.request_with_retry — see snapshot.py's main() and store.py's _log_run/
_log_decisions, which previously called requests.post(...).raise_for_status()
directly and crashed the whole run on a single transient Supabase timeout
(observed repeatedly as ReadTimeout on the once-a-minute snapshot workflows).
"""
import requests

from util import request_with_retry


class _FakeResponse:
    def raise_for_status(self):
        pass


def test_succeeds_on_first_try_without_sleeping(monkeypatch):
    calls = []
    monkeypatch.setattr("time.sleep", lambda s: calls.append(s))

    def method(url, **kwargs):
        return _FakeResponse()

    resp = request_with_retry(method, "https://example.invalid")
    assert isinstance(resp, _FakeResponse)
    assert calls == []


def test_retries_on_timeout_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    attempts = {"n": 0}

    def method(url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise requests.exceptions.ReadTimeout("boom")
        return _FakeResponse()

    resp = request_with_retry(method, "https://example.invalid", retries=2)
    assert isinstance(resp, _FakeResponse)
    assert attempts["n"] == 3
    assert len(sleeps) == 2


def test_raises_last_exception_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def method(url, **kwargs):
        raise requests.exceptions.ConnectionError("still down")

    try:
        request_with_retry(method, "https://example.invalid", retries=2)
        assert False, "expected ConnectionError to propagate"
    except requests.exceptions.ConnectionError:
        pass


def test_non_transient_error_is_not_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    attempts = {"n": 0}

    def method(url, **kwargs):
        attempts["n"] += 1
        raise ValueError("not a network error")

    try:
        request_with_retry(method, "https://example.invalid", retries=2)
        assert False, "expected ValueError to propagate"
    except ValueError:
        pass
    assert attempts["n"] == 1
