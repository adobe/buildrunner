import os
import sys

sys.path.insert(
    0,
    os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
)

import buildrunner.config
from buildrunner import (
    cli,
    __version__,
    BuildRunner,
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
        buildrunner.config.MASTER_GLOBAL_CONFIG_FILE = master_config_file
        if (
                not global_config_files
                or master_config_file != global_config_files[0]
        ):
            global_config_files.insert(0, master_config_file)
    if global_config_files:
        buildrunner.config.DEFAULT_GLOBAL_CONFIG_FILES = global_config_files

    try:
        build_runner = BuildRunner(
            args.directory,
            global_config_file=args.global_config_file,
            run_config_file=args.config_file,
            build_number=args.build_number,
            push=args.push,
            colorize_log=not args.no_log_color,
            cleanup_images=not args.keep_images,
            cleanup_step_artifacts=not args.keep_step_artifacts,
            steps_to_run=args.steps,
            publish_ports=args.publish_ports,
            log_generated_files=args.log_generated_files,
            docker_timeout=args.docker_timeout,
            platform=args.platform,
            build_results_dir=args.build_results_dir
        )

        build_runner.run()
        if build_runner.exit_code:
            return build_runner.exit_code
    except BuildRunnerConfigurationError as brce:
        print(str(brce))
        return os.EX_CONFIG
    return os.EX_OK

