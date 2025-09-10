"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import base64
from collections import OrderedDict
import copy
import functools
import getpass
from graphlib import TopologicalSorter
from io import StringIO
import logging
import os
from typing import List, Optional, Union

import jinja2

from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerVersionError,
    ConfigVersionFormatError,
    ConfigVersionTypeError,
)
from buildrunner.utils import (
    checksum,
    hash_sha1,
    load_config,
)

from .models import GlobalConfig

from . import fetch, jinja_context


MASTER_GLOBAL_CONFIG_FILE = "/etc/buildrunner/buildrunner.yaml"
VERSION_FILE_PATH = (
    f"{os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))}/version.py"
)
RESULTS_DIR = "buildrunner.results"
LOGGER = logging.getLogger(__name__)


def _log_generated_file(
    log_generated_files: bool, file_name: str, file_contents: str
) -> None:
    """
    Conditionally log the contents of a generated file.
    """
    if log_generated_files:
        LOGGER.info(f"Generated contents of {file_name}:")
        for line in file_contents.splitlines():
            LOGGER.info(line)


def _add_default_tag_to_tags(config: Union[str, dict], default_tag: str) -> dict:
    # Add default tag to tags list if not in the list already
    if isinstance(config, dict):
        if not config.get("tags"):
            config["tags"] = []
        assert isinstance(config.get("tags"), list)
        # Only add the tag if not disabled in the config
        if config.get("add_build_tag", True) and default_tag not in config.get("tags"):
            config.get("tags").append(default_tag)

    # Convert to dictionary and add default tag if not listed already
    elif isinstance(config, str):
        image_name = config.split(":")
        step_config = dict()
        step_config["repository"] = image_name[0]
        step_config["tags"] = []

        # Check if image name has defined a tag, if so add it to tags
        if len(image_name) > 1:
            tag = image_name[1]
            assert tag
            step_config["tags"].append(tag)

        # Add default tag if not in the list already
        if default_tag not in step_config["tags"]:
            step_config["tags"].append(default_tag)

        config = step_config
    return config


def _set_default_tag(config: dict, default_tag: str) -> dict:
    """
    Set default tag if not set for each image

    Args:
        config (dict):  configuration
        default_tag (str): default tag

        Returns:
            dict: configuration
    """
    steps = config.get("steps")
    if not isinstance(steps, dict):
        return config
    for step_name, step in steps.items():
        for substep_name, substep in step.items():
            if substep_name in ["push", "commit"]:
                # Add default tag to tags list if not in the list
                if isinstance(substep, list):
                    curr_image_infos = []
                    for push_config in substep:
                        curr_image_infos.append(
                            _add_default_tag_to_tags(push_config, default_tag)
                        )
                    config["steps"][step_name][substep_name] = curr_image_infos
                else:
                    curr_image_info = _add_default_tag_to_tags(substep, default_tag)
                    config["steps"][step_name][substep_name] = curr_image_info
    return config


def _validate_version(config: dict) -> None:
    """
    Compares that the version in the config is less than or equal to the current version of
    buildrunner. If the config version is greater than the buildrunner version or any parsing error occurs
    it will raise a buildrunner exception.
    """
    buildrunner_version = None

    if not os.path.exists(VERSION_FILE_PATH):
        LOGGER.warning(
            f"File {VERSION_FILE_PATH} does not exist. This could indicate an error with "
            f"the buildrunner installation. Unable to validate version."
        )
        return

    with open(VERSION_FILE_PATH, "r", encoding="utf-8") as version_file:
        for line in version_file.readlines():
            if "__version__" in line:
                try:
                    version_values = (
                        line.split("=")[1]
                        .strip()
                        .replace("'", "")
                        .replace('"', "")
                        .split(".")
                    )
                    buildrunner_version = f"{version_values[0]}.{version_values[1]}"
                except IndexError as exception:
                    raise ConfigVersionFormatError(
                        f'couldn\'t parse version from "{line}"'
                    ) from exception

    if not buildrunner_version:
        raise BuildRunnerVersionError("unable to determine buildrunner version")

    # version is optional and is valid to not have it in the config
    if "version" not in config.keys():
        return

    config_version = config["version"]

    try:
        if float(config_version) > float(buildrunner_version):
            raise ConfigVersionFormatError(
                f"configuration version {config_version} is higher than "
                f"buildrunner version {buildrunner_version}"
            )
    except ValueError as exception:
        raise ConfigVersionTypeError(
            f'unable to convert config version "{config_version}" '
            f'or buildrunner version "{buildrunner_version}" '
            f"to a float"
        ) from exception


def _reorder_dependency_steps(config: dict) -> dict:
    """
    Reorders the steps based on the dependencies that are outlined in the config
    """
    # Defines configuration keywords, should add to a config validation class
    keyword_version = "version"
    keyword_steps = "steps"
    keyword_depends = "depends"
    supported_version = 2.0

    if (
        keyword_version not in config.keys()
        or config[keyword_version] < supported_version
    ):
        return config

    ordered_steps = OrderedDict()
    if keyword_steps in config.keys():
        topo_sorter = TopologicalSorter()
        for name, instructions in config[keyword_steps].items():
            if keyword_depends in instructions.keys():
                for depend in instructions[keyword_depends]:
                    topo_sorter.add(name, depend)
            else:
                topo_sorter.add(name)
        for step in topo_sorter.static_order():
            if step not in config[keyword_steps]:
                raise KeyError(
                    f"Step '{step}' is not defined and is listed as a step dependency in "
                    f"the configuration. "
                    f"Please correct the typo or define step '{step}' in the configuration."
                )

            if keyword_depends in config[keyword_steps][step].keys():
                del config[keyword_steps][step][keyword_depends]

            ordered_steps[step] = config[keyword_steps][step]

        config[keyword_steps] = ordered_steps

    return config


