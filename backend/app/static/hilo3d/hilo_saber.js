/* ================================================================
   Lo que Hilo sabe y cómo lo cuenta
   - Carga los datos de /api/hilo/tienda o /api/hilo/admin (solo lectura).
   - Arma las tarjetas: cierre del mes, plan por día, reto del día, coach de
     conversión, comparación con tiendas del mismo clima, meta distribuible,
     y para la administración: resumen de la red, tiendas en riesgo, causas,
     tiendas sin entrar, calidad de datos, a quién felicitar, pronóstico V3,
     cambios bruscos, mensajes sugeridos e informe semanal.
   - «Pregúntale a Hilo»: responde preguntas en español con reglas (sin IA de pago).
   - Voz opcional con la voz del navegador.
   ================================================================ */

/* ---------- Datos ---------- */
export async function cargarDatos(P) {
  const q = new URLSearchParams();
  let url;
  if (P.tipo === 'tienda') {
    const D = P.D;
    ['anio', 'mes', 'dia_corte'].forEach(k => { if (D[k]) q.set(k, D[k]); });
    const m = location.pathname.match(/\/dashboard\/tienda\/(\d+)/);
    if (m) q.set('store_id', m[1]);
    url = '/api/hilo/tienda';
  } else if (P.tipo === 'admin') {
    const p = new URLSearchParams(location.search);
    const anio = p.get('anio') || P.corte.anio, mes = p.get('mes') || P.corte.mes, dia = p.get('dia_corte') || P.corte.dia;
    if (anio) q.set('anio', anio);
    if (mes) q.set('mes', mes);
    if (dia) q.set('dia_corte', dia);
    url = '/api/hilo/admin';
  } else return null;
  try {
    const r = await fetch(`${url}?${q}`, { credentials: 'same-origin' });
    if (!r.ok) return null;
    const datos = await r.json();
    return datos && datos.ok ? datos : null;
  } catch (e) { return null; }
}

export async function enviarMensaje({ texto, tono, tiendas, dias }) {
  try {
    const r = await fetch('/api/hilo/admin/mensaje', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto, tono, tiendas, dias: dias || 3 })
    });
    const d = await r.json().catch(() => ({}));
    return r.ok && d.ok;
  } catch (e) { return false; }
}

/* ---------- Reto del día ---------- */
export function retoDelDia(D, S) {
  const opciones = [];
  const conv = S && S.conversion;
  if (conv && conv.conversion != null && conv.conversion < 0.2 && conv.trafico_dia > 0) {
    const meta = Math.ceil(conv.trafico_dia * 0.2);
    opciones.push({
      tipo: 'facturas', objetivo: meta, icono: 'bi-people',
      texto: `Lograr ${meta} facturas hoy`,
      detalle: `Entran unas ${conv.trafico_dia} personas al día. Si compran 20 de cada 100 son ${meta} compras (hoy compran ${Math.round(conv.conversion * 100)} de cada 100).`
    });
  }
  if (num(D.meta_vpt) > 0 && num(D.ticket) > 0 && num(D.ticket) < num(D.meta_vpt)) opciones.push({
    tipo: 'vpt', objetivo: num(D.meta_vpt), icono: 'bi-bag-check',
    texto: `Cada compra de ${dinero(D.meta_vpt)} o más`,
    detalle: `El tiquete promedio va en ${dinero(D.ticket)}. Ofrezcan un complemento en cada compra.`
  });
  if (num(D.upt) > 0 && num(D.upt) < 2) opciones.push({
    tipo: 'upt', objetivo: 2, icono: 'bi-layers',
    texto: 'Que cada cliente lleve 2 prendas',
    detalle: `Hoy llevan ${num(D.upt).toFixed(2)} prendas por compra. Muestren la prenda que combina con lo que eligió.`
  });
  const pr = S && S.proyeccion;
  if (pr && !pr.cerrado && pr.falta > 0) {
    const hoy = new Date();
    const paso = (pr.plan || []).find(p => S.corte.anio === hoy.getFullYear() && S.corte.mes === hoy.getMonth() + 1 && p.dia === hoy.getDate()) || (pr.plan || [])[0];
    const valor = paso ? paso.valor : pr.necesita_dia;
    opciones.push({
      tipo: 'venta', objetivo: valor, dia: paso ? paso.dia : null, icono: 'bi-graph-up-arrow',
      texto: `Vender ${dinero(valor)} hoy`,
      detalle: 'Es lo que pide la meta para hoy, según cómo vende la tienda este día de la semana.'
    });
  }
  if (!opciones.length) return null;
  const h = new Date();
  const n = Math.floor((Date.UTC(h.getFullYear(), h.getMonth(), h.getDate()) - Date.UTC(h.getFullYear(), 0, 1)) / 864e5);
  return opciones[n % opciones.length];
}

// Guarda el reto mostrado hoy y dice cómo les fue en los retos anteriores (cuando ya hay datos de ese día)
export function anotarReto(tiendaId, reto) {
  if (!reto || reto.tipo === 'upt') return;
  const k = 'lhpulse-hilo-retos-' + tiendaId;
  const lista = leerJSON(localStorage, k, {});
  const hoy = fechaISO(new Date());
  if (!lista[hoy]) lista[hoy] = { tipo: reto.tipo, objetivo: reto.objetivo };
  Object.keys(lista).sort().slice(0, -20).forEach(f => delete lista[f]);
  guardar(localStorage, k, JSON.stringify(lista));
}
export function resultadoRetoAnterior(tiendaId, S) {
  if (!S) return null;
  const k = 'lhpulse-hilo-retos-' + tiendaId;
  const lista = leerJSON(localStorage, k, {});
  let ultimo = null;
  Object.keys(lista).sort().forEach(f => {
    const [a, m, d] = f.split('-').map(Number);
    const r = lista[f];
    if (a !== S.corte.anio || m !== S.corte.mes || d > S.corte.dia || r.hecho) return;
    const venta = (S.dias.find(x => x.dia === d) || {}).venta || 0;
    const fact = (S.diario.find(x => x.dia === d) || {}).facturas || 0;
    let logrado = null, texto = '';
    if (r.tipo === 'facturas') { logrado = fact; texto = `${fact} facturas de ${r.objetivo}`; }
    else if (r.tipo === 'venta') { logrado = venta; texto = `${dinero(venta)} de ${dinero(r.objetivo)}`; }
    else if (r.tipo === 'vpt' && fact > 0) { logrado = venta / fact; texto = `tiquete de ${dinero(venta / fact)} (meta ${dinero(r.objetivo)})`; }
    if (logrado == null) return;
    r.hecho = true;
    const nombre = DIAS[new Date(a, m - 1, d).getDay()];
    ultimo = { cumplido: logrado >= r.objetivo, texto: `Reto del ${nombre} ${d}: ${texto}.` };
  });
  guardar(localStorage, k, JSON.stringify(lista));
  return ultimo;
}

