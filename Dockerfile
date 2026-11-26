FROM ubuntu:noble

ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Europe/Berlin
ARG FREECAD_VERSION=1.1.4
ARG PY_VERSION=311
ARG TARGETARCH

ENV FREECAD_PATH=/usr/lib

# Single layer: download, extract, install and clean up, so the AppImage and
# squashfs-root are never stored in any image layer.
RUN set -e; \
    apt update && apt install -y curl xvfb; \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone; \
    case "$TARGETARCH" in \
      amd64) FC_ARCH=x86_64 ;; \
      arm64|aarch64) FC_ARCH=aarch64 ;; \
      *) echo "unsupported arch: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    curl -L https://github.com/FreeCAD/FreeCAD/releases/download/${FREECAD_VERSION}/FreeCAD_${FREECAD_VERSION}-Linux-${FC_ARCH}-py${PY_VERSION}.AppImage > FreeCAD.AppImage; \
    chmod a+x ./FreeCAD.AppImage; \
    ./FreeCAD.AppImage --appimage-extract; \
    rm -rf ./FreeCAD.AppImage ./squashfs-root/usr/share/X11/xkb; \
    cp -rf ./squashfs-root/usr /; \
    rm -rf ./squashfs-root; \
    apt remove -y curl; \
    rm -rf /var/lib/apt/lists/*

# Static FCStd checker (stdlib only): `import fcstd_check` from FreeCAD's Python, or
# `fcstd-check <file>...` (JSON on stdout, exit 1 on findings). See README.
COPY fcstd_check/fcstd_check.py /usr/local/lib/fcstd_check/fcstd_check.py
COPY fcstd_check/fcstd-check /usr/local/bin/fcstd-check
ENV PYTHONPATH=/usr/local/lib/fcstd_check${PYTHONPATH:+:$PYTHONPATH}
# Fail the build if the wrapper cannot find a Python that runs the module.
RUN fcstd-check /dev/null | grep -q "not a readable zip"

CMD ["xvfb-run", "freecad"]
