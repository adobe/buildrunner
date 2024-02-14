import logging
import sys
from unittest import mock

import pytest

from buildrunner import loggers


@pytest.fixture(autouse=True)
def fixture_override_colors():
    original_build_colors = loggers.ContainerLogger.BUILD_LOG_COLORS
    original_service_colors = loggers.ContainerLogger.SERVICE_LOG_COLORS
    loggers.ContainerLogger.BUILD_LOG_COLORS = loggers.ColorQueue("yellow", "blue")
    loggers.ContainerLogger.SERVICE_LOG_COLORS = loggers.ColorQueue(
        "purple",
        "cyan",
        "red",
        "green",
        "purple",
    )
    yield
    loggers.ContainerLogger.BUILD_LOG_COLORS = original_build_colors
    loggers.ContainerLogger.SERVICE_LOG_COLORS = original_service_colors


@pytest.mark.parametrize(
    "debug, no_color, disable_timestamps, log_level, console_format, file_format",
    [
        (
            False,
            False,
            False,
            logging.INFO,
            "%(log_color)s%(asctime)s %(levelname)-8s %(message)s",
            "%(log_color)s%(asctime)s %(levelname)-8s %(message)s",
        ),
        (
            True,
            True,
            True,
            logging.DEBUG,
            "%(log_color)s%(levelname)-8s %(message)s",
            "%(log_color)s%(asctime)s %(levelname)-8s %(message)s",
        ),
    ],
)
@mock.patch("buildrunner.loggers.logging")
def test_initialize_root_logger(
    logging_mock,
    debug,
    no_color,
    disable_timestamps,
    log_level,
    console_format,
    file_format,
    tmp_path,
):
    logging_mock.DEBUG = logging.DEBUG
    logging_mock.INFO = logging.INFO
    root_logger = mock.create_autospec(logging.Logger)
    root_logger.handlers = mock.MagicMock()
    file_handler = mock.create_autospec(logging.FileHandler)
    stream_handler = mock.create_autospec(logging.StreamHandler)
    logging_mock.getLogger.return_value = root_logger
    logging_mock.FileHandler.return_value = file_handler
    logging_mock.StreamHandler.return_value = stream_handler
    results_dir = tmp_path

    loggers.initialize_root_logger(
        debug, no_color, disable_timestamps, str(results_dir)
    )
    logging_mock.getLogger.assert_called_once_with()
    root_logger.setLevel.assert_called_once_with(log_level)
    logging_mock.FileHandler.assert_called_once_with(
        str(results_dir / "build.log"), "w", encoding="utf8"
    )
    logging_mock.StreamHandler.assert_called_once_with(sys.stdout)
    file_handler.setFormatter.assert_called_once()
    stream_handler.setFormatter.assert_called_once()
    root_logger.handlers.clear.assert_called_once_with()
    assert root_logger.addHandler.call_args_list == [
        mock.call(stream_handler),
        mock.call(file_handler),
    ]

    # Check formatters
    file_formatter = file_handler.setFormatter.call_args.args[0]
    assert file_formatter.fmt == file_format
    assert file_formatter.no_color
    assert file_formatter.color == "white"
    stream_formatter = stream_handler.setFormatter.call_args.args[0]
    assert stream_formatter.fmt == console_format
    assert stream_formatter.no_color == no_color
    assert stream_formatter.color == "white"
    # Make sure the formatters are not the same, they should be distinct
    assert file_formatter != stream_formatter


@pytest.mark.parametrize(
    "output, lines",
    [
        ("", [""]),
        ("output1", ["output1"]),
        ("output1\n", ["output1"]),
        ("\noutput1\n\n", ["", "output1", ""]),
    ],
)
@mock.patch("buildrunner.loggers.logging")
def test_console_logger(logging_mock, output, lines):
    mock_logger = mock.create_autospec(logging.Logger)
    logging_mock.getLogger.return_value = mock_logger
    console_logger = loggers.ConsoleLogger("name1")
    console_logger.write(output)
    assert mock_logger.info.call_args_list == [mock.call(line) for line in lines]


@mock.patch("buildrunner.loggers.ContainerLogger.__init__")
def test_container_logger_for_methods(container_logger_mock):
    container_logger_mock.return_value = None
    loggers.ContainerLogger.for_build_container("build1")
    loggers.ContainerLogger.for_build_container("build1")
    loggers.ContainerLogger.for_build_container("build2")
    loggers.ContainerLogger.for_service_container("service1")
    loggers.ContainerLogger.for_service_container("service2")
    loggers.ContainerLogger.for_service_container("service3")
    loggers.ContainerLogger.for_service_container("service4")
    loggers.ContainerLogger.for_service_container("service5")

    assert container_logger_mock.call_args_list == [
        mock.call("build1_yellow", "yellow", prefix="build1"),
        mock.call("build1_blue", "blue", prefix="build1"),
        mock.call("build2_yellow", "yellow", prefix="build2"),
        mock.call("service-service1", "purple"),
        mock.call("service-service2", "cyan"),
        mock.call("service-service3", "red"),
        mock.call("service-service4", "green"),
        mock.call("service-service5", "purple"),
    ]


