/* ================================================================
   Dashboard de tienda más limpio y más claro
   - Quita las tarjetas «Ventas del mes» y «Cumplimiento de meta» de arriba:
     ya están en «Cumplimiento de meta» y «Evolución de ventas».
   - Quita «Etiquetas del día» y «El pulso de la tienda» (repiten datos).
   - Quita la gráfica de «Evolución diaria de conversión» (la tabla se queda).
   - En «Metas por línea», aunque vaya cumpliendo al corte, dice cuánto le
     falta en pesos para la meta del mes.
   - Mensaje final: «¡Excelente trabajo!» solo con la meta del mes; si va
     cumpliendo al corte, dice por cuánto supera y cuánto falta para el mes.
   - VPT: cuánto deja de vender la tienda (y cada asesora) por estar debajo de
     la meta de VPT, y a qué % llegaría la tienda con esa venta.
   - «Metas y vendedores»: «Auxiliar» se muestra como «Apoyo».
   Solo cambia lo que se ve: no toca datos ni cálculos.
   ================================================================ */
(function () {
  'use strict';
  // «Metas y vendedores»: las asesoras auxiliares se llaman «Apoyo» (solo el texto; el tipo guardado no cambia)
  if (document.querySelector('.type-select')) {
    var apoyo = function (raiz) {
      var w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
      var n;
      while ((n = w.nextNode())) {
        if (/\bAuxiliar(es)?\b/.test(n.nodeValue)) {
          n.nodeValue = n.nodeValue.replace(/\bVenta auxiliares\b/g, 'Venta de apoyo').replace(/\bAuxiliares\b/g, 'Apoyo').replace(/\bAuxiliar\b/g, 'Apoyo');
        }
      }
    };
    var correr = function () { apoyo(document.querySelector('.main-content, main') || document.body); };
    correr();
    document.addEventListener('DOMContentLoaded', correr);
    if (window.MutationObserver) new MutationObserver(function (m) { m.forEach(function (x) { apoyo(x.target.parentNode || x.target); }); })
      .observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  var datosNodo = document.getElementById('tpDatos');
  if (!datosNodo) return;                       // solo en el dashboard de tienda
  var D = {};
  try { D = JSON.parse(datosNodo.textContent) || {}; } catch (e) { D = {}; }

  var PESOS = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  function texto(n) { return (n && n.textContent || '').replace(/\s+/g, ' ').trim().toUpperCase(); }
  function quitar(n) { if (n && n.parentNode) n.parentNode.removeChild(n); }

  // 1. Tarjetas repetidas de arriba
  function tarjetas() {
    var quitadas = 0, fila = null;
    document.querySelectorAll('.kpi-card .kpi-title').forEach(function (t) {
      var nombre = texto(t);
      if (nombre !== 'VENTAS DEL MES' && nombre !== 'CUMPLIMIENTO DE META') return;
      var col = t.closest('[class*="col-"]');
      if (!col) return;
      fila = col.parentNode;
      quitar(col);
      quitadas++;
    });
    if (quitadas && fila) {   // las que quedan ocupan el espacio
      Array.prototype.forEach.call(fila.children, function (c) { c.className = c.className.replace(/\bcol-xl-3\b/, 'col-xl-6'); });
    }
  }

  // 2 y 3. Bloques animados que repiten información
  function bloques() {
    document.querySelectorAll('.tp-block').forEach(function (b) {
      var k = texto(b.querySelector('.tp-kicker'));
      if (k !== 'ETIQUETAS DEL DÍA' && k !== 'EL PULSO DE LA TIENDA' && !b.classList.contains('tp-pulse')) return;
      var grid = b.parentNode;
      quitar(b);
      if (grid && grid.classList && grid.classList.contains('tp-grid-2') && grid.children.length === 1) {
        grid.style.gridTemplateColumns = 'minmax(0, 1fr)';
      }
    });
  }

  // 4. Gráfica de conversión diaria (la tabla de abajo se queda)
  function grafica() {
    var c = document.getElementById('conversionDiariaChart');
    if (c && c.parentNode && !c.parentNode.hidden) c.parentNode.hidden = true;
  }

  // 5. Metas por línea: cuánto falta en pesos para la meta del mes
  function lineas() {
    var porNombre = {};
    (D.lineas || []).forEach(function (l) { porNombre[String(l.linea || '').trim().toUpperCase()] = l; });
    document.querySelectorAll('.line-title').forEach(function (t) {
      var l = porNombre[texto(t)];
      var card = t.parentNode;
      while (card && card !== document.body && !card.querySelector('.progress')) card = card.parentNode;
      if (!l || !card || card === document.body || card.querySelector('.tl-falta')) return;
      var ok = Array.prototype.find.call(card.querySelectorAll('.text-success'), function (n) { return /Meta al corte alcanzada/i.test(n.textContent); });
      if (!ok) return;    // si no va cumpliendo, la tarjeta ya dice «Faltan $…»
      var falta = (parseFloat(l.meta) || 0) - (parseFloat(l.venta) || 0);
      var extra = document.createElement('span');
      extra.className = 'tl-falta d-block mt-1';
      extra.style.cssText = 'color:#6b6259;font-weight:600;';
      extra.innerHTML = falta > 0
        ? 'Faltan <strong style="color:#2d2a26">$' + PESOS.format(Math.round(falta)) + '</strong> para la meta del mes'
        : '<strong style="color:#2d6a4f">¡Meta del mes lograda!</strong>';
      ok.parentNode.insertBefore(extra, ok.nextSibling);
    });
  }

  // Datos de la tienda para los mensajes
  var ventas = parseFloat(D.ventas) || 0, cumpCorte = parseFloat(D.cumplimiento) || 0;
  var cuotaTotal = ventas + (parseFloat(D.falta) || 0);          // falta = cuota total − venta
  var cuotaCorte = cumpCorte > 0 ? ventas / cumpCorte : 0;
  function pesos(v) { return '$' + PESOS.format(Math.round(v)); }
  function metaVPT() {
    var l = Array.prototype.find.call(document.querySelectorAll('.meta-label'), function (n) { return /Meta m[ií]nima VPT/i.test(n.textContent); });
    var num = l && l.parentNode.querySelector('.meta-number');
    var v = num ? parseFloat(num.textContent.replace(/[^\d]/g, '')) : 0;
    return v > 0 ? v : 0;
  }

  // 6. Mensaje final: «¡Excelente trabajo!» solo con la meta del MES; si va cumpliendo al corte, por cuánto supera
  function motivacion() {
    var caja = document.querySelector('.motivation');
    if (!caja || caja.dataset.tl || !(cuotaTotal > 0)) return;
    caja.dataset.tl = '1';
    var h = caja.querySelector('h4'), p = caja.querySelector('p');
    if (!h || !p) return;
    var total = ventas / cuotaTotal, tienda = D.tienda || 'equipo';
    if (total >= 1) {
      h.textContent = '🏆 ¡Excelente trabajo, ' + tienda + '!';
      p.textContent = 'La tienda ya alcanzó su meta del mes. Ahora el objetivo es mantener el liderazgo y seguir creciendo.';
    } else if (cumpCorte >= 1) {
      h.textContent = '✅ ¡Van cumpliendo al día, ' + tienda + '!';
      p.innerHTML = 'Superan la cuota al corte por <strong>' + pesos(ventas - cuotaCorte) + '</strong> (van al ' +
        (cumpCorte * 100).toFixed(1) + '%). Para la meta del mes faltan <strong>' + pesos(cuotaTotal - ventas) + '</strong>. ¡A sostener el ritmo!';
    }
  }

  // 7. Tarjeta del VPT: cuánto deja de vender la tienda por no tener el VPT en la meta
  function vptTienda() {
    var meta = metaVPT(), ticket = parseFloat(D.ticket) || 0, facturas = parseFloat(D.facturas) || 0;
    if (!meta || !ticket || !facturas || ticket >= meta || document.querySelector('.tl-vpt')) return;
    var l = Array.prototype.find.call(document.querySelectorAll('.meta-label'), function (n) { return /Cumplimiento meta VPT/i.test(n.textContent); });
    if (!l) return;
    var perdida = (meta - ticket) * facturas;
    var nota = document.createElement('small');
    nota.className = 'tl-vpt d-block mt-2';
    nota.style.cssText = 'color:#9f1d1d;font-weight:600;line-height:1.4;';
    nota.innerHTML = 'Están dejando de vender <strong>' + pesos(perdida) + '</strong> (' + pesos(meta - ticket) + ' × ' + PESOS.format(facturas) + ' facturas).' +
      (cuotaCorte > 0 ? ' Con esa venta la tienda iría al <strong>' + ((ventas + perdida) / cuotaCorte * 100).toFixed(1) + '%</strong>. ¡A subir el VPT!' : '');
    l.parentNode.appendChild(nota);
  }

  // 8. Ranking de asesoras de la tienda: meta del VPT y lo que deja de vender cada una
  function vptAsesoras() {
    var meta = metaVPT();
    var filas = document.querySelectorAll('tr[data-ta-asesora]');
    if (!meta || !filas.length) return;
    var tabla = filas[0].closest('table'), ths = tabla ? tabla.querySelectorAll('thead th') : [];
    var iTicket = -1, iFact = -1;
    Array.prototype.forEach.call(ths, function (th, i) {
      var t = texto(th);
      if (t.indexOf('TICKET') === 0) iTicket = i;
      if (t.indexOf('FACTURAS') === 0) iFact = i;
    });
    if (iTicket < 0 || iFact < 0) return;
    filas.forEach(function (tr) {
      var celda = tr.children[iTicket], fact = parseFloat((tr.children[iFact] || {}).textContent.replace(/[^\d]/g, '')) || 0;
      var ticket = parseFloat(tr.dataset.ticket) || 0;
      if (!celda || celda.querySelector('.tl-vpta') || !ticket || tr.dataset.generico === '1') return;
      var s = document.createElement('small');
      s.className = 'tl-vpta d-block';
      s.style.cssText = 'font-size:11px;line-height:1.3;font-weight:600;white-space:nowrap;';
      s.innerHTML = ticket >= meta
        ? '<span style="color:#2d6a4f">✓ Meta VPT ' + pesos(meta) + '</span>'
        : '<span style="color:#6b6259">Meta VPT ' + pesos(meta) + '</span><br><span style="color:#9f1d1d">Deja de vender ' + pesos((meta - ticket) * fact) + '</span>';
      celda.appendChild(s);
    });
  }

  // 9. Histórico de la tienda (hoja ACUM): sus meses de los dos últimos años y la red, sin otra pestaña
  function historico() {
    if (document.querySelector('.tl-hist')) return;
    var titulo = Array.prototype.find.call(document.querySelectorAll('.section-header h4, h4'), function (h) { return /Cumplimiento de meta/i.test(h.textContent); });
    var ancla = titulo ? titulo.closest('.row') : document.querySelector('.motivation');
    if (!ancla) return;
    var caja = document.createElement('section');
    caja.className = 'tl-hist';
    caja.hidden = true;
    ancla.parentNode.insertBefore(caja, titulo ? ancla.nextSibling : ancla);
    var m = location.pathname.match(/\/dashboard\/tienda\/(\d+)/);
    fetch('/historico/api/tienda' + (m ? '?store_id=' + m[1] : ''), { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (H) { if (H && H.ok) pintarHistorico(caja, H, !!m); })
      .catch(function () { /* sin histórico: no se muestra nada */ });
  }

  function pintarHistorico(caja, H, admin) {
    var MES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    var anios = H.anios.slice(-2), ultimo = anios[anios.length - 1], tipo = 'cumplimiento';
    if (!document.getElementById('tlHistCss')) {
      var css = document.createElement('style');
      css.id = 'tlHistCss';
      css.textContent =
        '.tl-hist{margin:0 0 24px;padding:18px 20px;border-radius:18px;background:#FDFBF7;border:1px solid rgba(139,125,107,.22);color:#2D2A26}' +
        '.tl-hist-cab{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:12px}' +
        '.tl-hist-cab h4{margin:0;font:800 18px Inter,sans-serif;display:flex;gap:8px;align-items:center}.tl-hist-cab h4 i{color:#A8865A}' +
        '.tl-hist-cab p{margin:2px 0 0;color:#6B6259;font-size:13px}' +
        '.tl-hist-seg{display:inline-flex;padding:3px;border-radius:11px;background:#F5F0E8;border:1px solid rgba(139,125,107,.22)}' +
        '.tl-hist-seg button{border:0;padding:6px 12px;border-radius:8px;background:transparent;color:#6B6259;font:700 12.5px Inter,sans-serif;cursor:pointer}' +
        '.tl-hist-seg button[aria-pressed="true"]{background:#fff;color:#2D2A26;box-shadow:0 1px 3px rgba(45,42,38,.12)}' +
        '.tl-hist-seg button:focus-visible{outline:2px solid #A8865A;outline-offset:2px}' +
        '.tl-hist-caja{overflow-x:auto}' +
        '.tl-hist table{border-collapse:separate;border-spacing:4px;min-width:100%;font-size:13px}' +
        '.tl-hist th{color:#6B6259;font:700 11px Inter,sans-serif;letter-spacing:.04em;text-transform:uppercase;text-align:center;padding:0 2px}' +
        '.tl-hist th.n,.tl-hist td.n{text-align:left;white-space:nowrap;padding-right:8px}' +
        '.tl-hist td{text-align:center;padding:7px 4px;border-radius:8px;font-weight:600;font-variant-numeric:tabular-nums;min-width:48px;background:#F7F3EC}' +
        '.tl-hist td.n{background:none;font-weight:800}.tl-hist tr.red td.n{color:#6B6259;font-weight:600}' +
        '.tl-hist td.vacio{color:#BDB3A6;font-weight:400;background:none}' +
        '.tl-hist td.c-top{background:#B9E0C9;color:#1F5E3F;font-weight:800}.tl-hist td.c-ok{background:#D9EFE2;color:#1F5E3F}' +
        '.tl-hist td.c-cerca{background:#FBF0D6;color:#7A5A12}.tl-hist td.c-bajo{color:#9F1D1D}' +
        '.tl-hist td.p{border-left:2px solid #fff;font-weight:800}' +
        '.tl-hist tr.red td:not(.n){background:none;color:#6B6259;font-weight:600}' +
        '.tl-hist-pie{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;margin-top:8px;color:#6B6259;font-size:12px}' +
        '.tl-hist-pie a{color:#7A5A2E;font-weight:700;text-decoration:none}.tl-hist-pie a:hover{text-decoration:underline}';
      document.head.appendChild(css);
    }
    function serie(f, a) {
      var s = (f && f[tipo] && f[tipo][a]) || [];
      return tipo === 'cumplimiento' ? s.map(function (v) { return v === 0 ? null : v; }) : s;
    }
    function prom(s) { var v = s.filter(function (x) { return x != null; }); return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : null; }
    function clase(v) {
      if (v == null) return 'vacio';
      if (tipo === 'cumplimiento') return v >= 1.1 ? 'c-top' : v >= 1 ? 'c-ok' : v >= 0.9 ? 'c-cerca' : 'c-bajo';
      return v >= 0.1 ? 'c-top' : v >= 0 ? 'c-ok' : v >= -0.05 ? 'c-cerca' : 'c-bajo';
    }
    function txt(v) { if (v == null) return '—'; var p = Math.round(v * 100); return (tipo === 'incremento' && p > 0 ? '+' : '') + p + '%'; }
    function fila(nombre, s, clases) {
      var p = prom(s);
      return '<tr class="' + (clases || '') + '"><td class="n">' + nombre + '</td>' +
        MES.map(function (x, i) { return '<td class="' + clase(s[i]) + '">' + txt(s[i]) + '</td>'; }).join('') +
        '<td class="p ' + clase(p) + '" title="Promedio de los meses con dato">' + txt(p) + '</td></tr>';
    }
    function pintar() {
      var cuerpo = anios.map(function (a) { return fila(a, serie(H.fila, a)); }).join('') +
        (H.total ? fila('Red ' + ultimo, serie(H.total, ultimo), 'red') : '');
      caja.querySelector('tbody').innerHTML = cuerpo;
      caja.querySelector('.tl-hist-cab p').textContent = tipo === 'cumplimiento'
        ? 'Cuánto de la cuota se cumplió cada mes · ' + anios.join(' y ')
        : 'Cuánto creció la venta frente al mismo mes del año anterior · ' + anios.join(' y ');
      caja.querySelectorAll('.tl-hist-seg button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.t === tipo)); });
    }
    caja.innerHTML =
      '<div class="tl-hist-cab"><div><h4><i class="bi bi-table" aria-hidden="true"></i>Histórico de la tienda</h4><p></p></div>' +
      '<div class="tl-hist-seg" role="group" aria-label="Qué ver"><button type="button" data-t="cumplimiento">Cumplimiento</button><button type="button" data-t="incremento">Incremento</button></div></div>' +
      '<div class="tl-hist-caja"><table><thead><tr><th class="n">Año</th>' + MES.map(function (x) { return '<th>' + x + '</th>'; }).join('') +
      '<th>Prom.</th></tr></thead><tbody></tbody></table></div>' +
      '<div class="tl-hist-pie"><span>Verde: cumplió la cuota (o creció) · ámbar: cerca · número rojo: por debajo. Fuente: hoja ACUM de «' + String(H.archivo || '').replace(/[<>&"]/g, '') + '».</span>' +
      (admin ? '<a href="/historico/">Ver todas las tiendas →</a>' : '') + '</div>';
    caja.querySelectorAll('.tl-hist-seg button').forEach(function (b) { b.addEventListener('click', function () { tipo = b.dataset.t; pintar(); }); });
    pintar();
    caja.hidden = false;
  }

  function limpiar() {
    try { historico(); } catch (e) { /* sigue con lo demás */ }
    try { motivacion(); } catch (e) { /* sigue con lo demás */ }
    try { vptTienda(); } catch (e) { /* sigue con lo demás */ }
    try { vptAsesoras(); } catch (e) { /* sigue con lo demás */ }
    try { tarjetas(); } catch (e) { /* sigue con lo demás */ }
    try { bloques(); } catch (e) { /* sigue con lo demás */ }
    try { grafica(); } catch (e) { /* sigue con lo demás */ }
    try { lineas(); } catch (e) { /* sigue con lo demás */ }
  }

  limpiar();
  // Los efectos de la tienda se arman al terminar de cargar: se revisa otra vez cuando aparecen
  document.addEventListener('DOMContentLoaded', function () { setTimeout(limpiar, 0); });
  window.addEventListener('load', limpiar);
  if (window.MutationObserver) {
    var obs = new MutationObserver(function () { bloques(); });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(function () { obs.disconnect(); }, 15000);
  }
})();
