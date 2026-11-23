/* =========================================
   DASHBOARD · TASK 1 (SciVis Contest 2026)
   Navegación por grupos, visor con estados
   de carga/error y enlaces directos (#id).
========================================= */

const VISUALIZACIONES = [
    {
        id: "globo_presion", numero: "01", grupo: "global",
        titulo: "Circulación por nivel de presión",
        descripcion: "Magnitud y dirección del viento sobre el globo en tres niveles de presión (769, 822 y 876 hPa). El menú cambia entre M, U, V y flechas.",
        variables: ["U", "V", "M", "p"], vista: "Globo", peso: 0.02
    },
    {
        id: "globo_tiempo", numero: "03", grupo: "global",
        titulo: "Evolución temporal en el globo",
        descripcion: "Magnitud y dirección del viento en 21 pasos de tiempo de la simulación. Pulsa ▶ para animar o usa el deslizador.",
        variables: ["U", "V", "M"], vista: "Globo animado", peso: 0.34
    },
    {
        id: "mapa_presion", numero: "05", grupo: "horizontal",
        titulo: "Mapa de viento por nivel de presión",
        descripcion: "Mapa global de U, V, M y W en tres niveles de presión. U, V y W usan una paleta divergente: azul negativo, rojo positivo.",
        variables: ["U", "V", "W", "M", "p"], vista: "Mapa", peso: 0.09
    },
    {
        id: "mapa_uv_mag", numero: "06", grupo: "horizontal",
        titulo: "Mapas de U, V y M",
        descripcion: "Componentes horizontales y magnitud en la malla completa de 90 × 90 puntos.",
        variables: ["U", "V", "M"], vista: "Mapa de calor", peso: 0.06
    },
    {
        id: "capas_uvw", numero: "02", grupo: "horizontal",
        titulo: "Componentes U, V, W por nivel",
        descripcion: "Mapas de U, V, W y M en los niveles Z = 40, 41 y 42 (≈ 769, 822 y 876 hPa).",
        variables: ["U", "V", "W", "M"], vista: "Mapa de calor", peso: 0.09
    },
    {
        id: "panel_niveles", numero: "07", grupo: "vertical",
        titulo: "M por nivel vertical",
        descripcion: "Mapa e histograma de la magnitud M en 11 niveles verticales y 21 pasos de tiempo. Elige el nivel en el menú.",
        variables: ["M", "Z"], vista: "Mapa + histograma animado", peso: 1.11
    },
    {
        id: "perfil_vertical", numero: "10", grupo: "vertical",
        titulo: "Perfil vertical de M",
        descripcion: "Magnitud media del viento en cada uno de los 52 niveles verticales del modelo (51 = superficie).",
        variables: ["M", "Z"], vista: "Perfil", peso: 0.01
    },
    {
        id: "hist_percentiles", numero: "04", grupo: "estadistica",
        titulo: "Distribución de M y percentiles",
        descripcion: "Histograma de la magnitud M en superficie (Z = 51) con P25, mediana, P75 y P99 en cada paso de tiempo.",
        variables: ["M"], vista: "Histograma animado", peso: 0.01
    },
    {
        id: "uv_niveles", numero: "08", grupo: "estadistica",
        titulo: "Distribución conjunta U × V",
        descripcion: "Histograma 2D de U frente a V por nivel vertical: qué combinaciones de dirección y velocidad son más frecuentes.",
        variables: ["U", "V", "Z"], vista: "Histograma 2D", peso: 0.02
    },
    {
        id: "evolucion_temporal", numero: "09", grupo: "estadistica",
        titulo: "Evolución de U, V y M",
        descripcion: "Media espacial de U, V y M a lo largo de 21 pasos de tiempo en superficie (Z = 51).",
        variables: ["U", "V", "M"], vista: "Serie temporal", peso: 0.01
    }
];

const GRUPOS = [
    { id: "global", nombre: "Vista global", pregunta: "¿Cómo circula el viento sobre el planeta?" },
    { id: "horizontal", nombre: "Campos horizontales", pregunta: "¿Dónde están los máximos y el signo de cada componente?" },
    { id: "vertical", nombre: "Estructura vertical", pregunta: "¿Cómo cambia el viento con la altura?" },
    { id: "estadistica", nombre: "Estadística y tiempo", pregunta: "¿Qué tan variable es y cómo evoluciona?" }
];

const TIEMPO_MAXIMO_MS = 20000;

const $ = (id) => document.getElementById(id);
const marco = $("marcoPrincipal");
const capa = $("capaEstado");
const textoEstado = $("textoEstado");
const accionesEstado = $("accionesEstado");

let activa = null;
let temporizador = null;


/* =========================================
   GALERÍA
========================================= */

