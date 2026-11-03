import struct
from unittest import mock

import pytest
from paramiko import Message, RSAKey

from buildrunner.sshagent import (
    SSH2_AGENT_FAILURE,
    SSH2_AGENT_SIGN_RESPONSE,
    CustomAgentConnectionThread,
)


@pytest.fixture(scope="module")
def rsa_key():
    return RSAKey.generate(1024)


def _sign(key, flags, key_blob=None):
    agent = mock.Mock()
    agent.get_keys.return_value = [key]
    channel = mock.Mock()
    thread = CustomAgentConnectionThread(agent, channel)

    request = Message()
    request.add_string(key_blob if key_blob is not None else key.asbytes())
    request.add_string(b"data-to-sign")
    request.add_int(flags)
    request.rewind()
    thread._agent_sign_response(request)

    raw = channel.send.call_args[0][0]
    (length,) = struct.unpack(">I", raw[:4])
    reply = Message(raw[4 : 4 + length])
    return reply


@pytest.mark.parametrize(
    "flags, expected_alg",
    [
        (0, "ssh-rsa"),
        (2, "rsa-sha2-256"),
        (4, "rsa-sha2-512"),
        (8, "ssh-rsa"),
    ],
)
def test_sign_uses_requested_algorithm(rsa_key, flags, expected_alg):
    reply = _sign(rsa_key, flags)
    assert reply.get_byte() == SSH2_AGENT_SIGN_RESPONSE
    sig = Message(reply.get_binary())
    assert sig.get_text() == expected_alg
    sig.rewind()
    assert rsa_key.verify_ssh_sig(b"data-to-sign", sig)


def test_sign_unknown_key_fails(rsa_key):
    reply = _sign(rsa_key, 2, key_blob=b"not-a-key")
    assert reply.get_byte() == SSH2_AGENT_FAILURE
