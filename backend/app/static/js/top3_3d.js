/* =========================================================
   CEREMONIA TOP 3 EN 3D (podio dorado)
   Reemplaza solo la parte visual de la ceremonia de dashboard.js por
   el podio en 3D (static/top3/podio3d.js). Las tiendas quedan
   integradas al podio: nombre y % grabados en el bloque y la foto en
   un medallón dorado. Botón "Saltar". Con "reducir animaciones" se ve
   la escena completa sin movimiento.
   Un solo botón "Entrar" (cierra la ceremonia). El podio se encuadra en
   el espacio libre entre el título y el botón, en cualquier pantalla.
   Si el equipo no soporta 3D o algo falla, se usa la ceremonia anterior.
   ========================================================= */
(function () {
    "use strict";

    var original = window.ejecutarCeremoniaTop3;
    if (typeof original !== "function") return;
    var VERSION = "1";

    function hayWebGL() {
        try {
            var c = document.createElement("canvas");
            return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
        } catch (e) { return false; }
    }
    function reduceMovimiento() {
        try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; }
    }
    function el(tag, clase, texto) {
        var n = document.createElement(tag);
        if (clase) n.className = clase;
        if (texto != null) n.textContent = texto;
        return n;
    }

    window.ejecutarCeremoniaTop3 = function (top3) {
        var overlay = document.getElementById("top3StoresOverlay");
        if (!overlay || !Array.isArray(top3) || !top3.length || !hayWebGL()) return original(top3);

        if (!document.getElementById("t3dCss")) {
            var link = document.createElement("link");
            link.id = "t3dCss"; link.rel = "stylesheet";
            link.href = "/static/css/top3_3d.css?v=" + VERSION;
            document.head.appendChild(link);
        }
        overlay.classList.add("t3d-modo");

        var raiz = el("div", "t3d");
        var lienzo = el("div", "t3d-lienzo");
        var titulo = el("div", "t3d-titulo");
        titulo.append(el("span", "t3d-marca", "L&H PULSE"), el("span", "t3d-sub", "Top 3 · Ranking general de tiendas"));
        var saltar = el("button", "t3d-saltar", "Saltar");
        saltar.type = "button";
        // Para lectores de pantalla: el resultado en texto
        var lector = el("div", "t3d-lector");
        lector.setAttribute("aria-live", "polite");
        lector.textContent = top3.map(function (t, i) {
            return (t.posicion || i + 1) + ". " + (t.nombre || "Tienda") + " " + (Number(t.cumplimiento || 0) * 100).toFixed(1) + "%";
        }).join(" · ");
        raiz.append(lienzo, titulo, saltar, lector);
        overlay.appendChild(raiz);

        var acciones = document.getElementById("top3Actions");
        var contenidoViejo = overlay.querySelector(".top3-content");
        if (acciones) raiz.appendChild(acciones);

        // Un solo botón: "Entrar" (el de "Ir al inicio" hacía lo mismo)
        var botonEntrar = document.getElementById("top3DashboardButton");
        var botonInicio = document.getElementById("top3HomeButton");
        var textoOriginal = botonEntrar ? botonEntrar.innerHTML : "";
        function margenes() {
            var alto = raiz.getBoundingClientRect().height || window.innerHeight;
            var finTitulo = titulo.getBoundingClientRect().bottom - raiz.getBoundingClientRect().top;
            var reservaBoton = (botonEntrar ? 54 : 0) + Math.max(16, Math.min(40, alto * 0.04)) + 14;
            return { arriba: Math.max(0, finTitulo + 8), abajo: reservaBoton };
        }

        var podio = null;
        function volverAlOriginal(error) {
            if (error) console.error("top3_3d:", error);
            if (botonEntrar) botonEntrar.innerHTML = textoOriginal;
            if (botonInicio) botonInicio.hidden = false;
            if (podio) { try { podio.destruir(); } catch (e) { /* nada */ } }
            if (acciones && contenidoViejo) contenidoViejo.appendChild(acciones);
            raiz.remove();
            overlay.classList.remove("t3d-modo");
            original(top3);
        }

        // Si el overlay se cierra (botones o Escape), se libera la escena 3D
        var vigilante = new MutationObserver(function () {
            if (!document.body.contains(overlay) || overlay.classList.contains("closing")) {
                vigilante.disconnect();
                setTimeout(function () { if (podio) podio.destruir(); }, 900);
            }
        });
        vigilante.observe(document.body, { childList: true, subtree: false });
        vigilante.observe(overlay, { attributes: true, attributeFilter: ["class"] });

        import("/static/top3/podio3d.js?v=" + VERSION).then(function (modulo) {
            var quieto = reduceMovimiento();
            if (botonEntrar) botonEntrar.innerHTML = '<i class="bi bi-box-arrow-in-right me-2"></i> Entrar';
            if (botonInicio) botonInicio.hidden = true;
            podio = modulo.crearPodio(lienzo, top3, {
                quieto: quieto,
                margenes: margenes,
                alTerminar: function () {
                    saltar.hidden = true;
                    raiz.classList.add("t3d-final");
                    setTimeout(function () { if (acciones) acciones.classList.add("visible"); }, quieto ? 0 : 500);
                }
            });
            window.__top3_3d = podio;  // para pruebas
            requestAnimationFrame(function () { raiz.classList.add("visible"); });
            saltar.addEventListener("click", function () { if (podio) podio.saltar(); });
        }).catch(volverAlOriginal);
    };
})();
