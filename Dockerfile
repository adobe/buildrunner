FROM python:3.11-bookworm

ENV BUILDRUNNER_CONTAINER 1

# Install the docker client for multiplatform builds
RUN apt update && \
    apt -y install ca-certificates curl && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    apt clean all
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list

# Some of these packages are to have native installs so that arm packages will not be built
RUN                                                         \
    useradd -m buildrunner &&                               \
    apt update &&                                           \
    apt -y install                                          \
        docker-ce-cli                                       \
        docker-buildx-plugin                                \
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

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# Install dependencies first to leverage Docker cache
COPY pyproject.toml uv.lock README.rst /app/
RUN uv sync --locked --no-install-project --no-dev

# Install the project separately for optimal layer caching
COPY buildrunner /app/buildrunner
RUN uv sync --locked --no-dev

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

ENTRYPOINT ["uv", "--project", "/app", "run", "--no-sync", "buildrunner"]
CMD []
