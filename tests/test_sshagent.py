"""
Copyright 2026 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import io
import struct
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding
from paramiko import DSSKey, ECDSAKey, Ed25519Key, RSAKey
from paramiko.message import Message

from buildrunner.sshagent import (
    CustomAgentConnectionThread,
    CustomSSHAgent,
    load_ssh_key_from_file,
    load_ssh_key_from_str,
)


SIGN_DATA = b"Buildrunner SSH agent signature algorithm regression test"


@pytest.fixture(scope="module")
def rsa_key():
    return RSAKey.generate(2048)


@pytest.fixture(scope="module")
def dsa_key():
    return DSSKey.generate(1024)


@pytest.fixture(scope="module")
def ecdsa_key():
    return ECDSAKey.generate()


@pytest.fixture(scope="module")
def ed25519_key():
    private_key = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    )
    return Ed25519Key.from_private_key(io.StringIO(private_key.decode()))


def _sign_request(key_blob, flags):
    request = Message()
    request.add_string(key_blob)
    request.add_string(SIGN_DATA)
    request.add_int(flags)
    return request


def _agent_reply(keys, request):
    channel = Mock()
    connection = CustomAgentConnectionThread(CustomSSHAgent(keys), channel)
    connection._agent_sign_response(Message(request.asbytes()))

    channel.send.assert_called_once()
    wire_reply = channel.send.call_args[0][0]
    assert struct.unpack(">I", wire_reply[:4])[0] == len(wire_reply) - 4
    return Message(wire_reply[4:])


@pytest.mark.parametrize(
    "flags, algorithm, digest",
    [
        (0, "ssh-rsa", hashes.SHA1),
        (2, "rsa-sha2-256", hashes.SHA256),
        (4, "rsa-sha2-512", hashes.SHA512),
        (6, "rsa-sha2-256", hashes.SHA256),
    ],
)
def test_rsa_signature_matches_requested_algorithm(
    rsa_key, dsa_key, flags, algorithm, digest
):
    key_blob = rsa_key.asbytes()
    reply = _agent_reply([dsa_key, rsa_key], _sign_request(key_blob, flags))

    assert reply.get_byte() == b"\x0e"
    signature = Message(reply.get_string())
    assert signature.get_text() == algorithm
    # Verify the digest independently of the algorithm label in the response.
    public_key = RSAKey(data=key_blob)
    public_key.key.verify(
        signature.get_string(), SIGN_DATA, padding.PKCS1v15(), digest()
    )
    assert reply.get_remainder() == b""


@pytest.mark.parametrize("key_fixture", ["dsa_key", "ecdsa_key", "ed25519_key"])
def test_non_rsa_signing_is_unchanged(request, key_fixture):
    key = request.getfixturevalue(key_fixture)
    reply = _agent_reply([key], _sign_request(key.asbytes(), 0))

    assert reply.get_byte() == b"\x0e"
    signature = reply.get_string()
    assert Message(signature).get_text() == key.get_name()
    assert type(key)(data=key.asbytes()).verify_ssh_sig(SIGN_DATA, Message(signature))


@pytest.mark.parametrize("flags", [2, 4, 6])
@pytest.mark.parametrize("key_fixture", ["dsa_key", "ecdsa_key", "ed25519_key"])
def test_rsa_flags_are_rejected_for_non_rsa_keys(request, key_fixture, flags):
    key = request.getfixturevalue(key_fixture)
    reply = _agent_reply([key], _sign_request(key.asbytes(), flags))

    assert reply.asbytes() == b"\x05"


@pytest.mark.parametrize("flags", [1, 8, 10, 12, 0x80000000])
def test_unsupported_signing_flags_are_rejected(rsa_key, flags):
    reply = _agent_reply([rsa_key], _sign_request(rsa_key.asbytes(), flags))

    assert reply.asbytes() == b"\x05"


@pytest.mark.parametrize("flags", [0, 2, 4])
def test_unknown_key_is_rejected(rsa_key, flags):
    reply = _agent_reply([rsa_key], _sign_request(b"unknown key", flags))

    assert reply.asbytes() == b"\x05"


@pytest.mark.parametrize("flag_bytes", [b"", b"\x00", b"\x00\x00", b"\x00\x00\x00"])
def test_missing_or_truncated_signing_flags_are_rejected(rsa_key, flag_bytes):
    request = Message()
    request.add_string(rsa_key.asbytes())
    request.add_string(SIGN_DATA)
    request.add_bytes(flag_bytes)
    reply = _agent_reply([rsa_key], request)

    assert reply.asbytes() == b"\x05"


@pytest.mark.parametrize("key_fixture", ["rsa_key", "dsa_key"])
@pytest.mark.parametrize("password", [None, "test-passphrase"])
@pytest.mark.parametrize("source", ["file", "string"])
def test_private_key_loading(request, tmp_path, key_fixture, password, source):
    key = request.getfixturevalue(key_fixture)
    if source == "file":
        path = str(tmp_path / "private-key")
        key.write_private_key_file(path, password=password)
        loaded = load_ssh_key_from_file(path, password)
    else:
        key_file = io.StringIO()
        key.write_private_key(key_file, password=password)
        loaded = load_ssh_key_from_str(key_file.getvalue(), password)

    assert loaded.can_sign()
    assert loaded.asbytes() == key.asbytes()
