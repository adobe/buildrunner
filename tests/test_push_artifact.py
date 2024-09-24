import os
import tempfile
import json
import pytest


from tests import test_runner

test_dir_path = os.path.realpath(os.path.dirname(__file__))
TEST_DIR = os.path.basename(os.path.dirname(__file__))
top_dir_path = os.path.realpath(os.path.dirname(test_dir_path))


def _test_buildrunner_file(
    test_dir, file_name, args, exit_code, artifacts_in_file: dict
):
    with tempfile.TemporaryDirectory(prefix="buildrunner.results-") as temp_dir:
        command_line = [
            "buildrunner-tester",
            "-d",
            top_dir_path,
            "-b",
            temp_dir,
            # Since we are using a fresh temp directory, don't delete it first
            "--keep-step-artifacts",
            "-f",
            os.path.join(test_dir, file_name),
        ]
        if args:
            command_line.extend(args)

        assert exit_code == test_runner.run_tests(
            command_line,
            master_config_file=f"{test_dir_path}/config-files/etc-buildrunner.yaml",
            global_config_files=[
                f"{test_dir_path}/config-files/etc-buildrunner.yaml",
                f"{test_dir_path}/config-files/dot-buildrunner.yaml",
            ],
        )

        artifacts_file = f"{temp_dir}/artifacts.json"
        assert os.path.exists(artifacts_file)
        with open(artifacts_file, "r") as artifacts_file:
            artifacts = json.load(artifacts_file)

            if "build.log" in artifacts.keys():
                del artifacts["build.log"]

            for artifact, is_present in artifacts_in_file.items():
                if is_present:
                    assert artifact in artifacts.keys()
                    del artifacts[artifact]
                else:
                    assert artifact not in artifacts.keys()

        assert len(artifacts) == 0


# Test legacy builder
@pytest.mark.parametrize(
    "test_name, artifacts_in_file",
    [
        ("test-no-artifacts", {}),
        (
            "test-no-artifact-properties",
            {
                "test-no-artifact-properties/test-no-artifact-properties-dir/test1.txt": False,
                "test-no-artifact-properties/test-no-artifacts-properties-dir/test2.txt": False,
                "test-no-artifact-properties/test-no-artifact-properties.txt": False,
            },
        ),
        (
            "test-no-push-properties",
            {
                "test-no-push-properties/test-no-push-properties-dir/test1.txt": True,
                "test-no-push-properties/test-no-push-properties-dir/test2.txt": True,
                "test-no-push-properties/test-no-push-properties.txt": True,
            },
        ),
        (
            "test-push-true",
            {
                "test-push-true/test-push-true-dir/test1.txt": True,
                "test-push-true/test-push-true-dir/test2.txt": True,
                "test-push-true/test-push-true.txt": True,
            },
        ),
        (
            "test-push-false",
            {
                "test-push-false/test-push-false-dir/test1.txt": False,
                "test-push-false/test-push-false-dir/test2.txt": False,
                "test-push-false/test-push-false.txt": False,
            },
        ),
        (
            "single-file-rename",
            {
                "single-file-rename/hello-world.txt": True,
                "single-file-rename/hello-world1.txt": True,
                "single-file-rename/hello-world2.txt": True,
                "single-file-rename/hello.txt": False,
            },
        ),
        (
            "archive-file-rename",
            {
                "archive-file-rename/dir1.tar.gz": True,
                "archive-file-rename/dir1-dir2.tar.gz": True,
                "archive-file-rename/dir3-dir2.tar.gz": True,
                "archive-file-rename/dir2.tar.gz": False,
            },
        ),
    ],
)
def test_artifacts_with_legacy_builder(test_name, artifacts_in_file):
    _test_buildrunner_file(
        f"{TEST_DIR}/test-files",
        "test-push-artifact-legacy.yaml",
        ["-s", test_name],
        0,
        artifacts_in_file,
    )


# Test buildx builder
@pytest.mark.parametrize(
    "test_name, artifacts_in_file",
    [
        ("test-no-artifacts", {}),
        (
            "test-no-artifact-properties",
            {
                "test-no-artifact-properties/test-no-artifact-properties-dir/test1.txt": False,
                "test-no-artifact-properties/test-no-artifacts-properties-dir/test2.txt": False,
                "test-no-artifact-properties/test-no-artifact-properties.txt": False,
            },
        ),
        (
            "test-no-push-properties",
            {
                "test-no-push-properties/test-no-push-properties-dir/test1.txt": True,
                "test-no-push-properties/test-no-push-properties-dir/test2.txt": True,
                "test-no-push-properties/test-no-push-properties.txt": True,
            },
        ),
        (
            "test-push-true",
            {
                "test-push-true/test-push-true-dir/test1.txt": True,
                "test-push-true/test-push-true-dir/test2.txt": True,
                "test-push-true/test-push-true.txt": True,
            },
        ),
        (
            "test-push-false",
            {
                "test-push-false/test-push-false-dir/test1.txt": False,
                "test-push-false/test-push-false-dir/test2.txt": False,
                "test-push-false/test-push-false.txt": False,
            },
        ),
        (
            "single-file-rename",
            {
                "single-file-rename/hello-world.txt": True,
                "single-file-rename/hello-world1.txt": True,
                "single-file-rename/hello-world2.txt": True,
                "single-file-rename/hello.txt": False,
            },
        ),
        (
            "archive-file-rename",
            {
                "archive-file-rename/dir1.tar.gz": True,
                "archive-file-rename/dir1-dir2.tar.gz": True,
                "archive-file-rename/dir3-dir2.tar.gz": True,
                "archive-file-rename/dir2.tar.gz": False,
            },
        ),
    ],
)
def test_artifacts_with_buildx_builder(test_name, artifacts_in_file):
    _test_buildrunner_file(
        f"{TEST_DIR}/test-files",
        "test-push-artifact-buildx.yaml",
        ["-s", test_name],
        0,
        artifacts_in_file,
    )
