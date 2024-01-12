"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import logging
import os
import sys
from time import strftime, gmtime
from typing import Union


def get_logger(loglevel: str, name: str) -> logging.Logger:
    """
    :param loglevel:
    """
    logger = logging.getLogger(name)
    logger.setLevel(loglevel)

    formatter = logging.Formatter("%(asctime)s %(name)-30s %(levelname)-8s %(message)s")
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_build_log_file_path(build_results_dir: str) -> str:
    return os.path.join(build_results_dir, "build.log")


def initialize_root_logger(loglevel: str, build_results_dir: str) -> None:
    logger = logging.getLogger()
    logger.setLevel(loglevel)

    formatter = logging.Formatter("%(asctime)s %(name)-30s %(levelname)-8s %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(
        get_build_log_file_path(build_results_dir), "w", encoding="utf8"
    )
    file_handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


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
            output = str(output, encoding=sys.stdout.encoding, errors="replace")
        _stdout = output

        # colorize stdout
        if color and self.colorize_log:
            # Colorize stdout
            # pylint: disable=invalid-character-esc
            _stdout = f"[01;3{color}m{_stdout}\033[00;00m"
        self.stdout.write(_stdout)

        # do not colorize output to other streams
        for stream in self.streams:
            try:
                if stream.closed:
                    self.stderr.write(
                        f"WARNING: Attempted to write to a closed stream {stream}. "
                        f"Not writing {output} to {stream}."
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
        self.line_prefix = "[" + name + "] "
        self.color = color
        self.timestamps = timestamps
        self._buffer = []

    def _get_timestamp(self):
        if self.timestamps:
            return "[" + strftime("%H:%M:%S", gmtime()) + "] "
        return ""

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
            output = str(output, encoding=sys.stdout.encoding, errors="replace")

        for char in output:
            self._buffer.append(char)
            if char == "\n":
                self._write_buffer()

    def cleanup(self):
        """
        Flush the buffer.
        """
        self._buffer.append("\n")
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
