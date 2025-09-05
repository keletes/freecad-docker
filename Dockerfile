FROM ubuntu:noble

ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Europe/Berlin
ARG FREECAD_VERSION=weekly-2025.09.03
ARG PY_VERSION=311
ARG TARGETARCH

ENV FREECAD_PATH=/usr/lib

RUN apt update && apt install -y curl xwayland-run
RUN if [ "$TARGETARCH" = "amd64" ]; then curl -L https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/FreeCAD_${FREECAD_VERSION}-conda-Linux-x86_64-py${PY_VERSION}.AppImage > FreeCAD.AppImage; fi
RUN if [ "$TARGETARCH" = "arm64" ]; then curl -L https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/FreeCAD_${FREECAD_VERSION}-conda-Linux-aarch64-py${PY_VERSION}.AppImage > FreeCAD.AppImage; fi
RUN if [ "$TARGETARCH" = "aarch64" ]; then curl -L https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/FreeCAD_${FREECAD_VERSION}-conda-Linux-aarch64-py${PY_VERSION}.AppImage > FreeCAD.AppImage; fi
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt remove -y curl

RUN chmod a+x ./FreeCAD.AppImage
RUN ./FreeCAD.AppImage --appimage-extract
RUN rm -rf ./FreeCAD.AppImage
RUN rm -rf ./squashfs-root/usr/share/X11/xkb
RUN cp -rf ./squashfs-root/usr /
RUN rm -rf ./squashfs-root

CMD ["xwfb-run", "freecad"]
