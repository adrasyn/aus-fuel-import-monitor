import asyncio
import json
import ssl

import pytest

from pipeline import collector, orchestrator


class _FakeWS:
    """Websocket stub. Yields `frames`, then goes silent forever."""

    def __init__(self, frames=()):
        self.sent: list[str] = []
        self._frames = list(frames)

    async def send(self, payload):
        self.sent.append(payload)

    async def recv(self):
        if self._frames:
            return self._frames.pop(0)
        await asyncio.sleep(3600)  # never resolves; wait_for times out


class _FakeConnect:
    def __init__(self, ws):
        self._ws = ws

    async def __aenter__(self):
        return self._ws

    async def __aexit__(self, *exc_info):
        return False


def _patch_transport(monkeypatch, ws):
    monkeypatch.setattr(
        collector.websockets, "connect", lambda *a, **k: _FakeConnect(ws)
    )
    # Keep the test fast: tiny recv timeout and grace period.
    monkeypatch.setattr(collector, "_RECV_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(collector, "EMPTY_STREAM_GRACE_SECONDS", 0.3)


def test_collector_aborts_early_when_no_frames_arrive(monkeypatch, capsys):
    # AISStream outage: socket opens, subscription accepted, zero frames.
    # The collector must give up after the grace period rather than holding
    # the connection open for the full duration.
    ws = _FakeWS()
    _patch_transport(monkeypatch, ws)

    result = collector.run_collector("key", duration_seconds=30)

    assert result["vessels"] == []
    out = capsys.readouterr().out
    assert "No frames received" in out
    # Subscription was still sent, so this is a data-delivery failure, not a
    # connection failure.
    assert json.loads(ws.sent[0])["APIKey"] == "key"


def test_collector_does_not_abort_when_frames_are_flowing(monkeypatch, capsys):
    # A frame arrived, so the stream is alive — the early-abort path must not
    # trigger even though the stream later goes quiet.
    frame = json.dumps(
        {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 123456789, "latitude": -32.0, "longitude": 115.0},
            "Message": {"PositionReport": {"Sog": 12.0}},
        }
    )
    ws = _FakeWS(frames=[frame])
    _patch_transport(monkeypatch, ws)

    collector.run_collector("key", duration_seconds=1)

    out = capsys.readouterr().out
    assert "No frames received" not in out


class _FailedOpen:
    def __init__(self, error):
        self.error = error

    async def __aenter__(self):
        raise self.error

    async def __aexit__(self, *exc_info):
        raise AssertionError("never entered")


def _with_open_results(monkeypatch, results):
    opens, waits = [], []
    remaining = iter(results)

    def connect(url, *, ssl, open_timeout):
        opens.append((url, ssl, open_timeout))
        result = next(remaining)
        return _FailedOpen(result) if isinstance(result, Exception) else _FakeConnect(result)

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(collector.websockets, "connect", connect)
    monkeypatch.setattr(collector.asyncio, "sleep", sleep)
    return opens, waits


def _assert_verified_opens(opens, count):
    assert len(opens) == count
    for url, context, timeout in opens:
        assert url == collector.AISSTREAM_URL
        assert context.check_hostname
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert timeout == 10.0


def test_open_timeout_retries_verified_then_sends_once(monkeypatch):
    ws = _FakeWS()
    opens, waits = _with_open_results(monkeypatch, [TimeoutError(), TimeoutError(), ws])

    collector.run_collector("fixture-key", duration_seconds=0)

    _assert_verified_opens(opens, 3)
    assert waits == [1.0, 2.0]
    assert len(ws.sent) == 1
    assert json.loads(ws.sent[0])["APIKey"] == "fixture-key"


def test_open_timeouts_stop_after_three_attempts(monkeypatch):
    would_connect = _FakeWS()
    results = [TimeoutError(), TimeoutError(), TimeoutError(), would_connect]
    opens, waits = _with_open_results(monkeypatch, results)

    result = collector.run_collector("fixture-key", duration_seconds=0)

    _assert_verified_opens(opens, 3)
    assert waits == [1.0, 2.0]
    assert result["vessels"] == []
    assert would_connect.sent == []


@pytest.mark.parametrize("preceding", [[], [TimeoutError()]])
def test_bad_certificate_does_not_retry_or_send_and_keeps_last_good_snapshot(
    tmp_path, monkeypatch, capsys, preceding,
):
    would_connect = _FakeWS()
    opens, waits = _with_open_results(
        monkeypatch, [*preceding, ssl.SSLCertVerificationError("bad cert"), would_connect],
    )
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ports.json").write_text('{"ports": []}')
    snapshot = tmp_path / "data" / "snapshot.json"
    previous = (
        b'{"timestamp": "2026-11-22T00:38:00Z", '
        b'"vessels": [{"imo": "9000001", "name": "Last-good tanker"}]}'
    )
    snapshot.write_bytes(previous)
    monkeypatch.setattr(orchestrator, "_update_petroleum_stats", lambda: None)
    monkeypatch.setattr(orchestrator, "_update_mso_reserves", lambda: None)

    orchestrator.run_pipeline("fixture-key", duration_seconds=0)

    _assert_verified_opens(opens, len(preceding) + 1)
    assert waits == ([1.0] if preceding else [])
    assert would_connect.sent == []
    assert snapshot.read_bytes() == previous
    out = capsys.readouterr().out
    assert "certificate verification failed; subscription not sent" in out
    assert "Preserving last-good data" in out
    assert "fixture-key" not in out


def test_subscription_timeout_is_not_an_opening_timeout(monkeypatch):
    class SendTimeout(_FakeWS):
        async def send(self, payload):
            await super().send(payload)
            raise TimeoutError("send timed out")

    ws = SendTimeout()
    opens, waits = _with_open_results(monkeypatch, [ws, _FakeWS()])

    result = collector.run_collector("fixture-key", duration_seconds=0)

    _assert_verified_opens(opens, 1)
    assert waits == []
    assert len(ws.sent) == 1
    assert result["vessels"] == []
