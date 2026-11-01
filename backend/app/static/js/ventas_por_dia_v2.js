(function () {
    "use strict";

    function formatoDinero(valor) {
        return new Intl.NumberFormat("es-CO", {
            style: "currency",
            currency: "COP",
            maximumFractionDigits: 0
        }).format(Number(valor || 0));
    }

    function colorTooltip(context) {
        var etiqueta = context.dataset.label || "";
        var valor = Number(context.parsed.y || 0);
        if (etiqueta.toLowerCase().indexOf("unidad") >= 0) {
            return etiqueta + ": " + valor.toLocaleString("es-CO");
        }
        return etiqueta + ": " + formatoDinero(valor);
    }

    document.addEventListener("DOMContentLoaded", function () {
        var datos = window.ventasDiariasV2 || {};
        var diasTienda = Array.isArray(datos.diasTienda) ? datos.diasTienda : [];
        var diasGlobal = Array.isArray(datos.diasGlobal) ? datos.diasGlobal : [];

        document.querySelectorAll("[data-vd-panel]").forEach(function (boton) {
            boton.addEventListener("click", function () {
                var panel = boton.getAttribute("data-vd-panel");
                document.querySelectorAll("[data-vd-panel]").forEach(function (item) {
                    item.classList.toggle("active", item === boton);
                });
                document.querySelectorAll("[data-vd-content]").forEach(function (item) {
                    item.classList.toggle(
                        "active",
                        item.getAttribute("data-vd-content") === panel
                    );
                });
            });
        });

        var panelInicial = String(datos.panelInicial || "resumen");
        var botonInicial = document.querySelector('[data-vd-panel="' + panelInicial + '"]');
        if (botonInicial) botonInicial.click();

        var buscador = document.getElementById("vdTableSearch");
        var tabla = document.getElementById("vdDetailTable");
        if (buscador && tabla) {
            buscador.addEventListener("input", function () {
                var termino = buscador.value.toLocaleLowerCase("es").trim();
                tabla.querySelectorAll("tbody tr").forEach(function (fila) {
                    fila.style.display = fila.textContent
                        .toLocaleLowerCase("es")
                        .includes(termino) ? "" : "none";
                });
            });
        }

        if (typeof Chart === "undefined") {
            return;
        }

        Chart.defaults.color = "#746b61";
        Chart.defaults.font.family = "Montserrat, system-ui, sans-serif";

        var ritmoCanvas = document.getElementById("vdRitmoChart");
        var ritmoChart = null;

        function valoresRitmo(metrica) {
            if (diasTienda.length) {
                return {
                    labels: diasTienda.map(function (item) { return item.dia; }),
                    values: diasTienda.map(function (item) { return Number(item[metrica] || 0); }),
                    previous: diasTienda.map(function (item) {
                        return item.venta_anterior === null || item.venta_anterior === undefined
                            ? null
                            : Number(item.venta_anterior);
                    })
                };
            }
            return {
                labels: diasGlobal.map(function (item) { return item.dia; }),
                values: diasGlobal.map(function (item) {
                    return metrica === "unidades" ? 0 : Number(item.venta_2026 || 0);
                }),
                previous: diasGlobal.map(function (item) {
                    return metrica === "unidades" ? null : Number(item.venta_2025 || 0);
                })
            };
        }

        function dibujarRitmo(metrica) {
            if (!ritmoCanvas) return;
            var serie = valoresRitmo(metrica);
            if (ritmoChart) ritmoChart.destroy();

            var contexto = ritmoCanvas.getContext("2d");
            var relleno = contexto.createLinearGradient(0, 0, 0, 300);
            relleno.addColorStop(0, metrica === "venta" ? "rgba(13,92,117,.30)" : "rgba(217,93,57,.27)");
            relleno.addColorStop(1, "rgba(255,255,255,0)");

            var anioActual = Number(datos.anio || new Date().getFullYear());
            var datasets = [{
                label: metrica === "venta" ? "Ventas " + anioActual : "Unidades",
                data: serie.values,
                borderColor: metrica === "venta" ? "#0d5c75" : "#d95d39",
                backgroundColor: relleno,
                borderWidth: 3,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: "#fdfbf7",
                pointBorderWidth: 2,
                tension: .35,
                fill: true
            }];

            if (metrica === "venta" && serie.previous.some(function (valor) { return valor !== null; })) {
                datasets.unshift({
                    label: "Ventas " + (anioActual - 1),
                    data: serie.previous,
                    borderColor: "#8b7d6b",
                    backgroundColor: "rgba(139,125,107,.05)",
                    borderWidth: 2,
                    borderDash: [6, 5],
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    pointBackgroundColor: "#fdfbf7",
                    pointBorderWidth: 2,
                    tension: .35,
                    fill: false,
                    spanGaps: false
                });
            }

            ritmoChart = new Chart(ritmoCanvas, {
                type: "line",
                data: {
                    labels: serie.labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: {
                            display: metrica === "venta" && datasets.length > 1,
                            labels: { usePointStyle: true, boxWidth: 8 }
                        },
                        tooltip: { callbacks: { label: colorTooltip } }
                    },
                    scales: {
                        x: { grid: { display: false }, title: { display: true, text: "Día del mes" } },
                        y: {
                            beginAtZero: true,
                            grid: { color: "rgba(139,125,107,.10)" },
                            ticks: {
                                callback: function (valor) {
                                    if (metrica === "unidades") return Number(valor).toLocaleString("es-CO");
                                    return "$" + (Number(valor) / 1000000).toLocaleString("es-CO", { maximumFractionDigits: 1 }) + "M";
                                }
                            }
                        }
                    }
                }
            });
        }

        document.querySelectorAll("[data-vd-metric]").forEach(function (boton) {
            boton.addEventListener("click", function () {
                document.querySelectorAll("[data-vd-metric]").forEach(function (item) {
                    item.classList.toggle("active", item === boton);
                });
                dibujarRitmo(boton.getAttribute("data-vd-metric"));
            });
        });
        dibujarRitmo("venta");

        var comparativoCanvas = document.getElementById("vdComparativoChart");
        if (comparativoCanvas && diasGlobal.length) {
            new Chart(comparativoCanvas, {
                type: "bar",
                data: {
                    labels: diasGlobal.map(function (item) { return item.dia; }),
                    datasets: [
                        {
                            label: "2025",
                            data: diasGlobal.map(function (item) { return Number(item.venta_2025 || 0); }),
                            backgroundColor: "rgba(139,125,107,.45)",
                            borderColor: "#8b7d6b",
                            borderWidth: 1,
                            borderRadius: 7
                        },
                        {
                            label: "2026",
                            data: diasGlobal.map(function (item) { return Number(item.venta_2026 || 0); }),
                            backgroundColor: "rgba(13,92,117,.72)",
                            borderColor: "#0d5c75",
                            borderWidth: 1,
                            borderRadius: 7
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: { labels: { usePointStyle: true, boxWidth: 8 } },
                        tooltip: { callbacks: { label: colorTooltip } }
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: {
                            beginAtZero: true,
                            grid: { color: "rgba(139,125,107,.10)" },
                            ticks: {
                                callback: function (valor) {
                                    return "$" + (Number(valor) / 1000000).toLocaleString("es-CO", { maximumFractionDigits: 1 }) + "M";
                                }
                            }
                        }
                    }
                }
            });
        }
    });
})();
