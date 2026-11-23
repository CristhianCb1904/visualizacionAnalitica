#!/usr/bin/env python3
"""
Optimiza las 10 gráficas Plotly del dashboard de la Task 1 (SciVis Contest 2026).

Las gráficas originales se exportaron con ``fig.write_html(include_plotlyjs="cdn")``
y no tenemos el notebook que las generó. Este script lee el JSON que va dentro de
cada HTML original y escribe una versión ligera en ``graficas/``:

Fase A (rendimiento, sin cambiar los datos)
  * Redondea coordenadas a 0,01° y el resto de valores a 4 cifras significativas.
  * Quita de cada frame las coordenadas que no cambian entre frames.
  * Sustituye el texto de tooltip precalculado por ``hovertemplate``.
  * Quita el ancho/alto fijos para que la figura ocupe todo su contenedor.
  * No reproduce la animación automáticamente al cargar.

Fase B (legibilidad)
  * U, V y W con paleta divergente (RdBu) centrada en 0 y rango fijo entre frames;
    la magnitud M con Viridis desde 0.
  * Tooltips con coordenadas, variable y unidad; títulos y ejes con unidades.
  * Corrige W (malla 90×90) submuestreándola a la malla 45×45 de U y V.
  * Ejes de los mapas de calor en grados en vez de índices de malla.

Fase C (flechas en el navegador)
  * Las flechas de dirección de los globos ya no se guardan: ``assets/grafica.js``
    las dibuja a partir de U y V con la misma geometría que las originales.

Uso:
    python tools/optimizar_graficas.py               # lee los originales del commit 9155d57
    python tools/optimizar_graficas.py --origen DIR  # o de una carpeta con los HTML originales
"""
import argparse
import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "graficas"
COMMIT_ORIGINAL = "9155d57"

# ----------------------------------------------------------------- paletas
DIVERGENTE = [  # ColorBrewer RdBu invertida: azul = negativo, rojo = positivo
    [0.0, "#053061"], [0.1, "#2166ac"], [0.2, "#4393c3"], [0.3, "#92c5de"],
    [0.4, "#d1e5f0"], [0.5, "#f7f7f7"], [0.6, "#fddbc7"], [0.7, "#f4a582"],
    [0.8, "#d6604d"], [0.9, "#b2182b"], [1.0, "#67001f"],
]
SECUENCIAL = "Viridis"
COLOR_BARRAS = "#38bdf8"
FONDO = "#0b1120"
PANEL = "#111c30"

# Grados de la malla de 90 × 90 (la de 45 × 45 es esta tomada cada 2 puntos),
# la misma convención que usan los globos originales.
LAT90 = np.linspace(-90, 90, 90)
LON90 = np.linspace(-180, 180, 90)

# Nivel Z ↔ presión, comprobado: capas_uvw (Z=40,41,42) tiene los mismos datos
# que mapa_presion (769, 822, 876 hPa).
Z_A_HPA = {40: 769, 41: 822, 42: 876}

GRAFICAS = {
    # destino: archivo original
    "globo_presion.html": "globo_presion.html",
    "capas_uvw.html": "capas_uvw.html",
    "globo_tiempo.html": "globo_tiempo.html",
    "hist_percentiles.html": "hist_percentiles.html",
    "mapa_presion.html": "mapa_presion.html",
    "mapa_uv_mag.html": "mapa_uv_mag (1).html",
    "panel_niveles.html": "panel_niveles.html",
    "uv_niveles.html": "uv_niveles.html",
    "evolucion_temporal.html": "evolucion_temporal.html",
    "perfil_vertical.html": "perfil_vertical.html",
}


# ----------------------------------------------------------------- lectura
def leer_original(nombre, origen):
    if origen:
        return (Path(origen) / nombre).read_text(encoding="utf-8")
    return subprocess.run(
        ["git", "-C", str(RAIZ), "show", f"{COMMIT_ORIGINAL}:{nombre}"],
        check=True, capture_output=True,
    ).stdout.decode("utf-8")


