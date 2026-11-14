#!/usr/bin/env python3
"""Punto de entrada de la estacion de asistencia Edge AI (ventana Tkinter)."""
import generador
import ollama_client
from gui import App

MODELO_TEXTO = generador.MODELO_TEXTO   # texto, Markdown, LaTeX, especificaciones de diagramas
MODELO_INTENCION = "qwen3:0.6b"         # clasificacion de intencion -> JSON (fase 2)
MODELO_JEV = "tev1:0.8b"                # decisiones estructuradas (/v1/systemone)


class Backend:
    modelos_requeridos = {MODELO_TEXTO, MODELO_INTENCION, MODELO_JEV}

    def verificar(self):
        """(listo, mensaje). Se sondea hasta que Ollama y los modelos esten disponibles."""
        instalados = ollama_client.modelos_disponibles()
        if instalados is None:
            return False, "Esperando a Ollama..."
        faltan = sorted(self.modelos_requeridos - instalados)
        if faltan:
            return False, "Faltan modelos en Ollama: " + ", ".join(faltan)
        return True, "Listo"

    def procesar(self, texto, historial):
        """Generador de eventos (tipo, contenido); ver generador.procesar."""
        yield from generador.procesar(texto, historial)


def main():
    App(Backend()).mainloop()


if __name__ == "__main__":
    main()
