FROM python:3.11

COPY . /buildrunner-source

ENV PIP_DEFAULT_TIMEOUT 60

# Some of these packages are to have native installs so that arm packages will not be built
RUN                                                         \
    set -x &&                                              \
    useradd -m buildrunner &&                               \
    apt update &&                                           \
    apt -y install                                          \
        libffi-dev                                          \
        libssl-dev                                          \
        libyaml-dev                                         \
        python3-pip                                         \
        python3-wheel                                       \
        python3-cryptography                                \
        python3-paramiko                                    \
        python3-wrapt                                       \
        python3-dev &&                                      \
    apt clean all

# Running pip this way is strange, but it allows it to detect the system packages installed
# HACK - For some reason, 'python3 setup.py install' produces an error with 'jaraco-classes' package
# but replacing it with 'jaraco.classes' in the requirements.txt works. ¯\_(ツ)_/¯
RUN                                                              \
    cd /buildrunner-source &&                                    \
    python3 -m pip install -U pip &&                             \
    sed -i s/jaraco-classes/jaraco.classes/ requirements.txt &&  \
    python3 -m pip install                                       \
        -r requirements.txt                                      \
        -r test_requirements.txt &&                              \
    python3 setup.py install &&                                  \
    rm -rf /buildrunner-source

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
CMD []

# Local Variables:
# fill-column: 100
# End:
