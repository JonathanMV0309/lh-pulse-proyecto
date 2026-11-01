/* ================================================================
   Hilo dentro de L&H Pulse (esquina inferior derecha)
   Páginas:
   - Dashboard de tienda (#tpDatos): reacciona a la meta, dice cuánto debe
     vender hoy cada asesora, avisa qué revisar y explica cada indicador ("?").
   - Dashboard del administrador (#dashboard-v2-data): resume las tiendas y
     avisa cuáles están en rojo o sin ventas; cada aviso lleva a esa tienda.
   - Ranking de desempeño (#performanceRankingData): aplaude el podio y cuenta
     si la tienda subió o bajó de puesto desde la última visita.
   En todas: dice los mensajes que deja el administrador ("Mensajes con Hilo"),
   saluda una vez por sesión, gira mientras cargan los filtros,
   se duerme, se ríe con cosquillas y se puede esconder.
   Hilo inteligente (hilo_escena.js + hilo_saber.js):
   - Antes de hablar busca un espacio libre para no tapar nada y salta ahí;
     si lo que dice es largo abre su panel a la derecha (modo conversación).
   - Tienda: cierre proyectado y plan por día, reto del día, coach de
     conversión, celebraciones, comparación por clima, meta distribuible,
     «Pregúntale a Hilo», voz opcional y Modo TV.
   - Administración: resumen de la red, riesgo, causas, tiendas sin entrar,
     calidad de datos, a quién felicitar, pronóstico V3, cambios bruscos,
     mensajes sugeridos e informe semanal.
   Solo lee datos (la página y /api/hilo/*); no cambia cálculos ni diseño.
   ================================================================ */
// Se arranca al terminar de cargar el módulo (las constantes de abajo ya existen)
queueMicrotask(() => {
  // Mensajes con Hilo (administrador): quién vio cada mensaje y mensajes sugeridos
  if (document.getElementById('mhForm')) import('./hilo_mensajes_admin.js?v=1').catch(() => {});
  const P = detectarPagina();
  if (P && window.innerWidth >= 900) iniciar(P);
});

function detectarPagina() {
  const leerJSON = id => { const n = document.getElementById(id); if (!n) return null; try { return JSON.parse(n.textContent); } catch (e) { return null; } };
  let D = leerJSON('tpDatos');
  if (D) return { tipo: 'tienda', D, periodo: `${D.tienda}-${D.anio}-${D.mes}`, avisos: calcularAvisos(D), metaHoy: calcularMetaHoy(D) };
  D = leerJSON('dashboard-v2-data');
  if (D && Array.isArray(D.ranking)) {
    const corte = leerCorteAdmin();
    return { tipo: 'admin', D, corte, periodo: `admin-${corte.anio || ''}-${corte.mes || ''}`, avisos: avisosAdmin(D, corte) };
  }
  D = leerJSON('performanceRankingData');
  if (D && document.getElementById('rankingPage')) {
    const per = document.querySelector('.performance-period strong');
    return { tipo: 'ranking', D, periodo: 'ranking-' + (per ? per.textContent.trim() : ''), avisos: [] };
  }
  return null;
}

