/* ================================================================
   Dónde se para Hilo para hablar
   1. Busca un espacio libre (sin tarjetas, tablas, gráficas ni textos)
      donde quepan él y lo que va a decir, y salta hasta ahí.
   2. Si lo que va a decir es largo y no hay espacio, abre su panel a la
      derecha («modo conversación»): el menú de la izquierda se reduce a
      íconos, toda la página se corre y Hilo salta adentro del panel.
   3. Al terminar vuelve a su esquina.
   En pantallas angostas se queda en la esquina como siempre.
   ================================================================ */
const HILO_W = 176, HILO_H = 164;
const CUERPO = { x: 34, y: 16, w: 108, h: 148 };   // parte visible de Hilo dentro del lienzo
const CELDA = 8;
const CAJON_W = 392;
const CAJON_MIN_PANTALLA = 1100;
const ALTO_CORTO = 340;           // lo que mide menos que esto sale junto a Hilo, como antes
const quieto = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

export function crearEscena({ raiz, burbuja, hilo, alCerrarCajon }) {
  let sitio = null;              // {x, y} esquina superior izquierda de Hilo; null = su esquina
  let lado = -1;                 // -1: lo que dice queda a su izquierda · 1: a su derecha
  let enCajon = false, cajon = null, moviendo = null;
  const mostrados = new Map();   // nodo -> { alCerrar, alto }
  let regreso = 0;

  const mismo = (a, b) => Math.abs(a.x - b.x) < 2 && Math.abs(a.y - b.y) < 2;
  const casa = () => ({ x: innerWidth - 12 - HILO_W, y: innerHeight - 4 - HILO_H });
  const actual = () => sitio || casa();

  /* ---------- Mapa de lo que hay en pantalla ---------- */
  function zona() {
    const top = (document.querySelector('.lh-topbar')?.getBoundingClientRect().bottom || 0) + 8;
    const sb = document.querySelector('.lh-sidebar');
    const r = sb && sb.getBoundingClientRect();
    const izq = (r && r.right > 0 && getComputedStyle(sb).visibility !== 'hidden' ? r.right : 0) + 8;
    const der = innerWidth - (enCajon ? CAJON_W : 0) - 8;
    return { top, izq, der, abajo: innerHeight - 4 };
  }

  function mapa() {
    const z = zona();
    const cols = Math.ceil(innerWidth / CELDA), filas = Math.ceil(innerHeight / CELDA);
    const ocupado = new Uint8Array(cols * filas);
    const marcar = (l, t, r, b) => {
      const c0 = Math.max(0, Math.floor(l / CELDA)), c1 = Math.min(cols - 1, Math.floor((r - 1) / CELDA));
      const f0 = Math.max(0, Math.floor(t / CELDA)), f1 = Math.min(filas - 1, Math.floor((b - 1) / CELDA));
      for (let f = f0; f <= f1; f++) ocupado.fill(1, f * cols + c0, f * cols + c1 + 1);
    };
    // Fuera de la zona útil = ocupado
    marcar(0, 0, innerWidth, z.top); marcar(0, 0, z.izq, innerHeight);
    marcar(z.der, 0, innerWidth, innerHeight); marcar(0, z.abajo, innerWidth, innerHeight);

    const raizContenido = document.getElementById('lhMainContent') || document.querySelector('main') || document.body;
    const areaZona = Math.max(1, (z.der - z.izq) * (z.abajo - z.top));
    for (const n of raizContenido.querySelectorAll('*')) {
      const r = n.getBoundingClientRect();
      if (r.width < 3 || r.height < 3 || r.bottom <= z.top || r.top >= z.abajo || r.right <= z.izq || r.left >= z.der) continue;
      if (esContenido(n, r, areaZona)) marcar(r.left - 6, r.top - 6, r.right + 6, r.bottom + 6);
    }
    // Tabla de sumas para contar celdas ocupadas en cualquier rectángulo
    const W = cols + 1, suma = new Uint32Array(W * (filas + 1));
    for (let f = 0; f < filas; f++) {
      let fila = 0;
      for (let c = 0; c < cols; c++) {
        fila += ocupado[f * cols + c];
        suma[(f + 1) * W + c + 1] = suma[f * W + c + 1] + fila;
      }
    }
    const cuenta = (l, t, w, h) => {
      const c0 = Math.floor(l / CELDA), f0 = Math.floor(t / CELDA);
      const c1 = Math.ceil((l + w) / CELDA), f1 = Math.ceil((t + h) / CELDA);
      if (c0 < 0 || f0 < 0 || c1 > cols || f1 > filas) return Infinity;
      return suma[f1 * W + c1] - suma[f0 * W + c1] - suma[f1 * W + c0] + suma[f0 * W + c0];
    };
    return { z, cuenta };
  }

  function esContenido(n, r, areaZona) {
    const tag = n.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEMPLATE' || tag === 'BR') return false;
    const cs = getComputedStyle(n);
    if (cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.5 || cs.display === 'contents') return false;
    let texto = false;
    for (const h of n.childNodes) if (h.nodeType === 3 && h.textContent.trim()) { texto = true; break; }
    if (texto) return true;
    // Adornos (confeti, luces, brillos) no cuentan como información
    if (cs.pointerEvents === 'none') return false;
    if (/^(IMG|SVG|CANVAS|VIDEO|IFRAME|INPUT|SELECT|TEXTAREA|BUTTON|TABLE)$/.test(tag)) return true;
    if (r.width * r.height > areaZona * 0.7) return false; // contenedores de toda la página
    const fondo = cs.backgroundColor;
    return (fondo && fondo !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(fondo))
      || cs.backgroundImage !== 'none' || cs.boxShadow !== 'none'
      || parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle !== 'none' && parseFloat(cs.borderLeftWidth) > 0;
  }

  /* ---------- Dónde va lo que dice, según dónde esté Hilo ---------- */
  function cajaContenido(p, w, h, ladoC, tipo) {
    const base = tipo === 'burbuja' ? p.y + 72 : p.y + 146;
    const x = ladoC < 0 ? p.x + 10 - w : p.x + HILO_W - 10;
    return { x, y: Math.max(base - h, 0), w, h };
  }

  function buscarSitio(w, h, tipo) {
    const { z, cuenta } = mapa();
    const preferido = actual();
    const tolerancia = (a) => Math.max(1, Math.floor(a / (CELDA * CELDA) * 0.01));
    const libre = (p, ladoC) => {
      if (p.x + CUERPO.x < z.izq || p.y + CUERPO.y < z.top || p.x + CUERPO.x + CUERPO.w > z.der || p.y + HILO_H > z.abajo + 4) return false;
      const c = cajaContenido(p, w, h, ladoC, tipo);
      if (c.x < z.izq || c.x + c.w > z.der || c.y < z.top || c.y + c.h > z.abajo) return false;
      return cuenta(p.x + CUERPO.x, p.y + CUERPO.y, CUERPO.w, Math.min(CUERPO.h, z.abajo - p.y - CUERPO.y)) <= tolerancia(CUERPO.w * CUERPO.h)
        && cuenta(c.x, c.y, c.w, c.h) <= tolerancia(c.w * c.h);
    };
    // ¿Sirve donde ya está?
    if (libre(preferido, lado)) return { p: preferido, lado };
    if (libre(preferido, -lado)) return { p: preferido, lado: -lado };
    let mejor = null, costo = Infinity;
    const paso = 16;
    for (let y = z.top - CUERPO.y; y <= z.abajo - HILO_H + 4; y += paso) {
      for (let x = z.izq - CUERPO.x; x <= z.der - CUERPO.x - CUERPO.w; x += paso) {
        const d = Math.hypot(x - preferido.x, (y - preferido.y) * 1.3);
        if (d >= costo) continue;
        for (const l of [lado, -lado]) {
          const c = d + (l !== lado ? 30 : 0);
          if (c < costo && libre({ x, y }, l)) { mejor = { p: { x, y }, lado: l }; costo = c; }
        }
      }
    }
    return mejor;
  }

  /* ---------- Saltar ---------- */
  function moverA(p, { saltar = true } = {}) {
    const desde = actual(), h = casa();
    const destino = p || h;
    sitio = p && (Math.abs(p.x - h.x) > 2 || Math.abs(p.y - h.y) > 2) ? p : null;
    const fin = `${Math.round(destino.x - h.x)}px ${Math.round(destino.y - h.y)}px`;
    if (moviendo) moviendo.cancel();
    const distancia = Math.hypot(destino.x - desde.x, destino.y - desde.y);
    if (!saltar || quieto() || distancia < 4 || raiz.hidden) {
      raiz.style.translate = fin;
      return Promise.resolve();
    }
    const ini = `${Math.round(desde.x - h.x)}px ${Math.round(desde.y - h.y)}px`;
    const alto = Math.min(desde.y, destino.y) - h.y - Math.min(140, 50 + distancia * 0.18);
    const medio = `${Math.round((desde.x + destino.x) / 2 - h.x)}px ${Math.round(alto)}px`;
    if (hilo) hilo.poner('feliz');
    raiz.classList.add('saltando');
    moviendo = raiz.animate(
      [{ translate: ini }, { translate: medio, offset: 0.48, easing: 'cubic-bezier(.3,.7,.5,1)' }, { translate: fin }],
      { duration: Math.min(820, 420 + distancia * 0.35), easing: 'cubic-bezier(.45,.05,.55,.95)' }
    );
    raiz.style.translate = fin;
    return moviendo.finished.catch(() => {}).then(() => { moviendo = null; raiz.classList.remove('saltando'); });
  }

  function colocar(nodo, w, h, tipo) {
    const p = actual();
    const c = cajaContenido(p, w, h, lado, tipo);
    nodo.style.left = Math.round(c.x) + 'px';
    nodo.style.top = Math.round(c.y) + 'px';
    nodo.style.right = 'auto';
    nodo.style.bottom = 'auto';
    nodo.style.transformOrigin = lado < 0 ? '100% 100%' : '0% 100%';
    nodo.classList.toggle('lado-der', lado > 0);
  }

  function soltarEstilo(nodo) {
    ['left', 'top', 'right', 'bottom', 'transformOrigin'].forEach(k => { nodo.style[k] = ''; });
    nodo.classList.remove('lado-der');
  }

  function medir(nodo) {
    const r = nodo.getBoundingClientRect();
    return { w: Math.ceil(r.width) || 300, h: Math.ceil(r.height) || 120 };
  }

  function programarRegreso() {
    clearTimeout(regreso);
    regreso = setTimeout(() => {
      if (enCajon || mostrados.size || burbuja.classList.contains('visible') || !sitio) return;
      lado = -1;
      moverA(null);
    }, 2600);
  }

  /* ---------- Lo que se llama desde Hilo ---------- */
  // Antes de mostrar la burbuja: si tapa algo, busca dónde pararse.
  async function hablar() {
    clearTimeout(regreso);
    if (enCajon) { burbuja.classList.remove('visible'); return; }
    if (innerWidth < 900 || mostrados.size) { reubicarBurbuja(); return; }
    const { w, h } = medir(burbuja);
    const r = buscarSitio(w, h, 'burbuja');
    if (r && (!mismo(r.p, actual()) || r.lado !== lado)) {
      const cambia = !mismo(r.p, actual());
      lado = r.lado;
      if (cambia) {
        const texto = burbuja.textContent;
        burbuja.classList.remove('visible');
        await moverA(r.p);
        if (burbuja.textContent !== texto) return;
        colocar(burbuja, w, h, 'burbuja');
        burbuja.classList.add('visible');
        return;
      }
    }
    reubicarBurbuja();
  }
  function reubicarBurbuja() {
    if (!sitio && lado < 0) { soltarEstilo(burbuja); return; }
    const { w, h } = medir(burbuja);
    colocar(burbuja, w, h, 'burbuja');
  }
  function callo() { programarRegreso(); }

  // Paneles (Para revisar, Meta de hoy, explicaciones, mensajes, tarjetas)
  // corto: mensajes como el «?» o los de la administración; si no hay espacio libre salen
  // junto a Hilo en su esquina (como antes) en vez de abrir el panel de la derecha.
  async function mostrar(nodo, { alCerrar, forzarCajon = false, corto = false } = {}) {
    clearTimeout(regreso);
    mostrados.set(nodo, { alCerrar });
    burbuja.classList.remove('visible');
    if (enCajon) { alCajon(nodo); return 'cajon'; }
    if (innerWidth < 900) return 'esquina';
    const { w, h } = medir(nodo);
    const r = forzarCajon ? null : buscarSitio(w, h, 'panel');
    if (r) {
      lado = r.lado;
      if (!mismo(r.p, actual())) {
        nodo.style.visibility = 'hidden';
        await moverA(r.p);
        nodo.style.visibility = '';
      }
      if (mostrados.has(nodo)) colocar(nodo, w, h, 'panel');
      return 'libre';
    }
    if (innerWidth >= CAJON_MIN_PANTALLA && !corto && h > ALTO_CORTO) {
      await abrirCajon();
      if (mostrados.has(nodo)) alCajon(nodo);
      return 'cajon';
    }
    lado = -1;
    soltarEstilo(nodo);
    if (sitio) { nodo.style.visibility = 'hidden'; await moverA(null); nodo.style.visibility = ''; }
    return 'esquina';
  }
  function soltar(nodo) {
    if (!mostrados.has(nodo)) return;
    mostrados.delete(nodo);
    const envoltura = nodo.closest('.hilo-cajon-tarjeta');
    if (envoltura) {
      document.body.append(nodo);
      envoltura.remove();
    }
    nodo.classList.remove('en-cajon');
    soltarEstilo(nodo);
    programarRegreso();
  }

  /* ---------- Modo conversación ---------- */
  function armarCajon() {
    const a = document.createElement('aside');
    a.className = 'hilo-cajon';
    a.setAttribute('aria-label', 'Conversación con Hilo');
    a.innerHTML = `
      <div class="hilo-cajon-cab">
        <div class="hilo-cajon-sitio" aria-hidden="true"></div>
        <div class="hilo-cajon-titulos">
          <strong>Hilo</strong>
          <small>Tu compañero de resultados</small>
          <p class="hilo-cajon-dice" aria-live="polite"></p>
        </div>
        <div class="hilo-cajon-botones"></div>
      </div>
      <div class="hilo-cajon-atajos" role="toolbar" aria-label="Qué te muestro"></div>
      <div class="hilo-cajon-feed" aria-live="polite"></div>
      <form class="hilo-cajon-preguntar" autocomplete="off">
        <label class="visually-hidden" for="hiloPregunta">Pregúntale a Hilo</label>
        <input id="hiloPregunta" type="text" maxlength="160" placeholder="Pregúntale a Hilo…" enterkeyhint="send">
        <button type="submit" aria-label="Preguntar"><i class="bi bi-send-fill" aria-hidden="true"></i></button>
      </form>`;
    const cerrar = document.createElement('button');
    cerrar.type = 'button'; cerrar.className = 'hilo-cajon-boton'; cerrar.title = 'Cerrar (Esc)';
    cerrar.setAttribute('aria-label', 'Cerrar la conversación con Hilo');
    cerrar.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
    cerrar.addEventListener('click', () => cerrarCajon());
    a.querySelector('.hilo-cajon-botones').append(cerrar);
    document.body.append(a);
    const c = {
      raiz: a,
      feed: a.querySelector('.hilo-cajon-feed'),
      dice: a.querySelector('.hilo-cajon-dice'),
      atajos: a.querySelector('.hilo-cajon-atajos'),
      botones: a.querySelector('.hilo-cajon-botones'),
      form: a.querySelector('form'),
      input: a.querySelector('input'),
    };
    return c;
  }

  function sitioEnCajon() {
    return { x: innerWidth - CAJON_W + 4, y: 2 };
  }

  async function abrirCajon() {
    if (enCajon || innerWidth < CAJON_MIN_PANTALLA) return enCajon;
    if (!cajon) cajon = armarCajon();
    enCajon = true;
    clearTimeout(regreso);
    burbuja.classList.remove('visible');
    // Lo que estaba flotando pasa adentro del panel
    mostrados.forEach((_, nodo) => alCajon(nodo));
    document.body.classList.add('hilo-conversando');
    cajon.raiz.classList.add('abierto');
    raiz.classList.add('en-cajon');
    avisarCambioDeTamano();
    await new Promise(r => setTimeout(r, quieto() ? 0 : 260));
    lado = 1;
    await moverA(sitioEnCajon());
    return true;
  }

  async function cerrarCajon() {
    if (!enCajon) return;
    enCajon = false;
    Array.from(mostrados.entries()).forEach(([nodo, info]) => { if (info.alCerrar) info.alCerrar(); else soltar(nodo); });
    document.body.classList.remove('hilo-conversando');
    cajon.raiz.classList.remove('abierto');
    cajon.dice.textContent = '';
    avisarCambioDeTamano();
    lado = -1;
    await moverA(null);
    raiz.classList.remove('en-cajon');
    if (alCerrarCajon) alCerrarCajon();
  }

  function alCajon(nodo) {
    if (!cajon) cajon = armarCajon();
    soltarEstilo(nodo);
    nodo.classList.add('en-cajon');
    const anterior = nodo.closest('.hilo-cajon-tarjeta');
    if (anterior) anterior.remove();
    const item = document.createElement('div');
    item.className = 'hilo-cajon-item hilo-cajon-tarjeta';
    cajon.feed.append(item);
    item.append(nodo);
    bajar(item);
  }

  function bajar(item) {
    requestAnimationFrame(() => {
      if (!cajon) return;
      const f = cajon.feed;
      const objetivo = item.offsetTop - 8;
      f.scrollTo({ top: Math.max(0, Math.min(objetivo, f.scrollHeight)), behavior: quieto() ? 'auto' : 'smooth' });
    });
  }

  // Burbujas de conversación dentro del panel
  function decirEnCajon(texto, { quien = 'hilo', nodo = null } = {}) {
    if (!cajon) cajon = armarCajon();
    const item = document.createElement('div');
    item.className = `hilo-cajon-item hilo-cajon-${quien}`;
    if (texto) {
      const p = document.createElement('p');
      p.className = 'hilo-cajon-globo';
      p.textContent = texto;
      item.append(p);
    }
    if (nodo) { nodo.classList.add('hilo-tarjeta'); item.append(nodo); }
    cajon.feed.append(item);
    // No guardar conversaciones eternas
    while (cajon.feed.children.length > 60) cajon.feed.firstElementChild.remove();
    bajar(item);
    return item;
  }

  function avisarCambioDeTamano() {
    // Gráficas y mapas recalculan su ancho cuando la página termina de correrse
    setTimeout(() => window.dispatchEvent(new Event('resize')), quieto() ? 30 : 380);
  }

  /* ---------- Si cambia la página bajo sus pies ---------- */
  let esperaScroll = 0;
  addEventListener('scroll', () => {
    clearTimeout(esperaScroll);
    esperaScroll = setTimeout(() => {
      if (enCajon || innerWidth < 900) return;
      if (burbuja.classList.contains('visible') && !mostrados.size) hablar();
      else if (mostrados.size === 1) {
        const [nodo] = mostrados.keys();
        if (nodo.isConnected && !nodo.hidden) recolocar(nodo);
      }
    }, 350);
  }, { passive: true });
  async function recolocar(nodo) {
    const { w, h } = medir(nodo);
    const r = buscarSitio(w, h, 'panel');
    if (!r) return;
    lado = r.lado;
    if (!mismo(r.p, actual())) { nodo.style.visibility = 'hidden'; await moverA(r.p); nodo.style.visibility = ''; }
    colocar(nodo, w, h, 'panel');
  }
  let esperaTam = 0;
  addEventListener('resize', () => {
    clearTimeout(esperaTam);
    esperaTam = setTimeout(() => {
      if (enCajon && innerWidth < CAJON_MIN_PANTALLA) { cerrarCajon(); return; }
      if (enCajon) { moverA(sitioEnCajon(), { saltar: false }); return; }
      if (sitio) { sitio = null; lado = -1; raiz.style.translate = ''; mostrados.forEach((_, n) => soltarEstilo(n)); soltarEstilo(burbuja); }
    }, 200);
  });

  return {
    hablar, callo, mostrar, soltar, abrirCajon, cerrarCajon, decirEnCajon,
    cajonAbierto: () => enCajon,
    puedeCajon: () => innerWidth >= CAJON_MIN_PANTALLA,
    cajon: () => (cajon || (cajon = armarCajon())),
    lado: () => lado,
    sitio: () => ({ ...actual() }),
    // Para pruebas: dónde se pararía para un contenido de este tamaño
    probar: (w, h, tipo = 'panel') => buscarSitio(w, h, tipo),
  };
}