def extraer(html):
    """Devuelve (data, layout, config, frames) de un HTML exportado por plotly.py."""
    dec = json.JSONDecoder()
    i = html.index("Plotly.newPlot(")
    data, fin = dec.raw_decode(html, html.index("[", i))
    layout, fin = dec.raw_decode(html, html.index("{", fin))
    config, fin = dec.raw_decode(html, html.index("{", fin))
    frames = None
    j = html.find("Plotly.addFrames", fin)
    if j >= 0:
        frames, _ = dec.raw_decode(html, html.index("[", j))
    return data, layout, config, frames


# ----------------------------------------------------------------- utilidades
def redondear(obj, clave=None):
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        if clave in ("lat", "lon"):
            return round(obj, 2)
        if obj == 0:
            return 0
        return float(f"{obj:.4g}")
    if isinstance(obj, list):
        return [redondear(x, clave) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in ("colorscale", "domain") else redondear(v, k)) for k, v in obj.items()}
    return obj


def valores(*listas):
    a = np.array([x for l in listas for x in np.ravel(np.array(l, dtype=float))], dtype=float)
    return a[np.isfinite(a)]


def rango_simetrico(*listas, percentil=100):
    a = np.abs(valores(*listas))
    m = float(np.percentile(a, percentil)) if a.size else 1.0
    m = float(f"{m:.3g}")
    return -m, m


def maximo(*listas):
    return float(f"{float(valores(*listas).max()):.3g}")


def submuestrear_w(w):
    """W viene en la malla 90×90; U y V en la 45×45 = 90×90 tomada cada 2 puntos."""
    a = np.array(w, dtype=float)
    if a.ndim == 1:
        a = a.reshape(90, 90)
    assert a.shape == (90, 90), a.shape
    return a[::2, ::2]


def a_lista(a):
    return [[None if not np.isfinite(x) else float(x) for x in fila] for fila in a]


def colorbar(titulo, **extra):
    cb = {"title": {"text": titulo, "side": "right"}, "thickness": 14, "len": 0.75,
          "outlinewidth": 0, "tickfont": {"size": 11}}
    cb.update(extra)
    return cb


def pintar_marcador(traza, escala, cmin, cmax, titulo, centro=None):
    m = traza.setdefault("marker", {})
    m["colorscale"] = escala
    m["cmin"], m["cmax"] = cmin, cmax
    m.pop("cmid", None)
    m["colorbar"] = colorbar(titulo, **{k: v for k, v in (m.get("colorbar") or {}).items() if k == "x"})
    if centro is not None:
        m["cmid"] = centro


def pintar_heatmap(traza, escala, zmin, zmax, titulo):
    traza["colorscale"] = escala
    traza["zmin"], traza["zmax"] = zmin, zmax
    traza.pop("zmid", None)
    traza["colorbar"] = colorbar(titulo, **{k: v for k, v in (traza.get("colorbar") or {}).items() if k == "x"})


def geo_hover(var):
    return ("Lat %{lat:.1f}° · Lon %{lon:.1f}°<br>"
            f"<b>{var} = %{{marker.color:.2f}} m/s</b><extra></extra>")


def mapa_hover(var, dec=2):
    return ("Lat %{y:.1f}° · Lon %{x:.1f}°<br>"
            f"<b>{var} = %{{z:.{dec}f}} m/s</b><extra></extra>")


def titulo(layout, texto):
    layout["title"] = {"text": texto}


