"""Cliente de JEV (decisiones estructuradas) sobre POST /v1/systemone de Ollama.

JEV no es un servicio aparte: Ollama (>= 0.35) sirve modelos de decision
(tev1, nimble) en /v1/systemone. Este modulo arma la solicitud, la envia y
normaliza la respuesta. Solo usa la biblioteca estandar.

Prueba rapida en la Pi:
    python3 /opt/estacion-asistencia/jev_client.py "Necesito un manual en Markdown"
"""
import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("ESTACION_OLLAMA_URL", "http://127.0.0.1:11434")
MODELO_JEV = os.environ.get("ESTACION_JEV_MODELO", "tev1:0.8b")

ACCIONES = ("responder", "generar_txt", "generar_md", "generar_latex", "generar_diagrama")

# Preguntas tipadas (Ollama admite 1-64 por solicitud; cada una necesita 'instructions')
PREGUNTAS = {
    "accion": {
        "type": "choice",
        "instructions": "Que debe hacer el asistente con la solicitud del usuario?",
        "criteria": {
            "responder": "Contestar una pregunta o conversar con una respuesta breve en pantalla.",
            "generar_txt": "Producir un texto plano (carta, nota, resumen) sin formato especial.",
            "generar_md": "Producir un documento Markdown estructurado (manual, guia, informe).",
            "generar_latex": "Producir un documento tecnico o academico en LaTeX, o formulas matematicas.",
            "generar_diagrama": "Dibujar un diagrama de flujo, arbol, red, circuito o plano.",
        },
    },
    "urgente": {
        "type": "noul",
        "instructions": "La solicitud expresa urgencia, una falla critica o necesidad inmediata?",
    },
    "prioridad": {
        "type": "score",
        "instructions": "Que prioridad operativa tiene esta solicitud?",
        "criteria": ["Baja", "Media", "Alta"],
    },
}


class JevError(Exception):
    """Error al consultar JEV."""


def decidir(estado, preguntas, modelo=None, timeout=120):
    """Envia 'estado' (texto o dict) y las preguntas; devuelve el dict 'answers' crudo."""
    cuerpo = json.dumps(
        {"model": modelo or MODELO_JEV, "state": estado, "questions": preguntas}
    ).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/v1/systemone",
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            datos = json.load(resp)
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")[:300]
        raise JevError(f"JEV respondio HTTP {exc.code}: {detalle}") from exc
    except (urllib.error.URLError, OSError) as exc:
        motivo = getattr(exc, "reason", exc)
        raise JevError(f"No se pudo consultar a Ollama: {motivo}") from exc
    except ValueError as exc:
        raise JevError(f"Respuesta de JEV no es JSON valido: {exc}") from exc
    if "answers" not in datos:
        raise JevError(f"Respuesta inesperada de JEV: {str(datos)[:200]}")
    return datos["answers"]


def clasificar(texto, timeout=120):
    """Decision normalizada para la solicitud del usuario."""
    r = decidir(texto, PREGUNTAS, timeout=timeout)
    try:
        acc, urg, pri = r["accion"], r["urgente"], r["prioridad"]
        nivel = pri.get("legend", {}).get(str(round(pri["score"])))
        return {
            "accion": acc["choice"],
            "probabilidades": acc["probabilities"],
            "confianza": acc.get("confidence"),
            "urgente": urg["noul"],            # probabilidad 0..1
            "prioridad": pri["score"],         # 0..2 (puede ser fraccionario)
            "prioridad_nivel": nivel,
        }
    except (KeyError, TypeError) as exc:
        raise JevError(f"Respuesta de JEV con formato inesperado: {exc!r}") from exc


if __name__ == "__main__":
    import sys

    solicitud = " ".join(sys.argv[1:]) or "Necesito un manual tecnico en Markdown sobre el arranque del sistema"
    print(json.dumps(clasificar(solicitud), ensure_ascii=False, indent=2))
