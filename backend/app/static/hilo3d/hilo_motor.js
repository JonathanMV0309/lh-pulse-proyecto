/* ================================================================
   Hilo 3D · motor compartido (login y dashboard de tienda)
   Modelo hecho en código con Three.js, con texturas tomadas del Hilo original.
   Cada página (anfitrión) decide dónde va, qué dice y cuándo cambia de estado.

   Estados: reposo · mira · tapa · error · feliz · saluda · carga · senala
            enredado · animo · concentra · explica · dormido · despierta · risa · aplaude
   Extras propios en reposo: paseo · estira · mirar
   Temporada: sombrero de bruja en octubre y gorro navideño en diciembre
   ================================================================ */
import * as THREE from './three.module.min.js';
import { RoomEnvironment } from './RoomEnvironment.js';

const BASE = new URL('.', import.meta.url).href;

export function hayWebGL() {
  try { const c = document.createElement('canvas'); return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl'))); } catch (e) { return false; }
}
// Sombrero según el mes (se puede forzar con ?hiloTemporada=halloween|navidad|ninguna)
export function temporadaActual() {
  try {
    const forzada = new URLSearchParams(location.search).get('hiloTemporada');
    if (forzada) return forzada === 'ninguna' ? null : forzada;
  } catch (e) { /* sin URL */ }
  const m = new Date().getMonth();
  return m === 9 ? 'halloween' : m === 11 ? 'navidad' : null;
}
export function prefiereQuieto() {
  try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; }
}

/*  op: ancho, alto, quieto (sin saltos, paseos ni giros), pasear, irAlMirar,
        ideas ('muchas' | 'pocas'), fps, maxPixelRatio, temporada,
        sueno (segundos sin actividad para dormirse; 0 = nunca), alDormir(dormido),
        mover(x) para desplazar el elemento, visible() para pausar  */
