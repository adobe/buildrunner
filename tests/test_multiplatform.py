import os
from typing import List
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from python_on_whales import Image, docker
from python_on_whales.exceptions import DockerException

from buildrunner.docker.multiplatform_image_builder import (
    ImageInfo, MultiplatformImageBuilder)

TEST_DIR = os.path.basename(os.path.dirname(__file__))

# FIXME: These tests can be broken if a custom buildx builder is set as default  # pylint: disable=fixme


@pytest.fixture(autouse=True)
def fixture_uuid_mock():
    with patch('buildrunner.docker.multiplatform_image_builder.uuid') as uuid_mock:
        counter = 0
        def _get_uuid():
            nonlocal counter
            counter += 1
            return f'uuid{counter}'

        uuid_mock.uuid4.side_effect = _get_uuid
        yield uuid_mock


def actual_images_match_expected(actual_images, expected_images) -> List[str]:
    missing_images = []
    found = False
    for expected_image in expected_images:
        found = False
        for actual_image in actual_images:
            if actual_image.repo.endswith(expected_image):
                found = True
        if not found:
            missing_images.append(expected_image)
    return missing_images


def test_start_local_registry():
    registry_name = None
    volume_name = None

    with MultiplatformImageBuilder() as mp:
        mp._start_local_registry()
        registry_name = mp._mp_registry_info.name

        # Check that the registry is running and only one is found with that name
        registry_container = docker.ps(filters={"name": registry_name})
        assert len(registry_container) == 1
        registry_container = registry_container[0]

        # Check that the registry only has one mount
        mounts = registry_container.mounts
        assert len(mounts) == 1
        mount = mounts[0]
        assert mount.type == 'volume'
        volume_name = mount.name
        assert docker.volume.exists(volume_name)

        # Check that the running container is the registry
        assert registry_container.config.image == 'registry'
        assert registry_container.state.running

    # Check that the registry is stopped and cleaned up
    registry_container = docker.ps(filters={"name": registry_name})
    assert len(registry_container) == 0
    assert not docker.volume.exists(volume_name)


def test_start_local_registry_on_build():
    registry_name = None
    volume_name = None

    with MultiplatformImageBuilder() as mp:
        # Check that the registry is NOT running
        assert mp._mp_registry_info is None
        assert mp._local_registry_is_running is False

        # Building should start the registry
        test_path = f'{TEST_DIR}/test-files/multiplatform'
        mp.build_multiple_images(mp_image_name='test-images-2000-start-on-build',
                                 platforms=['linux/arm64', 'linux/amd64'],
                                 path=test_path,
                                 file=f'{test_path}/Dockerfile',
                                 do_multiprocessing=False)


        # Check that the registry is running and only one is found with that name
        registry_name = mp._mp_registry_info.name
        first_registry_name = registry_name
        registry_container = docker.ps(filters={"name": registry_name})
        assert len(registry_container) == 1
        registry_container = registry_container[0]

        # Check that the registry only has one mount
        mounts = registry_container.mounts
        assert len(mounts) == 1
        mount = mounts[0]
        assert mount.type == 'volume'
        volume_name = mount.name
        assert docker.volume.exists(volume_name)

        # Check that the running container is the registry
        assert registry_container.config.image == 'registry'
        assert registry_container.state.running

        # Building again should not start a new registry
        mp.build_multiple_images(mp_image_name='test-images-2000-start-on-build2',
                                 platforms=['linux/arm64', 'linux/amd64'],
                                 path=test_path,
                                 file=f'{test_path}/Dockerfile',
                                 do_multiprocessing=False)

        registry_name = mp._mp_registry_info.name
        assert first_registry_name == registry_name

    # Check that the registry is stopped and cleaned up
    registry_container = docker.ps(filters={"name": registry_name})
    assert len(registry_container) == 0
    assert not docker.volume.exists(volume_name)


