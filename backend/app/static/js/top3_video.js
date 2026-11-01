/* =========================================================
   CEREMONIA TOP 3 CON VIDEO (podio dorado)
   Reemplaza solo la parte visual de la ceremonia de dashboard.js:
   - El video del podio se reproduce una vez (7,8 s) y se congela.
   - Mientras corre, se anuncian el 3.º, el 2.º y el 1.er lugar.
   - Al congelarse, la foto de cada tienda queda sobre su bloque y su
     nombre y cumplimiento en una placa frente al bloque.
   - Botón "Saltar". Con "reducir animaciones" se ve el podio quieto.
   - Si el video no carga, se usa la ceremonia anterior tal cual.
   Botones "Ir al inicio" / "Ver dashboard" y Escape: los de siempre.
   ========================================================= */
(function () {
    "use strict";

    var original = window.ejecutarCeremoniaTop3;
    if (typeof original !== "function") return;

    var BASE = "/static/img/top3/";
    var VERSION = "1";

    // Posición de cada bloque en el cuadro congelado (porcentaje del video 16:9)
    var BLOQUES = {
        1: { x: 49.9, techo: 43.2 },
        2: { x: 24.2, techo: 51.2 },
        3: { x: 75.5, techo: 58.6 }
    };
    var PLACA_Y = 90.5;  // altura de las placas frente al podio (piso)

    function reduceMovimiento() {
        try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; }
    }

    function el(tag, clase, texto) {
        var n = document.createElement(tag);
        if (clase) n.className = clase;
        if (texto != null) n.textContent = texto;
        return n;
    }

    function pct(valor) {
        return (Number(valor || 0) * 100).toFixed(1) + "%";
    }

    function cargarCss() {
        if (document.getElementById("t3vCss")) return;
        var link = document.createElement("link");
        link.id = "t3vCss";
        link.rel = "stylesheet";
        link.href = "/static/css/top3_video.css?v=" + VERSION;
        document.head.appendChild(link);
    }

    function imagenTienda(img, tienda) {
        if (typeof window.cargarImagenTienda === "function") {
            window.cargarImagenTienda(img, tienda.codigo || "", tienda.nombre || "");
        }
    }

    window.ejecutarCeremoniaTop3 = function (top3) {
        var overlay = document.getElementById("top3StoresOverlay");
        if (!overlay || !Array.isArray(top3) || !top3.length) return original(top3);
        try {
            montar(overlay, top3);
        } catch (error) {
            console.error("top3_video:", error);
            limpiar(overlay);
            original(top3);
        }
    };

    function limpiar(overlay) {
        overlay.classList.remove("t3v-modo");
        var viejo = overlay.querySelector(".t3v");
        if (viejo) viejo.remove();
    }

    function montar(overlay, top3) {
        cargarCss();
        overlay.classList.add("t3v-modo");

        var porPuesto = {};
        top3.forEach(function (t, i) { porPuesto[Number(t.posicion || i + 1)] = t; });

        var raiz = el("div", "t3v");
        var titulo = el("div", "t3v-titulo");
        titulo.append(el("span", "t3v-marca", "L&H PULSE"), el("span", "t3v-sub", "Top 3 · Ranking general de tiendas"));
        var anuncio = el("div", "t3v-anuncio");
        anuncio.setAttribute("aria-live", "polite");
        var saltar = el("button", "t3v-saltar", "Saltar");
        saltar.type = "button";

        var caja = el("div", "t3v-caja");
        var video = document.createElement("video");
        video.className = "t3v-video";
        video.muted = true;
        video.defaultMuted = true;
        video.playsInline = true;
        video.setAttribute("playsinline", "");
        video.setAttribute("muted", "");
        video.preload = "auto";
        video.poster = BASE + "podio_inicio.jpg?v=" + VERSION;
        video.src = BASE + "podio.mp4?v=" + VERSION;
        var quieto = el("img", "t3v-quieto");
        quieto.alt = "";
        quieto.src = BASE + "podio_final.jpg?v=" + VERSION;
        quieto.hidden = true;
        caja.append(video, quieto);

        // Medallones (foto sobre el bloque) y placas (nombre y % frente al bloque)
        var medallones = [];
        [2, 1, 3].forEach(function (puesto) {
            var t = porPuesto[puesto];
            if (!t) return;
            var b = BLOQUES[puesto];
            var med = el("div", "t3v-medallon t3v-p" + puesto);
            med.style.left = b.x + "%";
            med.style.top = b.techo + "%";
            var img = el("img", "t3v-foto");
            img.alt = t.nombre || "Tienda";
            imagenTienda(img, t);
            med.append(img);
            var placa = el("div", "t3v-placa t3v-p" + puesto);
            placa.style.left = b.x + "%";
            placa.style.top = PLACA_Y + "%";
            placa.append(el("strong", "", t.nombre || "Tienda"), el("span", "", pct(t.cumplimiento)));
            caja.append(med, placa);
            medallones.push({ puesto: puesto, med: med, placa: placa });
        });

        raiz.append(titulo, anuncio, caja, saltar);
        overlay.appendChild(raiz);

        var acciones = document.getElementById("top3Actions");
        if (acciones) raiz.appendChild(acciones);  // se mueven: siguen funcionando igual

        // Escala de textos y tamaños según el ancho real del video en pantalla
        function escalar() {
            var w = caja.getBoundingClientRect().width;
            if (w > 0) caja.style.setProperty("--k", (w / 1280).toFixed(4));
        }
        escalar();
        window.addEventListener("resize", escalar);
        if (window.ResizeObserver) new ResizeObserver(escalar).observe(caja);  // también cuando carga el estilo

        var timers = [];
        var terminado = false;

        function anunciar(puesto) {
            var t = porPuesto[puesto];
            if (!t) return;
            var nombres = { 1: "1.er lugar", 2: "2.º lugar", 3: "3.er lugar" };
            anuncio.replaceChildren();
            var foto = el("img", "t3v-anuncio-foto");
            foto.alt = "";
            imagenTienda(foto, t);
            var txt = el("div", "t3v-anuncio-texto");
            txt.append(el("small", "", nombres[puesto]), el("strong", "", t.nombre || "Tienda"), el("span", "", "Cumplimiento " + pct(t.cumplimiento)));
            anuncio.append(foto, txt);
            anuncio.className = "t3v-anuncio t3v-puesto" + puesto;
            void anuncio.offsetWidth;
            anuncio.classList.add("visible");
        }

        function final(inmediato) {
            if (terminado) return;
            terminado = true;
            timers.forEach(clearTimeout);
            saltar.hidden = true;
            anuncio.classList.remove("visible");
            if (inmediato || video.readyState < 2 || video.error) {
                video.hidden = true;
                quieto.hidden = false;
            } else {
                try { video.pause(); } catch (e) { /* nada */ }
            }
            raiz.classList.add("t3v-final");
            escalar();
            // Las fotos caen sobre los bloques: 3.º, 2.º y por último el 1.º
            [3, 2, 1].forEach(function (puesto, i) {
                var m = medallones.filter(function (x) { return x.puesto === puesto; })[0];
                if (!m) return;
                setTimeout(function () { m.med.classList.add("visible"); m.placa.classList.add("visible"); }, inmediato ? 0 : 150 + i * 320);
            });
            setTimeout(function () { if (acciones) acciones.classList.add("visible"); }, inmediato ? 0 : 1300);
        }

        saltar.addEventListener("click", function () { final(true); });

        if (reduceMovimiento()) {
            final(true);
            return;
        }

        var arranco = false;
        var respaldo = setTimeout(function () {
            if (arranco) return;
            // El video no arrancó: ceremonia anterior
            window.removeEventListener("resize", escalar);
            if (acciones) overlay.querySelector(".top3-content").appendChild(acciones);
            limpiar(overlay);
            original(top3);
        }, 4000);

        video.addEventListener("playing", function () {
            if (arranco) return;
            arranco = true;
            clearTimeout(respaldo);
            timers.push(setTimeout(function () { anunciar(3); }, 900));
            timers.push(setTimeout(function () { anunciar(2); }, 3100));
            timers.push(setTimeout(function () { anunciar(1); }, 5300));
        });
        video.addEventListener("ended", function () { final(false); });
        video.addEventListener("error", function () {
            if (!arranco) { clearTimeout(respaldo); window.removeEventListener("resize", escalar); if (acciones) overlay.querySelector(".top3-content").appendChild(acciones); limpiar(overlay); original(top3); }
            else final(true);
        });

        var promesa = video.play();
        if (promesa && promesa.catch) {
            promesa.catch(function () {
                // El navegador no dejó reproducir: se muestra el podio quieto con las tiendas
                clearTimeout(respaldo);
                arranco = true;
                final(true);
            });
        }
    };
})();
