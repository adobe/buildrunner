"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from collections import OrderedDict
from datetime import datetime
import io
import logging
import os
import re
import sys
import uuid
import portalocker
import timeout_decorator
import yaml.resolver
import yaml.scanner
import glob
import hashlib
from typing import Optional, Tuple

from buildrunner import loggers
from buildrunner.errors import BuildRunnerConfigurationError


LOCK_TIMEOUT_SECONDS = 1800.0
LOGGER = logging.getLogger(__name__)


class FailureToAcquireLockException(Exception):
    """
    Raised when there is failure to acquire file lock
    """

    pass


class OrderedLoader(yaml.Loader):  # pylint: disable=too-many-ancestors
    """
    Custom loader class that preserves dictionary order.
    """

    pass


def construct_mapping(loader, node):
    """
    :param loader:
    :param node:
    """
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))


OrderedLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
)
# Tell YAML how to dump the OrderedDict
yaml.add_representer(
    OrderedDict,
    lambda dumper, data: dumper.represent_dict(iter(data.items())),
)
yaml.add_representer(
    OrderedDict,
    lambda dumper, data: dumper.represent_dict(iter(data.items())),
    Dumper=yaml.SafeDumper,
)


class IgnoreAliasesDumper(yaml.Dumper):  # pylint: disable=too-many-ancestors
    """
    Custom dumper class that removes aliases.
    """

    def ignore_aliases(self, data):
        return True


def load_config(stream, cfg_file):
    """
    Load yaml while preserving the order of attributes in maps/dictionaries and
    removing any aliases.
    """
    # run the data through pyyaml again to remove any aliases
    try:
        return yaml.load(
            yaml.dump(
                yaml.load(stream, OrderedLoader),
                default_flow_style=False,
                Dumper=IgnoreAliasesDumper,
            ),
            Loader=OrderedLoader,
        )
    except yaml.scanner.ScannerError as err:
        raise BuildRunnerConfigurationError(
            f"The {cfg_file} file contains malformed yaml, "
            f"please check the syntax and try again: {err}"
        ) from err


def sanitize_tag(tag):
    """
    Sanitize a tag to remove illegal characters.

    :param tag: The tag to sanitize.
    :return: The sanitized tag.
    """
    _tag = re.sub(r"[^-_\w.]+", "-", tag.lower())
    if _tag != tag:
        LOGGER.debug(
            f"Forcing tag to lowercase and removing illegal characters: {tag} => {_tag}"
        )
    return _tag


def is_dict(obj):
    """
    Determines whether an object acts like a dict.

    Args:
      obj (object): The object to test.

    Return:
      True if the obj acts like a dict, False otherwise.
    """
    return hasattr(obj, "keys") and hasattr(obj, "__getitem__")


