ARG DOCKER_REGISTRY
FROM $DOCKER_REGISTRY/centos:8
RUN						\
    set -eux;					\
    yum clean all;				\
    yum -y group install "Development Tools";	\
    yum -y install python3-setuptools python3-pip;		\
    rm -rf /var/cache/yum
RUN pip3 install bottle pika
COPY . /root
EXPOSE 8080
CMD ["/root/testserver.py"]
