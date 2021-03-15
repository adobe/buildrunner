ARG DOCKER_REGISTRY
FROM $DOCKER_REGISTRY/centos:7
RUN						\
    set -eux;					\
    yum clean all;				\
    yum groups mark convert;			\
    yum -y group install "Development Tools";	\
    yum -y install python3-setuptools;		\
    rm -rf /var/cache/yum
RUN pip3 install bottle pika
COPY . /root
EXPOSE 8080
CMD ["/root/testserver.py"]