def epoch_time():
    """Return the current epoch time in integer seconds."""
    return int((datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds())


def tempfile(prefix=None, suffix=None, temp_dir="/tmp"):
    """
    Generate a temporary file path within the container.
    """
    name = str(uuid.uuid4())
    if suffix:
        name = name + suffix
    if prefix:
        name = prefix + name

    return os.path.join(temp_dir, name)


def checksum(*files: Tuple[str]) -> str:
    """
    Generate a single SHA1 checksum of the list of files passed in
    """
    if not isinstance(files, tuple):
        LOGGER.warning(
            f"TypeError - Input 'files' needs to be a tuple instead of {type(files)}"
        )
        sys.exit()

    blocksize = 2**16
    hasher = hashlib.sha1()

    for filename in sorted(files):
        if not os.path.isfile(filename):
            LOGGER.warning(f"{filename} does not exist, skipping file.")
            continue

        with open(filename, "rb") as open_file:
            buf = open_file.read(blocksize)
            while len(buf) > 0:
                hasher.update(buf)
                buf = open_file.read(blocksize)

    return hasher.hexdigest()


def hash_sha1(file_name_globs=None):
    """
    Return the sha1 hash from the content of multiple files, represented by a list of globs
    """
    if not file_name_globs:
        file_name_globs = []
    blocksize = 2**16  # 65,536
    hasher = hashlib.sha1()
    for file_name_glob in file_name_globs:
        for file_name in sorted(glob.glob(file_name_glob)):
            try:
                # Use blocksize to ensure python memory isn't too full
                with open(file_name, "rb") as open_file:
                    buf = open_file.read(blocksize)
                    while len(buf) > 0:
                        hasher.update(buf)
                        buf = open_file.read(blocksize)
            except Exception:  # pylint: disable=broad-except
                LOGGER.warning(f"Error reading file: {file_name}")
    return hasher.hexdigest()


def _acquire_flock_open(
    lock_file: str,
    logger: loggers.ContainerLogger,
    mode: str,
    timeout_seconds: float = LOCK_TIMEOUT_SECONDS,
    exclusive: bool = True,
) -> io.IOBase:
    """
    Acquire file lock and open file with configurable timeout

    :param lock_file: path and file name of file open and lock
    :param logger: logger to log messages
    :param mode: mode used by open()
    :param timeout_seconds: number of seconds for timeout
    :param exclusive: config exclusive lock (True) or shared lock (False), defaults to True
    :return: opened file object if successful else None
    """

    @timeout_decorator.timeout(
        seconds=timeout_seconds, timeout_exception=FailureToAcquireLockException
    )
    def get_lock(file_obj, flags):
        portalocker.lock(
            file_obj,
            flags,
        )
        return file_obj

    # pylint: disable=unspecified-encoding,consider-using-with
    file_obj = open(lock_file, mode)
    lock_file_obj = None
    pid = os.getpid()

    try:
        flags = (
            portalocker.LockFlags.EXCLUSIVE
            if exclusive
            else portalocker.LockFlags.SHARED
        )
        lock_file_obj = get_lock(file_obj, flags)
    except FailureToAcquireLockException:
        file_obj.close()
        raise FailureToAcquireLockException(
            f"PID:{pid} failed to acquire file lock for {lock_file} after timeout of {timeout_seconds} seconds"
        )

    logger.info(
        f"PID:{pid} file opened and lock acquired for {lock_file} ({lock_file_obj})"
    )

    return lock_file_obj


def acquire_flock_open_read_binary(
    lock_file: str,
    logger: loggers.ContainerLogger,
    timeout_seconds: float = LOCK_TIMEOUT_SECONDS,
) -> io.BufferedReader:
    """
    Acquire file lock and open binary file in read mode with configurable timeout

    :param lock_file: path and file name of file open and lock
    :param logger: logger to log messages
    :param timeout_seconds: number of seconds for timeout
    :return: opened file object
    """
    return _acquire_flock_open(
        lock_file=lock_file,
        logger=logger,
        mode="rb",
        timeout_seconds=timeout_seconds,
        exclusive=False,
    )


def acquire_flock_open_write_binary(
    lock_file: str,
    logger: loggers.ContainerLogger,
    timeout_seconds: float = LOCK_TIMEOUT_SECONDS,
    mode: str = "wb",
) -> io.BufferedWriter:
    """
    Acquire file lock and open binary file in write mode with configurable timeout

    :param lock_file: path and file name of file open and lock
    :param logger: logger to log messages
    :param timeout_seconds: number of seconds for timeout
    :param exclusive: config exclusive lock (True) or shared lock (False), defaults to True
    :return: opened file object
    """
    return _acquire_flock_open(
        lock_file=lock_file,
        logger=logger,
        mode=mode,
        timeout_seconds=timeout_seconds,
        exclusive=True,
    )


def release_flock(
    lock_file_obj: Optional[io.BufferedReader], logger: loggers.ContainerLogger
):
    """
    Release the file lock and close file descriptor

    :param lock_file_obj: opened lock file object
    :param logger: logger to log messages
    """
    if lock_file_obj is None:
        return
    portalocker.unlock(lock_file_obj)
    lock_file_obj.close()
    logger.write(f"PID:{os.getpid()} released and closed file {lock_file_obj}")
