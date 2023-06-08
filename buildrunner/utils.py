"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from collections import OrderedDict
from datetime import datetime
import fcntl
import io
from time import strftime, gmtime
import os
import sys
import time
import uuid
import yaml.resolver
import yaml.scanner
import glob
import hashlib
from typing import Union, Tuple

from buildrunner.errors import BuildRunnerConfigurationError

LOCK_TIMEOUT_SECONDS = 1800.0


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
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping
)
# Tell YAML how to dump the OrderedDict
yaml.add_representer(
    OrderedDict,
    lambda dumper, data: dumper.represent_dict(iter(data.items())),
)
yaml.add_representer(
    OrderedDict,
    lambda dumper, data: dumper.represent_dict(iter(data.items())),
    Dumper=yaml.SafeDumper
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
                default_flow_style=False, Dumper=IgnoreAliasesDumper,
            ),
            Loader=OrderedLoader,
        )
    except yaml.scanner.ScannerError as err:
        raise BuildRunnerConfigurationError(
            f'The {cfg_file} file contains malformed yaml, '
            f'please check the syntax and try again: {err}'
        ) from err


def is_dict(obj):
    """
    Determines whether an object acts like a dict.

    Args:
      obj (object): The object to test.

    Return:
      True if the obj acts like a dict, False otherwise.
    """
    return hasattr(obj, 'keys') and hasattr(obj, '__getitem__')


