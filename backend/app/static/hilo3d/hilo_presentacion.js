/* ================================================================
   Presentación de Hilo: «Horarios y Novedades»
   - Tiendas (dashboard de tienda) y administración (dashboard del
     administrador) tienen cada una su versión. Sale una sola vez por usuario:
     el servidor recuerda quién ya la vio (/novedades/api/presentacion/...),
     así no se repite aunque cambien de computador.
   - Para verla otra vez: agregar ?presentacion=horarios a la dirección.
   - En «Mensajes con Hilo» se ve quién ya la vio y a quién le falta.
   Solo muestra información: no cambia datos ni cálculos.
   ================================================================ */
const VERSIONES = {
  tienda: { clave: 'horarios-novedades', ir: ['/cuadrante/', 'Ir a Horarios'] },
  admin: { clave: 'horarios-novedades-admin', ir: ['/planilla/', 'Ir a Horarios de las tiendas'] }
};

const PASOS = [
  {
    pose: ['saluda'], titulo: 'Novedades en tu menú', sub: 'Dos secciones que les ahorran trabajo',
    dice: '¡Hola, equipo! 👋 Soy Hilo. Les cuento rapidito lo nuevo en <b>Horarios del equipo</b> y <b>Novedades del equipo</b>.',
    escena: `<div class="hp-menu" aria-hidden="true">
      <div><i class="bi bi-speedometer2"></i>Resultados de mi tienda</div>
      <div><i class="bi bi-calendar-day"></i>Ventas diarias</div>
      <div class="nuevo"><i class="bi bi-calendar-week"></i>Horarios del equipo<span class="hp-chip nuevo">Nuevo</span></div>
      <div class="nuevo"><i class="bi bi-person-lines-fill"></i>Novedades del equipo<span class="hp-chip nuevo">Nuevo</span></div>
      <div><i class="bi bi-lightning-charge"></i>Retos de la semana</div></div>`
  },
  {
    pose: ['explica'], titulo: 'La planilla de horas', sub: 'Ahora es la pestaña principal de Horarios',
    dice: 'En la <b>Planilla de horas</b> llenan la <b>entrada</b> y la <b>salida</b> de cada persona, día por día. Yo calculo las horas solito.',
    escena: `<div class="hp-planilla" aria-hidden="true">
      <div class="hp-fila"><b>Ana María</b><small>Asesora · Lunes 3</small></div>
      <div class="hp-celda"><div class="hp-sel uno"><small>Entra</small><span>10 a. m.</span></div><div class="hp-sel dos"><small>Sale</small><span>6 p. m.</span></div></div>
      <div class="hp-total"><span class="hp-mini">Horas del día</span><strong><span>7 h</span></strong></div>
      <p class="hp-mini" style="margin:10px 0 0">De 10 a 6 son 8 horas, menos 1 hora de almuerzo = 7 horas.</p></div>`
  },
  {
    pose: ['senala', { lado: 1 }], titulo: '¿Almorzó o no?', sub: 'Una marca por día',
    dice: 'Cada día tiene la casilla <b>Almorzó</b>. Si alguien <b>no almorzó</b>, le quitan la marca y le cuento <b>todas</b> las horas.',
    escena: `<div class="hp-planilla" aria-hidden="true" style="position:relative">
      <div class="hp-fila"><b>Ana María</b><small>Asesora · Lunes 3</small></div>
      <div class="hp-celda"><div class="hp-sel"><small>Entra</small>10 a. m.</div><div class="hp-sel"><small>Sale</small>6 p. m.</div></div>
      <div class="hp-check"><i></i><span>Almorzó</span></div>
      <div class="hp-total"><span class="hp-mini">Horas del día</span><strong><span class="antes">7 h</span><span class="despues">8 h<small>sin almuerzo</small></span></strong></div>
      <span class="hp-cursor"></span></div>`
  },
  {
    pose: ['animo'], titulo: '¿Falta alguien?', sub: 'Auxiliar, subadministradora, volante…',
    dice: 'Si en la planilla no sale la <b>auxiliar</b> o la <b>subadministradora</b>, toquen <b>Agregar persona</b>: nombre, cargo y listo.',
    escena: `<div class="hp-planilla" aria-hidden="true">
      <div class="hp-fila"><b>Administradora</b><small>Administradora</small></div>
      <div class="hp-fila"><b>Ana María</b><small>Asesora</small></div>
      <div class="hp-fila"><b>Sofía</b><small>Asesora</small></div>
      <div class="hp-fila nueva"><b>Laura</b><small>Auxiliar</small><span class="hp-chip azul" style="margin-left:auto">Agregada</span></div>
      <span class="hp-boton"><i class="bi bi-person-plus-fill"></i>Agregar persona</span></div>`
  },
  {
    pose: ['feliz', { saltos: 3 }], titulo: 'Los turnos se llenan solos', sub: 'Sin hacer el trabajo dos veces',
    dice: 'Cuando den <b>Guardar planilla</b>, yo lleno los <b>Turnos de la semana</b>: quién abre, quién cierra y quién descansa. ¡Sin doble trabajo! 🎉',
    escena: `<div aria-hidden="true"><span class="hp-guardar"><i class="bi bi-check2"></i>Guardar planilla</span><span class="hp-chip ok">Turnos actualizados</span>
      <div class="hp-turnos">
        <div class="hp-turno" style="--c:#22c55e"><h4>Apertura</h4><span class="hp-chip ok" style="--d:1.2s">Ana María</span><span class="hp-chip ok" style="--d:1.4s">Laura</span></div>
        <div class="hp-turno" style="--c:#3b82f6"><h4>Cierre</h4><span class="hp-chip azul" style="--d:1.6s">Sofía</span><span class="hp-chip azul" style="--d:1.8s">Administradora</span></div>
        <div class="hp-turno" style="--c:#f59e0b"><h4>Descanso</h4><span class="hp-chip ambar" style="--d:2s">Marcela</span></div>
      </div></div>`
  },
  {
    pose: ['explica'], titulo: 'Novedades del equipo', sub: 'Lo que registra Talento Humano',
    dice: 'Talento Humano registra <b>vacaciones</b>, <b>incapacidades</b> y <b>permisos</b>. Las ven en <b>Novedades del equipo</b> y salen marcadas solas en la planilla.',
    escena: `<div aria-hidden="true">
      <div class="hp-aviso"><i class="bi bi-person-lines-fill"></i><div><b>Vacaciones · Sofía</b><div class="hp-mini">Del miércoles 5 al lunes 10 · registrado por Talento Humano</div></div></div>
      <div class="hp-semana">
        <div class="hp-dia">Mar 4<small>Trabaja</small></div>
        <div class="hp-dia th" style="--d:1s">Mié 5<small>🌴 Vac.</small></div>
        <div class="hp-dia th" style="--d:1.15s">Jue 6<small>🌴 Vac.</small></div>
        <div class="hp-dia th" style="--d:1.3s">Vie 7<small>🌴 Vac.</small></div>
        <div class="hp-dia th" style="--d:1.45s">Sáb 8<small>🌴 Vac.</small></div>
        <div class="hp-dia th" style="--d:1.6s">Dom 9<small>🌴 Vac.</small></div>
        <div class="hp-dia th" style="--d:1.75s">Lun 10<small>🌴 Vac.</small></div>
      </div>
      <p class="hp-mini" style="margin:14px 0 0">En la planilla esos días salen con la etiqueta <span class="hp-chip ambar">TH: Vacaciones</span> y así ya saben quién no está al armar los horarios.</p></div>`
  },
  {
    pose: ['aplaude'], titulo: 'Metas justas para todas', sub: 'Los días que no está, no le cuentan',
    dice: 'Y lo mejor: los días que alguien está de vacaciones o incapacitada <b>no le cuentan en su meta</b>. Su cumplimiento se mide justo. 💪',
    escena: `<div aria-hidden="true">
      <div class="hp-meta"><div class="hp-meta-cab"><b>Sofía</b><span class="hp-chip ambar">Vacaciones 5 – 10</span></div>
        <div class="hp-numeros"><span class="hp-mini">Meta del mes</span><span class="viejo">$10.000.000</span><span class="nuevo">$8.064.516</span></div>
        <div class="hp-barra"><span></span></div>
        <div class="hp-pct">Cumplimiento: <b>84%</b> en vez de 68%, porque solo cuentan los días que estuvo.</div></div>
      <div class="hp-meta"><div class="hp-meta-cab"><b>También aplica</b></div>
        <div class="hp-mini" style="margin-top:6px">Incapacidades, licencias, traslados, ingresos y retiros. Junto al nombre verán la etiqueta de la novedad.</div></div></div>`
  }
];

