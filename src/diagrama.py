"""Renderizado local de diagramas de flujo a PNG usando solo Pillow.

Entrada (dict):
    {"titulo": str,
     "nodos":   [{"id": str, "texto": str, "tipo": "inicio|proceso|decision|fin"}],
     "aristas": [{"de": id, "a": id, "etiqueta": str (opcional)}]}

Se dibuja por capas (de arriba hacia abajo). Las flechas que saltan varias capas
pasan por nodos intermedios invisibles para no atravesar otros nodos, y los ciclos
se dibujan por el lado derecho.
"""
import math
import textwrap

from PIL import Image, ImageDraw, ImageFont


class DiagramaError(Exception):
    """La especificacion del diagrama no es valida."""


MAX_NODOS = 30
MAX_ARISTAS = 60
TIPOS = ("inicio", "proceso", "decision", "fin")
COLORES = {"inicio": "#d5f5e3", "proceso": "#d6eaf8", "decision": "#fcf3cf", "fin": "#fadbd8"}
BORDE = "#34495e"
TEXTO = "#17202a"
FUENTES = (
    "/usr/share/fonts/truetype/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/ttf/DejaVuSans.ttf",
    "DejaVuSans.ttf",
)


def _fuente(tam):
    for ruta in FUENTES:
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            continue
    try:
        return ImageFont.load_default(tam)
    except TypeError:        # Pillow antiguo, sin tamano
        return ImageFont.load_default()


def normalizar(spec):
    """Valida y limpia la especificacion. Devuelve (titulo, nodos, aristas)."""
    if not isinstance(spec, dict):
        raise DiagramaError("la especificacion no es un objeto JSON")
    nodos, vistos = [], set()
    for n in spec.get("nodos") or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id", "")).strip()
        if not nid or nid in vistos:
            continue
        vistos.add(nid)
        tipo = str(n.get("tipo", "proceso")).strip().lower()
        nodos.append({
            "id": nid,
            "texto": str(n.get("texto") or nid).strip()[:80],
            "tipo": tipo if tipo in TIPOS else "proceso",
        })
        if len(nodos) >= MAX_NODOS:
            break
    if not nodos:
        raise DiagramaError("el diagrama no tiene nodos")
    aristas = []
    for a in spec.get("aristas") or []:
        if not isinstance(a, dict):
            continue
        de, hasta = str(a.get("de", "")).strip(), str(a.get("a", "")).strip()
        if de in vistos and hasta in vistos and de != hasta:
            aristas.append({"de": de, "a": hasta,
                            "etiqueta": str(a.get("etiqueta") or "").strip()[:20]})
        if len(aristas) >= MAX_ARISTAS:
            break
    titulo = str(spec.get("titulo") or "Diagrama").strip()[:80]
    return titulo, nodos, aristas


def _capas(ids, aristas):
    """Capa de cada nodo (camino mas largo) y conjunto de aristas que cierran ciclos."""
    adj = {i: [] for i in ids}
    for a in aristas:
        adj[a["de"]].append(a["a"])
    estado, atras = {}, set()

    def dfs(u):
        estado[u] = 1
        for v in adj[u]:
            if estado.get(v) == 1:
                atras.add((u, v))
            elif v not in estado:
                dfs(v)
        estado[u] = 2

    con_entrada = {a["a"] for a in aristas}
    for i in ids:
        if i not in con_entrada and i not in estado:
            dfs(i)
    for i in ids:
        if i not in estado:
            dfs(i)

    capa = {i: 0 for i in ids}
    dag = [(a["de"], a["a"]) for a in aristas if (a["de"], a["a"]) not in atras]
    for _ in range(len(ids) + 1):
        cambio = False
        for u, v in dag:
            if capa[v] < capa[u] + 1:
                capa[v] = capa[u] + 1
                cambio = True
        if not cambio:
            break
    return capa, atras


def _flecha(d, pts, etiqueta, fuente):
    d.line(pts, fill=BORDE, width=2, joint="curve")
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    ang = math.atan2(y1 - y0, x1 - x0)
    p1 = (x1 - 13 * math.cos(ang - 0.4), y1 - 13 * math.sin(ang - 0.4))
    p2 = (x1 - 13 * math.cos(ang + 0.4), y1 - 13 * math.sin(ang + 0.4))
    d.polygon([(x1, y1), p1, p2], fill=BORDE)
    if etiqueta:
        (ax, ay), (bx, by) = pts[0], pts[1]
        mx, my = ax + (bx - ax) * 0.4, ay + (by - ay) * 0.4
        bb = d.textbbox((0, 0), etiqueta, font=fuente)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.rectangle([mx + 4, my - th / 2 - 2, mx + 8 + tw, my + th / 2 + 3], fill="white")
        d.text((mx + 6 - bb[0], my - th / 2 - bb[1]), etiqueta, font=fuente, fill=TEXTO)


