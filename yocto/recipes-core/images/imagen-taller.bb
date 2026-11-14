SUMMARY = "Imagen personalizada para estacion de asistencia en Edge AI"
DESCRIPTION = "Imagen Yocto con Raspberry Pi 5, Ollama, aplicacion Python y JEV"
LICENSE = "MIT"

inherit core-image

IMAGE_INSTALL:append = " \
    packagegroup-core-boot \
    openssh \
    bash \
    ca-certificates \
    curl \
    htop \
"

IMAGE_INSTALL:append = " \
    python3 \
    python3-pip \
    python3-requests \
    python3-pydantic \
    python3-tkinter \
    python3-pillow \
"

IMAGE_INSTALL:append = " \
    ollama \
    estacion-asistencia \
"

IMAGE_ROOTFS_EXTRA_SPACE = "2097152"

export IMAGE_BASENAME = "imagen-taller"

IMAGE_FEATURES += "ssh-server-openssh"
IMAGE_FEATURES += "allow-empty-password empty-root-password allow-root-login"

