/* ================================================================
   Hilo 3D · mascota del inicio de sesión de L&H Pulse
   Entra caminando y saluda; mira lo que escribes, se tapa los ojos en la
   contraseña, avisa si las mayúsculas están activadas, gira soltando hilo
   mientras se valida, se preocupa con un error, se enreda si fallan varias
   veces seguidas y celebra al entrar.
   No modifica el formulario: solo observa foco, teclas, botón y mensajes.
   ================================================================ */
import { crearHilo, hayWebGL, prefiereQuieto, temporadaActual } from './hilo_motor.js';

const tarjeta = document.querySelector('.login-card');
const ANCHO = 300, ALTO = 280;

if (tarjeta && hayWebGL()) iniciar();

function iniciar() {
  const raiz = document.createElement('div');
  raiz.className = 'hilo3d';
  raiz.setAttribute('aria-hidden', 'true');
  const burbuja = document.createElement('div');
  burbuja.className = 'hilo3d-burbuja';
  burbuja.setAttribute('aria-hidden', 'true');
  document.body.appendChild(raiz);
  document.body.appendChild(burbuja);

  const hilo = crearHilo({
    ancho: ANCHO, alto: ALTO, quieto: prefiereQuieto(), pasear: true, irAlMirar: true,
    temporada: temporadaActual(), sueno: 40,
    alDormir: dormido => {
      raiz.classList.toggle('dormido', dormido);
      if (!dormido) decir('¡Ay! No estaba dormido…', 2200);
    },
    mover: x => { raiz.style.transform = `translateX(${x.toFixed(1)}px)`; },
    visible: () => !raiz.hidden
  });
  raiz.appendChild(hilo.canvas);

  // Cosquillas: al darle clic se ríe (solo con el mouse; es decorativo)
  const toque = document.createElement('div');
  toque.className = 'hilo3d-toque';
  raiz.appendChild(toque);
  const RISAS = ['¡Jaja, cosquillas!', '¡Ay, para, para!', '¡Jijiji!', '¡Me vas a desenrollar!'];
  let risa = 0;
  toque.addEventListener('click', () => {
    if (!['reposo', 'saluda', 'mira', 'dormido', 'despierta', 'risa'].includes(hilo.estado())) return;
    hilo.poner('risa');
    decir(RISAS[risa++ % RISAS.length], 1800);
  });

  /* ---------- Zona libre a la izquierda del formulario ---------- */
  let xMax = 0;
  function ubicar() {
    const r = tarjeta.getBoundingClientRect();
    let tope = r.left;
    const ben = document.querySelector('.benefits > *');
    if (ben) tope = Math.min(tope, ben.getBoundingClientRect().left + ANCHO * 0.35);
    xMax = Math.max(0, tope + window.scrollX - ANCHO - 6);
    if (window.innerWidth < 1000 || xMax < 60) { raiz.hidden = true; burbuja.hidden = true; return; }
    raiz.hidden = false; burbuja.hidden = false;
    raiz.style.left = '0px';
    raiz.style.top = Math.round(r.bottom + window.scrollY - ALTO + 66) + 'px';
    hilo.limites(0, xMax);
  }
  window.addEventListener('resize', ubicar);

  /* ---------- Burbuja ---------- */
  function decir(texto, ms) {
    clearTimeout(decir.r);
    if (!texto) { burbuja.classList.remove('visible'); return; }
    burbuja.textContent = texto;
    const r = raiz.getBoundingClientRect(), tope = tarjeta.getBoundingClientRect().left;
    const ancho = burbuja.offsetWidth || 200;
    burbuja.style.left = Math.round(Math.max(8, Math.min(r.left + window.scrollX + r.width * 0.42, tope + window.scrollX - ancho - 14))) + 'px';
    burbuja.style.top = Math.round(r.top + window.scrollY + 22 - (burbuja.offsetHeight || 38)) + 'px';
    burbuja.classList.add('visible');
    if (ms) decir.r = setTimeout(() => burbuja.classList.remove('visible'), ms);
  }
  function volverLuego(estado, ms) {
    setTimeout(() => { if (hilo.estado() === estado) hilo.poner(segunFoco()); }, ms);
  }

  /* ---------- Campos ---------- */
  const usuario = document.getElementById('correo'), clave = document.getElementById('password');
  let mayusculas = false;
  function segunFoco() {
    const a = document.activeElement;
    if (a === clave) return mayusculas ? 'senala' : 'tapa';
    if (a === usuario) return 'mira';
    return 'reposo';
  }
  function ocupado() { const e = hilo.estado(); return e === 'feliz' || e === 'carga' || e === 'enredado'; }

  if (usuario) usuario.addEventListener('focus', () => { if (!ocupado()) { hilo.poner('mira'); decir('Escribe tu usuario'); } });
  if (clave) {
    clave.addEventListener('focus', () => {
      if (ocupado()) return;
      if (mayusculas) avisarMayusculas(); else { hilo.poner('tapa'); decir('No estoy mirando, lo prometo'); }
    });
    // Mayúsculas activadas: se destapa y señala el campo
    const revisar = e => {
      if (!e.getModifierState) return;
      const antes = mayusculas;
      mayusculas = e.getModifierState('CapsLock');
      if (antes === mayusculas || ocupado() || document.activeElement !== clave) return;
      if (mayusculas) avisarMayusculas();
      else { hilo.poner('tapa'); decir('No estoy mirando, lo prometo'); }
    };
    clave.addEventListener('keydown', revisar);
    clave.addEventListener('keyup', revisar);
  }
  function avisarMayusculas() { hilo.poner('senala', { lado: 1 }); decir('Ojo: tienes las mayúsculas activadas'); }

  document.addEventListener('focusout', () => setTimeout(() => {
    const a = document.activeElement, e = hilo.estado();
    if (a !== usuario && a !== clave && (e === 'mira' || e === 'tapa' || e === 'senala')) { hilo.poner('reposo'); decir(''); }
  }, 0));

  /* ---------- Validando: gira soltando hilo ---------- */
  const boton = document.getElementById('btnLogin');
  let enviando = false, errores = 0;
  if (boton && window.MutationObserver) new MutationObserver(() => {
    const cargando = boton.classList.contains('loading-active');
    if (cargando && !enviando) { enviando = true; hilo.poner('carga'); decir('Revisando tus datos…'); }
    else if (!cargando && enviando) {
      // El mensaje de error llega en el mismo instante: se deja que lo cuente primero
      setTimeout(() => {
        enviando = false;
        if (hilo.estado() === 'carga') { hilo.poner(segunFoco()); decir(''); }
      }, 0);
    }
  }).observe(boton, { attributes: true, attributeFilter: ['class'] });

  /* ---------- Resultado ---------- */
  const mensaje = document.getElementById('mensaje');
  if (mensaje && window.MutationObserver) new MutationObserver(() => {
    if (mensaje.classList.contains('error')) {
      if (enviando) errores++; // solo cuentan las respuestas del servidor, no los campos vacíos
      if (enviando && errores >= 3) {
        hilo.poner('enredado');
        decir('¡Me enredé! Si no recuerdas tu contraseña, pide ayuda al administrador', 5600);
        volverLuego('enredado', 4600);
      } else {
        hilo.poner('error'); decir('Uy, revisa tus datos', 3200);
        volverLuego('error', 2600);
      }
    } else if (mensaje.classList.contains('exito')) { hilo.poner('feliz'); decir('¡Listo, adelante!'); }
  }).observe(mensaje, { attributes: true, attributeFilter: ['class'] });

  /* ---------- Entrada: llega caminando y saluda ---------- */
  ubicar();
  const destino = Math.min(xMax, 30);
  hilo.entrar(-ANCHO, destino, () => {
    if (hilo.estado() !== 'reposo') return;
    hilo.poner('saluda'); decir('Hola, soy Hilo', 3000);
    volverLuego('saluda', 2400);
  });
  setTimeout(() => raiz.classList.add('visible'), 150);

  window.__hilo3d = { poner: (n, o) => hilo.poner(n, o), estado: hilo.estado, extra: hilo.extra, errores: () => errores };
}
