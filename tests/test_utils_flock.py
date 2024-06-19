from multiprocessing import Process, Event
import time
from unittest import mock

import pytest
from buildrunner.utils import (
    FailureToAcquireLockException,
    acquire_flock_open_read_binary,
    acquire_flock_open_write_binary,
    release_flock,
)


@pytest.fixture(name="mock_logger")
def fixture_mock_logger():
    mock_logger = mock.MagicMock()
    mock_logger.info.side_effect = lambda message: print(f"[info] {message}")
    mock_logger.warning.side_effect = lambda message: print(f"[warning] {message}")
    return mock_logger


def _get_and_hold_lock(
    ready_event: Event, done_event: Event, lock_file, exclusive=True, timeout_seconds=2
):
    fd = None
    mock_logger = mock.MagicMock()
    mock_logger.info.side_effect = lambda message: print(
        f"[get-and-hold-info] {message}"
    )
    mock_logger.warning.side_effect = lambda message: print(
        f"[get-and-hold-warning] {message}"
    )
    try:
        if exclusive:
            fd = acquire_flock_open_write_binary(
                lock_file=lock_file, logger=mock_logger, timeout_seconds=timeout_seconds
            )
        else:
            fd = acquire_flock_open_read_binary(
                lock_file=lock_file, logger=mock_logger, timeout_seconds=timeout_seconds
            )
        assert fd is not None
        print(
            f"Acquired lock for file {lock_file} in background process (exclusive={exclusive})"
        )
        ready_event.set()
        done_event.wait()
    finally:
        release_flock(fd, mock_logger)


def _wait_and_set(event: Event, sleep_seconds: float):
    time.sleep(sleep_seconds)
    event.set()


def test_flock_acquire1(mock_logger, tmp_path):
    try:
        fd = None
        lock_file = str(tmp_path / "mylock.file")
        fd = acquire_flock_open_write_binary(
            lock_file=lock_file, logger=mock_logger, timeout_seconds=1.0
        )
        assert fd is not None

    finally:
        if fd:
            release_flock(fd, mock_logger)


def test_flock_exclusive_acquire(mock_logger, tmp_path):
    try:
        lock_file = str(tmp_path / "mylock.file")
        fd = None

        # Test exclusive followed by exclusive acquire
        ready_event = Event()
        done_event = Event()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file)
        )
        p.start()
        ready_event.wait()

        with pytest.raises(FailureToAcquireLockException):
            fd = acquire_flock_open_write_binary(
                lock_file, mock_logger, timeout_seconds=1.0
            )
        assert fd is None
        done_event.set()
        p.join()

        # Test shared followed by exclusive acquire
        ready_event.clear()
        done_event.clear()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file, False)
        )
        p.start()
        ready_event.wait()

        with pytest.raises(FailureToAcquireLockException):
            fd = acquire_flock_open_write_binary(
                lock_file, mock_logger, timeout_seconds=1.0
            )
        assert fd is None
        done_event.set()
        p.join()

        # Test exclusive followed by shared acquire
        ready_event.clear()
        done_event.clear()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file, True)
        )
        p.start()
        ready_event.wait()

        with pytest.raises(FailureToAcquireLockException):
            fd = acquire_flock_open_read_binary(
                lock_file, mock_logger, timeout_seconds=1.0
            )
        assert fd is None
        done_event.set()
        p.join()

    finally:
        if fd:
            release_flock(fd, mock_logger)


def test_flock_release(mock_logger, tmp_path):
    fd = None
    try:
        lock_file = str(tmp_path / "mylock.file")

        ready_event = Event()
        done_event = Event()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file)
        )
        p.start()
        ready_event.wait()
        p2 = Process(target=_wait_and_set, args=(done_event, 1.0))
        p2.start()

        fd = acquire_flock_open_write_binary(
            lock_file, mock_logger, timeout_seconds=5.0
        )
        assert fd is not None
        p.join()
        p2.join()
    finally:
        if fd:
            release_flock(fd, mock_logger)


def test_flock_acquire_exclusive_timeout(mock_logger, tmp_path):
    try:
        lock_file = str(tmp_path / "mylock.file")
        fd = None

        # Test exclusive followed by exclusive acquire
        ready_event = Event()
        done_event = Event()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file)
        )
        p.start()
        ready_event.wait()

        timeout_seconds = 5
        start_time = time.time()
        with pytest.raises(FailureToAcquireLockException):
            fd = acquire_flock_open_write_binary(
                lock_file, mock_logger, timeout_seconds=timeout_seconds
            )
        duration_seconds = time.time() - start_time
        tolerance_seconds = 0.6
        assert (
            (timeout_seconds - tolerance_seconds)
            <= duration_seconds
            <= (timeout_seconds + tolerance_seconds)
        )
        assert fd is None
        done_event.set()
        p.join()

        # Test exclusive followed by shared acquire
        ready_event.clear()
        done_event.clear()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file)
        )
        p.start()
        ready_event.wait()

        timeout_seconds = 5
        start_time = time.time()
        with pytest.raises(FailureToAcquireLockException):
            fd = acquire_flock_open_read_binary(
                lock_file, mock_logger, timeout_seconds=timeout_seconds
            )
        duration_seconds = time.time() - start_time
        tolerance_seconds = 0.6
        assert (
            (timeout_seconds - tolerance_seconds)
            <= duration_seconds
            <= (timeout_seconds + tolerance_seconds)
        )
        assert fd is None
        done_event.set()
        p.join()

        # Test shared followed by exclusive acquire
        ready_event.clear()
        done_event.clear()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file, False)
        )
        p.start()
        ready_event.wait()

        timeout_seconds = 5
        start_time = time.time()
        with pytest.raises(FailureToAcquireLockException):
            fd = acquire_flock_open_write_binary(
                lock_file, mock_logger, timeout_seconds=timeout_seconds
            )
        duration_seconds = time.time() - start_time
        tolerance_seconds = 0.6
        assert (
            (timeout_seconds - tolerance_seconds)
            <= duration_seconds
            <= (timeout_seconds + tolerance_seconds)
        )
        assert fd is None
        done_event.set()
        p.join()
    finally:
        if fd:
            release_flock(fd, mock_logger)


def test_flock_shared_acquire(mock_logger, tmp_path):
    try:
        lock_file = str(tmp_path / "mylock.file")
        # Lock file needs to be created
        with open(lock_file, "w") as file:
            file.write("Test file.")
        fd = None
        ready_event = Event()
        done_event = Event()
        p = Process(
            target=_get_and_hold_lock, args=(ready_event, done_event, lock_file, False)
        )
        p.start()
        ready_event.wait()
        fd = acquire_flock_open_read_binary(lock_file, mock_logger, timeout_seconds=1.0)
        assert fd is not None
        done_event.set()
        p.join()
    finally:
        if fd:
            release_flock(fd, mock_logger)
