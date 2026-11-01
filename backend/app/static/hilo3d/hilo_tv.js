/* ================================================================
   Modo TV: los resultados de la tienda en grande para la pantalla,
   con Hilo comentando cada lámina. Se actualiza solo cada 10 minutos.
   ================================================================ */
import { retoDelDia } from './hilo_saber.js?v=2';

const raiz = document.getElementById('tv');
const escena = document.getElementById('tvEscena');
const puntos = document.getElementById('tvPuntos');
const globo = document.getElementById('tvGlobo');
const storeId = raiz.dataset.store;
const SEGUNDOS = 14;
let laminas = [], actual = 0, temporizador = 0, hilo = null, retos = null;

/* ---------- Reloj ---------- */
const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
function reloj() {
  const d = new Date();
  document.getElementById('tvHora').textContent = d.toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
  document.getElementById('tvFecha').textContent = `${DIAS[d.getDay()]} ${d.getDate()} de ${MESES[d.getMonth()]}`;
}
reloj(); setInterval(reloj, 20000);

/* ---------- Hilo ---------- */
(async () => {
  try {
    const motor = await import('./hilo_motor.js');
    if (!motor.hayWebGL()) return;
    const caja = document.getElementById('tvHilo');
    const r = caja.getBoundingClientRect();
    hilo = motor.crearHilo({
      ancho: Math.round(r.width) || 300, alto: Math.round(r.height) || 280, quieto: motor.prefiereQuieto(),
      pasear: false, ideas: 'pocas', fps: 30, maxPixelRatio: 1.5, temporada: motor.temporadaActual(), sueno: 0
    });
    caja.append(hilo.canvas);
    hilo.poner('saluda');
  } catch (e) { /* sin 3D: el Modo TV funciona igual */ }
})();
function decir(texto, pose) {
  if (pose && hilo) hilo.poner(pose);
  globo.classList.remove('visible');
  if (!texto) return;
  setTimeout(() => { globo.textContent = texto; globo.classList.add('visible'); }, 250);
  setTimeout(() => globo.classList.remove('visible'), (SEGUNDOS - 3) * 1000);
}

/* ---------- Datos ---------- */
async function cargar() {
  try {
    const r = await fetch('/api/hilo/tienda' + (storeId ? `?store_id=${encodeURIComponent(storeId)}` : ''), { credentials: 'same-origin' });
    if (r.status === 401) { location.href = '/'; return; }
    const S = await r.json();
    if (!S || !S.ok) { mostrarVacio('Todavía no hay resultados para mostrar.'); return; }
    // Retos de la semana (batalla, récords, hora dorada); si no están, el Modo TV sigue igual
    retos = await fetch('/api/retos/tienda' + (storeId ? `?store_id=${encodeURIComponent(storeId)}` : ''), { credentials: 'same-origin' })
      .then(x => x.json()).catch(() => null);
    armar(S);
  } catch (e) { /* sin conexión: se queda con lo último */ }
}
function mostrarVacio(texto) {
  escena.replaceChildren(lamina([el('p', 'tv-vacio', texto)]));
  escena.firstChild.classList.add('activa');
}