@pytest.mark.parametrize("name, in_mock_os, in_mock_arch, built_images, expected_image",
    [
        # platform = linux/arm64
        (
            'test-images-2000',
            'linux',
            'arm64',
            {'test-images-2000': [ImageInfo('localhost:32828/test-images-2000-linux-amd64', ['latest']),
                                    ImageInfo('localhost:32828/test-images-2000-linux-arm64', ['latest'])]},
            'localhost:32828/test-images-2000-linux-arm64:latest'
        ),
        # OS does not match for Darwin change to linux
        (
            'test-images-2000',
            'Darwin',
            'arm64',
            {'test-images-2000': [ImageInfo('localhost:32829/test-images-2000-linux-amd64', ['latest']),
                                    ImageInfo('localhost:32829/test-images-2000-linux-arm64', ['latest'])]},
            'localhost:32829/test-images-2000-linux-arm64:latest'
        ),
        # platform = linux/amd64
        (
            'test-images-2000',
            'linux',
            'amd64',
            {'test-images-2000': [ImageInfo('localhost:32811/test-images-2000-linux-amd64', ['latest']),
                                    ImageInfo('localhost:32811/test-images-2000-linux-arm64', ['latest'])]},
            'localhost:32811/test-images-2000-linux-amd64:latest'
        ),
        # No match found, get the first image
        (
            'test-images-2000',
            'linux',
            'arm',
            {'test-images-2000': [ImageInfo('localhost:32830/test-images-2000-linux-amd64', ['0.1.0']),
                                    ImageInfo('localhost:32830/test-images-2000-linux-amd64', ['0.2.0'])]},
            'localhost:32830/test-images-2000-linux-amd64:0.1.0'
        ),
        # Built_images for name does not exist in dictionary
        (
            'test-images-2001',
            'linux',
            'arm64',
            {'test-images-2000': [ImageInfo('localhost:32831/test-images-2000-linux-amd64', ['latest']),
                                    ImageInfo('localhost:32831/test-images-2000-linux-arm64', ['latest'])]},
            None
        ),
        # Built_images for name is empty
        (
            'test-images-2000',
            'linux',
            'arm64',
            {'test-images-2000': []},
            None
        ),
    ])
@patch('buildrunner.docker.multiplatform_image_builder.machine')
@patch('buildrunner.docker.multiplatform_image_builder.system')
def test_find_native_platform(mock_os,
                              mock_arch,
                              name,
                              in_mock_os,
                              in_mock_arch,
                              built_images,
                              expected_image):
    mock_os.return_value = in_mock_os
    mock_arch.return_value = in_mock_arch
    with MultiplatformImageBuilder() as mp:
        mp._intermediate_built_images = built_images
        found_platform = mp._find_native_platform_images(name)
        assert str(found_platform) == str(expected_image)


@pytest.mark.parametrize("name, platforms, expected_image_names",[
    ('test-image-tag-2000',
     ['linux/arm64'],
     ['buildrunner-mp-uuid1-linux-arm64']
    )])
def test_tag_single_platform(name, platforms, expected_image_names):
    tag='latest'
    test_path = f'{TEST_DIR}/test-files/multiplatform'
    with MultiplatformImageBuilder() as mp:
        built_images = mp.build_multiple_images(mp_image_name=name,
                                platforms=platforms,
                                path=test_path,
                                file=f'{test_path}/Dockerfile',
                                do_multiprocessing=False)

        assert built_images is not None and len(built_images) == 1, f'Failed to build {name} for {platforms}'
        missing_images = actual_images_match_expected(built_images, expected_image_names)
        assert missing_images == [], f'Failed to find {missing_images} in {[image.repo for image in built_images]}'

        mp.tag_single_platform(name)
        # Check that the image was tagged and present
        found_image = docker.image.list(filters={'reference': f'{name}*'})
        assert len(found_image) == 1
        assert f'{name}:{tag}' in found_image[0].repo_tags

        # Check that intermediate images are not on host registry
        found_image = docker.image.list(filters={'reference': f'{built_images[0]}*'})
        assert len(found_image) == 0

    # Check that the image has be removed for host registry
    found_image = docker.image.list(filters={'reference': f'{name}*'})
    assert len(found_image) == 0


@pytest.mark.parametrize("name, platforms, expected_image_names",[
    ('test-image-tag-2000',
     ['linux/arm64'],
     ['buildrunner-mp-uuid1-linux-arm64']
    )])
