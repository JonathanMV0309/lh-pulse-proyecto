/* =========================================================
   L&H PULSE - Animaciones premium del dashboard administrativo V2
   1. Barra dorada de progreso de lectura
   2. Entrada escalonada de secciones y tarjetas al hacer scroll
   3. Título con línea dorada y destello
   4. Brillo que sigue al cursor en las tarjetas
   5. Filas de ranking en cascada + acento del podio
   6. Pausa de animaciones infinitas fuera de pantalla

   Solo presentación: no cambia datos ni hace peticiones.
   Complementa tienda_animaciones.js (contadores y barras).
   ========================================================= */
(function () {
    "use strict";

    if (!document.body || !document.body.classList) return;

    var sinMovimiento = false /* Las animaciones se muestran siempre, aunque Windows tenga apagadas las animaciones. */;

    var conHover = window.matchMedia &&
        window.matchMedia("(hover: hover) and (pointer: fine)").matches;

    var hayObserver = "IntersectionObserver" in window;

    function todos(selector, raiz) {
        return Array.prototype.slice.call((raiz || document).querySelectorAll(selector));
    }

    // Red de seguridad: el IntersectionObserver siempre responde una
    // primera vez al observar. Si no lo hace (navegador raro, pestaña
    // congelada), se muestra todo para que nada quede oculto.
    function alVerse(elementos, callback, opciones) {
        if (!elementos.length) return;
        if (!hayObserver) {
            elementos.forEach(callback);
            return;
        }
        var vivo = false;
        var pendientes = elementos.slice();
        setTimeout(function () {
            if (vivo) return;
            obs.disconnect();
            pendientes.forEach(callback);
        }, 1500);
        var obs = new IntersectionObserver(function (entradas) {
            vivo = true;
            entradas.forEach(function (e) {
                if (e.isIntersecting) {
                    obs.unobserve(e.target);
                    callback(e.target);
                }
            });
        }, opciones || { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
        elementos.forEach(function (el) { obs.observe(el); });
    }

    // -----------------------------------------------------
    // 1. Barra de progreso de lectura
    // -----------------------------------------------------
    function prepararProgresoLectura() {
        if (sinMovimiento) return;
        var barra = document.createElement("div");
        barra.className = "aa-progreso-lectura";
        barra.setAttribute("aria-hidden", "true");
        document.body.appendChild(barra);

        var pendiente = false;
        function actualizar() {
            pendiente = false;
            var doc = document.documentElement;
            var max = doc.scrollHeight - window.innerHeight;
            var avance = max > 0 ? Math.min(window.scrollY / max, 1) : 0;
            barra.style.transform = "scaleX(" + avance.toFixed(4) + ")";
        }
        window.addEventListener("scroll", function () {
            if (!pendiente) {
                pendiente = true;
                requestAnimationFrame(actualizar);
            }
        }, { passive: true });
        actualizar();
    }

    // -----------------------------------------------------
    // 2. Entrada escalonada
    // -----------------------------------------------------
    function prepararEntradas() {
        if (sinMovimiento || !hayObserver) return;

        var contenedor = document.querySelector(".dashboard-container");
        if (!contenedor) return;

        // Grupos de tarjetas: cada hijo entra con un pequeño retraso
        var grupos = [".kpi-grid", ".secondary-kpi-grid", ".charts-grid", ".v2-insight-strip", ".summary-grid"];
        var hijosAgrupados = [];

        grupos.forEach(function (sel) {
            todos(sel, contenedor).forEach(function (grupo) {
                Array.prototype.forEach.call(grupo.children, function (hijo, i) {
                    hijo.style.setProperty("--aa-retraso", (Math.min(i, 6) * 0.07) + "s");
                    hijosAgrupados.push(hijo);
                });
            });
        });

        // Secciones sueltas (las que no son grupos)
        var sueltas = Array.prototype.filter.call(contenedor.children, function (el) {
            if (el.tagName === "SCRIPT") return false;
            return !grupos.some(function (sel) { return el.matches(sel); });
        });

        var elementos = sueltas.concat(hijosAgrupados);

        // Lo que ya se ve al cargar no se toca (evita parpadeos);
        // solo se anima lo que aparece al bajar.
        var alto = window.innerHeight;
        elementos.forEach(function (el) {
            if (el.getBoundingClientRect().top > alto) {
                el.classList.add("aa-oculto");
            }
        });

        alVerse(elementos.filter(function (el) { return el.classList.contains("aa-oculto"); }), function (el) {
            el.classList.remove("aa-oculto");
            el.classList.add("aa-entra");
        });

        // Al terminar, se quitan las clases para no interferir con el hover
        contenedor.addEventListener("animationend", function (e) {
            if (e.animationName === "aaEntrar") {
                e.target.classList.remove("aa-entra");
                e.target.style.removeProperty("--aa-retraso");
            }
        });
    }

    // -----------------------------------------------------
    // 3. Título
    // -----------------------------------------------------
    function prepararTitulo() {
        var titulo = document.querySelector(".dashboard-title");
        if (!titulo || sinMovimiento) return;
        titulo.classList.add("aa-titulo");
        var destello = document.createElement("span");
        destello.className = "aa-destello";
        destello.setAttribute("aria-hidden", "true");
        titulo.appendChild(destello);
        setTimeout(function () { destello.remove(); }, 3000);
    }

    // -----------------------------------------------------
    // 4. Brillo que sigue al cursor
    // -----------------------------------------------------
    function prepararFoco() {
        if (!conHover || sinMovimiento) return;

        todos(".kpi-card, .secondary-kpi, .v2-insight").forEach(function (tarjeta) {
            if (tarjeta.querySelector(":scope > .aa-luz")) return;
            var luz = document.createElement("span");
            luz.className = "aa-luz";
            luz.setAttribute("aria-hidden", "true");
            tarjeta.classList.add("aa-foco");
            tarjeta.appendChild(luz);

            var rect = null, pendiente = false, x = 0, y = 0;

            tarjeta.addEventListener("pointerenter", function () {
                rect = tarjeta.getBoundingClientRect();
            });

            tarjeta.addEventListener("pointermove", function (e) {
                if (!rect) rect = tarjeta.getBoundingClientRect();
                x = e.clientX - rect.left;
                y = e.clientY - rect.top;
                if (pendiente) return;
                pendiente = true;
                requestAnimationFrame(function () {
                    pendiente = false;
                    luz.style.setProperty("--aa-x", x + "px");
                    luz.style.setProperty("--aa-y", y + "px");
                });
            });

            tarjeta.addEventListener("pointerleave", function () { rect = null; });
        });
    }

    // -----------------------------------------------------
    // 5. Filas de ranking
    // -----------------------------------------------------
    function prepararFilas() {
        todos(".futuristic-table tbody").forEach(function (cuerpo) {
            var filas = Array.prototype.slice.call(cuerpo.rows);
            if (!filas.length) return;

            // Acento del podio (solo si la tabla usa medallas)
            if (cuerpo.querySelector(".gold-rank")) {
                ["aa-top1", "aa-top2", "aa-top3"].forEach(function (clase, i) {
                    if (filas[i]) filas[i].classList.add(clase);
                });
            }

            if (sinMovimiento || !hayObserver) return;
            if (cuerpo.getBoundingClientRect().top < window.innerHeight) return;

            // Se animan las primeras 15 filas; el resto aparece directo
            var animadas = filas.slice(0, 15);
            animadas.forEach(function (fila, i) {
                fila.classList.add("aa-fila");
                fila.style.setProperty("--aa-retraso", (i * 0.04) + "s");
            });

            alVerse([cuerpo], function () {
                setTimeout(function () {
                    animadas.forEach(function (fila) { fila.classList.add("aa-fila-in"); });
                }, 20);
                // Limpia el retraso para que el hover responda al instante
                setTimeout(function () {
                    animadas.forEach(function (fila) { fila.style.removeProperty("--aa-retraso"); });
                }, 1400);
            });
        });

        // Lista "Tiendas con mayor venta"
        todos(".ranking-list").forEach(function (lista) {
            var items = todos(".ranking-item", lista);
            if (!items.length || sinMovimiento || !hayObserver) return;
            if (lista.getBoundingClientRect().top < window.innerHeight) return;
            items.forEach(function (it, i) {
                it.classList.add("aa-fila");
                it.style.setProperty("--aa-retraso", (Math.min(i, 12) * 0.05) + "s");
            });
            alVerse([lista], function () {
                setTimeout(function () {
                    items.forEach(function (it) { it.classList.add("aa-fila-in"); });
                }, 20);
            });
        });
    }

    // -----------------------------------------------------
    // 6. Pausar animaciones infinitas fuera de pantalla
    // -----------------------------------------------------
    function prepararPausa() {
        if (!hayObserver || sinMovimiento) return;
        var objetivos = todos(".dashboard-header, .welcome-panel, .comparison-panel");
        if (!objetivos.length) return;
        var obs = new IntersectionObserver(function (entradas) {
            entradas.forEach(function (e) {
                e.target.classList.toggle("aa-pausa", !e.isIntersecting);
            });
        });
        objetivos.forEach(function (el) { obs.observe(el); });
    }

    function iniciar() {
        if (!document.body.classList.contains("dashboard-v2")) {
            document.body.classList.add("dashboard-v2");
        }
        var pasos = [prepararProgresoLectura, prepararTitulo, prepararEntradas, prepararFilas, prepararFoco, prepararPausa];
        pasos.forEach(function (fn) {
            try { fn(); } catch (e) { console.error("admin_animaciones:", fn.name, e); }
        });
    }

    // dashboard-v2.js arma sus gráficas e insights a los 80 ms;
    // esperamos un poco más para incluir esos elementos.
    function arrancar() { setTimeout(iniciar, 140); }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", arrancar);
    } else {
        arrancar();
    }
})();
