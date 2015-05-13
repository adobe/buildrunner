"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
import fcntl
import os
from paramiko import (
    DSSKey,
    MissingHostKeyPolicy,
    PasswordRequiredException,
    RSAKey,
    SSHClient,
    SSHException,
)
from paramiko.agent import AgentSSH, AgentRequestHandler
from paramiko.common import asbytes, io_sleep
from paramiko.message import Message
from select import select
import struct
import threading
import time
import urlparse

from buildrunner import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.docker.builder import DockerBuilder


SSH_AGENT_PROXY_BUILD_CONTEXT = os.path.join(
    os.path.dirname(__file__),
    'SSHAgentProxyImage'
)


def get_ssh_keys(keys):
    """
    Load the given keys into paramiko PKey objects.
    """
    ssh_keys = []
    for _key, _passwd in keys.iteritems():
        # load the paramiko key file
        try:
            rsa_key = RSAKey.from_private_key_file(_key, _passwd)
            ssh_keys.append(rsa_key)
        except PasswordRequiredException:
            raise BuildRunnerConfigurationError(
                "Key at %s requires a password" % _key
            )
        except SSHException:
            try:
                dss_key = DSSKey.from_private_key_file(_key, _passwd)
                ssh_keys.append(dss_key)
            except PasswordRequiredException:
                raise BuildRunnerConfigurationError(
                    "Key at %s requires a password" % _key
                )
            except SSHException:
                raise BuildRunnerConfigurationError(
                    "Unable to load key at %s" % _key
                )

    return ssh_keys


class DockerSSHAgentProxy(object):
    """
    Class used to manage a Docker container that exposes a ssh-agent socket
    through a volume that can be mounted within other containers running within
    the same Docker host. Keys are loaded and shared through a custom ssh-agent
    implementation that is managed by this class.
    """


    def __init__(self, docker_client, log):
        """
        """
        self.docker_client = docker_client
        self.log = log
        self._ssh_agent_image = None
        self._ssh_agent_container = None
        self._ssh_client = None
        self._ssh_channel = None


    def get_info(self):
        """
        Return a tuple where the first item is the ssh-agent container id and
        the second is a dict of environment variables to be injected into other
        containers providing settings for ssh clients to connect to the shared
        agent.
        """
        return (
            self._ssh_agent_container,
            {
                'SSH_AUTH_SOCK': '/ssh-agent/agent'
            }
        )


    def start(self, keys):
        """
        Loads the given keys, starts a Docker container, creates a persistant
        ssh connection to the container, and starts the custom ssh agent
        thread.

        Args:
          - keys a dict with the key being the file path and the value being a
            password (or null if not required)
        """
        # load the keys
        _pkkeys = get_ssh_keys(keys)
        if not _pkkeys:
            raise BuildRunnerConfigurationError("Unable to load private keys")

        # create and start the Docker container
        self._ssh_agent_container = self.docker_client.create_container(
            self.get_ssh_agent_image(),
            command=[
                '%s %s' % (_pkkeys[0].get_name(), _pkkeys[0].get_base64()),
            ],
        )['Id']
        self.docker_client.start(
            self._ssh_agent_container,
            publish_all_ports=True,
        )
        self.log.write(
            "Created ssh-agent container %.10s\n" % self._ssh_agent_container
        )

        # get the Docker server ip address and ssh port exposed by this
        # container
        _ssh_host = 'localhost'
        p_data = urlparse.urlparse(self.docker_client.base_url)
        if p_data and 'unix' not in p_data.scheme and p_data.hostname:
            if p_data.hostname != 'localunixsocket':
                _ssh_host = p_data.hostname
        _ssh_port_info = self.docker_client.port(self._ssh_agent_container, 22)
        if not _ssh_port_info or 'HostPort' not in _ssh_port_info[0]:
            raise BuildRunnerProcessingError(
                "Unable to find port for ssh-agent container"
            )
        _ssh_port = _ssh_port_info[0]['HostPort']
        _ssh_port = int(_ssh_port)
        time.sleep(3)

        # setup ssh connection with fake agent in own thread
        self._ssh_client = SSHClient()
        self._ssh_client.set_missing_host_key_policy(MissingHostKeyPolicy())
        #pylint: disable=W0212
        self._ssh_client._agent = CustomSSHAgent(_pkkeys)
        self._ssh_client.connect(
            _ssh_host,
            port=_ssh_port,
            username='root',
            allow_agent=True,
            look_for_keys=False,
        )
        self._ssh_channel = self._ssh_client.get_transport().open_session()
        #AgentRequestHandler(channel)
        self._ssh_channel.request_forward_agent(
            self._ssh_client._agent.forward_agent_handler
        )
        self._ssh_channel.get_pty()
        self._ssh_channel.exec_command('/login.sh')
        self.log.write("Established ssh-agent container connection\n")


    def stop(self):
        """
        Stops the custom agent thread, kills the persistant ssh connection to
        the remote container, and kills the container.
        """
        # kill ssh connection thread
        self.log.write("Closing ssh-agent container connection\n")
        if self._ssh_client:
            #pylint: disable=W0212
            if self._ssh_client._agent:
                try:
                    self._ssh_client._agent.close()
                #pylint: disable=W0703
                except Exception as _ex:
                    self.log.write(
                        "Error stopping ssh-agent: %s\n" % _ex
                    )
            try:
                self._ssh_client.close()
            #pylint: disable=W0703
            except Exception as _ex:
                self.log.write(
                    "Error stopping ssh-agent connection: %s\n" % _ex
                )

        # kill container
        self.log.write(
            "Destroying ssh-agent container %.10s\n" % self._ssh_agent_container
        )
        if self._ssh_agent_container:
            self.docker_client.remove_container(
                self._ssh_agent_container,
                force=True,
            )


    def get_ssh_agent_image(self):
        """
        Get and/or create the image used to proxy the ssh agent to a container.
        """
        if not self._ssh_agent_image:
            self.log.write('Creating ssh-agent image\n')
            ssh_agent_builder = DockerBuilder(
                path=SSH_AGENT_PROXY_BUILD_CONTEXT,
            )
            exit_code = ssh_agent_builder.build(
                nocache=False,
            )
            if exit_code != 0 or not ssh_agent_builder.image:
                raise BuildRunnerProcessingError(
                    'Error building ssh agent image'
                )
            self._ssh_agent_image = ssh_agent_builder.image
        return self._ssh_agent_image


