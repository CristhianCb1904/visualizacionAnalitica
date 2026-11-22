
const dashboard = document.getElementById("dashboard");

const charts = document.querySelectorAll(".chart-card");

const resetButton = document.getElementById("resetDashboard");


// Guardar la tarjeta que inicia como principal
const initialMain = document.querySelector(".main-chart");


// Intercambiar gráfica principal
charts.forEach(chart => {

    chart.addEventListener("click", () => {

        // Ignorar clic si ya es la principal
        if (chart.classList.contains("main-chart")) {
            return;
        }

        // Obtener gráfica principal actual
        const currentMain = dashboard.querySelector(".main-chart");

        // Intercambiar posiciones
        currentMain.classList.remove("main-chart");

        chart.classList.add("main-chart");

    });

});


// Restaurar distribución inicial
resetButton.addEventListener("click", () => {

    const currentMain = dashboard.querySelector(".main-chart");

    if (currentMain) {
        currentMain.classList.remove("main-chart");
    }

    initialMain.classList.add("main-chart");

});
