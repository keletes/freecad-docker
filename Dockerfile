FROM ubuntu:20.04

ARG TZ=Europe/Berlin
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:freecad-maintainers/freecad-stable
RUN apt-get update && apt-get install -y python3 python3-pip xvfb freecad
RUN ln -s /usr/lib/freecad/Mod /usr/lib/freecad-python3/Mod
RUN ln -s /usr/lib/freecad/Ext /usr/lib/freecad-python3/Ext