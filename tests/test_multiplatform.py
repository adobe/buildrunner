import os
from typing import List
from unittest.mock import MagicMock, call, patch

import pytest
from python_on_whales import docker
from python_on_whales.exceptions import DockerException

from buildrunner.docker.multiplatform_image_builder import MultiplatformImageBuilder
from buildrunner.docker.image_info import BuiltImageInfo


TEST_DIR = os.path.dirname(__file__)

# FIXME: These tests can be broken if a custom buildx builder is set as default  # pylint: disable=fixme


@pytest.fixture(autouse=True)
def fixture_uuid_mock():
    with patch("buildrunner.docker.multiplatform_image_builder.uuid") as uuid_mock:
        counter = 0

        def _get_uuid():
            nonlocal counter
            counter += 1
            return f"uuid{counter}"

        uuid_mock.uuid4.side_effect = _get_uuid
        yield uuid_mock


@pytest.fixture(autouse=True)
def fixture_init_config():
    with patch(
        "buildrunner.docker.multiplatform_image_builder.BuildRunnerConfig"
    ) as config_mock:
        config_mock.get_instance.return_value.global_config.disable_multi_platform = (
            False
        )
        yield config_mock


def _actual_images_match_expected(
    built_image: BuiltImageInfo, expected_tags
) -> List[str]:
    actual_images = built_image.built_images
    missing_images = []
    for expected_tag in expected_tags:
        found = False
        for actual_image in actual_images:
            if actual_image.tag.endswith(expected_tag):
                found = True
        if not found:
            missing_images.append(expected_tag)
    return missing_images


def test_start_local_registry():
    with MultiplatformImageBuilder() as mpib:
        mpib._start_local_registry()
        registry_name = mpib._mp_registry_info.name

        # Check that the registry is running and only one is found with that name
        registry_container = docker.ps(filters={"name": registry_name})
        assert len(registry_container) == 1
        registry_container = registry_container[0]

        # Check that the registry only has one mount
        mounts = registry_container.mounts
        assert len(mounts) == 1
        mount = mounts[0]
        assert mount.type == "volume"
        volume_name = mount.name
        assert docker.volume.exists(volume_name)

        # Check that the running container is the registry
        assert registry_container.config.image == "registry"
        assert registry_container.state.running

    # Check that the registry is stopped and cleaned up
    registry_container = docker.ps(filters={"name": registry_name})
    assert len(registry_container) == 0
    assert not docker.volume.exists(volume_name)


def test_start_local_registry_on_build():
    with MultiplatformImageBuilder() as mpib:
        # Check that the registry is NOT running
        assert mpib._mp_registry_info is None
        assert mpib._local_registry_is_running is False

        # Building should start the registry
        test_path = f"{TEST_DIR}/test-files/multiplatform"
        mpib.build_multiple_images(
            platforms=["linux/arm64", "linux/amd64"],
            path=test_path,
            file=f"{test_path}/Dockerfile",
            use_threading=False,
        )

        # Check that the registry is running and only one is found with that name
        registry_name = mpib._mp_registry_info.name
        first_registry_name = registry_name
        registry_container = docker.ps(filters={"name": registry_name})
        assert len(registry_container) == 1
        registry_container = registry_container[0]

        # Check that the registry only has one mount
        mounts = registry_container.mounts
        assert len(mounts) == 1
        mount = mounts[0]
        assert mount.type == "volume"
        volume_name = mount.name
        assert docker.volume.exists(volume_name)

        # Check that the running container is the registry
        assert registry_container.config.image == "registry"
        assert registry_container.state.running

        # Building again should not start a new registry
        mpib.build_multiple_images(
            platforms=["linux/arm64", "linux/amd64"],
            path=test_path,
            file=f"{test_path}/Dockerfile",
            use_threading=False,
        )

        registry_name = mpib._mp_registry_info.name
        assert first_registry_name == registry_name

    # Check that the registry is stopped and cleaned up
    registry_container = docker.ps(filters={"name": registry_name})
    assert len(registry_container) == 0
    assert not docker.volume.exists(volume_name)


@pytest.mark.parametrize(
    "platforms, expected_image_tags",
    [(["linux/arm64"], ["uuid1-linux-arm64"])],
)
def test_tag_native_platform(platforms, expected_image_tags):
    test_path = f"{TEST_DIR}/test-files/multiplatform"
    with MultiplatformImageBuilder() as mpib:
        built_image = mpib.build_multiple_images(
            platforms,
            path=test_path,
            file=f"{test_path}/Dockerfile",
            use_threading=False,
        )

        assert (
            built_image is not None and len(built_image.built_images) == 1
        ), f"Failed to build for {platforms}"
        missing_images = _actual_images_match_expected(built_image, expected_image_tags)
        assert (
            missing_images == []
        ), f"Failed to find {missing_images} in {[image.repo for image in built_image.built_images]}"

        mpib.tag_native_platform(built_image)
        # Check that the image was tagged and present
        found_image = docker.image.list(
            filters={"reference": built_image.built_images[0].image_ref}
        )
        assert len(found_image) == 1
        assert built_image.built_images[0].image_ref in found_image[0].repo_tags

        # Check that intermediate images are on the host registry
        found_image = docker.image.list(
            filters={"reference": f"{built_image.built_images[0].image_ref}*"}
        )
        assert len(found_image) == 1