# ----------------------------------------------------------------- fase B por gráfica
def globo(data, layout, frames, eje_tiempo):
    """01 y 03: puntos U, V, M + flechas de dirección (trazas 0..3)."""
    todos = [data] + [f["data"] for f in frames]
    lo, hi = rango_simetrico(*[t[0]["marker"]["color"] for t in todos],
                             *[t[1]["marker"]["color"] for t in todos])
    mmax = maximo(*[t[2]["marker"]["color"] for t in todos])
    nombres = [("U", "Componente zonal U (m/s)"), ("V", "Componente meridional V (m/s)"),
               ("M", "Magnitud M (m/s)")]
    for i, (var, cb) in enumerate(nombres):
        t = data[i]
        t.pop("text", None)
        t.pop("hoverinfo", None)
        t["hovertemplate"] = geo_hover(var)
        if var == "M":
            pintar_marcador(t, SECUENCIAL, 0, mmax, cb)
        else:
            pintar_marcador(t, DIVERGENTE, lo, hi, cb)
        t["marker"]["colorbar"]["x"] = 1.0
    for f in frames:
        for t in f["data"][:3]:
            t.pop("text", None)
    # Fase C: las flechas se reconstruyen en el navegador (assets/grafica.js).
    flechas = data[3]
    flechas["lat"], flechas["lon"] = [], []
    for f in frames:
        f["data"][3] = {"type": "scattergeo"}
    data[3]["name"] = "Dirección del viento"
    # Menú de vistas: títulos con variable y unidad.
    menu = layout["updatemenus"][0]
    textos = {
        "Puntos + Flechas": "Magnitud M (m/s) y dirección del viento",
        "Solo Puntos": "Magnitud M del viento (m/s)",
        "Solo Flechas": "Dirección del viento (flechas de longitud fija)",
        "Viento U": "Componente zonal U (m/s) · + hacia el este",
        "Viento V": "Componente meridional V (m/s) · + hacia el norte",
    }
    for b in menu["buttons"]:
        b["args"][1] = {"title.text": textos.get(b["label"], b["label"])}
    return {"flechas": {"traza": 3, "u": 0, "v": 1, "base": 0, "largo": 3.0, "punta": 0.8, "angulo": 150}}


def f_globo_presion(data, layout, frames):
    extra = globo(data, layout, frames, "presion")
    for f in frames:
        f.pop("layout", None)
    for s in layout["sliders"][0]["steps"]:
        hpa = int(s["label"].split()[0])
        z = {v: k for k, v in Z_A_HPA.items()}.get(hpa)
        s["label"] = f"{hpa} hPa" + (f" (Z={z})" if z else "")
    layout["sliders"][0]["currentvalue"] = {"prefix": "Nivel de presión: "}
    titulo(layout, "Magnitud M (m/s) y dirección del viento")
    return extra


def f_globo_tiempo(data, layout, frames):
    extra = globo(data, layout, frames, "tiempo")
    for f in frames:
        f.pop("layout", None)
    layout["sliders"][0]["currentvalue"] = {"prefix": "Paso de tiempo: "}
    titulo(layout, "Magnitud M (m/s) y dirección del viento")
    return extra


def f_mapa_presion(data, layout, frames):
    pasos = layout["sliders"][0]["steps"]
    # Corrige W: 8.100 colores (malla 90×90) para 2.025 puntos (malla 45×45).
    data[3]["marker"]["color"] = submuestrear_w(data[3]["marker"]["color"]).ravel().tolist()
    for s in pasos:
        col = s["args"][0]["marker.color"]
        col[3] = submuestrear_w(col[3]).ravel().tolist()
    capas = [[s["args"][0]["marker.color"][i] for s in pasos] for i in range(4)]
    lo, hi = rango_simetrico(*capas[0], *capas[1])
    wlo, whi = rango_simetrico(*capas[3], percentil=99)
    mmax = maximo(*capas[2])
    conf = [("U", DIVERGENTE, lo, hi, "U (m/s)"), ("V", DIVERGENTE, lo, hi, "V (m/s)"),
            ("M", SECUENCIAL, 0, mmax, "M (m/s)"), ("W", DIVERGENTE, wlo, whi, "W (m/s)")]
    for t, (var, esc, a, b, cb) in zip(data, conf):
        pintar_marcador(t, esc, a, b, cb)
        t["marker"]["colorbar"]["x"] = 1.0
        t["hovertemplate"] = geo_hover(var)
    for s in pasos:
        hpa = int(s["label"].split()[0])
        z = {v: k for k, v in Z_A_HPA.items()}.get(hpa)
        s["label"] = f"{hpa} hPa" + (f" (Z={z})" if z else "")
    layout["sliders"][0]["currentvalue"] = {"prefix": "Nivel de presión: "}
    textos = {"Viento U": "Componente zonal U (m/s) · + hacia el este",
              "Viento V": "Componente meridional V (m/s) · + hacia el norte",
              "Magnitud": "Magnitud M (m/s)",
              "Viento W": "Velocidad vertical W (m/s) · escala al percentil 99"}
    for b in layout["updatemenus"][0]["buttons"]:
        b["args"][1] = {"title.text": textos[b["label"]]}
    titulo(layout, textos["Viento U"])


