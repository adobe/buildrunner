import argparse
import os

import pytest
import yaml
from unittest import mock

from buildrunner import cli


class ExitError(BaseException):
    pass


class MockedArgs(argparse.Namespace):
    def __init__(self, args_dict: dict) -> None:
        super().__init__(**args_dict)
        self.args_dict = args_dict

    def __getattr__(self, item: str):
        return self.args_dict.get(item)


@pytest.mark.parametrize(
    "args, config_file_contents, result",
    [
        ({"disable_multi_platform": None}, None, {}),
        ({"disable_multi_platform": "false"}, None, {"disable-multi-platform": False}),
        ({"disable_multi_platform": "true"}, None, {"disable-multi-platform": True}),
        (
            {"security_scan_scanner": "scanner1", "security_scan_version": None},
            None,
            {"security-scan": {"scanner": "scanner1"}},
        ),
        (
            {
                "security_scan_max_score_threshold": 1.1,
            },
            {"option1": "val1", "option2": 2},
            {
                "security-scan": {
                    "max-score-threshold": 1.1,
                    "config": {"option1": "val1", "option2": 2},
                }
            },
        ),
    ],
)
def test__get_global_config_overrides(
    args: dict, config_file_contents, result, tmp_path
):
    # Replace the config file with a real file (if specified)
    if config_file_contents:
        file_path = tmp_path / "file1"
        with file_path.open("w", encoding="utf8") as fobj:
            yaml.safe_dump(config_file_contents, fobj)
        args["security_scan_config_file"] = str(file_path)
    assert cli._get_global_config_overrides(MockedArgs(args)) == result


@pytest.mark.parametrize(
    "file_name, error_message",
    [
        ("does-not-exist", "could not be found"),
        ("empty-file", "must contain a dictionary"),
        ("yaml-list", "must contain a dictionary"),
        ("bad-yaml", "could not be loaded: mapping values are not allowed here"),
    ],
)
@mock.patch("buildrunner.cli.sys")
def test__load_security_scan_config_file_failure(
    sys_mock, file_name, error_message, tmp_path
):
    sys_mock.exit.side_effect = ExitError("exit")

    (tmp_path / "empty-file").touch()
    (tmp_path / "bad-yaml").write_text("this is totally bogus\nyaml: bad: here")
    (tmp_path / "yaml-list").write_text("[]")

    with pytest.raises(ExitError) as exc_info:
        cli._load_security_scan_config_file(str(tmp_path / file_name))
    assert str(exc_info.value) == "exit"
    sys_mock.exit.assert_called_once_with(os.EX_CONFIG)
    sys_mock.stderr.write.assert_called_once()
    assert error_message in sys_mock.stderr.write.call_args.args[0]