/* ---------- Celebraciones automáticas ---------- */
export function celebracionesNuevas(D, S, periodo) {
  const salida = [];
  const k = 'lhpulse-hilo-cien-' + periodo;
  const antes = new Set(leerJSON(localStorage, k, []));
  const yaVisto = leer(localStorage, k) != null;
  const ahora = (D.asesoras || []).filter(a => !a.generico && num(a.meta) > 0 && num(a.venta) >= num(a.meta)).map(a => a.nombre);
  guardar(localStorage, k, JSON.stringify(ahora));
  const nuevas = ahora.filter(n => !antes.has(n));
  if (nuevas.length && (yaVisto || nuevas.length <= 3)) salida.push({
    pose: 'aplaude',
    texto: nuevas.length === 1 ? `¡${primerNombre(nuevas[0])} ya pasó el 100 % de su meta del mes! 👏` : `¡${unir(nuevas.map(primerNombre))} ya pasaron el 100 % de su meta del mes! 👏`
  });
  if (S && S.celebra) {
    const c = S.celebra;
    const base = `lhpulse-hilo-celebra-${periodo}-${S.corte.dia}`;
    if (c.record && !leer(localStorage, base + '-record')) {
      guardar(localStorage, base + '-record', '1');
      const nombre = DIAS[new Date(S.corte.anio, S.corte.mes - 1, c.record.dia).getDay()];
      salida.push({ pose: 'feliz', saltos: 4, texto: `¡Récord del mes! El ${nombre} ${c.record.dia} vendieron ${dinero(c.record.venta)} 🏆` });
    }
    if (c.racha >= 3 && !leer(localStorage, base + '-racha')) {
      guardar(localStorage, base + '-racha', '1');
      salida.push({ pose: 'aplaude', texto: `¡Llevan ${c.racha} días seguidos vendiendo más que la meta del día! 🔥` });
    }
  }
  return salida;
}

/* ---------- Tarjetas ---------- */
function tarjeta(titulo, sub, icono) {
  const c = el('section', 'hilo-card');
  const cab = el('header', 'hilo-card-cab');
  if (icono) cab.append(el('i', `bi ${icono} hilo-card-icono`));
  const t = el('div');
  t.append(el('strong', '', titulo));
  if (sub) t.append(el('small', '', sub));
  cab.append(t);
  const cuerpo = el('div', 'hilo-card-cuerpo');
  c.append(cab, cuerpo);
  return { c, cuerpo };
}
function fila(etiqueta, valor, clase) {
  const f = el('div', 'hilo-fila' + (clase ? ' ' + clase : ''));
  f.append(el('span', '', etiqueta), el('b', '', valor));
  return f;
}
function barra(valor, marca = 1) {
  const b = el('div', 'hilo-barra');
  const llenado = el('span');
  const v = Math.max(0, Math.min(num(valor) / 1.25, 1));
  llenado.style.width = (v * 100) + '%';
  llenado.dataset.nivel = num(valor) >= 1 ? 'ok' : num(valor) >= 0.9 ? 'bajo' : num(valor) >= 0.75 ? 'medio' : 'alto';
  const m = el('i'); m.style.left = (marca / 1.25 * 100) + '%';
  b.append(llenado, m);
  b.setAttribute('role', 'img');
  b.setAttribute('aria-label', `${pct(valor)} de la meta`);
  return b;
}
function enlace(texto, url, icono, nueva) {
  const a = el('a', 'hilo-accion');
  a.href = url;
  if (nueva) { a.target = '_blank'; a.rel = 'noopener'; }
  if (icono) a.append(el('i', `bi ${icono}`));
  a.append(document.createTextNode(texto));
  return a;
}
function boton(texto, icono, alHacer, clase) {
  const b = el('button', 'hilo-accion' + (clase ? ' ' + clase : ''));
  b.type = 'button';
  if (icono) b.append(el('i', `bi ${icono}`));
  b.append(document.createTextNode(texto));
  b.addEventListener('click', alHacer);
  return b;
}
function lista(items) {
  const ul = el('ul', 'hilo-lista');
  items.forEach(i => ul.append(i));
  return ul;
}
function item(titulo, detalle, nivel, extra) {
  const li = el('li');
  if (nivel) { const p = el('span', 'hilo-app-punto'); p.dataset.nivel = nivel; li.append(p); }
  const t = el('div', 'hilo-lista-texto');
  t.append(el('span', 'hilo-lista-titulo', titulo));
  if (detalle) t.append(el('small', '', detalle));
  li.append(t);
  if (extra) li.append(extra);
  return li;
}

// Pequeño editor para mandar un mensaje con Hilo sin salir de la página
function redactor({ texto, tono, tiendas, etiqueta = 'Enviar con Hilo' }) {
  const caja = el('div', 'hilo-redactor');
  const abrir = boton(etiqueta, 'bi-chat-heart', () => {
    abrir.hidden = true;
    form.hidden = false;
    area.focus();
  }, 'secundaria');
  const form = el('div', 'hilo-redactor-form'); form.hidden = true;
  const area = el('textarea'); area.maxLength = 400; area.rows = 3; area.value = texto;
  area.setAttribute('aria-label', 'Mensaje que dirá Hilo');
  const nota = el('small', '', tiendas && tiendas.length ? `Lo verán ${tiendas.length === 1 ? 'en esa tienda' : `en ${tiendas.length} tiendas`} durante 3 días.` : 'Lo verán todas las tiendas durante 3 días.');
  const acciones = el('div', 'hilo-redactor-acciones');
  const enviar = boton('Enviar', 'bi-send', async () => {
    enviar.disabled = true;
    const ok = await enviarMensaje({ texto: area.value, tono, tiendas });
    if (ok) caja.replaceChildren(el('p', 'hilo-ok', '✓ Listo: Hilo se lo dirá cuando entren.'));
    else { enviar.disabled = false; nota.textContent = 'No se pudo enviar. Intenta de nuevo.'; }
  });
  const cancelar = boton('Cancelar', null, () => { form.hidden = true; abrir.hidden = false; }, 'secundaria');
  acciones.append(enviar, cancelar);
  form.append(area, nota, acciones);
  caja.append(abrir, form);
  return caja;
}

