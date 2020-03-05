FROM python:2.7

COPY . /buildrunner-source

ENV PIP_DEFAULT_TIMEOUT 60

RUN                                         \
    set -ex;                                \
    useradd -m buildrunner;                 \
    apt update;                             \
    apt -y install                          \
        libffi-dev                          \
        libssl-dev                          \
        libyaml-dev                         \
        python-cryptography                 \
        python-pip                          \
        python-dev                          \
    ;                                       \
    cd /buildrunner-source;                 \
    pip install -r requirements.txt         \
                -r test_requirements.txt;   \
    python setup.py install;                \
    rm -rf /buildrunner-source;             \
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

# NOTE: this should likely have an ENTRYPOINT of the buildrunner executable with a default
# argument of "--help" in the CMD ... but the horse has already left the barn and it is
# likely difficult to fix all of the places that use the buildrunner Docker image.
#ENTRYPOINT ["/usr/local/bin/buildrunner"]
#CMD ["--help"]
CMD ["/usr/local/bin/buildrunner",  "--help"]
