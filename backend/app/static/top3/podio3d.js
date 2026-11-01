/* =========================================================
   Podio 3D de la ceremonia Top 3 (L&H Pulse)
   Recrea el podio del video (crema, bordes café/dorado, números
   dorados, corona, confeti, haces de luz e hilo dorado en el piso)
   con las tiendas integradas: nombre y % grabados en el frente del
   bloque y la foto de la tienda en un medallón sobre él.
   Usa la misma copia de Three.js que Hilo (sin internet).
   ========================================================= */
import * as THREE from '../hilo3d/three.module.min.js';
import { RoomEnvironment } from '../hilo3d/RoomEnvironment.js';

const C = {
    fondo: 0xE6DCCC,
    crema: 0xF2ECE2,
    cremaTapa: 0xF7F3EC,
    cafe: 0x8C7764,
    cafeOscuro: 0x5C4F44,
    oro: 0xD2AE62,
    hilo: 0xEBC57F
};

// Bloques: posición, altura y tiempos de aparición (segundos)
const BLOQUES = {
    1: { x: 0, h: 2.85, sube: 3.0 },
    2: { x: -3.2, h: 2.2, sube: 1.6 },
    3: { x: 3.2, h: 1.62, sube: 0.35 }
};
const ANCHO = 3.12, FONDO = 2.6, RADIO = 0.34;
const FIN = 6.4; // momento en que la escena queda completa