function armar(S) {
  document.getElementById('tvCorte').textContent = `Datos al ${S.corte.dia} de ${S.corte.nombre_mes} de ${S.corte.anio}`;
  const L = [];
  const pr = S.proyeccion;
  const cump = S.cumplimiento;

  // 1. Cumplimiento
  L.push({
    nodos: [
      el('span', 'tv-etiqueta', 'Cumplimiento de la meta al corte'),
      el('div', 'tv-gigante', pct(cump)),
      barra(cump),
      datos([
        ['Ventas del mes', dinero(S.venta)],
        [S.cuota_total > S.venta ? 'Falta para la meta' : 'Meta del mes', S.cuota_total > S.venta ? dinero(S.cuota_total - S.venta) : '¡Cumplida! 🎉'],
        [pr && !pr.cerrado ? 'Si seguimos así cerramos en' : 'Cerramos en', pr ? pct(pr.pct) : '—'],
      ])
    ],
    hilo: [cump >= 1 ? '¡Vamos por encima de la meta! 🎉' : cump >= 0.9 ? '¡Ya casi! Cada venta cuenta.' : '¡Vamos, equipo! Todavía hay tiempo.', cump >= 1 ? 'feliz' : cump >= 0.9 ? 'animo' : 'concentra']
  });

  // 2. Meta de hoy (mes en curso) o plan de los próximos días
  const hoy = new Date();
  const enCurso = S.corte.anio === hoy.getFullYear() && S.corte.mes === hoy.getMonth() + 1 && pr && !pr.cerrado;
  if (enCurso) {
    const dias = Math.max(1, S.corte.dias_mes - Math.max(S.corte.dia, hoy.getDate() - 1));
    const lista = S.asesoras.filter(a => a.meta > 0).map(a => {
      const falta = Math.max(0, a.meta - a.venta);
      return { nombre: a.nombre, hoy: falta / dias, cumplida: falta <= 0 };
    }).sort((x, y) => (x.cumplida - y.cumplida) || (y.hoy - x.hoy)).slice(0, 7);
    if (lista.length) L.push({
      nodos: [
        el('span', 'tv-etiqueta', 'Meta de hoy'),
        el('h2', 'tv-titulo', `La tienda necesita ${dinero(pr.falta / dias)} hoy`),
        ul(lista.map((a, i) => [String(i + 1), nombre(a.nombre), a.cumplida ? '✓ Cumplió' : dinero(a.hoy), a.cumplida ? 'ok' : '']))
      ],
      hilo: ['Esta es la meta de hoy para cada una. ¡A vender!', 'explica']
    });
  } else if (pr && !pr.cerrado && pr.plan.length) {
    L.push({
      nodos: [
        el('span', 'tv-etiqueta', 'Plan para cerrar el mes'),
        el('h2', 'tv-titulo', `${dinero(pr.necesita_dia)} por día para llegar al 100 %`),
        ul(pr.plan.slice(0, 6).map(p => [String(p.dia), cap(p.nombre), dinero(p.valor), '']))
      ],
      hilo: ['Así repartimos lo que falta en los próximos días.', 'explica']
    });
  }

  // 3. Asesoras
  const conMeta = S.asesoras.filter(a => a.cump != null).slice(0, 7);
  if (conMeta.length) L.push({
    nodos: [
      el('span', 'tv-etiqueta', 'Cumplimiento por asesora'),
      el('h2', 'tv-titulo', 'Así va el equipo'),
      ul(conMeta.map((a, i) => [String(i + 1), nombre(a.nombre), pct(a.cump), a.cump >= 1 ? 'ok' : '']))
    ],
    hilo: [`¡Aplausos para ${nombre(conMeta[0].nombre).split(' ')[0]}! 👏`, 'aplaude']
  });

  // 4. Reto del día y conversión
  const reto = retoDelDia({}, S);
  const cv = S.conversion || {};
  if (reto || cv.trafico) L.push({
    nodos: [
      el('span', 'tv-etiqueta', 'Reto del día'),
      reto ? (() => { const r = el('div', 'tv-reto'); r.append(el('i', `bi ${reto.icono || 'bi-lightning-charge'}`), document.createTextNode(reto.texto)); return r; })() : el('h2', 'tv-titulo', '¡Sigamos así!'),
      cv.trafico ? datos([
        ['De cada 100 personas que entran compran', String(Math.round((cv.conversion || 0) * 100))],
        ['Personas al día', miles(cv.trafico_dia || 0)],
        ['Facturas que faltaron para el 20 %', miles(cv.facturas_faltan || 0)],
      ]) : el('span')
    ],
    hilo: ['Saluden a cada persona que entra y acompáñenla al probador.', 'animo']
  });

  // 5. Tiendas del mismo clima
  const cp = S.comparacion;
  if (cp && cp.total > 1) L.push({
    nodos: [
      el('span', 'tv-etiqueta', `Tiendas de clima ${cp.clima}`),
      el('h2', 'tv-titulo', `Vamos ${cp.puesto}° de ${cp.total}`),
      ul(cp.tiendas.slice(0, 7).map((t, i) => [String(i + 1), t.nombre, pct(t.cump), t.mia ? 'mia' : '']))
    ],
    hilo: [cp.puesto === 1 ? '¡Somos la primera de nuestro grupo! 🏆' : `Vamos ${cp.puesto}° entre las tiendas de clima ${cp.clima}.`, cp.puesto <= 3 ? 'aplaude' : 'animo']
  });

  // 6. Celebraciones
  const cien = S.asesoras.filter(a => a.meta > 0 && a.venta >= a.meta);
  const c = S.celebra || {};
  if (cien.length || c.racha >= 3 || c.record) {
    const frases = [];
    if (cien.length) frases.push(`${unir(cien.map(a => nombre(a.nombre).split(' ')[0]))} ${cien.length === 1 ? 'ya pasó' : 'ya pasaron'} el 100 % de su meta`);
    if (c.record) frases.push(`Récord del mes: ${dinero(c.record.venta)} el día ${c.record.dia}`);
    if (c.racha >= 3) frases.push(`${c.racha} días seguidos por encima de la meta del día`);
    L.push({
      nodos: [el('span', 'tv-etiqueta', 'Para celebrar'), el('h2', 'tv-titulo', '¡Felicitaciones! 🎉'), ul(frases.map((f, i) => [['🏆', '⭐', '🔥'][i] || '🎉', f, '', '']))],
      hilo: ['¡Esto hay que celebrarlo! 🎉', 'aplaude']
    });
  }

  // 7. Retos de la semana
  const R = retos && retos.ok ? retos : null;
  if (R && R.batalla) {
    const b = R.batalla, yo = b.gana === b.yo.id, otra = b.gana === b.rival.id;
    L.push({
      nodos: [
        el('span', 'tv-etiqueta', 'Batalla de la semana'),
        el('h2', 'tv-titulo', yo ? '¡Vamos ganando! 👑' : otra ? `${b.rival.nombre} va adelante` : '¡Vamos empatadas!'),
        ul([[yo ? '👑' : '1', b.yo.nombre, pct(b.yo.avance), yo ? 'mia' : ''], [otra ? '👑' : '2', b.rival.nombre, pct(b.rival.avance), '']]),
        datos([['Gana la que va más adelante', 'en su meta de la semana'], ...(otra && b.falta ? [['Para pasar adelante', dinero(b.falta)]] : []), ...(b.racha >= 2 ? [['Racha', `${b.racha} semanas ganando`]] : [])])
      ],
      hilo: [yo ? `¡Le vamos ganando a ${b.rival.nombre}! ⚔️` : otra ? `Nos faltan ${dinero(b.falta)} para pasar a ${b.rival.nombre}. ¡Vamos!` : '¡Batalla pareja! Cada venta cuenta.', yo ? 'feliz' : 'animo']
    });
  }
  const rec = R && R.records ? [['dia', 'Mejor día'], ['semana', 'Mejor semana'], ['mes', 'Mejor mes']].filter(([k]) => R.records[k] && R.records[k].estado) : [];
  if (rec.length) {
    const txt = { roto: '¡Récord roto!', cerca: 'Muy cerca', camino: 'Va camino a récord' };
    L.push({
      nodos: [el('span', 'tv-etiqueta', 'Récords de la tienda'), el('h2', 'tv-titulo', '¡Estamos cerca de un récord! ⭐'),
        ul(rec.map(([k, n]) => ['⭐', `${n}: ${dinero(R.records[k].valor)}`, txt[R.records[k].estado], 'ok']))],
      hilo: ['¡Vamos por el récord! ⭐', 'aplaude']
    });
  }
  if (R && R.hora_dorada) {
    const h = R.hora_dorada, hh = x => `${x % 12 || 12} ${x < 12 ? 'a. m.' : 'p. m.'}`;
    L.push({
      nodos: [el('span', 'tv-etiqueta', 'Hora dorada'), el('h2', 'tv-titulo', `De ${hh(h.dorada)} a ${hh(h.dorada + 2)}`),
        datos([['Es cuando más vendemos', 'últimos 28 días'], ...(h.floja ? [[`A las ${hh(h.floja.h)} compran pocos`, pct(h.floja.valor)]] : [])])],
      hilo: ['¡En la hora dorada todas a vender! ✨', 'animo']
    });
  }

  laminas = L;
  escena.replaceChildren(...L.map(x => lamina(x.nodos)));
  puntos.replaceChildren(...L.map(() => el('i')));
  actual = -1;
  clearInterval(temporizador);
  siguiente();
  temporizador = setInterval(siguiente, SEGUNDOS * 1000);
}

