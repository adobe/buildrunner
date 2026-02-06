import os
import tempfile
import json
import platform
import sys
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


def test_multiplatform_image_tags_separate_artifacts():
    """
    Test that multiple build steps pushing to the same repository with different tags
    create separate artifact entries in artifacts.json, keyed by step name.
    """
    with tempfile.TemporaryDirectory(prefix="buildrunner.results-") as temp_dir:
        command_line = [
            "buildrunner-tester",
            "-d",
            top_dir_path,
            "-b",
            temp_dir,
            "--keep-step-artifacts",
            "-f",
            os.path.join(
                f"{TEST_DIR}/test-files", "test-multiplatform-image-tags.yaml"
            ),
        ]

        # Print troubleshooting info for GitHub Actions
        print("\n" + "=" * 80)
        print("TROUBLESHOOTING: test_multiplatform_image_tags_separate_artifacts")
        print("=" * 80)
        print(f"Platform: {platform.system()} {platform.machine()}")
        print(f"Python: {sys.version}")
        print(f"Working directory: {os.getcwd()}")
        print(f"Temp directory: {temp_dir}")
        print(f"Command line: {' '.join(command_line)}")
        print(f"Config file: {test_dir_path}/config-files/etc-buildrunner.yaml")

        # Print Docker info
        try:
            import subprocess

            docker_version = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if docker_version.returncode == 0:
                print(f"Docker version: {docker_version.stdout.strip()}")

            buildx_version = subprocess.run(
                ["docker", "buildx", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if buildx_version.returncode == 0:
                print(f"Buildx version: {buildx_version.stdout.strip()}")

            # Check for busybox images in cache
            busybox_images = subprocess.run(
                [
                    "docker",
                    "images",
                    "busybox",
                    "--format",
                    "{{.Repository}}:{{.Tag}} {{.ID}}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if busybox_images.returncode == 0 and busybox_images.stdout.strip():
                print("Cached busybox images:")
                for line in busybox_images.stdout.strip().split("\n"):
                    print(f"  {line}")
        except Exception as docker_info_err:
            print(f"Could not get Docker info: {docker_info_err}")

        print("=" * 80 + "\n")

        try:
            result = test_runner.run_tests(
                command_line,
                master_config_file=f"{test_dir_path}/config-files/etc-buildrunner.yaml",
                global_config_files=[
                    f"{test_dir_path}/config-files/etc-buildrunner.yaml",
                    f"{test_dir_path}/config-files/dot-buildrunner.yaml",
                ],
            )
            print(f"\nTROUBLESHOOTING: Test runner returned exit code: {result}")

            # List files in temp directory for debugging
            if os.path.exists(temp_dir):
                print(f"TROUBLESHOOTING: Files in {temp_dir}:")
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        filepath = os.path.join(root, file)
                        size = os.path.getsize(filepath)
                        print(f"  {filepath} ({size} bytes)")

            # If test failed, print the build log
            if result != 0:
                build_log_path = os.path.join(temp_dir, "build.log")
                if os.path.exists(build_log_path):
                    print("\nTROUBLESHOOTING: Build log contents (last 100 lines):")
                    print("-" * 80)
                    with open(build_log_path, "r") as log_file:
                        lines = log_file.readlines()
                        for line in lines[-100:]:
                            print(line.rstrip())
                    print("-" * 80)
                else:
                    print(f"\nTROUBLESHOOTING: Build log not found at {build_log_path}")

            assert 0 == result, f"Expected exit code 0, got {result}"
        except Exception as e:
            print(f"\nTROUBLESHOOTING: Exception caught: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            raise

        artifacts_file = f"{temp_dir}/artifacts.json"
        assert os.path.exists(artifacts_file)
        with open(artifacts_file, "r") as artifacts_file:
            artifacts = json.load(artifacts_file)

            # Remove build.log if present
            if "build.log" in artifacts:
                del artifacts["build.log"]

            # Verify both artifact entries exist with step-prefixed keys
            java17_key = "build-java17/adobe/buildrunner-test-multitag"
            java11_key = "build-java11/adobe/buildrunner-test-multitag"

            assert java17_key in artifacts, (
                f"Expected artifact key '{java17_key}' not found in artifacts.json"
            )
            assert java11_key in artifacts, (
                f"Expected artifact key '{java11_key}' not found in artifacts.json"
            )

            # Verify java17 artifact structure and tags
            java17_artifact = artifacts[java17_key]
            assert java17_artifact["type"] == "docker-image"
            assert (
                java17_artifact["docker:repository"]
                == "adobe/buildrunner-test-multitag"
            )
            assert "java17" in java17_artifact["docker:tags"], (
                f"Expected 'java17' tag not found in {java17_artifact['docker:tags']}"
            )
            # Verify step-specific default tag is included (should contain step name)
            java17_tags = java17_artifact["docker:tags"]
            assert any("build-java17" in tag for tag in java17_tags), (
                f"Expected step-specific tag containing 'build-java17' not found in {java17_tags}"
            )
            assert "docker:image" in java17_artifact
            assert "docker:platforms" in java17_artifact
            assert len(java17_artifact["docker:platforms"]) == 2, (
                "Expected multiplatform build with 2 platforms"
            )

            # Verify java11 artifact structure and tags
            java11_artifact = artifacts[java11_key]
            assert java11_artifact["type"] == "docker-image"
            assert (
                java11_artifact["docker:repository"]
                == "adobe/buildrunner-test-multitag"
            )
            assert "java11" in java11_artifact["docker:tags"], (
                f"Expected 'java11' tag not found in {java11_artifact['docker:tags']}"
            )
            # Verify step-specific default tag is included (should contain step name)
            java11_tags = java11_artifact["docker:tags"]
            assert any("build-java11" in tag for tag in java11_tags), (
                f"Expected step-specific tag containing 'build-java11' not found in {java11_tags}"
            )
            assert "docker:image" in java11_artifact
            assert "docker:platforms" in java11_artifact
            assert len(java11_artifact["docker:platforms"]) == 2, (
                "Expected multiplatform build with 2 platforms"
            )

            # Verify they are different entries (not overwriting each other)
            assert java17_artifact != java11_artifact, (
                "Artifacts should be different entries, not overwriting each other"
            )

            # Verify no other unexpected artifacts (except build.log which we already removed)
            remaining_artifacts = set(artifacts.keys()) - {java17_key, java11_key}
            assert len(remaining_artifacts) == 0, (
                f"Unexpected artifacts found: {remaining_artifacts}"
            )
