"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import getpass
import logging
import os
import tempfile
from typing import List, Optional

from buildrunner.errors import BuildRunnerConfigurationError
from buildrunner.sshagent import load_ssh_key_from_file, load_ssh_key_from_str
from buildrunner.utils import (
    epoch_time,
)
from .loader import MASTER_GLOBAL_CONFIG_FILE, load_global_config_files, load_run_file
from .models import (
    generate_and_validate_global_config,
    generate_and_validate_config,
    GlobalConfig,
    Config,
)


DEFAULT_GLOBAL_CONFIG_FILES = [
    MASTER_GLOBAL_CONFIG_FILE,
    "~/.buildrunner.yaml",
]
DEFAULT_RUN_CONFIG_FILES = ["buildrunner.yaml"]
RESULTS_DIR = "buildrunner.results"
LOGGER = logging.getLogger(__name__)


class BuildRunnerConfig:
    """
    Class used to manage buildrunner config.
    """

    _INSTANCE: "BuildRunnerConfig" = None

    def __init__(
        self,
        *,
        build_dir: str,
        default_tag: str,
        global_config_file: Optional[str],
        run_config_file: Optional[str],
        log_generated_files: bool,
        build_time: int,
        env: dict,
        # May be passed in to add temporary files to this list as they are created
        tmp_files: Optional[List[str]] = None,
    ):  # pylint: disable=too-many-arguments
        self.build_dir = build_dir
        self.default_tag = default_tag
        self.log_generated_files = log_generated_files
        self.build_time = build_time
        if not self.build_time:
            self.build_time = epoch_time()
        self.env = env
        self.tmp_files = tmp_files

        self.global_config = self._load_global_config(global_config_file)
        self.run_config = self._load_run_config(run_config_file)

    def _load_global_config(self, global_config_file: Optional[str]) -> GlobalConfig:
        # load global configuration
        gc_files = DEFAULT_GLOBAL_CONFIG_FILES[:]
        gc_files.append(global_config_file or f"{self.build_dir}/.buildrunner.yaml")

        abs_gc_files = self.to_abs_path(gc_files, return_list=True)

        LOGGER.info("")
        LOGGER.info(f"Global configuration is from: {', '.join(abs_gc_files)}")
        global_config, errors = generate_and_validate_global_config(
            **load_global_config_files(
                env=self.env,
                build_time=self.build_time,
                global_config_files=abs_gc_files,
            )
        )
        if errors:
            errors_str = "\n".join(errors)
            raise BuildRunnerConfigurationError(
                f"Invalid global configuration, {len(errors)} error(s) found:\n{errors_str}"
            )
        return global_config

    def _load_run_config(self, run_config_file: Optional[str]) -> Config:
        _run_config_file = None
        if run_config_file:
            _run_config_file = self.to_abs_path(run_config_file)
        else:
            for name_to_try in DEFAULT_RUN_CONFIG_FILES:
                _to_try = self.to_abs_path(name_to_try)
                if os.path.exists(_to_try):
                    _run_config_file = _to_try
                    LOGGER.info(f"Found run configuration in {name_to_try}")
                    break

        if not _run_config_file or not os.path.exists(_run_config_file):
            raise BuildRunnerConfigurationError("Cannot find build configuration file")

        run_config, errors = generate_and_validate_config(
            **load_run_file(
                global_config=self.global_config,
                build_time=self.build_time,
                env=self.env,
                run_config_file=_run_config_file,
                log_file=self.log_generated_files,
                default_tag=self.default_tag,
            )
        )
        if errors:
            errors_str = "\n".join(errors)
            raise BuildRunnerConfigurationError(
                f"Invalid configuration, {len(errors)} error(s) found:\n{errors_str}"
            )

        return run_config

    @classmethod
    def initialize_instance(cls, *args, **kwargs) -> None:
        cls._INSTANCE = cls(*args, **kwargs)

    @classmethod
    def get_instance(cls) -> "BuildRunnerConfig":
        if not cls._INSTANCE:
            raise Exception("Configuration was accessed before initialization")
        return cls._INSTANCE

    def to_abs_path(self, path, return_list=False):
        """
        Convert a path to an absolute path (if it isn't one already).
        """

        paths = path
        if not isinstance(path, list):
            paths = [path]

        for index, _ in enumerate(paths):
            _path = os.path.expanduser(paths[index])
            if os.path.isabs(_path):
                paths[index] = os.path.realpath(_path)
            else:
                paths[index] = os.path.realpath(os.path.join(self.build_dir, _path))
        if return_list:
            return paths
        return paths[0]

    def get_build_server_from_alias(self, host: str) -> str:
        """
        Given a host alias string determine the actual build server host value
        to use by checking the global configuration.
        """
        # if no build servers configuration in global config just return host
        if not self.global_config.build_servers:
            return host

        for _host, _host_aliases in self.global_config.build_servers.items():
            if host in _host_aliases:
                return _host

        return host

    def get_ssh_keys_from_aliases(self, key_aliases: List[str]) -> list:
        """
        Given a list of key aliases return key objects based on keys registered in the global config.
        """
        if not key_aliases:
            return []
        if not self.global_config.ssh_keys:
            raise BuildRunnerConfigurationError(
                "SSH key aliases specified but no 'ssh-keys' configuration in global build runner config"
            )

        _keys = []
        _matched_aliases = []
        for key_info in self.global_config.ssh_keys:
            if not key_info.aliases:
                continue

            _password = None
            _prompt_for_password = False
            if key_info.password:
                _password = key_info.password
            else:
                _prompt_for_password = key_info.prompt_password

            for alias in key_aliases:
                if alias in key_info.aliases:
                    _matched_aliases.append(alias)

                    # Prompt for password if necessary.  Only once per key
                    if _prompt_for_password:
                        _password = getpass.getpass(f"Password for SSH Key ({alias}): ")
                        _prompt_for_password = False

                    if key_info.file:
                        _key_file = os.path.realpath(
                            os.path.expanduser(os.path.expandvars(key_info.file))
                        )

                        _keys.append(load_ssh_key_from_file(_key_file, _password))
                    elif key_info.key:
                        _keys.append(load_ssh_key_from_str(key_info.key, _password))

        for alias in key_aliases:
            if alias not in _matched_aliases:
                raise BuildRunnerConfigurationError(
                    f"Could not find valid SSH key matching alias '{alias}'"
                )

        return _keys

    def get_local_files_from_alias(self, file_alias: str) -> Optional[str]:
        """
        Given a file alias lookup the local file path from the global config.
        """
        if not file_alias:
            return None
        if not self.global_config.local_files:
            LOGGER.info("No 'local-files' configuration in global build runner config")
            return None

        for local_alias, local_file in self.global_config.local_files.items():
            if file_alias == local_alias:
                local_path = os.path.realpath(
                    os.path.expanduser(os.path.expandvars(local_file))
                )
                if os.path.exists(local_path):
                    return local_path

                # This secondary code will create the file in the location specified and put the contents
                # from the config value into the file for usage in a container. This may ONLY be used in the master
                # global config file.
                # pylint: disable=consider-using-with
                _fileobj = tempfile.NamedTemporaryFile(
                    delete=False,
                    dir=self.global_config.temp_dir,
                )
                _fileobj.write(
                    local_file.encode("utf8")
                    if isinstance(local_file, str)
                    else local_file
                )
                tmp_path = os.path.realpath(_fileobj.name)
                _fileobj.close()
                if self.tmp_files is not None:
                    self.tmp_files.append(tmp_path)
                return tmp_path

        return None
