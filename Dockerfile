FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Europe/Berlin

ENV FREECAD_VERSION=freecad
ENV FREECAD_PATH=/usr/lib/$FREECAD_VERSION/lib

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt update && apt install -y software-properties-common
RUN add-apt-repository ppa:freecad-maintainers/freecad-stable
RUN apt update && apt -y install \
freecad \
xvfb

RUN ln -s /usr/lib/$FREECAD_VERSION/Mod /usr/lib/$FREECAD_VERSION-python3/Mod
RUN ln -s /usr/lib/$FREECAD_VERSION/Ext /usr/lib/$FREECAD_VERSION-python3/Ext

CMD ["xvfb-run", "freecad"]
