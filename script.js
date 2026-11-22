
/* =========================================
   ELEMENTOS DEL DASHBOARD
========================================= */

// Tarjetas de visualización
const cards = document.querySelectorAll(".chart-card");

// Iframe principal
const mainFrame = document.getElementById("mainFrame");

// Título del visor
const activeTitle = document.getElementById("activeTitle");

// Descripción del visor
const activeDescription =
    document.getElementById("activeDescription");


/* =========================================
   CAMBIAR VISUALIZACIÓN PRINCIPAL
========================================= */

cards.forEach(card => {

    card.addEventListener("click", () => {

        // Obtener información de la tarjeta
        const src = card.dataset.src;

        const title = card.dataset.title;

        const description = card.dataset.description;


        // Cambiar la gráfica principal
        mainFrame.src = src;


        // Actualizar título
        activeTitle.textContent = title;


        // Actualizar descripción
        activeDescription.textContent = description;


        // Quitar selección anterior
        cards.forEach(item => {

            item.classList.remove("active");

        });


        // Resaltar tarjeta seleccionada
        card.classList.add("active");

    });

});


/* =========================================
   INICIALIZACIÓN
========================================= */

console.log("Dashboard DYAMOND GEOS iniciado correctamente.");
console.log("Visualizaciones disponibles:", cards.length);