PASOS.forEach((p, i) => { p.e = 'hp-e' + (i + 1); });

// Versión para la administración: lo mismo visto desde la red, con sus secciones
const PASOS_ADMIN = [
  {
    e: 'hp-e1', pose: ['saluda'], titulo: 'Novedades en el menú', sub: 'Horarios y personal de toda la red',
    dice: '¡Hola! 👋 Te cuento lo nuevo de <b>Horarios</b> y <b>Novedades del personal</b>. A las tiendas ya se los expliqué yo también.',
    escena: `<div class="hp-menu" aria-hidden="true">
      <div><i class="bi bi-speedometer2"></i>Resumen general de ventas</div>
      <div><i class="bi bi-trophy"></i>Ranking de desempeño</div>
      <div class="nuevo"><i class="bi bi-clock-history"></i>Horarios de las tiendas<span class="hp-chip nuevo">Nuevo</span></div>
      <div class="nuevo"><i class="bi bi-person-lines-fill"></i>Novedades del personal<span class="hp-chip nuevo">Nuevo</span></div>
      <div><i class="bi bi-chat-heart"></i>Mensajes con Hilo</div></div>`
  },
  {
    e: 'hp-e8', pose: ['explica'], titulo: 'Horarios de las tiendas', sub: 'La planilla de cualquier tienda',
    dice: 'Eliges la tienda y ves su <b>planilla de horas</b>. Yo te aviso lo que hay que revisar y puedes descargar el <b>Excel del mes</b> en el formato de Talento Humano.',
    escena: `<div aria-hidden="true">
      <div class="hp-fila"><i class="bi bi-shop"></i><b>S-05 · Tienda</b><small style="margin-left:auto">Semana del 2 al 8</small></div>
      <div class="hp-alertas">
        <span class="hp-chip ambar" style="--d:.5s"><i class="bi bi-exclamation-triangle-fill"></i>Laura pasa de 42 horas</span>
        <span class="hp-chip ambar" style="--d:.8s"><i class="bi bi-exclamation-triangle-fill"></i>El jueves nadie abre</span>
        <span class="hp-chip ok" style="--d:1.1s"><i class="bi bi-check-circle-fill"></i>Todas tienen descanso</span>
      </div>
      <span class="hp-excel"><i class="bi bi-file-earmark-excel"></i>Descargar Excel de noviembre</span></div>`
  },
  {
    e: 'hp-e3', pose: ['senala', { lado: 1 }], titulo: 'Lo que llenan las tiendas', sub: 'Entrada, salida y almuerzo',
    dice: 'Las tiendas llenan <b>entrada</b>, <b>salida</b> y si la persona <b>almorzó</b>. Si no almorzó, se cuentan todas las horas. También pueden <b>agregar</b> a la auxiliar o la subadministradora.',
    escena: PASOS[2].escena
  },
  {
    e: 'hp-e5', pose: ['feliz', { saltos: 3 }], titulo: 'Los turnos se llenan solos', sub: 'Sin doble trabajo en las tiendas',
    dice: 'Al guardar la planilla, los <b>Turnos de la semana</b> se llenan solos: quién abre, quién cierra y quién descansa.',
    escena: PASOS[4].escena
  },
  {
    e: 'hp-e6', pose: ['explica'], titulo: 'Novedades del personal', sub: 'Las registra Talento Humano',
    dice: 'Talento Humano registra <b>vacaciones</b>, <b>incapacidades</b>, <b>permisos</b>, <b>traslados</b>, <b>ingresos</b> y <b>retiros</b>. La tienda las ve y salen marcadas solas en su planilla.',
    escena: PASOS[5].escena
  },
  {
    e: 'hp-e7', pose: ['aplaude'], titulo: 'Metas justas en los rankings', sub: 'Los días que no está, no le cuentan',
    dice: 'Con esas novedades, la <b>meta</b> y el <b>«debería ir hoy»</b> de cada asesora cuentan solo los días que estuvo en la tienda. En los rankings verás la etiqueta junto a su nombre.',
    escena: PASOS[6].escena
  }
];