export const T = {
  /* ===== Tienda ===== */
  proyeccion(S) {
    const pr = S && S.proyeccion;
    if (!pr) return null;
    const { c, cuerpo } = tarjeta(pr.cerrado ? 'Así cerró el mes' : 'Cierre del mes', pr.cerrado ? `${cap(S.corte.nombre_mes)} ${S.corte.anio}` : 'Si siguen a este ritmo', 'bi-flag');
    const grande = el('div', 'hilo-grande');
    grande.append(el('b', '', pct(pr.pct)), el('span', '', `≈ ${dinero(pr.valor)} de ${dinero(S.cuota_total)}`));
    cuerpo.append(grande, barra(pr.pct));
    if (!pr.cerrado) {
      cuerpo.append(
        fila('Venden en promedio', `${dinero(pr.ritmo_dia)} / día`),
        fila(pr.falta > 0 ? 'Para el 100 % necesitan' : 'Meta del mes', pr.falta > 0 ? `${dinero(pr.necesita_dia)} / día` : '¡Cumplida! 🎉', pr.falta > 0 && pr.necesita_dia > pr.ritmo_dia ? 'alerta' : 'bien'),
        fila('Días que quedan', String(pr.dias_restantes))
      );
      if (pr.falta > 0 && pr.plan.length) {
        cuerpo.append(el('p', 'hilo-subtitulo', 'Plan de los próximos días'));
        const tabla = el('div', 'hilo-plan');
        pr.plan.forEach(p => {
          const f = el('div');
          f.append(el('span', '', `${cap(p.nombre.slice(0, 3))} ${p.dia}`), el('b', '', dinero(p.valor)));
          tabla.append(f);
        });
        cuerpo.append(tabla);
        if (pr.metodo === 'semana') cuerpo.append(el('small', 'hilo-nota', 'Los días en que la tienda vende más piden un poco más.'));
        const esc = el('div', 'hilo-escenarios');
        pr.escenarios.forEach(e => {
          const x = el('div');
          x.append(el('span', '', `Para ${Math.round(e.pct * 100)} %`), el('b', '', e.logrado ? '✓' : `${dinero(e.por_dia)}/día`));
          esc.append(x);
        });
        cuerpo.append(esc);
      }
    }
    return c;
  },

  reto(reto, anterior) {
    if (!reto && !anterior) return null;
    const { c, cuerpo } = tarjeta('Reto del día', fechaLarga(new Date()), 'bi-lightning-charge');
    if (anterior) cuerpo.append(el('p', 'hilo-resultado' + (anterior.cumplido ? ' cumplido' : ''), `${anterior.cumplido ? '✓ ¡Cumplido! ' : ''}${anterior.texto}`));
    if (reto) {
      const g = el('div', 'hilo-reto');
      g.append(el('i', `bi ${reto.icono || 'bi-star'}`), el('b', '', reto.texto));
      cuerpo.append(g, el('p', 'hilo-texto', reto.detalle));
    }
    return c;
  },

  coach(S) {
    const cv = S && S.conversion;
    if (!cv || !cv.trafico) return null;
    const { c, cuerpo } = tarjeta('Coach de conversión', `${cap(S.corte.nombre_mes)} hasta el día ${S.corte.dia}`, 'bi-people');
    const g = el('div', 'hilo-grande');
    g.append(el('b', '', pct(cv.conversion)), el('span', '', `De ${miles(cv.trafico)} personas, compraron ${miles(cv.facturas)}`));
    cuerpo.append(g, barra(cv.conversion / 0.2));
    if (cv.facturas_faltan > 0) {
      cuerpo.append(
        fila('Facturas que faltaron para el 20 %', `${miles(cv.facturas_faltan)} (${String(cv.faltan_por_dia).replace('.', ',')}/día)`, 'alerta'),
        fila('Venta que se dejó de hacer', dinero(cv.venta_perdida), 'alerta')
      );
    } else cuerpo.append(el('p', 'hilo-ok', '¡Están por encima del 20 %! Cada cliente cuenta: sigan así.'));
    const horas = (cv.horas || []).filter(h => h.trafico > 0);
    if (horas.length >= 4) {
      cuerpo.append(el('p', 'hilo-subtitulo', 'Personas por hora (promedio por día)'));
      const max = Math.max(...horas.map(h => h.por_dia));
      const top = horas.slice().sort((a, b) => b.por_dia - a.por_dia).slice(0, 3).map(h => h.hora);
      const graf = el('div', 'hilo-horas');
      horas.forEach(h => {
        const col = el('div', top.includes(h.hora) ? 'pico' : '');
        const b = el('span'); b.style.height = Math.max(6, h.por_dia / max * 100) + '%';
        col.title = `${hora(h.hora)}: ${String(h.por_dia).replace('.', ',')} personas/día${h.conversion != null ? ` · conversión ${pct(h.conversion)}` : ''}`;
        col.append(b, el('small', '', String(h.hora > 12 ? h.hora - 12 : h.hora)));
        graf.append(col);
      });
      cuerpo.append(graf);
      const picos = horas.filter(h => top.includes(h.hora)).sort((a, b) => a.hora - b.hora);
      const conPeor = picos.filter(h => h.conversion != null).sort((a, b) => a.conversion - b.conversion)[0];
      let consejo = `Las horas con más gente: ${unir(picos.map(h => hora(h.hora)))}.`;
      if (conPeor && cv.conversion && conPeor.conversion < cv.conversion) consejo += ` A las ${hora(conPeor.hora)} compran solo ${Math.round(conPeor.conversion * 100)} de cada 100: pongan más asesoras en piso a esa hora.`;
      else consejo += ' Ahí es donde más se nota tener a todo el equipo en piso.';
      cuerpo.append(tip(consejo));
    }
    if ((cv.semana || []).length >= 5) {
      const mejor = cv.semana.slice().sort((a, b) => b.trafico - a.trafico)[0];
      cuerpo.append(el('small', 'hilo-nota', `El día con más gente es el ${mejor.dia} (unas ${mejor.trafico} personas).`));
    }
    return c;
  },

  comparacion(S) {
    const cp = S && S.comparacion;
    if (!cp || !cp.total) return null;
    const { c, cuerpo } = tarjeta(`Tiendas de clima ${cp.clima}`, 'Comparación justa: tiendas parecidas a la suya', 'bi-thermometer-sun');
    const g = el('div', 'hilo-grande');
    g.append(el('b', '', cp.puesto ? `${cp.puesto}° de ${cp.total}` : '—'), el('span', '', cp.puesto_general ? `En toda la red van ${cp.puesto_general}° de ${cp.total_general}` : ''));
    cuerpo.append(g);
    cuerpo.append(lista(cp.tiendas.map((t, i) => {
      const li = item(`${i + 1}. ${t.nombre}`, t.codigo, null, el('b', 'hilo-lista-valor', pct(t.cump)));
      if (t.mia) li.classList.add('mia');
      return li;
    })));
    if (cp.promedio) cuerpo.append(el('small', 'hilo-nota', `El promedio del grupo va en ${pct(cp.promedio)}.`));
    return c;
  },

  metaDistribuible(S) {
    const md = S && S.meta_distribuible;
    if (!md || !md.meta_tienda) return null;
    const { c, cuerpo } = tarjeta('Meta distribuible', 'Cómo se reparte la meta entre las asesoras', 'bi-diagram-3');
    cuerpo.append(
      fila('Meta de la tienda', dinero(md.meta_tienda)),
      fila('Venta de auxiliares', `− ${dinero(md.venta_auxiliares)}`),
      fila('Se reparte entre', `${md.de_planta} de planta`),
      fila('Meta distribuible', dinero(md.distribuible), 'bien')
    );
    if (md.revisar && md.revisar.length) {
      cuerpo.append(el('p', 'hilo-subtitulo', 'Para revisar'));
      cuerpo.append(lista(md.revisar.map(a => item(cap(a.nombre.toLowerCase()), `${cap(a.motivo)}. Sigue como «Fija» con meta de ${dinero(a.meta)}.`, 'medio'))));
      cuerpo.append(tip('Si no es de planta, en Metas y vendedores toca «Editar» y cámbiala a «Auxiliar»: su venta se descuenta y la meta se reparte entre las de planta.'));
    } else cuerpo.append(el('p', 'hilo-ok', 'Todo en orden: no veo asesoras que parezcan auxiliares marcadas como de planta.'));
    if (md.url) cuerpo.append(enlace('Ir a Metas y vendedores', md.url, 'bi-bullseye'));
    return c;
  },

  preguntas(tipo, alPreguntar) {
    const { c, cuerpo } = tarjeta('Pregúntale a Hilo', 'Escribe abajo o toca una pregunta', 'bi-chat-dots');
    const ejemplos = tipo === 'admin'
      ? ['¿Cómo va la red?', '¿Qué tiendas están en riesgo?', '¿Por qué bajó Caribe Plaza?', '¿Quién no ha entrado?', '¿A quién felicito?', '¿Cómo va el pronóstico V3?']
      : ['¿Cómo vamos a cerrar el mes?', '¿Cuánto debemos vender hoy?', '¿Quién va primera?', '¿A qué hora entra más gente?', '¿Cómo vamos frente al año pasado?', '¿Qué es el UPT?'];
    const chips = el('div', 'hilo-chips');
    ejemplos.forEach(e => chips.append(boton(e, null, () => alPreguntar(e), 'chip')));
    cuerpo.append(chips);
    return c;
  },

  /* ===== Administración ===== */
  resumen(A) {
    if (!A) return null;
    const r = A.red;
    const { c, cuerpo } = tarjeta('Resumen de la red', `${cap(A.corte.nombre_mes)} ${A.corte.anio} · corte día ${A.corte.dia}`, 'bi-speedometer2');
    const g = el('div', 'hilo-grande');
    g.append(el('b', '', pct(r.cump)), el('span', '', `al corte · ${r.al_dia} de ${r.tiendas} tiendas al día`));
    cuerpo.append(g, barra(r.cump));
    cuerpo.append(fila('Venta', dinero(r.venta)));
    if (r.crecimiento != null) cuerpo.append(fila('Frente al año anterior', signo(r.crecimiento), r.crecimiento < 0 ? 'alerta' : 'bien'));
    if (!r.cerrado && r.proy_pct != null) cuerpo.append(fila('Cierre proyectado', `${pct(r.proy_pct)} · ${dinero(r.proyeccion)}`, r.proy_pct < 1 ? 'alerta' : 'bien'));
    if (A.corte.atraso >= 1) cuerpo.append(el('p', 'hilo-resultado', `Ojo: los datos llegan hasta el día ${A.corte.dia} (faltan ${A.corte.atraso} ${A.corte.atraso === 1 ? 'día' : 'días'}).`));
    if (A.riesgo.length) {
      cuerpo.append(el('p', 'hilo-subtitulo', 'En riesgo de no llegar'));
      cuerpo.append(lista(A.riesgo.slice(0, 5).map(t => {
        const li = item(t.nombre, `${t.codigo} · proyecta ${pct(t.proy_pct)} · necesita ${dinero(t.necesita_dia)}/día`, t.proy_pct < 0.85 ? 'alto' : 'medio');
        if (t.url) li.append(enlace('', t.url, 'bi-box-arrow-up-right'));
        return li;
      })));
    }
    return c;
  },

  riesgo(A) {
    if (!A) return null;
    const { c, cuerpo } = tarjeta('Tiendas en riesgo', 'Proyectan cerrar por debajo del 95 %', 'bi-exclamation-triangle');
    if (!A.riesgo.length) { cuerpo.append(el('p', 'hilo-ok', A.red.cerrado ? 'El mes ya cerró.' : '¡Ninguna tienda proyecta cerrar por debajo del 95 %!')); return c; }
    cuerpo.append(lista(A.riesgo.map(t => {
      const li = item(t.nombre, `Proyecta ${pct(t.proy_pct)} · vende ${dinero(t.ritmo_dia)}/día y necesita ${dinero(t.necesita_dia)}/día`, t.proy_pct < 0.85 ? 'alto' : 'medio');
      if (t.url) li.append(enlace('', t.url, 'bi-box-arrow-up-right'));
      return li;
    })));
    cuerpo.append(redactor({
      texto: `Quedan ${A.red.dias_restantes} días del mes y todavía se puede. Revisen con Hilo cuánto necesitan vender por día y repartan el reto entre todas. ¡Vamos con toda!`,
      tono: 'anima', tiendas: A.riesgo.map(t => t.store_id), etiqueta: 'Animarlas con Hilo'
    }));
    return c;
  },

  diagnostico(A) {
    if (!A) return null;
    const bajan = A.diagnostico.filter(x => x.crecimiento < 0);
    const { c, cuerpo } = tarjeta('¿Por qué bajan?', 'Frente al mismo período del año anterior', 'bi-search');
    if (!bajan.length) { cuerpo.append(el('p', 'hilo-ok', '¡Todas las tiendas venden más que el año pasado!')); return c; }
    const nombres = { trafico: 'entra menos gente', conversion: 'compra menos gente de la que entra', ticket: 'cada compra vale menos' };
    bajan.slice(0, 7).forEach(x => {
      const b = el('div', 'hilo-diag');
      const cab = el('div', 'hilo-diag-cab');
      cab.append(el('b', '', x.nombre), el('span', 'malo', signo(x.crecimiento)));
      b.append(cab);
      if (x.causa) {
        const f = el('div', 'hilo-factores');
        [['trafico', 'Tráfico'], ['conversion', 'Conversión'], ['ticket', 'Tiquete']].forEach(([k, n]) => {
          const p = el('span', (x[k] < 0 ? 'malo' : 'bueno') + (x.causa === k ? ' causa' : ''));
          p.append(el('small', '', n), document.createTextNode(signo(x[k])));
          f.append(p);
        });
        b.append(f, el('small', 'hilo-nota', `Causa principal: ${nombres[x.causa]}.`));
      } else b.append(el('small', 'hilo-nota', 'No hay tráfico del año anterior para separar la causa.'));
      if (x.url) b.append(enlace('Ver tienda', x.url, 'bi-box-arrow-up-right'));
      cuerpo.append(b);
    });
    return c;
  },

  sinUso(A) {
    if (!A) return null;
    const su = A.sin_uso || {};
    const { c, cuerpo } = tarjeta('Tiendas que no entran', su.desde ? `Según el registro de accesos (desde el ${su.desde})` : 'Registro de accesos', 'bi-person-x');
    if (!su.activo) { cuerpo.append(el('p', 'hilo-texto', 'El registro de accesos todavía no tiene datos.')); return c; }
    if (!su.tiendas.length) { cuerpo.append(el('p', 'hilo-ok', '¡Todas las tiendas entraron en los últimos 3 días!')); return c; }
    cuerpo.append(lista(su.tiendas.map(t => item(t.nombre, `${t.codigo} · ${t.dias == null ? 'no ha entrado desde que empezó el registro' : `hace ${t.dias} días (${t.ultimo})`}`, t.dias == null || t.dias >= 7 ? 'alto' : 'medio'))));
    cuerpo.append(redactor({
      texto: 'Las extrañamos en L&H Pulse. Entren todos los días a revisar la meta de hoy de cada asesora: ahí está el plan para cerrar el mes.',
      tono: 'aviso', tiendas: su.tiendas.map(t => t.store_id), etiqueta: 'Recordarles con Hilo'
    }));
    return c;
  },

  calidad(A) {
    if (!A) return null;
    const { c, cuerpo } = tarjeta('Calidad de los datos', 'Lo que puede hacer ver mal los números', 'bi-clipboard-data');
    if (!A.calidad.length) { cuerpo.append(el('p', 'hilo-ok', 'Todo en orden: cargas al día, metas completas y sin días raros.')); return c; }
    A.calidad.forEach(a => {
      const b = el('div', 'hilo-calidad');
      const t = el('div', 'hilo-calidad-cab');
      const p = el('span', 'hilo-app-punto'); p.dataset.nivel = a.nivel;
      t.append(p, el('b', '', a.titulo));
      b.append(t, el('small', '', a.detalle));
      if (a.tiendas && a.tiendas.length) {
        const ch = el('div', 'hilo-etiquetas');
        a.tiendas.forEach(x => ch.append(el('span', '', x)));
        b.append(ch);
      }
      cuerpo.append(b);
    });
    return c;
  },

  felicitar(A) {
    if (!A) return null;
    const f = A.felicitar;
    const { c, cuerpo } = tarjeta('¿A quién felicitar?', f.referencia ? `Mejora frente al corte del día ${f.referencia}` : 'Las que van por encima de la meta', 'bi-award');
    const todas = [];
    f.mejoras.forEach(x => todas.push({ x, detalle: `Subió de ${pct(x.antes)} a ${pct(x.ahora)}`, texto: `¡Felicitaciones, ${x.nombre}! Pasaron de ${Math.round(x.antes * 100)} % a ${Math.round(x.ahora * 100)} % de cumplimiento. ¡Sigan con ese ritmo!` }));
    f.arriba.forEach(x => { if (!todas.some(t => t.x.store_id === x.store_id)) todas.push({ x, detalle: `Va en ${pct(x.ahora)}`, texto: `¡${x.nombre}, van por encima de la meta con ${Math.round(x.ahora * 100)} %! Gracias por el esfuerzo de todo el equipo.` }); });
    if (!todas.length) { cuerpo.append(el('p', 'hilo-texto', 'Todavía no hay tiendas por encima de la meta ni mejoras fuertes en la semana.')); return c; }
    todas.slice(0, 6).forEach(({ x, detalle, texto }) => {
      const b = el('div', 'hilo-felicitar');
      const t = el('div', 'hilo-diag-cab');
      t.append(el('b', '', x.nombre), el('span', 'bueno', x.codigo));
      b.append(t, el('small', 'hilo-nota', detalle), redactor({ texto, tono: 'celebra', tiendas: [x.store_id], etiqueta: 'Felicitar con Hilo' }));
      cuerpo.append(b);
    });
    return c;
  },

  v3(A) {
    if (!A) return null;
    const v = A.v3;
    const { c, cuerpo } = tarjeta('Pronóstico V3 vs. real', v ? `Corrida del ${v.corrida}` : 'Pronóstico de ventas V3', 'bi-stars');
    if (!v) { cuerpo.append(el('p', 'hilo-texto', `No hay una corrida del pronóstico V3 para ${A.corte.nombre_mes}.`)); return c; }
    const g = el('div', 'hilo-grande');
    g.append(el('b', '', signo(v.diferencia)), el('span', '', `V3 esperaba ${dinero(v.p50)}; al ritmo de hoy van para ${dinero(v.proyeccion)}`));
    cuerpo.append(g);
    const abajo = v.tiendas.filter(t => t.diferencia < -0.03).slice(0, 5);
    const arriba = v.tiendas.filter(t => t.diferencia > 0.03).slice(-4).reverse();
    if (abajo.length) {
      cuerpo.append(el('p', 'hilo-subtitulo', 'Van por debajo de lo que esperaba V3'));
      cuerpo.append(lista(abajo.map(t => item(t.nombre, `V3: ${dinero(t.p50)} · ritmo: ${dinero(t.proyeccion)}${t.fuera === 'abajo' ? ' · fuera del rango P10' : ''}`, t.fuera ? 'alto' : 'medio', el('b', 'hilo-lista-valor malo', signo(t.diferencia))))));
    }
    if (arriba.length) {
      cuerpo.append(el('p', 'hilo-subtitulo', 'Van mejor de lo esperado'));
      cuerpo.append(lista(arriba.map(t => item(t.nombre, `V3: ${dinero(t.p50)} · ritmo: ${dinero(t.proyeccion)}`, 'ok', el('b', 'hilo-lista-valor bueno', signo(t.diferencia))))));
    }
    return c;
  },

  cambios(A) {
    if (!A) return null;
    const { c, cuerpo } = tarjeta('Cambios bruscos', 'El último día frente al mismo día de las semanas anteriores', 'bi-activity');
    if (!A.cambios.length) { cuerpo.append(el('p', 'hilo-ok', 'Nada raro: todas vendieron parecido a un día normal.')); return c; }
    cuerpo.append(lista(A.cambios.map(x => {
      const li = item(x.nombre, `El ${x.nombre_dia} ${x.dia} vendió ${dinero(x.venta)}; un ${x.nombre_dia} normal es ${dinero(x.promedio)}`, x.variacion < 0 ? 'alto' : 'ok', el('b', 'hilo-lista-valor ' + (x.variacion < 0 ? 'malo' : 'bueno'), signo(x.variacion)));
      if (x.url) li.append(enlace('', x.url, 'bi-box-arrow-up-right'));
      return li;
    })));
    return c;
  },

  sugeridos(A) {
    if (!A) return null;
    const { c, cuerpo } = tarjeta('Mensajes sugeridos', 'Listos para enviar con Hilo', 'bi-chat-heart');
    if (!A.sugeridos.length) { cuerpo.append(el('p', 'hilo-texto', 'Hoy no tengo sugerencias.')); return c; }
    A.sugeridos.forEach(s => {
      const b = el('div', 'hilo-felicitar');
      b.append(el('small', 'hilo-nota', s.motivo), el('p', 'hilo-texto', `«${s.texto}»`), redactor({ texto: s.texto, tono: s.tono, tiendas: s.tiendas, etiqueta: 'Revisar y enviar' }));
      cuerpo.append(b);
    });
    cuerpo.append(enlace('Ir a Mensajes con Hilo', '/admin/mensajes-hilo', 'bi-box-arrow-up-right'));
    return c;
  },

  red(A) {
    const r = A && A.red_tejida;
    if (!r || !r.total) return null;
    const { c, cuerpo } = tarjeta('La red tejida', 'Tiendas que pasaron su meta, unidas por un hilo dorado', 'bi-diagram-3');
    const g = el('div', 'hilo-grande');
    g.append(el('b', '', `${r.unidas} de ${r.total}`), el('span', '', r.hace_una_semana != null ? `Hace una semana eran ${r.hace_una_semana}` : 'tiendas en el hilo'));
    const b = barra(r.unidas / r.total);
    b.firstChild.dataset.nivel = 'oro';  // la red tejida siempre en dorado
    cuerpo.append(g, b);
    if (r.nuevas.length) cuerpo.append(el('p', 'hilo-ok', `Se unieron en el último corte: ${unir(r.nuevas)}.`));
    if (r.orden.length) cuerpo.append(lista(r.orden.slice(0, 8).map((t, i) => item(`${i + 1}. ${t.nombre}`, `${t.ciudad || ''} · ${pct(t.cump)} · desde el corte ${t.dia}`, 'ok'))));
    const q = new URLSearchParams({ periodo: `${A.corte.anio}-${String(A.corte.mes).padStart(2, '0')}-${String(A.corte.dia).padStart(2, '0')}` });
    cuerpo.append(enlace('Ver el hilo en el mapa', `/dashboard/geografico-v2?${q}#hilo`, 'bi-map'));
    return c;
  },

  reporte(A) {
    if (!A) return null;
    const q = new URLSearchParams({ anio: A.corte.anio, mes: A.corte.mes, dia_corte: A.corte.dia });
    const s = A.semana || {};
    const { c, cuerpo } = tarjeta('Informe semanal', `Del ${s.desde || ''} al ${s.hasta || ''}`, 'bi-file-earmark-bar-graph');
    if (s.actual != null) {
      cuerpo.append(fila('Venta de los últimos 7 días', dinero(s.actual)));
      if (s.variacion != null) cuerpo.append(fila('Frente a la semana anterior', signo(s.variacion), s.variacion < 0 ? 'alerta' : 'bien'));
    }
    cuerpo.append(el('p', 'hilo-texto', 'Resumen para gerencia: red, proyección, tiendas, causas, calidad de datos, uso de L&H Pulse y pronóstico V3.'));
    const acciones = el('div', 'hilo-acciones');
    acciones.append(enlace('Descargar Excel', `/hilo/reporte-semanal.xlsx?${q}`, 'bi-file-earmark-excel'), enlace('Ver para imprimir o PDF', `/hilo/reporte-semanal?${q}`, 'bi-printer', true));
    cuerpo.append(acciones);
    return c;
  },
};
function tip(texto) {
  const t = el('div', 'hilo-ayuda-tip');
  t.append(el('i', 'bi bi-lightbulb'), el('span', '', texto));
  return t;
}

