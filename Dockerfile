FROM python:3.7

COPY . /buildrunner-source

ENV PIP_DEFAULT_TIMEOUT 60

# Use an extra index to provide ARM packages, see
# https://www.piwheels.org/
RUN                                                         \
    set -ex;                                                \
    useradd -m buildrunner;                                 \
    apt update;                                             \
    apt -y install                                          \
        libffi-dev                                          \
        libssl-dev                                          \
        libyaml-dev                                         \
        python3-cryptography                                \
        python3-wheel                                       \
        python3-pip                                         \
        python3-dev                                         \
    ;                                                       \
    cd /buildrunner-source;                                 \
    pip3 install -U pip;                                    \
    pip3 install                                            \
        --extra-index-url=https://www.piwheels.org/simple   \
        -r requirements.txt                                 \
        -r test_requirements.txt;                           \
    python3 setup.py install;                               \
    rm -rf /buildrunner-source;                             \
    apt clean all;

#RUN \
#    set -ex; \
#    apt-get -y install vim

# The following will install docker-engine. It's not needed for the container to run,
# but was very helpful during development
#RUN \
#    set -ex; \
#    echo "deb http://http.debian.net/debian wheezy-backports main" > /etc/apt/sources.list.d/backports.list; \
#    apt-get -y install apt-transport-https ca-certificates; \
#    apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D; \
#    echo "deb https://apt.dockerproject.org/repo debian-jessie main" > /etc/apt/sources.list.d/docker.list; \
#    apt-get update; \
#    apt-get -y install docker-engine

ENV BUILDRUNNER_CONTAINER 1

ENTRYPOINT ["/usr/local/bin/buildrunner"]
CMD ["--help"]

# Local Variables:
# fill-column: 100
# End:
