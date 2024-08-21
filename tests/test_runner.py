import os
import sys
import docker.errors

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

import buildrunner.config.loader  # noqa: E402
from buildrunner.docker.daemon import DAEMON_IMAGE_NAME  # noqa: E402
from buildrunner import docker as buildrunner_docker  # noqa: E402
from buildrunner import (  # noqa: E402
    cli,
    __version__,
    BuildRunnerConfigurationError,
)


def run_tests(argv, master_config_file=None, global_config_files=None):
    args = cli.parse_args(argv)

    # are we just printing the version?
    if args.print_version:
        print(__version__)
        return os.EX_OK

    global_config_files = global_config_files or []
    if master_config_file:
        buildrunner.config.loader.MASTER_GLOBAL_CONFIG_FILE = master_config_file
        if not global_config_files or master_config_file != global_config_files[0]:
            global_config_files.insert(0, master_config_file)
    if global_config_files:
        buildrunner.config.DEFAULT_GLOBAL_CONFIG_FILES = global_config_files

    try:
        build_runner = cli.initialize_br(args)

        # Pull Docker daemon proxy
        image_name = f"{build_runner.buildrunner_config.global_config.docker_registry}/{DAEMON_IMAGE_NAME}"
        docker_client = buildrunner_docker.new_client(
            timeout=build_runner.docker_timeout
        )
        docker_client.pull(image_name)

        build_runner.run()
        if build_runner.exit_code:
            return build_runner.exit_code
    except BuildRunnerConfigurationError as brce:
        print(str(brce))
        return os.EX_CONFIG
    except docker.errors.ImageNotFound as inf:
        print(str(inf))
        return os.EX_CONFIG
    return os.EX_OK
