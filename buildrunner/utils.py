"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import

from collections import OrderedDict
from datetime import datetime
import sys
import yaml


#pylint: disable=C0301
# from http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
def ordered_load(
    stream,
    loader_class=yaml.Loader,
    object_pairs_hook=OrderedDict,
):
    """
    Load yaml while preserving the order of attributes in maps/dictionaries.
    """
    #pylint: disable=too-many-ancestors,too-many-public-methods
    class OrderedLoader(loader_class):
        """
        Custom loader class that preserves dictionary order.
        """
        pass
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        lambda loader, node: object_pairs_hook(loader.construct_pairs(node)),
    )
    return yaml.load(stream, OrderedLoader)


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
        (datetime.now() - datetime.utcfromtimestamp(0)).total_seconds()
    )


class ConsoleLogger(object):
    """
    Class used to write decorated output to stdout while also redirecting
    non-decorated output to one or more streams.
    """
    def __init__(self, *streams):
        self.streams = streams


    def write(self, output, color=None):
        """
        Write the given text to stdout and streams decorating output to stdout
        with color.
        """
        # colorize stdout
        _stdout = output
        if color:
            _color_start = '\033[01;3{color}m'.format(color=color)
            _stdout = _color_start + _stdout + '\033[00;00m'
        sys.stdout.write(_stdout)

        # do not colorize output to other streams
        for stream in self.streams:
            stream.write(output)


    def flush(self):
        """
        Flush.
        """
        pass


class ContainerLogger(object):
    """
    Class used to write container specific output to a ConsoleLogger.
    """
    def __init__(self, console_logger, name, color):
        self.console_logger = console_logger
        self.name = name
        self.line_prefix = '[' + name + '] '
        self.color = color


    def write(self, output):
        """
        Write the given output to the log.
        """
        lines = output.splitlines()
        for line in lines:
            _line = self.line_prefix + line + '\n'
            self.console_logger.write(
                _line,
                color=self.color,
            )


    BUILD_LOG_COLOR = 3
    SERVICE_LOG_COLORS = [4, 5, 6, 1, 2]
    CURRENT_SERVICE_COLOR = 0
    LOGGERS = {}

    @classmethod
    def for_build_container(cls, console_logger, name):
        """
        Return a ContainerLogger for a build container.
        """
        if name not in cls.LOGGERS:
            cls.LOGGERS[name] = ContainerLogger(
                console_logger,
                name,
                cls.BUILD_LOG_COLOR,
            )
        return cls.LOGGERS[name]


    @classmethod
    def for_service_container(cls, console_logger, name):
        """
        Return a ContainerLogger for a service container.
        """
        idx = cls.CURRENT_SERVICE_COLOR % len(cls.SERVICE_LOG_COLORS)
        cls.CURRENT_SERVICE_COLOR += 1
        if name not in cls.LOGGERS:
            cls.LOGGERS[name] = ContainerLogger(
                console_logger,
                name,
                cls.SERVICE_LOG_COLORS[idx],
            )
        return cls.LOGGERS[name]