const facil = {
    salida: t => 1 - Math.pow(1 - t, 3),
    rebote: t => { const c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
    suave: t => t * t * (3 - 2 * t)
};
const tramo = (t, a, b) => Math.min(1, Math.max(0, (t - a) / (b - a)));

/* ---------- Geometrías ---------- */
function cajaRedondeada(w, d, alto, r, bisel) {
    const s = new THREE.Shape();
    const x = -w / 2, y = -d / 2;
    s.moveTo(x + r, y);
    s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + d - r); s.quadraticCurveTo(x + w, y + d, x + w - r, y + d);
    s.lineTo(x + r, y + d); s.quadraticCurveTo(x, y + d, x, y + d - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    const g = new THREE.ExtrudeGeometry(s, {
        depth: Math.max(0.001, alto - 2 * bisel), bevelEnabled: bisel > 0, bevelThickness: bisel,
        bevelSize: bisel, bevelSegments: 4, curveSegments: 10
    });
    g.rotateX(-Math.PI / 2);          // la extrusión pasa a ser vertical
    g.translate(0, bisel, 0);
    g.computeVertexNormals();
    return g;
}

function textoGrabado(numero, tienda, puesto, anchoCara, altoCara) {
    const escala = 340;
    const cw = Math.round(anchoCara * escala), ch = Math.round(altoCara * escala);
    const cv = document.createElement('canvas'); cv.width = cw; cv.height = ch;
    const g = cv.getContext('2d');
    g.clearRect(0, 0, cw, ch);
    // Número dorado con relieve
    const tamNum = Math.min(ch * (puesto === 3 ? 0.5 : 0.56), cw * 0.42);
    const yNum = ch * (puesto === 3 ? 0.4 : 0.43);
    g.font = `700 ${tamNum}px Georgia, "Times New Roman", serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillStyle = 'rgba(70, 50, 25, .35)';
    g.fillText(numero, cw / 2 + tamNum * 0.025, yNum + tamNum * 0.035);
    const oro = g.createLinearGradient(0, yNum - tamNum / 2, 0, yNum + tamNum / 2);
    oro.addColorStop(0, '#F3DCA0'); oro.addColorStop(0.45, '#C99B4C'); oro.addColorStop(1, '#8E6A2E');
    g.fillStyle = oro;
    g.fillText(numero, cw / 2, yNum);
    // Nombre y cumplimiento grabados debajo
    if (tienda) {
        const nombre = String(tienda.nombre || 'Tienda').toUpperCase();
        let tam = Math.min(ch * 0.11, cw * 0.075);
        g.font = `800 ${tam}px Inter, "Segoe UI", Arial, sans-serif`;
        while (g.measureText(nombre).width > cw * 0.86 && tam > 10) { tam -= 1; g.font = `800 ${tam}px Inter, "Segoe UI", Arial, sans-serif`; }
        const yNom = ch * (puesto === 3 ? 0.76 : 0.78);
        g.fillStyle = 'rgba(255,255,255,.55)';
        g.fillText(nombre, cw / 2, yNom + 1.5);
        g.fillStyle = '#5E4E3E';
        g.fillText(nombre, cw / 2, yNom);
        const pct = (Number(tienda.cumplimiento || 0) * 100).toFixed(1) + '%';
        const tamPct = tam * 0.92;
        g.font = `800 ${tamPct}px Inter, "Segoe UI", Arial, sans-serif`;
        g.fillStyle = '#A57C33';
        g.fillText(pct, cw / 2, yNom + tam * 1.25);
    }
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    return tex;
}

function texturaIniciales(nombre) {
    const cv = document.createElement('canvas'); cv.width = cv.height = 512;
    const g = cv.getContext('2d');
    const fondo = g.createRadialGradient(256, 200, 40, 256, 256, 300);
    fondo.addColorStop(0, '#FBF6EC'); fondo.addColorStop(1, '#E3D3B5');
    g.fillStyle = fondo; g.fillRect(0, 0, 512, 512);
    const partes = String(nombre || '?').replace(/[^A-Za-zÁÉÍÓÚÑ0-9 ]/g, ' ').trim().split(/\s+/);
    const ini = ((partes[0] || '?')[0] + ((partes[1] || '')[0] || '')).toUpperCase();
    g.fillStyle = '#9C7631'; g.font = '700 200px Georgia, serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText(ini, 256, 270);
    const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.center.set(0.5, 0.5); t.rotation = Math.PI / 2; return t;
}

function cargarFoto(tienda) {
    const codigo = String(tienda.codigo || '').trim().replace(/\s+/g, '-').replace(/[^a-zA-Z0-9_-]/g, '').toUpperCase();
    const rutas = codigo ? ['jpg', 'jpeg', 'png', 'webp'].flatMap(ext => [`/static/img/tiendas/${codigo}.${ext}`, `/static/images/tiendas/${codigo}.${ext}`]) : [];
    const cargador = new THREE.TextureLoader();
    return new Promise(resolve => {
        let i = 0;
        const intentar = () => {
            if (i >= rutas.length) { resolve(texturaIniciales(tienda.nombre)); return; }
            cargador.load(rutas[i++], tex => { tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; tex.center.set(0.5, 0.5); tex.rotation = Math.PI / 2; resolve(tex); }, undefined, intentar);
        };
        intentar();
    });
}

/* ---------- Escena ---------- */
export function crearPodio(contenedor, top3, opciones = {}) {
    const quieto = !!opciones.quieto;
    const porPuesto = {};
    top3.forEach((t, i) => { porPuesto[Number(t.posicion || i + 1)] = t; });

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.localClippingEnabled = true;  // los bloques salen del piso sin verse por debajo
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    contenedor.appendChild(renderer.domElement);

    const escena = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    escena.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    escena.environmentIntensity = 0.55;

    const camara = new THREE.PerspectiveCamera(32, 16 / 9, 0.1, 80);
    escena.add(new THREE.HemisphereLight(0xFFF6E8, 0xB9A58A, 0.85));
    const sol = new THREE.DirectionalLight(0xFFF1DC, 2.1);
    sol.position.set(-5, 11, 8);
    sol.castShadow = true;
    sol.shadow.mapSize.set(1536, 1536);
    sol.shadow.camera.left = -9; sol.shadow.camera.right = 9;
    sol.shadow.camera.top = 9; sol.shadow.camera.bottom = -6;
    sol.shadow.camera.near = 1; sol.shadow.camera.far = 30;
    sol.shadow.bias = -0.0004; sol.shadow.radius = 6;
    escena.add(sol);
    const relleno = new THREE.DirectionalLight(0xFFE7C6, 0.6); relleno.position.set(6, 4, 6); escena.add(relleno);

    // Piso
    const piso = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.ShadowMaterial({ color: 0x6B5539, opacity: 0.2 }));
    piso.rotation.x = -Math.PI / 2; piso.receiveShadow = true; escena.add(piso);

    // Materiales (los de los bloques se cortan en el piso: y >= 0)
    const piso0 = [new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)];
    const mCrema = new THREE.MeshPhysicalMaterial({ color: C.crema, roughness: 0.55, clearcoat: 0.25, clearcoatRoughness: 0.4, clippingPlanes: piso0, clipShadows: true });
    const mTapa = new THREE.MeshPhysicalMaterial({ color: C.cremaTapa, roughness: 0.4, clearcoat: 0.4, clearcoatRoughness: 0.3, clippingPlanes: piso0, clipShadows: true });
    const mCafe = new THREE.MeshStandardMaterial({ color: C.cafe, roughness: 0.45, metalness: 0.15, clippingPlanes: piso0, clipShadows: true });
    const mCafeOsc = new THREE.MeshStandardMaterial({ color: C.cafeOscuro, roughness: 0.6, clippingPlanes: piso0, clipShadows: true });
    const mOro = new THREE.MeshPhysicalMaterial({ color: C.oro, metalness: 1, roughness: 0.26, clearcoat: 0.6, clearcoatRoughness: 0.2, envMapIntensity: 1.25, clippingPlanes: piso0, clipShadows: true });

    /* --- Bloques --- */
    const bloques = {};
    for (const puesto of [1, 2, 3]) {
        const b = BLOQUES[puesto];
        const grupo = new THREE.Group();
        grupo.position.x = b.x;
        const cuerpo = new THREE.Mesh(cajaRedondeada(ANCHO, FONDO, b.h - 0.3, RADIO, 0.05), mCrema);
        cuerpo.position.y = 0.13; cuerpo.castShadow = true; cuerpo.receiveShadow = true; grupo.add(cuerpo);
        const base = new THREE.Mesh(cajaRedondeada(ANCHO + 0.02, FONDO + 0.02, 0.14, RADIO, 0.03), mCafeOsc);
        base.castShadow = true; grupo.add(base);
        const borde = new THREE.Mesh(cajaRedondeada(ANCHO + 0.14, FONDO + 0.14, 0.2, RADIO + 0.06, 0.06), puesto === 1 ? mOro : mCafe);
        borde.position.y = b.h - 0.2; borde.castShadow = true; borde.receiveShadow = true; grupo.add(borde);
        const tapa = new THREE.Mesh(cajaRedondeada(ANCHO - 0.08, FONDO - 0.08, 0.03, RADIO - 0.02, 0.01), mTapa);
        tapa.position.y = b.h - 0.012; tapa.receiveShadow = true; grupo.add(tapa);
        // Cara frontal con número, nombre y %
        const anchoCara = ANCHO - 2 * RADIO + 0.1, altoCara = b.h - 0.62;
        const cara = new THREE.Mesh(
            new THREE.PlaneGeometry(anchoCara, altoCara),
            new THREE.MeshStandardMaterial({ map: textoGrabado(String(puesto), porPuesto[puesto], puesto, anchoCara, altoCara), transparent: true, roughness: 0.35, metalness: 0.2, polygonOffset: true, polygonOffsetFactor: -2, clippingPlanes: piso0 })
        );
        cara.position.set(0, 0.16 + altoCara / 2 + 0.06, FONDO / 2 + 0.05 + 0.004);  // el bisel agranda el cuerpo 0,05
        grupo.add(cara);
        grupo.position.y = quieto ? 0 : -b.h - 0.3;
        escena.add(grupo);
        bloques[puesto] = { grupo, cara, h: b.h, sube: b.sube };
    }

    /* --- Medallones con la foto de cada tienda --- */
    const medallones = {};
    for (const puesto of [1, 2, 3]) {
        const tienda = porPuesto[puesto];
        if (!tienda) continue;
        const b = BLOQUES[puesto];
        const r = puesto === 1 ? 0.7 : 0.6;
        const grupo = new THREE.Group();
        const matFoto = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.55 });
        const disco = new THREE.Mesh(new THREE.CylinderGeometry(r, r, 0.06, 64), [mOro, matFoto, mOro]);
        disco.rotation.x = Math.PI / 2; // la tapa superior mira a la cámara
        disco.castShadow = true;
        grupo.add(disco);
        const aro = new THREE.Mesh(new THREE.TorusGeometry(r + 0.02, 0.055, 18, 72), mOro);
        aro.castShadow = true; grupo.add(aro);
        const pie = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.05, 0.42, 16), mOro);
        pie.position.y = -r - 0.2; pie.castShadow = true; grupo.add(pie);
        const peana = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.3, 0.06, 32), mOro);
        peana.position.y = -r - 0.43; peana.castShadow = true; grupo.add(peana);
        const yFinal = b.h + r + 0.46;
        grupo.position.set(b.x, yFinal, 0.15);
        grupo.scale.setScalar(quieto ? 1 : 0.0001);
        escena.add(grupo);
        cargarFoto(tienda).then(tex => { matFoto.map = tex; matFoto.needsUpdate = true; });
        medallones[puesto] = { grupo, yFinal, aparece: b.sube + 0.75 };
    }

    /* --- Corona --- */
    const corona = new THREE.Group();
    const perfil = [new THREE.Vector2(0.5, 0), new THREE.Vector2(0.56, 0.02), new THREE.Vector2(0.57, 0.24), new THREE.Vector2(0.53, 0.27), new THREE.Vector2(0.5, 0.25)];
    corona.add(new THREE.Mesh(new THREE.LatheGeometry(perfil, 64), mOro));
    const banda = new THREE.Mesh(new THREE.TorusGeometry(0.565, 0.025, 10, 64), mOro); banda.rotation.x = Math.PI / 2; banda.position.y = 0.06; corona.add(banda);
    for (let i = 0; i < 5; i++) {
        const a = (i / 5) * Math.PI * 2;
        const punta = new THREE.Mesh(new THREE.ConeGeometry(0.15, 0.52, 20), mOro);
        punta.position.set(Math.sin(a) * 0.48, 0.48, Math.cos(a) * 0.48);
        punta.rotation.set(Math.cos(a) * 0.18, 0, -Math.sin(a) * 0.18);
        corona.add(punta);
        const perla = new THREE.Mesh(new THREE.SphereGeometry(0.075, 20, 14), mOro);
        perla.position.set(Math.sin(a) * 0.53, 0.77, Math.cos(a) * 0.53);
        corona.add(perla);
    }
    corona.traverse(o => { if (o.isMesh) o.castShadow = true; });
    const yCorona = BLOQUES[1].h + 0.7 * 2 + 0.75;
    corona.position.set(0, quieto ? yCorona : yCorona + 5, 0.15);
    corona.scale.setScalar(0.92);
    escena.add(corona);

    /* --- Haces de luz --- */
    const matHaz = new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
        uniforms: { fuerza: { value: 0 } },
        vertexShader: 'varying float vy; varying vec3 vn; void main(){ vy = uv.y; vn = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
        fragmentShader: 'uniform float fuerza; varying float vy; varying vec3 vn; void main(){ float borde = pow(abs(vn.z), 2.5); float a = pow(1.0 - vy, 2.2) * 0.16 * fuerza * borde; gl_FragColor = vec4(1.0, 0.94, 0.80, a); }'
    });
    const haces = {};
    for (const puesto of [1, 2, 3]) {
        const b = BLOQUES[puesto];
        const m = matHaz.clone();
        const haz = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 0.95, 6.5, 40, 1, true), m);
        haz.position.set(b.x, b.h + 3.25, 0);
        escena.add(haz);
        haces[puesto] = m;
    }

    /* --- Hilo dorado en el piso y anillos --- */
    const puntosHilo = [];
    for (let i = 0; i <= 64; i++) {
        const s = i / 64, a = -Math.PI * 1.05 + s * Math.PI * 2.1;
        puntosHilo.push(new THREE.Vector3(Math.cos(a) * 6.9 + Math.sin(s * 9) * 0.25, 0.02, Math.sin(a) * 2.6 + 1.25 + Math.cos(s * 7) * 0.2));
    }
    const curvaHilo = new THREE.CatmullRomCurve3(puntosHilo);
    const geoHilo = new THREE.TubeGeometry(curvaHilo, 320, 0.014, 8, false);
    const hiloMat = new THREE.MeshBasicMaterial({ color: C.hilo, toneMapped: false });
    const hilo = new THREE.Mesh(geoHilo, hiloMat); escena.add(hilo);
    const geoBrillo = new THREE.TubeGeometry(curvaHilo, 320, 0.05, 8, false);
    const brillo = new THREE.Mesh(geoBrillo, new THREE.MeshBasicMaterial({ color: 0xFFDFA0, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    escena.add(brillo);
    const totalHilo = geoHilo.index.count, totalBrillo = geoBrillo.index.count;
    const anillos = [];
    for (let i = 0; i < 3; i++) {
        const m = new THREE.Mesh(new THREE.RingGeometry(1, 1.035, 128), new THREE.MeshBasicMaterial({ color: 0xFFDCA0, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }));
        m.rotation.x = -Math.PI / 2; m.position.set(0, 0.015, 0.4); escena.add(m);
        anillos.push({ m, retraso: i * 0.45 });
    }

    /* --- Confeti dorado --- */
    const N = 320;
    const confeti = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.15, 0.06), new THREE.MeshStandardMaterial({ color: 0xE2BE72, metalness: 0.9, roughness: 0.3, side: THREE.DoubleSide, envMapIntensity: 1.3 }), N);
    confeti.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    escena.add(confeti);
    const piezas = Array.from({ length: N }, () => ({ vivo: false }));
    const tmp = new THREE.Object3D();
    function soltarConfeti(cantidad, centroX, ancho) {
        let n = 0;
        for (const p of piezas) {
            if (p.vivo || n >= cantidad) continue;
            n++;
            p.vivo = true;
            p.x = centroX + (Math.random() - 0.5) * ancho; p.y = 7.5 + Math.random() * 3; p.z = (Math.random() - 0.5) * 3.5;
            p.vy = 0.9 + Math.random() * 0.9; p.fase = Math.random() * 6.28; p.giro = new THREE.Vector3(Math.random() * 6, Math.random() * 6, Math.random() * 6);
            p.r = new THREE.Euler(Math.random() * 6, Math.random() * 6, Math.random() * 6); p.esc = 0.7 + Math.random() * 0.6;
        }
    }
    function moverConfeti(dt, t) {
        let i = 0;
        for (const p of piezas) {
            if (p.vivo) {
                p.y -= p.vy * dt; p.x += Math.sin(t * 2 + p.fase) * 0.35 * dt;
                p.r.x += p.giro.x * dt; p.r.y += p.giro.y * dt; p.r.z += p.giro.z * dt;
                if (p.y < 0.03) { p.y = 0.03; p.vy = 0; p.giro.set(0, 0, 0); p.r.x = -Math.PI / 2; p.reposo = (p.reposo || 0) + dt; if (p.reposo > 4) { p.vivo = false; p.reposo = 0; } }
                tmp.position.set(p.x, p.y, p.z); tmp.rotation.copy(p.r); tmp.scale.setScalar(p.esc);
            } else { tmp.position.set(0, -50, 0); tmp.scale.setScalar(0.0001); }
            tmp.updateMatrix(); confeti.setMatrixAt(i++, tmp.matrix);
        }
        confeti.instanceMatrix.needsUpdate = true;
    }

    /* --- Cámara (encuadre según el tamaño de la pantalla) --- */
    let ancho = 1, alto = 1;
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    window.addEventListener('pointermove', e => { mouse.tx = (e.clientX / window.innerWidth - 0.5); mouse.ty = (e.clientY / window.innerHeight - 0.5); });
    // Espacio libre entre el título (arriba) y el botón (abajo), en píxeles
    let margen = { arriba: 0, abajo: 0 };
    function ajustar() {
        const r = contenedor.getBoundingClientRect();
        ancho = Math.max(1, r.width); alto = Math.max(1, r.height);
        renderer.setSize(ancho, alto, false);
        renderer.domElement.style.width = '100%'; renderer.domElement.style.height = '100%';
        camara.aspect = ancho / alto;
        margen = opciones.margenes ? opciones.margenes() : { arriba: 0, abajo: 0 };
        // Corre la imagen para que el podio quede centrado en el espacio libre
        const corrimiento = (margen.arriba - margen.abajo) / 2;
        camara.setViewOffset(ancho, alto, 0, -corrimiento, ancho, alto);
        camara.updateProjectionMatrix();
    }
    ajustar();
    const ro = window.ResizeObserver ? new ResizeObserver(ajustar) : null;
    if (ro) ro.observe(contenedor); else window.addEventListener('resize', ajustar);

    // Medidas del podio completo en el mundo 3D (bloques, fotos y corona)
    const MUNDO = { ancho: 10.6, alto: 6.9, centroY: 2.95 };
    function posCamara(avance) {
        // Distancia para que TODO el podio quepa en el espacio libre, en cualquier pantalla
        const tan = Math.tan(THREE.MathUtils.degToRad(camara.fov / 2));
        const libre = Math.max(0.3, (alto - margen.arriba - margen.abajo) / alto);
        const distAlto = (MUNDO.alto / 2) / (tan * libre);
        const distAncho = (MUNDO.ancho / 2) / (tan * camara.aspect);
        const base = Math.max(distAlto, distAncho) * 1.06;
        const dist = base * (1.2 - 0.2 * avance);   // se acerca despacio, como en el video
        camara.position.set(mouse.x * 1.0, MUNDO.centroY + base * 0.07 + 0.9 * (1 - avance) - mouse.y * 0.5, dist);
        camara.lookAt(0, MUNDO.centroY - 0.15 * (1 - avance), 0);
    }

    /* --- Animación --- */
    let t = quieto ? FIN + 1 : 0, ultimo = performance.now(), vivo = true, saltoA = null;
    const avisado = {};
    function aviso(nombre, fn) { if (!avisado[nombre]) { avisado[nombre] = true; fn(); } }

    function cuadro(ahora) {
        if (!vivo) return;
        requestAnimationFrame(cuadro);
        const dt = Math.min(0.05, (ahora - ultimo) / 1000); ultimo = ahora;
        if (saltoA !== null) { t = Math.max(t, saltoA); saltoA = null; }
        if (!quieto) t += dt;

        mouse.x += (mouse.tx - mouse.x) * Math.min(1, dt * 3);
        mouse.y += (mouse.ty - mouse.y) * Math.min(1, dt * 3);
        posCamara(facil.suave(tramo(t, 0, FIN)));

        // Hilo que se dibuja por el piso
        const avHilo = facil.salida(tramo(t, 0.1, 2.6));
        geoHilo.setDrawRange(0, Math.floor(totalHilo * avHilo / 6) * 6);
        geoBrillo.setDrawRange(0, Math.floor(totalBrillo * avHilo / 6) * 6);
        brillo.material.opacity = 0.12 + Math.sin(t * 2.2) * 0.04 + (t > BLOQUES[1].sube + 0.6 ? 0.08 : 0);

        // Bloques que suben, medallones que aparecen y haces de luz
        for (const puesto of [3, 2, 1]) {
            const bl = bloques[puesto];
            const k = facil.salida(tramo(t, bl.sube, bl.sube + 1.0));
            bl.grupo.position.y = (-bl.h - 0.3) * (1 - k);  // sale del piso como un elevador
            const med = medallones[puesto];
            if (med) {
                const km = facil.rebote(tramo(t, med.aparece, med.aparece + 0.7));
                med.grupo.scale.setScalar(Math.max(0.0001, km));
                med.grupo.position.y = med.yFinal + Math.sin(t * 1.6 + puesto) * 0.05 * (t > med.aparece + 0.7 ? 1 : 0);
                med.grupo.rotation.y = Math.sin(t * 0.9 + puesto * 2) * 0.22 + mouse.x * 0.25;
            }
            const kh = tramo(t, bl.sube + 0.5, bl.sube + 1.4);
            haces[puesto].uniforms.fuerza.value = (puesto === 1 ? 1.25 : 0.85) * facil.suave(kh) * (0.85 + Math.sin(t * 1.8 + puesto) * 0.15);
            if (t > bl.sube + 0.75) aviso('confeti' + puesto, () => {
                soltarConfeti(puesto === 1 ? 170 : 45, BLOQUES[puesto].x, puesto === 1 ? 11 : 3.5);
                if (opciones.alRevelar) opciones.alRevelar(puesto, porPuesto[puesto]);
            });
        }

        // La corona baja sobre el ganador
        const kc = facil.salida(tramo(t, BLOQUES[1].sube + 1.1, BLOQUES[1].sube + 2.3));
        corona.position.y = yCorona + 5 * (1 - kc) + (kc >= 1 ? Math.sin(t * 1.4) * 0.06 : 0);
        corona.rotation.y = (1 - kc) * 3.2 + t * 0.35;

        // Anillos de luz al coronar
        const tAn = t - (BLOQUES[1].sube + 2.0);
        anillos.forEach(a => {
            const u = (tAn - a.retraso) / 2.4;
            if (u > 0 && u < 1) { a.m.scale.setScalar(1.5 + u * 6.5); a.m.material.opacity = 0.75 * (1 - u); }
            else a.m.material.opacity = 0;
        });

        // Confeti suave que sigue cayendo un rato después
        if (t > FIN && t < FIN + 14 && Math.random() < dt * 6) soltarConfeti(3, 0, 12);
        moverConfeti(dt, t);

        if (t >= FIN) aviso('fin', () => { if (opciones.alTerminar) opciones.alTerminar(); });
        renderer.render(escena, camara);
    }
    requestAnimationFrame(cuadro);

    return {
        saltar() { saltoA = FIN; },
        irA(seg) { t = seg; },  // solo para pruebas y capturas
        reencuadrar() { ajustar(); },
        destruir() {
            vivo = false;
            if (ro) ro.disconnect();
            renderer.dispose();
            if (renderer.domElement.parentNode) renderer.domElement.remove();
        }
    };
}
