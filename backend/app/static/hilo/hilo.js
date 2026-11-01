/* ================================================================
   Hilo · mascota del inicio de sesión de L&H Pulse (cuerpo entero)
   No modifica el formulario ni su lógica: solo observa
   - foco en usuario  -> camina hacia el formulario y se inclina a mirar
   - foco en clave    -> se voltea tímido ("No estoy mirando, lo prometo")
   - mensaje "error"  -> se sacude ("Uy, revisa tus datos")
   - mensaje "exito"  -> salta de alegría ("¡Listo, adelante!")
   En reposo respira, parpadea y de vez en cuando da un paseo corto.
   Si el video no carga, queda la imagen fija: el login funciona igual.
   ================================================================ */
(function () {
  'use strict';
  var BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
  var TAM = 200, MARGEN = 20;
  var FRASES = {
    saludo: 'Hola, soy Hilo',
    mira: 'Escribe tu usuario',
    timido: 'No estoy mirando, lo prometo',
    error: 'Uy, revisa tus datos',
    feliz: '¡Listo, adelante!'
  };

  var tarjeta = document.querySelector('.login-card');
  if (!tarjeta) return;

  var raiz = document.createElement('div');
  raiz.className = 'hilo hilo--reposo';
  raiz.setAttribute('aria-hidden', 'true');
  raiz.innerHTML = '<div class="hilo__giro"><div class="hilo__cuerpo"><img src="' + BASE + 'cuerpo_poster.jpg" alt=""></div></div>';
  var burbuja = document.createElement('div');
  burbuja.className = 'hilo-burbuja';
  burbuja.setAttribute('aria-hidden', 'true');
  document.body.appendChild(raiz);
  document.body.appendChild(burbuja);

  var video = document.createElement('video');
  video.muted = true; video.defaultMuted = true; video.playsInline = true; video.loop = true;
  video.setAttribute('muted', ''); video.setAttribute('playsinline', '');
  video.preload = 'auto';
  video.src = BASE + 'cuerpo_reposo.mp4';
  video.addEventListener('playing', function () { video.classList.add('activo'); });
  raiz.querySelector('.hilo__cuerpo').appendChild(video);
  var p = video.play(); if (p && p.catch) p.catch(function () { /* sin reproducción automática: queda la imagen */ });

  var estado = 'reposo', base = 'reposo', x = 0, arriba = 0, reloj = 0, paseo = 0, relojBurbuja = 0;
  function poner(n) { raiz.classList.remove('hilo--' + estado); estado = n; raiz.classList.add('hilo--' + estado); }
  function mirarA(dir) { raiz.style.setProperty('--hilo-dir', dir); }
  function moverA(nx) { x = Math.round(nx); raiz.style.setProperty('--hilo-x', x + 'px'); }

  // Zona libre: entre el borde izquierdo y el formulario, sin tocar los beneficios de abajo
  function limites() {
    var tope = tarjeta.getBoundingClientRect().left;
    var ben = document.querySelector('.benefits > *');
    if (ben) tope = Math.min(tope, ben.getBoundingClientRect().left);
    return { min: MARGEN, max: Math.max(MARGEN, tope + window.scrollX - TAM - 16), tope: tarjeta.getBoundingClientRect().left + window.scrollX };
  }
  function ubicar() {
    var r = tarjeta.getBoundingClientRect(), l = limites();
    if (window.innerWidth < 1000 || l.max - l.min < 40) { raiz.hidden = true; burbuja.hidden = true; return false; }
    raiz.hidden = false; burbuja.hidden = false;
    arriba = Math.round(r.bottom + window.scrollY - TAM + 40); // los pies quedan sobre la onda
    raiz.style.top = arriba + 'px';
    raiz.style.left = '0px';
    moverA(Math.min(Math.max(x, l.min), l.max));
    return true;
  }

  function decir(texto, ms) {
    clearTimeout(relojBurbuja);
    if (!texto) { burbuja.classList.remove('visible'); return; }
    burbuja.textContent = texto;
    var l = limites(), ancho = burbuja.offsetWidth || 200;
    var izq = Math.min(x + TAM * 0.5, l.tope - ancho - 14);
    burbuja.style.left = Math.max(8, Math.round(izq)) + 'px';
    burbuja.style.top = Math.round(arriba + 6 - (burbuja.offsetHeight || 38)) + 'px';
    burbuja.classList.add('visible');
    if (ms) relojBurbuja = setTimeout(function () { burbuja.classList.remove('visible'); }, ms);
  }

  function pasear() {
    clearTimeout(paseo);
    paseo = setTimeout(function () {
      if (base === 'reposo' && estado === 'reposo' && !raiz.hidden) {
        var l = limites(), destino = l.min + Math.random() * (l.max - l.min);
        if (Math.abs(destino - x) > 40) {
          decir('');
          mirarA(destino < x ? -1 : 1);
          poner('paseo'); moverA(destino);
          clearTimeout(reloj);
          reloj = setTimeout(function () { if (estado === 'paseo') { poner('reposo'); mirarA(1); } }, 2600);
        }
      }
      pasear();
    }, 7000 + Math.random() * 6000);
  }

  function reaccion(tipo, duracion) {
    clearTimeout(reloj); poner(tipo);
    reloj = setTimeout(function () { poner(base); }, duracion);
  }

  var usuario = document.getElementById('correo'), clave = document.getElementById('password');
  if (usuario) usuario.addEventListener('focus', function () {
    if (estado === 'feliz') return;
    base = 'mira'; clearTimeout(reloj); mirarA(1); moverA(limites().max); poner('mira'); decir(FRASES.mira);
  });
  if (clave) clave.addEventListener('focus', function () {
    if (estado === 'feliz') return;
    base = 'timido'; clearTimeout(reloj); mirarA(-1); poner('timido'); decir(FRASES.timido);
  });
  document.addEventListener('focusout', function () {
    setTimeout(function () {
      var a = document.activeElement;
      if (a !== usuario && a !== clave && base !== 'reposo' && estado !== 'feliz') {
        base = 'reposo'; mirarA(1); if (estado === 'mira' || estado === 'timido') poner('reposo'); decir('');
      }
    }, 0);
  });

  var mensaje = document.getElementById('mensaje');
  if (mensaje && window.MutationObserver) {
    new MutationObserver(function () {
      if (mensaje.classList.contains('error')) { mirarA(1); reaccion('error', 800); decir(FRASES.error, 3200); }
      else if (mensaje.classList.contains('exito')) { clearTimeout(reloj); mirarA(1); base = 'feliz'; poner('feliz'); decir(FRASES.feliz); }
    }).observe(mensaje, { attributes: true, attributeFilter: ['class'] });
  }

  window.addEventListener('resize', ubicar);
  if (ubicar()) moverA(limites().min + 30);
  setTimeout(function () { raiz.classList.add('hilo--visible'); }, 400);
  setTimeout(function () { if (estado === 'reposo' && !raiz.hidden) decir(FRASES.saludo, 3000); }, 1600);
  pasear();
})();
