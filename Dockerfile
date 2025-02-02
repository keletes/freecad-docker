FROM ubuntu:rolling

ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Europe/Berlin
ARG FREECAD_VERSION=freecad

ENV FREECAD_PATH=/usr/lib/$FREECAD_VERSION/lib

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY ./install /usr/lib/${FREECAD_VERSION}

#RUN apt update && apt install -y software-properties-common
#RUN add-apt-repository ppa:freecad-maintainers/freecad-daily
RUN apt update
RUN apt install -y xvfb
#RUN apt  install -y freecad-daily

RUN mkdir /usr/lib/$FREECAD_VERSION-python3

RUN ln -s /usr/lib/$FREECAD_VERSION/Mod /usr/lib/$FREECAD_VERSION-python3/Mod
RUN ln -s /usr/lib/$FREECAD_VERSION/Ext /usr/lib/$FREECAD_VERSION-python3/Ext

CMD ["xvfb-run", "freecad"]