function siguiente() {
  if (!laminas.length) return;
  actual = (actual + 1) % laminas.length;
  Array.from(escena.children).forEach((n, i) => n.classList.toggle('activa', i === actual));
  Array.from(puntos.children).forEach((n, i) => n.classList.toggle('activo', i === actual));
  const [texto, pose] = laminas[actual].hilo || [];
  decir(texto, pose);
}

cargar();
setInterval(cargar, 10 * 60 * 1000);
setTimeout(() => location.reload(), 6 * 60 * 60 * 1000);
document.addEventListener('keydown', e => { if (e.key === 'ArrowRight' || e.key === ' ') { clearInterval(temporizador); siguiente(); temporizador = setInterval(siguiente, SEGUNDOS * 1000); } });

/* ---------- Piezas ---------- */
function lamina(nodos) { const s = el('div', 'tv-lamina'); nodos.forEach(n => n && s.append(n)); return s; }
function barra(v) {
  const b = el('div', 'tv-barra'), s = el('span'), i = el('i');
  s.className = v >= 1 ? 'ok' : v >= 0.9 ? '' : v >= 0.75 ? 'medio' : 'alto';
  s.style.width = Math.min(100, (v || 0) / 1.25 * 100) + '%';
  i.style.left = (100 / 1.25) + '%';
  b.append(s, i);
  return b;
}
function datos(lista) {
  const d = el('div', 'tv-datos');
  lista.forEach(([t, v]) => { const x = el('div', 'tv-dato'); x.append(el('span', '', t), el('b', '', v)); d.append(x); });
  return d;
}
function ul(filas) {
  const u = el('ul', 'tv-lista');
  filas.forEach(([pos, nom, val, clase]) => {
    const li = el('li', clase === 'mia' ? 'mia' : '');
    li.append(el('span', 'pos', pos), el('span', 'nom', nom), el('span', 'val' + (clase === 'ok' ? ' ok' : ''), val));
    u.append(li);
  });
  return u;
}
function el(tag, clase, texto) { const n = document.createElement(tag); if (clase) n.className = clase; if (texto != null) n.textContent = texto; return n; }
function pct(v) { return v == null ? '—' : (Number(v) * 100).toFixed(1) + '%'; }
function dinero(v) { return '$' + new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Math.max(0, Math.round(Number(v) || 0))); }
function miles(v) { return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Math.round(Number(v) || 0)); }
function cap(s) { s = String(s || ''); return s.charAt(0).toUpperCase() + s.slice(1); }
function nombre(n) { return String(n || '').toLowerCase().replace(/(^|\s)\S/g, m => m.toUpperCase()); }
function unir(l) { return l.length <= 1 ? (l[0] || '') : l.slice(0, -1).join(', ') + ' y ' + l[l.length - 1]; }
