/* ================================================================
   Mapa y resultados · mejoras
   - Resumen: tiendas en el hilo, «Hilo cuenta el mapa», regiones con semáforo y ciudades como equipos
   - Mapa: cada tienda visible (aunque compartan ciudad) y ficha al tocarla (cuánto le falta, proyección,
     causa principal, asesoras, última visita y tiendas gemelas)
   - Modos nuevos: Duelos y Asesoras. Capas: Cambios, Alertas, Clima hoy y Pulso de ventas
   - Acciones: Comparar meses, Ruta de visitas, Foto del mes, Pantalla completa y Modo oficina
   - En el hilo de la red: «Para el hilo completo» (meta de la red)
   Solo lee datos: /api/v2/tiendas, /api/v2/mapa-plus y /api/hilo/admin/red.
   ================================================================ */
(function () {
  'use strict';
  var cont = document.getElementById('mapContainer');
  var seg = document.getElementById('mapMetric');
  if (!cont || !seg || typeof L === 'undefined') return;

  var config = {};
  try { config = JSON.parse(document.getElementById('geoV2Config').textContent); } catch (e) { /* sin configuración */ }
  var filtros = config.filtros || {};
  var quieto = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var COL = { ok: '#6B7D3F', mid: '#C9952F', low: '#C96F4A', bad: '#B55A4E', gris: '#8B7D6B' };
  var RAMPA_VENTAS = ['#D8CABB', '#C5A880', '#A8865A', '#7A5F3E'];
  var RAMPA_BUENA = [COL.bad, COL.low, COL.mid, COL.ok];
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  var REGION_CIUDAD = {
    'bogota': 'Centro', 'chia': 'Centro', 'soacha': 'Centro', 'ibague': 'Centro', 'villavicencio': 'Centro', 'tunja': 'Centro', 'neiva': 'Centro', 'girardot': 'Centro',
    'medellin': 'Antioquia y Eje Cafetero', 'envigado': 'Antioquia y Eje Cafetero', 'rionegro': 'Antioquia y Eje Cafetero', 'bello': 'Antioquia y Eje Cafetero', 'itagui': 'Antioquia y Eje Cafetero',
    'pereira': 'Antioquia y Eje Cafetero', 'manizales': 'Antioquia y Eje Cafetero', 'armenia': 'Antioquia y Eje Cafetero', 'dosquebradas': 'Antioquia y Eje Cafetero',
    'cali': 'Pacífico', 'palmira': 'Pacífico', 'pasto': 'Pacífico', 'popayan': 'Pacífico', 'tulua': 'Pacífico', 'buenaventura': 'Pacífico',
    'barranquilla': 'Caribe y Oriente', 'cartagena': 'Caribe y Oriente', 'santa marta': 'Caribe y Oriente', 'valledupar': 'Caribe y Oriente', 'monteria': 'Caribe y Oriente', 'sincelejo': 'Caribe y Oriente',
    'bucaramanga': 'Caribe y Oriente', 'cucuta': 'Caribe y Oriente', 'floridablanca': 'Caribe y Oriente'
  };

  var mapa = null, tiendas = [], porId = {}, plus = null, red = null, corte = null, cortePrevio = null;
  var modo = 'red', capas = {}, grupoMarcas = null, grupoInsignias = null, grupoLineas = null, grupoClima = null, grupoRuta = null;
  var seleccion = null, gemelasSel = [], duelos = [], alertas = [], ladoActual = null, batallas = null;
  var grid = document.querySelector('.geo-v2-main-grid');

  /* ---------------- Utilidades ---------------- */
  function el(tag, clase, html) { var n = document.createElement(tag); if (clase) n.className = clase; if (html != null) n.innerHTML = html; return n; }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pct(v, dec) { return v == null || !isFinite(v) ? '—' : (v * 100).toFixed(dec == null ? 1 : dec).replace('.', ',') + '%'; }
  // Diferencias de cumplimiento en porcentaje (sin «puntos»: así lo leen las tiendas)
  function pts(v) { return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(1).replace('.', ',') + ' %'; }
  function dinero(v) {
    v = Number(v) || 0; var a = Math.abs(v);
    if (a >= 1e9) return '$' + (v / 1e9).toFixed(1).replace('.', ',') + ' mil M';
    if (a >= 1e6) return '$' + (v / 1e6).toFixed(1).replace('.', ',') + ' M';
    if (a >= 1e3) return '$' + Math.round(v / 1e3) + ' mil';
    return '$' + Math.round(v);
  }
  function facturas(n) { n = Math.round(Number(n) || 0); return (n === 1 ? 'una factura' : 'unas ' + n.toLocaleString('es-CO') + ' facturas'); }
  function entero(v) { return Math.round(Number(v) || 0).toLocaleString('es-CO'); }
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim(); }
  function mediana(lista) { var a = lista.filter(function (v) { return isFinite(v); }).sort(function (x, y) { return x - y; }); if (!a.length) return 0; var m = Math.floor(a.length / 2); return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; }
  function cuartiles(lista) { var a = lista.filter(isFinite).sort(function (x, y) { return x - y; }); var q = function (p) { return a.length ? a[Math.min(a.length - 1, Math.floor(p * (a.length - 1)))] : 0; }; return [q(.25), q(.5), q(.75)]; }
  function colorCump(v) { return v == null ? COL.gris : v >= 1 ? COL.ok : v >= .9 ? COL.mid : v >= .8 ? COL.low : COL.bad; }
  function km(a, b) {
    var R = 6371, r = Math.PI / 180, dLat = (b.lat - a.lat) * r, dLng = (b.lng - a.lng) * r;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  function consulta(extra) {
    var q = new URLSearchParams();
    Object.keys(filtros).forEach(function (k) { if (filtros[k] !== null && filtros[k] !== undefined && filtros[k] !== '') q.set(k, filtros[k]); });
    Object.keys(extra || {}).forEach(function (k) { if (extra[k] == null || extra[k] === '') q.delete(k); else q.set(k, extra[k]); });
    return q.toString();
  }
  function traer(url) { return fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function sobreMapa(n) { cont.appendChild(n); L.DomEvent.disableClickPropagation(n); L.DomEvent.disableScrollPropagation(n); return n; }
  function enHilo(t) { return t.union != null || (t.union === undefined && t.cump >= 1); }

  /* ---------------- Carga ---------------- */
  var intentos = 0, espera = setInterval(function () {
    if (window.__geoMapa || ++intentos > 60) { clearInterval(espera); if (window.__geoMapa) iniciar(window.__geoMapa); }
  }, 200);

  function iniciar(m) {
    mapa = m;
    var periodo = filtros.periodo || '';
    Promise.all([
      traer(config.urls.tiendas + '?' + consulta()),
      traer('/api/v2/mapa-plus' + (periodo ? '?periodo=' + encodeURIComponent(periodo) : '')).catch(function () { return null; }),
      traer('/api/hilo/admin/red' + (periodo ? '?periodo=' + encodeURIComponent(periodo) : '')).catch(function () { return null; })
    ]).then(function (r) {
      if (!Array.isArray(r[0])) return;
      plus = r[1] && r[1].ok ? r[1] : null;
      red = r[2] && r[2].ok ? r[2] : null;
      preparar(r[0]);
      pintarResumen();
      crearMarcadores();
      prepararBarra();
      cont.classList.add('mp-activo');
      document.addEventListener('geo:modo', function (e) { cambiarModo(e.detail); });
      var activo = seg.querySelector('button.on');
      cambiarModo(activo ? activo.dataset.m : 'cumplimiento');
      mapa.on('zoomend', reubicar);
      if (red) metaDeLaRed();
      traer('/api/retos/red' + (periodo ? '?periodo=' + encodeURIComponent(periodo) : '')).then(function (r) {
        if (!r || !r.ok || !r.batallas.parejas.length) return;
        batallas = r.batallas;
        duelos = r.batallas.parejas.filter(function (p) { return porId[p.a.id] && porId[p.b.id]; }).map(function (p) {
          return { a: porId[p.a.id], b: porId[p.b.id], va: p.a.avance, vb: p.b.avance, gana: p.gana === p.a.id ? porId[p.a.id] : p.gana === p.b.id ? porId[p.b.id] : null, avance: true };
        });
        if (modo === 'duelos') { dibujarDuelos(); ladoDuelos(); }
        pintarVirtual();
      }).catch(function () { /* se quedan las parejas calculadas aquí */ });
      document.addEventListener('hilo:datos', metaDeLaRed);
    }).catch(function () { /* el mapa original sigue funcionando */ });
  }

  function preparar(lista) {
    var extra = {};
    if (plus) plus.tiendas.forEach(function (x) { extra[x.id] = x; });
    var serie = {}, ordenRed = {};
    if (red) red.tiendas.forEach(function (x, i) { serie[x.id] = x; ordenRed[x.id] = i; });
    corte = plus ? plus.corte : red ? red.corte : null;
    if (red && red.cortes.length > 1) cortePrevio = red.cortes[red.cortes.length - 2];
    // La tienda virtual cuenta en todo; solo no tiene punto en el mapa (tiene su tarjeta en la esquina)
    tiendas = lista.map(function (t) {
      var p = extra[t.id] || {}, s = serie[t.id];
      var x = {
        id: t.id, codigo: t.codigo, nombre: t.nombre, ciudad: t.es_virtual ? 'Tienda virtual' : t.ciudad || 'Sin ciudad', clima: t.clima, virtual: !!t.es_virtual,
        lat: t.lat == null ? null : +t.lat, lng: t.lng == null ? null : +t.lng,
        venta: +t.venta_actual || 0, ventaAnt: +t.venta_anterior || 0, cump: +t.cumplimiento_pct || 0, trafico: +t.trafico || 0,
        conversion: +t.conversion || 0, ticket: +t.ticket_promedio || 0, facturas: +t.facturas || 0, score: +t.score || 0,
        region: t.es_virtual ? 'Canal virtual' : p.region || REGION_CIUDAD[norm(t.ciudad)] || 'Otras regiones',
        meta: p.meta || 0, metaCorte: p.meta_corte || 0, falta: p.falta, facturasFaltan: p.facturas_faltan,
        proyeccion: p.proyeccion || null, dias: p.dias || [], asesoras: p.asesoras || null, visita: p.visita || null, url: p.url || null,
        serie: s ? s.serie : null, union: red ? (s ? s.dia : null) : undefined, orden: ordenRed[t.id] == null ? 999 : ordenRed[t.id]
      };
      if (x.serie && x.serie.length > 1) x.delta = (x.serie[x.serie.length - 1][1] - x.serie[x.serie.length - 2][1]) * 100;
      return x;
    }).sort(function (a, b) { return a.orden - b.orden; });
    tiendas.forEach(function (t) { porId[t.id] = t; });
    calcularAlertas();
    calcularDuelos();
  }

  /* ---------------- Resumen: hilo, Hilo dice, regiones ---------------- */
  function pintarResumen() {
    var unidas = tiendas.filter(enHilo).length, total = tiendas.length;
    var kpi = document.getElementById('mpKpiHilo'), nota = document.getElementById('mpKpiHiloNota');
    if (kpi) kpi.textContent = unidas + ' de ' + total;
    if (nota) nota.textContent = unidas >= total ? '¡Toda la red pasó su meta!' : 'Faltan ' + (total - unidas) + ' para el hilo completo';
    pintarRegiones();
    hiloDice();
  }

  function grupos(clave) {
    var g = {};
    tiendas.forEach(function (t) { (g[t[clave]] = g[t[clave]] || []).push(t); });
    return Object.keys(g).map(function (k) {
      var l = g[k], prom = l.reduce(function (s, t) { return s + t.cump; }, 0) / l.length;
      var conPrev = l.filter(function (t) { return t.delta != null; });
      return { nombre: k, tiendas: l, prom: prom, unidas: l.filter(enHilo).length,
        delta: conPrev.length ? conPrev.reduce(function (s, t) { return s + t.delta; }, 0) / conPrev.length : null };
    });
  }

  function pintarRegiones() {
    var caja = document.getElementById('mpRegiones');
    if (!caja) return;
    var regiones = grupos('region').sort(function (a, b) { return b.prom - a.prom; });
    caja.innerHTML = regiones.map(function (r) {
      var ciudades = {};
      r.tiendas.forEach(function (t) { (ciudades[t.ciudad] = ciudades[t.ciudad] || []).push(t); });
      var equipos = Object.keys(ciudades).map(function (c) {
        var l = ciudades[c], p = l.reduce(function (s, t) { return s + t.cump; }, 0) / l.length, u = l.filter(enHilo).length;
        return { c: c, p: p, u: u, n: l.length };
      }).sort(function (a, b) { return b.p - a.p; });
      return '<article class="mp-region"><header><span class="mp-sem" style="color:' + colorCump(r.prom) + '"></span><b>' + esc(r.nombre) + '</b><span class="mp-pct">' + pct(r.prom) + '</span></header>' +
        '<small class="mp-tend">' + r.unidas + ' de ' + r.tiendas.length + ' tiendas en el hilo' + (r.delta != null && cortePrevio ? ' · ' + (r.delta >= 0 ? 'subió ' : 'bajó ') + pts(r.delta).replace(/^[+−]/, '') + ' desde el día ' + cortePrevio : '') + '</small>' +
        '<div class="mp-equipos">' + equipos.map(function (e) {
          return '<button type="button" class="mp-equipo" data-ciudad="' + esc(e.c) + '" title="Ver ' + esc(e.c) + ' en el mapa"><i style="background:' + colorCump(e.p) + '">' + Math.round(e.p * 100) + '</i>' + esc(e.c) + ' <small>' + e.u + '/' + e.n + '</small></button>';
        }).join('') + '</div></article>';
    }).join('');
    caja.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-ciudad]');
      if (!b) return;
      irACiudad(b.dataset.ciudad);
      document.getElementById('mapCard').scrollIntoView({ behavior: quieto ? 'auto' : 'smooth', block: 'start' });
    });
  }

  function irACiudad(ciudad, opciones) {
    var l = tiendas.filter(function (t) { return t.ciudad === ciudad && t.punto; });
    if (!l.length) {
      var v = tiendas.filter(function (t) { return t.ciudad === ciudad && t.virtual; })[0];
      if (v && !oficina) abrirFicha(v.id);
      return;
    }
    var b = L.latLngBounds(l.map(function (t) { return [t.lat, t.lng]; }));
    mapa.flyToBounds(b.pad(.4), Object.assign({ maxZoom: 12, duration: quieto ? 0 : 1.2 }, opciones || {}));
  }

  function frases() {
    var f = [], total = tiendas.length, unidas = tiendas.filter(enHilo);
    var regiones = grupos('region').sort(function (a, b) { return b.prom - a.prom; });
    if (regiones.length > 1) f.push('Hoy <b>' + esc(regiones[0].nombre) + '</b> va adelante: ' + pct(regiones[0].prom) + ' de cumplimiento promedio y ' + regiones[0].unidas + ' de ' + regiones[0].tiendas.length + ' tiendas en el hilo.');
    var ciudades = grupos('ciudad').filter(function (c) { return c.tiendas.length > 1 && c.unidas < c.tiendas.length; })
      .sort(function (a, b) { return (b.tiendas.length - b.unidas) - (a.tiendas.length - a.unidas) || b.tiendas.length - a.tiendas.length; });
    if (ciudades.length) {
      var c = ciudades[0], cerca = c.tiendas.filter(function (t) { return !enHilo(t); }).sort(function (a, b) { return b.cump - a.cump; })[0];
      var k = c.tiendas.length - c.unidas;
      f.push('A <b>' + esc(c.nombre) + '</b> le ' + (k === 1 ? 'falta 1 tienda' : 'faltan ' + k + ' tiendas') + ' para tener todo su equipo en el hilo. La más cerca: <b>' + esc(cerca.nombre) + '</b> (' + pct(cerca.cump) + ').');
    }
    var faltan = tiendas.filter(function (t) { return !enHilo(t); }).sort(function (a, b) { return b.cump - a.cump; });
    if (faltan.length) {
      var tres = faltan.slice(0, 3), suma = tres.reduce(function (s, t) { return s + (t.falta || 0); }, 0);
      f.push('Faltan <b>' + faltan.length + ' tiendas</b> para el hilo completo. Las ' + tres.length + ' más cerca' + (suma ? ' necesitan <b>' + dinero(suma) + '</b> entre todas' : '') + ': ' + tres.map(function (t) { return esc(t.nombre); }).join(', ') + '.');
    } else if (total) f.push('¡Las ' + total + ' tiendas están en el hilo dorado! 🧵');
    var conDelta = tiendas.filter(function (t) { return t.delta != null; });
    if (conDelta.length && cortePrevio) {
      var suben = conDelta.filter(function (t) { return t.delta > 0.05; }), mejor = conDelta.slice().sort(function (a, b) { return b.delta - a.delta; })[0];
      f.push('Desde el corte del día ' + cortePrevio + ', <b>' + suben.length + ' tiendas subieron</b> y ' + (conDelta.length - suben.length) + ' bajaron. La que más subió: <b>' + esc(mejor.nombre) + '</b> (' + pts(mejor.delta) + ').');
    }
    if (alertas.length) f.push('<b>' + alertas.length + (alertas.length === 1 ? ' tienda necesita' : ' tiendas necesitan') + ' atención</b>: ' + alertas.slice(0, 3).map(function (a) { return esc(a.t.nombre) + ' (' + esc(a.motivos[0].toLowerCase()) + ')'; }).join('; ') + '.');
    if (plus && corte) {
      var porDia = [];
      tiendas.forEach(function (t) { t.dias.forEach(function (v, i) { porDia[i] = (porDia[i] || 0) + v; }); });
      var mejorDia = porDia.reduce(function (m, v, i) { return v > porDia[m] ? i : m; }, 0);
      if (porDia.length) f.push('El mejor día del mes fue el <b>' + DIAS[new Date(corte.anio, corte.mes - 1, mejorDia + 1).getDay()] + ' ' + (mejorDia + 1) + '</b>: ' + dinero(porDia[mejorDia]) + ' en toda la red.');
    }
    return f;
  }

  function hiloDice() {
    var caja = document.getElementById('mpHiloDice');
    if (!caja) return;
    var f = frases();
    if (!f.length) return;
    caja.hidden = false;
    caja.innerHTML = '<span class="mp-avatar" aria-hidden="true">🧵</span><p></p><span class="mp-puntos">' + f.map(function (_, i) { return '<button type="button" aria-label="Frase ' + (i + 1) + '"></button>'; }).join('') + '</span>';
    var p = caja.querySelector('p'), puntos = caja.querySelectorAll('.mp-puntos button'), i = 0, reloj = 0;
    function mostrar(n) {
      i = (n + f.length) % f.length;
      p.classList.add('fuera');
      setTimeout(function () { p.innerHTML = f[i]; p.classList.remove('fuera'); }, quieto ? 0 : 300);
      puntos.forEach(function (b, k) { b.classList.toggle('on', k === i); });
    }
    function seguir() { clearInterval(reloj); if (f.length > 1) reloj = setInterval(function () { mostrar(i + 1); }, 8000); }
    puntos.forEach(function (b, k) { b.addEventListener('click', function () { mostrar(k); seguir(); }); });
    caja.addEventListener('mouseenter', function () { clearInterval(reloj); });
    caja.addEventListener('mouseleave', seguir);
    p.innerHTML = f[0]; puntos[0].classList.add('on'); seguir();
  }

  /* ---------------- Marcadores propios ---------------- */
  function crearMarcadores() {
    grupoLineas = L.layerGroup().addTo(mapa);
    grupoRuta = L.layerGroup().addTo(mapa);
    grupoMarcas = L.layerGroup().addTo(mapa);
    grupoInsignias = L.layerGroup().addTo(mapa);
    grupoClima = L.layerGroup().addTo(mapa);
    var maxVenta = Math.max.apply(null, tiendas.map(function (t) { return t.venta; }).concat([1]));
    var porPunto = {};
    tiendas.forEach(function (t) {
      if (t.lat == null || t.lng == null || !isFinite(t.lat)) return;
      var k = t.lat.toFixed(3) + ',' + t.lng.toFixed(3);
      (porPunto[k] = porPunto[k] || []).push(t);
    });
    Object.keys(porPunto).forEach(function (k) { porPunto[k].forEach(function (t, i, l) { t.grupo = l.length; t.indice = i; }); });
    tiendas.forEach(function (t) {
      if (t.grupo == null) return;
      t.tam = Math.round(16 + 14 * Math.sqrt(Math.max(t.venta, 0) / maxVenta));
      t.marca = L.marker([t.lat, t.lng], { icon: L.divIcon({ className: '', html: '<div class="mp-mk" data-id="' + t.id + '"><b></b><span>' + esc(t.nombre) + '</span></div>', iconSize: [t.tam, t.tam], iconAnchor: [t.tam / 2, t.tam / 2] }), zIndexOffset: 400, keyboard: true, title: t.nombre });
      t.marca.bindTooltip('', { direction: 'top', offset: [0, -t.tam / 2], className: 'geo-tip' });
      t.marca.on('click', function () { abrirFicha(t.id); });
      t.insignia = L.marker([t.lat, t.lng], { icon: L.divIcon({ className: '', html: '<div class="mp-insignias"></div>', iconSize: [t.tam, t.tam], iconAnchor: [t.tam / 2, t.tam / 2] }), interactive: false, keyboard: false, zIndexOffset: 900 });
      grupoMarcas.addLayer(t.marca);
      grupoInsignias.addLayer(t.insignia);
    });
    reubicar();
    // Las tiendas del hilo (hilo_red.js) también abren la ficha
    cont.addEventListener('click', function (ev) {
      var n = ev.target.closest('.hr-tienda[data-id]');
      if (n) abrirFicha(+n.dataset.id);
    });
    var sel = document.getElementById('mapStoreSelect');
    if (sel) sel.addEventListener('change', function () { marcar(sel.value ? +sel.value : null); });
  }

  // Igual que el hilo de la red: las tiendas de una misma ubicación se reparten en un círculo
  function reubicar() {
    tiendas.forEach(function (t) {
      if (t.grupo == null) return;
      var p = mapa.latLngToLayerPoint([t.lat, t.lng]);
      if (t.grupo > 1) { var a = 2 * Math.PI * t.indice / t.grupo - Math.PI / 2, r = 14 + t.grupo * 2; p = L.point(p.x + Math.cos(a) * r, p.y + Math.sin(a) * r); }
      t.punto = mapa.layerPointToLatLng(p);
      t.marca.setLatLng(t.punto); t.insignia.setLatLng(t.punto);
    });
    if (modo === 'duelos') dibujarDuelos();
    if (ladoActual === 'ruta' && rutaCiudad) dibujarRuta(rutaCiudad, false);
  }

  function configModo(m) {
    if (m === 'ventas') { var q = cuartiles(tiendas.map(function (t) { return t.venta; })); return { color: function (t) { return RAMPA_VENTAS[t.venta >= q[2] ? 3 : t.venta >= q[1] ? 2 : t.venta >= q[0] ? 1 : 0]; }, valor: function (t) { return 'Venta ' + dinero(t.venta); } }; }
    if (m === 'conversion') { var c = cuartiles(tiendas.map(function (t) { return t.conversion; })); return { color: function (t) { return RAMPA_BUENA[t.conversion >= c[2] ? 3 : t.conversion >= c[1] ? 2 : t.conversion >= c[0] ? 1 : 0]; }, valor: function (t) { return 'Conversión ' + t.conversion.toFixed(1).replace('.', ',') + '%'; } }; }
    if (m === 'score') return { color: function (t) { return t.score >= 75 ? COL.ok : t.score >= 50 ? COL.mid : t.score >= 30 ? COL.low : COL.bad; }, valor: function (t) { return 'Score ' + t.score.toFixed(1).replace('.', ',') + '/100'; } };
    return { color: function (t) { return colorCump(t.cump); }, valor: function (t) { return 'Cumplimiento ' + pct(t.cump); } };
  }

  function pintarMarcas() {
    var cfg = configModo(modo);
    tiendas.forEach(function (t) {
      if (!t.marca) return;
      var n = t.marca.getElement() && t.marca.getElement().querySelector('.mp-mk');
      if (!n) return;
      var a = t.asesoras, anillo = modo === 'asesoras';
      n.classList.toggle('anillo', anillo);
      n.classList.toggle('crit', !anillo && t.cump < .8);
      n.querySelector('b').style.setProperty('--c', cfg.color(t));
      var em = n.querySelector('em');
      if (anillo) {
        var p = a && a.con_meta ? a.en_meta / a.con_meta : 0;
        n.style.setProperty('--p', p);
        if (!em) { em = el('em'); n.appendChild(em); }
        em.textContent = a ? a.en_meta + '/' + a.con_meta : '—';
      } else if (em) em.remove();
      var tip = '<strong>' + esc(t.nombre) + '</strong> <small>· ' + esc(t.ciudad) + '</small><br>' +
        (anillo ? (a ? a.en_meta + ' de ' + a.con_meta + ' asesoras con meta ya la pasaron' : 'Sin datos de asesoras') : esc(cfg.valor(t)) + (modo !== 'cumplimiento' ? ' · Cumpl. ' + pct(t.cump) : '')) +
        '<br><small>Toca para ver su ficha</small>';
      t.marca.setTooltipContent(tip);
    });
    pintarVirtual();
    if (modo === 'asesoras' || modo === 'duelos') {
      var ley = document.getElementById('mapLegend');
      if (ley) ley.innerHTML = modo === 'asesoras'
        ? '<span class="geo-v2-legend-item"><span class="geo-v2-legend-dot" style="background:#E8C77E"></span>Asesoras que ya pasaron su meta</span><span class="geo-v2-legend-item"><span class="geo-v2-legend-dot" style="background:#6F665D"></span>Las que aún no</span><span class="mp-leyenda-nota">El número es «pasaron / tienen meta».</span>'
        : '<span class="geo-v2-legend-item"><span class="geo-v2-legend-dot" style="background:#C98A55"></span>Batalla de la semana</span><span class="mp-leyenda-nota">Gana la tienda que va más adelante en su meta de la semana. Color del punto = cumplimiento del mes.</span>';
    }
    pintarInsignias();
  }

  function cambiarModo(m) {
    modo = m;
    grupoLineas.clearLayers();
    if (m === 'duelos') dibujarDuelos();
    if (ladoActual === 'duelos' && m !== 'duelos') cerrarLado();
    if (ladoActual === 'asesoras' && m !== 'asesoras') cerrarLado();
    pintarMarcas();
    colocarLado();
    if (m === 'duelos') ladoDuelos();
    if (m === 'asesoras') ladoAsesoras();
  }

  // Duelos y Asesoras los dibuja este archivo (el mapa original no los conoce)
  seg.addEventListener('click', function (ev) {
    var b = ev.target.closest('button[data-m]');
    if (!b || (b.dataset.m !== 'duelos' && b.dataset.m !== 'asesoras')) return;
    ev.stopPropagation();
    seg.querySelectorAll('button').forEach(function (x) { var on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', String(on)); });
    document.dispatchEvent(new CustomEvent('geo:modo', { detail: b.dataset.m }));
  }, true);

  function marcar(id) {
    seleccion = id;
    tiendas.forEach(function (t) {
      var n = t.marca && t.marca.getElement() && t.marca.getElement().querySelector('.mp-mk');
      if (!n) return;
      n.classList.toggle('sel', t.id === id);
      n.classList.toggle('gemela', gemelasSel.indexOf(t.id) >= 0);
    });
  }

  /* ---------------- Tienda virtual (sin punto en el mapa) ---------------- */
  var tarjetaVirtual = null;
  function pintarVirtual() {
    var vs = tiendas.filter(function (t) { return t.virtual; });
    if (!vs.length) return;
    if (!tarjetaVirtual) {
      tarjetaVirtual = sobreMapa(el('div', 'mp-capa mp-virtual'));
      tarjetaVirtual.addEventListener('click', function (e) { var b = e.target.closest('[data-id]'); if (b) abrirFicha(+b.dataset.id); });
    }
    var cfg = configModo(modo === 'red' || modo === 'duelos' || modo === 'asesoras' ? 'cumplimiento' : modo);
    tarjetaVirtual.innerHTML = vs.map(function (t) {
      var a = t.asesoras, extra = modo === 'red' ? (enHilo(t) ? '🧵 en el hilo' : 'aún no está en el hilo')
        : modo === 'asesoras' ? (a ? a.en_meta + '/' + a.con_meta + ' asesoras' : 'sin datos de asesoras')
        : modo === 'duelos' ? batallaTxt(t) : cfg.valor(t);
      return '<button type="button" data-id="' + t.id + '" title="Abrir la ficha de ' + esc(t.nombre) + '"><span class="mp-v-icono" style="--c:' + cfg.color(t) + '">🌐</span><span><b>' + esc(t.nombre) + '</b><small>' + esc(extra) + '</small></span><b class="mp-v-pct">' + pct(t.cump) + '</b></button>';
    }).join('');
  }
  function batallaTxt(t) {
    var d = duelos.filter(function (x) { return x.a === t || x.b === t; })[0];
    if (!d) return 'descansa esta semana';
    var rival = d.a === t ? d.b : d.a;
    return (d.gana === t ? '👑 gana' : d.gana ? 'va detrás' : 'empata') + ' vs ' + rival.nombre;
  }

  /* ---------------- Ficha de tienda ---------------- */
  var ficha = sobreMapa(el('div', 'mp-capa mp-ficha'));
  ficha.hidden = true;
  ficha.setAttribute('role', 'dialog');
  ficha.setAttribute('aria-label', 'Ficha de la tienda');

  function gemelas(t, n) {
    return tiendas.filter(function (o) { return o !== t && o.meta >= 0; }).map(function (o) {
      var base = (x) => Math.log(Math.max(x, 1));
      var d = Math.abs(base(o.meta || o.venta) - base(t.meta || t.venta)) + .5 * Math.abs(base(o.trafico) - base(t.trafico)) + (o.clima === t.clima ? 0 : .15);
      return { o: o, d: d };
    }).sort(function (a, b) { return a.d - b.d; }).slice(0, n || 3).map(function (x) { return x.o; });
  }

  function causa(t) {
    if (t.virtual) {
      var mk = mediana(tiendas.map(function (x) { return x.ticket; })), rk = mk ? t.ticket / mk : 1;
      return rk >= .97 ? { titulo: 'Canal virtual', detalle: 'se mide por venta y ticket; su ticket va igual o mejor que la red' }
        : { titulo: 'Ticket ' + Math.round((1 - rk) * 100) + ' % por debajo', detalle: 'canal virtual: se mide por venta y ticket (no tiene tráfico de puerta)' };
    }
    var mT = mediana(tiendas.map(function (x) { return x.trafico; })), mC = mediana(tiendas.map(function (x) { return x.conversion; })), mK = mediana(tiendas.map(function (x) { return x.ticket; }));
    var r = [
      { n: 'Tráfico', v: mT ? t.trafico / mT : 1, txt: 'entran menos personas que en la tienda típica de la red' },
      { n: 'Conversión', v: mC ? t.conversion / mC : 1, txt: 'de los que entran, compran menos que en la red' },
      { n: 'Ticket', v: mK ? t.ticket / mK : 1, txt: 'cada factura es más pequeña que en la red' }
    ].sort(function (a, b) { return a.v - b.v; });
    if (r[0].v >= .97) return { titulo: 'Va igual o mejor que la red', detalle: 'en tráfico, conversión y ticket' };
    return { titulo: r[0].n + ' ' + Math.round((1 - r[0].v) * 100) + ' % por debajo', detalle: r[0].txt };
  }

  function abrirFicha(id) {
    var t = porId[id];
    if (!t) return;
    var gem = gemelas(t, 3);
    gemelasSel = gem.map(function (g) { return g.id; });
    marcar(t.id);
    var c = causa(t), a = t.asesoras, v = t.visita, proy = t.proyeccion;
    var maxDia = Math.max.apply(null, t.dias.concat([1])), promDia = t.dias.length ? t.dias.reduce(function (s, x) { return s + x; }, 0) / t.dias.length : 0;
    var falta = t.cump >= 1
      ? '<div class="mp-falta lista">✓ <b>Ya pasó su meta</b> al corte' + (t.metaCorte ? ': va <b>' + dinero(t.venta - t.metaCorte) + '</b> por encima.' : '.') + '</div>'
      : t.falta != null ? '<div class="mp-falta">Le faltan <b>' + dinero(t.falta) + '</b> para el 100 % al corte' + (t.facturasFaltan ? ': <b>' + facturas(t.facturasFaltan) + '</b> de ' + dinero(t.ticket) + '.' : '.') + '</div>' : '';
    var mejorGem = gem.filter(function (g) { return g.cump > t.cump; }).sort(function (x, y) { return y.cump - x.cump; })[0];
    ficha.innerHTML = '<header><div><h4>' + esc(t.nombre) + '</h4><small>' + esc(t.codigo) + ' · ' + esc(t.ciudad) + ' · ' + esc(t.region) + '</small></div><button type="button" class="mp-cerrar" aria-label="Cerrar ficha"><i class="bi bi-x-lg"></i></button></header>' +
      '<div class="mp-big"><b style="color:' + colorCump(t.cump) + '">' + pct(t.cump) + '</b><span>cumplimiento al corte' + (t.delta != null ? ' · ' + (t.delta >= 0 ? 'subió ' : 'bajó ') + pts(t.delta).replace(/^[+−]/, '') + ' desde el día ' + cortePrevio : '') + '</span></div>' +
      falta +
      (t.dias.length ? '<div class="mp-dias" aria-label="Venta de cada día">' + t.dias.map(function (x, i) { return '<i class="' + (x > promDia * 1.2 ? 'alto' : '') + '" style="height:' + Math.max(4, x / maxDia * 100) + '%" title="Día ' + (i + 1) + ': ' + dinero(x) + '"></i>'; }).join('') + '</div><small style="color:#6B6259">Venta de cada día · en dorado, los días fuertes</small>' : '') +
      (proy ? '<div class="mp-fila"><i class="bi bi-graph-up-arrow"></i><span>Cierre proyectado</span><b>' + pct(proy.pct) + '</b><small>' + dinero(proy.valor) + '</small></div>' : '') +
      '<div class="mp-fila"><i class="bi bi-search"></i><span>' + esc(c.titulo) + '<br><small>' + esc(c.detalle) + '</small></span></div>' +
      (a ? '<div class="mp-fila"><i class="bi bi-people"></i><span><b>' + a.en_meta + ' de ' + a.con_meta + '</b> asesoras con meta ya la pasaron' + (a.total > a.con_meta ? '<br><small>' + (a.total - a.con_meta) + ' sin meta asignada</small>' : '') + '</span></div>' : '') +
      '<div class="mp-fila"><i class="bi bi-clipboard-check"></i><span>' + (v ? 'Última visita hace <b>' + v.dias + ' días</b><br><small>' + v.fecha.split('-').reverse().join('/') + ' · evaluación ' + String(v.pct).replace('.', ',') + ' %</small>' : t.virtual ? 'Canal virtual: no lleva visitas de supervisor' : 'Sin visitas registradas') +
        (v && v.pendientes && v.pendientes.length ? '<br><small><b>Revisar en la próxima visita:</b> ' + v.pendientes.map(function (x) { return esc(x.item); }).join(' · ') + '</small>' : '') + '</span></div>' +
      '<div class="mp-fila" style="border-bottom:0"><i class="bi bi-intersect"></i><span><b>Tiendas gemelas</b><br><small>Las más parecidas en meta y tráfico' + (mejorGem ? '. La que mejor va: ' + esc(mejorGem.nombre) : '') + '</small></span></div>' +
      '<div class="mp-gemelas">' + gem.map(function (g) { return '<button type="button" data-gemela="' + g.id + '"><span>' + esc(g.nombre) + ' <small style="color:#6B6259">· ' + esc(g.ciudad) + '</small></span><b style="color:' + colorCump(g.cump) + '">' + pct(g.cump) + '</b></button>'; }).join('') + '</div>' +
      '<div class="mp-acciones">' + (t.url ? '<a href="' + esc(t.url) + '"><i class="bi bi-shop"></i> Ver su dashboard</a>' : '') +
      '<button type="button" data-ficha="contexto"><i class="bi bi-info-circle"></i> Contexto</button>' +
      (gem.length ? '<button type="button" data-ficha="comparar"><i class="bi bi-arrow-left-right"></i> Comparar</button>' : '') + '</div>';
    ficha.hidden = false;
    ficha.dataset.id = t.id;
    ficha.querySelector('.mp-cerrar').focus({ preventScroll: true });
  }

  ficha.addEventListener('click', function (ev) {
    var t = porId[+ficha.dataset.id];
    if (ev.target.closest('.mp-cerrar')) { ficha.hidden = true; gemelasSel = []; marcar(null); return; }
    var g = ev.target.closest('[data-gemela]');
    if (g) { abrirFicha(+g.dataset.gemela); return; }
    var acc = ev.target.closest('[data-ficha]');
    if (!acc || !t) return;
    if (acc.dataset.ficha === 'contexto') {
      cerrarLado();
      var sel = document.getElementById('mapStoreSelect');
      if (sel) { sel.value = String(t.id); sel.dispatchEvent(new Event('change', { bubbles: true })); }
      var panel = document.getElementById('contextPanel');
      if (grid && grid.classList.contains('modo-red')) { var b = seg.querySelector('button[data-m="cumplimiento"]'); if (b) b.click(); }
      if (panel && window.innerWidth <= 1200) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (acc.dataset.ficha === 'comparar') {
      var A = document.getElementById('compareA'), B = document.getElementById('compareB'), otra = gemelas(t, 1)[0];
      if (A && B && otra) {
        A.value = String(t.id); B.value = String(otra.id);
        B.dispatchEvent(new Event('change', { bubbles: true }));
        A.closest('.geo-v2-card').scrollIntoView({ behavior: quieto ? 'auto' : 'smooth', block: 'center' });
      }
    }
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && !ficha.hidden) { ficha.hidden = true; gemelasSel = []; marcar(null); } });

  /* ---------------- Cambios y alertas ---------------- */
  function calcularAlertas() {
    var mT = mediana(tiendas.map(function (t) { return t.trafico; })), mC = mediana(tiendas.map(function (t) { return t.conversion; }));
    alertas = [];
    tiendas.forEach(function (t) {
      var m = [], s = t.serie;
      if (s && s.length >= 3 && s[s.length - 1][1] < s[s.length - 2][1] && s[s.length - 2][1] < s[s.length - 3][1]) m.push('Lleva 3 cortes seguidos bajando');
      if (mT && mC && t.trafico >= mT * 1.1 && t.conversion <= mC * .85) m.push('Mucho tráfico y poca conversión');
      if (t.cump < .8) m.push('Por debajo de 80 %');
      if (!t.virtual && t.visita && t.visita.dias > 30) m.push('Sin visita hace ' + t.visita.dias + ' días');
      if (m.length) alertas.push({ t: t, motivos: m });
    });
    alertas.sort(function (a, b) { return b.motivos.length - a.motivos.length || a.t.cump - b.t.cump; });
  }

  function pintarInsignias() {
    var conAlerta = {};
    alertas.forEach(function (a) { conAlerta[a.t.id] = a; });
    tiendas.forEach(function (t) {
      var n = t.insignia && t.insignia.getElement() && t.insignia.getElement().querySelector('.mp-insignias');
      if (!n) return;
      var h = '';
      if (capas.cambios && t.delta != null && Math.abs(t.delta) >= .05) h += '<span class="mp-ins ' + (t.delta > 0 ? 'sube' : 'baja') + (Math.abs(t.delta) >= 3 && !quieto ? ' fuerte' : '') + '">' + (t.delta > 0 ? '▲ ' : '▼ ') + Math.abs(t.delta).toFixed(1).replace('.', ',') + '</span>';
      if (capas.alertas && conAlerta[t.id]) h += '<span class="mp-ins alerta" title="' + esc(conAlerta[t.id].motivos.join(' · ')) + '">⚠ ' + conAlerta[t.id].motivos.length + '</span>';
      n.innerHTML = h;
    });
  }

  /* ---------------- Duelos ---------------- */
  function calcularDuelos() {
    var libres = tiendas.filter(function (t) { return t.meta > 0 || t.venta > 0; }).sort(function (a, b) { return (b.meta || b.venta) - (a.meta || a.venta); });
    duelos = [];
    while (libres.length > 1) {
      var a = libres.shift(), mejor = 0, mejorD = Infinity;
      libres.forEach(function (b, i) {
        var d = Math.abs(Math.log((a.meta || a.venta) / (b.meta || b.venta))) + (a.ciudad === b.ciudad ? .25 : 0);
        if (d < mejorD) { mejorD = d; mejor = i; }
      });
      var b = libres.splice(mejor, 1)[0];
      var va = a.delta != null ? a.delta : 0, vb = b.delta != null ? b.delta : 0;
      duelos.push({ a: a, b: b, va: va, vb: vb, gana: Math.abs(va - vb) < .05 ? null : va > vb ? a : b });
    }
  }

  function dibujarDuelos() {
    grupoLineas.clearLayers();
    duelos.forEach(function (d) {
      if (!d.a.punto || !d.b.punto) return;
      var p0 = mapa.latLngToLayerPoint(d.a.punto), p2 = mapa.latLngToLayerPoint(d.b.punto);
      var dx = p2.x - p0.x, dy = p2.y - p0.y, largo = Math.hypot(dx, dy) || 1, k = Math.min(60, largo * .2);
      var p1 = L.point((p0.x + p2.x) / 2 - dy / largo * k, (p0.y + p2.y) / 2 + dx / largo * k), lista = [];
      for (var i = 0; i <= 30; i++) { var s = i / 30; lista.push(mapa.layerPointToLatLng(L.point((1 - s) * (1 - s) * p0.x + 2 * (1 - s) * s * p1.x + s * s * p2.x, (1 - s) * (1 - s) * p0.y + 2 * (1 - s) * s * p1.y + s * s * p2.y))); }
      grupoLineas.addLayer(L.polyline(lista, { className: 'mp-duelo-linea', interactive: false }));
      var medio = mapa.layerPointToLatLng(L.point(.25 * p0.x + .5 * p1.x + .25 * p2.x, .25 * p0.y + .5 * p1.y + .25 * p2.y));
      var et = L.marker(medio, { keyboard: false, zIndexOffset: 800, icon: L.divIcon({ className: '', iconSize: [0, 0], html: '<div class="mp-duelo-et" aria-hidden="true">⚔</div>' }) });
      var fa = d.avance ? pct : pts;
      et.bindTooltip('<strong>' + esc(d.a.nombre) + '</strong> ' + fa(d.va) + ' vs <strong>' + esc(d.b.nombre) + '</strong> ' + fa(d.vb) + '<br>' + (d.gana ? '🏆 Va ganando ' + esc(d.gana.nombre) : 'Van empatadas'), { direction: 'top', className: 'geo-tip' });
      grupoLineas.addLayer(et);
    });
  }

  /* ---------------- Panel lateral sobre el mapa (duelos, asesoras, alertas, clima, ruta) ---------------- */
  // Va en la columna derecha: en lugar del «Contexto de tienda» o encima del panel del hilo
  var lado = el('aside', 'mp-lado');
  lado.hidden = true;
  lado.setAttribute('aria-live', 'polite');
  function colocarLado() {
    var hr = document.querySelector('.hr-panel'), ctx = document.getElementById('contextPanel');
    if (grid && grid.classList.contains('modo-red') && hr) hr.insertBefore(lado, hr.firstChild);
    else if (ctx) ctx.parentNode.insertBefore(lado, ctx.nextSibling);
    if (grid) grid.classList.toggle('mp-con-panel', !lado.hidden);
  }
  function abrirLado(nombre, titulo, html) {
    ladoActual = nombre;
    lado.innerHTML = '<h4>' + titulo + '<button type="button" class="mp-cerrar" style="margin-left:auto" aria-label="Cerrar panel"><i class="bi bi-x"></i></button></h4>' + html;
    lado.hidden = false;
    colocarLado();
  }
  function cerrarLado() {
    var era = ladoActual;
    lado.hidden = true; ladoActual = null;
    colocarLado();
    if (era === 'ruta') { grupoRuta.clearLayers(); rutaCiudad = null; }
    ['alertas', 'clima'].forEach(function (c) { if (era === c && capas[c]) alternarCapa(c, false); });
  }
  lado.addEventListener('click', function (ev) {
    if (ev.target.closest('.mp-cerrar')) { cerrarLado(); return; }
    var t = ev.target.closest('[data-tienda]');
    if (t) { abrirFicha(+t.dataset.tienda); var x = porId[+t.dataset.tienda]; if (x && x.punto) mapa.flyTo(x.punto, Math.max(mapa.getZoom(), 11), { duration: quieto ? 0 : .8 }); }
    var c = ev.target.closest('[data-ruta]');
    if (c) dibujarRuta(c.dataset.ruta, true);
  });

  function ladoDuelos() {
    abrirLado('duelos', '<i class="bi bi-lightning-charge"></i> Batallas de la semana', '<ul>' + duelos.map(function (d) {
      var c = function (t, v) { return '<span class="' + (d.gana === t ? 'gana' : '') + '" data-tienda="' + t.id + '" style="cursor:pointer">' + (d.gana === t ? '<i class="bi bi-trophy-fill mp-corona"></i> ' : '') + esc(t.nombre) + ' <b>' + (d.avance ? pct(v) : pts(v)) + '</b></span>'; };
      return '<li><div class="mp-vs" style="flex-wrap:wrap">' + c(d.a, d.va) + '<small style="display:inline">vs</small>' + c(d.b, d.vb) + '</div></li>';
    }).join('') + '</ul><p class="mp-nota">' + (batallas
      ? 'Las batallas de la semana: parejas de meta parecida. Gana la que va más adelante en su meta de la semana (de lunes a hoy). Detalle en Ranking de desempeño › Batallas.'
      : 'Parejas de meta parecida (de otra ciudad cuando se puede). Gana la que más sube su cumplimiento' + (cortePrevio ? ' entre el corte del día ' + cortePrevio + ' y el del día ' + (corte ? corte.dia : '') : '') + '.') + '</p>');
  }

  function ladoAsesoras() {
    var con = tiendas.filter(function (t) { return t.asesoras && t.asesoras.con_meta; });
    if (!con.length) { abrirLado('asesoras', '<i class="bi bi-people"></i> Hilo de asesoras', '<p class="mp-nota">No hay datos de asesoras para este corte.</p>'); return; }
    var en = con.reduce(function (s, t) { return s + t.asesoras.en_meta; }, 0), tot = con.reduce(function (s, t) { return s + t.asesoras.con_meta; }, 0);
    con.sort(function (a, b) { return b.asesoras.en_meta / b.asesoras.con_meta - a.asesoras.en_meta / a.asesoras.con_meta; });
    abrirLado('asesoras', '<i class="bi bi-people"></i> Hilo de asesoras', '<p style="margin:0 0 6px"><b style="font-size:22px">' + en + ' de ' + tot + '</b> asesoras con meta ya la pasaron</p><ol>' + con.map(function (t, i) {
      return '<li data-tienda="' + t.id + '" style="cursor:pointer"><span>' + (i + 1) + '</span><div><b>' + esc(t.nombre) + '</b><small>' + esc(t.ciudad) + '</small></div><b>' + t.asesoras.en_meta + '/' + t.asesoras.con_meta + '</b></li>';
    }).join('') + '</ol>');
  }

  /* ---------------- Barra de herramientas ---------------- */
  function prepararBarra() {
    var barra = document.getElementById('mpBarra');
    if (!barra) return;
    var bAlertas = barra.querySelector('[data-capa="alertas"]');
    if (bAlertas && alertas.length) bAlertas.insertAdjacentHTML('beforeend', ' <span class="mp-n">' + alertas.length + '</span>');
    if (!red || !cortePrevio) { var bc = barra.querySelector('[data-capa="cambios"]'); if (bc) bc.title = 'Se necesita más de un corte en el mes'; }
    if (!plus) ['pulso'].forEach(function (c) { var b = barra.querySelector('[data-capa="' + c + '"]'); if (b) b.hidden = true; });
    barra.addEventListener('click', function (ev) {
      var b = ev.target.closest('button');
      if (!b) return;
      if (b.dataset.capa) alternarCapa(b.dataset.capa, b.getAttribute('aria-pressed') !== 'true');
      if (b.dataset.accion === 'comparar') compararMeses();
      if (b.dataset.accion === 'ruta') abrirRuta();
      if (b.dataset.accion === 'foto') fotoDelMes();
      if (b.dataset.accion === 'completa') pantallaCompleta();
      if (b.dataset.accion === 'oficina') modoOficina();
    });
  }

  function alternarCapa(nombre, on) {
    capas[nombre] = on;
    var b = document.querySelector('#mpBarra [data-capa="' + nombre + '"]');
    if (b) b.setAttribute('aria-pressed', String(on));
    if (nombre === 'cambios' || nombre === 'alertas') pintarInsignias();
    if (nombre === 'alertas') {
      if (on) abrirLado('alertas', '<i class="bi bi-exclamation-triangle"></i> Necesitan atención', alertas.length ? '<ul>' + alertas.map(function (a) {
        return '<li data-tienda="' + a.t.id + '" style="cursor:pointer"><span style="background:#B55A4E;color:#fff">!</span><div><b>' + esc(a.t.nombre) + '</b><small>' + a.motivos.map(esc).join(' · ') + '</small></div></li>';
      }).join('') + '</ul>' : '<p class="mp-nota">Ninguna tienda tiene alertas en este corte.</p>');
      else if (ladoActual === 'alertas') cerrarLado();
    }
    if (nombre === 'cambios' && on && !(red && cortePrevio)) mensaje('Para ver cambios se necesitan al menos dos cortes en el mes.');
    if (nombre === 'clima') { if (on) mostrarClima(); else { grupoClima.clearLayers(); if (ladoActual === 'clima') cerrarLado(); } }
    if (nombre === 'pulso') { if (on) abrirPulso(); else cerrarPulso(); }
  }

  var aviso = sobreMapa(el('div', 'mp-capa hr-globo'));
  aviso.style.cssText = 'left:50%;bottom:20px;transform:translateX(-50%)';
  function mensaje(txt) { aviso.textContent = txt; aviso.classList.add('visible'); clearTimeout(aviso._t); aviso._t = setTimeout(function () { aviso.classList.remove('visible'); }, 3200); }

  /* ---------------- Clima de hoy ---------------- */
  var climaCache = null;
  function icono(tipo) {
    if (tipo === 'sol') return '<svg viewBox="0 0 32 32" aria-hidden="true"><g class="mp-sol"><circle cx="16" cy="16" r="6.5" fill="#E8B04A"/>' + [0, 45, 90, 135, 180, 225, 270, 315].map(function (g) { return '<rect x="15" y="2" width="2" height="5" rx="1" fill="#E8B04A" transform="rotate(' + g + ' 16 16)"/>'; }).join('') + '</g></svg>';
    var nube = '<g class="mp-nube"><path d="M9 22h14a5 5 0 0 0 0-10 7 7 0 0 0-13.4 2A4 4 0 0 0 9 22z" fill="' + (tipo === 'lluvia' ? '#8E99A3' : '#B9C1C8') + '"/></g>';
    if (tipo === 'lluvia') return '<svg viewBox="0 0 32 32" aria-hidden="true">' + nube + '<line class="mp-gota" x1="12" y1="24" x2="11" y2="28" stroke="#4F86B8" stroke-width="2" stroke-linecap="round"/><line class="mp-gota" x1="17" y1="24" x2="16" y2="28" stroke="#4F86B8" stroke-width="2" stroke-linecap="round"/><line class="mp-gota" x1="22" y1="24" x2="21" y2="28" stroke="#4F86B8" stroke-width="2" stroke-linecap="round"/></svg>';
    if (tipo === 'parcial') return '<svg viewBox="0 0 32 32" aria-hidden="true"><g class="mp-sol"><circle cx="11" cy="11" r="5" fill="#E8B04A"/></g>' + nube + '</svg>';
    return '<svg viewBox="0 0 32 32" aria-hidden="true">' + nube + '</svg>';
  }
  function tipoCodigo(c) { return c <= 1 ? 'sol' : c === 2 ? 'parcial' : c <= 48 ? 'nube' : 'lluvia'; }
  function mostrarClima() {
    var ciudades = {};
    tiendas.forEach(function (t) { if (t.lat != null) (ciudades[t.ciudad] = ciudades[t.ciudad] || []).push(t); });
    var lista = Object.keys(ciudades).map(function (c) {
      var l = ciudades[c];
      return { c: c, lat: l.reduce(function (s, t) { return s + t.lat; }, 0) / l.length, lng: l.reduce(function (s, t) { return s + t.lng; }, 0) / l.length, zona: l[0].clima, tiendas: l };
    });
    function pintar(datos) {
      grupoClima.clearLayers();
      lista.forEach(function (c, i) {
        var d = datos && datos[i], tipo = d ? tipoCodigo(d.weather_code) : (c.zona === 'Cálido' ? 'sol' : c.zona === 'Frío' ? 'nube' : 'parcial');
        c.tipo = tipo; c.temp = d ? Math.round(d.temperature_2m) : null;
        grupoClima.addLayer(L.marker([c.lat, c.lng], { interactive: false, keyboard: false, zIndexOffset: 1200, icon: L.divIcon({ className: '', iconSize: [0, 0], html: '<div class="mp-clima">' + icono(tipo) + esc(c.c) + (c.temp != null ? ' <small>' + c.temp + '°</small>' : ' <small>' + esc(c.zona || '') + '</small>') + '</div>' }) }));
      });
      var llueve = lista.filter(function (c) { return c.tipo === 'lluvia'; });
      var nota = datos ? (llueve.length
        ? 'Llueve ahora en <b>' + llueve.map(function (c) { return esc(c.c); }).join(', ') + '</b>. Si hoy entra menos gente a esas tiendas, revisa «Tráfico y conversión».'
        : 'No llueve en ninguna ciudad con tiendas en este momento.') : 'No se pudo consultar el clima en vivo: se muestra el clima de zona registrado de cada ciudad.';
      abrirLado('clima', '<i class="bi bi-cloud-sun"></i> Clima de hoy', '<ul>' + lista.map(function (c) {
        return '<li><span style="background:transparent;width:30px">' + icono(c.tipo) + '</span><div><b>' + esc(c.c) + '</b><small>' + (c.temp != null ? c.temp + ' °C · ' : '') + 'zona ' + esc((c.zona || '').toLowerCase()) + ' · ' + c.tiendas.length + (c.tiendas.length === 1 ? ' tienda' : ' tiendas') + '</small></div></li>';
      }).join('') + '</ul><p class="mp-nota">' + nota + '</p>');
    }
    if (climaCache) { pintar(climaCache); return; }
    var url = 'https://api.open-meteo.com/v1/forecast?latitude=' + lista.map(function (c) { return c.lat.toFixed(3); }).join(',') + '&longitude=' + lista.map(function (c) { return c.lng.toFixed(3); }).join(',') + '&current=temperature_2m,weather_code,precipitation&timezone=America%2FBogota';
    fetch(url).then(function (r) { return r.json(); }).then(function (j) {
      var arr = Array.isArray(j) ? j : [j];
      climaCache = arr.map(function (x) { return x.current; });
      if (capas.clima) pintar(climaCache);
    }).catch(function () { if (capas.clima) pintar(null); });
  }

  /* ---------------- Pulso de ventas día a día ---------------- */
  var pulso = sobreMapa(el('div', 'mp-capa mp-pulso', '<button type="button" aria-label="Reproducir el pulso"><i class="bi bi-play-fill"></i></button><input type="range" min="1" value="1" aria-label="Día"><output>Día 1</output>'));
  pulso.hidden = true;
  var pRango = pulso.querySelector('input'), pSalida = pulso.querySelector('output'), pBoton = pulso.querySelector('button'), pReloj = 0;
  function totalDia(d) { return tiendas.reduce(function (s, t) { return s + (t.dias[d - 1] || 0); }, 0); }
  function encender(d) {
    var porCiudad = {};
    tiendas.forEach(function (t) {
      var v = t.dias[d - 1] || 0;
      porCiudad[t.ciudad] = (porCiudad[t.ciudad] || 0) + v;
      if (!t.punto || !v) return;
      var prom = t.dias.reduce(function (s, x) { return s + x; }, 0) / (t.dias.length || 1);
      var r = Math.min(2.2, v / (prom || 1)), p = mapa.latLngToContainerPoint(t.punto);
      var luz = el('div', 'mp-luz');
      luz.style.cssText = 'left:' + p.x + 'px;top:' + p.y + 'px;--s:' + Math.round(20 + 46 * r) + 'px;position:absolute;z-index:640;margin:0;transform-origin:center';
      luz.style.marginLeft = luz.style.marginTop = (-(20 + 46 * r) / 2) + 'px';
      cont.appendChild(luz);
      setTimeout(function () { luz.remove(); }, 950);
    });
    var mejor = Object.keys(porCiudad).sort(function (a, b) { return porCiudad[b] - porCiudad[a]; })[0];
    var fecha = corte ? new Date(corte.anio, corte.mes - 1, d) : null;
    pSalida.innerHTML = (fecha ? DIAS[fecha.getDay()].replace(/^./, function (c) { return c.toUpperCase(); }) + ' ' : 'Día ') + d + ' · ' + dinero(totalDia(d)) + '<small>Ciudad que más vendió: ' + esc(mejor || '—') + '</small>';
  }
  function abrirPulso() {
    var n = Math.max.apply(null, tiendas.map(function (t) { return t.dias.length; }).concat([0]));
    if (!n) { mensaje('No hay ventas por día cargadas para este corte.'); alternarCapa('pulso', false); return; }
    pRango.max = n; pRango.value = 1; pulso.hidden = false;
    var hr = cont.querySelector('.hr-tiempo'); if (hr) hr.style.visibility = 'hidden';
    encender(1);
  }
  function pararPulso() { clearInterval(pReloj); pReloj = 0; pBoton.innerHTML = '<i class="bi bi-play-fill"></i>'; }
  function cerrarPulso() { pararPulso(); pulso.hidden = true; var hr = cont.querySelector('.hr-tiempo'); if (hr) hr.style.visibility = ''; }
  pRango.addEventListener('input', function () { pararPulso(); encender(+pRango.value); });
  pBoton.addEventListener('click', function () {
    if (pReloj) { pararPulso(); return; }
    if (+pRango.value >= +pRango.max) pRango.value = 1;
    encender(+pRango.value);
    pBoton.innerHTML = '<i class="bi bi-pause-fill"></i>';
    pReloj = setInterval(function () {
      if (+pRango.value >= +pRango.max) { pararPulso(); return; }
      pRango.value = +pRango.value + 1; encender(+pRango.value);
    }, quieto ? 900 : 650);
  });

  /* ---------------- Ruta de visitas ---------------- */
  var rutaCiudad = null;
  function prioridad(t) { return (1 - Math.min(t.cump, 1.2)) * 100 + (t.visita ? Math.min(t.visita.dias, 90) : 60) / 3 + (alertas.some(function (a) { return a.t === t; }) ? 10 : 0); }
  function abrirRuta() {
    var ciudades = grupos('ciudad').filter(function (c) { return c.tiendas.some(function (t) { return t.punto; }); }).sort(function (a, b) { return b.tiendas.length - a.tiendas.length || a.prom - b.prom; });
    if (!ciudades.length) return;
    rutaCiudad = rutaCiudad || ciudades[0].nombre;
    dibujarRuta(rutaCiudad, true);
  }
  function dibujarRuta(ciudad, volar) {
    rutaCiudad = ciudad;
    grupoRuta.clearLayers();
    var l = tiendas.filter(function (t) { return t.ciudad === ciudad && t.punto; }).sort(function (a, b) { return prioridad(b) - prioridad(a); });
    var orden = l.filter(function (t) { return t.cump < 1; }).concat(l.filter(function (t) { return t.cump >= 1; }));
    if (orden.length > 1) grupoRuta.addLayer(L.polyline(orden.map(function (t) { return t.punto; }), { className: 'mp-ruta-linea', interactive: false }));
    orden.forEach(function (t, i) { grupoRuta.addLayer(L.marker(t.punto, { interactive: false, keyboard: false, zIndexOffset: 1100, icon: L.divIcon({ className: '', iconSize: [0, 0], html: '<div class="mp-ruta-n">' + (i + 1) + '</div>' }) })); });
    if (!volar) return;
    var ciudades = grupos('ciudad').filter(function (c) { return c.tiendas.some(function (t) { return t.punto; }); }).sort(function (a, b) { return b.tiendas.length - a.tiendas.length; });
    var sinVisita = tiendas.filter(function (t) { return !t.virtual && (!t.visita || t.visita.dias > 30); }).length;
    abrirLado('ruta', '<i class="bi bi-signpost-split"></i> Ruta sugerida', '<div class="mp-chipitos">' + ciudades.map(function (c) { return '<button type="button" data-ruta="' + esc(c.nombre) + '" class="' + (c.nombre === ciudad ? 'on' : '') + '">' + esc(c.nombre) + '</button>'; }).join('') + '</div><ol>' + orden.map(function (t, i) {
      var d = i ? km(orden[i - 1], t) : null;
      return '<li data-tienda="' + t.id + '" style="cursor:pointer"><span>' + (i + 1) + '</span><div><b>' + esc(t.nombre) + '</b> <b style="color:' + colorCump(t.cump) + '">' + pct(t.cump) + '</b><small>' +
        (t.cump >= 1 ? 'Pasar a felicitar' : t.falta ? 'Le faltan ' + dinero(t.falta) : 'Necesita apoyo') + ' · ' + (t.visita ? 'última visita hace ' + t.visita.dias + ' días' : 'sin visitas registradas') +
        (d != null ? ' · ' + (d < .3 ? 'muy cerca' : d.toFixed(1).replace('.', ',') + ' km') : '') + '</small></div></li>';
    }).join('') + '</ol><p class="mp-nota">Primero las que más necesitan apoyo (cumplimiento, días sin visita y alertas); al final, las que ya pasaron su meta. ' + sinVisita + ' tiendas de la red llevan más de 30 días sin visita o no tienen.</p>');
    irACiudad(ciudad, { maxZoom: 13 });
  }

  /* ---------------- Meta de la red (dentro del hilo de la red) ---------------- */
  function metaDeLaRed(ev) {
    if (ev && ev.detail && !red) { red = ev.detail; }
    var panel = document.querySelector('.hr-panel');
    if (!panel || panel.querySelector('.mp-meta-red')) return;
    var total = tiendas.length, unidas = tiendas.filter(enHilo).length;
    var faltan = tiendas.filter(function (t) { return !enHilo(t); }).sort(function (a, b) { return (a.falta == null ? 1e15 : a.falta) - (b.falta == null ? 1e15 : b.falta) || b.cump - a.cump; });
    var card = el('div', 'hr-card mp-meta-red', '<h3><i class="bi bi-flag"></i> Para el hilo completo</h3>' +
      (faltan.length ? '<div class="hr-grande">' + faltan.length + ' <small>' + (faltan.length === 1 ? 'tienda falta' : 'tiendas faltan') + '</small></div><div class="hr-barra"><span style="width:' + Math.round(unidas / (total || 1) * 100) + '%"></span></div>' +
        '<p class="hr-nota">Las que lo lograrían más fácil:</p><ul class="hr-lista">' + faltan.slice(0, 4).map(function (t) {
          return '<li style="cursor:pointer" data-mp-ficha="' + t.id + '"><span class="hr-n" style="background:#C9B48F">·</span><span><b>' + esc(t.nombre) + '</b><br><small style="color:#6B6259">' + (t.falta ? 'Le faltan ' + dinero(t.falta) + (t.facturasFaltan ? ' · ' + facturas(t.facturasFaltan) : '') : pct(t.cump)) + '</small></span><span class="hr-der"><b style="color:#2D2A26">' + pct(t.cump) + '</b></span></li>';
        }).join('') + '</ul>' : '<p class="hr-nota">¡Las ' + total + ' tiendas ya están en el hilo! 🎉</p>'));
    var segunda = panel.children[1];
    panel.insertBefore(card, segunda || null);
    card.addEventListener('click', function (e) { var li = e.target.closest('[data-mp-ficha]'); if (li) abrirFicha(+li.dataset.mpFicha); });
  }

  /* ---------------- Pantalla completa y modo oficina ---------------- */
  function pantallaCompleta() {
    if (document.fullscreenElement) { document.exitFullscreen(); return; }
    if (grid && grid.requestFullscreen) grid.requestFullscreen().catch(function () { mensaje('El navegador no permitió la pantalla completa.'); });
  }
  document.addEventListener('fullscreenchange', function () {
    setTimeout(function () { mapa.invalidateSize(); reubicar(); }, 250);
    if (!document.fullscreenElement && oficina) salirOficina();
  });

  var oficina = null;
  function modoOficina() {
    if (oficina) { salirOficina(); return; }
    oficina = { paso: 0, reloj: 0 };
    grid.classList.add('mp-oficina');
    ficha.hidden = true; cerrarLado(); if (capas.pulso) alternarCapa('pulso', false);
    var tv = sobreMapa(el('div', 'mp-capa mp-tv', '<small>L&amp;H PULSE · la red en vivo</small><h3>Así se tejió el mes</h3><p>Cada tienda que pasa su meta se une al hilo dorado.</p>'));
    var salir = sobreMapa(el('button', 'mp-capa mp-tv-salir', '<i class="bi bi-x-lg"></i> Salir'));
    salir.type = 'button';
    salir.addEventListener('click', salirOficina);
    oficina.tv = tv; oficina.salir = salir;
    var entrar = grid.requestFullscreen ? grid.requestFullscreen() : Promise.reject();
    entrar.catch(function () { grid.style.cssText = 'position:fixed;inset:0;z-index:2500;padding:18px;background:#1d1915;overflow:auto'; }).finally(function () {
      setTimeout(function () {
        mapa.invalidateSize();
        var b = seg.querySelector('button[data-m="red"]');
        if (b && !b.classList.contains('on')) b.click();
        if (window.__hiloRed && b) setTimeout(function () { if (oficina) window.__hiloRed.reproducir(); }, 1500);
        else recorrer();
      }, 400);
    });
    document.addEventListener('hilo:dia', finDelHilo);
  }
  function finDelHilo(ev) {
    if (!oficina || !ev.detail || ev.detail.dia < ev.detail.fin || oficina.recorriendo) return;
    oficina.recorriendo = true;
    setTimeout(recorrer, 4500);
  }
  function recorrer() {
    if (!oficina) return;
    var ciudades = grupos('ciudad').filter(function (c) { return c.tiendas.some(function (t) { return t.punto; }); }).sort(function (a, b) { return b.tiendas.length - a.tiendas.length || b.prom - a.prom; });
    var i = 0;
    function siguiente() {
      if (!oficina) return;
      if (i >= ciudades.length) {
        tarjeta('Toda la red', tiendas.filter(enHilo).length + ' de ' + tiendas.length + ' tiendas en el hilo dorado', pct(tiendas.reduce(function (s, t) { return s + t.cump; }, 0) / (tiendas.length || 1)), 'cumplimiento promedio', '¡Cada venta cuenta!', '');
        mapa.flyToBounds(L.latLngBounds(tiendas.filter(function (t) { return t.punto; }).map(function (t) { return [t.lat, t.lng]; })).pad(.15), { duration: quieto ? 0 : 2 });
        oficina.reloj = setTimeout(function () { if (!oficina) return; oficina.recorriendo = false; if (window.__hiloRed) window.__hiloRed.reproducir(); else { i = 0; siguiente(); } }, 9000);
        return;
      }
      var c = ciudades[i++], mejor = c.tiendas.slice().sort(function (a, b) { return b.cump - a.cump; })[0];
      irACiudad(c.nombre, { maxZoom: 12, duration: quieto ? 0 : 2 });
      tarjeta(c.nombre, c.unidas + ' de ' + c.tiendas.length + (c.tiendas.length === 1 ? ' tienda' : ' tiendas') + ' en el hilo dorado', pct(c.prom), 'cumplimiento promedio', esc(mejor.nombre), 'va adelante con ' + pct(mejor.cump));
      oficina.reloj = setTimeout(siguiente, 8000);
    }
    siguiente();
  }
  function tarjeta(titulo, frase, n1, l1, n2, l2) {
    var tv = oficina.tv;
    tv.classList.add('cambia');
    setTimeout(function () {
      tv.innerHTML = '<small>L&amp;H PULSE · la red en vivo</small><h3>' + esc(titulo) + '</h3><p>' + frase + '</p><div class="mp-tv-big"><div><b>' + n1 + '</b><span>' + l1 + '</span></div>' + (n2 ? '<div><b style="font-size:22px;line-height:1.6">' + n2 + '</b><span>' + l2 + '</span></div>' : '') + '</div>';
      tv.classList.remove('cambia');
    }, quieto ? 0 : 400);
  }
  function salirOficina() {
    if (!oficina) return;
    clearTimeout(oficina.reloj);
    oficina.tv.remove(); oficina.salir.remove();
    document.removeEventListener('hilo:dia', finDelHilo);
    oficina = null;
    grid.classList.remove('mp-oficina'); grid.style.cssText = '';
    if (document.fullscreenElement) document.exitFullscreen();
    setTimeout(function () { mapa.invalidateSize(); reubicar(); }, 300);
  }

  /* ---------------- Ventanas ---------------- */
  function ventana(titulo, cabecera, cuerpo) {
    var m = el('div', 'mp-modal', '<div class="mp-caja" role="dialog" aria-modal="true" aria-label="' + esc(titulo) + '"><header><h3>' + esc(titulo) + '</h3>' + (cabecera || '') + '<button type="button" class="mp-cerrar" style="margin-left:auto" aria-label="Cerrar"><i class="bi bi-x-lg"></i></button></header>' + cuerpo + '</div>');
    document.body.appendChild(m);
    var cerrar = function () { m.remove(); document.removeEventListener('keydown', tecla); if (m._alCerrar) m._alCerrar(); };
    var tecla = function (e) { if (e.key === 'Escape') cerrar(); };
    m.addEventListener('click', function (e) { if (e.target === m || e.target.closest('.mp-cerrar')) cerrar(); });
    document.addEventListener('keydown', tecla);
    m.querySelector('.mp-cerrar').focus();
    return m;
  }

  /* ---------------- Comparar meses (mapa partido en dos) ---------------- */
  function periodos() {
    var sel = document.getElementById('filtroPeriodoV2');
    return sel ? Array.prototype.map.call(sel.options, function (o) { return o.value; }).filter(function (v) { return /^\d{4}-\d{2}-\d{2}$/.test(v); }) : [];
  }
  function periodoPara(anio, mes, dia) {
    var p = periodos().filter(function (v) { return +v.slice(0, 4) === anio && +v.slice(5, 7) === mes; }).sort();
    if (!p.length) return null;
    var antes = p.filter(function (v) { return +v.slice(8) <= dia; });
    return antes.length ? antes[antes.length - 1] : p[0];
  }
  function compararMeses() {
    if (!corte) { mensaje('No hay datos del corte para comparar.'); return; }
    var actual = filtros.periodo && /^\d{4}-\d{2}-\d{2}$/.test(filtros.periodo) ? filtros.periodo : corte.anio + '-' + String(corte.mes).padStart(2, '0') + '-' + String(corte.dia).padStart(2, '0');
    var a = +actual.slice(0, 4), m = +actual.slice(5, 7), d = +actual.slice(8);
    var opciones = {
      anterior: periodoPara(m === 1 ? a - 1 : a, m === 1 ? 12 : m - 1, d),
      anio: periodoPara(a - 1, m, d)
    };
    var cab = '<div class="mp-seg"><button type="button" data-cmp="anterior">Mes anterior</button><button type="button" data-cmp="anio">Mismo mes del año pasado</button></div>';
    var v = ventana('Comparar meses', cab, '<div class="mp-dos"><div><h4 class="mp-izq"></h4><div class="mp-mapita"></div></div><div><h4 class="mp-der"></h4><div class="mp-mapita"></div></div></div><div class="mp-cambios"></div><p class="mp-nota" style="color:#6B6259;font-size:12.5px;margin:10px 0 0">Color del punto: cumplimiento al corte (verde 100 % o más, ámbar 90 a 99,9 %, naranja 80 a 89,9 %, rojo menos de 80 %). Mueve un mapa y el otro lo sigue.</p>');
    var divs = v.querySelectorAll('.mp-mapita'), mapas = [], sincronizando = false;
    divs.forEach(function (div) {
      var mm = L.map(div, { zoomSnap: .25, scrollWheelZoom: true, attributionControl: false });
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(mm);
      mapas.push(mm);
    });
    mapas.forEach(function (mm, i) {
      mm.on('move', function () { if (sincronizando) return; sincronizando = true; mapas[1 - i].setView(mm.getCenter(), mm.getZoom(), { animate: false }); sincronizando = false; });
    });
    var conPunto = tiendas.filter(function (t) { return t.punto; });
    var limites = L.latLngBounds(conPunto.map(function (t) { return [t.lat, t.lng]; })).pad(.1);
    mapas[1].fitBounds(limites);
    pintarMapita(mapas[1], tiendas);
    v.querySelector('.mp-der').innerHTML = 'Ahora · <b>' + MESES[m - 1] + ' ' + a + ' (día ' + d + ')</b>';
    function cargar(cual) {
      v.querySelectorAll('[data-cmp]').forEach(function (b) { b.classList.toggle('on', b.dataset.cmp === cual); b.disabled = !opciones[b.dataset.cmp]; });
      var p = opciones[cual];
      var izq = v.querySelector('.mp-izq'), caja = v.querySelector('.mp-cambios');
      if (!p) { izq.textContent = 'Sin datos para ese mes'; caja.innerHTML = ''; return; }
      izq.innerHTML = 'Antes · <b>' + MESES[+p.slice(5, 7) - 1] + ' ' + p.slice(0, 4) + ' (día ' + (+p.slice(8)) + ')</b>';
      caja.innerHTML = '<p class="mp-nota">Cargando…</p>';
      traer(config.urls.tiendas + '?' + consulta({ periodo: p, tienda: '' })).then(function (lista) {
        var antes = {};
        lista.forEach(function (x) { antes[x.id] = x; });
        var otras = tiendas.map(function (t) { var x = antes[t.id]; return Object.assign({}, t, { cump: x ? +x.cumplimiento_pct || 0 : null, venta: x ? +x.venta_actual || 0 : 0 }); });
        pintarMapita(mapas[0], otras);
        mapas[0].setView(mapas[1].getCenter(), mapas[1].getZoom(), { animate: false });
        var cambios = tiendas.filter(function (t) { return antes[t.id]; }).map(function (t) { return { t: t, d: (t.cump - (+antes[t.id].cumplimiento_pct || 0)) * 100 }; }).sort(function (x, y) { return y.d - x.d; });
        var enMetaAntes = otras.filter(function (t) { return t.cump >= 1; }).length, enMeta = tiendas.filter(function (t) { return t.cump >= 1; }).length;
        var fila = function (c) { return '<li><span>' + esc(c.t.nombre) + ' <small style="color:#6B6259">· ' + esc(c.t.ciudad) + '</small></span><b style="color:' + (c.d >= 0 ? COL.ok : COL.bad) + '">' + pts(c.d) + '</b></li>'; };
        caja.innerHTML = '<section><h5>Tiendas en meta</h5><p style="margin:0;font-size:14px">Antes <b>' + enMetaAntes + '</b> → ahora <b>' + enMeta + '</b> de ' + tiendas.length + '.</p></section>' +
          '<section><h5>Subieron</h5><ul>' + (cambios.filter(function (c) { return c.d > 0; }).slice(0, 5).map(fila).join('') || '<li>Ninguna tienda subió.</li>') + '</ul></section>' +
          '<section><h5>Bajaron</h5><ul>' + (cambios.filter(function (c) { return c.d < 0; }).reverse().slice(0, 5).map(fila).join('') || '<li>Ninguna tienda bajó. 🎉</li>') + '</ul></section>';
      }).catch(function () { caja.innerHTML = '<p class="mp-nota">No se pudieron cargar los datos de ese mes.</p>'; });
    }
    v.querySelectorAll('[data-cmp]').forEach(function (b) { b.addEventListener('click', function () { cargar(b.dataset.cmp); }); });
    setTimeout(function () { mapas.forEach(function (mm) { mm.invalidateSize(); }); mapas[1].fitBounds(limites); cargar(opciones.anterior ? 'anterior' : 'anio'); }, 60);
    v._alCerrar = function () { mapas.forEach(function (mm) { mm.remove(); }); };
  }
  function pintarMapita(mm, lista) {
    if (mm._capa) mm.removeLayer(mm._capa);
    var maxV = Math.max.apply(null, lista.map(function (t) { return t.venta || 0; }).concat([1]));
    mm._capa = L.layerGroup(lista.filter(function (t) { return t.lat != null; }).map(function (t) {
      var p = t.grupo > 1 ? (function () { var a = 2 * Math.PI * t.indice / t.grupo - Math.PI / 2; return [t.lat + Math.sin(-a) * .01 * t.grupo / 2, t.lng + Math.cos(a) * .012 * t.grupo / 2]; })() : [t.lat, t.lng];
      return L.circleMarker(p, { radius: 6 + 9 * Math.sqrt((t.venta || 0) / maxV), color: '#fff', weight: 2, fillColor: t.cump == null ? '#C9C1B5' : colorCump(t.cump), fillOpacity: .92 })
        .bindTooltip('<strong>' + esc(t.nombre) + '</strong><br>' + (t.cump == null ? 'Sin datos' : 'Cumplimiento ' + pct(t.cump)));
    })).addTo(mm);
  }

  /* ---------------- Foto del mes ---------------- */
  function fotoDelMes() {
    var c = document.createElement('canvas'), W = 1080, H = 1350;
    c.width = W; c.height = H;
    var g = c.getContext('2d');
    var fondo = g.createLinearGradient(0, 0, W, H);
    fondo.addColorStop(0, '#2c2925'); fondo.addColorStop(.6, '#34302b'); fondo.addColorStop(1, '#23272b');
    g.fillStyle = fondo; g.fillRect(0, 0, W, H);
    var halo = g.createRadialGradient(W * .7, H * .25, 10, W * .7, H * .25, 600);
    halo.addColorStop(0, 'rgba(197,168,128,.25)'); halo.addColorStop(1, 'rgba(197,168,128,0)');
    g.fillStyle = halo; g.fillRect(0, 0, W, H);
    var F = 'Inter, "Segoe UI", system-ui, sans-serif';
    g.fillStyle = '#C9A97F'; g.font = '700 26px ' + F; g.fillText('L & H   P U L S E', 70, 96);
    g.fillStyle = '#F5F0E8'; g.font = '800 84px ' + F; g.fillText('La red tejida', 66, 196);
    g.fillStyle = '#D8CABB'; g.font = '500 32px ' + F;
    var mesTxt = corte ? MESES[corte.mes - 1].replace(/^./, function (x) { return x.toUpperCase(); }) + ' ' + corte.anio + ' · corte del día ' + corte.dia : '';
    g.fillText(mesTxt, 70, 250);
    // Mapa: puntos de las tiendas proyectados en el recuadro
    var con = tiendas.filter(function (t) { return t.lat != null; });
    var box = { x: 90, y: 300, w: 900, h: 640 };
    var minLat = Math.min.apply(null, con.map(function (t) { return t.lat; })), maxLat = Math.max.apply(null, con.map(function (t) { return t.lat; }));
    var minLng = Math.min.apply(null, con.map(function (t) { return t.lng; })), maxLng = Math.max.apply(null, con.map(function (t) { return t.lng; }));
    var esc2 = Math.min(box.w / ((maxLng - minLng) || 1), box.h / ((maxLat - minLat) || 1)) * .9;
    var cx = box.x + box.w / 2, cy = box.y + box.h / 2, mLat = (minLat + maxLat) / 2, mLng = (minLng + maxLng) / 2;
    con.forEach(function (t) {
      var x = cx + (t.lng - mLng) * esc2, y = cy - (t.lat - mLat) * esc2;
      if (t.grupo > 1) { var a = 2 * Math.PI * t.indice / t.grupo - Math.PI / 2; x += Math.cos(a) * (16 + t.grupo * 3); y += Math.sin(a) * (16 + t.grupo * 3); }
      t._x = x; t._y = y;
    });
    g.strokeStyle = 'rgba(245,240,232,.06)'; g.lineWidth = 1;
    for (var i = 0; i <= 8; i++) { g.beginPath(); g.moveTo(box.x, box.y + i * box.h / 8); g.lineTo(box.x + box.w, box.y + i * box.h / 8); g.stroke(); g.beginPath(); g.moveTo(box.x + i * box.w / 8, box.y); g.lineTo(box.x + i * box.w / 8, box.y + box.h); g.stroke(); }
    var unidas = con.filter(enHilo).sort(function (a, b) { return (a.union || 0) - (b.union || 0) || a.orden - b.orden; });
    var todasUnidas = tiendas.filter(enHilo).sort(function (a, b) { return (a.union || 0) - (b.union || 0) || a.orden - b.orden; });
    g.lineCap = 'round';
    for (var k = 1; k < unidas.length; k++) {
      var p0 = unidas[k - 1], p2 = unidas[k], dx = p2._x - p0._x, dy = p2._y - p0._y, largo = Math.hypot(dx, dy) || 1, kk = Math.min(90, largo * .28);
      var c1x = (p0._x + p2._x) / 2 - dy / largo * kk, c1y = (p0._y + p2._y) / 2 + dx / largo * kk;
      g.shadowColor = 'rgba(232,199,126,.9)'; g.shadowBlur = 18; g.strokeStyle = '#E8C77E'; g.lineWidth = 5;
      g.beginPath(); g.moveTo(p0._x, p0._y); g.quadraticCurveTo(c1x, c1y, p2._x, p2._y); g.stroke();
    }
    g.shadowBlur = 0;
    con.forEach(function (t) {
      var u = enHilo(t);
      g.beginPath(); g.arc(t._x, t._y, u ? 13 : 9, 0, Math.PI * 2);
      g.fillStyle = u ? '#E8C77E' : '#6F665D'; g.fill();
      g.lineWidth = 4; g.strokeStyle = '#FDFBF7'; g.stroke();
      if (u) { g.fillStyle = '#F5F0E8'; g.font = '700 21px ' + F; g.fillText(t.nombre, t._x + 18, t._y + 7); }
    });
    // Pie: cuántas y quiénes
    g.fillStyle = 'rgba(253,251,247,.07)'; redondo(g, 70, 980, 940, 300, 30); g.fill();
    g.fillStyle = '#E8C77E'; g.font = '800 96px ' + F; g.fillText(todasUnidas.length + ' de ' + tiendas.length, 110, 1095);
    g.fillStyle = '#D8CABB'; g.font = '600 30px ' + F; g.fillText('tiendas pasaron su meta y se unieron al hilo', 112, 1145);
    g.fillStyle = '#F5F0E8'; g.font = '600 24px ' + F;
    var nombres = todasUnidas.map(function (t) { return (t.virtual ? '🌐 ' : '') + t.nombre; }), linea = '', yy = 1200;
    nombres.forEach(function (n, i) { var prueba = linea + (linea ? ' · ' : '') + n; if (g.measureText(prueba).width > 860 && linea) { g.fillText(linea, 112, yy); yy += 34; linea = n; } else linea = prueba; if (i === nombres.length - 1) g.fillText(linea, 112, yy); });
    g.fillStyle = '#C9A97F'; g.font = '700 24px ' + F; g.fillText('¡Cada venta cuenta! 🧵', 70, 1318);
    var nombre = 'foto_del_mes_' + (corte ? corte.anio + '_' + String(corte.mes).padStart(2, '0') : 'red') + '.png';
    var v = ventana('Foto del mes', '', '<div class="mp-foto-vista"><div class="mp-lienzo"></div><div><p>Una imagen lista para mandar por WhatsApp a las tiendas: el hilo dorado del mes con las tiendas que ya pasaron su meta.</p><p><button type="button" class="mp-boton" data-foto="bajar"><i class="bi bi-download"></i> Descargar imagen</button> <button type="button" class="mp-boton sec" data-foto="copiar"><i class="bi bi-clipboard"></i> Copiar</button></p><p class="mp-nota" data-foto-nota></p></div></div>');
    v.querySelector('.mp-lienzo').appendChild(c);
    v.addEventListener('click', function (e) {
      var b = e.target.closest('[data-foto]');
      if (!b) return;
      var nota = v.querySelector('[data-foto-nota]');
      if (b.dataset.foto === 'bajar') { var a = document.createElement('a'); a.download = nombre; a.href = c.toDataURL('image/png'); a.click(); nota.textContent = 'Descargada como ' + nombre + '.'; }
      else c.toBlob(function (blob) {
        if (!navigator.clipboard || !window.ClipboardItem) { nota.textContent = 'Este navegador no deja copiar imágenes: usa «Descargar imagen».'; return; }
        navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]).then(function () { nota.textContent = 'Copiada. Pégala en WhatsApp con Ctrl+V.'; }, function () { nota.textContent = 'No se pudo copiar: usa «Descargar imagen».'; });
      });
    });
  }
  function redondo(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
})();