queueMicrotask(iniciar);

async function iniciar() {
  if (document.getElementById('mhForm')) { quienLaVio(); return; }   // «Mensajes con Hilo»
  const tipo = document.getElementById('tpDatos') ? 'tienda' : document.getElementById('dashboard-v2-data') ? 'admin' : null;
  if (!tipo) return;                                                 // solo en el dashboard
  const V = VERSIONES[tipo], api = '/novedades/api/presentacion/' + V.clave, local = 'lhpulse-presentacion-' + V.clave;
  const forzar = new URLSearchParams(location.search).get('presentacion') === 'horarios';
  if (!forzar) {
    let ver = false;
    try { ver = !!(await (await fetch(api, { credentials: 'same-origin' })).json()).ver; } catch (e) { ver = false; }
    if (!ver || leer(local) === '1') return;   // la sesión recuerda por si el servidor no alcanzó a guardar
  }
  // El botón final solo si esa persona tiene la sección en su menú
  const ir = (tipo === 'tienda' || document.querySelector(`a[href="${V.ir[0]}"], a[href^="${V.ir[0]}?"]`)) ? V.ir : null;
  esperarTop3(() => setTimeout(() => abrir(tipo === 'tienda' ? PASOS : PASOS_ADMIN, { api, local, ir }), 700));
}

