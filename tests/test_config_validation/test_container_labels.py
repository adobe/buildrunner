import os
from unittest import mock

import pytest

from buildrunner import BuildRunner, BuildRunnerConfig


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BLANK_GLOBAL_CONFIG = os.path.join(TEST_DIR, "files/blank_global_config.yaml")


@pytest.mark.parametrize(
    "container_labels, result_labels",
    [
        (None, {}),
        ("", {}),
        ("key1=val1", {"key1": "val1"}),
        ("key1=val1,key2=val2", {"key1": "val1", "key2": "val2"}),
        ("key1=val1=val3,key2=val2", {"key1": "val1=val3", "key2": "val2"}),
    ],
)
@mock.patch("buildrunner.detect_vcs")
def test_container_labels(
    detect_vcs_mock,
    container_labels,
    result_labels,
    tmp_path,
):
    id_string = "main-921.ie02ed8.m1705616822"
    type(detect_vcs_mock.return_value).id_string = mock.PropertyMock(
        return_value=id_string
    )
    buildrunner_path = tmp_path / "buildrunner.yaml"
    buildrunner_path.write_text(
        """
        steps:
            build-container:
                build:
                    dockerfile: |
                        FROM {{ DOCKER_REGISTRY }}/nginx:latest
                        RUN printf '{{ BUILDRUNNER_BUILD_NUMBER }}' > /usr/share/nginx/html/index.html
        """
    )
    BuildRunner(
        build_dir=str(tmp_path),
        build_results_dir=str(tmp_path / "buildrunner.results"),
        global_config_file=None,
        run_config_file=str(buildrunner_path),
        build_time=0,
        build_number=1,
        push=False,
        cleanup_images=False,
        cleanup_cache=False,
        steps_to_run=None,
        publish_ports=False,
        log_generated_files=False,
        docker_timeout=30,
        local_images=False,
        platform=None,
        global_config_overrides={},
        container_labels=container_labels,
    )
    assert BuildRunnerConfig.get_instance().container_labels == result_labels