def _fetch_template(
    *,
    env: dict,
    build_time: int,
    cfg_file: str,
    global_config: Optional[GlobalConfig] = None,
    ctx: Optional[dict] = None,
    log_file: bool = True,
) -> dict:
    """
    Load a config file templating it with Jinja and parsing the YAML.

    Returns:
        Dictionary parsed from the contents of the final loaded file
    """

    fetch_file = cfg_file
    visited = set()

    while True:
        visited.add(fetch_file)
        contents = fetch.fetch_file(fetch_file, global_config)
        jenv = jinja2.Environment(
            loader=jinja2.FileSystemLoader("."), extensions=["jinja2.ext.do"]
        )
        jenv.filters["hash_sha1"] = hash_sha1
        jenv.filters["base64encode"] = base64.encode
        jenv.filters["base64decode"] = base64.decode
        jenv.filters["re_sub"] = jinja_context.re_sub_filter
        jenv.filters["re_split"] = jinja_context.re_split_filter

        jenv.globals.update(checksum=checksum)
        jtemplate = jenv.from_string(contents)

        config_context = copy.deepcopy(env)
        config_context.update({
            "CONFIG_FILE": cfg_file,
            "CONFIG_DIR": os.path.dirname(cfg_file),
            "read_yaml_file": functools.partial(
                jinja_context.read_yaml_file, env, _log_generated_file, log_file
            ),
            "raise": jinja_context.raise_exception_jinja,
            "strftime": functools.partial(jinja_context.strftime, build_time),
            "env": os.environ,
            # This is stored after the initial env is set
            "DOCKER_REGISTRY": global_config.docker_registry if global_config else None,
        })

        if ctx:
            config_context.update(ctx)

        config_contents = jtemplate.render(config_context)
        _log_generated_file(log_file, cfg_file, config_contents)
        config = load_config(StringIO(config_contents), cfg_file)

        if not config:
            break

        redirect = config.get("redirect")
        if redirect is None:
            break

        fetch_file = redirect
        if fetch_file in visited:
            raise BuildRunnerConfigurationError(
                f"Redirect loop visiting previously visited file: {fetch_file}"
            )

    return config or {}


def load_run_file(
    *,
    global_config: GlobalConfig,
    env: dict,
    build_time: int,
    run_config_file: str,
    log_file: bool,
    default_tag: Optional[str] = None,
) -> dict:
    config_data = _fetch_template(
        global_config=global_config,
        env=env,
        build_time=build_time,
        cfg_file=run_config_file,
        log_file=log_file,
    )
    # Validate the version
    _validate_version(config_data)
    # Reorder steps for dependencies
    config_data = _reorder_dependency_steps(config_data)
    # Always add default tag if not set
    config_data = _set_default_tag(config_data, default_tag)

    return config_data


def _deep_merge_dicts(a_dict: dict, b_dict: dict, path=None) -> dict:
    if path is None:
        path = []
    for key in b_dict:
        if key in a_dict:
            if isinstance(a_dict[key], dict) and isinstance(b_dict[key], dict):
                _deep_merge_dicts(a_dict[key], b_dict[key], path + [str(key)])
            elif a_dict[key] != b_dict[key]:
                a_dict[key] = b_dict[key]
        else:
            a_dict[key] = b_dict[key]
    return a_dict


def load_global_config_files(
    *,
    build_time: int,
    global_config_files: List[str],
    global_config_overrides: dict,
) -> dict:
    """
    Load global config files templating them with Jinja and parsing the YAML.

    Returns:
      A dictionary of configuration
    """
    username = getpass.getuser()
    homedir = os.path.expanduser("~")

    context = {}
    for cfg in global_config_files:
        cfg_path = os.path.realpath(os.path.expanduser(cfg))
        if os.path.exists(cfg_path):
            current_context = _fetch_template(
                env={},
                build_time=build_time,
                cfg_file=cfg_path,
                ctx=context,
                log_file=False,
            )
            if current_context is None:
                # Empty config file
                continue

            # Only allow MASTER_GLOBAL_CONFIG_FILE to specify arbitrary local-files for mounting
            # - all other local-files get scrubbed for specific requirements and non-matches
            # are dropped.
            if cfg_path != MASTER_GLOBAL_CONFIG_FILE:
                scrubbed_local_files = {}
                for fname, fpath in list(
                    current_context.get("local-files", {}).items()
                ):
                    if not isinstance(fpath, str):
                        LOGGER.info(f'Bad "local-files" entry in {cfg_path!r}:')
                        LOGGER.info(f"    {fname!r}: {fpath!r}")
                        continue
                    resolved_path = os.path.realpath(os.path.expanduser(fpath))
                    # pylint: disable=too-many-boolean-expressions
                    if (
                        username == "root"
                        or resolved_path == homedir
                        or resolved_path.startswith(homedir + os.path.sep)
                        or os.stat(resolved_path).st_uid == os.getuid()
                        or (
                            not os.path.isdir(resolved_path)
                            and os.access(resolved_path, os.R_OK | os.W_OK)
                        )
                    ):
                        scrubbed_local_files[fname] = resolved_path
                    else:
                        LOGGER.info(f'Bad "local-files" entry in {cfg_path!r}:')
                        LOGGER.info(
                            f"    User {username!r} is not allowed to mount {resolved_path!r}."
                        )
                        LOGGER.info(
                            f"    You may need an entry in {MASTER_GLOBAL_CONFIG_FILE!r}."
                        )
                current_context["local-files"] = scrubbed_local_files

            _deep_merge_dicts(context, current_context)

    return _deep_merge_dicts(context, global_config_overrides)