// La ceremonia del Top 3 va primero
function esperarTop3(cb) {
  const o = document.getElementById('top3StoresOverlay');
  if (!o || !o.classList.contains('active') || o.classList.contains('closing')) { cb(); return; }
  setTimeout(() => esperarTop3(cb), 400);
}

async function abrir(PASOS, cfg) {
  const BASE = new URL('.', import.meta.url).href;
  const css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = BASE + 'hilo_presentacion.css?v=4';
  document.head.appendChild(css);
  await new Promise(r => { css.onload = r; css.onerror = r; setTimeout(r, 1500); });

  let paso = 0, hilo = null, abierta = true;
  const anterior = document.activeElement;
  const capa = el('div', 'hp');
  capa.innerHTML = `
    <div class="hp-caja" role="dialog" aria-modal="true" aria-labelledby="hpTitulo">
      <aside class="hp-hilo">
        <span class="hp-kicker">Hilo te cuenta</span>
        <div class="hp-escenario"></div>
        <p class="hp-dice" aria-live="polite"></p>
        <div class="hp-puntos" aria-hidden="true">${PASOS.map(() => '<i></i>').join('')}</div>
      </aside>
      <section class="hp-lado">
        <header class="hp-cab"><div><h2 id="hpTitulo"></h2><p></p></div>
          <button type="button" class="hp-cerrar" aria-label="Cerrar la presentación">×</button></header>
        <div class="hp-escena">${PASOS.map((p, i) => `<div class="hp-e ${p.e}" data-i="${i}">${p.escena}</div>`).join('')}</div>
        <footer class="hp-pie">
          <button type="button" class="hp-btn texto hp-saltar">Saltar</button>
          <button type="button" class="hp-btn hp-atras"><i class="bi bi-arrow-left"></i>Atrás</button>
          <button type="button" class="hp-btn primario hp-sig">Siguiente<i class="bi bi-arrow-right"></i></button>
          ${cfg.ir ? `<a class="hp-btn oro hp-ir" href="${cfg.ir[0]}" hidden><i class="bi bi-calendar-week"></i>${cfg.ir[1]}</a>` : ''}
          <button type="button" class="hp-btn primario hp-fin" hidden>Entendido</button>
        </footer>
      </section>
    </div>`;
  document.body.append(capa);
  document.body.classList.add('hp-abierta');
  const $ = s => capa.querySelector(s);

  // Hilo en 3D; si el equipo no puede, un hilo de coser
  try {
    const motor = await import('./hilo_motor.js');
    if (motor.hayWebGL()) {
      hilo = motor.crearHilo({ ancho: 214, alto: 200, quieto: motor.prefiereQuieto(), pasear: false, ideas: 'pocas', fps: 30,
        maxPixelRatio: 1.5, temporada: motor.temporadaActual(), visible: () => abierta });
      $('.hp-escenario').append(hilo.canvas);
    }
  } catch (e) { hilo = null; }
  if (!hilo) $('.hp-escenario').innerHTML = '<div class="hp-sin3d" aria-hidden="true">🧵</div>';

  function mostrar(i) {
    paso = Math.max(0, Math.min(PASOS.length - 1, i));
    const p = PASOS[paso], ultimo = paso === PASOS.length - 1;
    $('#hpTitulo').textContent = p.titulo;
    $('.hp-cab p').textContent = `${p.sub} · Paso ${paso + 1} de ${PASOS.length}`;
    $('.hp-dice').innerHTML = p.dice;
    capa.querySelectorAll('.hp-e').forEach((e, j) => {
      e.classList.remove('on');
      if (j === paso) { void e.offsetWidth; e.classList.add('on'); }   // vuelve a empezar la animación
    });
    capa.querySelectorAll('.hp-puntos i').forEach((d, j) => d.classList.toggle('on', j === paso));
    $('.hp-atras').hidden = paso === 0;
    $('.hp-sig').hidden = ultimo;
    if ($('.hp-ir')) $('.hp-ir').hidden = !ultimo;
    $('.hp-fin').hidden = !ultimo;
    $('.hp-saltar').hidden = ultimo;
    if (hilo) hilo.poner(p.pose[0], p.pose[1]);
    (ultimo ? $('.hp-fin') : $('.hp-sig')).focus({ preventScroll: true });
  }

  function cerrar() {
    if (!abierta) return;
    abierta = false;
    guardar(cfg.local, '1');
    fetch(cfg.api, { method: 'POST', credentials: 'same-origin' }).catch(() => {});
    capa.classList.remove('visible');
    document.body.classList.remove('hp-abierta');
    document.removeEventListener('keydown', teclas);
    setTimeout(() => capa.remove(), 380);
    if (anterior && anterior.focus) anterior.focus({ preventScroll: true });
  }

  function teclas(e) {
    if (e.key === 'Escape') { cerrar(); return; }
    if (e.key === 'ArrowRight' && paso < PASOS.length - 1) mostrar(paso + 1);
    if (e.key === 'ArrowLeft' && paso > 0) mostrar(paso - 1);
    if (e.key === 'Tab') {   // el foco no sale de la presentación
      const f = [...capa.querySelectorAll('button:not([hidden]), a:not([hidden])')];
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  }

  $('.hp-sig').addEventListener('click', () => mostrar(paso + 1));
  $('.hp-atras').addEventListener('click', () => mostrar(paso - 1));
  $('.hp-saltar').addEventListener('click', cerrar);
  $('.hp-cerrar').addEventListener('click', cerrar);
  $('.hp-fin').addEventListener('click', cerrar);
  if ($('.hp-ir')) $('.hp-ir').addEventListener('click', () => { abierta = false; guardar(cfg.local, '1'); fetch(cfg.api, { method: 'POST', credentials: 'same-origin', keepalive: true }).catch(() => {}); });
  document.addEventListener('keydown', teclas);

  mostrar(0);
  requestAnimationFrame(() => capa.classList.add('visible'));
}

/* ---------- «Mensajes con Hilo»: quién ya vio cada presentación ---------- */
async function quienLaVio() {
  let d = null;
  try { d = await (await fetch('/novedades/api/presentaciones/vistos', { credentials: 'same-origin' })).json(); } catch (e) { d = null; }
  if (!d || !d.ok) return;
  const estilos = el('style');
  estilos.textContent = `
.hpv { margin-bottom: 18px; }
.hpv h3 { display: flex; align-items: center; gap: 8px; margin: 0 0 4px; font-size: 16px; font-weight: 700; }
.hpv > p { margin: 0 0 12px; color: #6B6259; font-size: 13px; }
.hpv-item { padding: 12px 0; border-top: 1px solid #F1EBE0; }
.hpv-cab { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.hpv-cab b { font-size: 14px; }
.hpv-barra { flex: 1 1 160px; height: 8px; border-radius: 999px; background: #EFE8DE; overflow: hidden; }
.hpv-barra span { display: block; height: 100%; border-radius: 999px; background: #3F7F55; }
.hpv-num { color: #6B6259; font-size: 13px; font-weight: 600; white-space: nowrap; }
.hpv-ver { padding: 3px 10px; border: 1px solid #E2D6C2; border-radius: 999px; background: #fff; color: #2D2A26; font: 600 12px/1.2 Inter, "Segoe UI", Arial, sans-serif; cursor: pointer; }
.hpv-ver:hover { background: #F6EFE3; } .hpv-ver:focus-visible { outline: 2px solid #C5A880; outline-offset: 1px; }
.hpv-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-top: 10px; padding: 10px 12px; border-radius: 12px; background: #FDF9F1; }
.hpv-cols h4 { margin: 0 0 6px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: #6B6259; }
.hpv-cols ul { list-style: none; margin: 0; padding: 0; max-height: 220px; overflow: auto; }
.hpv-cols li { display: flex; justify-content: space-between; gap: 10px; padding: 5px 0; border-bottom: 1px solid #F1EBE0; font-size: 12.5px; }
.hpv-cols li span { color: #6B6259; white-space: nowrap; }
.hpv-cols .ok b::before { content: "✓ "; color: #3F7F55; }
.hpv-cols .falta b::before { content: "• "; color: #A9472F; }`;
  document.head.append(estilos);

  const caja = el('div', 'glass-panel hpv');
  caja.innerHTML = '<h3><i class="bi bi-play-circle"></i>Animaciones de Hilo</h3><p>Se muestran una sola vez a cada usuario al entrar a su dashboard. Aquí ves quién ya la vio y a quién le falta.</p>';
  d.presentaciones.forEach(p => {
    const total = p.vieron.length + p.faltan.length;
    const item = el('div', 'hpv-item'), cab = el('div', 'hpv-cab');
    const barra = el('div', 'hpv-barra'), lleno = el('span');
    lleno.style.width = (total ? Math.round(p.vieron.length / total * 100) : 0) + '%';
    barra.append(lleno);
    const ver = el('button', 'hpv-ver'); ver.type = 'button'; ver.textContent = 'Ver quién'; ver.setAttribute('aria-expanded', 'false');
    cab.append(el('b', '', p.titulo), barra, el('span', 'hpv-num', `${p.vieron.length} de ${total} la vieron`), ver);
    item.append(cab);
    let detalle = null;
    ver.addEventListener('click', () => {
      if (detalle) { detalle.remove(); detalle = null; ver.textContent = 'Ver quién'; ver.setAttribute('aria-expanded', 'false'); return; }
      detalle = el('div', 'hpv-cols');
      const col = (titulo, lista, clase, vacio) => {
        const c = el('div'), ul = el('ul', clase);
        c.append(el('h4', '', `${titulo} (${lista.length})`));
        if (!lista.length) ul.append(el('li', '', vacio));
        lista.forEach(x => {
          const li = el('li');
          li.append(el('b', '', [x.tienda, x.usuario].filter(Boolean).join(' · ')));
          if (x.fecha) li.append(el('span', '', x.fecha));
          ul.append(li);
        });
        c.append(ul);
        return c;
      };
      detalle.append(col('La vieron', p.vieron, 'ok', 'Nadie todavía.'), col('Les falta', p.faltan, 'falta', '¡Ya la vieron todos!'));
      item.append(detalle);
      ver.textContent = 'Ocultar'; ver.setAttribute('aria-expanded', 'true');
    });
    caja.append(item);
  });
  // Antes de la tabla de mensajes enviados
  const tabla = document.querySelector('.mh-tabla');
  const panel = tabla ? tabla.closest('.glass-panel') : null;
  if (panel) panel.before(caja); else document.getElementById('mhForm').closest('.mh-grid').after(caja);
}

function el(tag, clase, texto) { const n = document.createElement(tag); if (clase) n.className = clase; if (texto != null) n.textContent = texto; return n; }
function leer(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
function guardar(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* sin almacenamiento */ } }
