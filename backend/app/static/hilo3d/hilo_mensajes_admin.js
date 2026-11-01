/* ================================================================
   Mensajes con Hilo (administrador)
   - «Quién lo vio»: en cada mensaje enviado muestra qué tiendas y usuarios
     ya lo vieron (y cuándo) y a quiénes les falta.
   - «Ideas de Hilo»: mensajes sugeridos con los datos del último corte;
     al tocar uno se llena el formulario (no se envía solo).
   No cambia el formulario ni la tabla: solo agrega botones.
   ================================================================ */
const el = (tag, clase, texto) => {
  const n = document.createElement(tag);
  if (clase) n.className = clase;
  if (texto != null) n.textContent = texto;
  return n;
};

const estilos = el('style');
estilos.textContent = `
.mhh-ideas { margin: 0 0 14px; padding: 12px 14px; border: 1px dashed rgba(197,168,128,.7); border-radius: 12px; background: #FDF9F1; }
.mhh-ideas strong { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #2D2A26; }
.mhh-ideas strong .bi { color: #B98A3E; }
.mhh-ideas small { display: block; margin: 2px 0 8px; color: #6B6259; font-size: 12px; }
.mhh-ideas-lista { display: flex; flex-wrap: wrap; gap: 6px; }
.mhh-idea { padding: 6px 11px; border: 1px solid #EADFCB; border-radius: 999px; background: #fff; color: #2D2A26; font: 600 12px/1.25 Inter, "Segoe UI", Arial, sans-serif; text-align: left; cursor: pointer; }
.mhh-idea:hover { background: #F6EFE3; border-color: #C5A880; }
.mhh-idea:focus-visible, .mhh-ver:focus-visible { outline: 2px solid #C5A880; outline-offset: 1px; }
.mhh-ver { margin-top: 6px; padding: 3px 9px; border: 1px solid #E2D6C2; border-radius: 999px; background: #fff; color: #2D2A26; font: 600 11.5px/1.2 Inter, "Segoe UI", Arial, sans-serif; cursor: pointer; }
.mhh-ver:hover { background: #F6EFE3; }
.mhh-detalle td { background: #FDF9F1; }
.mhh-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; padding: 6px 2px; }
.mhh-cols h4 { margin: 0 0 6px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: #6B6259; }
.mhh-cols ul { list-style: none; margin: 0; padding: 0; max-height: 220px; overflow: auto; }
.mhh-cols li { display: flex; justify-content: space-between; gap: 10px; padding: 5px 0; border-bottom: 1px solid #F1EBE0; font-size: 12.5px; }
.mhh-cols li span { color: #6B6259; white-space: nowrap; }
.mhh-cols .ok b::before { content: "✓ "; color: #3F7F55; }
.mhh-cols .falta b::before { content: "• "; color: #A9472F; }
`;
document.head.append(estilos);

/* ---------- Quién lo vio ---------- */
fetch('/api/hilo/admin/mensajes/vistos', { credentials: 'same-origin' })
  .then(r => (r.ok ? r.json() : null))
  .then(d => {
    if (!d || !d.ok) return;
    const filas = Array.from(document.querySelectorAll('.mh-tabla tbody > tr')).filter(tr => tr.children.length >= 5);
    filas.forEach((tr, i) => {
      const m = d.mensajes[i];
      if (!m) return;
      const celda = tr.children[4];
      const b = el('button', 'mhh-ver', 'Ver quién');
      b.type = 'button';
      b.setAttribute('aria-expanded', 'false');
      let detalle = null;
      b.addEventListener('click', () => {
        if (detalle) { detalle.remove(); detalle = null; b.textContent = 'Ver quién'; b.setAttribute('aria-expanded', 'false'); return; }
        detalle = el('tr', 'mhh-detalle');
        const td = el('td'); td.colSpan = tr.children.length;
        const cols = el('div', 'mhh-cols');
        const col = (titulo, lista, clase, vacio) => {
          const c = el('div');
          c.append(el('h4', '', `${titulo} (${lista.length})`));
          const ul = el('ul', clase);
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
        cols.append(col('Lo vieron', m.vieron, 'ok', 'Nadie todavía.'), col('Les falta', m.faltan, 'falta', '¡Ya lo vieron todos!'));
        td.append(cols); detalle.append(td);
        tr.after(detalle);
        b.textContent = 'Ocultar'; b.setAttribute('aria-expanded', 'true');
      });
      celda.append(b);
    });
  })
  .catch(() => {});

/* ---------- Ideas de Hilo ---------- */
fetch('/api/hilo/admin', { credentials: 'same-origin' })
  .then(r => (r.ok ? r.json() : null))
  .then(d => {
    if (!d || !d.ok || !(d.sugeridos || []).length) return;
    const form = document.getElementById('mhForm');
    const texto = document.getElementById('mhTexto');
    if (!form || !texto) return;
    const caja = el('div', 'mhh-ideas');
    const t = el('strong');
    const ico = el('i', 'bi bi-lightbulb'); ico.setAttribute('aria-hidden', 'true');
    t.append(ico, document.createTextNode('Ideas de Hilo'));
    caja.append(t, el('small', '', `Con los datos de ${d.corte.nombre_mes} (corte día ${d.corte.dia}). Toca una para llenar el formulario; revisa y envía.`));
    const lista = el('div', 'mhh-ideas-lista');
    d.sugeridos.forEach(s => {
      const b = el('button', 'mhh-idea', s.motivo);
      b.type = 'button';
      b.title = s.texto;
      b.addEventListener('click', () => llenar(s));
      lista.append(b);
    });
    caja.append(lista);
    const campo = texto.closest('.mh-campo') || texto.parentElement;
    campo.before(caja);
  })
  .catch(() => {});

function llenar(s) {
  const texto = document.getElementById('mhTexto');
  texto.value = s.texto.slice(0, texto.maxLength || 400);
  texto.dispatchEvent(new Event('input', { bubbles: true }));
  const tono = document.querySelector(`input[name="tono"][value="${s.tono}"]`);
  if (tono) tono.checked = true;
  const destino = document.getElementById('mhDestino');
  if (destino) {
    destino.value = s.tiendas && s.tiendas.length ? 'seleccion' : 'todas';
    destino.dispatchEvent(new Event('change', { bubbles: true }));
  }
  const ids = new Set((s.tiendas || []).map(String));
  document.querySelectorAll('#mhTiendasCampo input[type="checkbox"]').forEach(c => { c.checked = ids.has(c.value); });
  texto.focus();
  texto.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
