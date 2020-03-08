FROM ubuntu:18.04

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:freecad-maintainers/freecad-stable
RUN apt-get update && apt-get install -y python3 freecad
RUN ln -s /usr/lib/freecad/Mod /usr/lib/freecad-python3/Mod
RUN ln -s /usr/lib/freecad/Ext /usr/lib/freecad-python3/Ext