from unittest import mock

import pytest

from buildrunner import BuildRunnerConfig
from buildrunner.errors import BuildRunnerProcessingError
from buildrunner.steprunner.tasks.run import RunBuildStepRunnerTask


@pytest.fixture(name="initialize_config", autouse=True)
def fixture_initialize_config(tmp_path):
    buildrunner_path = tmp_path / "buildrunner.yaml"
    buildrunner_path.write_text("steps: {'step1': {}}")
    BuildRunnerConfig.initialize_instance(
        build_id="123",
        vcs=None,
        build_dir=str(tmp_path),
        global_config_file=None,
        run_config_file=str(buildrunner_path),
        build_time=0,
        build_number=1,
        push=False,
        steps_to_run=None,
        log_generated_files=False,
        global_config_overrides={},
        platform=None,
    )


@pytest.fixture(name="task")
def fixture_task():
    """
    A RunBuildStepRunnerTask with __init__ skipped, since it otherwise
    requires a live docker daemon connection. Only the attributes used by
    wait() are populated.
    """
    task = object.__new__(RunBuildStepRunnerTask)
    task._docker_client = mock.MagicMock()
    task._docker_client.inspect_container.return_value = {
        "NetworkSettings": {"IPAddress": "10.0.0.5"},
        "State": {"Status": "running"},
    }
    task.step_runner = mock.MagicMock()
    task.step_runner.network_name = None
    return task


def _mock_docker_runner_class(exit_code, container_id="abc123", log_output=b""):
    mock_class = mock.MagicMock()
    nc_tester = mock_class.return_value
    nc_tester.exit_code = exit_code
    nc_tester.container = {"Id": container_id}
    nc_tester.docker_client.logs.return_value = log_output
    return mock_class


def test_wait_uses_busybox_nc_and_succeeds_on_open_port(task):
    mock_class = _mock_docker_runner_class(exit_code=0)
    with mock.patch("buildrunner.steprunner.tasks.run.DockerRunner", mock_class):
        task.wait("mycontainer", 1234)

    nc_tester = mock_class.return_value
    _, start_kwargs = nc_tester.start.call_args
    assert start_kwargs["shell"] == "nc -n -z 10.0.0.5 1234"
    assert nc_tester.cleanup.called

    image_config_args, _ = mock_class.ImageConfig.call_args
    assert image_config_args[0].endswith("/busybox:latest")


def test_wait_raises_immediately_on_unexpected_exit_code(task):
    """
    A non-amd64 host running the (amd64-only) nc image previously used here
    causes docker to exit with 255 (exec format error) rather than nc's own
    0/1. That must fail fast instead of retrying until the timeout.
    """
    mock_class = _mock_docker_runner_class(
        exit_code=255,
        log_output=b"standard_init_linux.go:228: exec user process caused: exec format error\n",
    )
    with mock.patch("buildrunner.steprunner.tasks.run.DockerRunner", mock_class):
        with pytest.raises(BuildRunnerProcessingError) as exc_info:
            task.wait("mycontainer", 1234)

    assert "Unexpected exit code 255" in str(exc_info.value)
    assert "exec format error" in str(exc_info.value)
    assert mock_class.return_value.cleanup.called


def test_wait_retries_on_closed_port_then_succeeds(task):
    mock_class = mock.MagicMock()
    nc_testers = [mock.MagicMock(), mock.MagicMock()]
    for nc_tester in nc_testers:
        nc_tester.container = {"Id": "abc123"}
    nc_testers[0].exit_code = 1
    nc_testers[1].exit_code = 0
    mock_class.side_effect = nc_testers

    with mock.patch("buildrunner.steprunner.tasks.run.DockerRunner", mock_class):
        with mock.patch("time.sleep"):
            task.wait("mycontainer", 1234)

    assert mock_class.call_count == 2
    assert all(nc_tester.cleanup.called for nc_tester in nc_testers)
