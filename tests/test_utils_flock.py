from multiprocessing import Process, Value
import tempfile
import time
from unittest import mock
from os import path

import pytest
from buildrunner.utils import ContainerLogger, FailureToAcquireLockException, acquire_flock_open_read_binary, acquire_flock_open_write_binary, release_flock

@pytest.fixture(name="mock_logger")
def fixture_mock_logger():
    mock_logger = mock.create_autospec(ContainerLogger)
    mock_logger.write.side_effect = lambda message: print(message.strip())
    return mock_logger

def get_and_hold_lock(lock_file, sleep_seconds, exclusive=True, timeout_seconds=2):
    fd = None
    try:
        mock_logger = mock.create_autospec(ContainerLogger)
        mock_logger.write.side_effect = lambda message: print(message.strip())
        if exclusive:
            fd = acquire_flock_open_write_binary(lock_file=lock_file, logger=mock_logger, timeout_seconds=timeout_seconds)
        else:
            fd = acquire_flock_open_read_binary(lock_file=lock_file, logger=mock_logger, timeout_seconds=timeout_seconds)
        assert fd is not None
        time.sleep(sleep_seconds)
    finally:
        release_flock(fd, mock_logger)

def test_flock_aquire1(mock_logger):
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        try:
            fd = None
            lock_file = f'{tmp_dir_name}/mylock.file'
            fd = acquire_flock_open_write_binary(lock_file=lock_file, logger=mock_logger, timeout_seconds=1.0)
            assert fd is not None

        finally:
            if fd:
                release_flock(fd, mock_logger)

def test_flock_exclusive_aquire(mock_logger):
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        try:
            lock_file = f'{tmp_dir_name}/mylock.file'
            fd = None

            # Test exclusive followed by exclusive acquire
            p = Process(target=get_and_hold_lock, args=(lock_file, 4))
            p.start()
            time.sleep(1)
            with pytest.raises(FailureToAcquireLockException):
                fd = acquire_flock_open_write_binary(lock_file, mock_logger, timeout_seconds=1.0)
            assert fd is None
            p.join()

            # Test shared followed by exclusive acquire
            p = Process(target=get_and_hold_lock, args=(lock_file, 4, False))
            p.start()
            time.sleep(1)
            with pytest.raises(FailureToAcquireLockException):
                fd = acquire_flock_open_write_binary(lock_file, mock_logger, timeout_seconds=1.0)
            assert fd is None
            p.join()

            # Test exclusive followed by shared acquire
            p = Process(target=get_and_hold_lock, args=(lock_file, 4, True))
            p.start()
            time.sleep(1)
            with pytest.raises(FailureToAcquireLockException):
                fd = acquire_flock_open_read_binary(lock_file, mock_logger, timeout_seconds=1.0)
            assert fd is None
            p.join()

        finally:
            if fd:
                release_flock(fd, mock_logger)

def test_flock_release(mock_logger):
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        try:
            lock_file = f'{tmp_dir_name}/mylock.file'
            fd = None

            p = Process(target=get_and_hold_lock, args=(lock_file, 2))
            p.start()
            time.sleep(1)
            fd = acquire_flock_open_write_binary(lock_file, mock_logger, timeout_seconds=2.0)
            assert fd is not None
            p.join()
        finally:
            if fd:
                release_flock(fd, mock_logger)

def test_flock_aquire_exlusive_timeout(mock_logger):
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        try:
            lock_file = f'{tmp_dir_name}/mylock.file'
            fd = None

            # Test exclusive followed by exclusive acquire
            p = Process(target=get_and_hold_lock, args=(lock_file, 7))
            p.start()
            time.sleep(1)

            timeout_seconds = 5
            start_time = time.time()
            with pytest.raises(FailureToAcquireLockException):
                fd = acquire_flock_open_write_binary(lock_file, mock_logger, timeout_seconds=timeout_seconds)
            duration_seconds = time.time() - start_time
            tolerance_seconds = 0.6
            assert (timeout_seconds - tolerance_seconds) <= duration_seconds <= (timeout_seconds + tolerance_seconds)
            assert fd is None
            p.join()

            # Test exclusive followed by shared acquire
            p = Process(target=get_and_hold_lock, args=(lock_file, 7))
            p.start()
            time.sleep(1)

            timeout_seconds = 5
            start_time = time.time()
            with pytest.raises(FailureToAcquireLockException):
                fd = acquire_flock_open_read_binary(lock_file, mock_logger, timeout_seconds=timeout_seconds)
            duration_seconds = time.time() - start_time
            tolerance_seconds = 0.6
            assert (timeout_seconds - tolerance_seconds) <= duration_seconds <= (timeout_seconds + tolerance_seconds)
            assert fd is None
            p.join()

            # Test shared followed by exclusive acquire
            p = Process(target=get_and_hold_lock, args=(lock_file, 7, False))
            p.start()
            time.sleep(1)

            timeout_seconds = 5
            start_time = time.time()
            with pytest.raises(FailureToAcquireLockException):
                fd = acquire_flock_open_write_binary(lock_file, mock_logger, timeout_seconds=timeout_seconds)
            duration_seconds = time.time() - start_time
            tolerance_seconds = 0.6
            assert (timeout_seconds - tolerance_seconds) <= duration_seconds <= (timeout_seconds + tolerance_seconds)
            assert fd is None
            p.join()
        finally:
            if fd:
                release_flock(fd, mock_logger)

def test_flock_shared_aquire(mock_logger):
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        try:
            lock_file = f'{tmp_dir_name}/mylock.file'
            # Lock file needs to be created
            with open(lock_file,"w") as file:
                file.write("Test file.")
            fd = None
            p = Process(target=get_and_hold_lock, args=(lock_file, 5, False))
            p.start()
            time.sleep(1)
            fd = acquire_flock_open_read_binary(lock_file, mock_logger, timeout_seconds=1.0)
            assert fd is not None
            p.join()
        finally:
            if fd:
                release_flock(fd, mock_logger)
