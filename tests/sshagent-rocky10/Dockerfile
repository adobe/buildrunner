ARG ROCKY_IMAGE=rockylinux/rockylinux:10
FROM ${ROCKY_IMAGE}

RUN dnf -y install git-core openssh-clients openssh-server && dnf clean all
# Only a disposable test server uses this image. Password login is disabled.
RUN usermod -p x root && mkdir -p /run/sshd

VOLUME /probe-results
CMD ["/bin/bash"]