def f_capas_uvw(data, layout, frames):
    pasos = layout["sliders"][0]["steps"]
    data[3]["z"] = a_lista(submuestrear_w(data[3]["z"]))
    for s in pasos:
        z = s["args"][0]["z"]
        z[3] = a_lista(submuestrear_w(z[3]))
    capas = [[s["args"][0]["z"][i] for s in pasos] for i in range(4)]
    lo, hi = rango_simetrico(*capas[0], *capas[1])
    wlo, whi = rango_simetrico(*capas[3], percentil=99)
    mmax = maximo(*capas[2])
    conf = [("U", DIVERGENTE, lo, hi, "U (m/s)", 2), ("V", DIVERGENTE, lo, hi, "V (m/s)", 2),
            ("M", SECUENCIAL, 0, mmax, "M (m/s)", 2), ("W", DIVERGENTE, wlo, whi, "W (m/s)", 3)]
    for t, (var, esc, a, b, cb, dec) in zip(data, conf):
        pintar_heatmap(t, esc, a, b, cb)
        t["x"], t["y"] = LON90[::2].round(2).tolist(), LAT90[::2].round(2).tolist()
        t["hovertemplate"] = mapa_hover(var, dec)
    for s in pasos:
        z = int(s["label"].split(":")[1])
        s["label"] = f"Z={z}" + (f" (≈{Z_A_HPA[z]} hPa)" if z in Z_A_HPA else "")
    layout["sliders"][0]["currentvalue"] = {"prefix": "Nivel: "}
    textos = {"Viento U": "Componente zonal U (m/s) · + hacia el este",
              "Viento V": "Componente meridional V (m/s) · + hacia el norte",
              "Magnitud": "Magnitud M (m/s)",
              "Viento W": "Velocidad vertical W (m/s) · escala al percentil 99"}
    for b in layout["updatemenus"][0]["buttons"]:
        b["args"][1] = {"title.text": textos[b["label"]]}
    titulo(layout, textos["Viento U"])
    layout["xaxis"] = {"title": {"text": "Longitud (°)"}, "constrain": "domain"}
    layout["yaxis"] = {"title": {"text": "Latitud (°)"}, "scaleanchor": "x", "scaleratio": 1, "constrain": "domain"}


def f_mapa_uv_mag(data, layout, frames):
    zs = [t["z"] for t in data]
    lo, hi = rango_simetrico(zs[0], zs[1])
    mmax = maximo(zs[2])
    conf = [("U", DIVERGENTE, lo, hi, "U (m/s)"), ("V", DIVERGENTE, lo, hi, "V (m/s)"),
            ("M", SECUENCIAL, 0, mmax, "M (m/s)")]
    for t, (var, esc, a, b, cb) in zip(data, conf):
        pintar_heatmap(t, esc, a, b, cb)
        t["x"], t["y"] = LON90.round(2).tolist(), LAT90.round(2).tolist()
        t["hovertemplate"] = mapa_hover(var)
    textos = ["Componente zonal U (m/s) · + hacia el este",
              "Componente meridional V (m/s) · + hacia el norte",
              "Magnitud M = √(U² + V²) (m/s)"]
    for b, txt in zip(layout["updatemenus"][0]["buttons"], textos):
        b["args"][1] = {"title.text": txt}
    titulo(layout, textos[0])
    layout["xaxis"] = {"title": {"text": "Longitud (°)"}, "constrain": "domain"}
    layout["yaxis"] = {"title": {"text": "Latitud (°)"}, "scaleanchor": "x", "scaleratio": 1, "constrain": "domain"}


