"""Cliente minimo de Ollama (solo biblioteca estandar)."""
import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("ESTACION_OLLAMA_URL", "http://127.0.0.1:11434")


class OllamaError(Exception):
    """Error de comunicacion con Ollama."""


def modelos_disponibles(timeout=2):
    """Conjunto de modelos instalados, o None si el servidor aun no responde."""
    try:
        with urllib.request.urlopen(BASE_URL + "/api/tags", timeout=timeout) as resp:
            datos = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return {m.get("name", "") for m in datos.get("models", [])}


def chat_stream(modelo, mensajes, timeout=300):
    """Generador: entrega los fragmentos de texto de la respuesta."""
    cuerpo = json.dumps(
        {"model": modelo, "messages": mensajes, "stream": True}
    ).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/api/chat",
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for linea in resp:
                linea = linea.strip()
                if not linea:
                    continue
                datos = json.loads(linea)
                if "error" in datos:
                    raise OllamaError(datos["error"])
                fragmento = datos.get("message", {}).get("content", "")
                if fragmento:
                    yield fragmento
                if datos.get("done"):
                    return
    except urllib.error.URLError as exc:
        raise OllamaError(f"No se pudo conectar con Ollama: {exc.reason}") from exc


def chat_json(modelo, mensajes, esquema, timeout=900):
    """Respuesta estructurada: el modelo debe ajustarse al esquema JSON dado.

    Devuelve el objeto ya interpretado (dict/list).
    """
    cuerpo = json.dumps({
        "model": modelo,
        "messages": mensajes,
        "stream": False,
        "format": esquema,
        "options": {"temperature": 0.2},
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/api/chat",
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            datos = json.load(resp)
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")[:300]
        raise OllamaError(f"Ollama respondio HTTP {exc.code}: {detalle}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise OllamaError(f"No se pudo conectar con Ollama: {getattr(exc, 'reason', exc)}") from exc
    except ValueError as exc:
        raise OllamaError(f"Respuesta de Ollama no es JSON valido: {exc}") from exc
    if "error" in datos:
        raise OllamaError(datos["error"])
    contenido = datos.get("message", {}).get("content", "")
    try:
        return json.loads(contenido)
    except ValueError as exc:
        raise OllamaError(f"El modelo no devolvio JSON valido: {contenido[:120]!r}") from exc
