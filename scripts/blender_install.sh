#!/bin/sh
BLENDER_VERSION=4.5.3
# install blender
#echo ${BLENDER_VERSION%.*}
wget -qO- "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" | tar -xJf - -C /opt
mv -f "/opt/blender-${BLENDER_VERSION}-linux-x64" /opt/blender_${BLENDER_VERSION%.*}
