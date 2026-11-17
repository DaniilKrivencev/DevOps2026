# «Чистая машина» для проверки подготовки с нуля (ЛР7): Ubuntu 24.04 с systemd
# и SSH — как свежеустановленный сервер. Ничего, кроме входа по SSH, не настроено.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive container=docker
RUN apt-get update \
 && apt-get install -y --no-install-recommends systemd systemd-sysv dbus openssh-server sudo python3 python3-apt iproute2 \
 && rm -rf /var/lib/apt/lists/* \
 && systemctl enable ssh
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
