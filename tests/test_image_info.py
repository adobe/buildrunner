from unittest import mock

import pytest

from buildrunner.docker.image_info import BuiltTaggedImage, BuiltImageInfo


@pytest.mark.parametrize(
    "system_result, machine_result, platform_result",
    [
        ("Darwin", "x86_64", "linux/amd64"),
        ("Darwin", "aarch64", "linux/arm64/v7"),
        ("Linux", "x86_64", "linux/amd64"),
        ("Linux", "aarch64", "linux/arm64/v7"),
        ("Bogus", "Noarch", "bogus"),
    ],
)
@mock.patch("buildrunner.docker.image_info.python_platform")
def test_find_native_platform(
    platform_mock,
    system_result,
    machine_result,
    platform_result,
):
    platform_mock.system.return_value = system_result
    platform_mock.machine.return_value = machine_result

    run_id = "abc123"
    built_image = BuiltImageInfo(id=run_id)
    for platform in ("bogus", "linux/arm64/v7", "linux/amd64"):
        built_image.add_platform_image(
            platform,
            BuiltTaggedImage(
                repo="repo1",
                tag=f'{run_id}-{platform.replace("/", "-")}',
                digest="12345",
                platform=platform,
            ),
        )
    assert (
        built_image.native_platform_image
        == built_image.images_by_platform[platform_result]
    )
