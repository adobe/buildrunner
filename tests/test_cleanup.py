"""
Tests for the buildrunner.cleanup module — signal-handler-based container cleanup.
"""

from unittest import mock

import pytest

from buildrunner.cleanup import (
    _force_cleanup_all,
    _registered_containers,
    install_signal_handlers,
    register_container,
    set_docker_client,
    unregister_container,
)


@pytest.fixture(autouse=True)
def _reset_cleanup_state():
    """Reset cleanup module state before each test."""
    import buildrunner.cleanup as mod

    mod._registered_containers.clear()
    mod._docker_client = None
    mod._cleanup_done = False
    yield
    mod._registered_containers.clear()
    mod._docker_client = None
    mod._cleanup_done = False


class TestRegisterUnregister:
    def test_register_adds_container(self):
        register_container("abc123")
        assert "abc123" in _registered_containers

    def test_register_ignores_duplicates(self):
        register_container("abc123")
        register_container("abc123")
        assert _registered_containers.count("abc123") == 1

    def test_register_ignores_empty(self):
        register_container("")
        register_container(None)
        assert len(_registered_containers) == 0

    def test_unregister_removes_container(self):
        register_container("abc123")
        unregister_container("abc123")
        assert "abc123" not in _registered_containers

    def test_unregister_nonexistent_is_noop(self):
        unregister_container("nonexistent")
        # Should not raise

    def test_register_multiple(self):
        register_container("aaa")
        register_container("bbb")
        register_container("ccc")
        assert len(_registered_containers) == 3


class TestForceCleanupAll:
    def test_removes_all_registered_containers(self):
        client = mock.MagicMock()
        set_docker_client(client)
        register_container("aaa")
        register_container("bbb")

        _force_cleanup_all()

        assert client.remove_container.call_count == 2
        client.remove_container.assert_any_call("aaa", force=True, v=True)
        client.remove_container.assert_any_call("bbb", force=True, v=True)

    def test_only_runs_once(self):
        client = mock.MagicMock()
        set_docker_client(client)
        register_container("aaa")

        _force_cleanup_all()
        _force_cleanup_all()  # second call should be no-op

        assert client.remove_container.call_count == 1

    def test_no_containers_is_noop(self):
        client = mock.MagicMock()
        set_docker_client(client)

        _force_cleanup_all()

        client.remove_container.assert_not_called()

    def test_handles_remove_exception_gracefully(self):
        client = mock.MagicMock()
        client.remove_container.side_effect = Exception("container not found")
        set_docker_client(client)
        register_container("aaa")
        register_container("bbb")

        # Should not raise
        _force_cleanup_all()

        # Should attempt both even if first fails
        assert client.remove_container.call_count == 2

    def test_creates_client_if_none_set(self):
        register_container("aaa")

        with mock.patch("buildrunner.cleanup.sys") as mock_sys:
            mock_sys.stderr = mock.MagicMock()
            with mock.patch.dict("sys.modules", {"docker": mock.MagicMock()}) as _:
                import buildrunner.cleanup as mod

                mod._docker_client = None
                mod._cleanup_done = False
                # This should try to create a client via docker.from_env()
                _force_cleanup_all()


class TestInstallSignalHandlers:
    def test_installs_sigterm_handler(self):
        with mock.patch("buildrunner.cleanup.signal") as mock_signal:
            with mock.patch("buildrunner.cleanup.atexit") as mock_atexit:
                install_signal_handlers()

                mock_signal.signal.assert_any_call(mock_signal.SIGTERM, mock.ANY)
                mock_signal.signal.assert_any_call(mock_signal.SIGINT, mock.ANY)
                mock_atexit.register.assert_called_once()