def test_tag_single_platform_multiple_tags(name, platforms, expected_image_names):
    tags=['latest', '0.1.0']
    test_path = f'{TEST_DIR}/test-files/multiplatform'
    with MultiplatformImageBuilder() as mp:
        built_images = mp.build_multiple_images(mp_image_name=name,
                                platforms=platforms,
                                path=test_path,
                                file=f'{test_path}/Dockerfile',
                                do_multiprocessing=False)

        assert built_images is not None and len(built_images) == 1, f'Failed to build {name} for {platforms}'
        missing_images = actual_images_match_expected(built_images, expected_image_names)
        assert missing_images == [], f'Failed to find {missing_images} in {[image.repo for image in built_images]}'

        mp.tag_single_platform(name=name, tags=tags)
        # Check that the image was tagged and present
        found_image = docker.image.list(filters={'reference': f'{name}*'})
        assert len(found_image) == 1
        for tag in tags:
            assert f'{name}:{tag}' in found_image[0].repo_tags

        # Check that intermediate images are not on host registry
        found_image = docker.image.list(filters={'reference': f'{built_images[0]}*'})
        assert len(found_image) == 0

    # Check that the tagged image has be removed for host registry
    found_image = docker.image.list(filters={'reference': f'{name}*'})
    assert len(found_image) == 0


@pytest.mark.parametrize("name, platforms, expected_image_names",[
    ('test-image-tag-2000',
     ['linux/arm64'],
     ['buildrunner-mp-uuid1-linux-arm64']
    )])
def test_tag_single_platform_keep_images(name, platforms, expected_image_names):
    tag='latest'
    test_path = f'{TEST_DIR}/test-files/multiplatform'
    try:
        with MultiplatformImageBuilder(keep_images=True) as mp:
            built_images = mp.build_multiple_images(mp_image_name=name,
                                    platforms=platforms,
                                    path=test_path,
                                    file=f'{test_path}/Dockerfile',
                                    do_multiprocessing=False)

            assert built_images is not None and len(built_images) == 1, f'Failed to build {name} for {platforms}'
            missing_images = actual_images_match_expected(built_images, expected_image_names)
            assert missing_images == [], f'Failed to find {missing_images} in {[image.repo for image in built_images]}'

            mp.tag_single_platform(name)

            # Check that the image was tagged and present
            found_image = docker.image.list(filters={'reference': f'{name}*'})
            assert len(found_image) == 1
            assert f'{name}:{tag}' in found_image[0].repo_tags

            # Check that intermediate images are not on host registry
            found_image = docker.image.list(filters={'reference': f'{built_images[0]}*'})
            assert len(found_image) == 0

        # Check that the image is still in host registry
        found_image = docker.image.list(filters={'reference': f'{name}*'})
        assert len(found_image) == 1
    finally:
        docker.image.remove(name, force=True)


def test_push():
    try:
        with MultiplatformImageBuilder() as remote_mp:
            remote_mp._start_local_registry()
            reg_add = remote_mp.registry_address()
            assert reg_add is not None

            tags=['latest', '0.1.0']
            build_name = f'{reg_add}/test-push-image-2001'
            platforms = ['linux/arm64','linux/amd64']

            test_path = f'{TEST_DIR}/test-files/multiplatform'
            with MultiplatformImageBuilder() as mp:
                built_images = mp.build_multiple_images(mp_image_name=build_name,
                                        platforms=platforms,
                                        path=test_path,
                                        file=f'{test_path}/Dockerfile',
                                        do_multiprocessing=False,
                                        tags=tags)

                assert built_images is not None
                mp.push(build_name)

                # Make sure the image isn't in the local registry
                docker.image.remove(build_name, force=True)

                # Pull the image from the remote registry to make sure it is there
                try:
                    docker.image.pull(build_name)
                except DockerException as err:
                    assert False, f'Failed to find/pull {build_name} from remote registry: {err}'
                found_image = docker.image.list(filters={'reference': f'{build_name}'})
                assert len(found_image) == 1

    finally:
        print(f'Cleaning up {build_name}')
        docker.image.remove(build_name, force=True)


def test_push_with_dest_names():
    dest_names = None
    built_images = None
    try:
        with MultiplatformImageBuilder() as remote_mp:
            remote_mp._start_local_registry()
            reg_add = remote_mp.registry_address()
            assert reg_add is not None

            tags=['latest', '0.1.0']
            build_name = 'test-push-image-2001'
            dest_names = [f'{reg_add}/{build_name}',f'{reg_add}/another-name']
            platforms = ['linux/arm64','linux/amd64']

            test_path = f'{TEST_DIR}/test-files/multiplatform'
            with MultiplatformImageBuilder() as mp:
                built_images = mp.build_multiple_images(mp_image_name=build_name,
                                        platforms=platforms,
                                        path=test_path,
                                        file=f'{test_path}/Dockerfile',
                                        do_multiprocessing=False,
                                        tags=tags)

                assert built_images is not None
                mp.push(name=build_name, dest_names=dest_names)

                # Make sure the image isn't in the local registry
                for dest_name in dest_names:
                    docker.image.remove(dest_name, force=True)

                    # Pull the image from the remote registry to make sure it is there
                    try:
                        docker.image.pull(dest_name)
                    except DockerException as err:
                        assert False, f'Failed to find/pull {dest_name} from remote registry: {err}'
                    found_image = docker.image.list(filters={'reference': f'{dest_name}'})
                    assert len(found_image) == 1

    finally:
        for dest_name in dest_names:
            print(f'Cleaning up {dest_name}')
            docker.image.remove(dest_name, force=True)


