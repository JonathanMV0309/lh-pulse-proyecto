/* ================================================================
   Retos de la semana de la tienda
   - Página «Retos de la semana» (/retos): todo el detalle
   - Dashboard de la tienda: solo una franja con la batalla y el enlace a la página
   - Batalla de la semana (en porcentaje de la meta de la semana, sin puntos)
   - Récords de la tienda, hora dorada y turnos sugeridos, batalla de asesoras,
     pendientes de la última visita, remontada y la imagen «Tu semana»
   - Hilo anuncia la batalla una vez al día, lleva corona si ganaron la semana
     pasada y tiene el atajo «Mi batalla»
   Solo lee /api/retos/tienda.
   ================================================================ */
(function () {
  'use strict';
  var pagina = document.getElementById('retosPagina');
  var datosTp = null;
  try { datosTp = JSON.parse(document.getElementById('tpDatos').textContent); } catch (e) { /* no es el dashboard */ }
  if (!pagina && !datosTp) return;
  var anioRef = datosTp ? datosTp.anio : null;
  var quieto = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

  var css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = '/static/css/retos.css?v=2';
  document.head.appendChild(css);

  var m = location.pathname.match(/\/dashboard\/tienda\/(\d+)/);
  var q = new URLSearchParams();
  if (pagina) {
    if (pagina.dataset.store) q.set('store_id', pagina.dataset.store);
    var url = new URLSearchParams(location.search);
    ['anio', 'mes', 'dia_corte'].forEach(function (k) { if (url.get(k)) q.set(k, url.get(k)); });
  } else {
    if (m) q.set('store_id', m[1]);
    ['anio', 'mes', 'dia_corte'].forEach(function (k) { if (datosTp[k]) q.set(k, datosTp[k]); });
  }
  var urlPagina = '/retos' + (q.toString() ? '?' + q : '');
  fetch('/api/retos/tienda?' + q, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
    if (!d || !d.ok) { if (pagina) pagina.innerHTML = '<p class="text-muted">Todavía no hay retos para esta tienda en este período.</p>'; return; }
    anioRef = anioRef || d.corte.anio;
    if (pagina) pintar(d); else franja(d);
    conHilo(d);
    if (d.remontada) despuesDelTop3(function () { setTimeout(function () { remontada(d); }, 900); });
  }).catch(function () { /* sin retos: el dashboard queda igual */ });

  /* ---------------- Utilidades ---------------- */
  function el(tag, clase, html) { var n = document.createElement(tag); if (clase) n.className = clase; if (html != null) n.innerHTML = html; return n; }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pct(v, dec) { return v == null ? '—' : (v * 100).toFixed(dec == null ? 1 : dec).replace('.', ',') + '%'; }
  function dinero(v) { v = Number(v) || 0; var a = Math.abs(v); if (a >= 1e6) return '$' + (v / 1e6).toFixed(1).replace('.', ',') + ' M'; if (a >= 1e3) return '$' + Math.round(v / 1e3) + ' mil'; return '$' + Math.round(v); }
  function fechaTxt(iso) { var p = iso.split('-'); var f = new Date(+p[0], +p[1] - 1, +p[2]); return DIAS[f.getDay()] + ' ' + f.getDate() + ' de ' + MESES[f.getMonth()] + (+p[0] !== +anioRef ? ' de ' + p[0] : ''); }
  function corto(iso) { var p = iso.split('-'); return +p[2] + ' de ' + MESES[+p[1] - 1] + (+p[0] !== +anioRef ? ' de ' + p[0] : ''); }
  function hora(h) { var x = h % 12 || 12; return x + (h < 12 ? ' a. m.' : ' p. m.'); }
  function rango(h) { return 'de ' + hora(h).replace(/ (a|p)\. m\./, '') + ' a ' + hora(h + 2); }
  function facturas(n) { return n === 1 ? 'una factura' : 'unas ' + n + ' facturas'; }

  /* ---------------- Sección ---------------- */
  function lugar() {
    var titulos = Array.prototype.slice.call(document.querySelectorAll('.main-content h2, .main-content h3, .main-content h4, .main-content h5, .main-content .section-title'));
    var cump = titulos.find(function (h) { return /cumplimiento de meta/i.test(h.textContent); });
    // Sube hasta el bloque que es hijo directo del contenedor de la página
    var contenedor = document.querySelector('.main-content > .container') || (cump && cump.closest('.container'));
    var bloque = cump;
    while (bloque && contenedor && bloque.parentNode !== contenedor) bloque = bloque.parentNode;
    if (bloque && contenedor && bloque.parentNode === contenedor) return { padre: contenedor, antes: bloque.nextSibling };
    var top3 = document.querySelector('.main-content > .container > section.pp');
    if (top3) return { padre: top3.parentNode, antes: top3.nextSibling };
    var cab = document.querySelector('.dashboard-header');
    if (cab) return { padre: cab.parentNode, antes: cab.nextSibling };
    return null;
  }

  // Dashboard: una sola franja; el detalle está en «Retos de la semana»
  function franja(d) {
    var donde = lugar();
    if (!donde) return;
    var b = d.batalla, txt;
    if (!b) txt = d.descansa ? 'Esta semana les tocó descansar de la batalla.' : 'Esta semana no hay batalla para esta tienda.';
    else {
      var yo = b.gana === b.yo.id, otra = b.gana === b.rival.id;
      txt = '<b>Batalla de la semana:</b> ustedes <b class="rt-f-num">' + pct(b.yo.avance) + '</b> vs ' + esc(b.rival.nombre) + ' <b class="rt-f-num">' + pct(b.rival.avance) + '</b> · ' +
        (yo ? '¡van ganando! 👑' : otra ? 'les faltan ' + dinero(b.falta) + ' para pasar adelante' : '¡van empatadas!');
    }
    var n = el('a', 'rt-franja', '<span class="rt-f-icono" aria-hidden="true">⚔️</span><span class="rt-f-txt">' + txt + '</span><span class="rt-f-ir">Ver retos <i class="bi bi-arrow-right" aria-hidden="true"></i></span>');
    n.href = urlPagina;
    n.id = 'rtBatalla';
    donde.padre.insertBefore(n, donde.antes);
  }

  function pintar(d) {
    var s = d.semana;
    var sec = el('section', 'rt-seccion');
    sec.id = 'retosSemana';
    sec.innerHTML = '<div class="rt-cabeza"><div><h1><i class="bi bi-lightning-charge-fill" aria-hidden="true"></i> ' + esc(d.tienda.nombre) + '</h1><p>Del ' + fechaTxt(s.desde) + ' al ' + fechaTxt(s.hasta) + ' (corte)</p></div>' +
      '<button type="button" class="rt-boton" id="rtTuSemana"><i class="bi bi-image" aria-hidden="true"></i> Tu semana para WhatsApp</button></div><div class="rt-grid"></div>';
    var grid = sec.querySelector('.rt-grid');
    grid.appendChild(cartaBatalla(d));
    if (d.records) grid.appendChild(cartaRecords(d));
    if (d.hora_dorada) grid.appendChild(cartaHora(d));
    if (d.asesoras && d.asesoras.asesoras.length) grid.appendChild(cartaAsesoras(d));
    if (d.visita && d.visita.items.length) grid.appendChild(cartaVisita(d));
    grid.appendChild(cartaTrofeos(d));
    var cartas = grid.children;
    if (cartas.length % 2 === 0) cartas[cartas.length - 1].classList.add('ancha');
    pagina.replaceChildren(sec);
    sec.querySelector('#rtTuSemana').addEventListener('click', function () { tuSemana(d); });
    // Barras animadas al aparecer
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (e) { if (e.some(function (x) { return x.isIntersecting; })) { io.disconnect(); animar(sec); } }) : null;
    if (io) io.observe(sec); else animar(sec);
  }
  function animar(sec) { sec.querySelectorAll('[data-w]').forEach(function (n) { n.style.width = n.dataset.w; }); sec.querySelectorAll('[data-h]').forEach(function (n) { n.style.height = n.dataset.h; }); }

  function cartaBatalla(d) {
    var c = el('article', 'rt-card ancha rt-batalla');
    c.id = 'rtBatalla';
    var b = d.batalla;
    if (!b) {
      c.innerHTML = '<h3><i class="bi bi-lightning-charge-fill"></i> Batalla de la semana</h3><p class="rt-estado">' + (d.descansa ? 'Esta semana les tocó descansar: el número de tiendas es impar. ¡La próxima semana vuelven a la batalla!' : 'Esta semana no hay batalla para esta tienda.') + '</p>';
      return c;
    }
    var yoLider = b.gana === b.yo.id, rivalLider = b.gana === b.rival.id;
    var escala = Math.max(1.2, b.yo.avance, b.rival.avance);
    var estado;
    if (yoLider) estado = '¡Van ganando por <b>' + pct(b.yo.avance - b.rival.avance) + '</b>! Sigan así para cerrar la semana adelante.';
    else if (rivalLider) estado = 'Para pasar adelante les falta <b>' + dinero(b.falta) + '</b>' + (b.facturas ? ', ' + facturas(b.facturas) : '') + '. ¡Se puede!';
    else estado = '¡Van empatadas! Cada venta cuenta.';
    var chips = [];
    if (b.racha >= 2) chips.push('🔥 ' + b.racha + ' semanas ganando seguidas');
    else if (b.gano_semana_pasada) chips.push('👑 Ganaron la semana pasada');
    if (b.victorias_mes) chips.push('🏆 ' + b.victorias_mes + (b.victorias_mes === 1 ? ' batalla ganada' : ' batallas ganadas') + ' este mes');
    if (b.racha_rival >= 2) chips.push(esc(b.rival.nombre) + ' viene con ' + b.racha_rival + ' semanas invicta');
    c.innerHTML = '<h3><i class="bi bi-lightning-charge-fill"></i> Batalla de la semana <small>Gana la que va más adelante en su meta de la semana</small></h3>' +
      '<div class="rt-vs"><div class="rt-lado' + (yoLider ? ' lider' : '') + '"><small>Ustedes</small><b>' + (yoLider ? '<span class="rt-corona">👑</span> ' : '') + esc(b.yo.nombre) + '</b><div class="rt-pct">' + pct(b.yo.avance) + '</div><small>' + dinero(b.yo.venta) + ' de ' + dinero(b.yo.meta) + '</small></div>' +
      '<div class="rt-x" aria-hidden="true">VS</div>' +
      '<div class="rt-lado der' + (rivalLider ? ' lider' : '') + '"><small>' + esc(b.rival.ciudad || '') + '</small><b>' + (rivalLider ? '<span class="rt-corona">👑</span> ' : '') + esc(b.rival.nombre) + '</b><div class="rt-pct">' + pct(b.rival.avance) + '</div><small>' + dinero(b.rival.venta) + ' de ' + dinero(b.rival.meta) + '</small></div></div>' +
      '<div class="rt-barras" aria-hidden="true"><div class="rt-barra' + (yoLider ? ' lider' : '') + '"><span data-w="' + Math.min(100, b.yo.avance / escala * 100) + '%"></span></div><div class="rt-barra' + (rivalLider ? ' lider' : '') + '"><span data-w="' + Math.min(100, b.rival.avance / escala * 100) + '%"></span></div></div>' +
      '<p class="rt-estado">' + estado + '</p>' + (chips.length ? '<div class="rt-chips">' + chips.map(function (x) { return '<span class="rt-chip">' + x + '</span>'; }).join('') + '</div>' : '');
    return c;
  }

  // Mis trofeos: rachas, batallas ganadas y las últimas semanas
  function cartaTrofeos(d) {
    var b = d.batalla || {}, semanas = d.semanas || [];
    var ganadas = semanas.filter(function (s) { return s.resultado === 'gano'; }).length;
    var copas = semanas.map(function (s) { return s.resultado === 'gano' ? '🏆' : s.resultado === 'empate' ? '🤝' : '⚪'; }).reverse().join(' ');
    var filas = semanas.map(function (s) {
      var gano = s.resultado === 'gano';
      return '<div class="rt-fila"><i class="bi ' + (gano ? 'bi-trophy-fill' : s.resultado === 'empate' ? 'bi-hand-thumbs-up' : 'bi-arrow-repeat') + '"' + (gano ? ' style="color:#B98A3E"' : '') + '></i><span>vs ' + esc(s.rival) + '<small>Del ' + corto(s.desde) + ' al ' + corto(s.hasta) + '</small></span><b>' + pct(s.yo, 0) + ' · ' + pct(s.otra, 0) + '</b></div>';
    }).join('');
    var racha = b.racha || 0;
    return el('article', 'rt-card', '<h3><i class="bi bi-award"></i> Mis trofeos <small>Últimas semanas</small></h3>' +
      '<div class="rt-trofeos"><div><b>' + racha + '</b><span>' + (racha === 1 ? 'semana ganando' : 'semanas ganando seguidas') + '</span></div><div><b>' + (b.victorias_mes || 0) + '</b><span>batallas ganadas este mes</span></div><div><b>' + ganadas + ' de ' + semanas.length + '</b><span>en las últimas semanas</span></div></div>' +
      (copas ? '<p class="rt-copas" aria-label="Resultados de las últimas semanas">' + copas + '</p>' : '') +
      (filas ? '<div class="rt-filas">' + filas + '</div>' : '<p class="rt-nota">Aquí irán sus batallas de las semanas anteriores.</p>') +
      '<p class="rt-nota">Perder una semana no borra nada: cada lunes empieza una batalla nueva. 💪</p>');
  }

  function sello(estado) {
    return estado === 'roto' ? '<span class="rt-sello roto">¡Récord roto!</span>' : estado === 'cerca' ? '<span class="rt-sello cerca">Muy cerca</span>' : estado === 'camino' ? '<span class="rt-sello camino">Va camino a récord</span>' : '';
  }
  function cartaRecords(d) {
    var r = d.records, filas = [];
    if (r.dia) filas.push('<div class="rt-fila"><i class="bi bi-sun"></i><span>Mejor día<small>' + fechaTxt(r.dia.fecha) + ' · el día del corte vendieron ' + dinero(r.dia.hoy) + '</small></span>' + sello(r.dia.estado) + '<b>' + dinero(r.dia.valor) + '</b></div>');
    if (r.semana) filas.push('<div class="rt-fila"><i class="bi bi-calendar-week"></i><span>Mejor semana<small>Desde el ' + corto(r.semana.desde) + ' · esta semana van ' + dinero(r.semana.actual) + '</small></span>' + sello(r.semana.estado) + '<b>' + dinero(r.semana.valor) + '</b></div>');
    if (r.mes) filas.push('<div class="rt-fila"><i class="bi bi-calendar3"></i><span>Mejor mes<small>' + r.mes.mes.replace(/^./, function (x) { return x.toUpperCase(); }) + ' ' + r.mes.anio + ' · a este ritmo cerrarían en ' + dinero(r.mes.ritmo) + '</small></span>' + sello(r.mes.estado) + '<b>' + dinero(r.mes.valor) + '</b></div>');
    return el('article', 'rt-card', '<h3><i class="bi bi-trophy"></i> Récords de la tienda</h3><div class="rt-filas">' + filas.join('') + '</div>');
  }

  function cartaHora(d) {
    var h = d.hora_dorada, max = Math.max.apply(null, h.horas.map(function (x) { return x.trafico; }).concat([1]));
    var barras = h.horas.map(function (x) {
      var clase = x.h === h.dorada || x.h === h.dorada + 1 ? 'dorada' : h.floja && x.h === h.floja.h ? 'floja' : '';
      return '<div class="' + clase + '" title="' + hora(x.h) + ': ' + x.trafico + ' personas, ' + x.facturas + ' facturas"><i data-h="' + Math.max(4, x.trafico / max * 100) + '%" style="height:0"></i><small>' + (x.h % 12 || 12) + '</small></div>';
    }).join('');
    var txt = '<p class="rt-nota" style="color:#2D2A26;font-size:13.5px">Su hora dorada es <b>' + rango(h.dorada) + '</b>: ahí hacen más ventas.' +
      (h.floja && h.floja.h !== h.dorada && h.floja.h !== h.dorada + 1 ? ' A las <b>' + hora(h.floja.h) + '</b> entra gente pero compran pocos (' + pct(h.floja.valor) + '): buena hora para un reto.' : '') + '</p>';
    var turnos = '';
    var t = d.turnos;
    if (t && t.hay) {
      var cortos = t.dias.filter(function (x) { return x.corto; });
      turnos = '<h3 style="margin-top:14px"><i class="bi bi-people"></i> Turnos de los próximos días</h3><div class="rt-turnos">' + t.dias.map(function (x) {
        return '<div class="rt-dia' + (x.corto ? ' corto' : '') + '"><b>' + x.dia.slice(0, 3) + ' ' + (+x.fecha.slice(8)) + '</b><span>☀ ' + x.apertura + ' · 🌙 ' + x.cierre + '</span></div>';
      }).join('') + '</div><p class="rt-nota">' + (cortos.length ? 'Ojo: el ' + cortos.map(function (x) { return x.dia + ' ' + (+x.fecha.slice(8)); }).join(', el ') + ' hay pocas asesoras en el turno de ' + t.turno_clave + ', que es el de su hora dorada.' : 'El turno de ' + t.turno_clave + ', el de su hora dorada, está bien cubierto.') + ' ☀ apertura · 🌙 cierre</p>';
    } else if (t) turnos = '<p class="rt-nota">Cuando carguen el cuadrante, aquí verán si hay suficientes asesoras en su hora dorada.</p>';
    return el('article', 'rt-card', '<h3><i class="bi bi-clock-history"></i> Hora dorada <small>Últimos ' + h.dias + ' días</small></h3><div class="rt-horas" aria-hidden="true">' + barras + '</div>' + txt + turnos);
  }

  function cartaAsesoras(d) {
    var a = d.asesoras, max = Math.max.apply(null, a.asesoras.map(function (x) { return x.avance || 0; }).concat([1.2]));
    return el('article', 'rt-card', '<h3><i class="bi bi-people-fill"></i> Batalla de asesoras <small>Del día ' + a.desde + ' al ' + a.hasta + '</small></h3><div class="rt-asesoras">' + a.asesoras.map(function (x, i) {
      return '<div class="rt-asesora"><em>' + (i === 0 ? '👑' : i + 1) + '</em><span><span class="rt-nom">' + esc(x.nombre) + '</span><div class="rt-mini"><span data-w="' + Math.min(100, (x.avance || 0) / max * 100) + '%" style="width:0"></span></div></span><b>' + pct(x.avance, 0) + '</b></div>';
    }).join('') + '</div><p class="rt-nota">Cuánto avanzó cada una en su meta entre los dos últimos cortes. Gana la que más avanza, no la que más vende.</p>');
  }

  function cartaVisita(d) {
    return el('article', 'rt-card', '<h3><i class="bi bi-clipboard-check"></i> Para la próxima visita <small>Evaluación del ' + corto(d.visita.fecha) + '</small></h3><ul class="rt-pendientes">' + d.visita.items.map(function (x) {
      return '<li><i class="bi bi-x-circle-fill"></i><span>' + esc(x.item) + '<small>' + esc(x.categoria) + (x.obs ? ' · ' + esc(x.obs) : '') + '</small></span></li>';
    }).join('') + '</ul>');
  }

  /* ---------------- Hilo ---------------- */
  function conHilo(d) {
    var intentos = 0, espera = setInterval(function () {
      var app = window.__hiloApp;
      if (!app && ++intentos < 60) return;
      clearInterval(espera);
      if (!app) return;
      if (d.batalla && d.batalla.gano_semana_pasada) corona();
      atajo(d, app);
      var clave = 'lhpulse-retos-' + new Date().toISOString().slice(0, 10) + '-' + (d.tienda && d.tienda.id);
      try { if (localStorage.getItem(clave)) return; localStorage.setItem(clave, '1'); } catch (e) { /* sin almacenamiento: lo dice igual */ }
      setTimeout(function () { var f = frase(d); if (f) { app.poner(f[1]); app.decir(f[0], 6500); } }, 14000);
    }, 500);
  }
  function frase(d) {
    var b = d.batalla;
    if (!b) return null;
    var lunes = d.semana.dias === 1, rival = b.rival.nombre;
    if (lunes) return ['¡Nueva batalla! Esta semana: ' + b.yo.nombre + ' vs. ' + rival + '. ¡A ganarla! ⚔️', 'animo'];
    if (d.semana.dias >= 7) return b.gana === b.yo.id ? ['¡Ganamos la batalla de la semana contra ' + rival + '! 👑', 'feliz'] : ['Esta semana ganó ' + rival + '. ¡La próxima es nuestra! 💪', 'animo'];
    if (b.gana === b.yo.id) return ['¡Vamos ganando la batalla contra ' + rival + ': ' + pct(b.yo.avance) + ' vs ' + pct(b.rival.avance) + '!', 'feliz'];
    return ['Batalla: ' + rival + ' va adelante. Nos faltan ' + dinero(b.falta) + ' para pasarla. ¡Vamos!', 'concentra'];
  }
  function corona() {
    var intentos = 0, t = setInterval(function () {
      var raiz = document.querySelector('.hilo-app');
      if (!raiz && ++intentos < 40) return;
      clearInterval(t);
      if (!raiz || raiz.querySelector('.rt-corona-hilo')) return;
      var c = el('span', 'rt-corona-hilo', '👑');
      c.title = 'Ganaron la batalla de la semana pasada';
      if (getComputedStyle(raiz).position === 'static') raiz.style.position = 'relative';
      raiz.appendChild(c);
    }, 500);
  }
  function atajo(d, app) {
    if (!d.batalla) return;
    var poner = function () {
      var ref = document.querySelector('.hilo-atajo');
      if (!ref || ref.parentNode.querySelector('.rt-atajo')) return !!ref;
      var b = el('button', 'hilo-atajo rt-atajo', '<i class="bi bi-lightning-charge"></i><span>Mi batalla</span>');
      b.type = 'button';
      b.addEventListener('click', function () {
        var f = frase(d); if (f) { app.poner(f[1]); app.decir(f[0], 6000); }
        if (!pagina) { setTimeout(function () { location.href = urlPagina; }, 1200); return; }
        var carta = document.getElementById('rtBatalla');
        if (carta) carta.scrollIntoView({ behavior: quieto ? 'auto' : 'smooth', block: 'center' });
      });
      ref.parentNode.insertBefore(b, ref.parentNode.children[1] || null);
      return true;
    };
    if (poner()) return;
    var obs = new MutationObserver(function () { if (poner()) obs.disconnect(); });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  /* ---------------- Remontada ---------------- */
  // La ceremonia del Top 3 va primero
  function despuesDelTop3(cb) {
    var o = document.getElementById('top3StoresOverlay');
    if (!o || !o.classList.contains('active') || o.classList.contains('closing')) { cb(); return; }
    setTimeout(function () { despuesDelTop3(cb); }, 500);
  }
  function remontada(d) {
    var r = d.remontada, clave = 'lhpulse-remontada-' + d.tienda.id + '-' + d.corte.anio + '-' + d.corte.mes;
    try { if (localStorage.getItem(clave)) return; localStorage.setItem(clave, '1'); } catch (e) { return; }
    var capa = el('div', 'rt-remontada', '<div role="dialog" aria-modal="true" aria-label="Remontada"><small>¡Remontada!</small><h3>¡Lo lograron! 🚀</h3><p>Pasaron de estar por debajo del 90 % a superar la meta del mes.</p><div class="rt-salto"><span>' + pct(r.desde, 0) + '</span><i class="bi bi-arrow-right"></i><span>' + pct(r.hasta, 0) + '</span></div><button type="button" class="rt-boton" style="background:#E8C77E;color:#2D2A26">¡Seguimos! 💪</button></div>');
    document.body.appendChild(capa);
    if (!quieto) for (var i = 0; i < 40; i++) {
      var p = el('i', 'rt-confeti');
      p.style.cssText = 'left:' + Math.random() * 100 + '%;background:' + ['#E8C77E', '#C98A55', '#F5F0E8', '#6B7D3F'][i % 4] + ';animation-duration:' + (1.8 + Math.random() * 1.6) + 's;animation-delay:' + Math.random() * .6 + 's';
      capa.firstChild.appendChild(p);
    }
    var cerrar = function () { capa.remove(); };
    capa.querySelector('button').addEventListener('click', cerrar);
    capa.addEventListener('click', function (e) { if (e.target === capa) cerrar(); });
    capa.querySelector('button').focus();
    if (window.__hiloApp) { window.__hiloApp.poner('feliz', { saltos: 4 }); window.__hiloApp.decir('¡Qué remontada! 🚀', 5000); }
  }

  /* ---------------- Tu semana (imagen para WhatsApp) ---------------- */
  function tuSemana(d) {
    var c = document.createElement('canvas'), W = 1080, H = 1350, g = c.getContext('2d');
    c.width = W; c.height = H;
    var F = 'Inter, "Segoe UI", system-ui, sans-serif';
    var fondo = g.createLinearGradient(0, 0, W, H);
    fondo.addColorStop(0, '#2c2925'); fondo.addColorStop(.6, '#34302b'); fondo.addColorStop(1, '#23272b');
    g.fillStyle = fondo; g.fillRect(0, 0, W, H);
    var halo = g.createRadialGradient(W * .8, 160, 10, W * .8, 160, 560);
    halo.addColorStop(0, 'rgba(197,168,128,.28)'); halo.addColorStop(1, 'rgba(197,168,128,0)');
    g.fillStyle = halo; g.fillRect(0, 0, W, H);
    g.fillStyle = '#C9A97F'; g.font = '700 26px ' + F; g.fillText('L & H   P U L S E', 70, 96);
    g.fillStyle = '#F5F0E8'; g.font = '800 80px ' + F; g.fillText('Tu semana', 66, 190);
    g.fillStyle = '#D8CABB'; g.font = '600 34px ' + F; g.fillText(d.tienda.nombre + ' · ' + corto(d.semana.desde) + ' al ' + corto(d.semana.hasta), 70, 246);
    var y = 300;
    function caja(alto) { g.fillStyle = 'rgba(253,251,247,.07)'; redondo(g, 70, y, 940, alto, 28); g.fill(); }
    function titulo(t) { g.fillStyle = '#C9A97F'; g.font = '800 22px ' + F; g.fillText(t.toUpperCase().split('').join(String.fromCharCode(8202)), 104, y + 50); }
    var vs = d.venta_semana;
    caja(200); titulo('Venta de la semana');
    g.fillStyle = '#E8C77E'; g.font = '800 84px ' + F; g.fillText(dinero(vs ? vs.venta : 0), 100, y + 150);
    g.fillStyle = '#E8E0D4'; g.font = '600 30px ' + F; g.fillText(vs ? pct(vs.avance) + ' de la meta de la semana' : '', 560, y + 145);
    y += 230;
    var b = d.batalla;
    caja(230); titulo('Batalla de la semana');
    if (b) {
      g.font = '700 34px ' + F; g.fillStyle = '#F5F0E8';
      g.fillText((b.gana === b.yo.id ? '👑 ' : '') + b.yo.nombre, 100, y + 112); g.fillText((b.gana === b.rival.id ? '👑 ' : '') + b.rival.nombre, 100, y + 182);
      g.font = '800 44px ' + F; g.textAlign = 'right';
      g.fillStyle = b.gana === b.yo.id ? '#E8C77E' : '#C9B8A3'; g.fillText(pct(b.yo.avance), 970, y + 115);
      g.fillStyle = b.gana === b.rival.id ? '#E8C77E' : '#C9B8A3'; g.fillText(pct(b.rival.avance), 970, y + 185);
      g.textAlign = 'left';
    } else { g.fillStyle = '#E8E0D4'; g.font = '600 32px ' + F; g.fillText('Esta semana descansan.', 100, y + 130); }
    y += 260;
    var top = d.asesoras && d.asesoras.asesoras[0];
    caja(170); titulo('Asesora que más avanzó');
    g.fillStyle = '#F5F0E8'; g.font = '800 46px ' + F; g.fillText(top ? '⭐ ' + top.nombre : 'Sin datos', 100, y + 118);
    if (top) { g.textAlign = 'right'; g.fillStyle = '#E8C77E'; g.fillText(pct(top.avance, 0), 970, y + 118); g.textAlign = 'left'; }
    y += 200;
    caja(220); titulo('Reto de la nueva semana');
    var reto = 'Superar la meta de cada día';
    if (d.records && d.records.dia) reto = 'Romper el récord del día: ' + dinero(d.records.dia.valor);
    if (d.hora_dorada && d.hora_dorada.floja) reto = 'Subir la conversión a las ' + hora(d.hora_dorada.floja.h) + ' (hoy ' + pct(d.hora_dorada.floja.valor, 0) + ')';
    g.fillStyle = '#F5F0E8'; g.font = '700 38px ' + F; envolver(g, reto, 100, y + 118, 860, 48);
    g.fillStyle = '#C9A97F'; g.font = '700 26px ' + F; g.fillText('¡Cada venta cuenta! 🧵', 70, 1300);
    var nombre = 'tu_semana_' + String(d.tienda.nombre).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '_') + '_' + d.semana.hasta + '.png';
    var v = el('div', 'rt-modal', '<div class="rt-caja" role="dialog" aria-modal="true" aria-label="Tu semana"><header><h3>Tu semana</h3><button type="button" class="rt-cerrar" aria-label="Cerrar"><i class="bi bi-x-lg"></i></button></header><div class="rt-foto"><div class="rt-lienzo"></div><div><p>Una imagen con la semana de la tienda, lista para mandar al grupo de WhatsApp del equipo.</p><p><button type="button" class="rt-boton" data-f="bajar"><i class="bi bi-download"></i> Descargar</button> <button type="button" class="rt-boton sec" data-f="copiar"><i class="bi bi-clipboard"></i> Copiar</button></p><p class="rt-nota" data-nota></p></div></div></div>');
    v.querySelector('.rt-lienzo').appendChild(c);
    document.body.appendChild(v);
    var cerrar = function () { v.remove(); document.removeEventListener('keydown', tecla); };
    var tecla = function (e) { if (e.key === 'Escape') cerrar(); };
    document.addEventListener('keydown', tecla);
    v.addEventListener('click', function (e) {
      if (e.target === v || e.target.closest('.rt-cerrar')) { cerrar(); return; }
      var bt = e.target.closest('[data-f]'); if (!bt) return;
      var nota = v.querySelector('[data-nota]');
      if (bt.dataset.f === 'bajar') { var a = document.createElement('a'); a.download = nombre; a.href = c.toDataURL('image/png'); a.click(); nota.textContent = 'Descargada como ' + nombre + '.'; }
      else c.toBlob(function (blob) {
        if (!navigator.clipboard || !window.ClipboardItem) { nota.textContent = 'Este navegador no deja copiar imágenes: usa «Descargar».'; return; }
        navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]).then(function () { nota.textContent = 'Copiada. Pégala en WhatsApp con Ctrl+V.'; }, function () { nota.textContent = 'No se pudo copiar: usa «Descargar».'; });
      });
    });
    v.querySelector('.rt-cerrar').focus();
  }
  function redondo(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function envolver(g, texto, x, y, ancho, alto) {
    var linea = '';
    texto.split(' ').forEach(function (p) { var prueba = linea ? linea + ' ' + p : p; if (g.measureText(prueba).width > ancho && linea) { g.fillText(linea, x, y); y += alto; linea = p; } else linea = prueba; });
    g.fillText(linea, x, y);
  }
})();
