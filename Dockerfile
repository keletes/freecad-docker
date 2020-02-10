FROM ubuntu:18.04

RUN apt-get update
RUN apt-get install -y curl software-properties-common
RUN curl -sL https://deb.nodesource.com/setup_10.x | bash
RUN add-apt-repository ppa:freecad-maintainers/freecad-stable
RUN apt-get update && apt-get install -y nodejs python3 freecad
RUN ln -s /usr/lib/freecad/Mod /usr/lib/freecad-python3/Mod
RUN ln -s /usr/lib/freecad/Ext /usr/lib/freecad-python3/Ext