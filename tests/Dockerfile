ARG DOCKER_REGISTRY
FROM $DOCKER_REGISTRY/python:2.7.12-alpine
EXPOSE 80
RUN mkdir -p /var/http
WORKDIR /var/http
ADD files/version.txt /var/http/version.txt
CMD python -m SimpleHTTPServer 80
