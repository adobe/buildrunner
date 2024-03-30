import os
from unittest import mock

import pytest
import yaml

from buildrunner.config.models import GlobalSecurityScanConfig
from buildrunner.errors import BuildRunnerProcessingError
from buildrunner.steprunner.tasks import push


@pytest.fixture(name="config_mock")
def fixture_config_mock():
    with mock.patch(
        "buildrunner.steprunner.tasks.push.BuildRunnerConfig"
    ) as buildrunner_config_mock:
        config_mock = mock.MagicMock()
        buildrunner_config_mock.get_instance.return_value = config_mock
        yield config_mock


def _generate_built_image(num: int) -> mock.MagicMock():
    image = mock.MagicMock()
    image.repo = f"repo{num}"
    image.tag = f"tag{num}"
    image.platform = f"platform{num}"
    return image


def test__security_scan_mp():
    image_info = mock.MagicMock()
    image_info.built_images = [_generate_built_image(num) for num in range(1, 4)]

    self_mock = mock.MagicMock()
    self_mock._security_scan.side_effect = (
        lambda **kwargs: None
        if kwargs["repository"] == "repo2"
        else {"image": kwargs["repository"]}
    )
    push_security_scan = mock.MagicMock()

    assert push.PushBuildStepRunnerTask._security_scan_mp(
        self_mock,
        image_info,
        "image_ref1",
        push_security_scan,
    ) == {
        "docker:security-scan": {
            "platform1": {"image": "repo1"},
            "platform3": {"image": "repo3"},
        }
    }
    assert self_mock._security_scan.call_args_list == [
        mock.call(
            repository="repo1",
            tag="tag1",
            log_image_ref="image_ref1:platform1",
            pull=True,
            push_security_scan=push_security_scan,
        ),
        mock.call(
            repository="repo2",
            tag="tag2",
            log_image_ref="image_ref1:platform2",
            pull=True,
            push_security_scan=push_security_scan,
        ),
        mock.call(
            repository="repo3",
            tag="tag3",
            log_image_ref="image_ref1:platform3",
            pull=True,
            push_security_scan=push_security_scan,
        ),
    ]


def test__security_scan_mp_empty():
    image_info = mock.MagicMock()
    image_info.built_images = [_generate_built_image(num) for num in range(1, 4)]

    self_mock = mock.MagicMock()
    self_mock._security_scan.return_value = None

    assert not push.PushBuildStepRunnerTask._security_scan_mp(
        self_mock,
        image_info,
        "image_ref1",
        None,
    )


@mock.patch(
    "buildrunner.steprunner.tasks.push.MultiplatformImageBuilder.get_native_platform"
)
def test__security_scan_single(get_native_platform_mock):
    get_native_platform_mock.return_value = "platform1"
    self_mock = mock.MagicMock()
    self_mock._security_scan.return_value = {"result": True}
    push_security_scan = mock.MagicMock()

    assert push.PushBuildStepRunnerTask._security_scan_single(
        self_mock, "repo1", "abc123", push_security_scan
    ) == {"docker:security-scan": {"platform1": {"result": True}}}
    self_mock._security_scan.assert_called_once_with(
        repository="repo1",
        tag="abc123",
        log_image_ref="repo1:abc123",
        pull=False,
        push_security_scan=push_security_scan,
    )


@mock.patch(
    "buildrunner.steprunner.tasks.push.MultiplatformImageBuilder.get_native_platform"
)
def test__security_scan_single_empty(get_native_platform_mock):
    get_native_platform_mock.return_value = "platform1"
    self_mock = mock.MagicMock()
    self_mock._security_scan.return_value = None
    assert (
        push.PushBuildStepRunnerTask._security_scan_single(
            self_mock, "repo1", "abc123", None
        )
        == {}
    )
    self_mock._security_scan.assert_called_once()


def test__security_scan_scanner_disabled(config_mock):
    config_mock.global_config.security_scan = GlobalSecurityScanConfig(enabled=False)
    self_mock = mock.MagicMock()
    assert not push.PushBuildStepRunnerTask._security_scan(
        self_mock,
        repository="repo1",
        tag="tag1",
        log_image_ref="image1",
        pull=False,
        push_security_scan=None,
    )
    self_mock._security_scan_trivy.assert_not_called()


def test__security_scan_scanner_trivy(config_mock):
    security_scan_mock = mock.MagicMock()
    merged_config_mock = mock.MagicMock()
    config_mock.global_config.security_scan = security_scan_mock
    security_scan_mock.merge_scan_config.return_value = merged_config_mock
    merged_config_mock.enabled = True
    merged_config_mock.scanner = "trivy"
    push_security_scan = mock.MagicMock()

    self_mock = mock.MagicMock()
    self_mock._security_scan_trivy.return_value = {"result": True}
    assert push.PushBuildStepRunnerTask._security_scan(
        self_mock,
        repository="repo1",
        tag="tag1",
        log_image_ref="image1",
        pull=False,
        push_security_scan=push_security_scan,
    ) == {"result": True}
    self_mock._security_scan_trivy.assert_called_once_with(
        security_scan_config=merged_config_mock,
        repository="repo1",
        tag="tag1",
        log_image_ref="image1 (repo1:tag1)",
        pull=False,
    )
    security_scan_mock.merge_scan_config.assert_called_once_with(push_security_scan)


