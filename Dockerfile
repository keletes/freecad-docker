FROM ubuntu:noble

ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Europe/Berlin
ARG FREECAD_VERSION=0.20.2
ARG PY_VERSION=310
ARG DATE=2022-12-27-
ARG TARGETARCH

ENV FREECAD_PATH=/usr/lib

RUN apt update && apt install -y curl xvfb
RUN if [ "$TARGETARCH" = "amd64" ]; then curl -L https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/FreeCAD_${FREECAD_VERSION}-${DATE}conda-Linux-x86_64-${PY_VERSION}.AppImage > FreeCAD.AppImage; fi
RUN if [ "$TARGETARCH" = "arm64" ]; then curl -L https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/FreeCAD_${FREECAD_VERSION}-${DATE}conda-Linux-aarch64-${PY_VERSION}.AppImage > FreeCAD.AppImage; fi
RUN if [ "$TARGETARCH" = "aarch64" ]; then curl -L https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/FreeCAD_${FREECAD_VERSION}-${DATE}conda-Linux-aarch64-${PY_VERSION}.AppImage > FreeCAD.AppImage; fi
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN chmod a+x ./FreeCAD.AppImage
RUN ./FreeCAD.AppImage --appimage-extract
RUN rm -rf ./FreeCAD.AppImage
RUN cp -r ./squashfs-root/usr /
RUN rm -rf ./squashfs-root

CMD ["xvfb-run", "freecad"]
