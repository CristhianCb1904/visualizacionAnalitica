# visualizacionAnalitica

Dashboard interactivo de la **Task 1 del SciVis Contest 2026**: circulación atmosférica
(viento U, V, W, magnitud M y presión) en la simulación DYAMOND GEOS.

## Estructura

| Ruta | Qué es |
| --- | --- |
| `index.html`, `style.css`, `script.js` | Dashboard: visor con estados de carga/error y 10 visualizaciones en 4 grupos. |
| `graficas/*.html` | Las 10 gráficas Plotly (se pueden abrir solas). |
| `assets/grafica.js`, `assets/grafica.css` | Renderizador común: dibuja la figura, rehace las flechas de dirección y adapta la gráfica al móvil. |
| `tools/optimizar_graficas.py` | Genera `graficas/` a partir de los HTML originales exportados desde Python. |

| # | Gráfica | Variables | Grupo |
| --- | --- | --- | --- |
| 01 | `globo_presion` | U, V, M, p | Vista global |
| 03 | `globo_tiempo` | U, V, M | Vista global |
| 05 | `mapa_presion` | U, V, W, M, p | Campos horizontales |
| 06 | `mapa_uv_mag` | U, V, M | Campos horizontales |
| 02 | `capas_uvw` | U, V, W, M | Campos horizontales |
| 07 | `panel_niveles` | M por nivel Z | Estructura vertical |
| 10 | `perfil_vertical` | M por nivel Z | Estructura vertical |
| 04 | `hist_percentiles` | M | Estadística y tiempo |
| 08 | `uv_niveles` | U × V | Estadística y tiempo |
| 09 | `evolucion_temporal` | U, V, M | Estadística y tiempo |

Convenciones: U positivo hacia el este, V positivo hacia el norte, M = √(U² + V²), todo en m/s.
U, V y W usan la paleta divergente RdBu centrada en 0 (azul negativo, rojo positivo); M usa Viridis.
Las escalas de color son fijas entre niveles y pasos de tiempo para poder compararlos.

## Verlo en local

```bash
python -m http.server 8000
# abrir http://localhost:8000
```

Se necesita conexión a internet: Plotly 2.35.2 y los contornos de los mapas se cargan desde `cdn.plot.ly`.
Un enlace como `index.html#globo_tiempo` abre directamente esa gráfica.

## Regenerar las gráficas

Las gráficas originales se exportaron desde Python con `fig.write_html(include_plotlyjs="cdn")`
(el notebook no está en el repositorio). El script lee esos HTML originales, que siguen en el
historial de git (commit `9155d57`), y escribe `graficas/`:

```bash
pip install numpy
python tools/optimizar_graficas.py               # lee los originales del commit 9155d57
python tools/optimizar_graficas.py --origen DIR  # o de una carpeta con HTML nuevos
```

Qué hace, sin quitar puntos, niveles ni pasos de tiempo:

- Redondea coordenadas a 0,01° y valores a 4 cifras significativas.
- Quita de cada frame de animación las coordenadas que no cambian.
- Cambia el texto de tooltip precalculado por `hovertemplate` con coordenadas, variable y unidad.
- No guarda las flechas de dirección: `assets/grafica.js` las dibuja a partir de U y V con la misma geometría (tallo de 3°, punta de 0,8° a ±30°).
- Corrige W, que venía en la malla 90×90 mientras U y V están en 45×45 (la 90×90 tomada cada 2 puntos).
- Comprueba al final que cada gráfica conserva el mismo número de trazas, puntos y frames.

Si se vuelve a exportar una gráfica desde el notebook, basta con pasarla por el script.

## Pesos

| Gráfica | Antes | Ahora | Descarga con gzip |
| --- | --- | --- | --- |
| globo_tiempo | 20,49 MB | 0,95 MB | 0,34 MB |
| panel_niveles | 5,31 MB | 3,10 MB | 1,11 MB |
| Las 10 | 28,69 MB | 5,04 MB | ≈ 1,8 MB |