def test__security_scan_scanner_unsupported(config_mock):
    config_mock.global_config.security_scan = GlobalSecurityScanConfig(
        enabled=True, scanner="bogus"
    )
    self_mock = mock.MagicMock()
    with pytest.raises(Exception) as exc_info:
        assert push.PushBuildStepRunnerTask._security_scan(
            self_mock,
            repository="repo1",
            tag="tag1",
            log_image_ref="image1",
            pull=False,
            push_security_scan=None,
        ) == {"result": True}
    assert "Unsupported scanner" in str(exc_info.value)
    self_mock._security_scan_trivy.assert_not_called()


@pytest.mark.parametrize(
    "input_results, parsed_results",
    [
        ({}, {"max_score": 0, "vulnerabilities": []}),
        ({"Results": []}, {"max_score": 0, "vulnerabilities": []}),
        (
            {"Results": [{"Vulnerabilities": [{}]}]},
            {
                "max_score": 0,
                "vulnerabilities": [
                    {
                        "cvss_v3_score": None,
                        "severity": None,
                        "vulnerability_id": None,
                        "pkg_name": None,
                        "installed_version": None,
                        "primary_url": None,
                    }
                ],
            },
        ),
        (
            {
                "Results": [
                    {
                        "Vulnerabilities": [
                            {
                                "CVSS": {"nvd": {"V3Score": 1.0}},
                                "Severity": "HIGH",
                                "VulnerabilityID": "CVE1",
                                "PkgName": "pkg1",
                                "InstalledVersion": "v1",
                                "PrimaryURL": "url1",
                            }
                        ]
                    }
                ]
            },
            {
                "max_score": 1.0,
                "vulnerabilities": [
                    {
                        "cvss_v3_score": 1.0,
                        "severity": "HIGH",
                        "vulnerability_id": "CVE1",
                        "pkg_name": "pkg1",
                        "installed_version": "v1",
                        "primary_url": "url1",
                    }
                ],
            },
        ),
    ],
)
def test__security_scan_trivy_parse_results(input_results, parsed_results):
    security_scan_config = GlobalSecurityScanConfig()
    assert (
        push.PushBuildStepRunnerTask._security_scan_trivy_parse_results(
            security_scan_config, input_results
        )
        == parsed_results
    )


@pytest.mark.parametrize(
    "max_score_threshold, exception_raised",
    [
        (None, False),
        (2.11, False),
        (2.1, True),
    ],
)
def test__security_scan_trivy_parse_results_max_score_threshold(
    max_score_threshold, exception_raised
):
    security_scan_config = GlobalSecurityScanConfig(
        **{"max-score-threshold": max_score_threshold}
    )
    input_results = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "CVSS": {"nvd": {"V3Score": 1.0}},
                    },
                    {
                        "CVSS": {"nvd": {"V3Score": None}},
                    },
                    {
                        "CVSS": {"nvd": {"V3Score": 0}},
                    },
                ],
            },
            {
                "Vulnerabilities": [
                    {
                        "CVSS": {"nvd": {"V3Score": 2.1}},
                    },
                    {
                        "CVSS": {"nvd": {"V3Score": 1.9}},
                    },
                ],
            },
        ]
    }
    if exception_raised:
        with pytest.raises(
            BuildRunnerProcessingError, match="is above the configured threshold"
        ):
            push.PushBuildStepRunnerTask._security_scan_trivy_parse_results(
                security_scan_config,
                input_results,
            )
    else:
        push.PushBuildStepRunnerTask._security_scan_trivy_parse_results(
            security_scan_config, input_results
        )


