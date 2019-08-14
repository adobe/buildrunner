FROM centos:7
RUN						\
    set -eux;					\
    yum clean all;				\
    yum groups mark convert;			\
    yum -y group install "Development Tools";	\
    yum -y install python-setuptools;		\
    rm -rf /var/cache/yum
RUN easy_install pip
RUN pip install bottle pika
COPY . /root
EXPOSE 8080
CMD ["/root/testserver.py"]