/* ---------- Pregúntale a Hilo ---------- */
const normal = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[¿?¡!.,;:"'()]/g, ' ').replace(/\s+/g, ' ').trim();
const tiene = (q, re) => re.test(q);

export function responder(pregunta, ctx) {
  const q = normal(pregunta);
  if (!q) return null;
  if (tiene(q, /^(hola|buen(a|o)s?|hey|que mas|saludos)\b/)) return { texto: `¡Hola${ctx.nombre ? ', ' + ctx.nombre : ''}! Pregúntame lo que quieras de ${ctx.tipo === 'admin' ? 'la red' : 'la tienda'}.`, nodo: T.preguntas(ctx.tipo, ctx.preguntar), pose: 'saluda' };
  if (tiene(q, /\b(gracias|listo|perfecto|genial|chevere|bacano)\b/)) return { texto: '¡Con gusto! Aquí estoy cuando me necesites.', pose: 'feliz' };
  if (tiene(q, /\b(ayuda|que (puedo|te puedo) preguntar|que sabes|que haces)\b/)) return { texto: 'Esto es lo que más me preguntan:', nodo: T.preguntas(ctx.tipo, ctx.preguntar), pose: 'explica' };
  const r = ctx.tipo === 'admin' ? responderAdmin(q, ctx) : responderTienda(q, ctx);
  if (r) return r;
  return {
    texto: 'Mmm, esa no me la sé todavía. Prueba con una de estas:',
    nodo: T.preguntas(ctx.tipo, ctx.preguntar), pose: 'enredado'
  };
}

function glosario(q, ctx) {
  if (!tiene(q, /\b(que es|que son|que significa|para que sirve|explica|explicame|como se calcula)\b/)) return null;
  const item = (ctx.ayuda || []).find(a => a.claves.some(c => q.includes(normal(c))) || q.includes(normal(a.titulo)));
  if (!item) return null;
  const tipTexto = typeof item.tip === 'function' ? (ctx.D ? item.tip(ctx.D) : '') : item.tip;
  return { texto: `${item.titulo}: ${item.que}${tipTexto ? ' ' + tipTexto : ''}`, pose: 'explica' };
}

function responderTienda(q, ctx) {
  const { D, S, P } = ctx;
  const g = glosario(q, ctx);
  if (g) return g;
  const pr = S && S.proyeccion;

  // Una asesora por su nombre
  const asesoras = (D.asesoras || []).filter(a => !a.generico);
  const palabras = q.split(' ');
  const nombrada = asesoras.find(a => { const n = normal(primerNombre(a.nombre)); return n.length >= 3 && palabras.includes(n); });
  if (nombrada && !tiene(q, /\b(mejor|primera|ranking)\b/)) {
    const meta = num(nombrada.meta), venta = num(nombrada.venta);
    const hoy = (P.metaHoy && P.metaHoy.asesoras.find(a => a.nombre === nombrada.nombre)) || null;
    let texto = `${cap(nombrada.nombre.toLowerCase())} lleva ${dinero(venta)}`;
    if (meta > 0) texto += ` de ${dinero(meta)} (${pct(venta / meta)} de su meta del mes)`;
    else texto += ' y no tiene meta: está como auxiliar o falta repartir la meta';
    if (hoy) texto += hoy.cumplida ? '. ¡Ya cumplió su meta! 🎉' : `. Hoy debería vender ${dinero(hoy.hoy)}.`;
    else texto += '.';
    return { texto, pose: meta > 0 && venta >= meta ? 'aplaude' : 'explica' };
  }

  if (tiene(q, /\b(cierr|cerra|proyecc|proyect|terminar|fin de mes|final del mes|como vamos a (cerrar|terminar)|si seguimos)/)) {
    if (!pr) return { texto: 'Todavía no tengo cómo proyectar el cierre: falta la meta o la venta del mes.', pose: 'enredado' };
    return { texto: pr.cerrado ? `El mes cerró en ${pct(pr.pct)}.` : `Si siguen así, cierran el mes en ${pct(pr.pct)} (unos ${dinero(pr.valor)}).${pr.falta > 0 ? ` Para el 100 % necesitan ${dinero(pr.necesita_dia)} por día.` : ''}`, nodo: T.proyeccion(S), pose: pr.pct >= 1 ? 'feliz' : 'concentra' };
  }
  if (tiene(q, /\b(reto)\b/)) {
    const reto = retoDelDia(D, S);
    return { texto: reto ? `El reto de hoy: ${reto.texto.toLowerCase()}.` : 'Hoy no tengo reto: ¡van muy bien en todo!', nodo: T.reto(reto, null), pose: 'animo' };
  }
  if (tiene(q, /\b(hoy|por dia|diari|cada dia|al dia)\b/) && tiene(q, /\b(vend|meta|necesit|debo|debemos|toca)/)) {
    const M = P.metaHoy;
    if (M) return { texto: M.tienda > 0 ? `Hoy la tienda necesita ${dinero(M.tienda)}. Te muestro lo de cada asesora.` : '¡La meta del mes ya está cumplida!', abrir: 'metaHoy', pose: 'explica' };
    if (pr && pr.falta > 0 && !pr.cerrado) return { texto: `Para llegar al 100 % necesitan ${dinero(pr.necesita_dia)} por día en los ${pr.dias_restantes} días que quedan.`, nodo: T.proyeccion(S), pose: 'explica' };
    return { texto: num(D.falta) > 0 ? `Faltan ${dinero(D.falta)} para la meta.` : '¡La meta del mes ya está cumplida!', pose: 'explica' };
  }
  if (tiene(q, /\b(falta|faltan|nos falta|cuanto queda)\b/)) {
    return { texto: num(D.falta) > 0 ? `Faltan ${dinero(D.falta)} para la meta del mes.${pr && !pr.cerrado && pr.dias_restantes ? ` Son ${dinero(pr.necesita_dia)} por día.` : ''}` : '¡No falta nada: la meta del mes está cumplida! 🎉', pose: num(D.falta) > 0 ? 'concentra' : 'feliz' };
  }
  if (tiene(q, /\b(mejor asesora|quien va (primera|primero|ganando|de primera)|primera|ranking|lider|quien vende mas|quien va mejor)\b/)) {
    const orden = asesoras.filter(a => num(a.meta) > 0).sort((a, b) => num(b.cump) - num(a.cump));
    if (!orden.length) return { texto: 'Todavía no hay asesoras con meta para comparar.', pose: 'enredado' };
    const top = orden.slice(0, 3).map((a, i) => `${i + 1}. ${primerNombre(a.nombre)} (${pct(a.cump)})`).join(' · ');
    return { texto: `Van primeras: ${top}.`, pose: 'aplaude' };
  }
  if (tiene(q, /\b(hora|horas|horario|mas gente|cuando entra|trafico|personas|entran)\b/)) {
    const cv = S && S.conversion;
    if (!cv || !(cv.horas || []).length) return { texto: 'No tengo el tráfico por hora de esta tienda.', pose: 'enredado' };
    const top = cv.horas.slice().sort((a, b) => b.por_dia - a.por_dia).slice(0, 3).sort((a, b) => a.hora - b.hora);
    return { texto: `Entra más gente a las ${unir(top.map(h => hora(h.hora)))}. Ahí es cuando más asesoras deben estar en piso.`, nodo: T.coach(S), pose: 'senala' };
  }
  if (tiene(q, /\b(conversion|conviert|compran|facturas que faltan|venta perdida|dejamos de vender|se deja de)/)) {
    const cv = S && S.conversion;
    if (!cv || !cv.trafico) return { texto: 'No tengo datos de tráfico para calcular la conversión.', pose: 'enredado' };
    return { texto: `De cada 100 personas que entran, compran ${Math.round((cv.conversion || 0) * 100)}.${cv.facturas_faltan > 0 ? ` Con 20 habrían hecho ${miles(cv.facturas_faltan)} facturas más: unos ${dinero(cv.venta_perdida)}.` : ' ¡Están por encima del 20 %!'}`, nodo: T.coach(S), pose: 'explica' };
  }
  if (tiene(q, /\b(ticket|tiquete|vpt|valor por)\b/)) return { texto: `El tiquete promedio va en ${dinero(D.ticket)}${num(D.meta_vpt) > 0 ? ` y la meta mínima es ${dinero(D.meta_vpt)}` : ''}.${num(D.vpt_anterior) > 0 ? ` El año pasado era ${dinero(D.vpt_anterior)}.` : ''}`, pose: 'explica' };
  if (tiene(q, /\b(upt|unidades por|prendas por)\b/)) return { texto: `Cada cliente lleva en promedio ${num(D.upt).toFixed(2).replace('.', ',')} prendas por compra.`, pose: 'explica' };
  if (tiene(q, /\b(ano pasado|ano anterior|crec|vs|frente al ano|comparado con el ano)\b/)) {
    if (!S || !S.venta_anterior) return { texto: 'No tengo la venta del año anterior de este período.', pose: 'enredado' };
    const v = S.venta / S.venta_anterior - 1;
    return { texto: `Van ${v >= 0 ? 'arriba' : 'abajo'} ${pct(Math.abs(v))} frente al año pasado (${dinero(S.venta)} contra ${dinero(S.venta_anterior)}).`, pose: v >= 0 ? 'feliz' : 'concentra' };
  }
  if (tiene(q, /\b(puesto|posicion|clima|otras tiendas|comparacion|comparar|como vamos frente)\b/)) {
    const cp = S && S.comparacion;
    if (!cp) return { texto: 'No tengo el clima de la tienda para compararla.', pose: 'enredado' };
    return { texto: `Entre las ${cp.total} tiendas de clima ${cp.clima} van en el puesto ${cp.puesto}.`, nodo: T.comparacion(S), pose: cp.puesto <= 3 ? 'aplaude' : 'animo' };
  }
  if (tiene(q, /\b(racha|record|mejor dia)\b/)) {
    const c = S && S.celebra;
    if (!c || !c.mejor_dia) return { texto: 'Todavía no tengo ventas diarias de este mes.', pose: 'enredado' };
    return { texto: `El mejor día del mes fue el ${c.mejor_dia.nombre} ${c.mejor_dia.dia} con ${dinero(c.mejor_dia.venta)}.${c.racha >= 2 ? ` Llevan ${c.racha} días seguidos por encima de la meta del día.` : ''}`, pose: 'feliz' };
  }
  if (tiene(q, /\b(auxiliar|distribu|de planta|reparte|repartir|meta de cada|meta de las asesoras)/)) return { texto: 'Así se reparte la meta entre las asesoras de planta:', nodo: T.metaDistribuible(S), pose: 'explica' };
  if (tiene(q, /\b(linea|lineas|categoria)\b/) || (D.lineas || []).some(l => q.includes(normal(l.linea)))) {
    const linea = (D.lineas || []).find(l => q.includes(normal(l.linea)));
    if (linea) return { texto: `La línea ${linea.linea} lleva ${dinero(linea.venta)}${num(linea.meta) > 0 ? ` de ${dinero(linea.meta)} (${pct(linea.cump)})` : ''}.`, pose: 'explica' };
    const bajas = (D.lineas || []).filter(l => num(l.meta) > 0).sort((a, b) => num(a.cump) - num(b.cump)).slice(0, 3);
    return { texto: bajas.length ? `Las líneas más bajas: ${bajas.map(l => `${l.linea} (${pct(l.cump)})`).join(', ')}.` : 'No hay metas por línea este mes.', pose: 'explica' };
  }
  if (tiene(q, /\b(revisar|alerta|problema|que hago|consejo|mejorar|que debemos)\b/)) return { texto: P.avisos.length ? 'Esto es lo que yo revisaría:' : 'No veo nada urgente. ¡Van bien!', abrir: P.avisos.length ? 'avisos' : null, pose: 'senala' };
  if (tiene(q, /\b(tv|television|pantalla|televisor)\b/)) return { texto: 'El Modo TV muestra los resultados en grande para la pantalla de la tienda.', nodo: (() => { const d = el('div'); d.append(enlace('Abrir Modo TV', ctx.urlTV, 'bi-tv', true)); return d; })(), pose: 'senala' };
  if (tiene(q, /\b(como vamos|como va|cumplimiento|vamos bien|porcentaje|meta)\b/)) {
    const c = num(D.cumplimiento);
    return { texto: `Van en ${pct(c)} de la meta al corte del día ${D.dia_corte}.${num(D.falta) > 0 ? ` Faltan ${dinero(D.falta)} para el mes.` : ' ¡Meta del mes cumplida!'}`, pose: c >= 1 ? 'feliz' : c >= 0.9 ? 'animo' : 'concentra' };
  }
  if (tiene(q, /\b(vend|venta|ventas|llevamos)\b/)) return { texto: `Llevan ${dinero(D.ventas)} vendidos en el mes, unos ${dinero(D.venta_dia)} por día.`, pose: 'explica' };
  return null;
}

function responderAdmin(q, ctx) {
  const A = ctx.A;
  if (!A) return { texto: 'Todavía estoy cargando los datos de la red. Pregúntame en un momento.', pose: 'carga' };
  const g = glosario(q, ctx);
  if (g) return g;
  // Una tienda por código o nombre
  const tienda = A.tiendas.find(t => {
    const cod = normal(t.codigo), sin = cod.replace(/[^a-z0-9]/g, '');
    return q.includes(cod) || q.split(' ').includes(sin) || (normal(t.nombre).length >= 4 && q.includes(normal(t.nombre)));
  });
  if (tienda && !tiene(q, /\b(felicit)/)) {
    const d = A.diagnostico.find(x => x.store_id === tienda.store_id);
    const causas = { trafico: 'entra menos gente', conversion: 'compra menos gente de la que entra', ticket: 'cada compra vale menos' };
    let texto = `${tienda.nombre} va en ${pct(tienda.cump)} al corte`;
    if (tienda.proy_pct != null && !A.red.cerrado) texto += ` y proyecta cerrar en ${pct(tienda.proy_pct)}`;
    texto += '.';
    if (tienda.crecimiento != null) texto += ` Frente al año pasado: ${signo(tienda.crecimiento)}.`;
    if (d && d.crecimiento < 0 && d.causa) texto += ` La causa principal es que ${causas[d.causa]} (tráfico ${signo(d.trafico)}, conversión ${signo(d.conversion)}, tiquete ${signo(d.ticket)}).`;
    const nodo = el('div');
    if (tienda.url) nodo.append(enlace(`Abrir ${tienda.codigo}`, tienda.url, 'bi-box-arrow-up-right'));
    return { texto, nodo, pose: tienda.cump >= 1 ? 'feliz' : 'explica' };
  }
  if (tiene(q, /\b(riesgo|bajas|peor|peores|rojo|no van a llegar|preocup|atrasad)/)) return { texto: A.riesgo.length ? `${A.riesgo.length} ${A.riesgo.length === 1 ? 'tienda proyecta' : 'tiendas proyectan'} cerrar por debajo del 95 %.` : 'Ninguna tienda proyecta cerrar por debajo del 95 %.', nodo: T.riesgo(A), pose: A.riesgo.length ? 'concentra' : 'feliz' };
  if (tiene(q, /\b(por que|causa|diagnost|bajan|bajo|bajaron)\b/)) return { texto: 'Separé la venta en tráfico, conversión y tiquete frente al año pasado:', nodo: T.diagnostico(A), pose: 'explica' };
  if (tiene(q, /\b(no (ha|han)? ?entra|no entran|uso|usan|acceso|ingres|conect|entrado)/)) return { texto: (A.sin_uso.tiendas || []).length ? `${A.sin_uso.tiendas.length} ${A.sin_uso.tiendas.length === 1 ? 'tienda lleva' : 'tiendas llevan'} 3 días o más sin entrar.` : '¡Todas las tiendas entraron en los últimos 3 días!', nodo: T.sinUso(A), pose: 'senala' };
  if (tiene(q, /\b(calidad|datos|carga|cargas|atras|cero|sin meta)\b/)) return { texto: A.calidad.length ? `Encontré ${A.calidad.length} ${A.calidad.length === 1 ? 'cosa' : 'cosas'} en los datos:` : 'Los datos están en orden.', nodo: T.calidad(A), pose: A.calidad.length ? 'senala' : 'feliz' };
  if (tiene(q, /\b(felicit|mejora|mejoraron|subieron|destac|premiar)/)) return { texto: 'Estas tiendas merecen un aplauso:', nodo: T.felicitar(A), pose: 'aplaude' };
  if (tiene(q, /\b(pronost|v3|ia|inteligencia|modelo)\b/)) return { texto: A.v3 ? `Al ritmo de hoy la red va ${signo(A.v3.diferencia)} frente a lo que esperaba V3.` : 'No hay corrida del pronóstico V3 para este mes.', nodo: T.v3(A), pose: 'explica' };
  if (tiene(q, /\b(cambio|cambios|caida|cayo|brusc|raro|anormal|subida)\b/)) return { texto: A.cambios.length ? `Hubo ${A.cambios.length} ${A.cambios.length === 1 ? 'cambio brusco' : 'cambios bruscos'} en el último día.` : 'Nada raro en el último día.', nodo: T.cambios(A), pose: 'senala' };
  if (tiene(q, /\b(hilo de la red|red tejida|tejid|hilo dorado|cuantas (tiendas )?(pasaron|cumplieron)|cuantas van sobre la meta)/) && A.red_tejida) return { texto: `${A.red_tejida.unidas} de ${A.red_tejida.total} tiendas ya pasaron su meta y están en el hilo de la red.`, nodo: T.red(A), pose: 'aplaude' };
  if (tiene(q, /\b(reporte|informe|excel|pdf|gerencia|semana|semanal)\b/)) return { texto: 'Aquí está el informe semanal:', nodo: T.reporte(A), pose: 'explica' };
  if (tiene(q, /\b(mensaje|mensajes|sugier|sugerencia|enviar|escribir)\b/)) return { texto: 'Te dejo mensajes listos para enviar:', nodo: T.sugeridos(A), pose: 'explica' };
  if (tiene(q, /\b(cierr|cerra|proyecc|proyect|fin de mes|terminar)/)) return { texto: A.red.cerrado ? `El mes cerró en ${pct(A.red.cump)}.` : `Al ritmo de hoy la red cierra en ${pct(A.red.proy_pct)} (${dinero(A.red.proyeccion)} de ${dinero(A.red.cuota_total)}).`, nodo: T.resumen(A), pose: 'explica' };
  if (tiene(q, /\b(mejor|primera|primer lugar|lider|ranking|top)\b/)) {
    const top = A.tiendas.slice(0, 3).map((t, i) => `${i + 1}. ${t.nombre} (${pct(t.cump)})`).join(' · ');
    return { texto: `Van primeras: ${top}.`, pose: 'aplaude' };
  }
  if (tiene(q, /\b(como va|como vamos|red|resumen|total|todas|general)\b/)) return { texto: `La red va en ${pct(A.red.cump)} al corte del día ${A.corte.dia}, con ${A.red.al_dia} de ${A.red.tiendas} tiendas al día.`, nodo: T.resumen(A), pose: A.red.cump >= 1 ? 'feliz' : 'explica' };
  return null;
}

/* ---------- Voz (opcional, con la voz del navegador) ---------- */
const CLAVE_VOZ = 'lhpulse-hilo-voz';
let vozElegida = null;
export const voz = {
  disponible: () => 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined',
  activa: () => leer(localStorage, CLAVE_VOZ) === '1',
  poner(on) {
    guardar(localStorage, CLAVE_VOZ, on ? '1' : '0');
    if (!on && voz.disponible()) speechSynthesis.cancel();
  },
  decir(texto) {
    if (!texto || !voz.activa() || !voz.disponible()) return;
    const limpio = String(texto)
      .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '')
      .replace(/\$\s?([\d,]+)/g, (_, n) => n.replace(/,/g, '') + ' pesos')
      .replace(/(\d+)\.(\d)%/g, '$1 coma $2 por ciento')
      .replace(/%/g, ' por ciento')
      .replace(/L&H/g, 'Ele y Hache');
    const u = new SpeechSynthesisUtterance(limpio);
    u.lang = 'es-CO';
    const v = elegirVoz();
    if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = 1.02; u.pitch = 1.08;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  },
};
function elegirVoz() {
  if (vozElegida) return vozElegida;
  const voces = (speechSynthesis.getVoices() || []).filter(v => /^es/i.test(v.lang));
  if (!voces.length) return null;
  const puntos = v => (/natural|online|neural/i.test(v.name) ? 4 : 0) + (/es-CO/i.test(v.lang) ? 3 : /es-(MX|US|419)/i.test(v.lang) ? 2 : 1)
    + (/gonzalo|jorge|alvaro|pablo|raul|carlos|emilio|andres|diego|male/i.test(v.name) ? 1 : 0);
  vozElegida = voces.sort((a, b) => puntos(b) - puntos(a))[0];
  return vozElegida;
}
if ('speechSynthesis' in window) speechSynthesis.addEventListener?.('voiceschanged', () => { vozElegida = null; });

