/* =========================================================
   L&H PULSE - Gráficas premium del administrador (V2)
   1. Ventas por clima: dona que se dibuja por partes y una
      tarjeta por clima con su cielo animado.
   2. Top cumplimiento: un velocímetro por tienda; responde a
      los botones Top / En meta / Cerca / Críticas del V2.

   Solo presentación: usa los mismos datos de la página. Si algo
   falla, se deja visible la gráfica original de Chart.js.
   ========================================================= */
(function () {
    "use strict";

    var REDUCE = false /* Las animaciones se muestran siempre, aunque Windows tenga apagadas las animaciones. */;
    var HAS_IO = "IntersectionObserver" in window;

    function readJSON(id) {
        var node = document.getElementById(id);
        if (!node) return {};
        try { return JSON.parse(node.textContent || "{}"); } catch (e) { return {}; }
    }

    function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }
    function asPercent(v) { var n = num(v); return Math.abs(n) <= 3 ? n * 100 : n; }
    function ease(t) { return 1 - Math.pow(1 - t, 3); }
    function money(v) {
        v = num(v);
        if (Math.abs(v) >= 1e9) return "$" + (v / 1e9).toFixed(2).replace(".", ",") + "B";
        if (Math.abs(v) >= 1e6) return "$" + Math.round(v / 1e6) + "M";
        return "$" + Math.round(v).toLocaleString("es-CO");
    }
    function pct(v) { return num(v).toFixed(1).replace(".", ",") + "%"; }
    function escapeHtml(t) {
        return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }
    function statusColor(p) { return p >= 100 ? "#2d6a4f" : p >= 90 ? "#e0a96d" : p >= 75 ? "#d95d39" : "#a63d40"; }

    // Cuenta por tiempo real (se ve igual en un PC lento).
    function countTo(node, target, dur, format) {
        if (REDUCE) { node.textContent = format(target); return; }
        var start = performance.now();
        var step = function () {
            var t = Math.min((performance.now() - start) / dur, 1);
            node.textContent = format(target * ease(t));
            if (t < 1) setTimeout(step, 33);
        };
        step();
    }

    // Ejecuta una vez al aparecer; red de seguridad si el observador no responde.
    function onVisible(node, cb) {
        if (!HAS_IO || REDUCE) { cb(); return; }
        var done = false, alive = false;
        var run = function () { if (!done) { done = true; obs.disconnect(); cb(); } };
        var obs = new IntersectionObserver(function (entries) {
            alive = true;
            if (entries.some(function (e) { return e.isIntersecting; })) run();
        }, { threshold: 0.15 });
        obs.observe(node);
        setTimeout(function () { if (!alive) run(); }, 1500);
    }

    function pauseOffscreen(node) {
        if (!HAS_IO) return;
        new IntersectionObserver(function (entries) {
            node.classList.toggle("gp-paused", !entries[0].isIntersecting);
        }).observe(node);
    }

    // Reemplaza el contenido visual de un panel conservando su encabezado.
    function takeOver(canvasId) {
        var canvas = document.getElementById(canvasId);
        var panel = canvas && canvas.closest(".chart-panel");
        var wrapper = canvas && canvas.closest(".chart-wrapper");
        if (!panel || !wrapper) return null;
        var box = document.createElement("div");
        box.className = "gp-wrap";
        wrapper.parentNode.insertBefore(box, wrapper.nextSibling);
        // El botón de descarga exporta el canvas original, que ya no se ve.
        var download = panel.querySelector('.v2-chart-button[title*="Descargar"]');
        if (download) download.style.display = "none";
        wrapper.style.display = "none";
        return { panel: panel, wrapper: wrapper, box: box, restore: function () { box.remove(); wrapper.style.display = ""; if (download) download.style.display = ""; } };
    }

    // -----------------------------------------------------
    // 1. Ventas por clima
    // -----------------------------------------------------
    var CLIMAS = [
        { re: /CAL|CALID/i, key: "calido", color: "#e8772e" },
        { re: /FR[IÍ]/i, key: "frio", color: "#0d5c75" },
        { re: /TEMPL/i, key: "templado", color: "#2d6a4f" },
        { re: /COST|MAR|PLAY|TROP/i, key: "costero", color: "#3fa0b8" },
    ];

    function climaTipo(nombre) {
        var n = String(nombre || "");
        for (var i = 0; i < CLIMAS.length; i++) if (CLIMAS[i].re.test(n)) return CLIMAS[i];
        return { key: "otro", color: "#8b7d6b" };
    }

    function cielo(key) {
        var html = "", j;
        if (key === "calido") html = '<div class="gp-sun"></div>';
        if (key === "templado") {
            for (j = 0; j < 3; j++) html += '<div class="gp-cloud" style="top:' + (14 + j * 22) + "px;width:" + (48 + j * 14) +
                "px;animation-duration:" + (9 + j * 4) + "s;animation-delay:" + (-j * 3) + 's"></div>';
        }
        if (key === "frio") {
            for (j = 0; j < 11; j++) html += '<span class="gp-flake" style="left:' + (j * 9) + "%;animation-duration:" + (3 + j % 4) +
                "s;animation-delay:" + (-j * .6) + 's">❄</span>';
        }
        if (key === "costero") html = '<div class="gp-wave"></div><div class="gp-wave" style="bottom:12px;opacity:.6;animation-duration:6s"></div>' +
            '<div class="gp-sun" style="width:32px;height:32px;opacity:.85"></div>';
        if (key === "otro") {
            for (j = 0; j < 3; j++) html += '<div class="gp-wind" style="top:' + (24 + j * 26) + "px;animation-delay:" + (-j * 1.1) + 's"></div>';
        }
        return html;
    }

    function ventasPorClima(rows) {
        rows = (rows || []).filter(function (r) { return num(r.ventas) > 0; });
        if (!rows.length) return;
        var slot = takeOver("climasGlobalChart");
        if (!slot) return;
        try {
            var total = rows.reduce(function (s, r) { return s + num(r.ventas); }, 0);
            var data = rows.map(function (r) {
                var tipo = climaTipo(r.clima);
                return { nombre: r.clima || "Sin clima", ventas: num(r.ventas), share: num(r.ventas) / total,
                    cump: asPercent(r.cumplimiento), tiendas: num(r.tiendas), tipo: tipo };
            });
            var maxShare = Math.max.apply(null, data.map(function (d) { return d.share; }));
            slot.box.innerHTML =
                '<div class="gp-donut-row"><canvas class="gp-donut" width="340" height="340" role="img" aria-label="Participación de la venta por clima"></canvas>' +
                '<div class="gp-legend">' + data.map(function (d) {
                    return '<span><span><i style="background:' + d.tipo.color + '"></i>' + escapeHtml(d.nombre) + "</span><b>" +
                        Math.round(d.share * 100) + "%</b></span>";
                }).join("") + "</div></div>" +
                '<div class="gp-climates">' + data.map(function (d) {
                    return '<div class="gp-cl gp-' + d.tipo.key + '"><div class="gp-sky">' + cielo(d.tipo.key) + "</div>" +
                        '<div class="gp-info"><small>' + escapeHtml(String(d.nombre).toUpperCase()) + "</small><b>$0</b>" +
                        '<div class="gp-share"><i></i></div><div class="gp-meta">' + Math.round(d.share * 100) + "% de la venta · " +
                        Math.round(d.cump) + "% de meta · " + d.tiendas + (d.tiendas === 1 ? " tienda" : " tiendas") + "</div></div></div>";
                }).join("") + "</div>";

            var cards = slot.box.querySelectorAll(".gp-cl");
            pauseOffscreen(slot.box);
            var canvas = slot.box.querySelector(".gp-donut");
            var ctx = canvas.getContext("2d"), C = 170, R = 128;
            function drawDonut(t) {
                ctx.clearRect(0, 0, 340, 340);
                var a0 = -Math.PI / 2;
                data.forEach(function (d) {
                    var sweep = d.share * Math.PI * 2 * ease(t);
                    ctx.beginPath();
                    ctx.arc(C, C, R, a0 + .025, Math.max(a0 + .025, a0 + sweep - .025));
                    ctx.strokeStyle = d.tipo.color; ctx.lineWidth = 40; ctx.stroke();
                    a0 += sweep;
                });
                ctx.textAlign = "center";
                ctx.fillStyle = "#6b6259"; ctx.font = "700 19px Inter, system-ui, sans-serif";
                ctx.fillText("VENTA TOTAL", C, C - 10);
                ctx.fillStyle = "#202a2d"; ctx.font = "800 32px 'JetBrains Mono', Consolas, monospace";
                ctx.fillText(money(total * ease(t)), C, C + 26);
            }
            drawDonut(REDUCE ? 1 : 0);
            onVisible(slot.panel, function () {
                var start = performance.now();
                var step = function () {
                    var t = REDUCE ? 1 : Math.min((performance.now() - start) / 1600, 1);
                    drawDonut(t);
                    if (t < 1) setTimeout(step, 33);
                };
                step();
                Array.prototype.forEach.call(cards, function (card, i) {
                    setTimeout(function () {
                        countTo(card.querySelector("b"), data[i].ventas, 1400, money);
                        card.querySelector(".gp-share i").style.width = (data[i].share / maxShare * 100) + "%";
                    }, REDUCE ? 0 : 250 + i * 180);
                });
            });
        } catch (error) {
            console.error("graficas-premium: clima", error);
            slot.restore();
        }
    }

    // -----------------------------------------------------
    // 2. Top cumplimiento: velocímetros
    // -----------------------------------------------------
    var GAUGE = '<svg viewBox="0 0 120 76" aria-hidden="true">' +
        '<path d="M12 60 A48 48 0 0 1 42.4 15.3" stroke="#a63d40" stroke-width="10" fill="none"/>' +
        '<path d="M43.4 14.9 A48 48 0 0 1 77.6 14.9" stroke="#d95d39" stroke-width="10" fill="none"/>' +
        '<path d="M78.6 15.3 A48 48 0 0 1 96.6 30" stroke="#e0a96d" stroke-width="10" fill="none"/>' +
        '<path d="M97.3 31 A48 48 0 0 1 108 60" stroke="#2d6a4f" stroke-width="10" fill="none"/>' +
        '<g class="gp-needle"><path d="M60 60 L58 22 L60 16 L62 22 Z" fill="#202a2d"/></g>' +
        '<circle cx="60" cy="60" r="6" fill="#202a2d"/><circle cx="60" cy="60" r="2.5" fill="#fff"/></svg>';
    var MAX_GAUGE = 130;   // la aguja llega al tope en 130%

    function topCumplimiento(rows) {
        rows = (rows || []).map(function (r) {
            return { nombre: r.nombre || "Sin nombre", pct: asPercent(r.cumplimiento_pct) };
        });
        if (!rows.length) return;
        var slot = takeOver("cumplimientoChart");
        if (!slot) return;
        try {
            var grid = document.createElement("div");
            grid.className = "gp-gauges";
            slot.box.appendChild(grid);
            var seen = false, current = "all";

            function filtered(filter) {
                var list = rows.slice().sort(function (a, b) { return b.pct - a.pct; });
                if (filter === "goal") list = list.filter(function (r) { return r.pct >= 100; });
                if (filter === "close") list = list.filter(function (r) { return r.pct >= 90 && r.pct < 100; });
                if (filter === "critical") list = list.filter(function (r) { return r.pct < 75; });
                return list.slice(0, filter === "all" ? 9 : 12);
            }

            function render(filter, animate) {
                current = filter;
                var list = filtered(filter);
                if (!list.length) {
                    grid.innerHTML = '<div class="gp-empty">No hay tiendas en este grupo.</div>';
                    return;
                }
                grid.innerHTML = list.map(function (r) {
                    return '<div class="gp-ga' + (r.pct >= 100 ? " gp-win" : "") + '" title="' + escapeHtml(r.nombre) + ": " + pct(r.pct) + '">' +
                        GAUGE + '<span class="gp-name">' + escapeHtml(r.nombre) + '</span><div class="gp-pv" style="color:' +
                        statusColor(r.pct) + '">' + (animate ? "0%" : pct(r.pct)) + "</div><small>cumplimiento</small></div>";
                }).join("");
                var cards = grid.querySelectorAll(".gp-ga");
                Array.prototype.forEach.call(cards, function (card, i) {
                    var r = list[i], needle = card.querySelector(".gp-needle");
                    var angle = -90 + Math.min(Math.max(r.pct, 0), MAX_GAUGE) / MAX_GAUGE * 180;
                    if (!animate) { needle.style.transition = "none"; needle.style.transform = "rotate(" + angle + "deg)"; return; }
                    setTimeout(function () {
                        needle.style.transform = "rotate(" + angle + "deg)";
                        countTo(card.querySelector(".gp-pv"), r.pct, 1500, pct);
                    }, REDUCE ? 0 : 120 + i * 100);
                });
            }

            render("all", false);
            onVisible(slot.panel, function () { seen = true; render(current, !REDUCE); });

            // Los botones del V2 (Top / En meta / Cerca / Críticas) también mueven los velocímetros.
            slot.panel.addEventListener("click", function (event) {
                var button = event.target.closest(".v2-segment button");
                if (!button || !button.dataset.value) return;
                render(button.dataset.value, seen && !REDUCE);
            });
        } catch (error) {
            console.error("graficas-premium: cumplimiento", error);
            slot.restore();
        }
    }

    function init() {
        var base = readJSON("dashboard-data");
        var extra = readJSON("dashboard-v2-data");
        var ranking = Array.isArray(extra.ranking) && extra.ranking.length ? extra.ranking
            : (Array.isArray(base.topCumplimiento) ? base.topCumplimiento : []);
        try { ventasPorClima(base.resumenClimas); } catch (e) { console.error("graficas-premium:", e); }
        try { topCumplimiento(ranking); } catch (e) { console.error("graficas-premium:", e); }
    }

    // dashboard-v2.js arma sus gráficas y botones a los 80 ms del DOMContentLoaded.
    function start() { setTimeout(init, 220); }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
})();
