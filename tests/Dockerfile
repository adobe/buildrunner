ARG DOCKER_REGISTRY
FROM $DOCKER_REGISTRY/python:3.6-alpine
EXPOSE 80
RUN mkdir -p /var/http
WORKDIR /var/http
ADD files/version.txt /var/http/version.txt
CMD python -m SimpleHTTPServer 80