/* ---------- Utilidades ---------- */
const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
export function el(tag, clase, texto) {
  const n = document.createElement(tag);
  if (clase) n.className = clase;
  if (texto != null) n.textContent = texto;
  return n;
}
function num(v) { const n = parseFloat(v); return isFinite(n) ? n : 0; }
export function pct(v) { return v == null ? '—' : (num(v) * 100).toFixed(1) + '%'; }
function signo(v) { return v == null ? '—' : (v >= 0 ? '+' : '−') + (Math.abs(num(v)) * 100).toFixed(1) + '%'; }
export function dinero(v) { return '$' + new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Math.max(0, Math.round(num(v)))); }
function miles(v) { return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Math.round(num(v))); }
function primerNombre(n) { const t = String(n || '').trim().split(/\s+/)[0] || ''; return t.charAt(0) + t.slice(1).toLowerCase(); }
function cap(s) { s = String(s || ''); return s.charAt(0).toUpperCase() + s.slice(1); }
function unir(lista) { return lista.length <= 1 ? (lista[0] || '') : lista.slice(0, -1).join(', ') + ' y ' + lista[lista.length - 1]; }
function hora(h) { return h === 12 ? '12 m.' : h > 12 ? `${h - 12} p. m.` : `${h} a. m.`; }
function fechaISO(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function fechaLarga(d) { return `${cap(DIAS[d.getDay()])} ${d.getDate()}`; }
function leer(almacen, k) { try { return almacen.getItem(k); } catch (e) { return null; } }
function guardar(almacen, k, v) { try { almacen.setItem(k, v); } catch (e) { /* sin almacenamiento */ } }
function leerJSON(almacen, k, defecto) { try { const v = JSON.parse(leer(almacen, k)); return v == null ? defecto : v; } catch (e) { return defecto; } }