def f_panel_niveles(data, layout, frames):
    def ajustar(trazas, inicial):
        for t in trazas:
            if t.get("type") == "heatmap":
                t["colorscale"] = SECUENCIAL
                if inicial:
                    t["colorbar"] = colorbar("M (m/s)", x=0.46)
                    t["x"], t["y"] = LON90[::2].round(2).tolist(), LAT90[::2].round(2).tolist()
                    t["hovertemplate"] = mapa_hover("M")
                else:
                    t.pop("colorbar", None)
            elif t.get("type") == "bar":
                t["marker"] = {"color": COLOR_BARRAS}
                if inicial:
                    t["hovertemplate"] = "M ≈ %{x:.2f} m/s<br>%{y} puntos de malla<extra></extra>"
    ajustar(data, True)
    for f in frames:
        ajustar(f["data"], False)
        f["layout"] = {"title": {"text": f"Magnitud M por nivel vertical · paso de tiempo {f['name']}"}}
    layout["xaxis"]["title"] = {"text": "Longitud (°)"}
    layout["yaxis"]["title"] = {"text": "Latitud (°)"}
    layout["xaxis2"]["title"] = {"text": "Magnitud M (m/s)"}
    layout["yaxis2"]["title"] = {"text": "Puntos de malla"}
    layout.pop("annotations", None)  # los títulos de subgráfica chocaban con los menús
    for b in layout["updatemenus"][0]["buttons"]:
        b["args"][1] = {"title.text": f"Magnitud M por nivel vertical · {b['label']}"}
    layout["sliders"][0]["currentvalue"] = {"prefix": "Paso de tiempo: "}
    titulo(layout, "Magnitud M por nivel vertical · paso de tiempo 0")
    layout["showlegend"] = False


def f_hist_percentiles(data, layout, frames):
    for t in [data[0]] + [f["data"][0] for f in frames]:
        t["marker"] = {"color": COLOR_BARRAS}
    data[0]["hovertemplate"] = "M ≈ %{x:.2f} m/s<br>%{y} puntos de malla<extra></extra>"
    for f in frames:
        f["layout"]["title"] = {"text": f"Distribución de la magnitud M · Z=51 · paso de tiempo {f['name']}"}
    titulo(layout, "Distribución de la magnitud M · Z=51 · paso de tiempo 0")
    layout["xaxis"]["title"] = {"text": "Magnitud horizontal M = √(U² + V²) (m/s)"}
    layout["yaxis"]["title"] = {"text": "Puntos de malla"}
    layout["sliders"][0]["currentvalue"] = {"prefix": "Paso de tiempo: "}


def f_uv_niveles(data, layout, frames):
    for b in layout["updatemenus"][0]["buttons"]:
        b["label"] = b["label"].replace("Z=45 (Superficie)", "Z=45 (Cerca de superficie)")
        b["args"][1]["title"] = b["args"][1]["title"].replace("Z=45 (Superficie)", "Z=45 (Cerca de superficie)")
        b["args"][1]["title"] = b["args"][1]["title"].replace("Distribución Frecuencial", "Distribución conjunta")
        b["args"][1] = {"title.text": b["args"][1]["title"]}
    titulo(layout, layout["updatemenus"][0]["buttons"][0]["args"][1]["title.text"])
    for t in data:
        t["colorbar"] = colorbar("Puntos de malla")
        t["hovertemplate"] = ("U = %{x:.2f} m/s · V = %{y:.2f} m/s<br>"
                              "<b>%{z} puntos de malla</b><extra></extra>")
    layout["xaxis"]["title"] = {"text": "Componente zonal U (m/s) · − oeste / + este"}
    layout["yaxis"]["title"] = {"text": "Componente meridional V (m/s) · − sur / + norte"}