@pytest.mark.parametrize(
    "name, platforms, expected_image_tags",
    [("test-image-tag-2000", ["linux/arm64"], ["uuid1-linux-arm64"])],
)
def test_tag_native_platform_multiple_tags(name, platforms, expected_image_tags):
    tags = ["latest", "0.1.0"]
    test_path = f"{TEST_DIR}/test-files/multiplatform"
    with MultiplatformImageBuilder() as mpib:
        built_image = mpib.build_multiple_images(
            platforms=platforms,
            path=test_path,
            file=f"{test_path}/Dockerfile",
            use_threading=False,
        )

        assert (
            built_image is not None and len(built_image.built_images) == 1
        ), f"Failed to build {name} for {platforms}"
        missing_images = _actual_images_match_expected(built_image, expected_image_tags)
        assert (
            missing_images == []
        ), f"Failed to find {missing_images} in {[image.repo for image in built_image.built_images]}"

        built_image.add_tagged_image(repo=name, tags=tags)
        mpib.tag_native_platform(built_image)
        # Check that the image was tagged and present
        found_image = docker.image.list(filters={"reference": f"{name}*"})
        assert len(found_image) == 1
        for tag in tags:
            assert f"{name}:{tag}" in found_image[0].repo_tags

        # Check that intermediate images are not on host registry
        found_image = docker.image.list(
            filters={"reference": f"{built_image.built_images[0].image_ref}*"}
        )
        assert len(found_image) == 0


@pytest.mark.parametrize(
    "name, platforms, expected_image_tags",
    [("test-image-tag-2000", ["linux/arm64"], ["uuid1-linux-arm64"])],
)
def test_tag_native_platform_keep_images(name, platforms, expected_image_tags):
    tag = "latest"
    test_path = f"{TEST_DIR}/test-files/multiplatform"
    try:
        with MultiplatformImageBuilder() as mpib:
            built_image = mpib.build_multiple_images(
                platforms=platforms,
                path=test_path,
                file=f"{test_path}/Dockerfile",
                use_threading=False,
            )

            assert (
                built_image is not None and len(built_image.built_images) == 1
            ), f"Failed to build {name} for {platforms}"
            missing_images = _actual_images_match_expected(
                built_image, expected_image_tags
            )
            assert (
                missing_images == []
            ), f"Failed to find {missing_images} in {[image.repo for image in built_image.built_images]}"

            built_image.add_tagged_image(repo=name, tags=["latest"])
            mpib.tag_native_platform(built_image)

            # Check that the image was tagged and present
            found_image = docker.image.list(filters={"reference": f"{name}:{tag}"})
            assert len(found_image) == 1
            assert f"{name}:{tag}" in found_image[0].repo_tags

            # Check that intermediate images are not on host registry
            found_image = docker.image.list(
                filters={"reference": f"{built_image.built_images[0].image_ref}*"}
            )
            assert len(found_image) == 0

        # Check that the image is still in host registry
        found_image = docker.image.list(filters={"reference": f"{name}:{tag}"})
        assert len(found_image) == 1
    finally:
        docker.image.remove(name, force=True)


def test_push():
    try:
        with MultiplatformImageBuilder() as remote_mp:
            remote_mp._start_local_registry()
            reg_add = remote_mp._build_registry_address()
            assert reg_add is not None

            tags = ["latest", "0.1.0"]
            build_name = f"{reg_add}/test-push-image-2001"
            platforms = ["linux/arm64", "linux/amd64"]

            test_path = f"{TEST_DIR}/test-files/multiplatform"
            with MultiplatformImageBuilder() as mpib:
                built_image = mpib.build_multiple_images(
                    platforms=platforms,
                    path=test_path,
                    file=f"{test_path}/Dockerfile",
                    use_threading=False,
                )

                assert built_image is not None
                built_image.add_tagged_image(repo=build_name, tags=tags)
                mpib.push()

                # Make sure the image isn't in the local registry
                docker.image.remove(build_name, force=True)

                # Pull the image from the remote registry to make sure it is there
                try:
                    docker.image.pull(build_name)
                except DockerException as err:
                    assert (
                        False
                    ), f"Failed to find/pull {build_name} from remote registry: {err}"
                found_image = docker.image.list(filters={"reference": f"{build_name}"})
                assert len(found_image) == 1

    finally:
        print(f"Cleaning up {build_name}")
        docker.image.remove(build_name, force=True)