@pytest.mark.parametrize("name, platforms, expected_image_names",[
    ('test-build-image-2000',
     ['linux/arm64'],
     ['buildrunner-mp-uuid1-linux-arm64']
    ),
    ('test-build-image-2001',
     ['linux/amd64', 'linux/arm64'],
     ['buildrunner-mp-uuid1-linux-amd64', 'buildrunner-mp-uuid1-linux-arm64']
    )
])
@patch('buildrunner.docker.multiplatform_image_builder.docker.image.remove')
@patch('buildrunner.docker.multiplatform_image_builder.docker.image.inspect')
@patch('buildrunner.docker.multiplatform_image_builder.docker.push')
@patch('buildrunner.docker.multiplatform_image_builder.docker.image.pull')
@patch('buildrunner.docker.multiplatform_image_builder.docker.buildx.build')
def test_build(mock_build, mock_pull, mock_push, mock_inspect, mock_remove, name, platforms, expected_image_names):
    mock_inspect.return_value = MagicMock()
    mock_inspect.return_value.id = 'myfakeimageid'
    test_path = f'{TEST_DIR}/test-files/multiplatform'
    with MultiplatformImageBuilder() as mp:
        built_images = mp.build_multiple_images(mp_image_name=name,
                                platforms=platforms,
                                path=test_path,
                                file=f'{test_path}/Dockerfile',
                                do_multiprocessing=False)

        assert len(built_images) ==  len(platforms)
        assert len(built_images) ==  len(expected_image_names)

        missing_images = actual_images_match_expected(built_images, expected_image_names)
        assert missing_images == [], f'Failed to find {missing_images} in {[image.repo for image in built_images]}'


