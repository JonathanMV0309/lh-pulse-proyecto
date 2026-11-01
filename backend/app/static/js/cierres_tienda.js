/* ================================================================
   Configuración › Cierres de tienda (solo el administrador principal)
   Para marcar a mano que una tienda estuvo cerrada (remodelación, apertura):
   su cuota total y su cuota al corte cuentan solo los días que vendió.
   Se ajusta al guardar, a todos los cortes cargados de ese mes, y en cada
   carga del Excel. Es lo mismo que «Cierre de tienda» en Novedades.
   ================================================================ */
(function () {
  'use strict';
  if (!/^\/configuracion\/?$/.test(location.pathname)) return;
  var fila = document.querySelector('.row.g-4');
  if (!fila) return;

  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fecha(s) { var p = String(s).split('-'); return +p[2] + '/' + +p[1] + '/' + p[0]; }

  fetch('/novedades/api/cierres', { credentials: 'same-origin' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && d.ok) montar(d); })
    .catch(function () { /* sin permiso: no se muestra */ });

  function montar(d) {
    var css = document.createElement('style');
    css.textContent =
      '.ct-form{display:grid;grid-template-columns:minmax(0,2fr) repeat(2,minmax(0,1fr)) auto;gap:10px;align-items:end;margin:14px 0}' +
      '.ct-form label{display:grid;gap:4px;font:700 11px Inter,sans-serif;letter-spacing:.05em;text-transform:uppercase;color:#6B6259}' +
      '.ct-form select,.ct-form input{width:100%;padding:9px 10px;border-radius:10px;border:1px solid rgba(139,125,107,.3);background:#fff;font:14px Inter,sans-serif;color:#2D2A26;text-transform:none;letter-spacing:0}' +
      '.ct-form .ancho{grid-column:1/-2}' +
      '.ct-btn{padding:10px 16px;border-radius:10px;border:0;background:#2D2A26;color:#fff;font:700 14px Inter,sans-serif;cursor:pointer;white-space:nowrap}' +
      '.ct-btn:hover{background:#45403a}.ct-btn:active{transform:scale(.97)}.ct-btn.sec{background:#fff;color:#2D2A26;border:1px solid rgba(139,125,107,.3)}' +
      '.ct-btn:focus-visible,.ct-form select:focus-visible,.ct-form input:focus-visible,.ct-acc button:focus-visible{outline:2px solid #A8865A;outline-offset:2px}' +
      '.ct-error{min-height:18px;margin:0;color:#9F1D1D;font-size:13px;font-weight:600}.ct-error.ok{color:#1F5E3F}' +
      '.ct-lista{width:100%;border-collapse:collapse;font-size:14px}' +
      '.ct-lista th{padding:8px 10px;text-align:left;color:#6B6259;font:700 11px Inter,sans-serif;letter-spacing:.05em;text-transform:uppercase;border-bottom:1px solid rgba(139,125,107,.25)}' +
      '.ct-lista td{padding:10px;border-bottom:1px solid rgba(139,125,107,.15);vertical-align:top}' +
      '.ct-lista td small{display:block;color:#6B6259}' +
      '.ct-acc{white-space:nowrap;text-align:right}.ct-acc button{border:0;background:transparent;color:#6B6259;padding:4px 8px;border-radius:8px;cursor:pointer}.ct-acc button:hover{background:#F5F0E8;color:#2D2A26}' +
      '.ct-vacio{padding:14px 0;color:#6B6259}' +
      '@media (max-width:760px){.ct-form{grid-template-columns:1fr 1fr}.ct-form label:first-child,.ct-form .ancho{grid-column:1/-1}}';
    document.head.appendChild(css);

    var col = document.createElement('div');
    col.className = 'col-12';
    col.innerHTML =
      '<div class="glass-panel settings-card" id="cierresTienda">' +
        '<div class="settings-icon"><i class="bi bi-cone-striped"></i></div>' +
        '<span class="page-kicker">CUOTAS</span>' +
        '<h3>Cierres de tienda</h3>' +
        '<p class="text-muted mb-0">Si una tienda estuvo cerrada parte del mes (remodelación o apertura), márcala aquí: su cuota total y su cuota al corte van a contar solo los días que vendió. Se ajusta sola en los cortes ya cargados y en cada carga del Excel, sin importar lo que traiga la hoja CUMPL.</p>' +
        '<form class="ct-form" novalidate>' +
          '<input type="hidden" name="id">' +
          '<label>Tienda<select name="store_id" required><option value="">Elige…</option>' +
            d.tiendas.map(function (t) { return '<option value="' + t.id + '">' + esc(t.codigo + ' · ' + t.nombre) + '</option>'; }).join('') + '</select></label>' +
          '<label>Primer día cerrada<input type="date" name="desde" required></label>' +
          '<label>Último día cerrada<input type="date" name="hasta" required></label>' +
          '<div style="display:flex;gap:6px"><button type="submit" class="ct-btn">Guardar</button><button type="button" class="ct-btn sec" data-ct="limpiar" hidden>Cancelar</button></div>' +
          '<label class="ancho">Motivo (opcional)<input name="observacion" maxlength="300" placeholder="Remodelación, apertura…"></label>' +
        '</form>' +
        '<p class="ct-error" aria-live="polite"></p>' +
        '<div class="table-responsive"><table class="ct-lista"><thead><tr><th>Tienda</th><th>Cerrada</th><th>Días</th><th>Motivo</th><th></th></tr></thead><tbody></tbody></table></div>' +
      '</div>';
    fila.appendChild(col);

    var form = col.querySelector('form'), error = col.querySelector('.ct-error'), cierres = d.cierres;
    function pintar() {
      col.querySelector('tbody').innerHTML = cierres.length ? cierres.map(function (c) {
        return '<tr><td><b>' + esc(c.tienda) + '</b><small>Marcado por ' + esc(c.creado_por) + '</small></td>' +
          '<td>Del ' + fecha(c.desde) + ' al ' + fecha(c.hasta) + '</td><td>' + c.dias + '</td><td>' + esc(c.observacion) + '</td>' +
          '<td class="ct-acc"><button type="button" data-ed="' + c.id + '" aria-label="Cambiar"><i class="bi bi-pencil"></i></button>' +
          '<button type="button" data-bo="' + c.id + '" aria-label="Quitar"><i class="bi bi-trash"></i></button></td></tr>';
      }).join('') : '<tr><td colspan="5" class="ct-vacio">No hay cierres marcados.</td></tr>';
    }
    function recargar() {
      return fetch('/novedades/api/cierres', { credentials: 'same-origin' }).then(function (r) { return r.json(); })
        .then(function (x) { cierres = x.cierres || []; pintar(); });
    }
    function aviso(texto, bien) { error.textContent = texto; error.classList.toggle('ok', !!bien); }
    function limpiar() { form.reset(); form.id.value = ''; col.querySelector('[data-ct="limpiar"]').hidden = true; aviso(''); }
    form.desde.addEventListener('change', function () { if (!form.hasta.value || form.hasta.value < form.desde.value) form.hasta.value = form.desde.value; });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!form.store_id.value || !form.desde.value || !form.hasta.value) { error.textContent = 'Elige la tienda y los días que estuvo cerrada.'; return; }
      aviso('Guardando y ajustando la cuota…', true);
      fetch('/novedades/api/cierres', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: form.id.value || null, store_id: form.store_id.value, desde: form.desde.value, hasta: form.hasta.value, observacion: form.observacion.value }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j.ok) { error.textContent = j.error || 'No se pudo guardar.'; return; }
          limpiar(); aviso('Guardado: la cuota de la tienda ya cuenta solo los días que vendió.', true); recargar();
        }).catch(function () { error.textContent = 'No se pudo guardar.'; });
    });
    col.addEventListener('click', function (e) {
      var ed = e.target.closest('[data-ed]'), bo = e.target.closest('[data-bo]'), li = e.target.closest('[data-ct="limpiar"]');
      if (li) { limpiar(); return; }
      if (ed) {
        var c = cierres.filter(function (x) { return String(x.id) === ed.dataset.ed; })[0];
        if (!c) return;
        form.id.value = c.id; form.store_id.value = c.store_id; form.desde.value = c.desde; form.hasta.value = c.hasta; form.observacion.value = c.observacion;
        col.querySelector('[data-ct="limpiar"]').hidden = false; error.textContent = ''; form.store_id.focus();
      }
      if (bo) {
        var cb = cierres.filter(function (x) { return String(x.id) === bo.dataset.bo; })[0];
        if (!cb || !confirm('¿Quitar el cierre de ' + cb.tienda + '? Su cuota vuelve a ser la del mes completo.')) return;
        fetch('/novedades/api/cierres/' + cb.id, { method: 'DELETE', credentials: 'same-origin' })
          .then(function () { aviso('Cierre quitado: la cuota volvió a la del mes completo.', true); recargar(); });
      }
    });
    pintar();
  }
})();
