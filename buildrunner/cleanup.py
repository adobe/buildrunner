"""
Copyright 2026 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import atexit
import os
import signal
import sys

# Global registry of container IDs started by this buildrunner process.
# Used by the signal handler to force-remove containers on abort.
#
# Design notes:
# - No threading.Lock: signal handlers in Python run in the main thread and
#   must not acquire locks (deadlock risk). Python's GIL makes list.append()
#   and list snapshot (list(...)) atomic enough for this use case.
# - No logging in signal handler: logging acquires internal locks.
# - _cleanup_done is a simple bool flag; only the main thread writes it.

_registered_containers: list[str] = []
_docker_client = None
_cleanup_done = False


def set_docker_client(client) -> None:
    """Set the Docker client used for cleanup. Call from main thread after client init."""
    global _docker_client
    _docker_client = client


def register_container(container_id: str) -> None:
    """Register a container for cleanup on signal/exit."""
    if container_id and container_id not in _registered_containers:
        _registered_containers.append(container_id)


def unregister_container(container_id: str) -> None:
    """Unregister a container after successful removal."""
    try:
        _registered_containers.remove(container_id)
    except ValueError:
        pass


def _force_cleanup_all() -> None:
    """Force-remove all registered containers.

    Called from:
    - atexit hook (normal exit, unhandled exception)
    - signal handler (SIGTERM/SIGINT from CI system aborting the build)

    Safe to call multiple times; only the first call does work.
    """
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True

    # Snapshot the list — no lock needed, GIL protects list copy
    containers = list(_registered_containers)
    if not containers:
        return

    client = _docker_client
    if not client:
        try:
            import docker as docker_module

            client = docker_module.from_env()
        except Exception:
            # No way to reach Docker — print to stderr (signal-safe)
            print(
                f"buildrunner cleanup: cannot create Docker client, "
                f"{len(containers)} container(s) may be orphaned",
                file=sys.stderr,
            )
            return

    print(
        f"buildrunner cleanup: removing {len(containers)} container(s)",
        file=sys.stderr,
    )

    for cid in containers:
        try:
            client.remove_container(cid, force=True, v=True)
        except Exception:
            # Container may already be removed by normal cleanup — that's fine
            pass


def _signal_handler(signum, _frame):
    """Handle SIGTERM/SIGINT by cleaning up containers then exiting.

    Avoids logging, locks, and complex operations to remain signal-safe.
    Uses os._exit() instead of sys.exit() to prevent finally blocks from
    running (which would race with the cleanup we just did).
    """
    _force_cleanup_all()
    # os._exit() skips finally blocks and atexit — we already cleaned up
    os._exit(128 + signum)


def install_signal_handlers() -> None:
    """Install SIGTERM/SIGINT handlers and atexit hook for container cleanup."""
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    atexit.register(_force_cleanup_all)
