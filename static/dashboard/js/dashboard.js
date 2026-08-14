document.addEventListener("DOMContentLoaded", () => {
    if (!window.Chart) return;
    const parseData = (id) => {
        const element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : [];
    };
    const categories = parseData("dashboard-categories-data");
    const states = parseData("dashboard-status-data");
    const common = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 350 },
        plugins: { legend: { display: false } },
    };
    const categoryCanvas = document.getElementById("categories-chart");
    if (categoryCanvas && categories.length) new Chart(categoryCanvas, {
        type: "bar",
        data: {
            labels: categories.map((item) => item.tipo__categoria__nombre),
            datasets: [{ data: categories.map((item) => item.total), backgroundColor: "#b5121b", borderRadius: 5 }],
        },
        options: { ...common, indexAxis: "y", scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } } },
    });
    const statusCanvas = document.getElementById("status-chart");
    if (statusCanvas && states.length) new Chart(statusCanvas, {
        type: "doughnut",
        data: {
            labels: states.map((item) => item.nombre),
            datasets: [{ data: states.map((item) => item.total), backgroundColor: ["#13866f", "#b56a00", "#dc0014", "#667085"], borderWidth: 0 }],
        },
        options: { ...common, cutout: "68%", plugins: { legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true } } } },
    });
});
