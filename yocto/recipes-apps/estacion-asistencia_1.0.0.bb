SUMMARY = "Estacion de asistencia de escritorio en Edge AI"
DESCRIPTION = "Aplicacion Python con GUI Tkinter (se ve por VNC): JEV decide, Ollama genera y la app guarda archivos"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://main.py \
    file://gui.py \
    file://generador.py \
    file://diagrama.py \
    file://ollama_client.py \
    file://jev_client.py \
    file://estacion-asistencia.init \
    file://estacion-asistencia-run \
"

S = "${UNPACKDIR}"

# Arranque con sysvinit: S90, despues de ollama (S80) y del escritorio virtual (S85)
inherit update-rc.d
INITSCRIPT_NAME = "estacion-asistencia"
INITSCRIPT_PARAMS = "defaults 90 10"

do_install() {
    install -d ${D}/opt/estacion-asistencia
    install -m 0755 ${UNPACKDIR}/main.py ${D}/opt/estacion-asistencia/main.py
    for f in gui generador diagrama ollama_client jev_client; do
        install -m 0644 ${UNPACKDIR}/$f.py ${D}/opt/estacion-asistencia/$f.py
    done

    install -d ${D}${bindir}
    install -m 0755 ${UNPACKDIR}/estacion-asistencia-run ${D}${bindir}/estacion-asistencia-run

    install -d ${D}${sysconfdir}/init.d
    install -m 0755 ${UNPACKDIR}/estacion-asistencia.init ${D}${sysconfdir}/init.d/estacion-asistencia
}

FILES:${PN} += " \
    /opt/estacion-asistencia \
    ${bindir}/estacion-asistencia-run \
"

RDEPENDS:${PN} = " \
    python3 \
    python3-tkinter \
    python3-requests \
    python3-pydantic \
    python3-pillow \
    estacion-display \
    ollama \
    ollama-models \
"
