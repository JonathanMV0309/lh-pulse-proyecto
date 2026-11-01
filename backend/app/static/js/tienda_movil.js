/* =========================================================
   L&H PULSE - Dashboard de tienda en celular
   Copia el nombre de cada columna a sus celdas (data-label)
   para que en celular las tablas se vean como tarjetas.
   ========================================================= */
(function () {
    "use strict";

    function prepararTabla(tabla) {
        var encabezados = Array.prototype.map.call(
            tabla.querySelectorAll("thead th"),
            function (th) { return th.textContent.trim(); }
        );
        if (!encabezados.length) return;

        tabla.querySelectorAll("tbody tr").forEach(function (fila) {
            var celdas = fila.children;
            for (var i = 0; i < celdas.length; i++) {
                var td = celdas[i];
                if (td.hasAttribute("colspan")) continue;
                var titulo = (encabezados[i] || "").toUpperCase();
                td.setAttribute("data-label", encabezados[i] || "");
                if (titulo.indexOf("POS") === 0) td.classList.add("ta-m-pos");
                else if (titulo === "ASESORA" || titulo === "TIENDA" && i === 1 || titulo === "LÍNEA" || titulo === "LINEA") td.classList.add("ta-m-nombre");
                if (td.querySelector(".progress, .progress-track")) td.classList.add("ta-m-ancho");
            }
        });
    }

    function iniciar() {
        document.querySelectorAll("table.advisors-table, table.futuristic-table").forEach(function (t) {
            try { prepararTabla(t); } catch (e) { console.error("tienda_movil:", e); }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar);
    } else {
        iniciar();
    }
})();