@mock.patch("buildrunner.steprunner.tasks.push.DockerRunner")
@mock.patch("buildrunner.steprunner.tasks.push.tempfile")
@mock.patch("buildrunner.steprunner.tasks.push.os")
def test__security_scan_trivy(
    os_mock, tempfile_mock, docker_runner_mock, config_mock, tmp_path
):
    os_mock.makedirs = os.makedirs
    os_mock.path = os.path
    os_mock.getuid.return_value = "123"
    os_mock.getgid.return_value = "234"

    run_path = tmp_path / "run"
    run_path.mkdir()
    tempfile_mock.TemporaryDirectory.return_value.__enter__.return_value = str(run_path)

    config_mock.global_config.docker_registry = "registry1"
    security_scan_config = GlobalSecurityScanConfig()
    self_mock = mock.MagicMock()
    self_mock._security_scan_trivy_parse_results.return_value = {"parsed_results": True}
    config_mock.global_config.temp_dir = str(tmp_path)

    def _call_run(command, **kwargs):
        _ = kwargs
        if command.startswith("trivy --config"):
            (run_path / "results.json").write_text('{"results": True}')
        return 0

    docker_runner_mock.return_value.run.side_effect = _call_run

    assert push.PushBuildStepRunnerTask._security_scan_trivy(
        self_mock,
        security_scan_config=security_scan_config,
        repository="repo1",
        tag="tag1",
        log_image_ref="image1",
        pull=True,
    ) == {"parsed_results": True}

    assert set(path.name for path in tmp_path.iterdir()) == {
        "run",
        "trivy-cache",
    }
    assert set(path.name for path in run_path.iterdir()) == {
        "config.yaml",
        "results.json",
    }
    assert (
        yaml.safe_load((run_path / "config.yaml").read_text())
        == security_scan_config.config
    )
    assert (
        yaml.safe_load((run_path / "config.yaml").read_text())
        == security_scan_config.config
    )

    docker_runner_mock.ImageConfig.assert_called_once_with(
        "registry1/aquasec/trivy:latest",
        pull_image=False,
    )
    docker_runner_mock.assert_called_once_with(
        docker_runner_mock.ImageConfig.return_value,
        log=self_mock.step_runner.log,
    )
    docker_runner_mock().start.assert_called_once_with(
        entrypoint="/bin/sh",
        volumes={
            str(run_path): "/trivy",
            str(tmp_path / "trivy-cache"): "/root/.cache/trivy",
            "/var/run/docker.sock": "/var/run/docker.sock",
        },
    )
    assert docker_runner_mock().run.call_args_list == [
        mock.call("trivy --version", console=self_mock.step_runner.log),
        mock.call(
            "trivy --config /trivy/config.yaml image -f json -o /trivy/results.json repo1:tag1",
            console=self_mock.step_runner.log,
        ),
        mock.call(
            "chown -R 123:234 /trivy",
            log=self_mock.step_runner.log,
        ),
    ]
    docker_runner_mock().cleanup.assert_called_once_with()
    self_mock._security_scan_trivy_parse_results.assert_called_once_with(
        security_scan_config, {"results": True}
    )


@mock.patch("buildrunner.steprunner.tasks.push.DockerRunner")
def test__security_scan_trivy_failure(docker_runner_mock, config_mock, tmp_path):
    config_mock.global_config.docker_registry = "registry1"
    security_scan_config = GlobalSecurityScanConfig()
    self_mock = mock.MagicMock()
    config_mock.global_config.temp_dir = str(tmp_path)
    docker_runner_mock.return_value.run.return_value = 1

    with pytest.raises(BuildRunnerProcessingError, match="Could not scan"):
        push.PushBuildStepRunnerTask._security_scan_trivy(
            self_mock,
            security_scan_config=security_scan_config,
            repository="repo1",
            tag="tag1",
            log_image_ref="image1",
            pull=True,
        )

    docker_runner_mock.ImageConfig.assert_called_once()
    docker_runner_mock.assert_called_once()
    docker_runner_mock().start.assert_called_once()
    assert docker_runner_mock().run.call_count == 3
    docker_runner_mock().cleanup.assert_called_once()
    self_mock._security_scan_trivy_parse_results.assert_not_called()


@mock.patch("buildrunner.steprunner.tasks.push.DockerRunner")
def test__security_scan_trivy_file_not_created(
    docker_runner_mock, config_mock, tmp_path
):
    config_mock.global_config.docker_registry = "registry1"
    security_scan_config = GlobalSecurityScanConfig()
    self_mock = mock.MagicMock()
    config_mock.global_config.temp_dir = str(tmp_path)
    docker_runner_mock.return_value.run.return_value = 0

    with pytest.raises(BuildRunnerProcessingError, match="does not exist"):
        push.PushBuildStepRunnerTask._security_scan_trivy(
            self_mock,
            security_scan_config=security_scan_config,
            repository="repo1",
            tag="tag1",
            log_image_ref="image1",
            pull=True,
        )


@mock.patch("buildrunner.steprunner.tasks.push.DockerRunner")
@mock.patch("buildrunner.steprunner.tasks.push.tempfile")
def test__security_scan_trivy_empty_file(
    tempfile_mock, docker_runner_mock, config_mock, tmp_path
):
    run_path = tmp_path / "run"
    run_path.mkdir()
    tempfile_mock.TemporaryDirectory.return_value.__enter__.return_value = str(run_path)

    config_mock.global_config.docker_registry = "registry1"
    security_scan_config = GlobalSecurityScanConfig()
    self_mock = mock.MagicMock()
    config_mock.global_config.temp_dir = str(tmp_path)

    def _call_run(command, **kwargs):
        _ = kwargs
        if command.startswith("trivy --config"):
            (run_path / "results.json").write_text("{}")
        return 0

    docker_runner_mock.return_value.run.side_effect = _call_run

    with pytest.raises(BuildRunnerProcessingError, match="Could not read results file"):
        push.PushBuildStepRunnerTask._security_scan_trivy(
            self_mock,
            security_scan_config=security_scan_config,
            repository="repo1",
            tag="tag1",
            log_image_ref="image1",
            pull=True,
        )