def epoch_time():
    """Return the current epoch time in integer seconds."""
    return int(
        (datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds()
    )


def tempfile(prefix=None, suffix=None, temp_dir='/tmp'):
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
        print(f"WARNING: TypeError - Input 'files' needs to be a tuple instead of {type(files)}")
        sys.exit()

    blocksize = 2 ** 16
    hasher = hashlib.sha1()

    for filename in sorted(files):
        if not os.path.isfile(filename):
            print(f"WARNING: {filename} does not exist, skipping file.")
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
    blocksize = 2 ** 16  # 65,536
    hasher = hashlib.sha1()
    for file_name_glob in file_name_globs:
        for file_name in sorted(glob.glob(file_name_glob)):
            try:
                # Use blocksize to ensure python memory isn't too full
                with open(file_name, 'rb') as open_file:
                    buf = open_file.read(blocksize)
                    while len(buf) > 0:
                        hasher.update(buf)
                        buf = open_file.read(blocksize)
            except Exception:  # pylint: disable=broad-except
                print(f"WARNING: Error reading file: {file_name}")
    return hasher.hexdigest()


class ConsoleLogger:
    """
    Class used to write decorated output to stdout while also redirecting
    non-decorated output to one or more streams.
    """

    def __init__(self, colorize_log, *streams):
        self.colorize_log = colorize_log
        self.streams = []
        for stream in streams:
            self.streams.append(stream)
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def write(self, output: Union[bytes, str], color=None):
        """
        Write the given text to stdout and streams decorating output to stdout
        with color.
        """
        if not isinstance(output, str):
            output = str(output, encoding=sys.stdout.encoding, errors='replace')
        _stdout = output

        # colorize stdout
        if color and self.colorize_log:
            # Colorize stdout
            # pylint: disable=invalid-character-esc
            _stdout = f'[01;3{color}m{_stdout}\033[00;00m'
        self.stdout.write(_stdout)

        # do not colorize output to other streams
        for stream in self.streams:
            try:
                if stream.closed:
                    self.stderr.write(
                        f'WARNING: Attempted to write to a closed stream {stream}. '
                        f'Not writing {output} to {stream}.'
                    )
                else:
                    stream.write(output)
            except UnicodeDecodeError as ude:
                stream.write(f"\nERROR writing to log: {str(ude)}\n")

    def flush(self):
        """
        Flush.
        """
        for stream in self.streams:
            stream.flush()


class ContainerLogger:
    """
    Class used to write container specific output to a ConsoleLogger.

    This class is not thread safe, but since each container gets its own that
    is ok.
    """
    BUILD_LOG_COLORS = [3, 4]
    SERVICE_LOG_COLORS = [5, 6, 1, 2]
    LOGGERS = {}

    def __init__(self, console_logger, name, color, timestamps=True):
        self.console_logger = console_logger
        self.name = name
        self.line_prefix = '[' + name + '] '
        self.color = color
        self.timestamps = timestamps
        self._buffer = []

    def _get_timestamp(self):
        if self.timestamps:
            return '[' + strftime("%H:%M:%S", gmtime()) + '] '
        return ''

    def _write_buffer(self):
        """
        Write the contents of the buffer to the log.
        """
        _line = f'{self._get_timestamp()}{self.line_prefix}{"".join(self._buffer)}'
        self._buffer.clear()
        self.console_logger.write(
            _line,
            color=self.color,
        )

    def write(self, output: Union[bytes, str]):
        """
        Write the given output to the log.
        """
        # Ensure that the output is a string
        if not isinstance(output, str):
            output = str(output, encoding=sys.stdout.encoding, errors='replace')

        for char in output:
            self._buffer.append(char)
            if char == '\n':
                self._write_buffer()

    def cleanup(self):
        """
        Flush the buffer.
        """
        self._buffer.append('\n')
        self._write_buffer()

    @classmethod
    def for_build_container(cls, console_logger, name, timestamps=True):
        """
        Return a ContainerLogger for a build container.
        """
        color = cls._cycle_colors(cls.BUILD_LOG_COLORS)
        name_idx = f"{name}{color}"
        if name_idx not in cls.LOGGERS:
            cls.LOGGERS[name_idx] = ContainerLogger(
                console_logger,
                name,
                color,
                timestamps=timestamps,
            )
        return cls.LOGGERS[name_idx]

    @classmethod
    def for_service_container(cls, console_logger, name, timestamps=True):
        """
        Return a ContainerLogger for a service container.
        """
        color = cls._cycle_colors(cls.SERVICE_LOG_COLORS)
        if name not in cls.LOGGERS:
            cls.LOGGERS[name] = ContainerLogger(
                console_logger,
                name,
                color,
                timestamps=timestamps,
            )
        return cls.LOGGERS[name]

    @staticmethod
    def _cycle_colors(colors):
        """
        Cycle through console colors.
        """
        current = colors[0]
        colors[0] = colors[1]
        colors[-1] = current

        return current


def _acquire_flock_open(
        lock_file: str,
        logger: ContainerLogger,
        mode: str,
        timeout_seconds: float = LOCK_TIMEOUT_SECONDS,
        exclusive: bool = True) -> io.IOBase:
    """
    Acquire file lock and open file with configurable timeout

    :param lock_file: path and file name of file open and lock
    :param logger: logger to log messages
    :param mode: mode used by open()
    :param timeout_seconds: number of seconds for timeout
    :param exclusive: config exclusive lock (True) or shared lock (False), defaults to True
    :return: opened file object if successful else None
    """
    # pylint: disable=unspecified-encoding,consider-using-with
    file_obj = open(lock_file, mode)
    pid = os.getpid()
    lock_file_obj = None
    retry_sleep_seconds = 0.5

    start_time = current_time = time.time()
    duration_seconds = current_time - start_time

    while duration_seconds < timeout_seconds:
        try:
            # The LOCK_NB means non blocking
            # More information here:
            # https://docs.python.org/3/library/fcntl.html#fcntl.flock
            if exclusive:
                # Obtain an exclusive lock, blocks shared (read) locks
                fcntl.flock(file_obj, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                # Allow multiple people to read from the file at the same time
                # If another instance adds an exclusive lock in the save method below,
                # this will block until the lock is released
                fcntl.flock(file_obj, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except (IOError, OSError):
            # Limit the amount of logs written while waiting for the file lock
            num_seconds_between_log_writes = 10
            if 0 <= (duration_seconds % num_seconds_between_log_writes) <= retry_sleep_seconds:
                logger.write(f"PID:{pid} waiting for file lock on {lock_file} after {duration_seconds} seconds")
        else:
            lock_file_obj = file_obj
            break
        time.sleep(retry_sleep_seconds)
        duration_seconds = time.time() - start_time

    if lock_file_obj is None:
        file_obj.close()
        raise FailureToAcquireLockException(
            f"PID:{pid} failed to acquire file lock for {lock_file} after timeout of {timeout_seconds} seconds"
        )

    logger.write(f"PID:{pid} file opened and lock acquired for {lock_file} ({lock_file_obj})")

    return lock_file_obj


def acquire_flock_open_read_binary(
        lock_file: str,
        logger: ContainerLogger,
        timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> io.BufferedReader:
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
        mode='rb',
        timeout_seconds=timeout_seconds,
        exclusive=False)


def acquire_flock_open_write_binary(
        lock_file: str,
        logger: ContainerLogger,
        timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> io.BufferedWriter:
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
        mode='wb',
        timeout_seconds=timeout_seconds,
        exclusive=True)


def release_flock(lock_file_obj, logger: ContainerLogger):
    """
    Release the file lock and close file descriptor

    :param lock_file_fd: file descriptor
    :param logger: logger to log messages
    """
    fcntl.flock(lock_file_obj, fcntl.LOCK_UN)
    lock_file_obj.close()
    logger.write(f"PID:{os.getpid()} released and closed file {lock_file_obj}")
