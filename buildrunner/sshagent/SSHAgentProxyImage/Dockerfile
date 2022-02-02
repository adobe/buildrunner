ARG DOCKER_REGISTRY
FROM $DOCKER_REGISTRY/rockylinux:8.5

RUN yum clean all; yum -y install openssh-server socat
RUN mkdir /var/run/sshd; mkdir /ssh-agent
RUN mkdir /root/.ssh; chmod 700 /root/.ssh
RUN sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
RUN sed -i 's/GSSAPIAuthentication yes/GSSAPIAuthentication no/' /etc/ssh/sshd_config
RUN sed -i 's/X11Forwarding yes/X11Forwarding no/' /etc/ssh/sshd_config
RUN sed -i 's/UsePrivilegeSeparation sandbox/UsePrivilegeSeparation no/' /etc/ssh/sshd_config
RUN printf "\nAllowTcpForwarding no\n" >> /etc/ssh/sshd_config
RUN printf "\nForceCommand /login.sh\n" >> /etc/ssh/sshd_config

EXPOSE 22
ENTRYPOINT ["/run.sh"]
VOLUME ["/ssh-agent"]

ADD run.sh /run.sh
ADD login.sh /login.sh

