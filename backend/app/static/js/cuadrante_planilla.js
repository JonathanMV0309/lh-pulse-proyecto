/* ================================================================
   Planilla de horas (formato GTH-ODSCTD-003 de Talento Humano)
   - En «Horarios del equipo»: pestaña nueva junto a los turnos de arrastrar
   - En /planilla (administración): la planilla de la tienda elegida
   Por persona y día: entrada, salida, «Almorzó» y horas trabajadas (salida − entrada − 1 h si almorzó),
   novedad (descanso, vacaciones, permiso, incapacidad…), total de la semana y observaciones.
   Si un día no tiene horas, se sugieren con el turno arrastrado y el horario de la tienda.
   La planilla es la principal: al guardarla se llenan solos los «Turnos de la semana».
   ================================================================ */
(function () {
  'use strict';
  var raizAdmin = document.getElementById('planillaRaiz');
  var paginaTurnos = document.querySelector('.cuadrante-page');
  if (!raizAdmin && !paginaTurnos) return;

  var css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = '/static/css/cuadrante_planilla.css?v=4';
  document.head.appendChild(css);

  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var NOV = { TRABAJA: 'Trabaja', DESCANSO: 'Descanso', VACACIONES: 'Vacaciones', PERMISO: 'Permiso', INCAPACIDAD: 'Incapacidad', CALAMIDAD: 'Calamidad', LICENCIA: 'Licencia' };
  var storeId = raizAdmin ? raizAdmin.dataset.store : '';
  var domingo = null, datos = null, cambios = false, turnosViejos = false;

  function el(tag, clase, html) { var n = document.createElement(tag); if (clase) n.className = clase; if (html != null) n.innerHTML = html; return n; }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function iso(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function fecha(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function minutos(h) { if (!h) return null; var p = h.split(':'); return +p[0] * 60 + +p[1]; }
  function horas(e, s, almuerzo) { var a = minutos(e), b = minutos(s); if (a == null || b == null || b <= a) return 0; return Math.max(Math.round(((b - a) / 60 - (almuerzo === false ? 0 : 1)) * 100) / 100, 0); }
  function num(v) { return (Math.round(v * 100) / 100).toString().replace('.', ','); }
  function q(extra) { var p = new URLSearchParams(extra || {}); if (storeId) p.set('store_id', storeId); return p.toString(); }

  /* ---------------- Estructura ---------------- */
  var raiz = el('section', 'pl-planilla');
  raiz.setAttribute('aria-label', 'Planilla de horas');
  raiz.innerHTML =
    '<div class="pl-barra">' +
      '<div class="pl-semana"><button type="button" class="pl-btn icono" data-pl="anterior" aria-label="Semana anterior"><i class="bi bi-chevron-left"></i></button>' +
      '<div><span class="pl-kicker">Planilla de horas · formato Talento Humano</span><h2 class="pl-titulo">Semana</h2></div>' +
      '<button type="button" class="pl-btn icono" data-pl="siguiente" aria-label="Semana siguiente"><i class="bi bi-chevron-right"></i></button>' +
      '<button type="button" class="pl-btn" data-pl="hoy">Esta semana</button></div>' +
      '<div class="pl-acciones"><span class="pl-estado" aria-live="polite"></span>' +
      '<button type="button" class="pl-btn" data-pl="persona" hidden><i class="bi bi-person-plus"></i> Agregar persona</button>' +
      '<button type="button" class="pl-btn" data-pl="copiar"><i class="bi bi-copy"></i> Copiar semana anterior</button>' +
      '<button type="button" class="pl-btn" data-pl="excel"><i class="bi bi-file-earmark-excel"></i> Descargar Excel del mes</button>' +
      '<button type="button" class="pl-btn primario" data-pl="guardar"><i class="bi bi-check2"></i> Guardar planilla</button></div>' +
    '</div>' +
    '<div class="pl-horario"></div>' +
    '<div class="pl-tabla-caja"><table class="pl-tabla"><thead></thead><tbody></tbody></table></div>' +
    '<div class="pl-pie"><div class="pl-alertas"></div><div class="pl-reglas"><b>Reglas del formato</b><ul>' +
      '<li>Horas del día = salida − entrada − 1 hora de almuerzo. Si no almorzó, quita la marca de «Almorzó» y se cuentan todas las horas.</li>' +
      '<li>Máximo 42 horas en la semana; más necesita autorización previa de la Directora de Talento Humano.</li>' +
      '<li>Cada persona descansa en las fechas acordadas con el equipo.</li>' +
      '<li>Vacaciones, permisos, incapacidades o calamidades se marcan en la novedad del día y en observaciones.</li>' +
      '<li>En quincena y cierre de mes la administradora está de apertura a cierre.</li></ul></div></div>';

  if (raizAdmin) {
    raizAdmin.replaceChildren(raiz);
  } else {
    // Pestañas en «Horarios del equipo»: los turnos de arrastrar siguen igual
    var cabecera = paginaTurnos.querySelector('.cuadrante-header');
    var tabs = el('div', 'pl-tabs', '<button type="button" data-vista="planilla" aria-pressed="false"><i class="bi bi-clock-history"></i> Planilla de horas</button>' +
      '<button type="button" class="on" data-vista="turnos" aria-pressed="true"><i class="bi bi-hand-index-thumb"></i> Turnos de la semana <span class="pl-auto">se llenan con la planilla</span></button>');
    cabecera.parentNode.insertBefore(tabs, cabecera.nextSibling);
    raiz.hidden = true;
    paginaTurnos.appendChild(raiz);
    var deTurnos = [paginaTurnos.querySelector('.summary-grid'), paginaTurnos.querySelector('.schedule-layout')].concat(
      Array.prototype.slice.call(cabecera.children).filter(function (n) { return !n.classList.contains('header-title'); }));
    tabs.addEventListener('click', function (e) {
      var b = e.target.closest('[data-vista]');
      if (!b) return;
      var plan = b.dataset.vista === 'planilla';
      tabs.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', String(x === b)); });
      deTurnos.forEach(function (n) { if (n) n.hidden = plan; });
      raiz.hidden = !plan;
      if (plan) cargar(domingo || hoyDomingo());
      try { sessionStorage.setItem('lh-horarios-vista', b.dataset.vista); } catch (er) { /* sin almacenamiento */ }
      if (!plan && turnosViejos) location.reload();   // los turnos cambiaron al guardar la planilla
    });
    // La planilla es la principal: se abre primero, salvo que la persona estuviera en los turnos
    var vista = null; try { vista = sessionStorage.getItem('lh-horarios-vista'); } catch (er) { /* sin almacenamiento */ }
    if (vista !== 'turnos') tabs.querySelector('[data-vista="planilla"]').click();
  }
  if (raizAdmin) cargar(hoyDomingo());

  function hoyDomingo() { var d = new Date(); d.setDate(d.getDate() - d.getDay()); return iso(d); }

  /* ---------------- Cargar y pintar ---------------- */
  function cargar(dom) {
    if (cambios && !confirm('Hay cambios sin guardar en esta semana. ¿Salir sin guardar?')) return;
    estado('Cargando…');
    fetch('/planilla/api/semana?' + q({ fecha: dom }), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      datos = d; domingo = d.domingo; cambios = false;
      pintar(); estado('');
    }).catch(function () { estado('No se pudo cargar la planilla.', true); });
  }

  function estado(texto, malo) { var n = raiz.querySelector('.pl-estado'); n.textContent = texto; n.classList.toggle('malo', !!malo); }

  function pintar() {
    var d0 = fecha(datos.dias[0].fecha), d6 = fecha(datos.dias[6].fecha);
    raiz.querySelector('.pl-titulo').textContent = 'Del domingo ' + d0.getDate() + ' de ' + MESES[d0.getMonth()] + ' al sábado ' + d6.getDate() + ' de ' + MESES[d6.getMonth()];
    var mes = MESES[fecha(datos.dias[3].fecha).getMonth()];
    raiz.querySelector('[data-pl="excel"]').innerHTML = '<i class="bi bi-file-earmark-excel"></i> Descargar Excel de ' + mes;
    pintarHorario();
    raiz.querySelector('[data-pl="persona"]').hidden = !datos.agregar;
    var thead = raiz.querySelector('thead'), tbody = raiz.querySelector('tbody');
    thead.innerHTML = '<tr><th class="pl-col-persona">Persona</th>' + datos.dias.map(function (d) {
      var f = fecha(d.fecha);
      return '<th class="' + (d.festivo ? 'festivo' : '') + '"><b>' + d.nombre.slice(0, 3) + ' ' + f.getDate() + '</b>' +
        (d.festivo ? '<span class="pl-tag festivo">Festivo</span>' : '') + (d.quincena ? '<span class="pl-tag quincena">' + (f.getDate() === 15 ? 'Quincena' : 'Cierre de mes') + '</span>' : '') +
        '<small>' + (d.horario ? d.horario.apertura + '–' + d.horario.cierre : 'Sin horario') + '</small></th>';
    }).join('') + '<th class="pl-col-total">Horas semana</th><th class="pl-col-obs">Observaciones</th></tr>';
    tbody.innerHTML = '';
    datos.filas.forEach(function (f, i) { tbody.appendChild(filaPersona(f, i)); });
    if (datos.agregar) {
      var mas = el('tr', 'pl-mas'); mas.innerHTML = '<td colspan="10"><button type="button" class="pl-btn-mas" data-pl="persona"><i class="bi bi-person-plus-fill"></i> Agregar persona <small>auxiliar, subadministradora, volante…</small></button></td>';
      tbody.appendChild(mas);
    }
    var pie = el('tr', 'pl-totales'); pie.innerHTML = '<td>Horas del equipo</td>' + datos.dias.map(function () { return '<td></td>'; }).join('') + '<td></td><td></td>';
    tbody.appendChild(pie);
    var quienFila = el('tr', 'pl-quien'); quienFila.innerHTML = '<td>Quién abre, cierra y descansa</td>' + datos.dias.map(function () { return '<td></td>'; }).join('') + '<td></td><td></td>';
    tbody.appendChild(quienFila);
    recalcular();
    pintarAlertas();
  }

  function pintarHorario() {
    var h = datos.horario || [];
    raiz.querySelector('.pl-horario').innerHTML = '<span class="pl-kicker">Horario de la tienda</span>' +
      (h.length ? h.map(function (x) { return '<span class="pl-chip"><b>' + esc(x.dias) + '</b> ' + esc(x.apertura) + ' a ' + esc(x.cierre) + '</span>'; }).join('') : '<span class="pl-chip malo">Sin horario: agrégalo</span>') +
      '<small>' + (datos.horario_origen === 'formato' ? 'Tomado de «Horas trabajadas por punto».' : 'Definido por la tienda.') + '</small>' +
      '<button type="button" class="pl-btn chico" data-pl="horario"><i class="bi bi-pencil"></i> Cambiar horario</button>';
  }

  function filaPersona(f, i) {
    var tr = el('tr');
    tr.dataset.i = i;
    tr.innerHTML = '<td class="pl-col-persona"><select class="pl-cargo" aria-label="Cargo de ' + esc(f.nombre) + '">' + datos.cargos.map(function (c) { return '<option' + (c === f.cargo ? ' selected' : '') + '>' + c + '</option>'; }).join('') + '</select>' +
      '<b>' + esc(f.nombre) + (f.manual && datos.agregar ? ' <button type="button" class="pl-quitar" data-pl="quitar" title="Quitar de la planilla" aria-label="Quitar a ' + esc(f.nombre) + ' de la planilla"><i class="bi bi-x"></i></button>' : '') + '</b><input class="pl-cedula" inputmode="numeric" placeholder="Cédula (opcional)" value="' + esc(f.cedula) + '" aria-label="Cédula de ' + esc(f.nombre) + '"></td>' +
      f.celdas.map(function (c, j) {
        return '<td class="pl-dia' + (c.sugerido ? ' sugerido' : '') + (c.novedad !== 'TRABAJA' ? ' novedad' : '') + '" data-j="' + j + '">' +
          '<select class="pl-nov" aria-label="Novedad del día">' + datos.novedades.map(function (n) { return '<option value="' + n + '"' + (n === c.novedad ? ' selected' : '') + '>' + NOV[n] + '</option>'; }).join('') + '</select>' +
          '<div class="pl-horas"><select class="pl-ent" aria-label="Entrada">' + opcionesHora(c.entrada, 'Entra') + '</select><select class="pl-sal" aria-label="Salida">' + opcionesHora(c.salida, 'Sale') + '</select>' +
          '<label class="pl-almuerzo" title="Si no almorzó, quita la marca: se cuentan todas las horas"><input type="checkbox" class="pl-alm"' + (c.almuerzo === false ? '' : ' checked') + '> Almorzó</label></div>' +
          '<span class="pl-turno"></span><span class="pl-tht"></span>' + (c.th ? '<span class="pl-th" title="Novedad registrada por Talento Humano">TH: ' + esc(c.th) + '</span>' : c.sugerido ? '<span class="pl-sug" title="Sugerido con el turno arrastrado y el horario de la tienda. Se guarda al tocar «Guardar planilla».">sugerido</span>' : '') + '</td>';
      }).join('') +
      '<td class="pl-col-total"><b class="pl-total"></b></td><td class="pl-col-obs"><textarea class="pl-obs" rows="2" placeholder="Vacaciones, permiso, incapacidad…" aria-label="Observaciones de la semana">' + esc(f.observacion) + '</textarea></td>';
    return tr;
  }

  // Solo horas en punto (5 a. m. a 11 p. m.); si ya había una hora con minutos se conserva
  function etiquetaHora(hhmm) { var h = +hhmm.slice(0, 2), m = hhmm.slice(3); return (h % 12 || 12) + (m !== '00' ? ':' + m : '') + (h < 12 ? ' a. m.' : ' p. m.'); }
  function opcionesHora(valor, vacio) {
    var horas = []; for (var h = 5; h <= 23; h++) horas.push(String(h).padStart(2, '0') + ':00');
    if (valor && horas.indexOf(valor) < 0) { horas.push(valor); horas.sort(); }
    return '<option value="">' + vacio + '</option>' + horas.map(function (x) { return '<option value="' + x + '"' + (x === valor ? ' selected' : '') + '>' + etiquetaHora(x) + '</option>'; }).join('');
  }

  function ponerHora(sel, valor) {
    if (valor && !Array.prototype.some.call(sel.options, function (o) { return o.value === valor; })) sel.add(new Option(etiquetaHora(valor), valor));
    sel.value = valor || '';
  }

  function leerFila(tr) {
    var f = datos.filas[+tr.dataset.i];
    return {
      persona_id: f.persona_id, nombre: f.nombre,
      cargo: tr.querySelector('.pl-cargo').value, cedula: tr.querySelector('.pl-cedula').value,
      observacion: tr.querySelector('.pl-obs').value,
      celdas: Array.prototype.map.call(tr.querySelectorAll('.pl-dia'), function (td) {
        var nov = td.querySelector('.pl-nov').value, trabaja = nov === 'TRABAJA';
        return { fecha: f.celdas[+td.dataset.j].fecha, novedad: nov, entrada: trabaja ? td.querySelector('.pl-ent').value : '', salida: trabaja ? td.querySelector('.pl-sal').value : '', almuerzo: td.querySelector('.pl-alm').checked, observacion: f.celdas[+td.dataset.j].observacion || '' };
      })
    };
  }

  function turnoDe(entrada, salida, h) {
    if (!entrada || !salida || !h) return '';
    var abre = minutos(entrada) <= minutos(h.apertura), cierra = minutos(salida) >= minutos(h.cierre);
    return abre && cierra ? 'Apertura a cierre' : abre ? 'Apertura' : cierra ? 'Cierre' : 'Intermedio';
  }
  function recalcular() {
    var porDia = [0, 0, 0, 0, 0, 0, 0], quien = [0, 1, 2, 3, 4, 5, 6].map(function () { return { abre: [], cierra: [], descansa: [] }; });
    raiz.querySelectorAll('tbody tr[data-i]').forEach(function (tr) {
      var total = 0, nombre = datos.filas[+tr.dataset.i].nombre.split(' ')[0];
      tr.querySelectorAll('.pl-dia').forEach(function (td, j) {
        var trabaja = td.querySelector('.pl-nov').value === 'TRABAJA';
        var ent = td.querySelector('.pl-ent').value, sal = td.querySelector('.pl-sal').value;
        var turno = trabaja ? turnoDe(ent, sal, datos.dias[j].horario) : '';
        td.querySelector('.pl-turno').textContent = turno;
        td.querySelector('.pl-turno').className = 'pl-turno ' + (turno === 'Apertura' ? 'abre' : turno === 'Cierre' ? 'cierra' : turno === 'Apertura a cierre' ? 'todo' : '');
        if (/Apertura/.test(turno)) quien[j].abre.push(nombre);
        if (/cierre|Cierre/.test(turno)) quien[j].cierra.push(nombre);
        if (!trabaja || (!ent && !sal)) quien[j].descansa.push(nombre + (trabaja ? '' : ' (' + NOV[td.querySelector('.pl-nov').value].toLowerCase() + ')'));
        td.classList.toggle('novedad', !trabaja);
        td.querySelector('.pl-horas').hidden = !trabaja;
        var alm = td.querySelector('.pl-alm').checked;
        td.classList.toggle('sin-almuerzo', trabaja && !alm);
        var h = trabaja ? horas(td.querySelector('.pl-ent').value, td.querySelector('.pl-sal').value, alm) : 0;
        var malo = trabaja && td.querySelector('.pl-ent').value && td.querySelector('.pl-sal').value && h === 0;
        td.querySelector('.pl-tht').textContent = trabaja ? (malo ? 'Revisa la hora' : h ? num(h) + ' h' + (alm ? '' : ' · sin almuerzo') : '') : NOV[td.querySelector('.pl-nov').value];
        td.classList.toggle('error', !!malo);
        total += h; porDia[j] += h;
      });
      var t = tr.querySelector('.pl-total');
      t.textContent = num(total) + ' h';
      t.classList.toggle('alto', total > datos.limite);
      t.title = total > datos.limite ? 'Más de ' + datos.limite + ' h: necesita autorización de Talento Humano' : '';
    });
    var pie = raiz.querySelectorAll('.pl-totales td');
    porDia.forEach(function (h, j) { pie[j + 1].textContent = h ? num(h) + ' h' : '—'; });
    var res = raiz.querySelectorAll('.pl-quien td');
    quien.forEach(function (q, j) {
      res[j + 1].innerHTML = '<span class="abre">Abre: ' + (q.abre.join(', ') || '<b>nadie</b>') + '</span><span class="cierra">Cierra: ' + (q.cierra.join(', ') || '<b>nadie</b>') + '</span>' +
        (q.descansa.length ? '<span class="descansa">Descansa: ' + q.descansa.join(', ') + '</span>' : '');
    });
    pie[8].textContent = num(porDia.reduce(function (a, b) { return a + b; }, 0)) + ' h';
  }

  function pintarAlertas() {
    var a = datos.alertas || [];
    raiz.querySelector('.pl-alertas').innerHTML = '<b>Revisión de la semana</b>' + (a.length
      ? '<ul>' + a.map(function (x) { return '<li class="' + x.nivel + '"><i class="bi ' + (x.nivel === 'alta' ? 'bi-exclamation-octagon-fill' : 'bi-exclamation-triangle-fill') + '"></i> ' + esc(x.texto) + '</li>'; }).join('') + '</ul>'
      : '<p class="pl-ok"><i class="bi bi-check-circle-fill"></i> Todo en orden: nadie pasa de 42 horas, todas descansan y la tienda abre y cierra cada día.</p>') +
      (cambios ? '<p class="pl-nota">Guarda para volver a revisar.</p>' : '');
  }

  /* ---------------- Eventos ---------------- */
  raiz.addEventListener('input', function (e) {
    if (!e.target.closest('tbody')) return;
    var td = e.target.closest('.pl-dia');
    if (td) { td.classList.remove('sugerido'); var s = td.querySelector('.pl-sug'); if (s) s.remove(); }
    cambios = true; estado('Cambios sin guardar');
    recalcular();
  });
  raiz.addEventListener('change', function (e) { if (e.target.closest('tbody')) { cambios = true; estado('Cambios sin guardar'); recalcular(); } });
  raiz.addEventListener('click', function (e) {
    var b = e.target.closest('[data-pl]');
    if (!b) return;
    var accion = b.dataset.pl;
    if (accion === 'anterior' || accion === 'siguiente') { var d = fecha(domingo); d.setDate(d.getDate() + (accion === 'anterior' ? -7 : 7)); cargar(iso(d)); }
    if (accion === 'hoy') cargar(hoyDomingo());
    if (accion === 'guardar') guardar();
    if (accion === 'excel') {
      if (cambios) { alert('Primero guarda la planilla: el Excel lleva lo guardado.'); return; }
      var m = fecha(datos.dias[3].fecha);
      location.href = '/planilla/exportar?' + q({ mes: m.getFullYear() + '-' + String(m.getMonth() + 1).padStart(2, '0') });
    }
    if (accion === 'copiar') copiarAnterior();
    if (accion === 'horario') editarHorario();
    if (accion === 'persona') agregarPersona();
    if (accion === 'quitar') quitarPersona(datos.filas[+b.closest('tr').dataset.i]);
  });

  function guardar() {
    var filas = Array.prototype.map.call(raiz.querySelectorAll('tbody tr[data-i]'), leerFila);
    estado('Guardando…');
    fetch('/planilla/api/semana?' + q(), { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ domingo: domingo, filas: filas, store_id: storeId || undefined }) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (x) {
        if (!x.ok || !x.j.ok) { estado(x.j.error || 'No se pudo guardar.', true); return; }
        datos = x.j; cambios = false; turnosViejos = true; pintar(); estado('Guardado ✓ · turnos de la semana actualizados');
      }).catch(function () { estado('No se pudo guardar.', true); });
  }

  function copiarAnterior() {
    var d = fecha(domingo); d.setDate(d.getDate() - 7);
    fetch('/planilla/api/semana?' + q({ fecha: iso(d) }), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (ant) {
      var porPersona = {};
      ant.filas.forEach(function (f) { porPersona[f.persona_id] = f; });
      raiz.querySelectorAll('tbody tr[data-i]').forEach(function (tr) {
        var f = porPersona[datos.filas[+tr.dataset.i].persona_id];
        if (!f) return;
        tr.querySelectorAll('.pl-dia').forEach(function (td, j) {
          var c = f.celdas[j];
          td.querySelector('.pl-nov').value = c.novedad;
          ponerHora(td.querySelector('.pl-ent'), c.entrada); ponerHora(td.querySelector('.pl-sal'), c.salida);
          td.querySelector('.pl-alm').checked = c.almuerzo !== false;
          td.classList.remove('sugerido'); var s = td.querySelector('.pl-sug'); if (s) s.remove();
        });
      });
      cambios = true; estado('Copiada la semana anterior: revisa y guarda'); recalcular();
    });
  }

  function agregarPersona() {
    if (cambios && !confirm('Hay cambios sin guardar. Guarda primero o se perderán al agregar la persona. ¿Seguir sin guardar?')) return;
    var cargos = datos.cargos.filter(function (c) { return c !== 'Administradora'; });
    var v = el('div', 'pl-modal', '<form class="pl-caja" role="dialog" aria-modal="true" aria-label="Agregar persona"><header><h3>Agregar persona a la planilla</h3><button type="button" class="pl-cerrar" aria-label="Cerrar"><i class="bi bi-x-lg"></i></button></header>' +
      '<p class="pl-nota">Para quien no sale sola en la planilla: auxiliar, subadministradora, volante… Queda en esta tienda hasta que la quites.</p>' +
      '<div class="pl-campos"><label>Nombre completo<input name="nombre" required minlength="3" maxlength="120" autocomplete="off"></label>' +
      '<label>Cargo<select name="cargo">' + cargos.map(function (c) { return '<option' + (c === 'Auxiliar' ? ' selected' : '') + '>' + c + '</option>'; }).join('') + '</select></label>' +
      '<label>Cédula (opcional)<input name="cedula" inputmode="numeric" maxlength="20"></label></div>' +
      '<p class="pl-error" aria-live="polite"></p>' +
      '<footer><button type="button" class="pl-btn" data-h="cancelar">Cancelar</button><button type="submit" class="pl-btn primario">Agregar</button></footer></form>');
    document.body.appendChild(v);
    var form = v.querySelector('form');
    form.nombre.focus();
    v.addEventListener('click', function (e) { if (e.target === v || e.target.closest('.pl-cerrar') || e.target.closest('[data-h="cancelar"]')) v.remove(); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      fetch('/planilla/api/persona?' + q(), { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre: form.nombre.value, cargo: form.cargo.value, cedula: form.cedula.value, store_id: storeId || undefined }) })
        .then(function (r) { return r.json(); }).then(function (j) {
          if (!j.ok) { v.querySelector('.pl-error').textContent = j.error || 'No se pudo agregar.'; return; }
          v.remove(); cambios = false; cargar(domingo); estado('Persona agregada ✓');
        }).catch(function () { v.querySelector('.pl-error').textContent = 'No se pudo agregar.'; });
    });
  }

  function quitarPersona(f) {
    if (!confirm('¿Quitar a ' + f.nombre + ' de la planilla? Sus horas guardadas no se borran y vuelve si la agregas otra vez.')) return;
    fetch('/planilla/api/persona/' + f.persona_id + '?' + q(), { method: 'DELETE', credentials: 'same-origin' })
      .then(function (r) { return r.json(); }).then(function (j) {
        if (!j.ok) { estado(j.error || 'No se pudo quitar.', true); return; }
        cambios = false; cargar(domingo);
      });
  }

  function editarHorario() {
    var filas = (datos.horario || []).slice();
    var v = el('div', 'pl-modal', '<div class="pl-caja" role="dialog" aria-modal="true" aria-label="Horario de la tienda"><header><h3>Horario de la tienda</h3><button type="button" class="pl-cerrar" aria-label="Cerrar"><i class="bi bi-x-lg"></i></button></header>' +
      '<p class="pl-nota">Días como en el formato: L-J (lunes a jueves), V-S, L-S, D-F (domingos y festivos)…</p><div class="pl-hfilas"></div>' +
      '<p><button type="button" class="pl-btn chico" data-h="mas"><i class="bi bi-plus"></i> Agregar fila</button></p>' +
      '<footer><button type="button" class="pl-btn" data-h="cancelar">Cancelar</button><button type="button" class="pl-btn primario" data-h="guardar">Guardar horario</button></footer></div>');
    function pintarFilas() {
      v.querySelector('.pl-hfilas').innerHTML = filas.map(function (f, i) {
        return '<div class="pl-hfila" data-i="' + i + '"><input class="pl-hd" value="' + esc(f.dias) + '" aria-label="Días" placeholder="L-S"><input type="time" class="pl-ha" value="' + esc(f.apertura) + '" aria-label="Apertura"><span>a</span><input type="time" class="pl-hc" value="' + esc(f.cierre) + '" aria-label="Cierre"><button type="button" class="pl-btn icono" data-h="quitar" aria-label="Quitar fila"><i class="bi bi-trash"></i></button></div>';
      }).join('');
    }
    function leer() { filas = Array.prototype.map.call(v.querySelectorAll('.pl-hfila'), function (n) { return { dias: n.querySelector('.pl-hd').value, apertura: n.querySelector('.pl-ha').value, cierre: n.querySelector('.pl-hc').value }; }); }
    pintarFilas();
    document.body.appendChild(v);
    v.addEventListener('click', function (e) {
      var b = e.target.closest('[data-h]');
      if (e.target === v || e.target.closest('.pl-cerrar') || (b && b.dataset.h === 'cancelar')) { v.remove(); return; }
      if (!b) return;
      leer();
      if (b.dataset.h === 'mas') { filas.push({ dias: '', apertura: '10:00', cierre: '20:00' }); pintarFilas(); }
      if (b.dataset.h === 'quitar') { filas.splice(+b.closest('.pl-hfila').dataset.i, 1); pintarFilas(); }
      if (b.dataset.h === 'guardar') {
        fetch('/planilla/api/horario?' + q(), { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ horario: filas, store_id: storeId || undefined }) })
          .then(function (r) { return r.json(); }).then(function () { v.remove(); cambios = false; cargar(domingo); });
      }
    });
  }

  window.addEventListener('beforeunload', function (e) { if (cambios) { e.preventDefault(); e.returnValue = ''; } });
})();