class CustomSSHAgent(AgentSSH):
    """
    Custom class implementing the paramiko ssh agent apis.
    """


    def __init__(self, keys):
        AgentSSH.__init__(self)
        self._conn = None
        self._keys = keys
        self._connection_threads = []


    def _connect(self, conn):
        """
        Override parent.
        """
        pass


    def __del__(self):
        self.close()


    def close(self):
        """
        Override parent.
        """
        if self._connection_threads:
            for _ct in self._connection_threads:
                _ct.stop()
        self._keys = []


    def get_keys(self):
        """
        Return the keys.
        """
        return tuple(self._keys)


    def forward_agent_handler(self, remote_channel):
        """
        Handler function for setting up the thread that handles remote ssh
        agent requests from the server we connect to.
        """
        _ct = CustomAgentConnectionThread(
            self,
            remote_channel,
        )
        self._connection_threads.append(_ct)
        _ct.start()


SSH2_AGENT_FAILURE = chr(30)
SSH2_AGENTC_REQUEST_IDENTITIES = 11
SSH2_AGENT_IDENTITIES_ANSWER = chr(12)
SSH2_AGENTC_SIGN_REQUEST = 13
SSH2_AGENT_SIGN_RESPONSE = chr(14)
class CustomAgentConnectionThread(threading.Thread):
    """
    Class that manages a remote (upstream server) connection to a
    CustomSSHAgent.
    """
    def __init__(self, agent, remote_channel):
        threading.Thread.__init__(self, target=self.run)
        self._agent = agent
        self._remote_channel = remote_channel
        self._exit = False

    def run(self):
        """
        Main server routine.
        """
        try:
            while not self._exit:
                try:
                    if self._remote_channel.eof_received:
                        self.stop()
                        continue

                    if self._remote_channel.recv_ready():
                        r_type, request = self._receive_request()

                        if r_type == SSH2_AGENTC_REQUEST_IDENTITIES:
                            self._agent_identities_answer()
                        elif r_type == SSH2_AGENTC_SIGN_REQUEST:
                            self._agent_sign_response(request)
                        else:
                            # return FAILURE message for everything else
                            self._send_reply(SSH2_AGENT_FAILURE)
                except SSHException:
                    raise
                except Exception:
                    pass
                time.sleep(io_sleep)
        #pylint: disable=W0703
        except Exception:
            self.stop()


    def _agent_identities_answer(self):
        """
        Return the keys in the custom agent.
        """
        msg = Message()
        msg.add_byte(SSH2_AGENT_IDENTITIES_ANSWER)
        _keys = self._agent.get_keys()
        msg.add_int(len(_keys))
        for _key in _keys:
            # add each key
            msg.add_string(_key.asbytes())
            msg.add_string('')
        self._send_reply(msg)


    def _agent_sign_response(self, request):
        """
        Lookup the key in the custom agent and use it to sign the passed data.
        """
        key_blob = request.get_string()
        data = request.get_string()

        signed = None
        for _key in self._agent.get_keys():
            if key_blob == _key.asbytes():
                _signed = _key.sign_ssh_data(data)
                signed = _signed.asbytes()
        msg = Message()
        if signed:
            msg.add_byte(SSH2_AGENT_SIGN_RESPONSE)
            msg.add_string(signed)
        else:
            msg.add_byte(SSH2_AGENT_FAILURE)
        self._send_reply(msg)


    def _send_reply(self, msg):
        """
        Send a reply back to the upstream agent.
        """
        raw_msg = asbytes(msg)
        length = struct.pack('>I', len(raw_msg))
        self._remote_channel.send(length + raw_msg)


    def _receive_request(self):
        """
        Receive the request, storing the bytes in a Message object for easy
        retrieval of message parts.
        """
        message_length = self._read_all(4)
        msg = Message(self._read_all(struct.unpack('>I', message_length)[0]))
        return ord(msg.get_byte()), msg


    def _read_all(self, wanted):
        """
        Read the specified bytes from the remote channel.
        """
        result = self._remote_channel.recv(wanted)
        while len(result) < wanted:
            if len(result) == 0:
                raise SSHException('lost upstream ssh-agent connection')
            extra = self._remote_channel.recv(wanted - len(result))
            if len(extra) == 0:
                raise SSHException('lost upstream ssh-agent connection')
            result += extra
        return result


    def stop(self):
        """
        Close the remote connection and stop the thread.
        """
        self._exit = True
        if self._remote_channel:
            self._remote_channel.close()
            self._remote_channel = None
