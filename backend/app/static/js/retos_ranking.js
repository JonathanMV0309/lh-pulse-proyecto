/* ================================================================
   Ranking de desempeño: pestañas «Batallas» y «Salón de la fama»
   - Batallas de la semana de toda la red, batalla de regiones y ciudades,
     rachas, remontadas, récords y semanas anteriores
   - Salón de la fama del último mes cerrado
   Solo lee /api/retos/red. Las pestañas originales siguen igual.
   ================================================================ */
(function () {
  'use strict';
  var barra = document.querySelector('.rk-tabs');
  if (!barra) return;
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

  var css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = '/static/css/retos.css?v=2';
  document.head.appendChild(css);

  function el(tag, clase, html) { var n = document.createElement(tag); if (clase) n.className = clase; if (html != null) n.innerHTML = html; return n; }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pct(v, dec) { return v == null ? '—' : (v * 100).toFixed(dec == null ? 1 : dec).replace('.', ',') + '%'; }
  function dinero(v) { v = Number(v) || 0; if (Math.abs(v) >= 1e6) return '$' + (v / 1e6).toFixed(1).replace('.', ',') + ' M'; return '$' + Math.round(v / 1e3) + ' mil'; }
  function dia(iso) { var p = iso.split('-'); var f = new Date(+p[0], +p[1] - 1, +p[2]); return DIAS[f.getDay()] + ' ' + f.getDate() + ' de ' + MESES[f.getMonth()]; }
  function corto(iso) { var p = iso.split('-'); return +p[2] + ' ' + MESES[+p[1] - 1].slice(0, 3); }

  // Pestañas nuevas: se comportan como las originales
  var original = Array.prototype.slice.call(barra.querySelectorAll('[data-tab]'));
  var paneles = Array.prototype.slice.call(document.querySelectorAll('.rk-panel'));
  var ultimo = paneles[paneles.length - 1];
  var nuevas = [['batallas', 'Batallas', 'bi-lightning-charge'], ['salon', 'Salón de la fama', 'bi-award']].map(function (x) {
    var b = el('button', 'rt-tab', '<i class="bi ' + x[2] + '"></i> ' + x[1] + ' <span class="rt-tab-nuevo">Nuevo</span>');
    b.type = 'button'; b.setAttribute('role', 'tab'); b.id = 'rkTab-' + x[0]; b.setAttribute('aria-controls', 'rkPanel-' + x[0]); b.setAttribute('aria-selected', 'false'); b.tabIndex = -1; b.dataset.rtTab = x[0];
    barra.appendChild(b);
    var p = el('div', 'rk-panel rt-panel', '<p class="rt-nota">Cargando…</p>');
    p.id = 'rkPanel-' + x[0]; p.setAttribute('role', 'tabpanel'); p.setAttribute('aria-labelledby', b.id); p.hidden = true;
    ultimo.parentNode.insertBefore(p, ultimo.nextSibling); ultimo = p;
    b.addEventListener('click', function () { abrir(x[0]); });
    return { b: b, p: p, nombre: x[0] };
  });
  function abrir(nombre) {
    original.forEach(function (t) { t.setAttribute('aria-selected', 'false'); t.tabIndex = -1; });
    paneles.forEach(function (p) { p.hidden = true; });
    nuevas.forEach(function (n) { var on = n.nombre === nombre; n.b.setAttribute('aria-selected', String(on)); n.b.tabIndex = on ? 0 : -1; n.p.hidden = !on; });
    try { history.replaceState(null, '', '#' + nombre); } catch (e) { /* sin historial */ }
  }
  original.forEach(function (t) { t.addEventListener('click', function () { nuevas.forEach(function (n) { n.b.setAttribute('aria-selected', 'false'); n.b.tabIndex = -1; n.p.hidden = true; }); }); });

  // Mismo período del filtro de la página
  var q = new URLSearchParams();
  ['anio', 'mes', 'dia_corte'].forEach(function (k) { var s = document.querySelector('form [name="' + k + '"]'); if (s && s.value) q.set(k, s.value); });
  fetch('/api/retos/red?' + q, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
    if (!d || !d.ok) { nuevas.forEach(function (n) { n.p.innerHTML = '<p class="rt-nota">No hay datos para este período.</p>'; }); return; }
    pintarBatallas(nuevas[0].p, d);
    pintarSalon(nuevas[1].p, d);
    if (location.hash === '#batallas' || location.hash === '#salon') abrir(location.hash.slice(1));
  }).catch(function () { nuevas.forEach(function (n) { n.p.innerHTML = '<p class="rt-nota">No se pudieron cargar los retos.</p>'; }); });

  function pintarBatallas(p, d) {
    var b = d.batallas, s = b.semana;
    var escala = Math.max.apply(null, [1.2].concat(b.parejas.map(function (x) { return Math.max(x.a.avance, x.b.avance); })));
    var fila = function (t, gana) { return '<span class="' + (gana ? 'gana' : '') + '">' + (gana ? '👑 ' : '') + esc(t.nombre) + ' <small style="color:#6B6259">' + esc(t.ciudad || '') + (b.rachas[t.id] >= 2 ? ' · 🔥 ' + b.rachas[t.id] + ' seguidas' : '') + '</small></span><b>' + pct(t.avance) + '</b><div class="rt-mini' + (gana ? ' gana' : '') + '"><span style="width:' + Math.min(100, t.avance / escala * 100) + '%"></span></div>'; };
    var duelos = b.parejas.map(function (x) {
      return '<article class="rt-duelo"><div class="rt-par">' + fila(x.a, x.gana === x.a.id) + fila(x.b, x.gana === x.b.id) + '</div></article>';
    }).join('');
    var equipo = function (lista) {
      var max = Math.max.apply(null, [1.1].concat(lista.map(function (x) { return x.avance || 0; })));
      return '<div class="rt-asesoras">' + lista.map(function (x, i) { return '<div class="rt-asesora"><em>' + (i === 0 ? '👑' : i + 1) + '</em><span><span class="rt-nom">' + esc(x.nombre) + ' <small style="color:#6B6259">· ' + x.tiendas + (x.tiendas === 1 ? ' tienda' : ' tiendas') + '</small></span><div class="rt-mini"><span style="width:' + Math.min(100, (x.avance || 0) / max * 100) + '%"></span></div></span><b>' + pct(x.avance) + '</b></div>'; }).join('') + '</div>';
    };
    var rachas = Object.keys(b.rachas).map(function (id) { return { id: +id, n: b.rachas[id] }; }).sort(function (x, y) { return y.n - x.n; });
    var nombres = {};
    b.parejas.forEach(function (x) { nombres[x.a.id] = x.a.nombre; nombres[x.b.id] = x.b.nombre; });
    var rec = { roto: '¡Récord roto!', cerca: 'Muy cerca del récord', camino: 'Va camino a récord' }, tipo = { dia: 'del día', semana: 'de la semana', mes: 'del mes' };
    p.innerHTML = '<div class="rt-cabeza"><div><h2><i class="bi bi-lightning-charge-fill"></i> Batallas de la semana</h2><p>Del ' + dia(s.desde) + ' al ' + dia(s.hasta) + '. Gana la tienda que va más adelante en su meta de la semana; todo en porcentaje.' + (b.descansa ? ' Esta semana descansa ' + esc(b.descansa) + '.' : '') + '</p></div></div>' +
      '<div class="rt-duelos">' + duelos + '</div>' +
      '<div class="rt-grid" style="margin-top:14px">' +
      '<article class="rt-card"><h3><i class="bi bi-map"></i> Batalla de regiones <small>Venta de la semana frente a su meta</small></h3>' + equipo(b.equipos.region) + '</article>' +
      '<article class="rt-card"><h3><i class="bi bi-buildings"></i> Batalla de ciudades</h3>' + equipo(b.equipos.ciudad) + '</article>' +
      '<article class="rt-card tercio"><h3><i class="bi bi-fire"></i> Rachas</h3>' + (rachas.length ? '<div class="rt-filas">' + rachas.slice(0, 6).map(function (r) { return '<div class="rt-fila"><i class="bi bi-fire"></i><span>' + esc(nombres[r.id] || '') + '</span><b>' + r.n + (r.n === 1 ? ' semana' : ' semanas') + '</b></div>'; }).join('') + '</div>' : '<p class="rt-nota">Aún no hay rachas: se cuentan las batallas ganadas seguidas.</p>') + '</article>' +
      '<article class="rt-card tercio"><h3><i class="bi bi-rocket-takeoff"></i> Remontadas del mes</h3>' + (d.remontadas.length ? '<div class="rt-filas">' + d.remontadas.map(function (r) { return '<div class="rt-fila"><i class="bi bi-graph-up-arrow"></i><span>' + esc(r.nombre) + '<small>Del ' + pct(r.desde, 0) + ' (día ' + r.dia_desde + ') al ' + pct(r.hasta, 0) + '</small></span></div>'; }).join('') + '</div>' : '<p class="rt-nota">Ninguna todavía. Una remontada es pasar de menos de 90 % a superar la meta del mes.</p>') + '</article>' +
      '<article class="rt-card tercio"><h3><i class="bi bi-trophy"></i> Récords</h3>' + (d.records.length ? '<div class="rt-filas">' + d.records.slice(0, 8).map(function (r) { return '<div class="rt-fila"><i class="bi bi-star"></i><span>' + esc(r.nombre) + '<small>' + rec[r.estado] + ' ' + tipo[r.tipo] + '</small></span></div>'; }).join('') + '</div>' : '<p class="rt-nota">Ninguna tienda está cerca de un récord.</p>') + '</article>' +
      (b.historia.length ? '<article class="rt-card ancha"><h3><i class="bi bi-clock-history"></i> Semanas anteriores</h3><div class="rt-duelos">' + b.historia.map(function (h) {
        return '<div class="rt-duelo"><b style="display:block;margin-bottom:6px">' + corto(h.desde) + ' al ' + corto(h.hasta) + '</b>' + h.parejas.map(function (x) { return '<div style="font-size:12.5px;padding:2px 0">' + (x.gana === x.a ? '👑 <b>' + esc(x.a) + '</b>' : esc(x.a)) + ' ' + pct(x.aa, 0) + ' · ' + (x.gana === x.b ? '👑 <b>' + esc(x.b) + '</b>' : esc(x.b)) + ' ' + pct(x.ab, 0) + '</div>'; }).join('') + '</div>';
      }).join('') + '</div></article>' : '') + '</div>';
  }

  function pintarSalon(p, d) {
    var s = d.salon;
    if (!s) { p.innerHTML = '<p class="rt-nota">Todavía no hay un mes cerrado para el salón de la fama.</p>'; return; }
    var reyes = {};
    d.batallas.historia.forEach(function (h) { if (MESES[+h.hasta.slice(5, 7) - 1] === s.mes) h.parejas.forEach(function (x) { if (x.gana) reyes[x.gana] = (reyes[x.gana] || 0) + 1; }); });
    var rey = Object.keys(reyes).sort(function (a, b) { return reyes[b] - reyes[a]; })[0];
    var premio = function (oro, icono, titulo, nombre, detalle) { return '<article class="rt-premio' + (oro ? ' oro' : '') + '"><div class="rt-medalla">' + icono + '</div><small>' + titulo + '</small><b>' + esc(nombre) + '</b><span>' + detalle + '</span></article>'; };
    p.innerHTML = '<div class="rt-cabeza"><div><h2><i class="bi bi-award-fill"></i> Salón de la fama · ' + s.mes.replace(/^./, function (x) { return x.toUpperCase(); }) + ' ' + s.anio + '</h2><p>Lo mejor del último mes cerrado (corte del día ' + s.dia + '). ' + s.en_meta + ' de ' + s.total + ' tiendas cerraron sobre su meta.</p></div></div>' +
      '<div class="rt-podio">' +
      premio(true, '🏆', 'Tienda campeona', s.campeona.nombre, esc(s.campeona.ciudad || '') + ' · cerró en ' + pct(s.campeona.cump)) +
      (s.remontada ? premio(false, '🚀', 'La que más subió', s.remontada.nombre, 'Del ' + pct(s.remontada.desde, 0) + ' al ' + pct(s.remontada.hasta, 0) + ' en el mes') : '') +
      (s.asesora ? premio(false, '⭐', 'Asesora que más avanzó', s.asesora.nombre, esc(s.asesora.tienda) + ' · subió ' + pct(s.asesora.subio, 0) + ' frente al mes anterior') : '') +
      (rey ? premio(false, '⚔️', 'Reina de las batallas', rey, reyes[rey] + (reyes[rey] === 1 ? ' batalla ganada' : ' batallas ganadas') + ' en el mes') : '') +
      '</div><p class="rt-nota">El salón de la fama se arma solo al cerrar cada mes.</p>';
  }
})();
