import asyncio
import json

from pipeline import collector


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
    monkeypatch.setattr(collector, "_aisstream_cert_verifies", lambda: True)
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
