/* =========================================================
   L&H PULSE - Efectos premium del dashboard de tienda
   1  Tablero de aeropuerto (ventas del mes)
   2  Bolsa que se llena (cumplimiento de meta)
   3  Carta holográfica (asesora #1)
   4  Carrera de asesoras
   5  Pulso diario (facturas por día)
   6  Embudo de clientes (tráfico -> facturas)
   7  Tiquete del cliente promedio
   8  Etiquetas colgantes
   9  Costura en las tarjetas de indicadores
   10 Calendario que se enciende
   11 Cuenta regresiva y racha
   12 Skyline de líneas

   Solo presentación: lee el bloque #tpDatos y la página; no
   modifica datos ni hace peticiones. Cada efecto está aislado:
   si uno falla, la sección queda como estaba.
   Todo avanza por tiempo real (se ve igual en un PC lento) y
   los bucles se detienen fuera de pantalla.
   ========================================================= */
(function () {
    "use strict";

    var REDUCE = false /* Las animaciones se muestran siempre, aunque Windows tenga apagadas las animaciones. */;
    var HOVER = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    var HAS_IO = "IntersectionObserver" in window;
    var NUM = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
    var MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
        "Septiembre", "Octubre", "Noviembre", "Diciembre"];

    // -----------------------------------------------------
    // Utilidades
    // -----------------------------------------------------
    function leerDatos() {
        var nodo = document.getElementById("tpDatos");
        if (!nodo) return null;
        try { return JSON.parse(nodo.textContent); } catch (e) { return null; }
    }

    function num(value) {
        var n = Number(value);
        return isFinite(n) ? n : 0;
    }

    function money(value) { return "$" + NUM.format(Math.round(num(value))); }

    function compactMoney(value) {
        var v = num(value);
        var one = function (x) { return (Math.round(x * 10) / 10).toFixed(1).replace(".", ","); };
        if (Math.abs(v) >= 1e9) return "$" + one(v / 1e9) + "B";
        if (Math.abs(v) >= 1e6) return "$" + one(v / 1e6) + "M";
        if (Math.abs(v) >= 1e3) return "$" + Math.round(v / 1e3) + "K";
        return "$" + Math.round(v);
    }

    function pct(value, decimals) {
        return (num(value) * 100).toFixed(decimals == null ? 1 : decimals).replace(".", ",") + "%";
    }

    function escapeHtml(text) {
        return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function ease(t) { return 1 - Math.pow(1 - t, 3); }

    function el(tag, className, html) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (html != null) node.innerHTML = html;
        return node;
    }

    function sectionByTitle(text) {
        var cards = document.querySelectorAll(".section-card");
        for (var i = 0; i < cards.length; i++) {
            var h = cards[i].querySelector(".section-header h4");
            if (h && h.textContent.indexOf(text) !== -1) return cards[i];
        }
        return null;
    }

    function kpiByTitle(text) {
        var titles = document.querySelectorAll(".kpi-card .kpi-title");
        for (var i = 0; i < titles.length; i++) {
            if (titles[i].textContent.trim().toUpperCase() === text) return titles[i].closest(".kpi-card");
        }
        return null;
    }

    // Ejecuta cb una vez cuando el elemento aparece. Red de seguridad: si el
    // observador no responde en 1,5 s (navegador raro), se ejecuta igual.
    function alVerse(node, cb) {
        if (!node) return;
        if (!HAS_IO || REDUCE) { cb(); return; }
        var done = false, alive = false;
        var run = function () { if (!done) { done = true; obs.disconnect(); cb(); } };
        var obs = new IntersectionObserver(function (entries) {
            alive = true;
            if (entries.some(function (e) { return e.isIntersecting; })) run();
        }, { threshold: 0.2 });
        obs.observe(node);
        setTimeout(function () { if (!alive) run(); }, 1500);
    }

    // Bucle de animación que solo corre mientras el elemento está en pantalla.
    // draw(now) devuelve false para detenerse.
    function loopVisible(node, draw) {
        var visible = !HAS_IO, raf = null, stopped = false;
        function frame(now) {
            raf = null;
            if (stopped || !visible) return;
            if (draw(now) === false) { stopped = true; return; }
            raf = requestAnimationFrame(frame);
        }
        function start() { if (!raf && !stopped && visible) raf = requestAnimationFrame(frame); }
        if (HAS_IO) {
            new IntersectionObserver(function (entries) {
                visible = entries[0].isIntersecting;
                if (visible) start();
            }).observe(node);
        }
        start();
        return { restart: function () { stopped = false; start(); } };
    }

    function pauseOffscreen(node) {
        if (!HAS_IO || !node) return;
        new IntersectionObserver(function (entries) {
            node.classList.toggle("tp-paused", !entries[0].isIntersecting);
        }).observe(node);
    }

    function hiDPI(canvas, cssWidth, ratio) {
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        var width = Math.max(cssWidth, 120);
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(width * ratio * dpr);
        var ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { ctx: ctx, w: width, h: width * ratio };
    }

    // -----------------------------------------------------
    // 1. Tablero de aeropuerto
    // -----------------------------------------------------
    function tableroAeropuerto(D) {
        var card = kpiByTitle("VENTAS DEL MES");
        if (!card) return;
        var value = card.querySelector(".kpi-value");
        if (!value) return;
        var full = "$" + value.textContent.trim().replace(/^\$/, "");
        // Ancho disponible real: el cuerpo de la tarjeta menos el ícono.
        var bodyCard = card.querySelector(".card-body") || card;
        var icon = card.querySelector(".kpi-icon");
        var available = function () {
            var style = getComputedStyle(bodyCard);
            var inner = bodyCard.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
            var iconWidth = icon && icon.offsetParent ? icon.offsetWidth + 10 : 0;
            return Math.max(inner - iconWidth, 80);
        };
        var unitsOf = function (t) {
            return t.split("").reduce(function (s, c) { return s + (/\d/.test(c) ? 1 : .45); }, 0) + t.length * .14;
        };
        // Si no caben los dígitos completos a un tamaño legible, se abrevia.
        var text = available() / unitsOf(full) >= 14 ? full : compactMoney(num(D.ventas) || num(full.replace(/[^\d]/g, "")));
        var holder = el("div", "tp-flaps");
        holder.setAttribute("aria-label", full);
        var cells = [];
        for (var i = 0; i < text.length; i++) {
            var ch = text[i], digit = /\d/.test(ch);
            var cell = el("span", "tp-flap" + (digit ? "" : " tp-sep"), REDUCE || !digit ? escapeHtml(ch) : "0");
            cell.setAttribute("aria-hidden", "true");
            holder.appendChild(cell);
            cells.push({ node: cell, ch: ch, digit: digit });
        }
        value.textContent = "";
        value.appendChild(holder);
        holder.title = full;
        var fit = function () {
            var size = Math.max(12, Math.min(26, available() / unitsOf(text)));
            holder.style.setProperty("--tp-flap-w", size.toFixed(1) + "px");
        };
        fit();
        window.addEventListener("resize", fit);
        if (REDUCE) return;
        alVerse(card, function () {
            var start = performance.now();
            cells.forEach(function (c, index) {
                if (!c.digit) return;
                var stopAt = 650 + index * 110;
                var tick = function () {
                    var elapsed = performance.now() - start;
                    var v = elapsed >= stopAt ? c.ch : String(Math.floor(Math.random() * 10));
                    c.node.innerHTML = v + '<span class="tp-leaf">' + v + "</span>";
                    c.node.classList.remove("tp-flip");
                    void c.node.offsetWidth;
                    c.node.classList.add("tp-flip");
                    if (elapsed < stopAt) setTimeout(tick, 75);
                };
                setTimeout(tick, index * 35);
            });
        });
    }

    // -----------------------------------------------------
    // 2 + 11. Bolsa de meta, cuenta regresiva y racha
    // -----------------------------------------------------
    function bolsaYReloj(D) {
        var section = sectionByTitle("Cumplimiento de meta");
        if (!section) return;
        var body = section.querySelector(".p-4");
        if (!body) return;
        var hero = el("div", "tp-grid-hero");
        var bagBox = el("div", "");
        var canvas = el("canvas", "tp-bag");
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", "Cumplimiento de meta " + pct(D.cumplimiento));
        bagBox.appendChild(canvas);
        bagBox.appendChild(el("div", "tp-bag-caption", "CUMPLIMIENTO AL CORTE"));
        var right = el("div", "");
        hero.appendChild(bagBox);
        hero.appendChild(right);
        body.insertBefore(hero, body.firstChild);
        dibujarBolsa(canvas, num(D.cumplimiento) * 100, hero);
        reloj(right, D);
    }

    function dibujarBolsa(canvas, target, container) {
        var size = hiDPI(canvas, Math.min(210, canvas.clientWidth || 190), 1.16);
        var ctx = size.ctx, W = size.w, H = size.h;
        var s = W / 380;
        var start = null;
        function path() {
            ctx.beginPath();
            ctx.moveTo(60 * s, 130 * s); ctx.lineTo(320 * s, 130 * s);
            ctx.lineTo(345 * s, 420 * s); ctx.lineTo(35 * s, 420 * s); ctx.closePath();
        }
        loopVisible(container, function (now) {
            if (start === null) start = now;
            var t = REDUCE ? 1 : Math.min((now - start) / 1800, 1);
            var level = target * ease(t);
            var gold = level >= 100;
            var phase = now / 1000;
            var main = gold ? "#c5a880" : "#0d5c75";
            ctx.clearRect(0, 0, W, H);
            ctx.lineWidth = 9 * s; ctx.strokeStyle = main;
            ctx.beginPath(); ctx.arc(190 * s, 132 * s, 70 * s, Math.PI, 0); ctx.stroke();
            ctx.save(); path(); ctx.clip();
            ctx.fillStyle = "#efe7da"; ctx.fillRect(0, 0, W, H);
            var top = (420 - Math.min(level, 100) / 100 * 290) * s;
            var waves = [[9, 2.6, 0, gold ? "rgba(224,169,109,.55)" : "rgba(13,92,117,.45)"], [6, 4.2, 2, main]];
            waves.forEach(function (w) {
                ctx.beginPath(); ctx.moveTo(0, H);
                for (var x = 0; x <= W; x += 4) {
                    ctx.lineTo(x, top + Math.sin(x / (38 * s) + phase * w[1] + w[2]) * w[0] * s);
                }
                ctx.lineTo(W, H); ctx.closePath(); ctx.fillStyle = w[3]; ctx.fill();
            });
            if (gold) {
                for (var i = 0; i < 6; i++) {
                    var bx = (70 + ((i * 53 + phase * 30) % 250)) * s;
                    var by = 410 * s - ((phase * 60 + i * 47) % Math.max(420 - top / s, 10)) * s;
                    ctx.beginPath(); ctx.arc(bx, by, (3 + i % 3) * s, 0, 7);
                    ctx.fillStyle = "rgba(255,255,255,.7)"; ctx.fill();
                }
            }
            ctx.restore();
            ctx.lineWidth = 6 * s; ctx.strokeStyle = main; path(); ctx.stroke();
            // Texto claro cuando el líquido lo cubre, oscuro cuando no.
            var covered = top < 285 * s;
            ctx.fillStyle = covered ? (gold ? "#3b2a10" : "#fdfbf7") : (gold ? "#7a5c2e" : "#083f51");
            ctx.font = "800 " + Math.round(46 * s) + "px Inter, system-ui, sans-serif";
            ctx.textAlign = "center";
            // Con un decimal, igual que «Cumplimiento al corte» (74.5 % no se redondea a 75 %)
            ctx.fillText(level.toFixed(1) + "%", 190 * s, 300 * s);
            if (REDUCE) return false;
            return true;
        });
    }

    function reloj(container, D) {
        var year = num(D.anio), month = num(D.mes);
        var daysInMonth = new Date(year, month, 0).getDate() || 30;
        var cutDay = Math.min(num(D.dia_corte) || daysInMonth, daysInMonth);
        var remainingDays = Math.max(daysInMonth - cutDay, 0);
        var today = new Date();
        var current = today.getFullYear() === year && today.getMonth() + 1 === month;
        var end = new Date(year, month, 1, 0, 0, 0).getTime();
        var falta = num(D.falta);

        container.appendChild(el("span", "tp-kicker", current ? "Cuenta regresiva al cierre" : "Mes " + (MESES[month - 1] || "") + " " + year));
        var clock = el("div", "tp-clock");
        container.appendChild(clock);

        var need = el("div", "tp-need");
        if (falta <= 0) {
            need.className += " tp-ok";
            need.innerHTML = "<b>¡Meta alcanzada!</b> Todo lo que se venda ahora suma por encima del 100%.";
        } else if (remainingDays > 0) {
            need.innerHTML = "Para llegar al 100% necesitan <b>" + money(falta / remainingDays) + " por día</b> en los " +
                remainingDays + " días que quedan.";
        } else {
            need.innerHTML = "Faltaron <b>" + money(falta) + "</b> para el 100% en este mes.";
        }
        container.appendChild(need);

        var streak = rachaConversion(D.diario || []);
        if (streak.dias > 0) {
            var row = el("div", "tp-streak",
                '<svg class="tp-flame" viewBox="0 0 42 54" aria-hidden="true"><path d="M21 2C24 14 36 18 36 34a15 15 0 0 1-30 0c0-8 5-12 8-16 1 6 4 8 6 8-3-8 1-18 1-24z" fill="#e0a96d"/><path d="M21 24c2 6 8 8 8 15a8 8 0 0 1-16 0c0-4 3-6 4-8 1 3 2 4 4 4-1-4 0-8 0-11z" fill="#d95d39"/></svg>' +
                "<div><b>" + streak.dias + "</b> " + (streak.dias === 1 ? "día" : "días seguidos") +
                " con conversión sobre el promedio del mes (" + pct(streak.promedio) + ")</div>");
            container.appendChild(row);
            pauseOffscreen(row);
        }

        var labels = current ? ["DÍAS", "HORAS", "MIN", "SEG"] : ["DÍA CORTE", "DE", "", ""];
        function parts() {
            if (!current) return [String(cutDay).padStart(2, "0"), String(daysInMonth).padStart(2, "0")];
            var s = Math.max(0, Math.floor((end - Date.now()) / 1000));
            return [Math.floor(s / 86400), Math.floor(s / 3600) % 24, Math.floor(s / 60) % 60, s % 60]
                .map(function (x) { return String(x).padStart(2, "0"); });
        }
        function digit(v) {
            return '<span class="tp-dg"><span class="tp-top">' + v + '</span><span class="tp-bot"><span>' + v +
                '</span></span><span class="tp-flipper">' + v + "</span></span>";
        }
        var initial = parts();
        clock.innerHTML = initial.map(function (p, i) {
            return '<div class="tp-unit"><div class="tp-digits">' + p.split("").map(digit).join("") + "</div><small>" +
                labels[i] + "</small></div>" + (i < initial.length - 1 ? '<div class="tp-colon">' + (current ? ":" : "/") + "</div>" : "");
        }).join("");
        if (!current || REDUCE) return;

        var prev = initial.join(""), timer = null;
        function tick() {
            var flat = parts().join("");
            var digits = clock.querySelectorAll(".tp-dg");
            for (var k = 0; k < flat.length; k++) {
                if (flat[k] === prev[k] || !digits[k]) continue;
                digits[k].querySelector(".tp-top").textContent = flat[k];
                digits[k].querySelector(".tp-bot span").textContent = flat[k];
                var flipper = digits[k].querySelector(".tp-flipper");
                flipper.textContent = prev[k];
                flipper.classList.remove("tp-go"); void flipper.offsetWidth; flipper.classList.add("tp-go");
            }
            prev = flat;
        }
        // El reloj solo corre mientras se ve.
        if (HAS_IO) {
            new IntersectionObserver(function (entries) {
                if (entries[0].isIntersecting && !timer) { tick(); timer = setInterval(tick, 1000); }
                if (!entries[0].isIntersecting && timer) { clearInterval(timer); timer = null; }
            }).observe(clock);
        } else {
            timer = setInterval(tick, 1000);
        }
    }

    function rachaConversion(diario) {
        var values = diario.map(function (d) { return num(d.conversion); }).filter(function (v) { return v > 0; });
        if (values.length < 3) return { dias: 0, promedio: 0 };
        var avg = values.reduce(function (a, b) { return a + b; }, 0) / values.length;
        var count = 0;
        for (var i = diario.length - 1; i >= 0; i--) {
            var v = num(diario[i].conversion);
            if (v <= 0) continue;
            if (v >= avg) count++; else break;
        }
        return { dias: count, promedio: avg };
    }

    // -----------------------------------------------------
    // 3 + 4. Carta holográfica y carrera de asesoras
    // -----------------------------------------------------
    function asesorasPremium(D) {
        var section = sectionByTitle("Ranking de asesoras");
        var people = (D.asesoras || []).filter(function (a) { return !a.generico && a.nombre; });
        if (!section || people.length < 2) return;
        people.sort(function (a, b) { return num(b.cump) - num(a.cump) || num(b.venta) - num(a.venta); });
        var wrap = el("div", "tp-grid-asesoras");
        var cardBox = el("div", "");
        var raceBox = el("div", "");
        wrap.appendChild(cardBox); wrap.appendChild(raceBox);
        var header = section.querySelector(".section-header");
        header.parentNode.insertBefore(wrap, header.nextSibling);
        cartaHolografica(cardBox, people[0], D);
        carrera(raceBox, people.slice(0, 8));
    }

    function iniciales(nombre) {
        var parts = String(nombre).trim().split(/\s+/).filter(Boolean);
        return ((parts[0] || "?")[0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
    }

    function cartaHolografica(box, top, D) {
        var mes = MESES[num(D.mes) - 1] || "";
        box.innerHTML =
            '<div class="tp-holo-stage"><div class="tp-holo" role="button" tabindex="0" aria-label="Asesora destacada: ' + escapeHtml(top.nombre) + '">' +
            '<div class="tp-face tp-back">L&amp;H PULSE<br>ASESORA DEL MES</div>' +
            '<div class="tp-face tp-front">' +
            '<div class="tp-rank">#1 · ' + escapeHtml(mes.toUpperCase()) + "</div>" +
            '<div class="tp-avatar">' + escapeHtml(iniciales(top.nombre)) + "</div>" +
            "<h5>" + escapeHtml(top.nombre) + "</h5>" +
            '<div class="tp-store">' + escapeHtml(D.tienda || "") + "</div>" +
            '<div class="tp-stats"><div><b>' + compactMoney(top.venta) + "</b>Venta</div><div><b>" +
            num(top.upt).toFixed(2).replace(".", ",") + "</b>UPT</div><div><b>" + pct(top.cump, 0) + "</b>Meta</div></div>" +
            '<div class="tp-foil"></div><div class="tp-shine"></div></div></div></div>';
        var holo = box.querySelector(".tp-holo");
        var foil = box.querySelector(".tp-foil"), shine = box.querySelector(".tp-shine");
        var toggle = function () { holo.classList.toggle("tp-flipped"); holo.style.transform = ""; };
        holo.addEventListener("click", toggle);
        holo.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
        if (REDUCE) { holo.classList.add("tp-flipped"); return; }
        alVerse(holo, function () { setTimeout(function () { holo.classList.add("tp-flipped"); }, 300); });
        if (!HOVER) return;
        var rect = null, pending = false, px = .5, py = .5;
        holo.addEventListener("pointerenter", function () { rect = holo.getBoundingClientRect(); });
        holo.addEventListener("pointermove", function (e) {
            if (!holo.classList.contains("tp-flipped")) return;
            rect = rect || holo.getBoundingClientRect();
            px = (e.clientX - rect.left) / rect.width; py = (e.clientY - rect.top) / rect.height;
            if (pending) return;
            pending = true;
            requestAnimationFrame(function () {
                pending = false;
                holo.style.transition = "transform .08s linear";
                holo.style.transform = "rotateY(" + (180 + (px - .5) * -26) + "deg) rotateX(" + ((py - .5) * -20) + "deg)";
                foil.style.setProperty("--tp-fx", (100 - px * 100) + "%");
                foil.style.setProperty("--tp-fy", (py * 100) + "%");
                shine.style.setProperty("--tp-sx", (100 - px * 100) + "%");
                shine.style.setProperty("--tp-sy", (py * 100) + "%");
            });
        });
        holo.addEventListener("pointerleave", function () {
            rect = null;
            holo.style.transition = "";
            holo.style.transform = holo.classList.contains("tp-flipped") ? "rotateY(180deg)" : "";
        });
    }

    function carrera(box, people) {
        var maxPct = Math.max.apply(null, people.map(function (p) { return num(p.cump) * 100; }).concat([100]));
        var scale = Math.ceil((maxPct + 8) / 10) * 10;
        var goalLeft = 100 / scale * 100;
        box.appendChild(el("span", "tp-kicker", "Carrera del mes"));
        box.appendChild(el("div", "tp-title", "¿Quién llega primero a la meta?"));
        var race = el("div", "tp-race");
        race.appendChild(el("div", "tp-goal-lbl", "META 100%"));
        box.appendChild(race);
        var rows = people.map(function (p, i) {
            var node = el("div", "tp-runner",
                '<div class="tp-pos">' + (i + 1) + '</div><div class="tp-nm" title="' + escapeHtml(p.nombre) + '">' +
                escapeHtml(p.nombre) + '</div><div class="tp-track"><div class="tp-goal" style="left:' + goalLeft +
                '%"></div><div class="tp-bar"></div></div><div class="tp-pct">0%</div>');
            race.appendChild(node);
            return { node: node, target: num(p.cump) * 100, cur: 0, seed: i * 1.7 + 0.3 };
        });
        var medals = ["🥇", "🥈", "🥉"];
        function paint(t) {
            rows.forEach(function (r) {
                var wobble = t < 1 ? Math.sin(t * 9 + r.seed) * 14 * (1 - t) : 0;
                r.cur = Math.max(0, r.target * ease(t) + wobble);
                var bar = r.node.querySelector(".tp-bar");
                bar.style.width = Math.min(r.cur / scale * 100, 100) + "%";
                bar.classList.toggle("tp-win", r.cur >= 100);
                r.node.querySelector(".tp-pct").textContent = Math.round(r.cur) + "%";
            });
            var height = rows[0].node.getBoundingClientRect().height + 8;
            rows.slice().sort(function (a, b) { return b.cur - a.cur; }).forEach(function (r, i) {
                r.node.style.transform = "translateY(" + ((i - rows.indexOf(r)) * height) + "px)";
                r.node.querySelector(".tp-pos").textContent = i < 3 && t >= 1 ? medals[i] : String(i + 1);
            });
        }
        if (REDUCE) { paint(1); return; }
        paint(0);
        alVerse(race, function () {
            var start = performance.now();
            var step = function () {
                var t = Math.min((performance.now() - start) / 2800, 1);
                paint(t);
                if (t < 1) setTimeout(step, 90);   // ~11 pasos/s: liviano y fluido con la transición CSS
            };
            setTimeout(step, 200);
        });
    }

    // -----------------------------------------------------
    // 5 + 6 + 10. Pulso, embudo y calendario (sección de conversión)
    // -----------------------------------------------------
    function seccionConversion(D) {
        var section = sectionByTitle("Evolución diaria de conversión");
        var diario = (D.diario || []).filter(function (d) { return num(d.dia) > 0; });
        if (!section || diario.length < 3) return;
        var body = section.querySelector(".p-4");
        if (!body) return;
        var pulseBlock = el("div", "tp-block tp-pulse", '<span class="tp-kicker">El pulso de la tienda</span>' +
            '<div class="tp-title">Facturas por día, como un latido</div>');
        var grid = el("div", "tp-grid-2");
        var funnelBlock = el("div", "tp-block", '<span class="tp-kicker">Embudo de clientes</span>' +
            '<div class="tp-title">De cada 100 que entran, ¿cuántos compran?</div>');
        var calBlock = el("div", "tp-block", '<span class="tp-kicker">El mes que se enciende</span>' +
            '<div class="tp-title">Facturas de cada día frente al promedio</div>');
        grid.appendChild(funnelBlock); grid.appendChild(calBlock);
        // Embudo y calendario van después de los indicadores de conversión, antes de la gráfica
        var canvas = body.querySelector("#conversionDiariaChart");
        var antes = canvas ? canvas.parentNode : body.firstChild;
        body.insertBefore(grid, antes);
        grid.style.marginBottom = "24px";
        guard("embudo", function () { embudo(funnelBlock, diario); });
        guard("calendario", function () { calendario(calBlock, diario, D); });
    }

    function pulso(block, diario) {
        var W = 1100, H = 170, base = 118, days = diario.length;
        var values = diario.map(function (d) { return num(d.facturas); });
        var max = Math.max.apply(null, values.concat([1]));
        var step = W / days, d = "M0 " + base, beats = [];
        var sorted = values.slice().sort(function (a, b) { return b - a; });
        var highlighted = Math.min(days, Math.max(2, Math.round(days * 0.15)));
        var threshold = sorted[highlighted - 1] || max;
        values.forEach(function (v, i) {
            var x = i * step + step * .5, amp = v / max * 98, w = Math.min(14, step * .45);
            d += " L" + (x - w) + " " + base + " L" + (x - w / 2) + " " + (base + 9) + " L" + x + " " + (base - amp) +
                " L" + (x + w / 2) + " " + (base + 12) + " L" + (x + w) + " " + base;
            if (v >= threshold && v > 0) beats.push([x, base - amp, diario[i].dia, v]);
        });
        d += " L" + W + " " + base;
        var svg = '<svg viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="none" role="img" aria-label="Facturas por día">' +
            '<line x1="0" y1="' + base + '" x2="' + W + '" y2="' + base + '" stroke="rgba(139,125,107,.2)"/>' +
            '<path class="tp-pulse-glow" d="' + d + '"/><path class="tp-pulse-path" d="' + d + '"/>' +
            beats.map(function (b) {
                return '<circle class="tp-ring" cx="' + b[0] + '" cy="' + b[1] + '" r="6"/>' +
                    '<circle class="tp-beat" cx="' + b[0] + '" cy="' + b[1] + '" r="6" style="transform-origin:' + b[0] + "px " + b[1] + 'px"><title>Día ' +
                    b[2] + ": " + NUM.format(b[3]) + " facturas</title></circle>" +
                    '<text class="tp-lbl" x="' + b[0] + '" y="' + (H - 6) + '" text-anchor="middle">día ' + b[2] + "</text>";
            }).join("") + "</svg>";
        block.insertAdjacentHTML("beforeend", svg);
        block.insertAdjacentHTML("beforeend", '<p class="tp-note">Los puntos dorados son los días con más facturas del mes.</p>');
        var paths = block.querySelectorAll(".tp-pulse-path, .tp-pulse-glow");
        var len = paths[1].getTotalLength();
        paths.forEach(function (p) { p.style.strokeDasharray = len; p.style.strokeDashoffset = REDUCE ? 0 : len; });
        var dots = block.querySelectorAll(".tp-beat"), rings = block.querySelectorAll(".tp-ring");
        if (REDUCE) { dots.forEach(function (b) { b.classList.add("tp-show"); }); return; }
        alVerse(block, function () {
            var start = null;
            loopVisible(block, function (now) {
                if (start === null) start = now;
                var t = Math.min((now - start) / 2800, 1), off = len * (1 - t);
                paths.forEach(function (p) { p.style.strokeDashoffset = off; });
                dots.forEach(function (b, k) {
                    if (!b.classList.contains("tp-show") && +b.getAttribute("cx") / W <= t) {
                        b.classList.add("tp-show"); rings[k].classList.add("tp-show");
                    }
                });
                return t < 1;
            });
        });
    }

    function embudo(block, diario) {
        var traffic = diario.reduce(function (s, d) { return s + num(d.trafico); }, 0);
        var invoices = diario.reduce(function (s, d) { return s + num(d.facturas); }, 0);
        var conversion = traffic > 0 ? Math.min(invoices / traffic, 1) : 0;
        var canvas = el("canvas", "tp-funnel");
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", "Conversión del mes " + pct(conversion));
        block.appendChild(canvas);
        var stats = el("div", "tp-funnel-stats",
            '<div><b data-k="t">0</b>visitantes</div><div><b data-k="f">0</b>compraron</div><div><b data-k="c">0%</b>conversión</div>');
        block.appendChild(stats);
        var final = function () {
            stats.querySelector('[data-k="t"]').textContent = NUM.format(traffic);
            stats.querySelector('[data-k="f"]').textContent = NUM.format(invoices);
            stats.querySelector('[data-k="c"]').textContent = pct(conversion);
        };
        var size = hiDPI(canvas, canvas.clientWidth || block.clientWidth - 36, .5);
        var ctx = size.ctx, W = size.w, H = size.h, k = W / 1000;
        function scene() {
            ctx.clearRect(0, 0, W, H);
            ctx.fillStyle = "#efe7da"; ctx.beginPath();
            ctx.moveTo(300 * k, 60 * k); ctx.lineTo(620 * k, 200 * k); ctx.lineTo(620 * k, 300 * k); ctx.lineTo(300 * k, 440 * k);
            ctx.closePath(); ctx.fill();
            ctx.fillStyle = "#0d5c75"; ctx.fillRect(290 * k, 50 * k, 14 * k, 400 * k);
            ctx.fillStyle = "#083f51"; ctx.font = "700 " + Math.round(22 * k) + "px Inter, system-ui, sans-serif";
            ctx.textAlign = "center"; ctx.fillText("PUERTA", 297 * k, 38 * k);
            ctx.fillStyle = "#c5a880"; ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(800 * k, 190 * k, 150 * k, 120 * k, 16 * k); else ctx.rect(800 * k, 190 * k, 150 * k, 120 * k);
            ctx.fill();
            ctx.fillStyle = "#3b2a10"; ctx.font = "800 " + Math.round(24 * k) + "px Inter, system-ui, sans-serif";
            ctx.fillText("CAJA", 875 * k, 258 * k);
        }
        scene();
        if (REDUCE || traffic <= 0) { final(); return; }
        alVerse(block, function () {
            var people = [], start = null, last = null, seen = 0, bought = 0;
            var tEl = stats.querySelector('[data-k="t"]'), fEl = stats.querySelector('[data-k="f"]'), cEl = stats.querySelector('[data-k="c"]');
            loopVisible(block, function (now) {
                if (start === null) { start = last = now; }
                var dt = Math.min((now - last) / 16.7, 6); last = now;
                var elapsed = now - start;
                for (var s = 0; s < Math.round(dt); s++) {
                    if (elapsed < 5000 && Math.random() < .5) {
                        people.push({ x: -10 * k, y: (120 + Math.random() * 260) * k, vx: (3 + Math.random() * 2) * k,
                            buy: Math.random() < conversion, phase: 0 });
                    }
                }
                scene();
                people.forEach(function (p) {
                    if (p.x > 300 * k && p.phase === 0) { p.phase = 1; seen++; }
                    if (p.phase === 1 && p.x > 620 * k) {
                        if (p.buy) { p.phase = 2; bought++; } else { p.phase = 3; p.vy = (p.y < 250 * k ? -1 : 1) * 2.5 * k; }
                    }
                    if (p.phase === 2) {
                        p.x += (875 * k - p.x) * Math.min(.06 * dt, 1); p.y += (250 * k - p.y) * Math.min(.06 * dt, 1);
                        if (Math.abs(875 * k - p.x) < 4 * k) p.gone = true;
                    } else if (p.phase === 3) { p.x += p.vx * .6 * dt; p.y += p.vy * dt; }
                    else { p.x += p.vx * dt; if (p.phase === 1) p.y += (250 * k - p.y) * Math.min(.015 * dt, 1); }
                    ctx.beginPath(); ctx.arc(p.x, p.y, (p.phase === 2 ? 8 : 6) * k, 0, 7);
                    ctx.fillStyle = p.phase === 2 ? "#e0a96d" : p.phase === 3 ? "rgba(107,98,89,.35)" : "#0d5c75";
                    ctx.fill();
                });
                people = people.filter(function (p) { return !p.gone && p.y > -20 && p.y < H + 20 && p.x < W + 20; });
                // Los contadores llegan a los totales reales del mes.
                var t = Math.min(elapsed / 5600, 1);
                tEl.textContent = NUM.format(traffic * ease(t));
                fEl.textContent = NUM.format(invoices * ease(t));
                cEl.textContent = pct(seen ? Math.min(bought / seen, 1) * (1 - t) + conversion * t : 0);
                if (elapsed > 8000 && !people.length) { scene(); final(); return false; }
                return true;
            });
        });
    }

    function calendario(block, diario, D) {
        var year = num(D.anio), month = num(D.mes);
        var daysInMonth = new Date(year, month, 0).getDate() || 31;
        var firstDow = (new Date(year, month - 1, 1).getDay() + 6) % 7;   // lunes = 0
        var byDay = {};
        diario.forEach(function (d) { byDay[num(d.dia)] = num(d.facturas); });
        var values = Object.keys(byDay).map(function (k) { return byDay[k]; }).filter(function (v) { return v > 0; });
        var avg = values.length ? values.reduce(function (a, b) { return a + b; }, 0) / values.length : 0;
        var best = -1, bestValue = -1;
        Object.keys(byDay).forEach(function (k) { if (byDay[k] > bestValue) { bestValue = byDay[k]; best = num(k); } });
        var cal = el("div", "tp-cal");
        ["L", "M", "M", "J", "V", "S", "D"].forEach(function (h) { cal.appendChild(el("div", "tp-h", h)); });
        for (var i = 0; i < firstDow; i++) cal.appendChild(el("div", ""));
        var cells = [];
        for (var day = 1; day <= daysInMonth; day++) {
            var cell = el("div", "tp-day", String(day));
            var v = byDay[day];
            if (v != null) {
                cell.title = "Día " + day + ": " + NUM.format(v) + " facturas";
                cells.push([cell, v, day]);
            }
            cal.appendChild(cell);
        }
        block.appendChild(cal);
        block.appendChild(el("div", "tp-legend",
            '<span><i style="background:#d95d39"></i>bajo el promedio</span><span><i style="background:#e0a96d"></i>en el promedio</span>' +
            '<span><i style="background:#2d6a4f"></i>sobre el promedio</span><span><i style="background:#c5a880"></i>mejor día</span>'));
        function light(c) {
            var v = c[1], node = c[0];
            node.classList.add("tp-on");
            node.style.background = c[2] === best ? "#c5a880" : v >= avg * 1.1 ? "#2d6a4f" : v >= avg * .9 ? "#e0a96d" : "#d95d39";
            if (c[2] === best) node.classList.add("tp-best");
        }
        if (REDUCE) { cells.forEach(light); return; }
        alVerse(block, function () {
            var start = performance.now();
            var step = function () {
                var elapsed = performance.now() - start;
                cells.forEach(function (c, i) { if (!c[0].classList.contains("tp-on") && elapsed >= i * 65) light(c); });
                if (cells.some(function (c) { return !c[0].classList.contains("tp-on"); })) setTimeout(step, 60);
            };
            step();
        });
    }

    // -----------------------------------------------------
    // 7 + 8. Tiquete y etiquetas colgantes
    // -----------------------------------------------------
    function clientePromedio(D) {
        var anchor = kpiByTitle("FALTA PARA LA META") || sectionByTitle("Evolución de ventas");
        var row = anchor ? anchor.closest(".row") : null;
        if (!row) return;
        var section = el("div", "tp-grid-2");
        section.style.marginBottom = "24px";
        var receiptBlock = el("div", "tp-block", '<span class="tp-kicker">El tiquete que se imprime</span>' +
            '<div class="tp-title">Así compra el cliente promedio de la tienda</div>');
        var tagsBlock = el("div", "tp-block", '<span class="tp-kicker">Etiquetas del día</span>' +
            '<div class="tp-title">Los números que cuelgan de la vitrina</div>');
        section.appendChild(receiptBlock); section.appendChild(tagsBlock);
        row.parentNode.insertBefore(section, row.nextSibling);
        guard("tiquete", function () { tiquete(receiptBlock, D); });
        guard("etiquetas", function () { etiquetas(tagsBlock, D); });
    }

    function tiquete(block, D) {
        var ticket = num(D.ticket), upt = num(D.upt);
        var lines = (D.lineas || []).filter(function (l) { return num(l.venta) > 0; });
        var total = lines.reduce(function (s, l) { return s + num(l.venta); }, 0);
        lines.sort(function (a, b) { return num(b.venta) - num(a.venta); });
        var items = lines.slice(0, 4).map(function (l) {
            var name = String(l.linea || "").toLowerCase().replace(/(^|\s|-)\S/g, function (c) { return c.toUpperCase(); });
            return '<div class="tp-r"><span>' + escapeHtml(name) + "</span><span>" + money(ticket * num(l.venta) / total) + "</span></div>";
        }).join("");
        var mes = (MESES[num(D.mes) - 1] || "").slice(0, 3).toUpperCase();
        block.insertAdjacentHTML("beforeend",
            '<div class="tp-printer"><div class="tp-slot"></div><div class="tp-receipt">' +
            '<div class="tp-c"><b>L&amp;H · ' + escapeHtml(String(D.tienda || "").toUpperCase()) + "</b><br>CLIENTE PROMEDIO · " + mes + " " + num(D.anio) + "</div><hr>" +
            (items || '<div class="tp-c">Sin detalle por línea</div>') + "<hr>" +
            '<div class="tp-r"><span>Unidades (UPT)</span><span>' + upt.toFixed(2).replace(".", ",") + "</span></div>" +
            '<div class="tp-r"><span>Facturas del mes</span><span>' + NUM.format(num(D.facturas)) + "</span></div>" +
            '<div class="tp-r tp-tot"><span>TICKET PROM.</span><span>' + money(ticket) + "</span></div><hr>" +
            '<div class="tp-c">¡Gracias por vender con L&amp;H!</div></div></div>' +
            '<p class="tp-note">Cada línea muestra cuánto del ticket promedio corresponde a esa línea según su venta del mes.</p>');
        var receipt = block.querySelector(".tp-receipt");
        if (REDUCE) return;
        alVerse(block, function () { receipt.classList.add("tp-print"); });
    }

    function etiquetas(block, D) {
        var diario = D.diario || [];
        var traffic = diario.reduce(function (s, d) { return s + num(d.trafico); }, 0);
        var invoices = diario.reduce(function (s, d) { return s + num(d.facturas); }, 0);
        var days = diario.filter(function (d) { return num(d.trafico) > 0 || num(d.facturas) > 0; }).length || 1;
        var data = [
            ["VENTA / DÍA", compactMoney(D.venta_dia), num(D.cumplimiento) >= 1],
            ["FACTURAS / DÍA", NUM.format(Math.round(invoices / days)), false],
            ["PERSONAS / DÍA", traffic > 0 ? NUM.format(Math.round(traffic / days)) : "—", false],
        ];
        var holder = el("div", "tp-tags");
        block.appendChild(holder);
        var tags = data.map(function (d, i) {
            var node = el("div", "tp-hang" + (d[2] ? " tp-gold" : ""),
                '<div class="tp-string"></div><div class="tp-label"><small>' + d[0] + "</small><b>" + d[1] + "</b></div>");
            holder.appendChild(node);
            return { node: node, a: 0, v: 0, held: false };
        });
        block.appendChild(el("p", "tp-note", "Pasa el mouse o arrástralas: se balancean como etiquetas de verdad."));
        if (REDUCE) return;
        var running = null, last = 0;
        function wake() {
            if (running) return;
            last = performance.now();
            running = loopVisible(block, function (now) {
                var steps = Math.min(Math.round((now - last) / 16.7), 8); last = now;
                var energy = 0;
                tags.forEach(function (t) {
                    for (var s = 0; s < steps && !t.held; s++) { t.v += -0.045 * t.a; t.v *= 0.985; t.a += t.v; }
                    t.node.style.transform = "rotate(" + t.a + "deg)";
                    energy += Math.abs(t.a) + Math.abs(t.v) + (t.held ? 1 : 0);
                });
                if (energy < 0.05) { running = null; return false; }   // en reposo: el bucle se apaga
                return true;
            });
        }
        tags.forEach(function (t, i) {
            t.node.addEventListener("pointerenter", function (e) { t.v += ((e.movementX || 2) * .35); wake(); });
            t.node.addEventListener("pointerdown", function (e) {
                t.held = true; t.node.setPointerCapture(e.pointerId); wake();
                var move = function (ev) {
                    var r = t.node.getBoundingClientRect();
                    t.a = Math.max(-45, Math.min(45, (ev.clientX - (r.left + r.width / 2)) * .4)); t.v = 0;
                };
                var up = function () {
                    t.held = false;
                    t.node.removeEventListener("pointermove", move); t.node.removeEventListener("pointerup", up);
                    t.node.removeEventListener("pointercancel", up);
                };
                t.node.addEventListener("pointermove", move); t.node.addEventListener("pointerup", up);
                t.node.addEventListener("pointercancel", up);
            });
        });
        alVerse(block, function () {
            tags.forEach(function (t, i) { t.v = (i % 2 ? -1 : 1) * (1.6 + i * .5); });
            wake();
        });
    }

    // -----------------------------------------------------
    // 9. Costura en las tarjetas de indicadores
    // -----------------------------------------------------
    function costura() {
        if (REDUCE) return;
        var rows = document.querySelectorAll(".kpi-card");
        Array.prototype.forEach.call(rows, function (card, index) {
            if (card.closest(".tp-block")) return;
            alVerse(card, function () {
                var w = card.offsetWidth, h = card.offsetHeight;
                if (w < 40 || h < 40) return;
                var ns = "http://www.w3.org/2000/svg";
                var svg = document.createElementNS(ns, "svg");
                svg.setAttribute("class", "tp-stitch-svg");
                svg.setAttribute("viewBox", "0 0 " + w + " " + h);
                svg.setAttribute("aria-hidden", "true");
                var radius = parseFloat(getComputedStyle(card).borderTopLeftRadius) || 12;
                var rect = document.createElementNS(ns, "rect");
                rect.setAttribute("x", 6); rect.setAttribute("y", 6);
                rect.setAttribute("width", w - 12); rect.setAttribute("height", h - 12);
                rect.setAttribute("rx", Math.max(radius - 5, 4));
                var needle = document.createElementNS(ns, "circle");
                needle.setAttribute("class", "tp-needle"); needle.setAttribute("r", 4);
                svg.appendChild(rect); svg.appendChild(needle);
                card.appendChild(svg);
                var len = rect.getTotalLength();
                var start = null, delay = (index % 4) * 180;
                loopVisible(card, function (now) {
                    if (start === null) start = now + delay;
                    var t = Math.max(0, Math.min((now - start) / 1400, 1));
                    var drawn = len * ease(t), n = Math.floor(drawn / 13), dash = [];
                    for (var i = 0; i < n; i++) dash.push(7, 6);
                    dash.push(Math.max(drawn - n * 13, 0.01), len + 20);
                    rect.setAttribute("stroke-dasharray", dash.join(" "));
                    var point = rect.getPointAtLength(drawn);
                    needle.setAttribute("cx", point.x); needle.setAttribute("cy", point.y);
                    needle.style.opacity = t < 1 ? 1 : 0;
                    if (t >= 1) { svg.classList.add("tp-done"); return false; }
                    return true;
                });
            });
        });
    }

    // -----------------------------------------------------
    // 12. Skyline de líneas
    // -----------------------------------------------------
    function skyline(D) {
        var section = sectionByTitle("Desempeño por línea");
        var lines = (D.lineas || []).filter(function (l) { return num(l.venta) > 0 || num(l.meta) > 0; });
        if (!section || lines.length < 2) return;
        var body = section.querySelector(".p-4");
        if (!body) return;
        var block = el("div", "", "");
        block.style.marginBottom = "20px";
        var canvas = el("canvas", "tp-sky");
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", "Cumplimiento por línea: " + lines.map(function (l) {
            return l.linea + " " + pct(l.cump);
        }).join(", "));
        block.appendChild(canvas);
        block.appendChild(el("p", "tp-note", "Cada edificio es una línea: su altura es la venta y las ventanas encendidas su cumplimiento. Dorado = meta superada."));
        body.insertBefore(block, body.firstChild);
        var skyWidth = canvas.clientWidth || body.clientWidth - 48;
        var size = hiDPI(canvas, skyWidth, skyWidth < 560 ? .6 : .26);
        var ctx = size.ctx, W = size.w, H = size.h;
        var maxSale = Math.max.apply(null, lines.map(function (l) { return num(l.venta); }).concat([1]));
        var stars = [];
        for (var i = 0; i < 60; i++) stars.push([Math.random() * W, Math.random() * H * .45, Math.random()]);
        var ground = Math.max(30, H * .12);
        function frame(now, t) {
            var e = ease(t);
            var g = ctx.createLinearGradient(0, 0, 0, H);
            g.addColorStop(0, "#083f51"); g.addColorStop(1, "#1d4f60");
            ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
            stars.forEach(function (s) {
                ctx.fillStyle = "rgba(253,251,247," + (.25 + .5 * Math.abs(Math.sin(now / 900 + s[2] * 6))) + ")";
                ctx.fillRect(s[0], s[1], 2, 2);
            });
            ctx.fillStyle = "rgba(224,169,109,.9)"; ctx.beginPath(); ctx.arc(W - H * .32, H * .21, H * .09, 0, 7); ctx.fill();
            ctx.fillStyle = "#13485a"; ctx.beginPath(); ctx.arc(W - H * .28, H * .19, H * .085, 0, 7); ctx.fill();
            ctx.fillStyle = "#04232e"; ctx.fillRect(0, H - ground, W, ground);
            var n = lines.length, bw = Math.min(W / (n * 1.6), 220), gap = (W - bw * n) / (n + 1);
            var fontLbl = Math.max(11, Math.min(15, bw / 8));
            lines.forEach(function (l, idx) {
                var cump = num(l.cump), win = cump >= 1;
                var x = gap + idx * (bw + gap), hmax = (H - ground - 40) * Math.max(num(l.venta) / maxSale, .12);
                var h = hmax * e, y = H - ground - h;
                ctx.fillStyle = win ? "#c5a880" : "#0d5c75"; ctx.fillRect(x, y, bw, h);
                ctx.fillStyle = win ? "#a8842f" : "#0a4a5f"; ctx.fillRect(x + bw * .93, y, bw * .07, h);
                var cols = Math.max(2, Math.floor(bw / 30)), rowsN = Math.max(1, Math.floor(hmax / 22));
                var lit = Math.floor(cols * rowsN * Math.min(cump, 1) * Math.min(1, t * 1.3)), k = 0;
                var ww = (bw * .8) / cols;
                for (var r = 0; r < rowsN; r++) {
                    for (var c = 0; c < cols; c++) {
                        var wy = H - ground - 16 - r * 22;
                        if (wy < y + 6) continue;
                        ctx.fillStyle = k++ < lit ? (win ? "#fff4d6" : "#f4e3c1") : "rgba(0,0,0,.2)";
                        ctx.fillRect(x + bw * .08 + c * ww, wy, ww * .62, 11);
                    }
                }
                ctx.textAlign = "center";
                ctx.fillStyle = "#fdfbf7"; ctx.font = "800 " + fontLbl + "px Inter, system-ui, sans-serif";
                var name = String(l.linea || "").slice(0, 14);
                ctx.fillText(name, x + bw / 2, H - ground / 2 + fontLbl / 3);
                ctx.fillStyle = win ? "#f4e3c1" : "#cfe3ea"; ctx.font = "700 " + fontLbl + "px " + "JetBrains Mono, Consolas, monospace";
                ctx.fillText(Math.round(cump * 100 * e) + "%", x + bw / 2, y - 8);
            });
        }
        if (REDUCE) { frame(0, 1); return; }
        frame(0, 0);
        alVerse(canvas, function () {
            var start = null;
            loopVisible(canvas, function (now) {
                if (start === null) start = now;
                var t = Math.min((now - start) / 2400, 1);
                frame(now, t);
                return now - start < 7000;      // las estrellas titilan unos segundos y se detiene
            });
        });
    }

    // -----------------------------------------------------
    // Podio Top 3
    // -----------------------------------------------------
    function podio() {
        var pp = document.querySelector(".pp");
        if (!pp || REDUCE) return;
        var steps = Array.prototype.slice.call(pp.querySelectorAll(".pp-step"));
        if (!steps.length) return;
        pp.classList.add("pp-armed");
        steps.forEach(function (s) {
            var pctNode = s.querySelector(".pp-pct");
            if (pctNode) pctNode.textContent = "0,0%";
        });

        // Si la ceremonia del Top 3 está en pantalla, se espera a que cierre.
        function afterOverlay(cb) {
            var overlay = document.getElementById("top3StoresOverlay");
            if (!overlay || !overlay.classList.contains("active") || overlay.classList.contains("closing")) { cb(); return; }
            setTimeout(function () { afterOverlay(cb); }, 300);
        }

        alVerse(pp, function () {
            // La ceremonia se activa al terminar de cargar: se le da un instante.
            setTimeout(function () { afterOverlay(entrar); }, 250);
        });

        function entrar() {
            {
                // Un cuadro entre "armado" y "entrada" para que corran las transiciones.
                void pp.offsetWidth;
                setTimeout(function () { pp.classList.add("pp-in"); }, 30);
                var delays = { "1": 900, "2": 620, "3": 380 };
                steps.forEach(function (s) {
                    var pos = (s.className.match(/pp-p(\d)/) || [])[1];
                    var pctNode = s.querySelector(".pp-pct");
                    var target = num(pctNode && pctNode.getAttribute("data-target"));
                    setTimeout(function () { contar(pctNode, target); }, delays[pos] || 400);
                });
                setTimeout(function () { confetiPodio(pp); }, 1500);
            }
        }

        // Halo del 1.º lugar: se pausa fuera de pantalla.
        if (HAS_IO) {
            new IntersectionObserver(function (entries) {
                pp.classList.toggle("pp-paused", !entries[0].isIntersecting);
            }).observe(pp);
        }

        // Inclinación 3D al pasar el mouse (solo en equipos con mouse).
        if (!HOVER) return;
        steps.forEach(function (s) {
            var card = s.querySelector(".pp-card");
            var pending = false, rx = 0, ry = 0;
            s.addEventListener("pointermove", function (e) {
                var r = card.getBoundingClientRect();
                ry = ((e.clientX - r.left) / r.width - .5) * 14;
                rx = ((e.clientY - r.top) / r.height - .5) * -12;
                if (pending) return;
                pending = true;
                requestAnimationFrame(function () {
                    pending = false;
                    card.style.setProperty("--pp-rx", rx.toFixed(2) + "deg");
                    card.style.setProperty("--pp-ry", ry.toFixed(2) + "deg");
                });
            });
            s.addEventListener("pointerleave", function () {
                card.style.setProperty("--pp-rx", "0deg");
                card.style.setProperty("--pp-ry", "0deg");
            });
        });
    }

    function contar(node, target) {
        if (!node) return;
        var start = performance.now(), dur = 1100;
        var step = function () {
            var t = Math.min((performance.now() - start) / dur, 1);
            node.textContent = (target * ease(t)).toFixed(1).replace(".", ",") + "%";
            if (t < 1) setTimeout(step, 33);
        };
        step();
    }

    function confetiPodio(pp) {
        var canvas = pp.querySelector(".pp-confetti");
        var first = pp.querySelector(".pp-p1 .pp-card");
        if (!canvas || !first) return;
        var stage = canvas.parentElement.getBoundingClientRect();
        var size = hiDPI(canvas, stage.width, stage.height / Math.max(stage.width, 1));
        var ctx = size.ctx, W = size.w, H = size.h;
        var c = first.getBoundingClientRect();
        var ox = c.left - stage.left + c.width / 2, oy = c.top - stage.top + 10;
        var colors = ["#c5a880", "#e0a96d", "#0d5c75", "#2d6a4f", "#f4e3c1", "#d95d39"];
        var pieces = [];
        for (var i = 0; i < 110; i++) {
            var angle = -Math.PI / 2 + (Math.random() - .5) * 2.2;
            var speed = 5 + Math.random() * 7;
            pieces.push({ x: ox, y: oy, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
                w: 5 + Math.random() * 5, h: 8 + Math.random() * 7, rot: Math.random() * 6, vr: (Math.random() - .5) * .35,
                color: colors[i % colors.length] });
        }
        var start = null, last = null, dur = 2800;
        loopVisible(pp, function (now) {
            if (start === null) start = last = now;
            var dt = Math.min((now - last) / 16.7, 4); last = now;
            var t = now - start;
            ctx.clearRect(0, 0, W, H);
            ctx.globalAlpha = t > dur - 700 ? Math.max((dur - t) / 700, 0) : 1;
            pieces.forEach(function (p) {
                p.vy += .22 * dt; p.vx *= Math.pow(.99, dt);
                p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.vr * dt;
                ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.rot)));
                ctx.restore();
            });
            if (t >= dur) { ctx.clearRect(0, 0, W, H); return false; }
            return true;
        });
    }

    // -----------------------------------------------------
    // Inicio
    // -----------------------------------------------------
    function guard(name, fn) {
        try { fn(); } catch (error) { console.error("tienda_premium:", name, error); }
    }

    var D = leerDatos();
    if (!D) return;
    // El tablero se monta de inmediato, antes de tienda_animaciones.js, para
    // que el contador de ese archivo no compita con los dígitos.
    guard("tablero", function () { tableroAeropuerto(D); });
    guard("podio", podio);

    function iniciar() {
        guard("bolsa y reloj", function () { bolsaYReloj(D); });
        guard("cliente promedio", function () { clientePromedio(D); });
        guard("conversión", function () { seccionConversion(D); });
        guard("skyline", function () { skyline(D); });
        guard("asesoras", function () { asesorasPremium(D); });
        guard("costura", costura);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar);
    } else {
        iniciar();
    }
})();