def renderizar(spec, ruta_png):
    """Dibuja el diagrama y lo guarda en ruta_png. Devuelve (ancho, alto)."""
    titulo, nodos, aristas = normalizar(spec)
    ids = [n["id"] for n in nodos]
    capa, atras = _capas(ids, aristas)

    f_txt, f_tit, f_eti = _fuente(16), _fuente(22), _fuente(13)
    medida = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    # --- tamano de cada nodo ---
    caja = {}
    for n in nodos:
        ancho_txt = 16 if n["tipo"] == "decision" else 24
        txt = "\n".join(textwrap.wrap(n["texto"], ancho_txt) or [n["texto"]])
        bb = medida.multiline_textbbox((0, 0), txt, font=f_txt, align="center", spacing=4)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if n["tipo"] == "decision":
            w, h = tw * 2 + 20, th * 2 + 20
        elif n["tipo"] in ("inicio", "fin"):
            w, h = tw + 50, th + 30
        else:
            w, h = tw + 36, th + 28
        caja[n["id"]] = {"txt": txt, "tw": tw, "th": th, "bb": bb,
                         "w": max(w, 90), "h": max(h, 46)}

    # --- capas y nodos intermedios ---
    n_capas = max(capa.values()) + 1
    capas = [[] for _ in range(n_capas)]
    for i in ids:
        capas[capa[i]].append(i)
    ficticio = {}
    rutas = []
    for k, a in enumerate(aristas):
        u, v = a["de"], a["a"]
        if (u, v) in atras:
            continue
        cadena = [u]
        for c in range(capa[u] + 1, capa[v]):
            clave = ("d", k, c)
            capas[c].append(clave)
            ficticio[clave] = 26
            cadena.append(clave)
        cadena.append(v)
        rutas.append((a, cadena))

    # --- orden dentro de cada capa (baricentro) ---
    arriba, abajo = {}, {}
    for _, cadena in rutas:
        for x, y in zip(cadena, cadena[1:]):
            arriba.setdefault(y, []).append(x)
            abajo.setdefault(x, []).append(y)
    pos = {}

    def reindexar():
        for c in capas:
            for idx, k in enumerate(c):
                pos[k] = idx

    def baricentro(k, vec):
        vs = vec.get(k)
        return sum(pos[v] for v in vs) / len(vs) if vs else pos[k]

    reindexar()
    for _ in range(4):
        for c in range(1, n_capas):
            capas[c].sort(key=lambda k: baricentro(k, arriba))
            reindexar()
        for c in range(n_capas - 2, -1, -1):
            capas[c].sort(key=lambda k: baricentro(k, abajo))
            reindexar()

    # --- coordenadas ---
    def ancho(k):
        return caja[k]["w"] if k in caja else ficticio[k]

    def alto(k):
        return caja[k]["h"] if k in caja else 0

    sep_x, sep_y, margen, h_titulo = 50, 70, 40, 60
    anchos_capa = [sum(ancho(k) for k in c) + sep_x * max(len(c) - 1, 0) for c in capas]
    h_capa = [max([alto(k) for k in c] + [0]) for c in capas]
    extra_der = 30 + 14 * len({e for e in atras}) if atras else 0
    W = int(max(anchos_capa) + 2 * margen + extra_der)
    centro = {}
    cursor = margen + h_titulo
    for c, claves in enumerate(capas):
        cy = cursor + h_capa[c] / 2
        x = margen + (W - extra_der - 2 * margen - anchos_capa[c]) / 2
        for k in claves:
            centro[k] = (x + ancho(k) / 2, cy)
            x += ancho(k) + sep_x
        cursor += h_capa[c] + sep_y
    H = int(cursor - sep_y + margen)

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    bb = d.textbbox((0, 0), titulo, font=f_tit)
    d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], margen / 2 - bb[1] + 6), titulo,
           font=f_tit, fill=TEXTO)

    # --- aristas normales ---
    for a, cadena in rutas:
        u, v = cadena[0], cadena[-1]
        ux, uy = centro[u]
        vx, vy = centro[v]
        siguiente = centro[cadena[1]]
        inicio = (ux, uy + caja[u]["h"] / 2)
        if nodos[ids.index(u)]["tipo"] == "decision":
            dx = siguiente[0] - ux
            if dx < -10:
                inicio = (ux - caja[u]["w"] / 2, uy)
            elif dx > 10:
                inicio = (ux + caja[u]["w"] / 2, uy)
        pts = [inicio] + [centro[k] for k in cadena[1:-1]] + [(vx, vy - caja[v]["h"] / 2)]
        _flecha(d, pts, a["etiqueta"], f_eti)

    # --- aristas de ciclo: por el lado derecho ---
    for n_atras, (u, v) in enumerate(sorted(atras)):
        etiqueta = next((a["etiqueta"] for a in aristas if (a["de"], a["a"]) == (u, v)), "")
        ux, uy = centro[u]
        vx, vy = centro[v]
        xr = W - 24 - 14 * n_atras
        pts = [(ux + caja[u]["w"] / 2, uy), (xr, uy), (xr, vy), (vx + caja[v]["w"] / 2, vy)]
        _flecha(d, pts, etiqueta, f_eti)

    # --- nodos ---
    for n in nodos:
        cx, cy = centro[n["id"]]
        b = caja[n["id"]]
        w, h = b["w"], b["h"]
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        col = COLORES[n["tipo"]]
        if n["tipo"] == "decision":
            d.polygon([(cx, y0), (x1, cy), (cx, y1), (x0, cy)], fill=col, outline=BORDE, width=2)
        elif n["tipo"] in ("inicio", "fin"):
            d.rounded_rectangle([x0, y0, x1, y1], radius=h / 2, fill=col, outline=BORDE, width=2)
        else:
            d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=col, outline=BORDE, width=2)
        d.multiline_text((cx - b["tw"] / 2 - b["bb"][0], cy - b["th"] / 2 - b["bb"][1]),
                         b["txt"], font=f_txt, fill=TEXTO, align="center", spacing=4)

    img.save(ruta_png, "PNG")
    return W, H