function iniciar(P) {
  const D = P.D;

  const BASE = new URL('.', import.meta.url).href;
  const css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = BASE + 'hilo_app.css?v=4';
  document.head.appendChild(css);
  const css2 = document.createElement('link');
  css2.rel = 'stylesheet'; css2.href = BASE + 'hilo_cajon.css?v=1';
  document.head.appendChild(css2);

  // Lo nuevo se carga aparte: si falla, Hilo sigue funcionando como antes
  const modEscena = import('./hilo_escena.js?v=1').catch(() => null);
  const modSaber = import('./hilo_saber.js?v=2').catch(() => null);
  const datos = modSaber.then(s => (s && (P.tipo === 'tienda' || P.tipo === 'admin') ? s.cargarDatos(P) : null)).catch(() => null);
  let escena = null, saber = null, S = null, cajonListo = false, panelTarjeta = null, botonHablar = null;

  const CLAVE_OCULTO = 'lhpulse-hilo-oculto';
  const periodo = P.periodo;
  const avisos = P.avisos;
  let hilo = null, raiz, burbuja, panel, cuenta, volver, ayuda, panelHoy, botonHoy, tarjetaMensaje;
  datos.then(d => { S = d; });

  // Mensajes del administrador pendientes para este usuario
  const mensajes = fetch('/api/hilo/mensajes', { credentials: 'same-origin' })
    .then(r => (r.ok ? r.json() : []))
    .then(lista => (Array.isArray(lista) ? lista : []))
    .catch(() => []);

  if (leer(localStorage, CLAVE_OCULTO) === '1') {
    mostrarVolver();
    // Aunque Hilo esté escondido, los mensajes del administrador sí se muestran
    mensajes.then(lista => { if (lista.length) setTimeout(() => decirMensajes(lista.slice()), 800); });
  }
  else montar(true);

  /* ---------- Armar a Hilo ---------- */
  async function montar(conSecuencia) {
    let motor;
    try { motor = await import('./hilo_motor.js'); } catch (e) { return; }
    if (!motor.hayWebGL()) return;

    raiz = el('div', 'hilo-app');
    const toque = el('button', 'hilo-app-toque');
    toque.type = 'button';
    toque.setAttribute('aria-label', avisos.length ? `Hilo: ${avisos.length} cosas para revisar` : 'Hilo');
    const cerrar = el('button', 'hilo-app-cerrar', '×');
    cerrar.type = 'button'; cerrar.title = 'Ocultar a Hilo'; cerrar.setAttribute('aria-label', 'Ocultar a Hilo');
    cuenta = el('button', 'hilo-app-cuenta'); cuenta.type = 'button'; cuenta.hidden = true;
    cuenta.setAttribute('aria-label', 'Ver lo que hay para revisar');
    burbuja = el('div', 'hilo-app-burbuja'); burbuja.setAttribute('role', 'status');
    panel = armarPanel(); panel.hidden = true;
    raiz.append(toque, cuenta, cerrar);
    if (P.metaHoy) {
      botonHoy = el('button', 'hilo-app-hoy');
      botonHoy.type = 'button';
      botonHoy.title = 'Meta de hoy por asesora';
      botonHoy.setAttribute('aria-label', 'Ver la meta de hoy por asesora');
      botonHoy.append(el('i', 'bi bi-bullseye'), el('span', '', 'Hoy'));
      botonHoy.addEventListener('click', () => { if (panelHoy && !panelHoy.hidden) cerrarMetaHoy(); else abrirMetaHoy(); });
      raiz.append(botonHoy);
    }
    if (P.tipo === 'tienda' || P.tipo === 'admin') {
      botonHablar = el('button', 'hilo-app-hablar');
      botonHablar.type = 'button';
      botonHablar.title = 'Conversar con Hilo';
      botonHablar.setAttribute('aria-label', 'Abrir la conversación con Hilo');
      botonHablar.append(el('i', 'bi bi-chat-dots-fill'), el('span', '', 'Hablar'));
      botonHablar.addEventListener('click', () => { if (escena && escena.cajonAbierto()) escena.cerrarCajon(); else abrirConversacion(); });
      botonHablar.hidden = true;
      raiz.append(botonHablar);
    }
    document.body.append(raiz, burbuja, panel);

    hilo = motor.crearHilo({
      ancho: 176, alto: 164, quieto: motor.prefiereQuieto(), pasear: false, ideas: 'pocas',
      fps: 30, maxPixelRatio: 1.5, visible: () => !raiz.hidden,
      temporada: motor.temporadaActual(), sueno: 90,
      alDormir: dormido => {
        raiz.classList.toggle('dormido', dormido);
        if (!dormido) decir('¡Ay! No estaba dormido…', 2000);
      }
    });
    raiz.prepend(hilo.canvas);

    // Escena: espacio libre y modo conversación
    const [me, ms] = await Promise.all([modEscena, modSaber]);
    saber = ms;
    if (me && me.crearEscena) {
      escena = me.crearEscena({ raiz, burbuja, hilo, alCerrarCajon: () => { actualizarCuenta(); if (botonHablar) botonHablar.classList.remove('activo'); } });
      if (botonHablar && saber) botonHablar.hidden = false;
      if (saber) prepararCajon();
    }

    // Clic en Hilo: cosquillas. Clic en el número rojo: lo que hay para revisar.
    const RISAS = ['¡Jaja, cosquillas!', '¡Ay, para, para!', '¡Jijiji!', '¡Me vas a desenrollar!'];
    let risa = 0;
    toque.addEventListener('click', () => {
      if (!panel.hidden) { cerrarPanel(); return; }
      if (panelHoy && !panelHoy.hidden) { cerrarMetaHoy(); return; }
      cerrarAyuda();
      hilo.poner('risa');
      decir(RISAS[risa++ % RISAS.length], 1800);
    });
    cuenta.addEventListener('click', () => { cerrarAyuda(); abrirPanel(); });
    cerrar.addEventListener('click', esconder);
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      if (escena && escena.cajonAbierto()) { escena.cerrarCajon(); return; }
      if (!panel.hidden) cerrarPanel();
      cerrarMetaHoy();
      cerrarAyuda();
    });
    document.addEventListener('click', e => {
      if (ayuda && !ayuda.hidden && !ayuda.contains(e.target) && !e.target.closest('.hilo-ayuda-btn')) cerrarAyuda();
    });
    if (P.tipo === 'tienda') prepararAyuda();
    if (P.tipo === 'ranking') prepararRanking();

    // Filtros: mientras el servidor calcula, gira soltando hilo
    document.querySelectorAll('form').forEach(f => {
      if ((f.getAttribute('method') || 'get').toLowerCase() !== 'get' || f.closest('.hilo-cajon')) return;
      f.addEventListener('submit', () => { if (hilo && !raiz.hidden) { cerrarPanel(); hilo.poner('carga'); decir('Buscando los datos…'); } });
    });
    window.addEventListener('pageshow', e => { if (e.persisted && hilo) { hilo.poner('reposo'); decir(''); } });

    if (conSecuencia) despuesDelTop3(() => setTimeout(secuencia, 500));
    else { raiz.classList.add('visible'); actualizarCuenta(); }
    window.__hiloApp = {
      poner: (n, o) => hilo.poner(n, o), estado: hilo.estado, avisos: () => avisos.slice(), abrir: abrirPanel, mensajes: () => mensajes,
      escena: () => escena, datos: () => S, conversar: abrirConversacion, preguntar: q => preguntar(q), decir: (t, ms) => decir(t, ms),
      tarjeta: clave => mostrarTarjeta(clave), metaHoy: () => abrirMetaHoy()
    };
  }

  // La ceremonia del Top 3 va primero; Hilo espera a que cierre
  function despuesDelTop3(cb) {
    const o = document.getElementById('top3StoresOverlay');
    if (!o || !o.classList.contains('active') || o.classList.contains('closing')) { cb(); return; }
    setTimeout(() => despuesDelTop3(cb), 400);
  }

  /* ---------- Secuencia al entrar ---------- */
  function secuencia() {
    raiz.classList.add('visible');
    const conTiempo = Promise.race([datos, new Promise(r => setTimeout(() => r(null), 2500))]);
    Promise.all([mensajes, conTiempo]).then(([lista]) => armarSecuencia(lista));
  }
  function armarSecuencia(listaMensajes) {
    const pasos = [];
    if (!leer(sessionStorage, 'lhpulse-hilo-bienvenida')) { guardar(sessionStorage, 'lhpulse-hilo-bienvenida', '1'); pasos.push(bienvenida); }
    if (listaMensajes.length) pasos.push(() => decirMensajes(listaMensajes.slice()));
    const kMeta = 'lhpulse-hilo-meta-' + periodo;
    const meta = P.tipo === 'tienda' ? reaccionMeta() : P.tipo === 'admin' ? reaccionAdmin() : reaccionRanking();
    if (meta && !leer(sessionStorage, kMeta)) { guardar(sessionStorage, kMeta, '1'); pasos.push(meta); }
    // Celebraciones automáticas (asesoras al 100 %, récord del mes, rachas)
    if (P.tipo === 'tienda' && saber) saber.celebracionesNuevas(D, S, periodo).forEach(c => pasos.push(() => {
      hilo.poner(c.pose, c.saltos ? { saltos: c.saltos } : undefined);
      decir(c.texto, 5200); volverLuego(c.pose, 4800); return 5600;
    }));
    // Cierre proyectado (una vez al día)
    const kProy = `lhpulse-hilo-proy-${periodo}-${new Date().toDateString()}`;
    const pr = S && S.proyeccion;
    if (P.tipo === 'tienda' && pr && !pr.cerrado && !leer(localStorage, kProy)) {
      guardar(localStorage, kProy, '1');
      pasos.push(() => {
        hilo.poner(pr.pct >= 1 ? 'feliz' : 'concentra');
        decir(pr.falta > 0 ? `Si siguen así, cierran el mes en ${pct(pr.pct)}. Para el 100 % necesitan ${dinero(pr.necesita_dia)} por día` : `¡Van para cerrar en ${pct(pr.pct)}! La meta del mes ya está`, 5600);
        volverLuego(hilo.estado(), 5200); return 6000;
      });
    }
    // Administración: tiendas que se unieron al hilo de la red en el último corte (una vez al día)
    const kRed = `lhpulse-hilo-red-${periodo}-${new Date().toDateString()}`;
    const rt = P.tipo === 'admin' && S && S.red_tejida;
    if (rt && rt.nuevas.length && !leer(localStorage, kRed)) {
      guardar(localStorage, kRed, '1');
      pasos.push(() => {
        hilo.poner('aplaude');
        const quienes = rt.nuevas.length <= 3 ? rt.nuevas.join(', ').replace(/, ([^,]*)$/, ' y $1') : `${rt.nuevas.length} tiendas`;
        decir(`¡${quienes} ${rt.nuevas.length === 1 ? 'se unió' : 'se unieron'} al hilo de la red! Ya van ${rt.unidas} de ${rt.total} 🧵`, 5200);
        volverLuego('aplaude', 4800); return 5600;
      });
    }
    // Administración: resumen ejecutivo al entrar (una vez al día)
    const kResumen = `lhpulse-hilo-resumen-${periodo}-${new Date().toDateString()}`;
    if (P.tipo === 'admin' && S && saber && !leer(localStorage, kResumen)) {
      guardar(localStorage, kResumen, '1');
      pasos.push(() => {
        if (escena && escena.puedeCajon()) return abrirConversacion('resumen').then(() => 4500);
        const r = S.red;
        hilo.poner('explica');
        decir(r.cerrado ? `La red cerró en ${pct(r.cump)}` : `Al ritmo de hoy la red cierra en ${pct(r.proy_pct)}`, 5000);
        volverLuego('explica', 4600); return 5400;
      });
    }
    const kHoy = `lhpulse-hilo-metahoy-${periodo}-${new Date().toDateString()}`;
    const mostrarHoy = P.metaHoy && !leer(localStorage, kHoy);
    if (mostrarHoy) {
      guardar(localStorage, kHoy, '1');
      pasos.push(() => {
        const primera = P.metaHoy.asesoras.find(a => !a.cumplida);
        hilo.poner('explica');
        decir(primera ? `Oye, ${primerNombre(primera.nombre)}: hoy debes vender ${dinero(primera.hoy)}` : '¡Todas las asesoras ya cumplieron su meta del mes!', 4200);
        volverLuego('explica', 3800);
        return 4600;
      });
      pasos.push(() => { abrirMetaHoy(); return 0; });
    }
    const kAvisos = 'lhpulse-hilo-avisos-' + periodo;
    if (mostrarHoy) { /* "Para revisar" queda en el número rojo para no tapar la meta de hoy */ }
    else if (avisos.length && !leer(sessionStorage, kAvisos)) { guardar(sessionStorage, kAvisos, '1'); pasos.push(() => { abrirPanel(); return 0; }); }
    else if (!leer(localStorage, 'lhpulse-hilo-tip-ayuda') && document.querySelector('.hilo-ayuda-btn')) {
      // Una sola vez: cuenta que puede explicar los indicadores
      guardar(localStorage, 'lhpulse-hilo-tip-ayuda', '1');
      pasos.push(() => { hilo.poner('explica'); decir('Tip: toca el ? de un indicador y te explico qué significa', 5200); volverLuego('explica', 4000); return 5600; });
    }
    correr(pasos);
  }
  function correr(pasos) {
    if (!pasos.length) { actualizarCuenta(); return; }
    const r = pasos.shift()();
    if (r && typeof r.then === 'function') r.then(ms => setTimeout(() => correr(pasos), typeof ms === 'number' ? ms : 400));
    else setTimeout(() => correr(pasos), r);
  }
  function bienvenida() {
    const h = new Date().getHours();
    const saludo = h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches';
    const nombre = nombreUsuario();
    hilo.poner('saluda');
    decir(nombre ? `${saludo}, ${nombre}` : `${saludo}`, 3800);
    volverLuego('saluda', 3000);
    return 4300;
  }
  function reaccionMeta() {
    const c = num(D.cumplimiento), falta = num(D.falta);
    if (c <= 0 && falta <= 0) return null; // sin meta cargada
    if (falta <= 0 && num(D.ventas) > 0) return () => { hilo.poner('feliz', { saltos: 4 }); decir('¡Lograron la meta del mes! 🎉', 5200); volverLuego('feliz', 5000); return 5600; };
    if (c >= 1) return () => { hilo.poner('feliz'); decir(`¡Van por encima de la meta! Llevan ${pct(c)}`, 4600); volverLuego('feliz', 4200); return 5000; };
    if (c >= 0.9) return () => { hilo.poner('animo'); decir(`¡Casi! Faltan ${dinero(falta)} para la meta`, 4600); volverLuego('animo', 4200); return 5000; };
    return () => { hilo.poner('concentra'); decir(`Vamos, aún hay tiempo: faltan ${dinero(falta)} para la meta`, 4800); volverLuego('concentra', 4400); return 5200; };
  }

  /* ---------- Burbuja y panel de avisos ---------- */
  function decir(texto, ms) {
    if (!burbuja) return;
    clearTimeout(decir.r);
    if (!texto) { burbuja.classList.remove('visible'); if (escena) escena.callo(); return; }
    if (saber) saber.voz.decir(texto);
    if (escena && escena.cajonAbierto()) {
      const c = escena.cajon();
      c.dice.textContent = texto;
      if (ms) decir.r = setTimeout(() => { if (c.dice.textContent === texto) c.dice.textContent = ''; }, ms + 2500);
      return;
    }
    burbuja.textContent = texto;
    burbuja.classList.add('visible');
    if (escena) escena.hablar();
    if (ms) decir.r = setTimeout(() => { burbuja.classList.remove('visible'); if (escena) escena.callo(); }, ms);
  }
  // Paneles: en un espacio libre, en el panel de conversación o en la esquina
  function ubicar(nodo, alCerrar, corto) {
    return escena ? escena.mostrar(nodo, { alCerrar, corto: !!corto }) : Promise.resolve('esquina');
  }
  function soltarNodo(nodo) { if (escena && nodo) escena.soltar(nodo); }
  function senalar(donde) {
    if (!hilo) return;
    if (donde === 'cajon') hilo.poner('explica'); else hilo.poner('senala', { lado: escena ? escena.lado() : -1 });
    volverLuego(hilo.estado(), 2800);
  }
  function volverLuego(estado, ms) { setTimeout(() => { if (hilo && hilo.estado() === estado) hilo.poner('reposo'); }, ms); }

  function armarPanel() {
    const p = el('div', 'hilo-app-panel');
    p.setAttribute('role', 'dialog'); p.setAttribute('aria-label', 'Para revisar');
    const cab = el('div', 'hilo-app-panel-cab');
    const titulos = el('div');
    titulos.append(el('strong', '', 'Para revisar'), el('small', '', avisos.length === 1 ? 'Encontré 1 cosa este mes' : `Encontré ${avisos.length} cosas este mes`));
    const x = el('button', 'hilo-app-panel-cerrar', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Cerrar');
    x.addEventListener('click', cerrarPanel);
    cab.append(titulos, x);
    const lista = el('ul', 'hilo-app-lista');
    avisos.forEach(a => {
      const li = el('li'), b = el('button', 'hilo-app-item');
      b.type = 'button';
      const punto = el('span', 'hilo-app-punto'); punto.dataset.nivel = a.nivel;
      const texto = el('span', 'hilo-app-texto'); texto.append(el('span', 'hilo-app-titulo', a.titulo));
      if (a.detalle) texto.append(el('small', '', a.detalle));
      b.append(punto, texto); if (a.seccion || a.url) b.append(el('i', 'bi bi-chevron-right'));
      b.addEventListener('click', () => {
        cerrarPanel();
        if (a.url) { hilo.poner('carga'); decir('Abriendo la tienda…'); window.location.href = a.url; }
        else if (a.seccion) irA(a.seccion);
      });
      li.append(b); lista.append(li);
    });
    p.append(cab, lista);
    return p;
  }
  function abrirPanel() {
    if (!panel) return;
    decir(''); cerrarAyuda(); cerrarMetaHoy();
    panel.hidden = false;
    requestAnimationFrame(() => panel.classList.add('visible'));
    cuenta.hidden = true;
    ubicar(panel, cerrarPanel).then(senalar);
  }
  function cerrarPanel() {
    if (!panel || panel.hidden) return;
    panel.classList.remove('visible');
    panel.hidden = true;
    soltarNodo(panel);
    actualizarCuenta();
  }
  function actualizarCuenta() {
    if (!cuenta) return;
    cuenta.textContent = String(avisos.length);
    cuenta.hidden = !avisos.length || !panel.hidden;
  }
  function irA(titulo) {
    const h = Array.from(document.querySelectorAll('.section-card h4, .data-panel h3, section h2, section h3')).find(n => n.textContent.includes(titulo));
    const caja = h && (h.closest('.section-card, .data-panel, section') || h.parentElement);
    if (!caja) return;
    caja.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    caja.classList.remove('hilo-resalta'); void caja.offsetWidth; caja.classList.add('hilo-resalta');
    setTimeout(() => caja.classList.remove('hilo-resalta'), 2800);
  }

  /* ---------- Mensajes del administrador ---------- */
  // Muestra uno por uno; cada uno espera a que lo cierren con "Entendido" o ×.
  function decirMensajes(lista) {
    return new Promise(listo => {
      const siguiente = () => {
        const m = lista.shift();
        if (!m) { if (hilo) hilo.poner('reposo'); listo(); return; }
        mostrarMensaje(m, siguiente);
      };
      siguiente();
    });
  }
  function mostrarMensaje(m, alCerrar) {
    if (hilo) {
      decir(''); cerrarPanel(); cerrarAyuda(); cerrarMetaHoy();
      const pose = m.tono === 'celebra' ? ['feliz', { saltos: 3 }] : m.tono === 'aviso' ? ['senala', { lado: -1 }] : ['animo'];
      hilo.poner(pose[0], pose[1]);
    }
    tarjetaMensaje = el('div', 'hilo-app-panel hilo-app-mensaje' + (hilo && !raiz.hidden ? '' : ' sin-hilo'));
    tarjetaMensaje.setAttribute('role', 'alertdialog');
    tarjetaMensaje.setAttribute('aria-label', 'Mensaje de la administración');
    const cab = el('div', 'hilo-app-panel-cab'), tit = el('div');
    tit.append(el('strong', '', m.tono === 'aviso' ? 'Aviso importante' : 'Mensaje para ti'), el('small', '', `${m.autor} · ${m.fecha}`));
    const x = el('button', 'hilo-app-panel-cerrar', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Cerrar');
    cab.append(tit, x);
    const texto = el('p', 'hilo-mensaje-texto', m.texto);
    const ok = el('button', 'hilo-mensaje-ok', 'Entendido'); ok.type = 'button';
    tarjetaMensaje.append(cab, texto, ok);
    document.body.append(tarjetaMensaje);
    const esta = tarjetaMensaje;
    requestAnimationFrame(() => esta.classList.add('visible'));
    ok.focus({ preventScroll: true });
    if (saber) saber.voz.decir(m.texto);
    let cerrado = false;
    const cerrarEste = () => {
      if (cerrado) return;
      cerrado = true;
      fetch(`/api/hilo/mensajes/${m.id}/visto`, { method: 'POST', credentials: 'same-origin' }).catch(() => {});
      soltarNodo(esta);
      esta.remove();
      if (tarjetaMensaje === esta) tarjetaMensaje = null;
      alCerrar();
    };
    if (hilo && !raiz.hidden) ubicar(esta, cerrarEste, true);
    ok.addEventListener('click', cerrarEste);
    x.addEventListener('click', cerrarEste);
  }

  /* ---------- Meta de hoy por asesora ---------- */
  function abrirMetaHoy() {
    const M = P.metaHoy;
    if (!M) return;
    decir(''); cerrarPanel(); cerrarAyuda();
    if (!panelHoy) {
      panelHoy = el('div', 'hilo-app-panel hilo-app-panel-hoy');
      panelHoy.setAttribute('role', 'dialog'); panelHoy.setAttribute('aria-label', 'Meta de hoy');
      const cab = el('div', 'hilo-app-panel-cab'), tit = el('div');
      tit.append(el('strong', '', 'Meta de hoy'),
        el('small', '', M.dias === 1 ? 'Es el último día del mes' : `Quedan ${M.dias} días del mes, contando hoy`));
      const x = el('button', 'hilo-app-panel-cerrar', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Cerrar');
      x.addEventListener('click', cerrarMetaHoy);
      cab.append(tit, x);
      const total = el('div', 'hilo-hoy-total');
      total.append(el('span', '', 'La tienda necesita hoy'), el('b', '', M.tienda > 0 ? dinero(M.tienda) : '¡Meta cumplida!'));
      const lista = el('ul', 'hilo-app-lista');
      M.asesoras.forEach(a => {
        const li = el('li', 'hilo-hoy-fila');
        const punto = el('span', 'hilo-app-punto'); punto.dataset.nivel = a.cumplida ? 'ok' : a.cump < 0.75 ? 'alto' : a.cump < 0.9 ? 'medio' : 'bajo';
        const texto = el('span', 'hilo-app-texto');
        texto.append(el('span', 'hilo-app-titulo', a.nombre),
          el('small', '', a.cumplida ? `Ya cumplió su meta del mes (${pct(a.venta / a.meta)})` : `Lleva ${pct(a.venta / a.meta)} · le faltan ${dinero(a.falta)}`));
        li.append(punto, texto, el('b', 'hilo-hoy-valor', a.cumplida ? '✓' : dinero(a.hoy)));
        lista.append(li);
      });
      panelHoy.append(cab, total, lista);
      // Reto del día y plan del mes (si ya llegaron los datos)
      if (saber && S) {
        const reto = saber.retoDelDia(D, S);
        if (reto) {
          saber.anotarReto(S.tienda.id, reto);
          const r = el('div', 'hilo-hoy-reto');
          r.append(el('i', `bi ${reto.icono || 'bi-lightning-charge'}`), el('span', '', 'Reto del día: '), el('b', '', reto.texto));
          panelHoy.append(r);
        }
        if (S.proyeccion && escena && escena.puedeCajon()) {
          const ver = el('button', 'hilo-hoy-plan', 'Ver el plan para cerrar el mes');
          ver.type = 'button';
          ver.addEventListener('click', () => mostrarTarjeta('proyeccion'));
          panelHoy.append(ver);
        }
      }
      document.body.append(panelHoy);
    }
    panelHoy.hidden = false;
    requestAnimationFrame(() => panelHoy.classList.add('visible'));
    ubicar(panelHoy, cerrarMetaHoy).then(senalar);
  }
  function cerrarMetaHoy() {
    if (!panelHoy || panelHoy.hidden) return;
    panelHoy.classList.remove('visible');
    panelHoy.hidden = true;
    soltarNodo(panelHoy);
    actualizarCuenta();
  }

  /* ---------- Dashboard del administrador ---------- */
  function reaccionAdmin() {
    const tiendas = (D.ranking || []).filter(t => num(t.venta_actual) > 0);
    if (!tiendas.length) return null;
    const alDia = tiendas.filter(t => num(t.cumplimiento_pct) >= 1).length;
    const parte = alDia / tiendas.length;
    const texto = `${alDia} de ${tiendas.length} tiendas van al día con la meta`;
    if (parte >= 0.6) return () => { hilo.poner('feliz'); decir(`¡${texto}!`, 4600); volverLuego('feliz', 4200); return 5000; };
    if (parte >= 0.35) return () => { hilo.poner('animo'); decir(texto, 4600); volverLuego('animo', 4200); return 5000; };
    return () => { hilo.poner('concentra'); decir(`${texto}. Revisemos las que van bajas`, 4800); volverLuego('concentra', 4400); return 5200; };
  }

  /* ---------- Ranking de desempeño ---------- */
  function reaccionRanking() {
    const lista = D.tiendasDist || [];
    const mia = lista.find(t => t.mia);
    if (mia) {
      const total = lista.length, puesto = num(mia.p);
      const clave = `lhpulse-hilo-puesto-${mia.k}-${periodo}`;
      const antes = num(leer(localStorage, clave));
      guardar(localStorage, clave, String(puesto));
      if (antes && puesto < antes) {
        const n = antes - puesto;
        return () => { hilo.poner(puesto <= 3 ? 'aplaude' : 'feliz'); decir(`¡Subieron ${n === 1 ? '1 puesto' : n + ' puestos'} desde la última vez! Van en el puesto ${puesto} de ${total}`, 5200); volverLuego(hilo.estado(), 4800); return 5600; };
      }
      if (puesto >= 1 && puesto <= 3) return () => { hilo.poner('aplaude'); decir(`¡Están en el podio! Puesto ${puesto} de ${total} 🏆`, 5000); volverLuego('aplaude', 4600); return 5400; };
      if (antes && puesto > antes) {
        const n = puesto - antes;
        return () => { hilo.poner('concentra'); decir(`Bajaron ${n === 1 ? '1 puesto' : n + ' puestos'}. ¡A recuperarlos! Van en el puesto ${puesto} de ${total}`, 5200); volverLuego('concentra', 4800); return 5600; };
      }
      return () => { hilo.poner(num(mia.c) >= 1 ? 'feliz' : 'animo'); decir(`Van en el puesto ${puesto} de ${total} tiendas`, 4200); volverLuego(hilo.estado(), 3800); return 4600; };
    }
    const podio = lista.filter(t => num(t.p) >= 1 && num(t.p) <= 3).sort((a, b) => num(a.p) - num(b.p));
    if (!podio.length) return null;
    return () => { hilo.poner('aplaude'); decir(`¡Aplausos para ${podio.map(t => t.n).join(', ').replace(/, ([^,]*)$/, ' y $1')}!`, 5000); volverLuego('aplaude', 4600); return 5400; };
  }
  function prepararRanking() {
    // Al abrir la pestaña de asesoras, aplaude a la primera (una vez por visita)
    const tab = document.getElementById('rkTab-asesoras');
    const primera = (D.asesoras || []).filter(a => num(a.p) === 1)[0];
    if (!tab || !primera) return;
    let hecho = false;
    tab.addEventListener('click', () => {
      if (hecho || !hilo || raiz.hidden) return;
      hecho = true;
      hilo.poner('aplaude');
      decir(`¡${primerNombre(primera.n)} lidera entre las asesoras! 👏`, 4000);
      volverLuego('aplaude', 3600);
    });
  }

  /* ---------- Hilo te explica cada indicador ---------- */
  function prepararAyuda() {
    document.body.classList.add('hilo-ayuda-on');
    document.querySelectorAll('.kpi-card .kpi-title, .meta-label, .section-card .section-header h4').forEach(n => {
      if (n.querySelector('.hilo-ayuda-btn')) return;
      const texto = n.textContent.trim().replace(/\s+/g, ' ').toUpperCase();
      const item = AYUDA.find(a => a.claves.some(c => texto === c || texto.startsWith(c)));
      if (!item) return;
      const b = el('button', 'hilo-ayuda-btn');
      b.type = 'button';
      b.setAttribute('aria-label', `¿Qué es ${item.titulo}? Hilo te explica`);
      b.title = 'Hilo te explica';
      b.append(el('i', 'bi bi-question-circle')); // sin texto: otros scripts comparan el título exacto
      b.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); explicar(item); });
      n.append(b);
    });
  }
  function explicar(item) {
    cerrarPanel(); decir('');
    if (!ayuda) {
      ayuda = el('div', 'hilo-app-panel hilo-app-ayuda');
      ayuda.setAttribute('role', 'dialog');
      document.body.append(ayuda);
    }
    ayuda.replaceChildren();
    ayuda.setAttribute('aria-label', item.titulo);
    const cab = el('div', 'hilo-app-panel-cab'), tit = el('div');
    tit.append(el('strong', '', item.titulo), el('small', '', 'Hilo te explica'));
    const x = el('button', 'hilo-app-panel-cerrar', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Cerrar');
    x.addEventListener('click', cerrarAyuda);
    cab.append(tit, x);
    const que = el('p', 'hilo-ayuda-que', item.que);
    const consejo = el('div', 'hilo-ayuda-tip');
    consejo.append(el('i', 'bi bi-lightbulb'), el('span', '', typeof item.tip === 'function' ? item.tip(D) : item.tip));
    ayuda.append(cab, que, consejo);
    ayuda.hidden = false;
    requestAnimationFrame(() => ayuda.classList.add('visible'));
    soltarNodo(ayuda);
    ubicar(ayuda, cerrarAyuda, true);
    hilo.poner('explica');
    volverLuego('explica', 4000);
    if (saber) saber.voz.decir(`${item.titulo}. ${item.que}`);
  }
  function cerrarAyuda() {
    if (!ayuda || ayuda.hidden) return;
    ayuda.classList.remove('visible');
    ayuda.hidden = true;
    soltarNodo(ayuda);
  }

  /* ---------- Modo conversación: panel de Hilo a la derecha ---------- */
  function contexto() {
    return {
      tipo: P.tipo, D, S: P.tipo === 'tienda' ? S : null, A: P.tipo === 'admin' ? S : null, P,
      ayuda: AYUDA, nombre: nombreUsuario(), preguntar: q => preguntar(q), urlTV: urlTV()
    };
  }
  function urlTV() {
    const m = location.pathname.match(/\/dashboard\/tienda\/(\d+)/);
    return '/hilo/tv' + (m ? `?store_id=${m[1]}` : '');
  }
  const ATAJOS = {
    tienda: [
      ['proyeccion', 'Cierre del mes', 'bi-flag'], ['hoy', 'Meta de hoy', 'bi-bullseye'], ['reto', 'Reto del día', 'bi-lightning-charge'],
      ['coach', 'Conversión', 'bi-people'], ['clima', 'Mi clima', 'bi-thermometer-sun'], ['distribuible', 'Meta distribuible', 'bi-diagram-3'],
      ['avisos', 'Para revisar', 'bi-list-check'], ['preguntas', 'Preguntas', 'bi-chat-dots']
    ],
    admin: [
      ['resumen', 'Resumen', 'bi-speedometer2'], ['red', 'La red tejida', 'bi-diagram-3'], ['riesgo', 'En riesgo', 'bi-exclamation-triangle'], ['diagnostico', '¿Por qué bajan?', 'bi-search'],
      ['sinUso', 'Sin entrar', 'bi-person-x'], ['calidad', 'Calidad de datos', 'bi-clipboard-data'], ['felicitar', 'Felicitar', 'bi-award'],
      ['v3', 'Pronóstico V3', 'bi-stars'], ['cambios', 'Cambios bruscos', 'bi-activity'], ['sugeridos', 'Mensajes sugeridos', 'bi-chat-heart'],
      ['reporte', 'Informe semanal', 'bi-file-earmark-bar-graph'], ['preguntas', 'Preguntas', 'bi-chat-dots']
    ]
  };
  function prepararCajon() {
    if (cajonListo || !escena || !saber) return;
    cajonListo = true;
    const c = escena.cajon();
    c.raiz.querySelector('.hilo-cajon-titulos small').textContent = P.tipo === 'admin' ? 'Tu asistente de la red' : 'Tu compañero de resultados';
    (ATAJOS[P.tipo] || []).forEach(([clave, texto, icono]) => {
      if (clave === 'hoy' && !P.metaHoy) return;
      if (clave === 'avisos' && !avisos.length) return;
      const b = el('button', 'hilo-atajo');
      b.type = 'button';
      b.append(el('i', `bi ${icono}`), el('span', '', texto));
      b.addEventListener('click', () => mostrarTarjeta(clave));
      c.atajos.append(b);
    });
    // Voz (opcional) y Modo TV
    if (saber.voz.disponible()) {
      const v = el('button', 'hilo-cajon-boton');
      v.type = 'button';
      const pintar = () => {
        const on = saber.voz.activa();
        v.replaceChildren(el('i', `bi ${on ? 'bi-volume-up-fill' : 'bi-volume-mute'}`));
        v.title = on ? 'Hilo habla en voz alta (toca para silenciar)' : 'Que Hilo hable en voz alta';
        v.setAttribute('aria-pressed', on ? 'true' : 'false');
        v.setAttribute('aria-label', v.title);
      };
      v.addEventListener('click', () => { saber.voz.poner(!saber.voz.activa()); pintar(); if (saber.voz.activa()) saber.voz.decir('¡Listo! Ahora te hablo en voz alta.'); });
      pintar();
      c.botones.prepend(v);
    }
    if (P.tipo === 'tienda') {
      const tv = el('a', 'hilo-cajon-boton');
      tv.href = urlTV(); tv.target = '_blank'; tv.rel = 'noopener';
      tv.title = 'Modo TV: resultados en grande para la pantalla de la tienda';
      tv.setAttribute('aria-label', tv.title);
      tv.append(el('i', 'bi bi-tv'));
      c.botones.prepend(tv);
    }
    c.form.addEventListener('submit', e => {
      e.preventDefault();
      const q = c.input.value.trim();
      if (!q) return;
      c.input.value = '';
      preguntar(q);
    });
  }
  async function abrirConversacion(primera) {
    if (!escena || !saber) return false;
    prepararCajon();
    const nueva = !escena.cajonAbierto();
    const ok = await escena.abrirCajon();
    if (!ok) return false;
    if (botonHablar) botonHablar.classList.add('activo');
    if (primera) await mostrarTarjeta(primera);
    else if (nueva && !escena.cajon().feed.children.length) {
      const h = new Date().getHours();
      escena.decirEnCajon(`${h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches'}. ¿Qué quieres saber? Toca un tema de arriba o escríbeme abajo.`);
      hilo.poner('saluda'); volverLuego('saluda', 2600);
    }
    if (nueva) setTimeout(() => { try { escena.cajon().input.focus({ preventScroll: true }); } catch (e) { /* nada */ } }, 450);
    return true;
  }
  async function mostrarTarjeta(clave) {
    if (!saber) return;
    if (clave === 'hoy') { await abrirConversacion(); abrirMetaHoy(); return; }
    if (clave === 'avisos') { await abrirConversacion(); abrirPanel(); return; }
    if (!S && clave !== 'preguntas') {
      await abrirConversacion();
      escena.decirEnCajon('Todavía estoy cargando los datos… dame un segundo.');
      S = await datos;
      if (!S) { escena.decirEnCajon('No pude cargar los datos ahora. Intenta recargar la página.'); return; }
    }
    const T = saber.T;
    const textos = {
      proyeccion: () => [S.proyeccion && !S.proyeccion.cerrado ? `Si siguen así, cierran el mes en ${pct(S.proyeccion.pct)}.` : 'Así va el mes:', T.proyeccion(S), 'explica'],
      reto: () => {
        const r = saber.retoDelDia(D, S);
        if (r) saber.anotarReto(S.tienda.id, r);
        const ant = saber.resultadoRetoAnterior(S.tienda.id, S);
        return [r ? `Reto de hoy: ${r.texto.charAt(0).toLowerCase() + r.texto.slice(1)}.` : '¡Hoy no tengo reto: van bien en todo!', T.reto(r, ant), 'animo'];
      },
      coach: () => ['Así va la conversión:', T.coach(S), 'explica'],
      clima: () => [S.comparacion ? `Entre las tiendas de clima ${S.comparacion.clima} van ${S.comparacion.puesto}° de ${S.comparacion.total}.` : 'No tengo el clima de la tienda.', T.comparacion(S), 'senala'],
      distribuible: () => ['Así se reparte la meta entre las asesoras:', T.metaDistribuible(S), 'explica'],
      preguntas: () => ['Pregúntame lo que quieras:', T.preguntas(P.tipo, q => preguntar(q)), 'saluda'],
      resumen: () => [S.red.cerrado ? `El mes cerró en ${pct(S.red.cump)}.` : `La red va en ${pct(S.red.cump)} y, al ritmo de hoy, cierra en ${pct(S.red.proy_pct)}.`, T.resumen(S), 'explica'],
      red: () => [S.red_tejida ? `${S.red_tejida.unidas} de ${S.red_tejida.total} tiendas ya están en el hilo de la red.` : 'Todavía no tengo el hilo de la red.', T.red ? T.red(S) : null, 'aplaude'],
      riesgo: () => ['Estas son las que más me preocupan:', T.riesgo(S), 'concentra'],
      diagnostico: () => ['Separé la venta en tráfico, conversión y tiquete:', T.diagnostico(S), 'explica'],
      sinUso: () => ['Tiendas que no han entrado a L&H Pulse:', T.sinUso(S), 'senala'],
      calidad: () => ['Revisé los datos cargados:', T.calidad(S), 'concentra'],
      felicitar: () => ['¡Estas merecen un aplauso!', T.felicitar(S), 'aplaude'],
      v3: () => ['El pronóstico V3 frente a lo que va pasando:', T.v3(S), 'explica'],
      cambios: () => ['Comparé el último día con el mismo día de otras semanas:', T.cambios(S), 'senala'],
      sugeridos: () => ['Te dejé mensajes listos:', T.sugeridos(S), 'explica'],
      reporte: () => ['El informe para gerencia:', T.reporte(S), 'explica'],
    };
    const armar = textos[clave];
    if (!armar) return;
    const [texto, nodo, pose] = armar();
    await contar(texto, nodo, pose);
  }
  async function contar(texto, nodo, pose) {
    if (escena && escena.puedeCajon()) {
      await abrirConversacion();
      escena.decirEnCajon(texto, { nodo });
      if (saber) saber.voz.decir(texto);
    } else {
      // Pantalla mediana: la tarjeta flota junto a Hilo
      if (!panelTarjeta) {
        panelTarjeta = el('div', 'hilo-app-panel hilo-app-tarjeta');
        panelTarjeta.setAttribute('role', 'dialog');
        panelTarjeta.setAttribute('aria-label', 'Hilo');
        document.body.append(panelTarjeta);
      }
      const cab = el('div', 'hilo-app-panel-cab'), tit = el('div');
      tit.append(el('strong', '', 'Hilo'), el('small', '', texto));
      const x = el('button', 'hilo-app-panel-cerrar', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Cerrar');
      const cerrarT = () => { panelTarjeta.classList.remove('visible'); panelTarjeta.hidden = true; soltarNodo(panelTarjeta); };
      x.addEventListener('click', cerrarT);
      cab.append(tit, x);
      soltarNodo(panelTarjeta);
      panelTarjeta.replaceChildren(cab);
      if (nodo) panelTarjeta.append(nodo);
      panelTarjeta.hidden = false;
      requestAnimationFrame(() => panelTarjeta.classList.add('visible'));
      ubicar(panelTarjeta, cerrarT);
      if (saber) saber.voz.decir(texto);
    }
    if (pose && hilo) { hilo.poner(pose); volverLuego(pose, 3600); }
  }
  async function preguntar(q) {
    if (!saber) return;
    if (escena && escena.puedeCajon()) { await abrirConversacion(); escena.decirEnCajon(q, { quien: 'usuario' }); }
    if (!S && (P.tipo === 'tienda' || P.tipo === 'admin')) S = await datos;
    const r = saber.responder(q, contexto());
    if (!r) return;
    if (hilo) hilo.poner('concentra');
    await new Promise(listo => setTimeout(listo, 380));
    await contar(r.texto, r.nodo || null, r.pose || 'explica');
    if (r.abrir === 'metaHoy') abrirMetaHoy();
    if (r.abrir === 'avisos') abrirPanel();
  }

  /* ---------- Esconder / mostrar ---------- */
  function esconder() {
    if (escena && escena.cajonAbierto()) escena.cerrarCajon();
    guardar(localStorage, CLAVE_OCULTO, '1');
    cerrarPanel(); cerrarAyuda(); cerrarMetaHoy(); decir('');
    raiz.hidden = true; cuenta.hidden = true;
    document.body.classList.remove('hilo-ayuda-on');
    mostrarVolver();
  }
  function mostrarVolver() {
    if (!volver) {
      volver = el('button', 'hilo-app-volver');
      volver.type = 'button';
      volver.append(el('i', 'bi bi-emoji-smile'), document.createTextNode(' Hilo'));
      volver.title = 'Mostrar a Hilo';
      volver.setAttribute('aria-label', 'Mostrar a Hilo');
      volver.addEventListener('click', () => {
        guardar(localStorage, CLAVE_OCULTO, '0');
        volver.hidden = true;
        if (hilo) { raiz.hidden = false; document.body.classList.add('hilo-ayuda-on'); actualizarCuenta(); hilo.poner('saluda'); volverLuego('saluda', 2000); }
        else montar(false);
      });
      document.body.append(volver);
    }
    volver.hidden = false;
  }
}

/* ---------- Qué revisar (solo con los datos de la página) ---------- */
function calcularAvisos(D) {
  const avisos = [];

  // 0. Datos atrasados: en el mes actual lo normal es tener datos hasta ayer
  const hoy = new Date();
  if (num(D.anio) === hoy.getFullYear() && num(D.mes) === hoy.getMonth() + 1 && num(D.dia_corte) > 0) {
    const faltan = (hoy.getDate() - 1) - num(D.dia_corte);
    if (faltan >= 1) avisos.push({
      nivel: faltan >= 3 ? 'alto' : 'medio',
      titulo: `Los datos llegan hasta el día ${num(D.dia_corte)}`,
      detalle: `Hoy es ${hoy.getDate()}: ${faltan === 1 ? 'falta 1 día' : `faltan ${faltan} días`} por importar. Los números pueden verse más bajos.`,
      seccion: null
    });
  }

  // 1. Líneas por debajo del 90 % al corte
  const lineas = (D.lineas || []).filter(l => num(l.meta) > 0 && num(l.cump) < 0.9).sort((a, b) => num(a.cump) - num(b.cump));
  lineas.slice(0, 3).forEach(l => avisos.push({
    nivel: num(l.cump) < 0.75 ? 'alto' : 'medio',
    titulo: `Línea ${l.linea}: va en ${pct(l.cump)}`,
    detalle: `Faltan ${dinero(num(l.meta) - num(l.venta))} para su meta`,
    seccion: 'Desempeño por línea'
  }));
  if (lineas.length > 3) avisos.push({ nivel: 'medio', titulo: `${lineas.length - 3} líneas más por debajo del 90 %`, seccion: 'Desempeño por línea' });

  // 2. Asesoras por debajo del 75 % (con meta asignada)
  const bajas = (D.asesoras || []).filter(a => !a.generico && num(a.cump) > 0 && num(a.cump) < 0.75).sort((a, b) => num(a.cump) - num(b.cump));
  if (bajas.length) avisos.push({
    nivel: 'medio',
    titulo: bajas.length === 1 ? '1 asesora por debajo del 75 %' : `${bajas.length} asesoras por debajo del 75 %`,
    detalle: bajas.slice(0, 2).map(a => `${primerNombre(a.nombre)} ${pct(a.cump)}`).join(' · '),
    seccion: 'Ranking de asesoras'
  });

  // 3. Conversión de los últimos días por debajo del promedio del mes
  const dias = (D.diario || []).filter(d => num(d.trafico) > 0);
  const totT = dias.reduce((s, d) => s + num(d.trafico), 0), totF = dias.reduce((s, d) => s + num(d.facturas), 0);
  const ultimos = dias.slice(-3);
  if (dias.length >= 6 && totT > 0) {
    const mes = totF / totT;
    const uT = ultimos.reduce((s, d) => s + num(d.trafico), 0), uF = ultimos.reduce((s, d) => s + num(d.facturas), 0);
    const reciente = uT ? uF / uT : 0;
    if (mes > 0 && reciente < mes * 0.85) avisos.push({
      nivel: reciente < mes * 0.7 ? 'alto' : 'medio',
      titulo: `Conversión de los últimos 3 días: ${pct(reciente)}`,
      detalle: `El mes va en ${pct(mes)}`,
      seccion: 'Evolución diaria de conversión'
    });
  }

  // 4. Datos de tráfico para revisar
  const sinTrafico = (D.diario || []).filter(d => num(d.trafico) === 0 && num(d.facturas) > 0).length;
  if (sinTrafico) avisos.push({
    nivel: 'bajo',
    titulo: sinTrafico === 1 ? '1 día con ventas y sin tráfico registrado' : `${sinTrafico} días con ventas y sin tráfico registrado`,
    detalle: 'Puede faltar el dato del contador',
    seccion: 'Evolución diaria de conversión'
  });

  // 5. VPT por debajo de la meta mínima de la tienda
  if (num(D.meta_vpt) > 0 && num(D.ticket) > 0 && num(D.ticket) < num(D.meta_vpt)) avisos.push({
    nivel: num(D.ticket) < num(D.meta_vpt) * 0.9 ? 'alto' : 'medio',
    titulo: `VPT por debajo de la meta mínima`,
    detalle: `Va en ${dinero(D.ticket)}; la meta es ${dinero(D.meta_vpt)} (faltan ${dinero(num(D.meta_vpt) - num(D.ticket))} por tiquete)`,
    seccion: 'Evolución de ventas'
  });

  // 6. Ventas por debajo del año anterior
  const etiqueta = Array.from(document.querySelectorAll('.meta-label')).find(n => n.textContent.trim() === 'Diferencia');
  const valor = etiqueta && etiqueta.nextElementSibling;
  if (valor && valor.classList.contains('text-danger')) avisos.push({
    nivel: 'medio',
    titulo: 'Ventas por debajo del año anterior',
    detalle: `Diferencia: ${valor.textContent.trim().replace(/\s+/g, ' ')}`,
    seccion: 'Evolución de ventas'
  });

  return avisos;
}

/* ---------- Meta de hoy: lo que falta del mes ÷ días que quedan (contando hoy) ---------- */
function calcularMetaHoy(D) {
  const hoy = new Date();
  if (num(D.anio) !== hoy.getFullYear() || num(D.mes) !== hoy.getMonth() + 1) return null; // solo el mes en curso
  const diasMes = new Date(num(D.anio), num(D.mes), 0).getDate();
  const dias = Math.max(1, diasMes - Math.max(num(D.dia_corte), hoy.getDate() - 1));
  const asesoras = (D.asesoras || [])
    .filter(a => !a.generico && num(a.meta) > 0)
    .map(a => {
      const falta = Math.max(0, num(a.meta) - num(a.venta));
      return { nombre: a.nombre, venta: num(a.venta), meta: num(a.meta), cump: num(a.cump), falta, hoy: falta / dias, cumplida: falta <= 0 };
    })
    .sort((x, y) => (x.cumplida - y.cumplida) || (y.hoy - x.hoy));
  if (!asesoras.length) return null;
  return { dias, tienda: num(D.falta) / dias, asesoras };
}

/* ---------- Dashboard del administrador: qué revisar ---------- */
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
function leerCorteAdmin() {
  const n = document.querySelector('.cut-badge');
  const t = n ? n.textContent.replace(/\s+/g, ' ').toLowerCase() : '';
  const mes = MESES.findIndex(m => t.includes(m)) + 1;
  const anio = (t.match(/\b(20\d\d)\b/) || [])[1];
  const dia = (t.match(/día (\d{1,2})/) || [])[1];
  return { mes: mes || null, anio: anio ? +anio : null, dia: dia ? +dia : null };
}
function urlTienda(codigo) {
  const sel = document.getElementById('selectorTienda');
  if (!sel || !codigo) return null;
  const op = Array.from(sel.options).find(o => o.value && o.textContent.trim().toUpperCase().startsWith(String(codigo).toUpperCase() + ' '));
  if (!op) return null;
  const p = new URLSearchParams(location.search), q = new URLSearchParams();
  ['anio', 'mes', 'dia_corte'].forEach(k => { if (p.get(k)) q.set(k, p.get(k)); });
  return `/dashboard/tienda/${op.value}` + (q.toString() ? '?' + q : '');
}
function avisosAdmin(D, corte) {
  const avisos = [];
  const hoy = new Date();
  if (corte.anio === hoy.getFullYear() && corte.mes === hoy.getMonth() + 1 && corte.dia) {
    const faltan = (hoy.getDate() - 1) - corte.dia;
    if (faltan >= 1) avisos.push({
      nivel: faltan >= 3 ? 'alto' : 'medio',
      titulo: `Los datos llegan hasta el día ${corte.dia}`,
      detalle: `Hoy es ${hoy.getDate()}: ${faltan === 1 ? 'falta 1 día' : `faltan ${faltan} días`} por importar.`,
      seccion: null
    });
  }
  const tiendas = (D.ranking || []).map(t => ({ ...t, c: num(t.cumplimiento_pct), v: num(t.venta_actual) }));
  const sinVentas = tiendas.filter(t => t.v <= 0);
  const bajas = tiendas.filter(t => t.v > 0 && t.c > 0 && t.c < 0.75).sort((a, b) => a.c - b.c);
  bajas.slice(0, 4).forEach(t => avisos.push({
    nivel: t.c < 0.6 ? 'alto' : 'medio',
    titulo: `${t.nombre}: va en ${pct(t.c)}`,
    detalle: `${t.codigo} · ${dinero(t.v)} vendidos · Ver su dashboard`,
    url: urlTienda(t.codigo),
    seccion: urlTienda(t.codigo) ? null : 'Ranking de tiendas'
  }));
  if (bajas.length > 4) avisos.push({ nivel: 'medio', titulo: `${bajas.length - 4} tiendas más por debajo del 75 %`, seccion: 'Ranking de tiendas' });
  if (sinVentas.length) avisos.push({
    nivel: 'alto',
    titulo: sinVentas.length === 1 ? `${sinVentas[0].nombre} no tiene ventas cargadas` : `${sinVentas.length} tiendas sin ventas cargadas`,
    detalle: sinVentas.slice(0, 4).map(t => t.codigo).join(' · ') + ' · Revisa la carga de datos',
    url: sinVentas.length === 1 ? urlTienda(sinVentas[0].codigo) : null,
    seccion: 'Ranking de tiendas'
  });
  return avisos;
}

/* ---------- Qué significa cada indicador (Hilo te explica) ---------- */
function diasQueQuedan(D) {
  const total = new Date(num(D.anio), num(D.mes), 0).getDate();
  return Math.max(0, total - num(D.dia_corte));
}
function necesarioPorDia(D) {
  const dias = diasQueQuedan(D), falta = num(D.falta);
  if (falta <= 0) return '¡Ya cumplieron la cuota del mes! Todo lo que vendan ahora suma por encima de la meta.';
  if (!dias) return `Es el último día del período: faltan ${dinero(falta)} para la meta.`;
  return `Para llegar a la meta necesitan vender unos ${dinero(falta / dias)} por día en los ${dias} días que quedan.`;
}
function conversionMes(D) {
  const dias = (D.diario || []).filter(d => num(d.trafico) > 0);
  const t = dias.reduce((s, d) => s + num(d.trafico), 0), f = dias.reduce((s, d) => s + num(d.facturas), 0);
  return t ? f / t : 0;
}
const AYUDA = [
  { claves: ['CUMPLIMIENTO DE META', 'CUMPLIMIENTO AL CORTE'], titulo: 'Cumplimiento de meta',
    que: 'Compara lo que llevan vendido con lo que deberían llevar a esta fecha. 100 % significa que van al día con la meta.',
    tip: D => num(D.cumplimiento) >= 1 ? '¡Van al día o por encima! Sigan así para cerrar el mes arriba.'
      : 'Si están por debajo del 90 %, empiecen por las líneas y asesoras que aparecen en rojo.' },
  { claves: ['FALTA PARA LA META'], titulo: 'Falta para la meta',
    que: 'Lo que falta vender para llegar al 100 % de la cuota de todo el mes.', tip: necesarioPorDia },
  { claves: ['VENTA PROMEDIO / DÍA'], titulo: 'Venta promedio por día',
    que: 'La venta del mes dividida entre los días que van corridos.',
    tip: D => `Hoy van en ${dinero(D.venta_dia)} por día. ${necesarioPorDia(D)}` },
  { claves: ['VENTAS DEL MES', 'VENTA ACTUAL'], titulo: 'Ventas del mes',
    que: 'Todo lo vendido en el mes hasta el día de corte de los datos.',
    tip: 'Compárala con la venta del año anterior y con lo que falta para la meta.' },
  { claves: ['ACUM ENE'], titulo: 'Acumulado del año',
    que: 'Las ventas sumadas desde enero hasta hoy.',
    tip: 'Sirve para ver la tendencia del año completo, no solo la del mes.' },
  { claves: ['CRECIMIENTO VS'], titulo: 'Crecimiento',
    que: 'Cuánto más (o menos) venden frente al mismo período del año pasado.',
    tip: 'Si es negativo, revisen el tráfico y la conversión: ¿entra menos gente o compran menos los que entran?' },
  { claves: ['VENTA AÑO ANTERIOR'], titulo: 'Venta del año anterior',
    que: 'Lo que vendió la tienda en el mismo período del año pasado.', tip: 'Es la referencia para saber si la tienda está creciendo.' },
  { claves: ['DIFERENCIA'], titulo: 'Diferencia',
    que: 'La venta actual menos la del año anterior.', tip: 'En verde están vendiendo más que el año pasado; en rojo, menos.' },
  { claves: ['CUOTA TOTAL'], titulo: 'Cuota total', que: 'La meta de venta de todo el mes.', tip: necesarioPorDia },
  { claves: ['FACTURAS'], titulo: 'Facturas',
    que: 'El número de compras hechas en el mes: cada factura es un cliente que compró.',
    tip: 'Más facturas = más clientes comprando. Se sube atendiendo rápido a cada persona que entra.' },
  { claves: ['TICKET PROMEDIO', 'TICKET ASESORAS'], titulo: 'Ticket promedio',
    que: 'Lo que gasta en promedio cada cliente en una compra (venta ÷ facturas).',
    tip: D => `Van en ${dinero(D.ticket)}. Ofrecer un complemento en cada compra (accesorio, segunda prenda) lo sube.` },
  { claves: ['META MÍNIMA VPT'], titulo: 'Meta mínima de VPT',
    que: 'El valor mínimo que debería tener cada compra (VPT = venta ÷ facturas), según el promedio acumulado del año de la tienda.',
    tip: D => num(D.meta_vpt) > 0 ? `La meta de la tienda es ${dinero(D.meta_vpt)} por tiquete y van en ${dinero(D.ticket)}. Ofrecer un complemento en cada compra ayuda a llegar.` : 'Esta tienda todavía no tiene meta de VPT cargada.' },
  { claves: ['CUMPLIMIENTO META VPT'], titulo: 'Cumplimiento de la meta de VPT',
    que: 'Compara el VPT actual (ticket promedio) con la meta mínima. 100 % o más = cada compra vale lo esperado o más.',
    tip: 'Si está bajo, enfóquense en vender el conjunto completo y en los productos de mayor valor.' },
  { claves: ['VPT AÑO ANTERIOR', 'VARIACIÓN VPT'], titulo: 'VPT frente al año anterior',
    que: 'El valor por tiquete del mismo período del año pasado y cuánto cambió (venta ÷ facturas).',
    tip: D => num(D.vpt_anterior) > 0 ? `El año pasado era ${dinero(D.vpt_anterior)} por tiquete; hoy van en ${dinero(D.ticket)}.` : 'Si sale "Sin dato" es porque el informe de ese corte no trae el año anterior.' },
  { claves: ['UPT AÑO ANTERIOR', 'VARIACIÓN UPT'], titulo: 'UPT frente al año anterior',
    que: 'Las prendas por compra del mismo período del año pasado y cuánto cambió.',
    tip: 'Si bajó, refuercen la venta sugerida: mostrar la prenda que combina con lo que ya eligió el cliente.' },
  { claves: ['UPT'], titulo: 'UPT (unidades por tiquete)',
    que: 'Cuántas prendas lleva en promedio cada cliente por compra.',
    tip: 'Sugieran el conjunto completo: si lleva una blusa, muéstrenle el pantalón o el accesorio que combina.' },
  { claves: ['UNIDADES'], titulo: 'Unidades vendidas', que: 'El total de prendas vendidas en el mes.',
    tip: 'Si suben las unidades pero no la venta, revisen si se están vendiendo más prendas de precio bajo.' },
  { claves: ['VENTAS ASESORAS'], titulo: 'Ventas de asesoras', que: 'La venta registrada a nombre de las asesoras.',
    tip: 'Revisen que cada venta quede a nombre de quien atendió, para que el ranking sea justo.' },
  { claves: ['FACTURAS PARA LLEGAR AL 20'], titulo: 'Facturas para llegar al 20 %',
    que: 'Cuántas facturas más tendrían que llevar en el mes para que la conversión llegue al 20 % (20 de cada 100 personas que entran compran). También dice cuántas se dejan de hacer en promedio por día.',
    tip: 'La tabla de conversión diaria muestra cuántas faltaron cada día; revisen los días en rojo y qué pasó en la atención.' },
  { claves: ['VENTA QUE SE DEJA DE HACER'], titulo: 'Venta que se deja de hacer',
    que: 'Lo que habrían vendido de más si llegaran al 20 % de conversión: facturas que faltan × valor por tiquete (VPT).',
    tip: 'Cada cliente que entra y no compra es venta que se va. Saludar, ofrecer ayuda y acompañar al probador la recupera.' },
  { claves: ['EVOLUCIÓN DIARIA DE CONVERSIÓN', 'CONVERSIÓN'], titulo: 'Conversión',
    que: 'De cada 100 personas que entran a la tienda, cuántas compran (facturas ÷ tráfico).',
    tip: D => { const c = conversionMes(D); return (c ? `Este mes compran ${Math.round(c * 100)} de cada 100 personas. ` : '') + 'Saludar rápido, ofrecer ayuda y acompañar al probador la sube.'; } }
];

/* ---------- Utilidades ---------- */
function el(tag, clase, texto) {
  const n = document.createElement(tag);
  if (clase) n.className = clase;
  if (texto != null) n.textContent = texto;
  return n;
}
function num(v) { const n = parseFloat(v); return isFinite(n) ? n : 0; }
function pct(v) { return (num(v) * 100).toFixed(1) + '%'; }
function dinero(v) { return '$' + new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Math.max(0, Math.round(num(v)))); }
function primerNombre(n) { return String(n || '').trim().split(/\s+/)[0] || ''; }
function nombreUsuario() {
  const n = document.querySelector('.lh-user-name');
  const t = n ? n.textContent.trim().replace(/\s+/g, ' ') : '';
  if (!t || t === 'Usuario') return '';
  return t.length > 24 ? primerNombre(t) : t;
}
function leer(almacen, k) { try { return almacen.getItem(k); } catch (e) { return null; } }
function guardar(almacen, k, v) { try { almacen.setItem(k, v); } catch (e) { /* sin almacenamiento */ } }
