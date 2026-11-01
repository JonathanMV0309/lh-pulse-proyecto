/* ================================================================
   El hilo que une la red · modo «Hilo de la red» del mapa (Mapa y resultados)
   - Cada tienda que pasa su meta al corte se une a un hilo dorado que va
     de la última tienda unida a la nueva.
   - ▶ reproduce el mes día a día con los cortes cargados.
   - Las que están cerca (93 % o más) se ven con una línea punteada.
   Solo lee /api/hilo/admin/red. Al salir del modo el mapa queda como estaba.
   ================================================================ */
(function () {
  'use strict';
  /* ---------- Inicio del administrador: tarjeta en «Centro de control» ---------- */
  var bienvenida = document.querySelector('.welcome-panel');
  if (bienvenida && document.getElementById('dashboard-v2-data')) {
    var q = new URLSearchParams(location.search), consulta = new URLSearchParams();
    ['anio', 'mes', 'dia_corte'].forEach(function (k) { if (q.get(k)) consulta.set(k, q.get(k)); });
    fetch('/api/hilo/admin/red?' + consulta, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.ok || !d.total) return;
      var periodo = d.corte.anio + '-' + String(d.corte.mes).padStart(2, '0') + '-' + String(d.corte.dia).padStart(2, '0');
      var css = document.createElement('style');
      css.textContent = '.hr-tarjeta { position: relative; z-index: 1; margin-left: auto; display: flex; align-items: center; gap: 12px; padding: 12px 16px 12px 12px; border-radius: 16px; background: linear-gradient(135deg, #2D2A26, #3d352e); color: #F5F0E8; text-decoration: none; box-shadow: 0 10px 26px rgba(45,42,38,.18); transition: transform .2s, box-shadow .2s; flex: none; }' +
        '.hr-tarjeta:hover { color: #F5F0E8; transform: translateY(-2px); box-shadow: 0 14px 30px rgba(45,42,38,.24); }' +
        '.hr-tarjeta svg { width: 40px; height: 40px; flex: none; } .hr-tarjeta b { display: block; font-size: 15px; } .hr-tarjeta small { display: block; color: #D8CABB; font-size: 12px; } .hr-tarjeta .bi { color: #E8C77E; margin-left: 4px; }' +
        '@media (max-width: 760px) { .hr-tarjeta { margin: 14px 0 0; width: 100%; } }';
      document.head.appendChild(css);
      var h = 4 + 26 * d.unidas / d.total;
      var a = document.createElement('a');
      a.className = 'hr-tarjeta';
      a.href = '/dashboard/geografico-v2?periodo=' + periodo + '#hilo';
      a.setAttribute('aria-label', 'La red tejida: ' + d.unidas + ' de ' + d.total + ' tiendas pasaron su meta. Ver el hilo en el mapa');
      a.innerHTML = '<svg viewBox="0 0 54 54" aria-hidden="true"><rect x="10" y="6" width="34" height="6" rx="3" fill="#C98A55"/><rect x="10" y="42" width="34" height="6" rx="3" fill="#C98A55"/><rect x="14" y="' + (42 - h) + '" width="26" height="' + h + '" rx="4" fill="#E8C77E"/><circle cx="23" cy="25" r="2.6" fill="#2B1F17"/><circle cx="31" cy="25" r="2.6" fill="#2B1F17"/></svg>' +
        '<span><b>La red tejida: ' + d.unidas + ' de ' + d.total + '</b><small>' + (d.nuevas.length ? (d.nuevas.length === 1 ? d.nuevas[0] + ' se unió en el último corte' : d.nuevas.length + ' tiendas se unieron en el último corte') : 'Tiendas que ya pasaron su meta') + '</small></span><i class="bi bi-arrow-right"></i>';
      if (getComputedStyle(bienvenida).display !== 'flex') bienvenida.style.display = 'flex';
      bienvenida.style.flexWrap = 'wrap'; bienvenida.style.alignItems = 'center';
      bienvenida.appendChild(a);
    }).catch(function () { /* sin tarjeta */ });
  }

  var boton = document.querySelector('#mapMetric button[data-m="red"]');
  var contenedor = document.getElementById('mapContainer');
  if (!boton || !contenedor) return;
  var config = {};
  try { config = JSON.parse(document.getElementById('geoV2Config').textContent); } catch (e) { /* sin configuración */ }
  var quieto = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var estilo = document.createElement('style');
  estilo.textContent = [
    '.geo-map.modo-red .leaflet-tile-pane { filter: grayscale(.55) sepia(.55) brightness(.42) contrast(1.15); transition: filter .6s; }',
    '.geo-map .leaflet-tile-pane { transition: filter .6s; }',
    '.geo-map.modo-red .geo-mk-wrap { opacity: 0; pointer-events: none; }',
    '.hr-hilo { stroke: #E8C77E; stroke-width: 3.2; fill: none; stroke-linecap: round; filter: drop-shadow(0 0 4px rgba(232,199,126,.9)) drop-shadow(0 0 10px rgba(197,168,128,.6)); }',
    '.hr-sombra { stroke: rgba(90,64,20,.45); stroke-width: 5; fill: none; stroke-linecap: round; }',
    '.hr-futuro { stroke: rgba(232,199,126,.6); stroke-width: 1.6; stroke-dasharray: 4 7; fill: none; animation: hrLatir 1.6s ease-in-out infinite; }',
    '@keyframes hrLatir { 50% { stroke-opacity: .25; } }',
    '.hr-tienda { position: relative; width: 18px; height: 18px; }',
    '.hr-tienda b { position: absolute; inset: 0; border-radius: 50%; background: #6F665D; border: 3px solid #FDFBF7; box-shadow: 0 3px 10px rgba(0,0,0,.35); transition: background .5s, transform .5s; }',
    '.hr-tienda.unida b { background: radial-gradient(circle at 35% 30%, #FFF1C9, #E8C77E 45%, #B98A3E); transform: scale(1.2); }',
    '.hr-tienda.unida::after { content: ""; position: absolute; inset: -8px; border-radius: 50%; border: 2px solid rgba(232,199,126,.7); animation: hrOnda 2.4s ease-out infinite; }',
    '.hr-tienda.cerca b { background: #C9B48F; }',
    '@keyframes hrOnda { from { transform: scale(.6); opacity: 1; } to { transform: scale(1.7); opacity: 0; } }',
    '.hr-tienda span { display: none; position: absolute; left: 50%; top: 23px; transform: translateX(-50%); padding: 2px 8px; border-radius: 999px; background: rgba(29,25,21,.85); color: #F5F0E8; font: 600 11px Inter, system-ui, sans-serif; white-space: nowrap; }',
    '.hr-tienda.unida span, .hr-tienda.cerca span { display: block; } .hr-tienda.unida span { background: #B98A3E; color: #fff; }',
    '.hr-tienda.arriba span { top: auto; bottom: 23px; } .hr-tienda.der span { left: 23px; top: 50%; transform: translateY(-50%); } .hr-tienda.izq span { left: auto; right: 23px; top: 50%; transform: translateY(-50%); }',
    '.hr-chispa { position: absolute; z-index: 650; width: 90px; height: 90px; margin: -45px 0 0 -45px; border-radius: 50%; background: radial-gradient(circle, rgba(255,233,170,.95), rgba(232,199,126,.4) 35%, transparent 70%); animation: hrChispa 1.1s ease-out forwards; pointer-events: none; }',
    '@keyframes hrChispa { from { transform: scale(.2); opacity: 1; } to { transform: scale(1.6); opacity: 0; } }',
    '.hr-capa { position: absolute; z-index: 1000; pointer-events: none; }', '.hr-capa[hidden] { display: none; }',
    '.hr-capa > * { pointer-events: auto; }',
    '.hr-carrete { left: 14px; bottom: 14px; display: flex; align-items: center; gap: 10px; padding: 10px 14px 10px 10px; border-radius: 16px; background: rgba(29,25,21,.85); color: #F5F0E8; }',
    '.hr-carrete svg { width: 44px; height: 44px; } .hr-carrete b { display: block; font-size: 14px; } .hr-carrete small { color: #D8CABB; }',
    '.hr-tiempo { right: 14px; bottom: 14px; display: flex; align-items: center; gap: 10px; width: min(420px, calc(100% - 222px)); padding: 8px 12px; border-radius: 14px; background: rgba(29,25,21,.85); color: #F5F0E8; }',
    '.hr-tiempo button { display: grid; place-items: center; width: 34px; height: 34px; flex: none; border: 0; border-radius: 50%; background: #C5A880; color: #2D2A26; cursor: pointer; }',
    '.hr-tiempo input { flex: 1; accent-color: #E8C77E; } .hr-tiempo output { min-width: 56px; font-weight: 700; font-variant-numeric: tabular-nums; }',
    '.hr-globo { left: 14px; bottom: 84px; max-width: 300px; padding: 9px 13px; border-radius: 14px 14px 14px 4px; background: #FDFBF7; color: #2D2A26; font: 600 13px Inter, system-ui, sans-serif; box-shadow: 0 12px 28px rgba(0,0,0,.3); opacity: 0; transform: translateY(6px); transition: opacity .3s, transform .4s; }',
    '.hr-globo.visible { opacity: 1; transform: none; }',
    '.hr-panel { display: none; }',
    '.geo-v2-main-grid.modo-red #contextPanel { display: none; }',
    '.geo-v2-main-grid.modo-red .hr-panel { display: flex; flex-direction: column; gap: 14px; }',
    '.hr-card { padding: 16px 18px; border-radius: 18px; background: #FDFBF7; border: 1px solid rgba(139,125,107,.15); box-shadow: 0 8px 30px rgba(45,42,38,.06); }',
    '.hr-card h3 { margin: 0 0 10px; font-size: 15px; font-weight: 800; display: flex; gap: 8px; align-items: center; } .hr-card h3 i { color: #B98A3E; }',
    '.hr-grande { font: 800 32px/1 Inter, system-ui, sans-serif; letter-spacing: -.03em; } .hr-grande small { font-size: 14px; color: #6B6259; font-weight: 600; }',
    '.hr-barra { height: 10px; margin-top: 10px; border-radius: 99px; background: #EEE6D8; overflow: hidden; } .hr-barra span { display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, #B98A3E, #E8C77E); transition: width .8s; }',
    '.hr-lista { list-style: none; margin: 0; padding: 0; max-height: 300px; overflow: auto; } .hr-lista li { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid #F1EBE0; font-size: 13px; }',
    '.hr-lista li:last-child { border-bottom: 0; } .hr-n { display: grid; place-items: center; width: 22px; height: 22px; flex: none; border-radius: 50%; background: #C5A880; color: #fff; font-weight: 800; font-size: 11px; }',
    '.hr-lista .hr-der { margin-left: auto; color: #6B6259; font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; } .hr-lista li.nuevo { animation: hrEntra .6s; }',
    '@keyframes hrEntra { from { background: #FFF3D6; } to { background: transparent; } }',
    '.hr-nota { margin: 8px 0 0; color: #6B6259; font-size: 12.5px; }',
    '@media (max-width: 760px) { .hr-tiempo { left: 14px; width: auto; bottom: 74px; } .hr-globo { bottom: 130px; } }',
    '@media (prefers-reduced-motion: reduce) { .hr-tienda.unida::after, .hr-futuro { animation: none; } }'
  ].join('\n');
  document.head.appendChild(estilo);

  var vistaAntes = null, mapa = null, datos = null, activo = false, capas = [], marcadores = [], dia = 1, corriendo = 0, unidasAntes = 0, globoT = 0;
  var grid = document.querySelector('.geo-v2-main-grid'), leyenda = document.getElementById('mapLegend'), leyendaAntes = '';

  // Elementos sobre el mapa y panel lateral
  var capaCarrete = el('div', 'hr-capa hr-carrete', '<svg viewBox="0 0 54 54" aria-hidden="true"><rect x="10" y="6" width="34" height="6" rx="3" fill="#C98A55"/><rect x="10" y="42" width="34" height="6" rx="3" fill="#C98A55"/><rect class="hr-hilo-rect" x="14" y="38" width="26" height="4" rx="4" fill="#E8C77E"/><circle cx="23" cy="25" r="2.6" fill="#2B1F17"/><circle cx="31" cy="25" r="2.6" fill="#2B1F17"/></svg><div><b class="hr-cuenta">—</b><small>en el hilo dorado</small></div>');
  var capaTiempo = el('div', 'hr-capa hr-tiempo', '<button type="button" aria-label="Reproducir el mes"><i class="bi bi-play-fill"></i></button><input type="range" min="1" value="1" aria-label="Día del mes"><output>Día 1</output>');
  var globo = el('div', 'hr-capa hr-globo'); globo.setAttribute('role', 'status');
  var panel = el('aside', 'hr-panel', '<div class="hr-card"><h3><i class="bi bi-diagram-3"></i> La red tejida</h3><div class="hr-grande hr-pct">—</div><div class="hr-barra"><span style="width:0%"></span></div><p class="hr-nota hr-frase"></p></div>' +
    '<div class="hr-card"><h3><i class="bi bi-stars"></i> Se unieron al hilo</h3><ul class="hr-lista hr-unidas"></ul></div>' +
    '<div class="hr-card"><h3><i class="bi bi-hourglass-split"></i> A punto de unirse</h3><ul class="hr-lista hr-cerca"></ul><p class="hr-nota">La línea punteada muestra a dónde iría el hilo.</p></div>');
  // Van dentro del propio mapa; los clics sobre ellos no mueven el mapa
  [capaCarrete, capaTiempo, globo].forEach(function (n) {
    n.hidden = true; contenedor.appendChild(n);
    if (window.L && L.DomEvent) { L.DomEvent.disableClickPropagation(n); L.DomEvent.disableScrollPropagation(n); }
  });
  var contexto = document.getElementById('contextPanel');
  if (contexto) contexto.parentNode.insertBefore(panel, contexto.nextSibling);
  var rango = capaTiempo.querySelector('input'), salida = capaTiempo.querySelector('output'), play = capaTiempo.querySelector('button');

  document.addEventListener('geo:modo', function (e) { if (e.detail === 'red') entrar(); else salir(); });
  // «Hilo de la red» es el primer botón y la vista principal del mapa.
  // Con ?mapa=cumplimiento (o ventas, conversion, score) se abre en ese otro modo.
  boton.parentNode.insertBefore(boton, boton.parentNode.firstElementChild);
  var pedido = new URLSearchParams(location.search).get('mapa');
  if (!pedido || pedido === 'red' || location.hash === '#hilo') {
    var intentos = 0, esperar = setInterval(function () {
      if (window.__geoMapa && document.querySelector('.geo-mk-wrap') || ++intentos > 40) {
        clearInterval(esperar);
        if (window.__geoMapa) { boton.click(); if (location.hash === '#hilo') contenedor.scrollIntoView({ block: 'center' }); }
      }
    }, 250);
  }

  async function entrar() {
    mapa = window.__geoMapa || null;
    if (!mapa || activo) return;
    activo = true;
    contenedor.classList.add('modo-red');
    if (grid) grid.classList.add('modo-red');
    [capaCarrete, capaTiempo, globo].forEach(function (n) { n.hidden = false; });
    if (leyenda) { leyendaAntes = leyenda.innerHTML; leyenda.innerHTML = '<span class="geo-v2-legend-item"><span class="geo-v2-legend-dot" style="background:#E8C77E"></span>Pasó su meta (en el hilo)</span><span class="geo-v2-legend-item"><span class="geo-v2-legend-dot" style="background:#C9B48F"></span>93 % o más (a punto)</span><span class="geo-v2-legend-item"><span class="geo-v2-legend-dot" style="background:#6F665D"></span>Por debajo</span>'; }
    if (!datos) {
      try {
        var periodo = (config.filtros && config.filtros.periodo) || '';
        var r = await fetch('/api/hilo/admin/red' + (periodo ? '?periodo=' + encodeURIComponent(periodo) : ''), { credentials: 'same-origin' });
        datos = await r.json();
      } catch (e) { datos = null; }
      if (!activo) return;
      if (!datos || !datos.ok) {
        // Sin acceso (usuario de tienda) o sin datos: el mapa vuelve a Cumplimiento y el botón se quita.
        datos = null; salir(); boton.remove();
        var otro = document.querySelector('#mapMetric button[data-m="cumplimiento"]');
        if (otro) otro.click();
        return;
      }
      document.dispatchEvent(new CustomEvent('hilo:datos', { detail: datos }));
      // La tienda virtual cuenta en el total y en las listas; en el mapa solo se dibujan las que tienen ubicación
      datos.tiendas.forEach(function (t) { t.virtual = esVirtual(t); t.ubicada = t.lat != null && t.lng != null; });
      prepararMarcadores();
      rango.max = datos.corte.dia || 1;
    }
    vistaAntes = { centro: mapa.getCenter(), zoom: mapa.getZoom() };
    var ubicadas = datos.tiendas.filter(function (t) { return t.ubicada; });
    if (ubicadas.length) mapa.fitBounds(L.latLngBounds(ubicadas.map(function (t) { return [t.lat, t.lng]; })), { paddingTopLeft: [30, 30], paddingBottomRight: [30, 90], maxZoom: 9 });
    posicionar();
    dia = datos.corte.dia || 1; rango.value = dia;
    dibujar(dia, false);
    mapa.on('zoomend', redibujar);
  }
  function salir() {
    if (!activo) return;
    activo = false; parar();
    contenedor.classList.remove('modo-red');
    if (grid) grid.classList.remove('modo-red');
    [capaCarrete, capaTiempo, globo].forEach(function (n) { n.hidden = true; });
    if (leyenda && leyendaAntes) leyenda.innerHTML = leyendaAntes;
    limpiar(); marcadores.forEach(function (m) { mapa.removeLayer(m.marcador); });
    mapa.off('zoomend', redibujar);
    if (vistaAntes) mapa.setView(vistaAntes.centro, vistaAntes.zoom);
  }
  function redibujar() { if (activo) { posicionar(); dibujar(dia, false); } }

  // Tiendas en la misma ciudad (misma coordenada) se separan un poco para que se vean todas
  var LADOS = ['', 'arriba', 'der', 'izq'];
  function prepararMarcadores() {
    var porPunto = {}, ubicadas = datos.tiendas.filter(function (t) { return t.ubicada; });
    ubicadas.forEach(function (t) { var k = (+t.lat).toFixed(3) + ',' + (+t.lng).toFixed(3); (porPunto[k] = porPunto[k] || []).push(t); });
    Object.keys(porPunto).forEach(function (k) {
      porPunto[k].forEach(function (t, i, lista) { t.grupo = lista.length; t.indice = i; t.lado = LADOS[i % 4]; });
    });
    marcadores = ubicadas.map(function (t) {
      var icono = L.divIcon({ className: '', html: '<div class="hr-tienda ' + t.lado + '" data-id="' + t.id + '"><b></b><span>' + esc(t.nombre) + '</span></div>', iconSize: [18, 18], iconAnchor: [9, 9] });
      var m = L.marker([t.lat, t.lng], { icon: icono, keyboard: false, zIndexOffset: 500 });
      m.bindTooltip(esc(t.nombre) + ' · ' + esc(t.ciudad || ''), { direction: 'top', offset: [0, -10] });
      return { t: t, marcador: m };
    });
    posicionar();
  }
  function posicionar() {
    marcadores.forEach(function (m) {
      var t = m.t, p = mapa.latLngToLayerPoint([t.lat, t.lng]);
      if (t.grupo > 1) { var a = 2 * Math.PI * t.indice / t.grupo - Math.PI / 2, r = 14 + t.grupo * 2; p = L.point(p.x + Math.cos(a) * r, p.y + Math.sin(a) * r); }
      t.punto = mapa.layerPointToLatLng(p);
      m.marcador.setLatLng(t.punto);
      if (!mapa.hasLayer(m.marcador)) m.marcador.addTo(mapa);
    });
  }

  // Cumplimiento y día de unión según los cortes que había en ese día
  function estadoEn(t, d) {
    var cump = null, union = null;
    for (var i = 0; i < t.serie.length; i++) {
      var c = t.serie[i][0], v = t.serie[i][1];
      if (c > d) break;
      cump = v; union = v >= 1 ? (union || c) : null;
    }
    return { cump: cump, union: union };
  }
  function curva(a, b, n) {
    var p0 = mapa.latLngToLayerPoint(a), p2 = mapa.latLngToLayerPoint(b);
    var dx = p2.x - p0.x, dy = p2.y - p0.y, largo = Math.hypot(dx, dy) || 1, k = Math.min(90, largo * .28);
    var p1 = L.point((p0.x + p2.x) / 2 - dy / largo * k, (p0.y + p2.y) / 2 + dx / largo * k), pts = [];
    for (var i = 0; i <= n; i++) {
      var s = i / n;
      pts.push(mapa.layerPointToLatLng(L.point((1 - s) * (1 - s) * p0.x + 2 * (1 - s) * s * p1.x + s * s * p2.x, (1 - s) * (1 - s) * p0.y + 2 * (1 - s) * s * p1.y + s * s * p2.y)));
    }
    return pts;
  }
  function limpiar() { capas.forEach(function (c) { mapa.removeLayer(c); }); capas = []; }

  function dibujar(d, animar) {
    if (!datos || !mapa) return;
    limpiar();
    datos.tiendas.forEach(function (t) { var e = estadoEn(t, d); t.hoy = e.cump; t.union = e.union; });
    var unidas = datos.tiendas.filter(function (t) { return t.union != null; }).sort(function (a, b) { return a.union - b.union || b.hoy - a.hoy; });
    // El hilo se dibuja entre las tiendas con ubicación (la virtual se une, pero no tiene punto en el mapa)
    var trazo = unidas.filter(function (t) { return t.punto; });
    for (var i = 1; i < trazo.length; i++) {
      var pts = curva(trazo[i - 1].punto, trazo[i].punto, 40);
      capas.push(L.polyline(pts, { className: 'hr-sombra', interactive: false }).addTo(mapa));
      var hilo = L.polyline(pts, { className: 'hr-hilo', interactive: false }).addTo(mapa);
      capas.push(hilo);
      if (animar && i === trazo.length - 1 && trazo[i] === unidas[unidas.length - 1] && unidas.length > unidasAntes && !quieto) {
        var elem = hilo.getElement(), largo = elem.getTotalLength();
        elem.style.strokeDasharray = largo; elem.style.strokeDashoffset = largo; elem.getBoundingClientRect();
        elem.style.transition = 'stroke-dashoffset 1.3s cubic-bezier(.45,.05,.55,.95)'; elem.style.strokeDashoffset = 0;
      }
    }
    var cerca = datos.tiendas.filter(function (t) { return t.union == null && t.hoy != null && t.hoy >= .93; }).sort(function (a, b) { return b.hoy - a.hoy; });
    var ultima = unidas[unidas.length - 1], ultimaTrazo = trazo[trazo.length - 1];
    if (ultimaTrazo) cerca.slice(0, 3).forEach(function (t) { if (t.punto) capas.push(L.polyline(curva(ultimaTrazo.punto, t.punto, 30), { className: 'hr-futuro', interactive: false }).addTo(mapa)); });
    marcadores.forEach(function (m) {
      var n = m.marcador.getElement() && m.marcador.getElement().querySelector('.hr-tienda');
      if (!n) return;
      n.classList.toggle('unida', m.t.union != null);
      n.classList.toggle('cerca', cerca.slice(0, 3).indexOf(m.t) >= 0);
      m.marcador.setTooltipContent(esc(m.t.nombre) + ' · ' + esc(m.t.ciudad || '') + (m.t.hoy != null ? ' · ' + pct(m.t.hoy) : ' · sin corte aún'));
    });
    pintarPanel(unidas, cerca, d, animar);
    if (animar && ultima && unidas.length > unidasAntes) {
      if (ultima.punto) {
        var p = mapa.latLngToContainerPoint(ultima.punto), ch = el('div', 'hr-chispa');
        ch.style.left = p.x + 'px'; ch.style.top = p.y + 'px';
        contenedor.appendChild(ch); setTimeout(function () { ch.remove(); }, 1200);
      }
      decir(unidas.length === 1 ? '¡' + ultima.nombre + ' pasó su meta y empezó el hilo dorado! ✨' : '¡' + ultima.nombre + ' se unió al hilo! Ya van ' + unidas.length + ' tiendas 🧵');
    }
    unidasAntes = unidas.length;
    salida.textContent = 'Día ' + d;
    document.dispatchEvent(new CustomEvent('hilo:dia', { detail: { dia: d, unidas: unidas.length, fin: +rango.max } }));
  }
  function pintarPanel(unidas, cerca, d, animar) {
    var total = datos.tiendas.length, pc = total ? Math.round(unidas.length / total * 100) : 0;
    panel.querySelector('.hr-pct').innerHTML = pc + '% <small>de las tiendas</small>';
    panel.querySelector('.hr-barra span').style.width = pc + '%';
    capaCarrete.querySelector('.hr-cuenta').textContent = unidas.length + ' de ' + total + ' tiendas';
    var h = 4 + 26 * (total ? unidas.length / total : 0), r = capaCarrete.querySelector('.hr-hilo-rect');
    r.setAttribute('height', h); r.setAttribute('y', 42 - h);
    var ciudades = unidas.map(lugarTxt).filter(function (c, i, a) { return c && a.indexOf(c) === i; });
    panel.querySelector('.hr-frase').textContent = !unidas.length ? 'Todavía ninguna tienda pasó su meta al corte.' : 'El hilo une ' + ciudades.length + (ciudades.length === 1 ? ' ciudad: ' : ' ciudades: ') + ciudades.join(', ') + '.';
    panel.querySelector('.hr-unidas').innerHTML = unidas.length ? unidas.map(function (t, i) {
      return '<li class="' + (animar && i === unidas.length - 1 && unidas.length > unidasAntes ? 'nuevo' : '') + '"><span class="hr-n">' + (i + 1) + '</span><span><b>' + esc(t.nombre) + '</b><br><small style="color:#6B6259">' + esc(lugarTxt(t)) + ' · ' + pct(t.hoy) + '</small></span><span class="hr-der">corte ' + t.union + '</span></li>';
    }).join('') : '<li class="hr-nota">Nadie todavía.</li>';
    panel.querySelector('.hr-cerca').innerHTML = cerca.length ? cerca.slice(0, 5).map(function (t) {
      return '<li><span class="hr-n" style="background:#C9B48F">·</span><span><b>' + esc(t.nombre) + '</b><br><small style="color:#6B6259">' + esc(lugarTxt(t)) + '</small></span><span class="hr-der"><b style="color:#2D2A26">' + pct(t.hoy) + '</b></span></li>';
    }).join('') : '<li class="hr-nota">Ninguna está cerca del 100 % en este momento.</li>';
  }
  function decir(texto) {
    globo.textContent = texto; globo.classList.add('visible');
    clearTimeout(globoT); globoT = setTimeout(function () { globo.classList.remove('visible'); }, 2600);
  }

  rango.addEventListener('input', function () { parar(); dia = +rango.value; unidasAntes = 0; dibujar(dia, false); });
  function parar() { clearInterval(corriendo); corriendo = 0; play.innerHTML = '<i class="bi bi-play-fill"></i>'; play.setAttribute('aria-label', 'Reproducir el mes'); }
  play.addEventListener('click', function () {
    if (!datos) return;
    if (corriendo) { parar(); return; }
    var fin = +rango.max;
    dia = +rango.value >= fin ? 1 : +rango.value;
    unidasAntes = 0; rango.value = dia; dibujar(dia, true);
    play.innerHTML = '<i class="bi bi-pause-fill"></i>'; play.setAttribute('aria-label', 'Pausar');
    corriendo = setInterval(function () {
      dia++; rango.value = dia; dibujar(dia, true);
      if (dia >= fin) {
        parar();
        var u = datos.tiendas.filter(function (t) { return t.union != null; }).length;
        setTimeout(function () { decir('Corte del día ' + fin + ': ' + u + ' de ' + datos.tiendas.length + ' tiendas en el hilo.'); }, 1400);
      }
    }, quieto ? 350 : 800);
  });

  // Para mapa_plus.js (modo oficina): reproducir el mes desde afuera
  window.__hiloRed = { reproducir: function () { if (!corriendo) play.click(); }, activo: function () { return activo; }, datos: function () { return datos; } };

  // Misma regla de «Mapa y resultados»: código S-03 o ciudad GLOBAL
  function esVirtual(t) { return String(t.codigo || '').replace(/\s/g, '').toUpperCase() === 'S-03' || String(t.ciudad || '').trim().toUpperCase() === 'GLOBAL'; }
  function lugarTxt(t) { return t.virtual ? '🌐 canal virtual' : (t.ciudad || ''); }

  function el(tag, clase, html) { var n = document.createElement(tag); n.className = clase; if (html) n.innerHTML = html; return n; }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pct(v) { return v == null ? '—' : (v * 100).toFixed(1).replace('.', ',') + '%'; }
})();
