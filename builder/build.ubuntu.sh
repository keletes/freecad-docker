cmake -DINSTALL_TO_SITEPACKAGES:BOOL=0 /source
make -j$(nproc --ignore=2)
checkinstall --default --install=no --fstrans=yes -y --pkgname=$PACKAGE --pkgversion=$VERSION --maintainer=$MAINTAINER --backup=no