def f_evolucion_temporal(data, layout, frames):
    for t in data:
        t["hovertemplate"] = "%{y:.2f} m/s"
    data[0]["name"], data[1]["name"], data[2]["name"] = "U zonal", "V meridional", "Magnitud M"
    titulo(layout, "Evolución de la media de U, V y M · Z=51")
    layout["xaxis"]["title"] = {"text": "Paso de tiempo de la simulación"}
    layout["yaxis"]["title"] = {"text": "Media espacial (m/s)"}
    layout["yaxis"]["zeroline"] = True
    layout["yaxis"]["zerolinecolor"] = "#64748b"
    layout["legend"] = {"orientation": "h", "y": -0.18, "x": 0}


def f_perfil_vertical(data, layout, frames):
    titulo(layout, "Perfil vertical de la magnitud media M · paso de tiempo 0")
    layout["xaxis"]["title"] = {"text": "Magnitud media M (m/s)"}
    layout["yaxis"]["title"] = {"text": "Nivel vertical Z (0 = tope · 51 = superficie)"}


# Trazas de W que pasan de la malla 90×90 a la 45×45.
W_CORREGIDA = {"capas_uvw.html": 3, "mapa_presion.html": 3}

AJUSTES = {
    "globo_presion.html": f_globo_presion, "globo_tiempo.html": f_globo_tiempo,
    "mapa_presion.html": f_mapa_presion, "capas_uvw.html": f_capas_uvw,
    "mapa_uv_mag.html": f_mapa_uv_mag, "panel_niveles.html": f_panel_niveles,
    "hist_percentiles.html": f_hist_percentiles, "uv_niveles.html": f_uv_niveles,
    "evolucion_temporal.html": f_evolucion_temporal, "perfil_vertical.html": f_perfil_vertical,
}


# ----------------------------------------------------------------- fase A común
def estilo_comun(layout):
    for k in ("width", "height"):
        layout.pop(k, None)
    layout["autosize"] = True
    layout["paper_bgcolor"] = FONDO
    if "geo" not in layout:
        layout["plot_bgcolor"] = FONDO
    layout["font"] = {"family": "Inter, 'Segoe UI', system-ui, sans-serif", "color": "#e2e8f0", "size": 12}
    t = layout.get("title") or {}
    t.update({"x": 0.02, "xanchor": "left", "font": {"size": 15}})
    layout["title"] = t
    layout["hoverlabel"] = {"bgcolor": PANEL, "bordercolor": "#38bdf8",
                            "font": {"color": "#f8fafc", "size": 12}}
    if "geo" in layout:
        layout["geo"]["bgcolor"] = FONDO
    t.update({"y": 0.98, "yref": "container", "yanchor": "top"})
    # Menús en una fila fija sobre el área de la gráfica: selector a la izquierda,
    # reproducir/pausa a la derecha (Plotly pinta el botón activo casi blanco,
    # por eso el texto es oscuro).
    for m in layout.get("updatemenus", []):
        animacion = any(b.get("method") == "animate" for b in m.get("buttons", []))
        if animacion:
            for b in m["buttons"]:
                b["label"] = "▶" if b["args"][0] is None else "⏸"
        m.update({"bgcolor": "#94a3b8", "bordercolor": "#475569", "borderwidth": 1,
                  "font": {"color": FONDO, "size": 11},
                  "x": 1 if animacion else 0, "xanchor": "right" if animacion else "left",
                  "y": 1.02, "yanchor": "bottom", "pad": {"t": 0, "b": 4, "l": 0, "r": 0},
                  "direction": "right" if animacion or m.get("type") == "buttons" else "down"})
    for s in layout.get("sliders", []):
        s.update({"bgcolor": "#334155", "activebgcolor": "#38bdf8", "bordercolor": "#334155",
                  "font": {"color": "#cbd5e1", "size": 10}, "x": 0.05, "len": 0.9,
                  "xanchor": "left", "y": 0, "yanchor": "top", "pad": {"t": 40, "b": 0}})
        s.setdefault("currentvalue", {})["font"] = {"color": "#e2e8f0", "size": 12}


