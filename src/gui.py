"""Interfaz Tkinter: entrada y salida de texto, con vista previa de diagramas PNG.

Enter envia, Shift+Enter inserta salto de linea. El historial crece hacia abajo:
la entrada del usuario arriba y la respuesta del modelo justo debajo.

El backend entrega eventos (tipo, contenido):
    texto    fragmento de la respuesta (entra al historial del modelo)
    nota     informacion para el usuario (no entra al historial)
    archivo  ruta de un archivo guardado (si es .png se muestra una vista previa)
"""
import queue
import threading
import time
import tkinter as tk
from tkinter import scrolledtext


class App(tk.Tk):
    def __init__(self, backend):
        super().__init__()
        self.title("Asistente Edge AI")
        self.geometry("900x650")
        self.minsize(500, 400)

        self.backend = backend
        self.historial = []          # mensajes {"role", "content"}
        self.cola = queue.Queue()    # hilos -> GUI
        self.ocupado = True          # bloqueado hasta que los servicios respondan
        self._parcial = ""
        self._imagenes = []          # referencias: Tk libera las imagenes sin ellas

        self._crear_widgets()
        self.estado.set("Esperando a los servicios de IA...")
        threading.Thread(target=self._esperar_backend, daemon=True).start()
        self.after(50, self._revisar_cola)

    # -- construccion ---------------------------------------------------------
    def _crear_widgets(self):
        self.salida = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, state=tk.DISABLED,
            font=("DejaVu Sans", 12), padx=12, pady=12,
            relief=tk.FLAT, bg="#fafafa",
        )
        self.salida.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        self.salida.tag_configure("usuario", foreground="#1a4fa0",
                                  font=("DejaVu Sans", 12, "bold"),
                                  spacing1=10, spacing3=4)
        self.salida.tag_configure("asistente", foreground="#222222", spacing3=10)
        self.salida.tag_configure("nota", foreground="#7f8c8d",
                                  font=("DejaVu Sans", 10, "italic"),
                                  spacing1=2, spacing3=2)
        self.salida.tag_configure("archivo", foreground="#1e8449",
                                  font=("DejaVu Sans", 11, "bold"))
        self.salida.tag_configure("error", foreground="#b00020")

        self.estado = tk.StringVar(value="")
        tk.Label(self, textvariable=self.estado, anchor="w",
                 fg="#666666").pack(fill=tk.X, padx=12)

        self.entrada = tk.Text(self, height=3, wrap=tk.WORD,
                               font=("DejaVu Sans", 12), padx=8, pady=6)
        self.entrada.pack(fill=tk.X, padx=8, pady=(2, 8))
        self.entrada.focus_set()
        self.entrada.bind("<Return>", self._on_enter)
        self.entrada.bind("<Shift-Return>", lambda e: None)

    def _escribir(self, texto, tag=None):
        self.salida.configure(state=tk.NORMAL)
        self.salida.insert(tk.END, texto, tag)
        self.salida.see(tk.END)
        self.salida.configure(state=tk.DISABLED)

    def _mostrar_imagen(self, ruta):
        """Vista previa de un PNG dentro de la conversacion (Tk lo lee de forma nativa)."""
        try:
            img = tk.PhotoImage(file=ruta)
            factor = max(1, -(-img.width() // 820), -(-img.height() // 700))
            if factor > 1:
                img = img.subsample(factor)
            self._imagenes.append(img)
            self.salida.configure(state=tk.NORMAL)
            self.salida.image_create(tk.END, image=img)
            self.salida.insert(tk.END, "\n")
            self.salida.see(tk.END)
            self.salida.configure(state=tk.DISABLED)
        except Exception as exc:  # noqa: BLE001
            self._escribir(f"(no se pudo mostrar la vista previa: {exc})\n", "nota")

    # -- eventos --------------------------------------------------------------
    def _on_enter(self, _event):
        if self.ocupado:
            return "break"
        texto = self.entrada.get("1.0", tk.END).strip()
        if texto:
            self.entrada.delete("1.0", tk.END)
            self._enviar(texto)
        return "break"

    def _enviar(self, texto):
        self.ocupado = True
        self._parcial = ""
        self.estado.set("Procesando...")
        self.historial.append({"role": "user", "content": texto})
        self._escribir(f"Tu: {texto}\n", "usuario")
        threading.Thread(
            target=self._trabajador, args=(texto, list(self.historial)), daemon=True
        ).start()

    # -- hilos (nunca tocan widgets) -------------------------------------------
    def _esperar_backend(self):
        ultimo = None
        while True:
            try:
                ok, mensaje = self.backend.verificar()
            except Exception as exc:  # noqa: BLE001
                ok, mensaje = False, f"Error al verificar servicios: {exc}"
            if mensaje != ultimo:
                self.cola.put(("estado", mensaje))
                ultimo = mensaje
            if ok:
                self.cola.put(("listo", None))
                return
            time.sleep(2)

    def _trabajador(self, texto, historial):
        try:
            for evento in self.backend.procesar(texto, historial):
                self.cola.put(("evento", evento))
            self.cola.put(("fin", None))
        except Exception as exc:  # noqa: BLE001
            self.cola.put(("error", str(exc)))

    # -- cola hilos -> GUI ------------------------------------------------------
    def _evento(self, evento):
        if isinstance(evento, str):
            evento = ("texto", evento)
        tipo, contenido = evento
        if tipo == "texto":
            self._parcial += contenido
            self._escribir(contenido, "asistente")
        elif tipo == "nota":
            self._escribir(contenido + "\n", "nota")
        elif tipo == "archivo":
            self._escribir(f"\nArchivo guardado: {contenido}\n", "archivo")
            if contenido.lower().endswith(".png"):
                self._mostrar_imagen(contenido)

    def _revisar_cola(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "estado":
                    self.estado.set(dato)
                elif tipo == "listo":
                    self._terminar()
                elif tipo == "evento":
                    self._evento(dato)
                elif tipo == "fin":
                    self.historial.append(
                        {"role": "assistant",
                         "content": self._parcial or "(archivo generado)"})
                    self._escribir("\n", "asistente")
                    self._terminar()
                elif tipo == "error":
                    self._escribir(f"\n{dato}\n\n", "error")
                    if self.historial and self.historial[-1]["role"] == "user":
                        self.historial.pop()
                    self._terminar()
        except queue.Empty:
            pass
        self.after(50, self._revisar_cola)

    def _terminar(self):
        self.ocupado = False
        self.estado.set("Listo")
        self.entrada.focus_set()
