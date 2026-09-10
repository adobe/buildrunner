"""
Copyright 2026 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from unittest import mock

import pytest

from buildrunner import BuildRunnerConfig
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
    _retrieve_artifacts()/_archive_dir() are populated.
    """
    task = object.__new__(RunBuildStepRunnerTask)
    task._docker_client = mock.MagicMock()
    task.step = mock.MagicMock()
    task.step_runner = mock.MagicMock()
    task.step_runner.results_dir = "/local/results"
    task.step_runner.network_name = None
    task._get_source_container = mock.MagicMock(return_value="source-container-id")
    return task


def _mock_docker_runner_class(run_and_capture_result, run_exit_code=0):
    mock_class = mock.MagicMock()
    lister = mock_class.return_value
    lister.container = {"Id": "lister123"}
    lister.run.return_value = run_exit_code
    lister.run_and_capture.return_value = run_and_capture_result
    return mock_class


def test_retrieve_artifacts_file_uses_run_and_capture_without_temp_file(task):
    """
    Regression test for XENG-10989: the artifact-listing `stat` command must
    get its output back directly from run_and_capture, rather than writing
    to a temp file under results_dir that a container-root process creates
    and a host process must later remove (which can fail with
    PermissionError under parallel builds).
    """
    task.step.artifacts = {"some/*.txt": None}
    mock_class = _mock_docker_runner_class(
        (0, "some/file.txt~!~regular file\n"),
    )

    with mock.patch("buildrunner.steprunner.tasks.run.DockerRunner", mock_class):
        with mock.patch.object(
            RunBuildStepRunnerTask, "_archive_file"
        ) as mock_archive_file:
            task._retrieve_artifacts()

    lister = mock_class.return_value

    # the stat command must not redirect its output into /stepresults
    stat_cmd = lister.run_and_capture.call_args_list[0].args[0]
    assert ">" not in stat_cmd
    assert "/stepresults/" not in stat_cmd

    # the parsed output correctly identified the file and archived it
    assert mock_archive_file.called
    archive_args = mock_archive_file.call_args.args
    assert archive_args[4] == "some/file.txt"  # artifact_file

    # no run() call should be removing a temp .out file
    for call in lister.run.call_args_list:
        cmd = call.args[0]
        if isinstance(cmd, str):
            assert ".out" not in cmd


def test_retrieve_artifacts_directory_dispatches_to_archive_dir(task):
    task.step.artifacts = {"some/dir": None}
    mock_class = _mock_docker_runner_class(
        (0, "some/dir~!~directory\n"),
    )

    with mock.patch("buildrunner.steprunner.tasks.run.DockerRunner", mock_class):
        with mock.patch.object(
            RunBuildStepRunnerTask, "_archive_dir"
        ) as mock_archive_dir:
            task._retrieve_artifacts()

    assert mock_archive_dir.called
    _, _, artifact_file = mock_archive_dir.call_args.args
    assert artifact_file == "some/dir"


def test_retrieve_artifacts_no_matches_archives_nothing(task):
    task.step.artifacts = {"some/*.txt": None}
    mock_class = _mock_docker_runner_class((1, ""))

    with mock.patch("buildrunner.steprunner.tasks.run.DockerRunner", mock_class):
        with mock.patch.object(
            RunBuildStepRunnerTask, "_archive_file"
        ) as mock_archive_file:
            task._retrieve_artifacts()

    assert not mock_archive_file.called


def test_archive_dir_uncompressed_uses_run_and_capture_without_temp_file(task):
    """
    Regression test for XENG-10989 (second call site): the recursive `find`
    listing used for uncompressed directory artifacts must also come back
    directly from run_and_capture instead of a temp file under results_dir.
    """
    artifact_lister = mock.MagicMock()
    artifact_lister.run_and_capture.return_value = (
        0,
        "some/dir/a.txt\nsome/dir/b.txt\n",
    )
    artifact_lister.run.return_value = 0

    with mock.patch.object(
        RunBuildStepRunnerTask, "_archive_file"
    ) as mock_archive_file:
        task._archive_dir(
            artifact_lister,
            {"format": "uncompressed"},
            "some/dir",
        )

    find_cmd = artifact_lister.run_and_capture.call_args.args[0]
    assert ">" not in find_cmd
    assert "/stepresults/" not in find_cmd
    assert mock_archive_file.call_count == 2

    for call in artifact_lister.run.call_args_list:
        cmd = call.args[0]
        if isinstance(cmd, str):
            assert ".out" not in cmd
