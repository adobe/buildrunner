"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import codecs
import copy
import datetime
import re
from io import StringIO
from typing import Callable

import jinja2

from buildrunner.utils import load_config


def read_yaml_file(
    env: dict,
    log_generated_file_method: Callable[[bool, str, str], None],
    log_file: bool,
    filename: str,
):
    """
    Reads a file in the local workspace as Jinja-templated YAML and returns the contents.
    Throws an error on failure.
    """
    with codecs.open(filename, "r", encoding="utf-8") as _file:
        jtemplate = jinja2.Template(_file.read())
    context = copy.deepcopy(env)
    file_contents = jtemplate.render(context)
    log_generated_file_method(log_file, filename, file_contents)
    return load_config(StringIO(file_contents), filename)


def strftime(_build_time: int, _format="%Y-%m-%d", _ts=None):
    """
    Format the provided timestamp. If no timestamp is provided, build_time is used
    :param _build_time: The build timestamp. This is bound with functools.partial and is not required to pass in.
    :param _format: Format string - default "%Y-%m-%d"
    :param _ts: Timestamp to format - default self.build_time
    :return: Formatted date/time string
    """
    if _ts is None:
        _ts = _build_time
    _date = datetime.datetime.fromtimestamp(_ts)
    return _date.strftime(_format)


def raise_exception_jinja(message):
    """
    Raises an exception from a jinja template.
    """
    # pylint: disable=broad-exception-raised
    raise Exception(message)


def re_sub_filter(text, pattern, replace, count=0, flags=0):
    """
    Filter for regular expression replacement.
    :param text: The string being examined for ``pattern``
    :param pattern: The pattern to find in ``text``
    :param replace: The replacement for ``pattern``
    :param count: How many matches of ``pattern`` to replace with ``replace`` (0=all)
    :param flags: Regular expression flags
    """
    return re.sub(pattern, replace, text, count=count, flags=flags)


def re_split_filter(text, pattern, maxsplit=0, flags=0):
    """
    Filter for regular expression replacement.
    :param text: The string being examined for ``pattern``
    :param pattern: The pattern used to split ``text``
    :param maxsplit: How many instances of ``pattern`` to split (0=all)
    :param flags: Regular expression flags
    """
    return re.split(pattern, text, maxsplit=maxsplit, flags=flags)
