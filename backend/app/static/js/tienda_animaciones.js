/* =========================================================
   L&H PULSE - Animaciones del dashboard de tienda
   1. Números que cuentan hasta su valor
   2. Barras de cumplimiento que se llenan (dorado si >= 100%)
   3. Medidor circular de meta + días al cierre
   4. Insignias de asesoras (mejor ticket, UPT y avance)
   5. Celebración (confeti) al cumplir la meta o quedar en el top 3
   ========================================================= */
(function () {
    "use strict";

    var sinMovimiento = false /* Las animaciones se muestran siempre, aunque Windows tenga apagadas las animaciones. */;

    function alVerse(elementos, callback) {
        if (!("IntersectionObserver" in window) || sinMovimiento) {
            elementos.forEach(callback);
            return;
        }
        var obs = new IntersectionObserver(function (entradas) {
            entradas.forEach(function (e) {
                if (e.isIntersecting) {
                    obs.unobserve(e.target);
                    callback(e.target);
                }
            });
        }, { threshold: 0.25 });
        elementos.forEach(function (el) { obs.observe(el); });
    }

    function suavizar(t) { return 1 - Math.pow(1 - t, 3); }

    function formatear(valor, decimales) {
        return valor.toLocaleString("en-US", {
            minimumFractionDigits: decimales,
            maximumFractionDigits: decimales
        });
    }

    // -----------------------------------------------------
    // 1. Números animados
    // -----------------------------------------------------
    function prepararNumeros() {
        var selectores = ".kpi-value, .compliance-value, .meta-number, .secondary-kpi strong, .progress-header > strong";
        var elementos = Array.prototype.slice.call(document.querySelectorAll(selectores))
            .filter(function (el) { return el.children.length === 0; });

        var animables = [];
        elementos.forEach(function (el) {
            var texto = el.textContent.trim();
            var m = texto.match(/^([^\d\-]*?)(-?)([\d,]*\.?\d+)([^\d]*)$/);
            if (!m) return;
            var numero = parseFloat(m[3].replace(/,/g, ""));
            if (isNaN(numero)) return;
            var decimales = (m[3].split(".")[1] || "").length;
            el.dataset.taOriginal = texto;
            el._ta = {
                prefijo: m[1] + m[2],
                sufijo: m[4],
                valor: numero,
                decimales: decimales
            };
            if (!sinMovimiento) {
                el.textContent = el._ta.prefijo + formatear(0, decimales) + el._ta.sufijo;
            }
            animables.push(el);
        });

        alVerse(animables, function (el) {
            var d = el._ta;
            if (sinMovimiento) { el.textContent = el.dataset.taOriginal; return; }
            var duracion = 1300, inicio = null;
            function paso(ts) {
                if (!inicio) inicio = ts;
                var t = Math.min((ts - inicio) / duracion, 1);
                el.textContent = d.prefijo + formatear(d.valor * suavizar(t), d.decimales) + d.sufijo;
                if (t < 1) requestAnimationFrame(paso);
                else el.textContent = el.dataset.taOriginal;
            }
            requestAnimationFrame(paso);
        });
    }

    // -----------------------------------------------------
    // 2. Barras de progreso
    // -----------------------------------------------------
    function prepararBarras() {
        var barras = Array.prototype.slice.call(document.querySelectorAll(".progress .progress-bar, .progress-track .progress-fill"));
        barras.forEach(function (barra) {
            var destino = barra.style.width;
            if (!destino) return;
            barra.dataset.taDestino = destino;
            var llena = parseFloat(destino) >= 100;
            if (llena && barra.classList.contains("bg-success")) {
                barra.classList.add("ta-barra-oro");
            } else if (llena && barra.classList.contains("progress-fill")) {
                barra.classList.add("ta-barra-brillo");
            }
            if (!sinMovimiento) {
                barra.classList.add("ta-barra");
                barra.style.width = "0%";
            }
        });
        alVerse(barras.filter(function (b) { return b.dataset.taDestino; }), function (barra) {
            requestAnimationFrame(function () { barra.style.width = barra.dataset.taDestino; });
        });
    }

    // -----------------------------------------------------
    // 3. Medidor circular
    // -----------------------------------------------------
    function prepararMedidor() {
        var caja = document.getElementById("taMedidor");
        if (!caja) return;

        var valor = parseFloat(caja.dataset.valor) || 0;
        var anio = parseInt(caja.dataset.anio, 10);
        var mes = parseInt(caja.dataset.mes, 10);
        var dia = parseInt(caja.dataset.dia, 10) || 0;
        var falta = parseFloat(caja.dataset.falta) || 0;

        var medidor = caja.querySelector(".ta-medidor");
        var arco = caja.querySelector(".ta-arco");
        var texto = caja.querySelector(".ta-medidor-valor");
        var radio = 52, circ = 2 * Math.PI * radio;

        medidor.classList.add(valor >= 1 ? "ta-superado" : valor >= 0.9 ? "ta-cerca" : "ta-bajo");

        arco.style.strokeDasharray = circ.toFixed(2);
        arco.style.strokeDashoffset = circ.toFixed(2);

        // Días del mes y días que faltan
        var diasMes = (anio && mes) ? new Date(anio, mes, 0).getDate() : 30;
        if (!dia) dia = diasMes;
        var faltanDias = Math.max(diasMes - dia, 0);
        var elDias = caja.querySelector("[data-ta='dias']");
        var elRitmo = caja.querySelector("[data-ta='ritmo']");
        var elBarraDias = caja.querySelector(".ta-dias > span");

        if (elDias) {
            elDias.innerHTML = faltanDias > 0
                ? "Día <strong>" + dia + "</strong> de " + diasMes + " · faltan <strong>" + faltanDias + "</strong> " + (faltanDias === 1 ? "día" : "días")
                : "Día <strong>" + dia + "</strong> de " + diasMes + " · <strong>último día del mes</strong>";
        }
        if (elRitmo) {
            if (falta > 0 && faltanDias > 0) {
                elRitmo.innerHTML = "Necesitan <strong>$" + formatear(falta / faltanDias, 0) + "</strong> por día para llegar al 100%";
            } else if (falta > 0) {
                elRitmo.innerHTML = "Faltan <strong>$" + formatear(falta, 0) + "</strong> para llegar al 100%";
            } else {
                elRitmo.innerHTML = "<strong>¡Meta alcanzada!</strong> Todo lo que venga suma";
            }
        }

        alVerse([caja], function () {
            var porcentaje = Math.min(valor, 1);
            requestAnimationFrame(function () {
                arco.style.strokeDashoffset = (circ * (1 - porcentaje)).toFixed(2);
                if (elBarraDias) elBarraDias.style.width = (dia / diasMes * 100).toFixed(1) + "%";
            });
            var final = (valor * 100).toFixed(1) + "%";
            if (sinMovimiento) { texto.textContent = final; return; }
            var inicio = null, duracion = 1600;
            function paso(ts) {
                if (!inicio) inicio = ts;
                var t = Math.min((ts - inicio) / duracion, 1);
                texto.textContent = (valor * 100 * suavizar(t)).toFixed(1) + "%";
                if (t < 1) requestAnimationFrame(paso); else texto.textContent = final;
            }
            requestAnimationFrame(paso);
        });
    }

    // -----------------------------------------------------
    // 4. Insignias de asesoras
    // -----------------------------------------------------
    function prepararInsignias() {
        var filas = Array.prototype.slice.call(document.querySelectorAll("tr[data-ta-asesora]"))
            .filter(function (f) { return f.dataset.generico !== "1"; });
        if (filas.length < 2) return;

        var premios = [
            { campo: "cump", clase: "", texto: "🚀 Mayor avance", titulo: "Mayor cumplimiento al corte" },
            { campo: "ticket", clase: "ta-ticket", texto: "💎 Mejor ticket", titulo: "Ticket promedio más alto" },
            { campo: "upt", clase: "ta-upt", texto: "🛍️ Mejor UPT", titulo: "Más unidades por factura" }
        ];

        premios.forEach(function (p, i) {
            var mejor = null, mejorValor = 0;
            filas.forEach(function (f) {
                var v = parseFloat(f.dataset[p.campo]) || 0;
                if (v > mejorValor) { mejorValor = v; mejor = f; }
            });
            if (!mejor) return;
            var celda = mejor.querySelector(".advisor-name");
            if (!celda) return;
            var cont = celda.parentNode.querySelector(".ta-insignias");
            if (!cont) {
                cont = document.createElement("div");
                cont.className = "ta-insignias";
                celda.parentNode.appendChild(cont);
            }
            var s = document.createElement("span");
            s.className = "ta-insignia " + p.clase;
            s.textContent = p.texto;
            s.title = p.titulo;
            s.style.animationDelay = (0.4 + i * 0.2) + "s";
            cont.appendChild(s);
        });
    }

    // -----------------------------------------------------
    // 5. Celebración con confeti
    // -----------------------------------------------------
    function lanzarConfeti() {
        if (sinMovimiento) return;
        var canvas = document.createElement("canvas");
        canvas.id = "taConfeti";
        document.body.appendChild(canvas);
        var ctx = canvas.getContext("2d");
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        function ajustar() {
            canvas.width = window.innerWidth * dpr;
            canvas.height = window.innerHeight * dpr;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        ajustar();
        window.addEventListener("resize", ajustar);

        var colores = ["#C5A880", "#F4E3C1", "#0D5C75", "#D95D39", "#2D6A4F", "#E0A96D"];
        var ancho = window.innerWidth, piezas = [];
        for (var i = 0; i < 140; i++) {
            var desdeIzq = i % 2 === 0;
            piezas.push({
                x: desdeIzq ? -10 : ancho + 10,
                y: window.innerHeight * (0.55 + Math.random() * 0.3),
                vx: (desdeIzq ? 1 : -1) * (4 + Math.random() * 7),
                vy: -(9 + Math.random() * 8),
                w: 6 + Math.random() * 6,
                h: 8 + Math.random() * 8,
                rot: Math.random() * Math.PI,
                vr: (Math.random() - 0.5) * 0.3,
                color: colores[i % colores.length]
            });
        }
        var inicio = performance.now(), duracion = 3800;
        function cuadro(ts) {
            var t = ts - inicio;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.globalAlpha = t > duracion - 800 ? Math.max((duracion - t) / 800, 0) : 1;
            piezas.forEach(function (p) {
                p.vy += 0.28; p.vx *= 0.99;
                p.x += p.vx; p.y += p.vy; p.rot += p.vr;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.rot)));
                ctx.restore();
            });
            if (t < duracion) requestAnimationFrame(cuadro);
            else { window.removeEventListener("resize", ajustar); canvas.remove(); }
        }
        requestAnimationFrame(cuadro);
    }

    function mostrarAviso(titulo, detalle) {
        var aviso = document.createElement("div");
        aviso.className = "ta-aviso";
        aviso.innerHTML = titulo + (detalle ? "<small>" + detalle + "</small>" : "");
        document.body.appendChild(aviso);
        requestAnimationFrame(function () { aviso.classList.add("ta-visible"); });
        setTimeout(function () {
            aviso.classList.remove("ta-visible");
            setTimeout(function () { aviso.remove(); }, 500);
        }, 4200);
    }

    function prepararCelebracion() {
        var datos = document.getElementById("taCelebracion");
        if (!datos) return;
        var cumplimiento = parseFloat(datos.dataset.cumplimiento) || 0;
        var ranking = parseInt(datos.dataset.ranking, 10) || 0;
        var tienda = datos.dataset.tienda || "";

        var motivo = null;
        if (cumplimiento >= 1) {
            motivo = ["🏆 ¡Meta cumplida, " + tienda + "!", "Llevan " + (cumplimiento * 100).toFixed(1) + "% de cumplimiento"];
        } else if (ranking >= 1 && ranking <= 3) {
            var medalla = ranking === 1 ? "🥇" : ranking === 2 ? "🥈" : "🥉";
            motivo = [medalla + " ¡Están en el top " + ranking + "!", "Entre todas las tiendas de L&H"];
        }
        if (!motivo) return;

        // Solo una vez por sesión, tienda y período
        var clave = "ta-celebracion-" + (datos.dataset.clave || "") + "-" + (cumplimiento >= 1 ? "meta" : "top" + ranking);
        try {
            if (sessionStorage.getItem(clave)) return;
            sessionStorage.setItem(clave, "1");
        } catch (e) { /* sin almacenamiento: celebrar igual */ }

        setTimeout(function () {
            lanzarConfeti();
            mostrarAviso(motivo[0], motivo[1]);
        }, 700);
    }

    function iniciar() {
        var pasos = [prepararMedidor, prepararNumeros, prepararBarras, prepararInsignias, prepararCelebracion];
        pasos.forEach(function (fn) {
            try { fn(); } catch (e) { console.error("tienda_animaciones:", fn.name, e); }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar);
    } else {
        iniciar();
    }
})();