@mock.patch("buildrunner.loggers.logging")
def test_container_logger_set_logger_handlers(logging_mock, tmp_path):
    root_logger = mock.create_autospec(logging.Logger)
    root_logger.handlers = [
        logging.FileHandler(
            str(tmp_path / "log"),
            "w",
            encoding="utf8",
        ),
        logging.StreamHandler(sys.stdout),
    ]
    color_formatter = loggers.CustomColoredFormatter("%(message)s", False, "white")
    for handler in root_logger.handlers:
        handler.setFormatter(color_formatter)

    logging_mock.StreamHandler = logging.StreamHandler
    logging_mock.FileHandler = logging.FileHandler

    mock_logger1 = mock.create_autospec(logging.Logger)
    mock_logger1.handlers = []
    mock_logger1.propagate = True
    mock_logger2 = mock.create_autospec(logging.Logger)
    mock_logger2.handlers = []
    mock_logger2.propagate = True
    mock_loggers = {None: root_logger, "name1": mock_logger1, "name2": mock_logger2}
    logging_mock.getLogger.side_effect = lambda name=None: mock_loggers.get(name)

    loggers.ContainerLogger("name1", "blue")
    assert not mock_logger1.propagate
    assert mock_logger1.addHandler.call_count == 2
    assert mock_logger1.addHandler.call_args_list[0] == mock.call(
        root_logger.handlers[0]
    )
    handler = mock_logger1.addHandler.call_args_list[1].args[0]
    assert handler.__class__ == logging.StreamHandler
    assert isinstance(handler.formatter, loggers.CustomColoredFormatter)
    assert handler.formatter.fmt == "%(message)s"
    assert not handler.formatter.no_color
    assert handler.formatter.color == "blue"

    loggers.ContainerLogger("name2", "purple")
    assert not mock_logger2.propagate
    assert mock_logger2.addHandler.call_count == 2
    assert mock_logger2.addHandler.call_args_list[0] == mock.call(
        root_logger.handlers[0]
    )
    handler = mock_logger2.addHandler.call_args_list[1].args[0]
    assert isinstance(handler.formatter, loggers.CustomColoredFormatter)
    assert handler.formatter.color == "purple"


@pytest.mark.parametrize(
    "prefix, outputs, lines",
    [
        (None, [], []),
        (None, ["line1"], ["[name1] line1"]),
        ("p1", ["line", "1\nline", "2\n"], ["[p1] line1", "[p1] line2"]),
    ],
)
@mock.patch("buildrunner.loggers.logging")
def test_container_logger_write(logging_mock, prefix, outputs, lines):
    logger = loggers.ContainerLogger("name1", "white", prefix=prefix)
    for output in outputs:
        logger.write(output)
    logger.cleanup()
    assert logging_mock.getLogger.return_value.info.call_args_list == [
        mock.call(line) for line in lines
    ]


@mock.patch("buildrunner.loggers.progress")
def test_docker_pull_progress(progress_mock):
    with loggers.DockerPullProgress() as progress:
        progress_mock.Progress.assert_called_once_with()
        progress_instance = progress_mock.Progress.return_value
        progress_instance.__enter__.assert_called_once_with()
        progress_instance.__exit__.assert_not_called()
        task1 = mock.MagicMock()
        task2 = mock.MagicMock()
        progress_instance.add_task.side_effect = [
            task1,
            task2,
            Exception("this is a failure"),
        ]

        progress.status_report({})
        progress.status_report({"status": None})
        progress.status_report(
            {"status": "Downloading", "id": "1", "progressDetail": {"total": 100}}
        )
        progress.status_report(
            {"status": "Downloading", "progressDetail": {"total": 10}}
        )
        progress.status_report(
            {"status": "Downloading", "id": "0", "progressDetail": {"total": 10}}
        )
        progress.status_report(
            {"status": "Downloading", "id": "1", "progressDetail": {"current": 10}}
        )
        progress.status_report(
            {"status": "Downloading", "id": "2", "progressDetail": {"total": 10}}
        )
        progress.status_report({"status": "Downloading", "id": "failure"})
        progress.status_report(
            {"status": "Extracting", "id": "1", "progressDetail": {"current": 5}}
        )
        progress.status_report(
            {"status": "Extracting", "id": "2", "progressDetail": {"current": 10}}
        )
    progress_instance.__exit__.assert_called_once()

    assert progress_instance.add_task.call_args_list == [
        mock.call("[cyan]1: Downloading", total=100),
        mock.call("[cyan]2: Downloading", total=10),
    ]
    assert progress_instance.update.call_args_list == [
        mock.call(task1, description="[cyan]1: Downloading", completed=10),
        mock.call(task1, description="[green]1: Extracting", completed=5),
        mock.call(task2, description="[green]2: Extracting", completed=10),
    ]
