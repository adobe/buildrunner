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
        ({"disable_multi_platform": False}, None, {}),
        ({"disable_multi_platform": True}, None, {"disable-multi-platform": True}),
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


@pytest.mark.parametrize(
    "platform_arg",
    [
        None,  # No platform specified
        "linux/amd64",  # Specific platform
        "linux/arm64/v8",  # ARM platform
    ],
)
@mock.patch("buildrunner.cli.BuildRunner")
@mock.patch("buildrunner.cli.BuildRunnerConfig")
@mock.patch("buildrunner.cli.parse_args")
def test_clean_cache_with_platform(
    mock_parse_args, mock_config, mock_buildrunner, platform_arg, tmp_path
):
    """Test that clean_cache() correctly passes the platform parameter to BuildRunnerConfig.initialize_instance()"""
    # Setup mock args
    mock_args = mock.Mock()
    mock_args.directory = str(tmp_path)
    mock_args.global_config_file = None
    mock_args.config_file = None
    mock_args.log_generated_files = False
    mock_args.print_generated_files = False
    mock_args.platform = platform_arg
    mock_args.disable_multi_platform = False
    mock_args.security_scan_enabled = None
    mock_args.security_scan_scanner = None
    mock_args.security_scan_version = None
    mock_args.security_scan_config_file = None
    mock_args.security_scan_max_score_threshold = None
    mock_parse_args.return_value = mock_args

    # Call clean_cache
    cli.clean_cache()

    # Verify BuildRunnerConfig.initialize_instance was called with platform parameter
    mock_config.initialize_instance.assert_called_once()
    call_kwargs = mock_config.initialize_instance.call_args.kwargs

    # Verify all required parameters are present
    assert "platform" in call_kwargs
    assert call_kwargs["platform"] == platform_arg
    assert call_kwargs["push"] is False
    assert call_kwargs["build_number"] == 1
    assert call_kwargs["build_id"] == ""
    assert call_kwargs["vcs"] is None
    assert call_kwargs["steps_to_run"] == []
    assert call_kwargs["build_dir"] == str(tmp_path)
    assert call_kwargs["load_run_config"] is False

    # Verify BuildRunner.clean_cache was called
    mock_buildrunner.clean_cache.assert_called_once()


@mock.patch("buildrunner.cli.BuildRunner")
@mock.patch("buildrunner.cli.BuildRunnerConfig")
@mock.patch("buildrunner.cli.parse_args")
def test_clean_cache_with_global_config_overrides(
    mock_parse_args, mock_config, mock_buildrunner, tmp_path
):
    """Test that clean_cache() correctly passes global config overrides"""
    # Setup mock args with security scan options
    mock_args = mock.Mock()
    mock_args.directory = str(tmp_path)
    mock_args.global_config_file = None
    mock_args.config_file = None
    mock_args.log_generated_files = False
    mock_args.print_generated_files = False
    mock_args.platform = "linux/amd64"
    mock_args.disable_multi_platform = True
    mock_args.security_scan_enabled = "true"
    mock_args.security_scan_scanner = "trivy"
    mock_args.security_scan_version = "0.50.0"
    mock_args.security_scan_config_file = None
    mock_args.security_scan_max_score_threshold = 7.5
    mock_parse_args.return_value = mock_args

    # Call clean_cache
    cli.clean_cache()

    # Verify global_config_overrides were passed correctly
    call_kwargs = mock_config.initialize_instance.call_args.kwargs
    assert "global_config_overrides" in call_kwargs
    overrides = call_kwargs["global_config_overrides"]
    assert overrides["disable-multi-platform"] is True
    assert overrides["security-scan"]["enabled"] is True
    assert overrides["security-scan"]["scanner"] == "trivy"
    assert overrides["security-scan"]["version"] == "0.50.0"
    assert overrides["security-scan"]["max-score-threshold"] == 7.5
