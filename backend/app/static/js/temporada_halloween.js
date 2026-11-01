/* =========================================================
   L&H PULSE - Temporada de Halloween (octubre)
   Se activa sola del 1 al 31 de octubre y se apaga sola después.
   Cada persona puede apagarla con el botón 🎃 de la barra
   superior (se recuerda en su navegador).
   Para verla fuera de octubre: agregar ?tema=halloween a la URL.

   Solo decoración en los bordes: no cambia datos ni la lógica de
   la página. Los murciélagos solo vuelan con la pestaña visible.
   ========================================================= */
(function () {
    "use strict";

    var KEY = "lh_tema_halloween";
    var REDUCE = false /* Las animaciones se muestran siempre, aunque Windows tenga apagadas las animaciones. */;
    var root = document.documentElement;
    var params = new URLSearchParams(window.location.search);
    var forced = params.get("tema");
    var isOctober = new Date().getMonth() === 9;
    if (!isOctober && forced !== "halloween") return;   // fuera de temporada no hace nada

    function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
    function store(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* sin almacenamiento */ } }

    var nodes = [], batTimer = null, resizeTimer = null;
    var NS = "http://www.w3.org/2000/svg";

    function add(node, parent) { (parent || document.body).appendChild(node); nodes.push(node); return node; }
    function div(className, html) { var d = document.createElement("div"); d.className = className; if (html) d.innerHTML = html; return d; }

    // ---- Medidas: debajo de la barra superior y a la derecha del menú ----
    function measure() {
        var topbar = document.querySelector(".lh-topbar");
        var sidebar = document.querySelector(".lh-sidebar");
        var top = topbar ? Math.round(topbar.getBoundingClientRect().bottom) : 64;
        var left = 0;
        if (sidebar) {
            var r = sidebar.getBoundingClientRect();
            if (r.right > 0 && r.left >= 0 && getComputedStyle(sidebar).position === "fixed" && window.innerWidth >= 992) left = Math.round(r.right);
        }
        root.style.setProperty("--hw-top", top + "px");
        root.style.setProperty("--hw-left", left + "px");
        return { top: top, left: left, width: window.innerWidth - left };
    }

    // ---- Guirnalda de banderines ----
    function garland(width) {
        var box = div("hw-garland");
        var count = Math.max(6, Math.floor(width / 46));
        var step = width / count;
        var colors = ["#e8772e", "#5b3a8c", "#2a2238"];
        var svg = '<svg viewBox="0 0 ' + width + ' 34" aria-hidden="true">' +
            '<path d="M0 3 Q ' + width / 2 + ' 13 ' + width + ' 3" stroke="#6b5a48" stroke-width="1.4" fill="none"/>';
        for (var i = 0; i < count; i++) {
            var x = i * step + step / 2;
            var sag = 3 + Math.sin(Math.PI * x / width) * 9;
            var c = colors[i % 3];
            svg += '<g class="hw-flag" style="transform-origin:' + x + "px " + sag + "px;animation-delay:" + (i % 5) * -0.9 + 's">' +
                '<path d="M' + (x - 13) + " " + sag + " L" + (x + 13) + " " + sag + " L" + x + " " + (sag + 22) + ' Z" fill="' + c + '"/>';
            if (i % 3 === 0) {   // carita de calabaza en los naranjas
                svg += '<path d="M' + (x - 5) + " " + (sag + 5) + " l3 3 l-6 0 z M" + (x + 5) + " " + (sag + 5) + " l3 3 l-6 0 z M" + (x - 5) + " " + (sag + 11) +
                    " q5 4 10 0" + '" fill="#2a2238" stroke="#2a2238" stroke-width="1"/>';
            } else if (i % 3 === 2) {   // ojitos en los negros
                svg += '<circle cx="' + (x - 3.5) + '" cy="' + (sag + 7) + '" r="1.6" fill="#f4c542"/><circle cx="' + (x + 3.5) + '" cy="' + (sag + 7) + '" r="1.6" fill="#f4c542"/>';
            }
            svg += "</g>";
        }
        box.innerHTML = svg + "</svg>";
        return box;
    }

    // ---- Telaraña ----
    function web(cls) {
        var w = div("hw-web " + cls);
        var s = '<svg viewBox="0 0 150 150" aria-hidden="true">';
        var angles = [0, 15, 32, 50, 68, 90];
        angles.forEach(function (a) {
            var rad = a * Math.PI / 180;
            s += '<line x1="0" y1="0" x2="' + (150 * Math.cos(rad)) + '" y2="' + (150 * Math.sin(rad)) + '"/>';
        });
        [30, 58, 88, 120].forEach(function (r) {
            var d = "";
            angles.forEach(function (a, i) {
                var rad = a * Math.PI / 180, x = r * Math.cos(rad), y = r * Math.sin(rad);
                if (i === 0) { d += "M" + x + " " + y; return; }
                var prev = angles[i - 1] * Math.PI / 180, mid = (rad + prev) / 2, rr = r * .86;
                d += " Q" + (rr * Math.cos(mid)) + " " + (rr * Math.sin(mid)) + " " + x + " " + y;
            });
            s += '<path d="' + d + '"/>';
        });
        w.innerHTML = s + "</svg>";
        return w;
    }

    // ---- Araña ----
    function spider(cls, side, offset, drop, delay) {
        var sp = div("hw-spider " + cls,
            '<span class="hw-thread"></span><svg viewBox="0 0 40 34" aria-hidden="true">' +
            '<g class="hw-legs" stroke="#2a2238" stroke-width="1.6" fill="none" stroke-linecap="round">' +
            '<path d="M14 16 Q6 10 2 14"/><path d="M14 19 Q5 18 1 23"/><path d="M15 22 Q7 26 4 32"/>' +
            '<path d="M26 16 Q34 10 38 14"/><path d="M26 19 Q35 18 39 23"/><path d="M25 22 Q33 26 36 32"/></g>' +
            '<ellipse cx="20" cy="20" rx="7.5" ry="8.5" fill="#2a2238"/><circle cx="20" cy="11" r="5" fill="#2a2238"/>' +
            '<circle cx="18" cy="10.5" r="1.4" fill="#f4ece0"/><circle cx="22" cy="10.5" r="1.4" fill="#f4ece0"/>' +
            '<circle cx="18.3" cy="10.8" r=".6" fill="#e8772e"/><circle cx="22.3" cy="10.8" r=".6" fill="#e8772e"/></svg>');
        sp.style.setProperty("--hw-drop", drop + "px");
        sp.style[side] = offset;
        sp.style.animationDelay = delay + "s";
        sp.title = "¡Uy, una araña!";
        sp.setAttribute("aria-hidden", "true");
        var scare = function () {
            if (sp.classList.contains("hw-up")) return;
            sp.classList.add("hw-up");
            setTimeout(function () { sp.classList.remove("hw-up"); }, 2600);
        };
        sp.addEventListener("pointerenter", scare);
        sp.addEventListener("click", scare);
        return sp;
    }

    // ---- Murciélagos ----
    var BAT_SVG = '<svg viewBox="0 0 46 24" aria-hidden="true">' +
        '<path class="hw-wing hw-l" d="M23 12 C17 2 9 2 1 7 C6 8 7 12 6 15 C10 12 14 14 17 17 C18 14 21 13 23 12Z" fill="#2a2238"/>' +
        '<path class="hw-wing hw-r" d="M23 12 C29 2 37 2 45 7 C40 8 39 12 40 15 C36 12 32 14 29 17 C28 14 25 13 23 12Z" fill="#2a2238"/>' +
        '<ellipse cx="23" cy="13" rx="3.4" ry="5" fill="#2a2238"/><circle cx="21.6" cy="11.5" r=".9" fill="#f4c542"/><circle cx="24.4" cy="11.5" r=".9" fill="#f4c542"/></svg>';

    function flyBat(fromX, fromY, toX, toY, duration, delay, scale) {
        if (REDUCE || document.hidden) return;
        var bat = div("hw-bat", BAT_SVG);
        add(bat, layer);
        var frames = [];
        for (var i = 0; i <= 10; i++) {
            var t = i / 10;
            var x = fromX + (toX - fromX) * t;
            var y = fromY + (toY - fromY) * t + Math.sin(t * Math.PI * 3) * 26;
            frames.push({ transform: "translate(" + x + "px," + y + "px) scale(" + scale + ")", opacity: t < .05 || t > .95 ? 0 : 1 });
        }
        var anim = bat.animate(frames, { duration: duration, delay: delay, easing: "linear", fill: "both" });
        anim.onfinish = function () { bat.remove(); };
    }

    function batFlight() {
        if (document.hidden) return;
        var m = measure(), w = window.innerWidth, h = window.innerHeight;
        var y0 = m.top + 60 + Math.random() * Math.max(h * .25, 60);
        var ltr = Math.random() < .5;
        var count = window.innerWidth < 768 ? 2 : 3;
        for (var i = 0; i < count; i++) {
            flyBat(ltr ? m.left - 60 : w + 20, y0 + i * 18, ltr ? w + 40 : m.left - 80, y0 - 50 + i * 12,
                6500 + i * 600, i * 380, .7 + Math.random() * .4);
        }
    }

    function scheduleBats() {
        clearTimeout(batTimer);
        if (REDUCE) return;
        batTimer = setTimeout(function () { batFlight(); scheduleBats(); }, 22000 + Math.random() * 14000);
    }

    // ---- Montar / desmontar ----
    var layer = null;

    function mount() {
        if (layer) return;
        root.classList.add("tema-halloween");
        var m = measure();
        layer = div("hw-layer");
        layer.setAttribute("aria-hidden", "true");
        add(layer);
        add(garland(m.width));
        add(web("hw-tl"));
        add(web("hw-br"));
        add(div("hw-fog"));
        add(spider("hw-s1", "left", "calc(var(--hw-left, 0px) + 4px)", 95, 0));
        add(spider("hw-s2", "right", "6px", 150, -2.5));
        if (!REDUCE) setTimeout(batFlight, 2500);
        scheduleBats();
    }

    function unmount() {
        root.classList.remove("tema-halloween");
        clearTimeout(batTimer);
        nodes.forEach(function (n) { n.remove(); });
        nodes = [];
        layer = null;
    }

    function relayout(again) {
        if (!layer) return;
        // El menú lateral se desliza al cambiar de tamaño: se vuelve a medir
        // cuando termina su animación.
        if (again !== false) setTimeout(function () { relayout(false); }, 450);
        var m = measure();
        var old = document.querySelector(".hw-garland");
        if (old) {
            var fresh = garland(m.width);
            old.replaceWith(fresh);
            nodes[nodes.indexOf(old)] = fresh;
            fresh.style.animation = "none";
        }
    }

    // ---- Botón 🎃 en la barra superior ----
    function toggleButton() {
        var bar = document.querySelector(".lh-topbar-right");
        if (!bar) return;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "hw-toggle";
        var paint = function () {
            var on = root.classList.contains("tema-halloween");
            btn.innerHTML = "🎃";
            btn.setAttribute("aria-label", on ? "Apagar decoración de temporada" : "Prender decoración de temporada");
            btn.setAttribute("aria-pressed", on ? "true" : "false");
            btn.title = on ? "Apagar la decoración de Halloween" : "Prender la decoración de Halloween";
        };
        btn.addEventListener("click", function () {
            if (root.classList.contains("tema-halloween")) { unmount(); store("off"); }
            else { mount(); store("on"); }
            paint();
        });
        bar.insertBefore(btn, bar.firstChild);
        return paint;
    }

    function start() {
        var paint = toggleButton();
        var wanted = forced === "halloween" || (forced !== "normal" && stored() !== "off");
        if (wanted) { mount(); setTimeout(function () { relayout(false); }, 450); }
        if (paint) paint();
        window.addEventListener("resize", function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(relayout, 200);
        });
        document.addEventListener("visibilitychange", function () {
            if (!document.hidden && layer) scheduleBats();
        });
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
})();
