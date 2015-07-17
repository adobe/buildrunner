"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import

import codecs
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
        self.streams = []
        for stream in streams:
            self.streams.append(codecs.getwriter('utf-8')(stream, 'replace'))
        self.stdout = codecs.getwriter('utf-8')(sys.stdout, 'replace')


    def write(self, output, color=None):
        """
        Write the given text to stdout and streams decorating output to stdout
        with color.
        """
        # colorize stdout
        if not isinstance(output, unicode):
            output = unicode(output, encoding='utf-8', errors='replace')
        _stdout = output
        if color:
            _color_start = u'\033[01;3{color}m'.format(color=color)
            _stdout = _color_start + _stdout + u'\033[00;00m'
        self.stdout.write(_stdout)

        # do not colorize output to other streams
        for stream in self.streams:
            try:
                stream.write(output)
            except UnicodeDecodeError as ude:
                stream.write("\nERROR writing to log: %s\n" % str(ude))


    def flush(self):
        """
        Flush.
        """
        pass


class ContainerLogger(object):
    """
    Class used to write container specific output to a ConsoleLogger.

    This class is not thread safe, but since each container gets its own that
    is ok.
    """
    def __init__(self, console_logger, name, color):
        self.console_logger = console_logger
        self.name = name
        self.line_prefix = '[' + name + '] '
        self.color = color
        self._buffer = []


    def _write_buffer(self):
        """
        Write the contents of the buffer to the log.
        """
        _line = self.line_prefix + ''.join(self._buffer)
        del self._buffer[:]
        self.console_logger.write(
            _line,
            color=self.color,
        )


    def write(self, output):
        """
        Write the given output to the log.
        """
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


    BUILD_LOG_COLORS = [3, 4]
    SERVICE_LOG_COLORS = [5, 6, 1, 2]
    LOGGERS = {}

    @classmethod
    def for_build_container(cls, console_logger, name):
        """
        Return a ContainerLogger for a build container.
        """
        color = cls._cycle_colors(cls.BUILD_LOG_COLORS)
        nameIdx = "%s%s" % (name, color)
        if nameIdx not in cls.LOGGERS:
            cls.LOGGERS[nameIdx] = ContainerLogger(
                console_logger,
                name,
                color,
            )
        return cls.LOGGERS[nameIdx]


    @classmethod
    def for_service_container(cls, console_logger, name):
        """
        Return a ContainerLogger for a service container.
        """
        color = cls._cycle_colors(cls.SERVICE_LOG_COLORS)
        if name not in cls.LOGGERS:
            cls.LOGGERS[name] = ContainerLogger(
                console_logger,
                name,
                color,
            )
        return cls.LOGGERS[name]


    @staticmethod
    def _cycle_colors(colors):
        current = colors[0]
        colors[0] = colors[1]
        colors[-1] = current

        return current