def test_push_with_dest_names():
    dest_names = None
    try:
        with MultiplatformImageBuilder() as remote_mp:
            remote_mp._start_local_registry()
            reg_add = remote_mp._build_registry_address()
            assert reg_add is not None

            tags = ["latest", "0.1.0"]
            build_name = "test-push-image-2001"
            dest_names = [f"{reg_add}/{build_name}", f"{reg_add}/another-name"]
            platforms = ["linux/arm64", "linux/amd64"]

            test_path = f"{TEST_DIR}/test-files/multiplatform"
            with MultiplatformImageBuilder() as mpib:
                built_image = mpib.build_multiple_images(
                    platforms=platforms,
                    path=test_path,
                    file=f"{test_path}/Dockerfile",
                    use_threading=False,
                )

                assert built_image is not None
                for dest_name in dest_names:
                    built_image.add_tagged_image(repo=dest_name, tags=tags)
                mpib.push()

                # Make sure the image isn't in the local registry
                for dest_name in dest_names:
                    docker.image.remove(dest_name, force=True)

                    # Pull the image from the remote registry to make sure it is there
                    try:
                        docker.image.pull(dest_name)
                    except DockerException as err:
                        assert False, f"Failed to find/pull {dest_name} from remote registry: {err}"
                    found_image = docker.image.list(
                        filters={"reference": f"{dest_name}"}
                    )
                    assert len(found_image) == 1

    finally:
        for dest_name in dest_names:
            print(f"Cleaning up {dest_name}")
            docker.image.remove(dest_name, force=True)


@pytest.mark.parametrize(
    "name, platforms, expected_image_tags",
    [
        (
            "test-build-image-2000",
            ["linux/arm64"],
            ["uuid1-linux-arm64"],
        ),
        (
            "test-build-image-2001",
            ["linux/amd64", "linux/arm64"],
            ["uuid1-linux-amd64", "uuid1-linux-arm64"],
        ),
    ],
)
@patch("buildrunner.docker.multiplatform_image_builder.docker.image.remove")
@patch("buildrunner.docker.multiplatform_image_builder.docker.push")
@patch(
    "buildrunner.docker.multiplatform_image_builder.docker.buildx.imagetools.inspect"
)
@patch("buildrunner.docker.multiplatform_image_builder.docker.buildx.build")
def test_build(
    mock_build,
    mock_imagetools_inspect,
    mock_push,
    mock_remove,
    name,
    platforms,
    expected_image_tags,
):
    _ = mock_build
    _ = mock_push
    _ = mock_remove
    mock_imagetools_inspect.return_value = MagicMock()
    mock_imagetools_inspect.return_value.config.digest = "myfakeimageid"
    test_path = f"{TEST_DIR}/test-files/multiplatform"
    with MultiplatformImageBuilder() as mpib:
        built_image = mpib.build_multiple_images(
            platforms=platforms,
            path=test_path,
            file=f"{test_path}/Dockerfile",
            use_threading=False,
        )

        assert len(built_image.built_images) == len(platforms)
        assert len(built_image.built_images) == len(expected_image_tags)

        missing_images = _actual_images_match_expected(built_image, expected_image_tags)
        assert (
            missing_images == []
        ), f"Failed to find {missing_images} in {[image.repo for image in built_image.built_images]}"


