"""
Copyright 2026 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from unittest import mock

import pytest

from buildrunner.docker import BuildRunnerContainerError
from buildrunner.docker.runner import DockerRunner


@pytest.fixture(name="runner")
def fixture_runner():
    """
    A DockerRunner with __init__ skipped, since it otherwise requires a live
    docker daemon connection. Only the attributes used by run_and_capture()
    are populated.
    """
    runner = object.__new__(DockerRunner)
    runner.container = {"Id": "container123"}
    runner.shell = "/bin/sh"
    runner.run_log_debug = False
    runner.docker_client = mock.MagicMock()
    runner.docker_client.exec_create.return_value = {"Id": "exec123"}
    return runner


def test_run_and_capture_returns_exit_code_and_decoded_stdout(runner):
    """
    Regression test for XENG-10989: artifact-listing commands must be able
    to get their output back directly from the exec call, without writing
    to a file that a container-root process creates and a host process must
    later remove.
    """
    runner.docker_client.exec_start.return_value = (b"line1\nline2\n", b"")
    runner.docker_client.exec_inspect.return_value = {"ExitCode": 0}

    exit_code, output = runner.run_and_capture("stat -c '%n' /some/path")

    assert exit_code == 0
    assert output == "line1\nline2\n"

    # must not stream (would return a generator, not the full buffer) and
    # must demux so stdout doesn't contain the `-x` shell trace
    _, kwargs = runner.docker_client.exec_start.call_args
    assert kwargs["stream"] is False
    assert kwargs["demux"] is True


def test_run_and_capture_no_stdout_returns_empty_string(runner):
    runner.docker_client.exec_start.return_value = (None, None)
    runner.docker_client.exec_inspect.return_value = {"ExitCode": 1}

    exit_code, output = runner.run_and_capture("false")

    assert exit_code == 1
    assert output == ""


def test_run_and_capture_passes_iterable_command_through(runner):
    """
    A non-string (list/tuple) command must be handed to exec verbatim rather
    than being wrapped in the shell. run() relies on this for its cp/tar/chown
    commands, and both now share _build_exec_cmdv.
    """
    runner.docker_client.exec_start.return_value = (b"", b"")
    runner.docker_client.exec_inspect.return_value = {"ExitCode": 0}

    runner.run_and_capture(["find", "/some/dir", "-type", "f"])

    exec_args, _ = runner.docker_client.exec_create.call_args
    # second positional arg to exec_create is the command vector, passed
    # through unwrapped (not [shell, "-xc", ...])
    assert exec_args[1] == ["find", "/some/dir", "-type", "f"]


def test_run_and_capture_raises_when_exit_code_is_none(runner):
    runner.docker_client.exec_start.return_value = (b"", b"")
    runner.docker_client.exec_inspect.return_value = {"ExitCode": None}

    with pytest.raises(BuildRunnerContainerError):
        runner.run_and_capture("stat /some/path")


def test_run_and_capture_logs_stderr(runner):
    log = mock.MagicMock()
    log.clean_output.side_effect = lambda output: (
        output if isinstance(output, str) else output.decode("utf-8", errors="replace")
    )
    runner.docker_client.exec_start.return_value = (b"out", b"+ stat ...\n")
    runner.docker_client.exec_inspect.return_value = {"ExitCode": 0}

    runner.run_and_capture("stat -c '%n' /some/path", log=log)

    assert log.info.called


def test_run_and_capture_requires_started_container():
    runner = object.__new__(DockerRunner)
    runner.container = None
    runner.shell = "/bin/sh"

    with pytest.raises(BuildRunnerContainerError):
        runner.run_and_capture("stat /some/path")


def test_run_and_capture_raises_on_missing_exit_code(runner):
    runner.docker_client.exec_start.return_value = (b"", b"")
    runner.docker_client.exec_inspect.return_value = {}

    with pytest.raises(BuildRunnerContainerError):
        runner.run_and_capture("stat /some/path")


def test_run_still_delegates_to_build_exec_cmdv_and_returns_exit_code(runner):
    """
    run() was refactored to share command building with run_and_capture via
    _build_exec_cmdv; verify it still wraps the command and returns the exit
    code unchanged.
    """
    runner.docker_client.exec_start.return_value = b"some output\n"
    runner.docker_client.exec_inspect.return_value = {"ExitCode": 7}

    exit_code = runner.run("echo hi")

    assert exit_code == 7
    exec_args, _ = runner.docker_client.exec_create.call_args
    assert exec_args[1] == ["/bin/sh", "-xc", "echo hi"]


def test_build_exec_cmdv_wraps_string_in_shell(runner):
    assert runner._build_exec_cmdv("stat /x") == ["/bin/sh", "-xc", "stat /x"]


def test_build_exec_cmdv_raises_type_error_on_unknown_command(runner):
    with pytest.raises(TypeError):
        runner._build_exec_cmdv(12345)


def test_build_exec_cmdv_raises_when_shell_not_set(runner):
    runner.shell = None

    with pytest.raises(BuildRunnerContainerError):
        runner._build_exec_cmdv(["find", "/x"])