export function crearHilo(op) {
  const ANCHO = op.ancho, ALTO = op.alto, quieto = !!op.quieto;
  const pasear = op.pasear !== false && !quieto;
  const pausaCuadro = 1 / (op.fps || 60) - 0.002;

  /* ---------- Escena ---------- */
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, op.maxPixelRatio || 2));
  renderer.setSize(ANCHO, ALTO);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping; // respeta el tono y la saturación de las texturas reales
  renderer.toneMappingExposure = 0.95;

  const escena = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  escena.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  escena.environmentIntensity = 0.55;

  const camara = new THREE.PerspectiveCamera(30, ANCHO / ALTO, 0.1, 50);
  if (op.temporada) { camara.position.set(0.25, 0.62, 8.0); camara.lookAt(0.25, 0.2, 0); } // espacio para el sombrero
  else { camara.position.set(0.25, 0.45, 7.2); camara.lookAt(0.25, -0.02, 0); }

  escena.add(new THREE.HemisphereLight(0xfff3e2, 0x9c7a55, 0.5));
  const luzClave = new THREE.DirectionalLight(0xfff0d8, 2.1); luzClave.position.set(-3.5, 4.5, 5); escena.add(luzClave);
  const luzRelleno = new THREE.DirectionalLight(0xffe6c4, 0.55); luzRelleno.position.set(4, 1, 4); escena.add(luzRelleno);
  const luzBorde = new THREE.DirectionalLight(0xffe2b8, 1.0); luzBorde.position.set(3, 3, -4); escena.add(luzBorde);

  /* ---------- Texturas (recortes del Hilo original) ---------- */
  const cargador = new THREE.TextureLoader();
  function textura(nombre, ru, rv, color) {
    const t = cargador.load(BASE + nombre);
    t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace; t.anisotropy = 8;
    t.wrapS = t.wrapT = THREE.MirroredRepeatWrapping;
    t.repeat.set(ru, rv);
    return t;
  }
  const texHilo = textura('textura_hilo.jpg', 6.5, 2.6, true);
  const texHiloRelieve = textura('textura_hilo.jpg', 6.5, 2.6, false);
  const texMadera = textura('textura_madera.jpg', 3, 1, true);
  const texSombra = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
    const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    gr.addColorStop(0, 'rgba(60,40,22,0.6)'); gr.addColorStop(0.5, 'rgba(60,40,22,0.2)'); gr.addColorStop(1, 'rgba(60,40,22,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
    return new THREE.CanvasTexture(c);
  })();

  /* ---------- Materiales (colores medidos del original) ---------- */
  const matMadera = new THREE.MeshStandardMaterial({ map: texMadera, color: 0xFFF6EC, bumpMap: texMadera, bumpScale: 0.22, roughness: 0.5, metalness: 0 });
  const matHilo = new THREE.MeshStandardMaterial({ map: texHilo, bumpMap: texHiloRelieve, bumpScale: 0.6, roughness: 0.8 });
  const matHebra = new THREE.MeshPhysicalMaterial({ color: 0xE6B972, roughness: 0.42, metalness: 0.05, sheen: 0.6, sheenColor: 0xFFE2A8, sheenRoughness: 0.5 });
  const matOjo = new THREE.MeshPhysicalMaterial({ color: 0x241812, roughness: 0.14, clearcoat: 1, clearcoatRoughness: 0.05 });
  const matBrillo = new THREE.MeshBasicMaterial({ color: 0xFFFDF8 });
  const matAguja = new THREE.MeshStandardMaterial({ color: 0xE2B04E, metalness: 1, roughness: 0.2 });
  const matHueco = new THREE.MeshStandardMaterial({ color: 0x6b4526, roughness: 0.9 });

  /* ---------- Modelo (proporciones del original) ---------- */
  const PISO = -1.04, RHILO = 0.66, RTAPA = 0.82;
  const cuerpo = new THREE.Group(); cuerpo.position.y = PISO; escena.add(cuerpo); // pivote en el piso
  const carrete = new THREE.Group(); carrete.position.y = -PISO; cuerpo.add(carrete);

  function tapa(y) {
    const R = RTAPA, T = 0.26, r = 0.115, pts = [new THREE.Vector2(0, -T / 2)];
    for (let i = 0; i <= 10; i++) { const a = -Math.PI / 2 + (i / 10) * (Math.PI / 2); pts.push(new THREE.Vector2(R - r + Math.cos(a) * r, -T / 2 + r + Math.sin(a) * r)); }
    for (let i = 0; i <= 10; i++) { const a = (i / 10) * (Math.PI / 2); pts.push(new THREE.Vector2(R - r + Math.cos(a) * r, T / 2 - r + Math.sin(a) * r)); }
    pts.push(new THREE.Vector2(0, T / 2));
    const m = new THREE.Mesh(new THREE.LatheGeometry(pts, 72), matMadera); m.position.y = y; carrete.add(m);
  }
  tapa(0.92); tapa(-0.92);
  const hueco = new THREE.Mesh(new THREE.CircleGeometry(0.075, 32), matHueco);
  hueco.rotation.x = -Math.PI / 2; hueco.position.y = 1.042; carrete.add(hueco);
  carrete.add(new THREE.Mesh(new THREE.CylinderGeometry(RHILO, RHILO, 1.62, 96, 1, true), matHilo));

  // Ojos: óvalos negros grandes con su reflejo arriba a la derecha (como el original)
  function crearOjo(lado) {
    const g = new THREE.Group();
    const o = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 28), matOjo); o.scale.set(0.12, 0.165, 0.055); g.add(o);
    const b = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), matBrillo); b.scale.set(0.03, 0.038, 0.012); b.position.set(0.03, 0.06, 0.052); g.add(b);
    const matCeja = new THREE.MeshStandardMaterial({ color: 0x2b1f17, roughness: 0.5, transparent: true, opacity: 0 });
    const ceja = new THREE.Mesh(new THREE.CapsuleGeometry(0.02, 0.13, 4, 10), matCeja); ceja.position.set(0, 0.25, 0.02); g.add(ceja);
    carrete.add(g);
    return { g, o, b, ceja, lado, k: -0.38, y: 0.25 };
  }
  const ojos = [crearOjo(-1), crearOjo(1)];
  function ponerOjo(ojo, mx, my, abierto, grande) {
    const ang = ojo.lado * 0.33 + mx * 0.12, y = 0.22 + my * 0.07;
    ojo.g.position.set(Math.sin(ang) * (RHILO + 0.006), y, Math.cos(ang) * (RHILO + 0.006));
    ojo.g.rotation.y = ang;
    ojo.o.scale.set(0.12 * grande, 0.165 * grande * Math.max(0.05, abierto), 0.055);
    ojo.b.visible = abierto > 0.45;
  }
  // Cejas por estado: [inclinación, altura]. Negativo = preocupado, positivo = concentrado.
  const CEJAS = { error: [-0.38, 0.25], enredado: [-0.38, 0.25], concentra: [0.2, 0.22], senala: [-0.14, 0.29] };

  // Aguja dorada clavada entre las vueltas del hilo (lado izquierdo)
  const aguja = new THREE.Group();
  aguja.add(new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.005, 1.0, 14), matAguja));
  const ojoAguja = new THREE.Mesh(new THREE.TorusGeometry(0.034, 0.012, 10, 24), matAguja); ojoAguja.scale.set(0.7, 1.7, 1); ojoAguja.position.y = 0.52; aguja.add(ojoAguja);
  aguja.position.set(-0.47, 0.16, 0.44); aguja.rotation.set(0.1, -0.78, 0.24); carrete.add(aguja);

  // Sombrero de temporada (encima de la tapa superior, un poco ladeado)
  if (op.temporada === 'halloween' || op.temporada === 'navidad') {
    const sombrero = new THREE.Group();
    const punta = new THREE.Group();
    if (op.temporada === 'halloween') {
      const tela = new THREE.MeshStandardMaterial({ color: 0x3A2B47, roughness: 0.75 });
      const cinta = new THREE.MeshStandardMaterial({ color: 0xE08A2E, roughness: 0.5 });
      const ala = new THREE.Mesh(new THREE.CylinderGeometry(0.64, 0.64, 0.035, 56), tela); ala.position.y = 0.02; sombrero.add(ala);
      const copa = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.36, 0.55, 40), tela); copa.position.y = 0.3; sombrero.add(copa);
      const banda = new THREE.Mesh(new THREE.CylinderGeometry(0.345, 0.362, 0.1, 40), cinta); banda.position.y = 0.09; sombrero.add(banda);
      const pico = new THREE.Mesh(new THREE.ConeGeometry(0.2, 0.42, 32), tela); pico.position.y = 0.21; punta.add(pico);
      punta.position.set(0, 0.56, 0); punta.rotation.z = -0.75; sombrero.add(punta);
    } else {
      const rojo = new THREE.MeshPhysicalMaterial({ color: 0xB8322E, roughness: 0.8, sheen: 0.8, sheenColor: 0xff9a8a });
      const blanco = new THREE.MeshStandardMaterial({ color: 0xF6F1E8, roughness: 0.95 });
      const borde = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.1, 16, 48), blanco); borde.rotation.x = Math.PI / 2; borde.position.y = 0.06; sombrero.add(borde);
      const gorro = new THREE.Mesh(new THREE.ConeGeometry(0.5, 0.7, 40), rojo); gorro.position.y = 0.4; sombrero.add(gorro);
      const caida = new THREE.Mesh(new THREE.ConeGeometry(0.17, 0.4, 28), rojo); caida.position.y = 0.17; punta.add(caida);
      const pompon = new THREE.Mesh(new THREE.SphereGeometry(0.12, 20, 14), blanco); pompon.position.y = 0.38; punta.add(pompon);
      punta.position.set(0.04, 0.64, 0); punta.rotation.z = -1.25; sombrero.add(punta);
    }
    sombrero.position.set(0.06, 1.05, 0); sombrero.rotation.set(0.05, 0, -0.14);
    carrete.add(sombrero);
  }

  // Hebra que lo enreda (se dibuja de a poco cuando se enreda)
  const vueltas = [];
  for (let i = 0; i <= 160; i++) {
    const s = i / 160, a = s * Math.PI * 2 * 2.5 - 0.9, r = RHILO + 0.04;
    vueltas.push(new THREE.Vector3(Math.sin(a) * r, 0.6 - s * 1.2 + Math.sin(s * Math.PI * 5) * 0.05, Math.cos(a) * r));
  }
  const geoEnredo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(vueltas), 220, 0.028, 8, false);
  const totalEnredo = geoEnredo.index.count;
  const enredo = new THREE.Mesh(geoEnredo, matHebra); enredo.visible = false; carrete.add(enredo);
  let avanceEnredo = 0;

  // Bracitos de hilo con su lazo (se rehacen cada cuadro según la pose)
  const POSES = {
    reposo: l => [[0.65 * l, -0.08, 0.12], [0.92 * l, -0.27, 0.2], [1.04 * l, -0.5, 0.24]],
    tapa: l => [[0.65 * l, -0.08, 0.12], [0.74 * l, 0.0, 0.5], [0.27 * l, 0.22, 0.7]],
    saluda: () => [[0.65, -0.08, 0.12], [0.98, 0.28, 0.2], [1.04, 0.78, 0.24]],
    cintura: l => [[0.65 * l, -0.08, 0.12], [0.86 * l, -0.32, 0.4], [0.55 * l, -0.42, 0.58]],
    arriba: l => [[0.65 * l, -0.08, 0.12], [0.95 * l, 0.2, 0.15], [1.0 * l, 0.62, 0.18]],
    senala: l => [[0.65 * l, -0.08, 0.12], [1.0 * l, 0.0, 0.24], [1.4 * l, 0.08, 0.32]],
    menton: l => [[0.65 * l, -0.08, 0.12], [0.74 * l, -0.36, 0.48], [0.3 * l, -0.12, 0.74]],
    panza: l => [[0.65 * l, -0.08, 0.12], [0.8 * l, -0.35, 0.45], [0.35 * l, -0.32, 0.72]],
    explica: l => [[0.65 * l, -0.08, 0.12], [0.95 * l, 0.08, 0.3], [0.98 * l, 0.42, 0.42]],
    aplaude: l => [[0.65 * l, -0.08, 0.12], [0.78 * l, -0.12, 0.5], [0.16 * l, -0.06, 0.8]],
    pegado: l => [[0.65 * l, -0.08, 0.12], [0.7 * l, -0.3, 0.12], [0.68 * l, -0.52, 0.1]]
  };
  function crearBrazo(l) {
    const malla = new THREE.Mesh(new THREE.BufferGeometry(), matHebra);
    const lazo = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.03, 12, 28), matHebra);
    carrete.add(malla); carrete.add(lazo);
    return { l, malla, lazo, pose: POSES.reposo(l).map(v => v.slice()), destino: 'reposo' };
  }
  const brazos = [crearBrazo(-1), crearBrazo(1)];
  const tA = new THREE.Vector3(), tB = new THREE.Vector3(), puntos3 = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
  function actualizarBrazo(b, k, extra) {
    const meta = (POSES[b.destino] || POSES.reposo)(b.l);
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) b.pose[i][j] += (meta[i][j] + (extra ? extra[i][j] : 0) - b.pose[i][j]) * k;
    for (let i = 0; i < 3; i++) puntos3[i].set(b.pose[i][0], b.pose[i][1], b.pose[i][2]);
    const curva = new THREE.CatmullRomCurve3(puntos3);
    b.malla.geometry.dispose(); b.malla.geometry = new THREE.TubeGeometry(curva, 20, 0.033, 10, false);
    curva.getPoint(1, tA); curva.getTangent(1, tB);
    b.lazo.position.copy(tA).addScaledVector(tB, 0.085);
    b.lazo.rotation.set(0, 0, Math.atan2(tB.y, tB.x) - Math.PI / 2); // de frente, como en el original
  }

  // Cola de hilo: pulso · nudo · corazón · suelta (coordenadas relativas al piso del personaje)
  const cola = new THREE.Mesh(new THREE.BufferGeometry(), matHebra); cuerpo.add(cola);
  const N = 72, colaPts = Array.from({ length: N }, () => new THREE.Vector3());
  const pA = new THREE.Vector3(), pB = new THREE.Vector3();
  function puntoCola(modo, s, t, salida) {
    if (modo === 'corazon') {
      if (s < 0.25) { const u = s / 0.25; return salida.set(0.62 + u * 0.42, 0.26 + u * 0.5, 0.35 + u * 0.15); }
      const u = (s - 0.25) / 0.75 * Math.PI * 2, k = 0.026;
      const hx = 16 * Math.pow(Math.sin(u), 3), hy = 13 * Math.cos(u) - 5 * Math.cos(2 * u) - 2 * Math.cos(3 * u) - Math.cos(4 * u);
      return salida.set(1.04 + hx * k, 0.94 + hy * k, 0.5);
    }
    if (modo === 'suelta') { // el hilo se va soltando mientras gira
      const b = Math.min(1, s * 3);
      return salida.set(0.62 + s * 1.5, 0.28 - b * 0.26 + Math.sin(s * 14 - t * 9) * 0.045 * b, 0.3 + s * 0.2);
    }
    const x = 0.74 + s * 1.15, z = 0.32 + s * 0.25;
    let y = 0.02;
    if (s < 0.12) y = 0.26 - (s / 0.12) * 0.24;
    if (modo === 'nudo') {
      const c = Math.max(0, 1 - Math.abs(s - 0.5) / 0.22), a = (s - 0.28) / 0.44 * Math.PI * 4;
      return salida.set(x - c * Math.sin(a) * 0.14, y + c * (0.14 + Math.cos(a) * 0.14), z + c * Math.cos(a) * 0.08);
    }
    const latido = Math.pow(Math.max(0, Math.sin(t * Math.PI * 2 / 1.25)), 6);
    const d = s - 0.6, ecg = (Math.exp(-((d + 0.05) ** 2) / 0.0009) - Math.exp(-((d - 0.03) ** 2) / 0.0012) * 0.6) * (0.25 + latido * 0.75);
    return salida.set(x, y + ecg * 0.42, z);
  }
  let colaModo = 'pulso', colaMezcla = 1, colaPrev = 'pulso';
  function actualizarCola(t, dt) {
    colaMezcla = Math.min(1, colaMezcla + dt * 2.2);
    const e = colaMezcla * colaMezcla * (3 - 2 * colaMezcla);
    for (let i = 0; i < N; i++) {
      const s = i / (N - 1);
      puntoCola(colaPrev, s, t, pA); puntoCola(colaModo, s, t, pB);
      colaPts[i].copy(pA).lerp(pB, e);
    }
    cola.geometry.dispose();
    cola.geometry = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(colaPts), 120, 0.03, 10, false);
  }
  function cambiarCola(m) { if (m === colaModo) return; colaPrev = colaModo; colaModo = m; colaMezcla = 0; }

  // Sombra suave de contacto
  const sombra = new THREE.Mesh(new THREE.PlaneGeometry(2.7, 1.25), new THREE.MeshBasicMaterial({ map: texSombra, transparent: true, depthWrite: false }));
  sombra.rotation.x = -Math.PI / 2; sombra.position.set(0.12, PISO - 0.001, 0.05); escena.add(sombra);

  /* ---------- Estado ---------- */
  let estado = 'reposo', tEstado = 0, extra = '', tExtra = 0, lado = 1, saltos = 2;
  const mira = { x: 0, y: 0, tx: 0, ty: 0 };
  let parpado = 1, proximoParpadeo = 2, parpadeando = 0, grande = 1;
  let inclinar = 0, girar = 0, giroCarrete = 0;
  function poner(n, o) {
    if (estado === 'dormido' && n !== 'dormido' && op.alDormir) op.alDormir(false);
    if (n === 'dormido' && estado !== 'dormido' && op.alDormir) op.alDormir(true);
    estado = n; tEstado = 0;
    lado = o && o.lado ? o.lado : 1;
    saltos = o && o.saltos ? o.saltos : 2;
    if (extra !== 'paseo') extra = '';
  }

  let mouse = null, actividad = performance.now();
  window.addEventListener('pointermove', e => { mouse = { x: e.clientX, y: e.clientY, t: performance.now() }; despertar(); });
  ['pointerdown', 'keydown', 'wheel', 'focusin', 'scroll'].forEach(ev => window.addEventListener(ev, despertar, { passive: true }));
  function despertar() {
    actividad = performance.now();
    if (estado === 'dormido') poner('despierta');
  }
  function centroHilo() { const r = renderer.domElement.getBoundingClientRect(); return { x: r.left + r.width * 0.42, y: r.top + r.height * 0.45 }; }
  function mirarA(px, py) {
    const c = centroHilo();
    mira.tx = THREE.MathUtils.clamp((px - c.x) / 420, -1, 1);
    mira.ty = THREE.MathUtils.clamp(-(py - c.y) / 320, -1, 1);
  }

  /* ---------- Desplazamiento (lo pinta el anfitrión con op.mover) ---------- */
  let x = 0, xDestino = 0, xMin = 0, xMax = 0, direccion = 1, entrando = false, alLlegar = null;
  function mover() { if (op.mover) op.mover(x); }
  function limites(a, b) {
    xMin = a; xMax = Math.max(a, b);
    if (!entrando) { x = Math.min(Math.max(x, xMin), xMax); xDestino = Math.min(Math.max(xDestino, xMin), xMax); mover(); }
  }
  function entrar(desde, hasta, cb) {
    if (!pasear) { x = xDestino = hasta; mover(); if (cb) cb(); return; }
    x = desde; xDestino = hasta; direccion = 1; extra = 'paseo'; tExtra = 0; entrando = true; alLlegar = cb || null; mover();
  }

  /* ---------- Animación ---------- */
  const inicio = performance.now() / 1000;
  let ultimo = inicio, proximaIdea = op.ideas === 'pocas' ? 20 : 6;
  function cuadro() {
    requestAnimationFrame(cuadro);
    const ahora = performance.now() / 1000;
    if (ahora - ultimo < pausaCuadro) return;
    const dt = Math.min(ahora - ultimo, 0.05), t = ahora - inicio;
    ultimo = ahora;
    if (document.hidden || (op.visible && !op.visible())) return; // no gasta recursos si no se ve
    tEstado += dt; tExtra += dt;

    // Se duerme si nadie usa la página; los estados cortos vuelven solos a reposo
    if (op.sueno && estado === 'reposo' && !extra && performance.now() - actividad > op.sueno * 1000) poner('dormido');
    if ((estado === 'despierta' && tEstado > 1.0) || (estado === 'risa' && tEstado > 1.7)) poner('reposo');

    // Ideas propias cuando está tranquilo: pasear, estirarse o mirar alrededor
    if (estado === 'reposo' && !extra) {
      proximaIdea -= dt;
      if (proximaIdea <= 0) {
        const r = Math.random();
        if (pasear && r < 0.5 && xMax - xMin > 60) {
          xDestino = xMin + Math.random() * (xMax - xMin);
          if (Math.abs(xDestino - x) > 40) { extra = 'paseo'; direccion = xDestino > x ? 1 : -1; }
        } else if (!quieto && r < 0.75) extra = 'estira';
        else extra = 'mirar';
        tExtra = 0;
        proximaIdea = op.ideas === 'pocas' ? 18 + Math.random() * 20 : 8 + Math.random() * 7;
      }
    }
    if (op.irAlMirar && pasear && estado === 'mira' && Math.abs(xMax - x) > 4 && extra !== 'paseo') { xDestino = xMax; extra = 'paseo'; direccion = 1; tExtra = 0; }

    // Desplazamiento con saltitos (más rápido al entrar a la página)
    let saltito = 0;
    if (extra === 'paseo') {
      const paso = (entrando ? 200 : 95) * dt * Math.sign(xDestino - x);
      if (Math.abs(xDestino - x) <= Math.abs(paso)) {
        x = xDestino; extra = '';
        if (entrando) { entrando = false; const cb = alLlegar; alLlegar = null; if (cb) cb(); }
      } else { x += paso; saltito = Math.abs(Math.sin(tExtra * Math.PI / 0.32)) * 0.16; }
      mover();
    }
    const caminando = extra === 'paseo';

    // Dónde mira
    const activo = document.activeElement;
    if (estado === 'mira' && !caminando && activo && activo.getBoundingClientRect) {
      const r = activo.getBoundingClientRect(), avance = Math.min(1, (activo.value || '').length / 18);
      mirarA(r.left + 40 + avance * (r.width - 80), r.top + r.height / 2);
    } else if (caminando) { mira.tx = direccion * 0.6; mira.ty = -0.1; }
    else if (extra === 'mirar') { mira.tx = Math.sin(tExtra * 1.6) * 0.8; mira.ty = 0.15; if (tExtra > 3.9) extra = ''; }
    else if (mouse && performance.now() - mouse.t < 3500) mirarA(mouse.x, mouse.y);
    else { mira.tx = Math.sin(t * 0.33) * 0.3; mira.ty = Math.sin(t * 0.47) * 0.1; }
    if (estado === 'tapa' || estado === 'animo') { mira.tx = 0; mira.ty = 0.05; }
    if (estado === 'error') { mira.tx = 0; mira.ty = -0.25; }
    if (estado === 'carga') { mira.tx = 0; mira.ty = 0.25; }
    if (estado === 'senala') { mira.tx = lado * 0.75; mira.ty = 0.1; }
    if (estado === 'concentra') { mira.tx = -0.25; mira.ty = -0.2; }
    if (estado === 'enredado') { mira.tx = Math.cos(t * 6) * 0.45; mira.ty = Math.sin(t * 6) * 0.25; } // mareado
    if (estado === 'explica' || estado === 'risa' || estado === 'despierta' || estado === 'aplaude') { mira.tx = 0; mira.ty = 0.05; }
    if (estado === 'dormido') { mira.tx = 0; mira.ty = -0.15; }
    const kM = Math.min(1, dt * 7);
    mira.x += (mira.tx - mira.x) * kM; mira.y += (mira.ty - mira.y) * kM;

    // Parpadeo natural (a veces doble) y ojos grandes si el cursor se le acerca
    proximoParpadeo -= dt;
    if (proximoParpadeo <= 0) { parpadeando = 0.17; proximoParpadeo = Math.random() < 0.2 ? 0.3 : 2.2 + Math.random() * 3.6; }
    if (parpadeando > 0) { parpadeando -= dt; parpado = Math.abs(Math.cos((1 - Math.max(0, parpadeando) / 0.17) * Math.PI)); }
    else parpado += (1 - parpado) * Math.min(1, dt * 18);
    let cerca = false;
    if (mouse && performance.now() - mouse.t < 1500) { const c = centroHilo(); cerca = Math.hypot(mouse.x - c.x, mouse.y - c.y) < 110; }
    const tamOjos = estado === 'despierta' ? 1.3 : estado === 'enredado' ? 0.86 : (cerca || estado === 'feliz' || estado === 'animo' || estado === 'risa' || estado === 'aplaude' ? 1.12 : 1);
    grande += (tamOjos - grande) * Math.min(1, dt * 8);
    const abierto = estado === 'tapa' ? 0.12 : estado === 'dormido' ? 0.06 : estado === 'risa' ? 0.32
      : estado === 'feliz' && tEstado > saltos * 0.8 ? 0.55 : estado === 'concentra' ? parpado * 0.72 : estado === 'despierta' ? 1 : parpado;
    const kC = Math.min(1, dt * 9), ceja = CEJAS[estado];
    ojos.forEach(o => {
      ponerOjo(o, mira.x, mira.y, abierto, grande);
      if (ceja) { o.k += (ceja[0] - o.k) * kC; o.y += (ceja[1] - o.y) * kC; }
      o.ceja.rotation.z = Math.PI / 2 + o.lado * o.k; o.ceja.position.y = o.y;
      o.ceja.material.opacity += ((ceja ? 1 : 0) - o.ceja.material.opacity) * kC;
    });

    // Cuerpo: respiración + inclinación + giro + saltos
    const respira = estado === 'dormido' ? Math.sin(t * 1.3) * 0.03 : Math.sin(t * 2.1) * 0.014;
    let incObj = 0, girObj = mira.x * 0.22;
    if (caminando) { incObj = -0.06 * direccion; girObj = 0.5 * direccion; }
    else if (estado === 'mira') { incObj = -0.1; girObj = 0.35; }
    else if (estado === 'tapa') { incObj = 0.04; girObj = 0; }
    else if (estado === 'senala') { incObj = -lado * 0.05; girObj = lado * 0.3; }
    else if (estado === 'concentra') { incObj = 0.05; girObj = -0.15; }
    else if (estado === 'saluda' || estado === 'explica') girObj = 0.1;
    else if (estado === 'dormido') { incObj = 0.09; girObj = 0; }
    let sacude = 0;
    if (estado === 'error' && tEstado < 0.9) sacude = Math.sin(tEstado * 32) * (quieto ? 0.03 : 0.12) * (1 - tEstado / 0.9);
    if (estado === 'enredado') sacude = Math.sin(t * 3) * (quieto ? 0.015 : 0.05);
    if (estado === 'carga' && quieto) sacude = Math.sin(t * 2) * 0.04;
    if (estado === 'risa') sacude = Math.sin(t * 28) * (quieto ? 0.03 : 0.09) * Math.max(0, 1 - tEstado / 1.6);
    const timido = estado === 'tapa' ? Math.sin(t * 3) * 0.025 : 0;
    let salto = quieto ? 0 : saltito;
    if (!quieto && estado === 'feliz' && tEstado < saltos * 0.8) { const u = (tEstado % 0.8) / 0.8; salto = Math.sin(u * Math.PI) * 0.45; }
    if (!quieto && estado === 'animo' && tEstado < 1.2) { const u = (tEstado % 0.6) / 0.6; salto = Math.sin(u * Math.PI) * 0.22; }
    if (!quieto && estado === 'despierta' && tEstado < 0.5) salto = Math.sin(tEstado / 0.5 * Math.PI) * 0.3; // sobresalto
    if (!quieto && estado === 'risa' && tEstado < 0.45) salto = Math.sin(tEstado / 0.45 * Math.PI) * 0.18;
    if (!quieto && estado === 'aplaude') salto = Math.abs(Math.sin(tEstado * Math.PI / 0.55)) * 0.07;
    let estira = 0;
    if (extra === 'estira') { estira = Math.sin(Math.min(1, tExtra / 1.8) * Math.PI) * 0.07; if (tExtra > 1.8) extra = ''; }
    inclinar += (incObj - inclinar) * Math.min(1, dt * 6); girar += (girObj - girar) * Math.min(1, dt * 5);
    cuerpo.rotation.z = inclinar + sacude + timido; cuerpo.rotation.y = girar;
    cuerpo.position.y = PISO + salto;
    const aterriza = !quieto && ((estado === 'feliz' && salto < 0.04 && tEstado > 0.05 && tEstado < saltos * 0.8 + 0.1) ? 0.06 : (caminando && saltito < 0.02 ? 0.04 : 0));
    cuerpo.scale.set(1 + aterriza - estira * 0.4, 1 + respira - aterriza + estira, 1 + aterriza - estira * 0.4);
    sombra.scale.setScalar(1 - salto * 0.45); sombra.material.opacity = 1 - salto * 0.9;

    // Cargando: el carrete gira soltando hilo; al terminar vuelve de frente
    if (estado === 'carga' && !quieto) giroCarrete += dt * 6.5;
    else { const frente = Math.round(giroCarrete / (Math.PI * 2)) * Math.PI * 2; giroCarrete += (frente - giroCarrete) * Math.min(1, dt * 5); }
    carrete.rotation.y = giroCarrete;

    // Se enreda de a poco y se desenreda al salir del estado
    const metaEnredo = estado === 'enredado' ? 1 : 0;
    avanceEnredo += (metaEnredo - avanceEnredo) * Math.min(1, dt * (metaEnredo ? 1.8 : 4));
    enredo.visible = avanceEnredo > 0.01;
    geoEnredo.setDrawRange(0, Math.floor(totalEnredo * avanceEnredo / 6) * 6);

    // Bracitos
    const ex = estado === 'aplaude' ? 'aplaude' : estado === 'error' ? 'cintura' : estado === 'enredado' ? 'pegado' : estado === 'animo' ? 'arriba' : estado === 'risa' ? 'panza'
      : estado === 'despierta' ? 'arriba' : extra === 'estira' ? 'arriba' : 'reposo';
    brazos[0].destino = estado === 'tapa' ? 'tapa' : estado === 'senala' && lado === -1 ? 'senala' : estado === 'explica' ? 'explica' : ex;
    brazos[1].destino = estado === 'tapa' ? 'tapa' : estado === 'feliz' || estado === 'saluda' ? 'saluda' : estado === 'concentra' ? 'menton' : estado === 'senala' && lado === 1 ? 'senala' : ex;
    const vaiven = Math.sin(t * 2.1) * 0.03, balanceo = caminando ? Math.sin(tExtra * Math.PI / 0.32) * 0.08 : 0;
    brazos.forEach((b, i) => {
      let mov = null;
      if (b.destino === 'saluda') mov = [[0, 0, 0], [0, 0, 0], [Math.sin(t * 11) * (quieto ? 0.05 : 0.13), 0, 0]];
      else if (b.destino === 'senala') mov = [[0, 0, 0], [0, 0, 0], [lado * Math.sin(t * 6) * 0.05, 0, 0]];
      else if (b.destino === 'aplaude') mov = [[0, 0, 0], [0, 0, 0], [b.l * (0.5 + 0.5 * Math.sin(t * 15)) * (quieto ? 0.05 : 0.15), 0, 0]];
      else if (b.destino === 'explica') mov = [[0, 0, 0], [0, 0, 0], [0, Math.sin(t * 4) * 0.04, 0]];
      else if (b.destino === 'arriba' && estado === 'animo') mov = [[0, 0, 0], [0, 0, 0], [0, Math.sin(t * 8 + i * Math.PI) * (quieto ? 0.03 : 0.08), 0]];
      else if (b.destino === 'reposo') mov = [[0, 0, 0], [0, vaiven, balanceo * (i ? 1 : -1)], [0, vaiven * 1.6, balanceo * (i ? 1.6 : -1.6)]];
      actualizarBrazo(b, Math.min(1, dt * 9), mov);
    });

    // Cola
    cambiarCola(estado === 'feliz' || estado === 'risa' || estado === 'aplaude' ? 'corazon' : estado === 'error' || estado === 'enredado' ? 'nudo' : estado === 'carga' ? 'suelta' : 'pulso');
    actualizarCola(t, dt);

    renderer.render(escena, camara);
  }
  requestAnimationFrame(cuadro);

  return {
    canvas: renderer.domElement,
    poner,
    estado: () => estado,
    extra: () => extra,
    entrar,
    limites,
    x: () => x,
    entrando: () => entrando
  };
}
