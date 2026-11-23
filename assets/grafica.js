/* =========================================================
   Renderizador común de las gráficas del dashboard (Task 1)
   - Lee la figura Plotly incrustada en <script id="figura">.
   - Reconstruye las flechas de dirección a partir de U y V.
   - Ajusta márgenes y textos en pantallas pequeñas.
   - Avisa a la página principal cuando la gráfica está lista.
========================================================= */
(function () {
    "use strict";

    var estado = document.getElementById("estado");
    var div = document.getElementById("grafica");

    function avisarPadre(tipo, detalle) {
        if (window.parent && window.parent !== window) {
            window.parent.postMessage({ origen: "grafica", tipo: tipo, detalle: detalle || "" }, "*");
        }
    }

    function mostrarError(mensaje) {
        if (estado) {
            estado.textContent = mensaje;
            estado.classList.add("error");
        }
        console.error("[grafica] " + mensaje);
        avisarPadre("error", mensaje);
    }

    if (!window.Plotly) {
        mostrarError("No se pudo cargar Plotly desde cdn.plot.ly. Revisa la conexión y recarga.");
        return;
    }

    var fig;
    try {
        fig = JSON.parse(document.getElementById("figura").textContent);
    } catch (e) {
        mostrarError("Los datos de la gráfica están dañados.");
        return;
    }

    /* ---------------------------------------------------------
       Flechas de dirección (misma geometría que las originales):
       tallo de longitud fija "largo" (grados) en la dirección (U, V)
       y dos segmentos de punta de "punta" grados a ±"angulo" grados.
    --------------------------------------------------------- */
    function flechas(lat, lon, u, v, cfg) {
        var n = lat.length;
        var la = new Array(n * 9);
        var lo = new Array(n * 9);
        var g1 = cfg.angulo * Math.PI / 180;
        for (var i = 0; i < n; i++) {
            var k = i * 9;
            var m = Math.hypot(u[i], v[i]);
            if (!(m > 0)) {
                for (var j = 0; j < 9; j++) { la[k + j] = null; lo[k + j] = null; }
                continue;
            }
            var a = Math.atan2(v[i], u[i]);
            var lat1 = lat[i] + cfg.largo * v[i] / m;
            var lon1 = lon[i] + cfg.largo * u[i] / m;
            la[k] = lat[i]; lo[k] = lon[i];
            la[k + 1] = lat1; lo[k + 1] = lon1;
            la[k + 2] = null; lo[k + 2] = null;
            la[k + 3] = lat1; lo[k + 3] = lon1;
            la[k + 4] = lat1 + cfg.punta * Math.sin(a + g1);
            lo[k + 4] = lon1 + cfg.punta * Math.cos(a + g1);
            la[k + 5] = null; lo[k + 5] = null;
            la[k + 6] = lat1; lo[k + 6] = lon1;
            la[k + 7] = lat1 + cfg.punta * Math.sin(a - g1);
            lo[k + 7] = lon1 + cfg.punta * Math.cos(a - g1);
            la[k + 8] = null; lo[k + 8] = null;
        }
        return { lat: la, lon: lo };
    }

    function construirFlechas(f) {
        var c = f.flechas;
        var base = f.data[c.base];
        var estados = [f.data].concat((f.frames || []).map(function (fr) { return fr.data; }));
        estados.forEach(function (trazas) {
            var r = flechas(base.lat, base.lon, trazas[c.u].marker.color, trazas[c.v].marker.color, c);
            trazas[c.traza].lat = r.lat;
            trazas[c.traza].lon = r.lon;
        });
    }

    if (fig.flechas) {
        construirFlechas(fig);
    }

    /* ---------------------------------------------------------
       Modo compacto para móviles
    --------------------------------------------------------- */
    var compacto = null;
    var tiposOriginales = [];

    function ajustesTamano(esCompacto) {
        return esCompacto
            ? { "margin.l": 44, "margin.r": 8, "margin.t": 84, "margin.b": 70, "title.font.size": 12, "font.size": 10 }
            : { "margin.l": 64, "margin.r": 24, "margin.t": 96, "margin.b": 90, "title.font.size": 15, "font.size": 12 };
    }

    function aplicarTamano(inicial) {
        var es = div.clientWidth < 640;
        if (es === compacto) { return; }
        compacto = es;
        document.body.classList.toggle("compacto", es);
        var cambios = ajustesTamano(es);
        // En pantallas estrechas, las filas de 3-4 botones pasan a menú desplegable.
        (fig.layout.updatemenus || []).forEach(function (m, i) {
            if (m.buttons && m.buttons.length > 2 && m.buttons[0].method !== "animate") {
                if (tiposOriginales[i] === undefined) { tiposOriginales[i] = m.type || "buttons"; }
                if (tiposOriginales[i] === "buttons") {
                    cambios["updatemenus[" + i + "].type"] = es ? "dropdown" : "buttons";
                    cambios["updatemenus[" + i + "].direction"] = es ? "down" : "right";
                }
            }
        });
        // En móvil las etiquetas de los pasos no caben: se ocultan (el valor actual se sigue mostrando).
        (fig.layout.sliders || []).forEach(function (sl, i) {
            cambios["sliders[" + i + "].font.color"] = es ? "rgba(0,0,0,0)" : "#cbd5e1";
        });
        if (fig.layout.geo) {
            cambios["margin.l"] = 0;
            cambios["margin.r"] = es ? 0 : 10;
        }
        if (inicial) {
            Object.keys(cambios).forEach(function (ruta) {
                var partes = ruta.replace(/\[(\d+)\]/g, ".$1").split(".");
                var obj = fig.layout;
                for (var i = 0; i < partes.length - 1; i++) {
                    obj[partes[i]] = obj[partes[i]] || {};
                    obj = obj[partes[i]];
                }
                obj[partes[partes.length - 1]] = cambios[ruta];
            });
        } else {
            Plotly.relayout(div, cambios);
        }
    }

    aplicarTamano(true);

    var config = {
        responsive: true,
        displaylogo: false,
        scrollZoom: false,
        modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
        toImageButtonOptions: { format: "png", scale: 2, filename: document.title }
    };

    Plotly.newPlot(div, fig.data, fig.layout, config)
        .then(function () {
            if (fig.frames && fig.frames.length) {
                return Plotly.addFrames(div, fig.frames);
            }
        })
        .then(function () {
            if (estado) { estado.remove(); }
            avisarPadre("lista", document.title);
        })
        .catch(function (e) {
            mostrarError("No se pudo dibujar la gráfica: " + (e && e.message ? e.message : e));
        });

    var espera;
    window.addEventListener("resize", function () {
        clearTimeout(espera);
        espera = setTimeout(function () { aplicarTamano(false); }, 150);
    });
})();
