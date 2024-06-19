"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import logging
import os
import sys
import queue
from typing import Optional, Union

import colorlog
from rich import progress


CONSOLE_LOGGER_NAME = "buildrunner"
ENCODING = sys.stdout.encoding if sys.stdout.encoding else "utf8"


class CustomColoredFormatter(colorlog.ColoredFormatter):
    def __init__(self, fmt: str, no_color: bool, color: str = "white"):
        super().__init__(
            fmt, no_color=no_color, log_colors=self._get_log_level_colors(color)
        )
        self.fmt = fmt
        self.color = color

    def clone(
        self, color: Optional[str] = None, no_color: Optional[bool] = None
    ) -> "CustomColoredFormatter":
        if color is None:
            color = self.color
        if no_color is None:
            no_color = self.no_color
        return CustomColoredFormatter(self.fmt, no_color, color)

    @staticmethod
    def _get_log_level_colors(color: str) -> dict:
        return {
            "DEBUG": color,
            "INFO": color,
            "WARNING": color,
            "ERROR": color,
            "CRITICAL": color,
        }


def get_build_log_file_path(build_results_dir: str) -> str:
    return os.path.join(build_results_dir, "build.log")


def _get_logger_format(no_log_color: bool, disable_timestamps: bool):
    timestamp = "" if disable_timestamps else "%(asctime)s "
    return CustomColoredFormatter(
        f"%(log_color)s{timestamp}%(levelname)-8s %(message)s",
        no_log_color,
    )


def initialize_root_logger(
    debug: bool, no_log_color: bool, disable_timestamps: bool, build_results_dir: str
) -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    console_formatter = _get_logger_format(no_log_color, disable_timestamps)
    # The file formatter should always use no color and timestamps should be enabled
    file_formatter = _get_logger_format(True, False)

    console_handler = logging.StreamHandler(sys.stdout)
    # Console logger should use colored output when specified by config
    console_handler.setFormatter(console_formatter)
    file_handler = logging.FileHandler(
        get_build_log_file_path(build_results_dir), "w", encoding="utf8"
    )
    # The build log should never use colored output
    file_handler.setFormatter(file_formatter)
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


class ConsoleLogger:
    """
    Class inherited from logger that provides backwards support for the "write" method.
    This should be removed at some point and reimplemented with actual logging calls.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def write(self, output: Union[bytes, str]):
        """
        Write the given text to stdout and streams decorating output to stdout
        with color.
        """
        if not isinstance(output, str):
            output = str(output, encoding=ENCODING, errors="replace")
        if output and output[-1] == "\n":
            output = output[:-1]
        for line in output.split("\n"):
            self.logger.info(line)

    # Delegates all methods to the logger if they don't exist (allowing the logger methods to be used directly)
    def __getattr__(self, item):
        return getattr(self.logger, item)


class ColorQueue(queue.SimpleQueue):
    def __init__(self, *colors):
        super().__init__()
        for color in colors:
            self.put(color)

    def next(self) -> str:
        current = self.get()
        self.put(current)
        return current


class ContainerLogger(ConsoleLogger):
    """
    Class used to write container specific output to logging.

    This class is not thread safe, but since each container gets its own that
    is ok.
    """

    BUILD_LOG_COLORS = ColorQueue("yellow", "blue")
    SERVICE_LOG_COLORS = ColorQueue("purple", "cyan", "red", "green")
    LOGGERS = {}

    def __init__(self, name: str, color: str, prefix: Optional[str] = None):
        super().__init__(name)
        self._set_logger_handlers(color)

        self._line_prefix = f"[{prefix if prefix else name}] "
        self._buffer = []

    def _set_logger_handlers(self, color: str) -> None:
        """
        Copy and modify the handlers from the root logger in order to change the color for the console logger
        as well as push the logs to the results build log file
        :param color: the color to set on the console handler
        """
        # Only override this if not already set
        if self.logger.handlers:
            return

        self.logger.propagate = False
        for handler in logging.getLogger().handlers:
            if (
                isinstance(handler, logging.StreamHandler)
                and not isinstance(handler, logging.FileHandler)
                and isinstance(handler.formatter, CustomColoredFormatter)
            ):
                new_handler = logging.StreamHandler(handler.stream)
                new_handler.setFormatter(handler.formatter.clone(color))
                self.logger.addHandler(new_handler)
            else:
                self.logger.addHandler(handler)

    def _write_buffer(self):
        """
        Write the contents of the buffer to the log.
        """
        line = f'{self._line_prefix}{"".join(self._buffer)}'
        self._buffer.clear()
        super().write(line)

    def write(self, output: Union[bytes, str]):
        """
        Write the given output to the log.
        """
        # Ensure that the output is a string
        if not isinstance(output, str):
            output = str(output, ENCODING, errors="replace")

        for char in output:
            self._buffer.append(char)
            if char == "\n":
                self._write_buffer()

    def cleanup(self):
        """
        Flush the buffer.
        """
        if self._buffer:
            self._buffer.append("\n")
            self._write_buffer()

    @classmethod
    def for_build_container(cls, name: str) -> "ContainerLogger":
        """
        Return a ContainerLogger for a build container.
        """
        color = cls.BUILD_LOG_COLORS.next()
        name_idx = f"{name}_{color}"
        if name_idx not in cls.LOGGERS:
            cls.LOGGERS[name_idx] = ContainerLogger(name_idx, color, prefix=name)
        return cls.LOGGERS[name_idx]

    @classmethod
    def for_service_container(cls, name: str) -> "ContainerLogger":
        """
        Return a ContainerLogger for a service container.
        """
        color = cls.SERVICE_LOG_COLORS.next()
        if name not in cls.LOGGERS:
            cls.LOGGERS[name] = ContainerLogger(f"service-{name}", color)
        return cls.LOGGERS[name]


class DockerPullProgress:
    # Inspired by https://github.com/docker/docker-py/issues/376#issuecomment-1414535176
    tasks = {}

    def __init__(self):
        self.progress = progress.Progress()

    def __enter__(self):
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.__exit__(exc_type, exc_val, exc_tb)

    def status_report(self, data: dict) -> None:
        if not data:
            return
        try:
            status = data.get("status")
            if status == "Downloading":
                color = "cyan"
            elif status == "Extracting":
                color = "green"
            else:
                # Skip other statuses
                return
            status_id = data.get("id")
            if not status_id or status_id == "0":
                return
            description = f"[{color}]{status_id}: {status}"

            if status_id not in self.tasks:
                self.tasks[status_id] = self.progress.add_task(
                    description,
                    total=data["progressDetail"]["total"],
                )
            else:
                self.progress.update(
                    self.tasks[status_id],
                    completed=data["progressDetail"]["current"],
                    description=description,
                )
        except Exception:
            # Do not worry about any exceptions since it's just for helpful display purposes
            pass
