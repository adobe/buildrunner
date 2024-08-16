"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
import ssl
import tempfile
from typing import Tuple
import urllib.parse
import docker

from buildrunner.errors import BuildRunnerError, BuildRunnerConfigurationError

try:
    # Newer API
    Client = docker.client.Client  # pylint: disable=no-member
except Exception:  # pylint: disable=broad-except
    try:
        # Older API
        Client = docker.client.APIClient

    except Exception:  # pylint: disable=broad-except
        # Older API
        Client = docker.api.client.APIClient

DOCKER_API_VERSION = "auto"
DOCKER_DEFAULT_DOCKERD_URL = "unix:///var/run/docker.sock"
MAX_TIMEOUT = 3600  # 1 hour


class BuildRunnerContainerError(BuildRunnerError):
    """Error indicating an issue managing a Docker container"""

    pass


def new_client(
    dockerd_url=None,
    tls=False,
    tls_verify=False,
    cert_path=None,
    timeout=None,
):
    """
    Return a newly configured Docker client.
    """
    _dockerd_url = dockerd_url
    if not _dockerd_url:
        _dockerd_url = os.getenv("DOCKER_HOST", DOCKER_DEFAULT_DOCKERD_URL)

    _tls = tls

    tls_config = None
    if tls_verify or str(os.environ.get("DOCKER_TLS_VERIFY", "0")) == "1":
        _tls = True
        _cert_path = os.getenv("DOCKER_CERT_PATH", cert_path)
        if not _cert_path:
            raise BuildRunnerConfigurationError(
                "TLS connection specified but cannot determine cert path"
                " (from DOCKER_CERT_PATH env variable)"
            )

        ca_cert_path = os.path.join(_cert_path, "ca.pem")
        client_cert = (
            os.path.join(_cert_path, "cert.pem"),
            os.path.join(_cert_path, "key.pem"),
        )

        tls_config = docker.tls.TLSConfig(
            ssl_version=ssl.PROTOCOL_TLSv1,
            client_cert=client_cert,
            verify=ca_cert_path,
            assert_hostname=False,
        )

    if _tls:
        # make sure the scheme is https
        url_parts = urllib.parse.urlparse(_dockerd_url)
        if url_parts.scheme == "tcp":
            _dockerd_url = urllib.parse.urlunparse(("https",) + url_parts[1:])

    args = {}
    if timeout is not None:
        if timeout == 0:
            args["timeout"] = MAX_TIMEOUT
        else:
            args["timeout"] = timeout
    return Client(
        base_url=_dockerd_url, version=DOCKER_API_VERSION, tls=tls_config, **args
    )


def force_remove_container(docker_client, container):
    """
    Force removes a container from the given docker client.
    :param docker_client: the docker client
    :param container: the container
    """
    docker_client.remove_container(
        container,
        force=True,
        v=True,
    )


def get_dockerfile(
    dockerfile: str, temp_dir: str = None, path: str = None
) -> Tuple[str, bool]:
    """
    Check if the dockerfile exists, if not create a temporary file and write the dockerfile to it.
    :param dockerfile: the dockerfile
    :param temp_dir: the temporary directory
    :return: the dockerfile and a boolean indicating if the dockerfile was created
    """
    cleanup_dockerfile = False
    curr_dockerfile = None

    if path and path != "." and not dockerfile:
        if os.path.exists(path):
            if os.path.exists(os.path.join(path, "Dockerfile")):
                curr_dockerfile = os.path.join(path, "Dockerfile")
            else:
                raise BuildRunnerConfigurationError(
                    f"Path {path} exists but does not contain a Dockerfile"
                )
        else:
            raise BuildRunnerConfigurationError(
                f"Path {path} does not exist, cannot find Dockerfile"
            )
    elif dockerfile:
        if os.path.exists(dockerfile):
            curr_dockerfile = dockerfile
        else:
            # pylint: disable=consider-using-with
            df_file = tempfile.NamedTemporaryFile(delete=False, dir=temp_dir)
            try:
                df_file.write(dockerfile.encode("utf-8"))
                cleanup_dockerfile = True
                curr_dockerfile = df_file.name
            finally:
                df_file.close()
    return curr_dockerfile, cleanup_dockerfile