def quitar_constantes(data, frames):
    """Quita de los frames las claves de coordenadas iguales en todos y en el estado inicial."""
    if not frames:
        return
    for i in range(len(frames[0]["data"])):
        for k in ("lat", "lon", "x", "y"):
            ref = data[i].get(k) if i < len(data) else None
            if ref is None:
                continue
            if all(i < len(f["data"]) and f["data"][i].get(k) == ref for f in frames):
                for f in frames:
                    f["data"][i].pop(k, None)


def contar(data, frames):
    def n(t):
        return {k: int(np.size(np.array(t[k], dtype=object))) for k in ("lat", "lon", "x", "y", "z") if k in t}
    return [n(t) for t in data], (len(frames) if frames else 0)


PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<link rel="preconnect" href="https://cdn.plot.ly" crossorigin>
<link rel="stylesheet" href="../assets/grafica.css">
</head>
<body>
<div id="grafica" role="img" aria-label="{titulo}"></div>
<div id="estado" class="estado">Cargando gráfica…</div>
<script type="application/json" id="figura">{json}</script>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<script src="../assets/grafica.js"></script>
</body>
</html>
"""


def procesar(destino, original, origen):
    html = leer_original(original, origen)
    data, layout, config, frames = extraer(html)
    antes = contar(data, frames)
    data, layout, frames = copy.deepcopy(data), copy.deepcopy(layout), copy.deepcopy(frames)
    extra = AJUSTES[destino](data, layout, frames or []) or {}
    estilo_comun(layout)
    quitar_constantes(data, frames)
    fig = {"data": redondear(data), "layout": redondear(layout), "frames": redondear(frames) if frames else None}
    fig.update(extra)
    # Comprobación: mismo número de trazas, puntos y frames (las flechas se rehacen en el navegador).
    despues = contar(fig["data"], fig["frames"])
    for i, (a, b) in enumerate(zip(antes[0], despues[0])):
        if extra.get("flechas", {}).get("traza") == i:
            continue
        if W_CORREGIDA.get(destino) == i:  # 90×90 → 45×45
            a = {k: (v // 4 if v == 8100 else v) for k, v in a.items()}
        assert all(b.get(k) == v for k, v in a.items()), (destino, i, a, b)
    assert len(antes[0]) == len(despues[0]) and antes[1] == despues[1], destino
    texto = json.dumps(fig, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tit = layout["title"]["text"].split("<br>")[0]
    salida = SALIDA / destino
    salida.write_text(PLANTILLA.format(titulo=tit, json=texto), encoding="utf-8")
    return len(html.encode()), salida.stat().st_size


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origen", help="carpeta con los HTML originales (por defecto, el commit original)")
    args = p.parse_args()
    SALIDA.mkdir(exist_ok=True)
    total_a = total_d = 0
    print(f"{'Gráfica':26s} {'original':>10s} {'optimizada':>11s}")
    for destino, original in GRAFICAS.items():
        a, d = procesar(destino, original, args.origen)
        total_a += a
        total_d += d
        print(f"{destino:26s} {a / 1e6:9.2f}MB {d / 1e6:10.2f}MB")
    print(f"{'TOTAL':26s} {total_a / 1e6:9.2f}MB {total_d / 1e6:10.2f}MB")


if __name__ == "__main__":
    sys.exit(main())
