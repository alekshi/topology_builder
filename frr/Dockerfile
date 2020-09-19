FROM debian:buster
MAINTAINER alekshi (based on https://github.com/FRRouting/frr/blob/master/docker/debian/Dockerfile by @robgil) 

ENV DEBIAN_FRONTEND noninteractive
ENV APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=DontWarn

RUN apt-get update && \
    apt-get install -y libpcre3-dev apt-transport-https ca-certificates curl wget logrotate \
    libc-ares2 libjson-c3 vim procps libreadline7 gnupg2 lsb-release apt-utils openssh-server && \
    rm -rf /var/lib/apt/lists/*

RUN curl -s https://deb.frrouting.org/frr/keys.asc | apt-key add -
RUN echo deb https://deb.frrouting.org/frr $(lsb_release -s -c) frr-stable | tee -a /etc/apt/sources.list.d/frr.list

RUN apt-get update && \
    apt-get install -y frr frr-pythontools && \
    rm -rf /var/lib/apt/lists/*

ADD docker-start /usr/sbin/docker-start
RUN chmod a+x /usr/sbin/docker-start
ENTRYPOINT ["/usr/sbin/docker-start"]
