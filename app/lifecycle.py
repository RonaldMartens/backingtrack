"""Levensduur van de server: netjes stoppen, en automatisch stoppen als er geen browser meer open is.

Elke geopende pagina stuurt periodiek een 'heartbeat' (en bij sluiten een 'bye').
Is er een tijdje geen enkele pagina meer open en wordt er niets gegenereerd, dan stopt de server.

Instellingen (omgevingsvariabelen):
  BACKINGTRACK_AUTO_STOP=0            automatisch stoppen uitzetten (bv. voor een iOS-app zonder browser)
  BACKINGTRACK_AUTO_STOP_TIMEOUT=180  seconden zonder heartbeat voordat een pagina als 'weg' geldt
  BACKINGTRACK_AUTO_STOP_GRACE=10     seconden wachten na het sluiten van de laatste pagina
  BACKINGTRACK_AUTO_STOP_IDLE=300     stoppen als er na het starten nooit een pagina verbinding maakte
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import time
from contextlib import contextmanager

log = logging.getLogger("backingtrack")

ENABLED = os.environ.get("BACKINGTRACK_AUTO_STOP", "1") != "0"
TIMEOUT = float(os.environ.get("BACKINGTRACK_AUTO_STOP_TIMEOUT", "180"))
GRACE = float(os.environ.get("BACKINGTRACK_AUTO_STOP_GRACE", "10"))
IDLE = float(os.environ.get("BACKINGTRACK_AUTO_STOP_IDLE", "300"))

_lock = threading.Lock()
_clients: dict[str, float] = {}
_seen_any = False
_last_event = time.monotonic()
_started = time.monotonic()
_busy = 0
_stopping = False


def request_shutdown(delay: float = 0.4) -> None:
    """Geef uvicorn een nette stop-opdracht (na korte vertraging, zodat het antwoord nog verstuurd wordt)."""
    global _stopping
    with _lock:
        if _stopping:
            return
        _stopping = True
    threading.Timer(delay, lambda: os.kill(os.getpid(), signal.SIGINT)).start()


def heartbeat(client: str) -> None:
    global _seen_any, _last_event
    with _lock:
        _clients[client[:64]] = time.monotonic()
        _seen_any = True
        _last_event = time.monotonic()


def bye(client: str) -> None:
    global _last_event
    with _lock:
        _clients.pop(client[:64], None)
        _last_event = time.monotonic()


@contextmanager
def busy():
    """Zolang er gegenereerd wordt, nooit automatisch stoppen."""
    global _busy, _last_event
    with _lock:
        _busy += 1
    try:
        yield
    finally:
        with _lock:
            _busy -= 1
            _last_event = time.monotonic()


def status() -> dict:
    now = time.monotonic()
    with _lock:
        alive = sum(1 for t in _clients.values() if now - t < TIMEOUT)
        return {"auto_stop": ENABLED, "open_pages": alive, "busy": _busy > 0}


def _should_stop(now: float) -> bool:
    with _lock:
        if _busy or _stopping:
            return False
        if not _seen_any:
            return now - _started > IDLE
        alive = [c for c, t in _clients.items() if now - t < TIMEOUT]
        return not alive and now - _last_event >= GRACE


def _watchdog() -> None:
    while True:
        time.sleep(2)
        if _should_stop(time.monotonic()):
            log.warning("Geen geopende BackingTrack-pagina meer: server stopt automatisch.")
            print("BackingTrack: geen geopende pagina meer, server stopt automatisch.", flush=True)
            request_shutdown(0)
            return


def start_watchdog() -> None:
    if ENABLED:
        threading.Thread(target=_watchdog, name="auto-stop", daemon=True).start()
