"""Decide con JEV que hacer con la solicitud y genera el contenido y los archivos.

procesar() es un generador de eventos (tipo, contenido):
    ("nota",    texto)  informacion para el usuario; no entra al historial del modelo
    ("texto",   texto)  fragmento de la respuesta; entra al historial
    ("archivo", ruta)   archivo guardado en disco
"""
import json
import os
import re
import time
import unicodedata

import diagrama
import jev_client
import ollama_client

MODELO_TEXTO = "llama3.2:3b"
DIR_SALIDAS = os.environ.get("ESTACION_SALIDAS", "/home/root/salidas")
IP_PI = os.environ.get("ESTACION_IP", "192.168.50.2")

SISTEMA = {
    "responder": (
        "Eres un asistente tecnico. Responde en espanol, de forma clara y breve."
    ),
    "generar_txt": (
        "Redacta en espanol el contenido solicitado como texto plano, sin Markdown "
        "ni simbolos de formato. Responde solo con el contenido."
    ),
    "generar_md": (
        "Redacta en espanol el contenido solicitado como un documento Markdown bien "
        "estructurado (titulo, secciones, listas). Responde solo con el documento."
    ),
    "generar_latex": (
        "Escribe en espanol un documento LaTeX completo y compilable que cubra lo "
        "solicitado (de \\documentclass a \\end{document}). Responde solo con el "
        "codigo LaTeX, sin explicaciones."
    ),
}
EXTENSION = {"generar_txt": "txt", "generar_md": "md", "generar_latex": "tex"}

SISTEMA_DIAGRAMA = (
    "Eres un generador de diagramas de flujo. Responde SOLO con un objeto JSON "
    "valido con las claves titulo, nodos y aristas. Cada nodo tiene id corto (n1, "
    "n2, ...), texto breve en espanol (maximo 7 palabras) y tipo (inicio, proceso, "
    "decision o fin). Cada arista tiene de, a (ids de nodos) y una etiqueta "
    "opcional (por ejemplo Si o No en las decisiones). Debe haber un nodo de tipo "
    "inicio y al menos uno de tipo fin, y todos los nodos deben estar conectados. "
    "Usa como maximo 15 nodos."
)
ESQUEMA_DIAGRAMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "nodos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "texto": {"type": "string"},
                    "tipo": {"type": "string",
                             "enum": ["inicio", "proceso", "decision", "fin"]},
                },
                "required": ["id", "texto", "tipo"],
            },
        },
        "aristas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "de": {"type": "string"},
                    "a": {"type": "string"},
                    "etiqueta": {"type": "string"},
                },
                "required": ["de", "a"],
            },
        },
    },
    "required": ["titulo", "nodos", "aristas"],
}


def _slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40].strip("-")
    return t or "salida"


def _ruta(solicitud, extension):
    os.makedirs(DIR_SALIDAS, exist_ok=True)
    base = time.strftime("%Y%m%d-%H%M%S") + "-" + _slug(solicitud)
    ruta, n = os.path.join(DIR_SALIDAS, f"{base}.{extension}"), 1
    while os.path.exists(ruta):
        n += 1
        ruta = os.path.join(DIR_SALIDAS, f"{base}-{n}.{extension}")
    return ruta


def _limpiar(accion, texto):
    """Quita cercas ``` y, en LaTeX, todo lo que quede fuera del documento."""
    t = texto.strip()
    m = re.match(r"^```[\w-]*\n(.*)\n```\s*$", t, re.S)
    if m:
        t = m.group(1).strip()
    if accion == "generar_latex":
        i, fin = t.find("\\documentclass"), "\\end{document}"
        j = t.rfind(fin)
        if i != -1 and j != -1:
            t = t[i:j + len(fin)]
    return t + "\n"


def _resumen(decision):
    accion = decision["accion"]
    prob = decision["probabilidades"].get(accion, 0)
    nivel = decision.get("prioridad_nivel") or f"{decision['prioridad']:.1f}"
    return (f"[JEV] accion: {accion} ({prob:.0%}) | urgente: "
            f"{decision['urgente']:.0%} | prioridad: {nivel}")


def procesar(texto, historial):
    try:
        decision = jev_client.clasificar(texto)
        accion = decision["accion"]
        yield ("nota", _resumen(decision))
    except jev_client.JevError as exc:
        accion = "responder"
        yield ("nota", f"[JEV no disponible: {exc}] Se respondera en texto.")
    if accion not in jev_client.ACCIONES:
        accion = "responder"

    if accion == "generar_diagrama":
        yield ("nota", "Generando el diagrama (puede tardar un par de minutos)...")
        mensajes = [{"role": "system", "content": SISTEMA_DIAGRAMA}] + historial
        spec = ollama_client.chat_json(MODELO_TEXTO, mensajes, ESQUEMA_DIAGRAMA)
        ruta_png = _ruta(texto, "png")
        diagrama.renderizar(spec, ruta_png)
        with open(ruta_png[:-4] + ".json", "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
        titulo, nodos, aristas = diagrama.normalizar(spec)
        yield ("texto", f"Diagrama \"{titulo}\": {len(nodos)} nodos y {len(aristas)} conexiones.")
        yield ("archivo", ruta_png)
        yield ("nota", f"Descarga desde el PC: scp root@{IP_PI}:{ruta_png} .")
        return

    mensajes = [{"role": "system", "content": SISTEMA[accion]}] + historial
    partes = []
    for fragmento in ollama_client.chat_stream(MODELO_TEXTO, mensajes):
        partes.append(fragmento)
        yield ("texto", fragmento)
    if accion in EXTENSION:
        ruta = _ruta(texto, EXTENSION[accion])
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(_limpiar(accion, "".join(partes)))
        yield ("archivo", ruta)
        yield ("nota", f"Descarga desde el PC: scp root@{IP_PI}:{ruta} .")
