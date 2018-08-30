FROM python:2.7

COPY . /buildrunner-source

RUN                                                             \
    set -ex;                                                    \
    useradd -m buildrunner;                                     \
    apt-get update;                                             \
    apt-get -y install python-dev libffi-dev libssl-dev;        \
    pip install cryptography;                                   \
    cd /buildrunner-source;                                     \
    pip install -r requirements.txt;                            \
    python setup.py install;                                    \
    rm -rf /buildrunner-source;                                 \
    apt-get clean all

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
CMD ["/usr/local/bin/buildrunner",  "--help"]