@patch("buildrunner.docker.multiplatform_image_builder.docker.image.remove")
@patch("buildrunner.docker.multiplatform_image_builder.docker.push")
@patch(
    "buildrunner.docker.multiplatform_image_builder.docker.buildx.imagetools.inspect"
)
@patch("buildrunner.docker.multiplatform_image_builder.docker.buildx.build")
def test_build_multiple_builds(
    mock_build, mock_imagetools_inspect, mock_push, mock_remove
):
    _ = mock_remove
    mock_imagetools_inspect.return_value = MagicMock()
    mock_imagetools_inspect.return_value.config.digest = "myfakeimageid"
    platforms1 = ["linux/amd64", "linux/arm64"]
    expected_image_tags1 = [
        "uuid1-linux-amd64",
        "uuid1-linux-arm64",
    ]

    platforms2 = ["linux/amd64", "linux/arm64"]
    expected_image_tags2 = [
        "uuid2-linux-amd64",
        "uuid2-linux-arm64",
    ]

    test_path = f"{TEST_DIR}/test-files/multiplatform"
    with MultiplatformImageBuilder() as mpib:
        # Build set 1
        built_image1 = mpib.build_multiple_images(
            platforms=platforms1,
            path=test_path,
            file=f"{test_path}/Dockerfile",
            use_threading=False,
        )

        # Build set 2
        built_image2 = mpib.build_multiple_images(
            platforms=platforms2,
            path=test_path,
            file=f"{test_path}/Dockerfile",
            use_threading=False,
        )

        # Check set 1
        assert len(built_image1.built_images) == len(platforms1)
        assert len(built_image1.built_images) == len(expected_image_tags1)
        missing_images = _actual_images_match_expected(
            built_image1, expected_image_tags1
        )
        assert (
            missing_images == []
        ), f"Failed to find {missing_images} in {[image.repo for image in built_image1.built_images1]}"

        # Check set 2
        assert len(built_image2.built_images) == len(platforms2)
        assert len(built_image2.built_images) == len(expected_image_tags2)
        missing_images = _actual_images_match_expected(
            built_image2, expected_image_tags2
        )
        assert (
            missing_images == []
        ), f"Failed to find {missing_images} in {[image.repo for image in built_image2.built_images]}"

    assert mock_build.call_count == 4
    image_name = mock_build.call_args.kwargs["tags"][0].rsplit(":", 1)[0]
    assert mock_build.call_args_list == [
        call(
            test_path,
            tags=[f"{image_name}:uuid1-linux-amd64"],
            platforms=["linux/amd64"],
            load=True,
            file=f"{test_path}/Dockerfile",
            build_args={"DOCKER_REGISTRY": None},
            builder=None,
            cache=False,
            cache_from=None,
            cache_to=None,
            pull=False,
            target=None,
            stream_logs=True,
        ),
        call(
            test_path,
            tags=[f"{image_name}:uuid1-linux-arm64"],
            platforms=["linux/arm64"],
            load=True,
            file=f"{test_path}/Dockerfile",
            build_args={"DOCKER_REGISTRY": None},
            builder=None,
            cache=False,
            cache_from=None,
            cache_to=None,
            pull=False,
            target=None,
            stream_logs=True,
        ),
        call(
            test_path,
            tags=[f"{image_name}:uuid2-linux-amd64"],
            platforms=["linux/amd64"],
            load=True,
            file=f"{test_path}/Dockerfile",
            build_args={"DOCKER_REGISTRY": None},
            builder=None,
            cache=False,
            cache_from=None,
            cache_to=None,
            pull=False,
            target=None,
            stream_logs=True,
        ),
        call(
            test_path,
            tags=[f"{image_name}:uuid2-linux-arm64"],
            platforms=["linux/arm64"],
            load=True,
            file=f"{test_path}/Dockerfile",
            build_args={"DOCKER_REGISTRY": None},
            builder=None,
            cache=False,
            cache_from=None,
            cache_to=None,
            pull=False,
            target=None,
            stream_logs=True,
        ),
    ]
    assert mock_push.call_count == 4
    assert mock_push.call_args_list == [
        call([f"{image_name}:uuid1-linux-amd64"]),
        call([f"{image_name}:uuid1-linux-arm64"]),
        call([f"{image_name}:uuid2-linux-amd64"]),
        call([f"{image_name}:uuid2-linux-arm64"]),
    ]
    assert mock_imagetools_inspect.call_count == 4
    assert mock_imagetools_inspect.call_args_list == [
        call(f"{image_name}:uuid1-linux-amd64"),
        call(f"{image_name}:uuid1-linux-arm64"),
        call(f"{image_name}:uuid2-linux-amd64"),
        call(f"{image_name}:uuid2-linux-arm64"),
    ]


@pytest.mark.parametrize(
    "builder, cache_builders, return_cache_options",
    [
        ("b1", None, True),
        ("b1", [], True),
        ("b1", ["b1"], True),
        ("b2", ["b1"], False),
    ],
)
def test__get_build_cache_options(builder, cache_builders, return_cache_options):
    multi_platform = MultiplatformImageBuilder(
        cache_to="to-loc",
        cache_from="from-loc",
        cache_builders=cache_builders,
    )
    assert multi_platform._get_build_cache_options(builder) == (
        {"cache_to": "to-loc", "cache_from": "from-loc"} if return_cache_options else {}
    )


def test_use_build_registry():
    registry_mpib = MultiplatformImageBuilder()
    registry_mpib._start_local_registry()
    build_registry = registry_mpib._build_registry_address()
    try:
        with MultiplatformImageBuilder(build_registry=build_registry) as mpib:
            # Building should use the registry
            test_path = f"{TEST_DIR}/test-files/multiplatform"
            built_image = mpib.build_multiple_images(
                platforms=["linux/arm64", "linux/amd64"],
                path=test_path,
                file=f"{test_path}/Dockerfile",
                use_threading=False,
            )
            assert all(
                image_info.repo.startswith(f"{build_registry}/")
                for image_info in built_image.images_by_platform.values()
            )

            # Check that the registry is running and only one is found with that name
            assert (
                mpib._mp_registry_info is None
            ), "The local registry should not have been started when using a build registry"
    finally:
        registry_mpib._stop_local_registry()