function crearGaleria() {
    const contenedor = $("grupos");

    GRUPOS.forEach((grupo) => {
        const seccion = document.createElement("section");
        seccion.className = "grupo";
        seccion.setAttribute("aria-labelledby", `grupo-${grupo.id}`);
        seccion.innerHTML = `
            <h3 id="grupo-${grupo.id}">${grupo.nombre}</h3>
            <p class="grupo-pregunta">${grupo.pregunta}</p>
            <div class="tarjetas"></div>`;

        const lista = seccion.querySelector(".tarjetas");

        VISUALIZACIONES.filter((v) => v.grupo === grupo.id).forEach((v) => {
            const boton = document.createElement("button");
            boton.type = "button";
            boton.className = "tarjeta";
            boton.dataset.id = v.id;
            boton.setAttribute("aria-pressed", "false");
            boton.innerHTML = `
                <span class="tarjeta-numero">${v.numero}</span>
                <span class="tarjeta-titulo">${v.titulo}</span>
                <span class="tarjeta-meta">${v.vista} · ${v.variables.join(", ")}</span>`;
            boton.addEventListener("click", () => {
                seleccionar(v.id, { desplazar: true });
                history.replaceState(null, "", `#${v.id}`);
            });
            lista.appendChild(boton);
        });

        contenedor.appendChild(seccion);
    });
}


/* =========================================
   ESTADOS DEL VISOR
========================================= */

function formatoPeso(mb) {
    return mb < 0.1 ? `≈ ${Math.max(1, Math.round(mb * 1000))} kB` : `≈ ${mb.toFixed(2).replace(".", ",")} MB`;
}

function mostrarCargando(v) {
    clearTimeout(temporizador);
    capa.hidden = false;
    capa.classList.remove("error");
    accionesEstado.hidden = true;
    textoEstado.textContent = `Cargando ${v.numero} · ${v.titulo} (${formatoPeso(v.peso)})…`;

    temporizador = setTimeout(() => {
        mostrarError("La gráfica está tardando más de lo normal. Revisa la conexión o ábrela en una pestaña nueva.");
    }, TIEMPO_MAXIMO_MS);
}

function mostrarLista() {
    clearTimeout(temporizador);
    capa.hidden = true;
}

function mostrarError(mensaje) {
    clearTimeout(temporizador);
    capa.hidden = false;
    capa.classList.add("error");
    textoEstado.textContent = mensaje;
    accionesEstado.hidden = false;
}

// Cada gráfica avisa con postMessage cuando Plotly termina de dibujar.
window.addEventListener("message", (evento) => {
    const datos = evento.data;
    if (!datos || datos.origen !== "grafica" || evento.source !== marco.contentWindow) {
        return;
    }
    if (datos.tipo === "lista") {
        mostrarLista();
    } else if (datos.tipo === "error") {
        mostrarError(datos.detalle);
    }
});

// Respaldo por si la gráfica se abre sin el aviso (p. ej. archivo antiguo).
marco.addEventListener("load", () => {
    setTimeout(() => {
        if (!capa.classList.contains("error") && !capa.hidden) {
            try {
                if (marco.contentDocument && !marco.contentDocument.getElementById("estado")) {
                    mostrarLista();
                }
            } catch (e) {
                mostrarLista();
            }
        }
    }, 300);
});


/* =========================================
   SELECCIÓN
========================================= */

function seleccionar(id, opciones = {}) {
    const v = VISUALIZACIONES.find((item) => item.id === id) || VISUALIZACIONES[0];
    const ruta = `graficas/${v.id}.html`;
    const grupo = GRUPOS.find((g) => g.id === v.grupo);

    if (activa !== v.id || opciones.forzar) {
        mostrarCargando(v);
        marco.src = ruta;
    }
    activa = v.id;

    $("grupoActivo").textContent = grupo.nombre;
    $("tituloActivo").textContent = `${v.numero} · ${v.titulo}`;
    $("descripcionActiva").textContent = v.descripcion;
    $("pesoActivo").textContent = formatoPeso(v.peso);
    $("abrirNueva").href = ruta;
    $("abrirEstado").href = ruta;
    marco.title = `${v.numero} · ${v.titulo}`;
    document.title = `${v.numero} · ${v.titulo} | Task 1 · SciVis Contest 2026`;

    $("chipsActivos").innerHTML = v.variables.map((x) => `<li>${x}</li>`).join("");

    document.querySelectorAll(".tarjeta").forEach((t) => {
        const es = t.dataset.id === v.id;
        t.classList.toggle("activa", es);
        t.setAttribute("aria-pressed", String(es));
    });

    if (opciones.desplazar && window.matchMedia("(max-width: 1100px)").matches) {
        $("visor").scrollIntoView({ behavior: preferirMovimiento() ? "smooth" : "auto", block: "start" });
    }
}

function preferirMovimiento() {
    return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function idDesdeHash() {
    const id = decodeURIComponent(location.hash.replace("#", ""));
    return VISUALIZACIONES.some((v) => v.id === id) ? id : null;
}


/* =========================================
   INICIALIZACIÓN
========================================= */

crearGaleria();

$("reintentar").addEventListener("click", () => seleccionar(activa, { forzar: true }));

$("pantallaCompleta").addEventListener("click", () => {
    const el = $("contenedorVisor");
    if (el.requestFullscreen) {
        el.requestFullscreen();
    } else if (el.webkitRequestFullscreen) {
        el.webkitRequestFullscreen();
    }
});

window.addEventListener("hashchange", () => {
    const id = idDesdeHash();
    if (id) {
        seleccionar(id);
    }
});

// El iframe del HTML ya apunta a la primera gráfica; si el enlace trae otra, se cambia.
const inicial = idDesdeHash() || VISUALIZACIONES[0].id;
activa = VISUALIZACIONES[0].id;
mostrarCargando(VISUALIZACIONES[0]);
seleccionar(inicial);

console.info(`Dashboard Task 1 listo · ${VISUALIZACIONES.length} visualizaciones`);