@patch('buildrunner.docker.multiplatform_image_builder.docker.image.remove')
@patch('buildrunner.docker.multiplatform_image_builder.docker.image.inspect')
@patch('buildrunner.docker.multiplatform_image_builder.docker.push')
@patch('buildrunner.docker.multiplatform_image_builder.docker.image.pull')
@patch('buildrunner.docker.multiplatform_image_builder.docker.buildx.build')
def test_build_multiple_builds(mock_build, mock_pull, mock_push, mock_inspect, mock_remove):
    mock_inspect.return_value = MagicMock()
    mock_inspect.return_value.id = 'myfakeimageid'
    name1 = 'test-build-multi-image-2001'
    platforms1 = ['linux/amd64', 'linux/arm64']
    expected_image_names1 = ['buildrunner-mp-uuid1-linux-amd64', 'buildrunner-mp-uuid1-linux-arm64']

    name2 = 'test-build-multi-image-2002'
    platforms2 = ['linux/amd64', 'linux/arm64']
    expected_image_names2 = ['buildrunner-mp-uuid2-linux-amd64', 'buildrunner-mp-uuid2-linux-arm64']

    test_path = f'{TEST_DIR}/test-files/multiplatform'
    with MultiplatformImageBuilder() as mp:
        # Build set 1
        built_images1 = mp.build_multiple_images(mp_image_name=name1,
                                platforms=platforms1,
                                path=test_path,
                                file=f'{test_path}/Dockerfile',
                                do_multiprocessing=False)

        # Build set 2
        built_images2 = mp.build_multiple_images(mp_image_name=name2,
                                platforms=platforms2,
                                path=test_path,
                                file=f'{test_path}/Dockerfile',
                                do_multiprocessing=False)

        # Check set 1
        assert len(built_images1) ==  len(platforms1)
        assert len(built_images1) ==  len(expected_image_names1)
        missing_images = actual_images_match_expected(built_images1, expected_image_names1)
        assert missing_images == [], f'Failed to find {missing_images} in {[image.repo for image in built_images1]}'

        # Check set 2
        assert len(built_images2) ==  len(platforms2)
        assert len(built_images2) ==  len(expected_image_names2)
        missing_images = actual_images_match_expected(built_images2, expected_image_names2)
        assert missing_images == [], f'Failed to find {missing_images} in {[image.repo for image in built_images2]}'

    assert mock_build.call_count == 4
    prefix = mock_build.call_args.kwargs['tags'][0].split('buildrunner-mp')[0]
    assert mock_build.call_args_list == [
        call(
            'tests/test-files/multiplatform',
            tags=[f'{prefix}buildrunner-mp-uuid1-linux-amd64:latest'],
            platforms=['linux/amd64'],
            load=True,
            file='tests/test-files/multiplatform/Dockerfile',
            build_args={'DOCKER_REGISTRY': None},
            builder=None,
            cache=False,
            cache_from=None,
            pull=False
        ),
        call(
            'tests/test-files/multiplatform',
            tags=[f'{prefix}buildrunner-mp-uuid1-linux-arm64:latest'],
            platforms=['linux/arm64'],
            load=True,
            file='tests/test-files/multiplatform/Dockerfile',
            build_args={'DOCKER_REGISTRY': None},
            builder=None,
            cache=False,
            cache_from=None,
            pull=False
        ),
        call(
            'tests/test-files/multiplatform',
            tags=[f'{prefix}buildrunner-mp-uuid2-linux-amd64:latest'],
            platforms=['linux/amd64'],
            load=True,
            file='tests/test-files/multiplatform/Dockerfile',
            build_args={'DOCKER_REGISTRY': None},
            builder=None,
            cache=False,
            cache_from=None,
            pull=False
        ),
        call(
            'tests/test-files/multiplatform',
            tags=[f'{prefix}buildrunner-mp-uuid2-linux-arm64:latest'],
            platforms=['linux/arm64'],
            load=True,
            file='tests/test-files/multiplatform/Dockerfile',
            build_args={'DOCKER_REGISTRY': None},
            builder=None,
            cache=False,
            cache_from=None,
            pull=False
        ),
    ]
    assert mock_push.call_count == 4
    assert mock_push.call_args_list == [
        call([f'{prefix}buildrunner-mp-uuid1-linux-amd64:latest']),
        call([f'{prefix}buildrunner-mp-uuid1-linux-arm64:latest']),
        call([f'{prefix}buildrunner-mp-uuid2-linux-amd64:latest']),
        call([f'{prefix}buildrunner-mp-uuid2-linux-arm64:latest']),
    ]
    assert mock_pull.call_count == 4
    assert mock_pull.call_args_list == [
        call(f'{prefix}buildrunner-mp-uuid1-linux-amd64:latest'),
        call(f'{prefix}buildrunner-mp-uuid1-linux-arm64:latest'),
        call(f'{prefix}buildrunner-mp-uuid2-linux-amd64:latest'),
        call(f'{prefix}buildrunner-mp-uuid2-linux-arm64:latest'),
    ]


@pytest.mark.parametrize("name, tags, platforms, expected_image_names",[
    ('test-build-tag-image-2000',
     ['latest', '0.1.0'],
     ['linux/arm64'],
     ['buildrunner-mp-uuid1-linux-arm64']
    ),
    ('test-build-tag-image-2001',
     ['latest', '0.2.0'],
     ['linux/amd64', 'linux/arm64'],
     ['buildrunner-mp-uuid1-linux-amd64', 'buildrunner-mp-uuid1-linux-arm64']
    )
])
def test_build_with_tags(name, tags, platforms, expected_image_names):
    test_path = f'{TEST_DIR}/test-files/multiplatform'
    with MultiplatformImageBuilder() as mp:
        built_images = mp.build_multiple_images(mp_image_name=name,
                                platforms=platforms,
                                path=test_path,
                                file=f'{test_path}/Dockerfile',
                                tags=tags,
                                do_multiprocessing=False)

        assert len(built_images) ==  len(platforms)
        assert len(built_images) ==  len(expected_image_names)
        missing_images = actual_images_match_expected(built_images, expected_image_names)
        assert missing_images == [], f'Failed to find {missing_images} in {[image.repo for image in built_images]}'


def test_no_images_built():
    """
    Check that None is returned when no images are built
    """
    with MultiplatformImageBuilder() as mp:
        image = mp._find_native_platform_images('bogus-image-name')
        assert image is None
