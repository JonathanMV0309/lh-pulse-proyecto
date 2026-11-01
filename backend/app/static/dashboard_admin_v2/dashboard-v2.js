/* =========================================================
   L&H PULSE · DASHBOARD ADMINISTRATIVO V2
   Solo presentación: no realiza peticiones ni cambia datos.
========================================================= */

(function () {
    "use strict";

    const COLORS = {
        ink: "#202a2d",
        muted: "#6b6259",
        teal: "#0d5c75",
        tealDark: "#083f51",
        emerald: "#2d6a4f",
        gold: "#c5a880",
        goldBright: "#e0a96d",
        terracotta: "#d95d39",
        danger: "#a63d40",
        grid: "rgba(139, 125, 107, .13)"
    };

    const currency = new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 0
    });

    const compact = new Intl.NumberFormat("es-CO", {
        notation: "compact",
        maximumFractionDigits: 1
    });

    const number = new Intl.NumberFormat("es-CO", {
        maximumFractionDigits: 0
    });

    function readJSON(id) {
        const node = document.getElementById(id);
        if (!node) return {};
        try {
            return JSON.parse(node.textContent || "{}");
        } catch (error) {
            console.error(`No fue posible leer ${id}`, error);
            return {};
        }
    }

    function asNumber(value) {
        const result = Number(value);
        return Number.isFinite(result) ? result : 0;
    }

    function asPercent(value) {
        const result = asNumber(value);
        return Math.abs(result) <= 3 ? result * 100 : result;
    }

    function destroyChart(canvas) {
        if (!canvas || typeof Chart === "undefined") return;
        const current = Chart.getChart(canvas);
        if (current) current.destroy();
    }

    function chartFont(size, weight) {
        return {
            family: "Inter, system-ui, sans-serif",
            size: size || 11,
            weight: weight || "500"
        };
    }

    function baseTooltip(extra) {
        return Object.assign({
            backgroundColor: "rgba(32, 42, 45, .96)",
            titleColor: "#ffffff",
            bodyColor: "#f5f0e8",
            borderColor: "rgba(224, 169, 109, .45)",
            borderWidth: 1,
            padding: 13,
            cornerRadius: 11,
            displayColors: true,
            titleFont: chartFont(12, "700"),
            bodyFont: chartFont(11, "500")
        }, extra || {});
    }

    function horizontalOptions(valueFormatter) {
        return {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 850, easing: "easeOutQuart" },
            interaction: { mode: "nearest", axis: "y", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: baseTooltip({
                    callbacks: {
                        label: context => valueFormatter(context.parsed.x, context.dataIndex)
                    }
                })
            },
            scales: {
                x: {
                    beginAtZero: true,
                    border: { display: false },
                    grid: { color: COLORS.grid, drawTicks: false },
                    ticks: {
                        color: COLORS.muted,
                        font: chartFont(10),
                        padding: 8,
                        callback: value => compact.format(value)
                    }
                },
                y: {
                    border: { display: false },
                    grid: { display: false },
                    ticks: {
                        color: COLORS.ink,
                        font: chartFont(11, "650"),
                        autoSkip: false,
                        callback: function (value) {
                            const label = String(this.getLabelForValue(value));
                            return label.length > 21 ? `${label.slice(0, 20)}…` : label;
                        }
                    }
                }
            }
        };
    }

    const barValuePlugin = {
        id: "lhBarValues",
        afterDatasetsDraw(chart, args, opts) {
            if (!opts || opts.display === false) return;
            const { ctx } = chart;
            const meta = chart.getDatasetMeta(0);
            ctx.save();
            ctx.font = "700 10px Inter, system-ui, sans-serif";
            ctx.fillStyle = COLORS.ink;
            ctx.textBaseline = "middle";
            meta.data.forEach((bar, index) => {
                const raw = chart.data.datasets[0].data[index];
                const label = opts.formatter ? opts.formatter(raw) : String(raw);
                const width = ctx.measureText(label).width;
                const roomRight = chart.chartArea.right - bar.x;
                ctx.textAlign = roomRight > width + 12 ? "left" : "right";
                ctx.fillText(label, roomRight > width + 12 ? bar.x + 7 : bar.x - 7, bar.y);
            });
            ctx.restore();
        }
    };

    const complianceZones = {
        id: "lhComplianceZones",
        beforeDatasetsDraw(chart) {
            if (chart.canvas.id !== "cumplimientoChart") return;
            const scale = chart.scales.x;
            const area = chart.chartArea;
            if (!scale || !area) return;
            const zones = [
                [0, 75, "rgba(166, 61, 64, .045)"],
                [75, 90, "rgba(217, 93, 57, .045)"],
                [90, 100, "rgba(224, 169, 109, .07)"],
                [100, scale.max, "rgba(45, 106, 79, .055)"]
            ];
            const { ctx } = chart;
            ctx.save();
            zones.forEach(([from, to, color]) => {
                const left = Math.max(area.left, scale.getPixelForValue(from));
                const right = Math.min(area.right, scale.getPixelForValue(to));
                if (right > left) {
                    ctx.fillStyle = color;
                    ctx.fillRect(left, area.top, right - left, area.bottom - area.top);
                }
            });
            const target = scale.getPixelForValue(100);
            if (target >= area.left && target <= area.right) {
                ctx.strokeStyle = COLORS.emerald;
                ctx.lineWidth = 2;
                ctx.setLineDash([6, 5]);
                ctx.beginPath();
                ctx.moveTo(target, area.top);
                ctx.lineTo(target, area.bottom);
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.fillStyle = COLORS.emerald;
                ctx.font = "700 10px Inter, system-ui, sans-serif";
                ctx.textAlign = "right";
                ctx.fillText("META 100%", target - 6, area.top + 11);
            }
            ctx.restore();
        }
    };

    const doughnutCenter = {
        id: "lhDoughnutCenter",
        afterDraw(chart) {
            if (chart.config.type !== "doughnut") return;
            const meta = chart.getDatasetMeta(0);
            if (!meta.data.length) return;
            const { x, y } = meta.data[0];
            const total = chart.data.datasets[0].data.reduce((sum, value) => sum + asNumber(value), 0);
            const { ctx } = chart;
            ctx.save();
            ctx.textAlign = "center";
            ctx.fillStyle = COLORS.muted;
            ctx.font = "700 10px Inter, system-ui, sans-serif";
            ctx.fillText("VENTA TOTAL", x, y - 8);
            ctx.fillStyle = COLORS.ink;
            ctx.font = "800 17px Inter, system-ui, sans-serif";
            ctx.fillText(`$${compact.format(total)}`, x, y + 13);
            ctx.restore();
        }
    };

    function addInsights(ranking) {
        const firstCharts = document.querySelector(".charts-grid");
        if (!firstCharts || !ranking.length || document.querySelector(".v2-insight-strip")) return;

        const percentages = ranking.map(item => asPercent(item.cumplimiento_pct));
        const inGoal = percentages.filter(value => value >= 100).length;
        const close = percentages.filter(value => value >= 90 && value < 100).length;
        const critical = percentages.filter(value => value < 75).length;
        const strip = document.createElement("section");
        strip.className = "v2-insight-strip";
        strip.innerHTML = `
            <article class="v2-insight" style="--insight-color: rgba(45,106,79,.11)">
                <span class="v2-insight-label">Red saludable</span>
                <strong>${inGoal} tiendas en meta</strong>
                <small>Cumplimiento igual o superior al 100%</small>
            </article>
            <article class="v2-insight" style="--insight-color: rgba(224,169,109,.14)">
                <span class="v2-insight-label">Oportunidad inmediata</span>
                <strong>${close} cerca de la meta</strong>
                <small>Entre 90% y 99,9% de cumplimiento</small>
            </article>
            <article class="v2-insight" style="--insight-color: rgba(166,61,64,.10)">
                <span class="v2-insight-label">Atención prioritaria</span>
                <strong>${critical} tiendas críticas</strong>
                <small>Por debajo del 75% de cumplimiento</small>
            </article>`;
        firstCharts.parentNode.insertBefore(strip, firstCharts);
    }

    function addChartActions(panel, canvas, options) {
        const header = panel && panel.querySelector(".chart-header");
        if (!header || header.querySelector(".v2-chart-actions")) return;
        const actions = document.createElement("div");
        actions.className = "v2-chart-actions";

        if (options && options.segment) actions.appendChild(options.segment);

        const download = document.createElement("button");
        download.type = "button";
        download.className = "v2-chart-button";
        download.title = "Descargar gráfica como imagen";
        download.setAttribute("aria-label", "Descargar gráfica como imagen");
        download.innerHTML = '<i class="bi bi-download"></i>';
        download.addEventListener("click", () => {
            const link = document.createElement("a");
            link.download = `${canvas.id}.png`;
            link.href = canvas.toDataURL("image/png", 1);
            link.click();
        });
        actions.appendChild(download);
        header.appendChild(actions);
    }

    function makeSegment(items, onChange) {
        const segment = document.createElement("div");
        segment.className = "v2-segment";
        items.forEach((item, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = item.label;
            button.dataset.value = item.value;
            if (index === 0) button.classList.add("active");
            button.addEventListener("click", () => {
                segment.querySelectorAll("button").forEach(node => node.classList.remove("active"));
                button.classList.add("active");
                onChange(item.value);
            });
            segment.appendChild(button);
        });
        return segment;
    }

    function barColors(values, type) {
        return values.map(value => {
            if (type === "compliance") {
                if (value >= 100) return "rgba(45, 106, 79, .82)";
                if (value >= 90) return "rgba(224, 169, 109, .86)";
                if (value >= 75) return "rgba(217, 93, 57, .76)";
                return "rgba(166, 61, 64, .78)";
            }
            return "rgba(13, 92, 117, .82)";
        });
    }

    function createSalesChart(source, limit) {
        const canvas = document.getElementById("ventasChart");
        if (!canvas || !source.length) return;
        destroyChart(canvas);
        const rows = source.slice().sort((a, b) => asNumber(b.venta_actual) - asNumber(a.venta_actual));
        const data = limit === "all" ? rows : rows.slice(0, asNumber(limit));
        const values = data.map(item => asNumber(item.venta_actual));
        const wrapper = canvas.closest(".chart-wrapper");
        if (wrapper) wrapper.style.height = `${Math.max(390, Math.min(900, data.length * 34 + 85))}px`;

        const options = horizontalOptions((value, index) => {
            const compliance = asPercent(data[index] && data[index].cumplimiento_pct);
            return `${currency.format(value)} · Cumplimiento ${compliance.toFixed(1)}%`;
        });
        options.plugins.lhBarValues = { formatter: value => `$${compact.format(value)}` };

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: data.map((item, index) => `${index + 1}. ${item.nombre || "Sin nombre"}`),
                datasets: [{
                    data: values,
                    backgroundColor: values.map((value, index) => index < 3
                        ? ["rgba(224,169,109,.92)", "rgba(13,92,117,.82)", "rgba(217,93,57,.76)"][index]
                        : "rgba(13,92,117,.68)"),
                    borderColor: "rgba(255,255,255,.6)",
                    borderWidth: 1,
                    borderRadius: 9,
                    borderSkipped: false,
                    barPercentage: .72
                }]
            },
            options,
            plugins: [barValuePlugin]
        });
    }

    function createComplianceChart(source, filter) {
        const canvas = document.getElementById("cumplimientoChart");
        if (!canvas || !source.length) return;
        destroyChart(canvas);
        let rows = source.map(item => Object.assign({}, item, {
            pct: asPercent(item.cumplimiento_pct)
        }));
        if (filter === "goal") rows = rows.filter(item => item.pct >= 100);
        if (filter === "close") rows = rows.filter(item => item.pct >= 90 && item.pct < 100);
        if (filter === "critical") rows = rows.filter(item => item.pct < 75);
        rows.sort((a, b) => b.pct - a.pct);
        if (filter === "all") rows = rows.slice(0, 10);
        const values = rows.map(item => item.pct);
        const wrapper = canvas.closest(".chart-wrapper");
        if (wrapper) wrapper.style.height = `${Math.max(390, Math.min(900, rows.length * 34 + 85))}px`;

        const options = horizontalOptions(value => `${value.toFixed(1)}%`);
        options.scales.x.max = Math.max(110, Math.ceil((Math.max(...values, 100) + 8) / 10) * 10);
        options.scales.x.ticks.callback = value => `${value}%`;
        options.plugins.lhBarValues = { formatter: value => `${asNumber(value).toFixed(1)}%` };

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: rows.map(item => item.nombre || "Sin nombre"),
                datasets: [{
                    data: values,
                    backgroundColor: barColors(values, "compliance"),
                    borderRadius: 9,
                    borderSkipped: false,
                    barPercentage: .72
                }]
            },
            options,
            plugins: [complianceZones, barValuePlugin]
        });
    }

    function createCitiesChart(rows) {
        const canvas = document.getElementById("ciudadesGlobalChart");
        if (!canvas || !rows.length) return;
        destroyChart(canvas);
        const points = rows.map(item => ({
            x: asPercent(item.cumplimiento),
            y: asNumber(item.ventas),
            r: Math.max(7, Math.min(22, 6 + asNumber(item.tiendas) * 2.3)),
            ciudad: item.ciudad || "Sin ciudad",
            tiendas: asNumber(item.tiendas)
        }));

        new Chart(canvas, {
            type: "bubble",
            data: {
                datasets: [{
                    label: "Ciudades",
                    data: points,
                    backgroundColor: points.map(point => point.x >= 100
                        ? "rgba(45,106,79,.72)"
                        : point.x >= 90
                            ? "rgba(224,169,109,.78)"
                            : "rgba(217,93,57,.70)"),
                    borderColor: "rgba(255,255,255,.9)",
                    borderWidth: 2,
                    hoverBorderColor: COLORS.tealDark,
                    hoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 900, easing: "easeOutQuart" },
                plugins: {
                    legend: { display: false },
                    tooltip: baseTooltip({
                        callbacks: {
                            title: items => items[0].raw.ciudad,
                            label: context => [
                                `Ventas: ${currency.format(context.raw.y)}`,
                                `Cumplimiento: ${context.raw.x.toFixed(1)}%`,
                                `Tiendas: ${number.format(context.raw.tiendas)}`
                            ]
                        }
                    })
                },
                scales: {
                    x: {
                        title: { display: true, text: "Cumplimiento", color: COLORS.muted, font: chartFont(11, "700") },
                        grid: { color: COLORS.grid },
                        border: { display: false },
                        ticks: { color: COLORS.muted, callback: value => `${value}%` }
                    },
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: "Ventas", color: COLORS.muted, font: chartFont(11, "700") },
                        grid: { color: COLORS.grid },
                        border: { display: false },
                        ticks: { color: COLORS.muted, callback: value => `$${compact.format(value)}` }
                    }
                }
            }
        });
    }

    function createClimateChart(rows) {
        const canvas = document.getElementById("climasGlobalChart");
        if (!canvas || !rows.length) return;
        destroyChart(canvas);
        const palette = [COLORS.teal, COLORS.goldBright, COLORS.terracotta, COLORS.emerald, "#8b7d6b", "#557c83"];
        new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: rows.map(item => item.clima || "Sin clima"),
                datasets: [{
                    data: rows.map(item => asNumber(item.ventas)),
                    backgroundColor: rows.map((item, index) => palette[index % palette.length]),
                    borderColor: "#fdfbf7",
                    borderWidth: 4,
                    hoverOffset: 9,
                    spacing: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "66%",
                animation: { animateRotate: true, duration: 950 },
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { usePointStyle: true, pointStyle: "circle", padding: 18, color: COLORS.muted, font: chartFont(10, "650") }
                    },
                    tooltip: baseTooltip({
                        callbacks: {
                            label: context => {
                                const row = rows[context.dataIndex] || {};
                                return [
                                    `Ventas: ${currency.format(asNumber(row.ventas))}`,
                                    `Cumplimiento: ${asPercent(row.cumplimiento).toFixed(1)}%`,
                                    `Tiendas: ${number.format(asNumber(row.tiendas))}`
                                ];
                            }
                        }
                    })
                }
            },
            plugins: [doughnutCenter]
        });
    }

    function createLinesChart(rows) {
        const title = Array.from(document.querySelectorAll(".data-panel h3"))
            .find(node => node.textContent.includes("Ventas por línea"));
        const panel = title && title.closest(".data-panel");
        if (!panel || !rows.length || panel.querySelector("#lineasEvolutionChart")) return;

        const holder = document.createElement("div");
        holder.className = "v2-lines-chart";
        holder.innerHTML = '<canvas id="lineasEvolutionChart"></canvas>';
        const table = panel.querySelector(".table-container");
        panel.insertBefore(holder, table);

        const header = panel.querySelector(".data-header");
        if (header) {
            const toggle = document.createElement("button");
            toggle.type = "button";
            toggle.className = "v2-chart-button v2-table-toggle";
            toggle.innerHTML = '<i class="bi bi-table me-1"></i> Ocultar detalle';
            toggle.addEventListener("click", () => {
                panel.classList.toggle("v2-table-collapsed");
                const hidden = panel.classList.contains("v2-table-collapsed");
                toggle.innerHTML = hidden
                    ? '<i class="bi bi-table me-1"></i> Ver detalle'
                    : '<i class="bi bi-table me-1"></i> Ocultar detalle';
            });
            header.appendChild(toggle);
        }

        const ordered = rows.slice().sort((a, b) => asNumber(b.venta_2026) - asNumber(a.venta_2026));
        new Chart(document.getElementById("lineasEvolutionChart"), {
            type: "bar",
            data: {
                labels: ordered.map(item => item.linea || "Sin línea"),
                datasets: [
                    {
                        label: "Año anterior",
                        data: ordered.map(item => asNumber(item.venta_2025)),
                        backgroundColor: "rgba(139,125,107,.34)",
                        borderRadius: 7,
                        borderSkipped: false
                    },
                    {
                        label: "Año actual",
                        data: ordered.map(item => asNumber(item.venta_2026)),
                        backgroundColor: "rgba(13,92,117,.82)",
                        borderRadius: 7,
                        borderSkipped: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                animation: { duration: 900, easing: "easeOutQuart" },
                plugins: {
                    legend: { labels: { usePointStyle: true, color: COLORS.muted, font: chartFont(10, "650") } },
                    tooltip: baseTooltip({ callbacks: { label: context => `${context.dataset.label}: ${currency.format(context.parsed.y)}` } })
                },
                scales: {
                    x: { grid: { display: false }, border: { display: false }, ticks: { color: COLORS.muted, font: chartFont(10, "650") } },
                    y: { beginAtZero: true, grid: { color: COLORS.grid }, border: { display: false }, ticks: { color: COLORS.muted, callback: value => `$${compact.format(value)}` } }
                }
            }
        });
    }

    function initialize() {
        document.body.classList.add("dashboard-v2");
        if (typeof Chart === "undefined") {
            console.warn("Dashboard V2: Chart.js no está disponible.");
            return;
        }

        Chart.defaults.color = COLORS.muted;
        Chart.defaults.font.family = "Inter, system-ui, sans-serif";

        const base = readJSON("dashboard-data");
        const extra = readJSON("dashboard-v2-data");
        const ranking = Array.isArray(extra.ranking) ? extra.ranking : [];
        const salesSource = ranking.length ? ranking : (Array.isArray(base.topVentas) ? base.topVentas : []);
        const complianceSource = ranking.length ? ranking : (Array.isArray(base.topCumplimiento) ? base.topCumplimiento : []);

        addInsights(ranking);
        createSalesChart(salesSource, 10);
        createComplianceChart(complianceSource, "all");
        createCitiesChart(Array.isArray(base.rankingCiudades) ? base.rankingCiudades : []);
        createClimateChart(Array.isArray(base.resumenClimas) ? base.resumenClimas : []);
        createLinesChart(Array.isArray(extra.lineas) ? extra.lineas : []);

        const salesCanvas = document.getElementById("ventasChart");
        if (salesCanvas) {
            const segment = makeSegment([
                { label: "Top 10", value: 10 },
                { label: "Top 5", value: 5 },
                { label: "Todas", value: "all" }
            ], value => createSalesChart(salesSource, value));
            addChartActions(salesCanvas.closest(".chart-panel"), salesCanvas, { segment });
        }

        const complianceCanvas = document.getElementById("cumplimientoChart");
        if (complianceCanvas) {
            const segment = makeSegment([
                { label: "Top", value: "all" },
                { label: "En meta", value: "goal" },
                { label: "Cerca", value: "close" },
                { label: "Críticas", value: "critical" }
            ], value => createComplianceChart(complianceSource, value));
            addChartActions(complianceCanvas.closest(".chart-panel"), complianceCanvas, { segment });
        }

        ["ciudadesGlobalChart", "climasGlobalChart"].forEach(id => {
            const canvas = document.getElementById(id);
            if (canvas) addChartActions(canvas.closest(".chart-panel"), canvas);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        // Los gráficos clásicos se crean en otro listener. Este pequeño aplazamiento
        // permite destruirlos limpiamente y recrearlos sin usar dos veces el canvas.
        window.setTimeout(initialize, 80);
    });
})();
