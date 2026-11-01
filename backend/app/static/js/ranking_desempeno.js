/* Ranking de desempeño: pestañas, podio animado, distribución, filtros por estado,
   tabla ordenable con "Ver más" y ficha de asesora. Las tablas se generan en el
   servidor; si este archivo falla, la página sigue mostrando todos los datos. */
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  const page = document.getElementById("rankingPage");
  if (!page) return;
  page.classList.add("rk-js");
  let data = {};
  try { data = JSON.parse(document.getElementById("performanceRankingData")?.textContent || "{}"); } catch (_) { data = {}; }
  const esTienda = !!data.esTienda;
  const asesoras = Array.isArray(data.asesoras) ? data.asesoras : [];
  const COLOR = { meta: "#2d6a4f", cerca: "#c9952f", progreso: "#d95d39", sinmeta: "#a89a87" };
  const estadoDe = c => c >= 1 ? "meta" : c >= 0.9 ? "cerca" : "progreso";
  const pct = v => (Number(v) * 100).toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
  const money = v => "$" + Math.round(Number(v) || 0).toLocaleString("en-US");
  const entero = v => Math.round(Number(v) || 0).toLocaleString("en-US");
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const iniciales = nombre => String(nombre || "?").trim().split(/\s+/).slice(0, 2).map(p => p[0]).join("").toUpperCase();

  // Ejecuta fn cuando el elemento entra en pantalla, con red de seguridad.
  function cuandoVisible(el, fn) {
    if (!el) return;
    let hecho = false;
    const correr = () => { if (hecho) return; hecho = true; try { fn(); } catch (_) { /* La tabla del servidor sigue visible. */ } };
    if (!("IntersectionObserver" in window)) { correr(); return; }
    const io = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) { io.disconnect(); correr(); } }, { threshold: 0.12 });
    io.observe(el);
    setTimeout(() => { io.disconnect(); correr(); }, 2500);
  }

  function contar(el, final, formato, retraso = 0, dur = 1000) {
    const original = el.textContent;
    setTimeout(() => {
      const t0 = performance.now();
      const paso = now => {
        const p = Math.min((now - t0) / dur, 1);
        el.textContent = p < 1 ? formato(final * (1 - Math.pow(1 - p, 3))) : original;
        if (p < 1) requestAnimationFrame(paso);
      };
      requestAnimationFrame(paso);
      setTimeout(() => { el.textContent = original; }, dur + 400);
    }, retraso);
  }

  // Elementos fuera de las pestañas: resumen y "Tu tienda".
  page.querySelectorAll(":scope > .performance-summary .rk-rv, :scope > .rk-mine-banner").forEach(el => cuandoVisible(el, () => {
    el.classList.add("in");
    el.querySelectorAll("[data-count]").forEach(n => { const v = Number(n.textContent); if (v > 0) contar(n, v, x => entero(x)); });
  }));

  // ---------- Pestañas ----------
  const tabs = [...page.querySelectorAll(".rk-tabs [data-tab]")];
  const panels = [...page.querySelectorAll(".rk-panel")];
  const iniciados = new Set();
  function abrirTab(nombre, foco = false) {
    tabs.forEach(t => {
      const on = t.dataset.tab === nombre;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      if (on && foco) t.focus();
    });
    panels.forEach(p => {
      const on = p.dataset.panel === nombre;
      const estabaOculto = p.hidden;
      p.hidden = !on;
      if (on && estabaOculto) { p.classList.remove("rk-enter"); void p.offsetWidth; p.classList.add("rk-enter"); }
      if (on) activarPanel(p);
    });
    try { history.replaceState(null, "", "#" + nombre); } catch (_) { /* Sin historial disponible. */ }
  }
  tabs.forEach(t => {
    t.addEventListener("click", () => abrirTab(t.dataset.tab));
    t.addEventListener("keydown", e => {
      if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
      const i = (tabs.indexOf(t) + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      abrirTab(tabs[i].dataset.tab, true);
    });
  });

  function activarPanel(panel) {
    if (iniciados.has(panel)) return;
    iniciados.add(panel);
    panel.querySelectorAll(".rk-rv").forEach(el => cuandoVisible(el, () => el.classList.add("in")));
    const podio = panel.querySelector(".rk-podium");
    cuandoVisible(podio, () => {
      podio.classList.add("go");
      const retraso = { 1: 800, 2: 550, 3: 350 };
      podio.querySelectorAll(".rk-step").forEach(step => {
        const lugar = Number((step.className.match(/rk-p(\d)/) || [])[1]);
        const b = step.querySelector(".rk-pct");
        if (b) contar(b, Number(b.dataset.pct) / 100, x => pct(x), retraso[lugar] || 0, 900);
      });
    });
    const dist = panel.querySelector(".rk-dist");
    cuandoVisible(dist, () => renderDist(dist));
    const table = panel.querySelector("table[data-rk-table]");
    if (table) {
      const ctl = initTable(table, panel);
      controles[table.dataset.rkTable] = ctl;
      cuandoVisible(table.closest(".performance-panel"), () => panel.classList.add("rk-visible"));
    }
  }

  // ---------- Tabla: filtros, búsqueda, orden y "Ver más" ----------
  const controles = {};
  function initTable(table, panel) {
    const tbody = table.tBodies[0];
    const card = table.closest(".performance-panel");
    const info = card.querySelector("[data-more-info]");
    const more = card.querySelector("[data-more]");
    const chips = card.querySelector(".rk-chips");
    const buscador = card.querySelector("[data-search-input]");
    const filas = () => [...tbody.rows].filter(r => r.dataset.estado);
    if (!filas().length) return null;
    let filtro = "todas", texto = "", limite = 25;

    function aplicar(animarTodas) {
      let total = 0, n = 0;
      filas().forEach(r => {
        const pasa = (filtro === "todas" || r.dataset.estado === filtro) && (!texto || r.dataset.search.includes(texto));
        if (pasa) total++;
        const ver = pasa && total <= limite;
        const estabaOculta = r.hidden;
        r.hidden = !ver;
        if (ver && (animarTodas || estabaOculta)) {
          r.classList.remove("rk-in"); void r.offsetWidth;
          r.style.setProperty("--i", Math.min(n, 14) * 35 + "ms");
          r.classList.add("rk-in"); n++;
        }
      });
      if (info) info.textContent = total ? `Mostrando ${Math.min(total, limite)} de ${total}` : "No hay resultados con estos filtros.";
      if (more) { more.hidden = total <= limite; more.textContent = `Ver ${Math.min(25, total - limite)} más`; }
    }
    function marcarChip(valor) {
      chips?.querySelectorAll("button").forEach(b => { const on = b.dataset.filter === valor; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); });
    }
    chips?.addEventListener("click", e => {
      const b = e.target.closest("button[data-filter]");
      if (!b) return;
      filtro = b.dataset.filter; limite = 25; marcarChip(filtro); aplicar(true);
    });
    buscador?.addEventListener("input", () => { texto = buscador.value.toLowerCase().trim(); limite = 25; aplicar(true); });
    more?.addEventListener("click", () => { limite += 25; aplicar(false); });

    // Orden por columnas
    const ths = [...table.tHead.rows[0].cells];
    let columna = -1, dir = 1;
    ths.forEach((th, i) => {
      if (!th.dataset.sort) return;
      th.tabIndex = 0;
      th.setAttribute("aria-sort", "none");
      th.insertAdjacentHTML("beforeend", '<i class="bi bi-chevron-expand" aria-hidden="true"></i>');
      const ordenar = () => {
        if (columna === i) dir = -dir;
        else { columna = i; dir = th.dataset.first === "asc" || th.dataset.sort === "text" ? 1 : -1; }
        const lista = filas();
        lista.sort((a, b) => {
          const va = a.cells[i]?.dataset.v ?? "", vb = b.cells[i]?.dataset.v ?? "";
          if (th.dataset.sort === "text") return va.localeCompare(vb, "es") * dir;
          const na = va === "" ? null : Number(va), nb = vb === "" ? null : Number(vb);
          if (na === null && nb === null) return 0;
          if (na === null) return 1;
          if (nb === null) return -1;
          return (na - nb) * dir;
        });
        lista.forEach(r => tbody.appendChild(r));
        ths.forEach((h, j) => {
          const icono = h.querySelector("i.bi");
          if (!icono) return;
          const activa = j === columna;
          icono.className = "bi " + (activa ? (dir < 0 ? "bi-caret-down-fill" : "bi-caret-up-fill") : "bi-chevron-expand");
          h.classList.toggle("on", activa);
          h.setAttribute("aria-sort", activa ? (dir < 0 ? "descending" : "ascending") : "none");
        });
        aplicar(true);
      };
      th.addEventListener("click", ordenar);
      th.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ordenar(); } });
    });
    aplicar(true);

    return {
      // Muestra y resalta una fila aunque esté oculta por filtros o por "Ver más".
      mostrar(key) {
        const fila = filas().find(r => r.dataset.key === String(key));
        if (!fila) return;
        if (fila.hidden) {
          filtro = "todas"; texto = ""; if (buscador) buscador.value = ""; marcarChip("todas");
          limite = Math.max(25, Math.ceil((filas().indexOf(fila) + 1) / 25) * 25);
          aplicar(false);
        }
        fila.scrollIntoView({ behavior: "smooth", block: "center" });
        fila.classList.remove("rk-flash"); void fila.offsetWidth; fila.classList.add("rk-flash");
      }
    };
  }

  // ---------- Distribución (cada punto es una tienda o asesora) ----------
  const MAX = 1.5;
  function renderDist(box) {
    const tipo = box.dataset.dist;
    const items = (tipo === "tiendas" ? (data.tiendasDist || []) : asesoras.filter(a => !a.sm))
      .map(it => ({ ...it, c: Number(it.c) || 0 }));
    if (!items.length) { box.innerHTML = '<p class="empty-ranking">Sin datos para este corte.</p>'; return; }
    const x = c => Math.max(0, Math.min(c, MAX)) / MAX * 100;
    const conteo = { progreso: 0, cerca: 0, meta: 0 };
    items.forEach(it => { conteo[estadoDe(it.c)]++; });
    const z90 = x(0.9), z100 = x(1);
    box.innerHTML =
      `<div class="rk-zone progreso" style="left:0;width:${z90}%"></div>` +
      `<div class="rk-zone cerca" style="left:${z90}%;width:${z100 - z90}%"></div>` +
      `<div class="rk-zone meta" style="left:${z100}%;right:0"></div>` +
      `<span class="rk-zone-label progreso" style="left:0">En progreso · ${conteo.progreso}</span>` +
      `<span class="rk-zone-label cerca" style="left:${z90}%;transform:translateX(-100%);padding-right:6px">Muy cerca · ${conteo.cerca}</span>` +
      `<span class="rk-zone-label meta" style="right:0">En meta · ${conteo.meta}</span>` +
      `<div class="rk-goal" style="left:${z100}%"></div>` +
      `<div class="rk-axis">${[[0, "0%"], [0.5, "50%"], [1, "100% meta"], [1.5, "150% o más"]].map(([v, l]) => `<span style="left:${x(v)}%;${v === 1.5 ? "transform:translateX(-100%)" : v === 0 ? "transform:none" : ""}">${l}</span>`).join("")}</div>`;
    const capa = document.createElement("div");
    box.append(capa);
    const tip = document.createElement("div");
    tip.className = "rk-tip"; tip.hidden = true;
    box.append(tip);
    const ordenados = [...items].sort((a, b) => a.c - b.c);
    const puntos = ordenados.map((it, i) => {
      const dot = document.createElement("span");
      dot.className = "rk-dot" + (it.mia ? " mia" : "");
      dot.tabIndex = 0;
      dot.setAttribute("role", "button");
      dot.setAttribute("aria-label", `${it.n}: ${pct(it.c)}`);
      dot.style.setProperty("--c", COLOR[estadoDe(it.c)]);
      dot.style.setProperty("--d", Math.min(i * (900 / ordenados.length), 900) + "ms");
      capa.append(dot);
      const verTip = () => {
        tip.innerHTML = `<strong>${esc(it.n)}</strong><br>${pct(it.c)}${it.p ? ` · <small>puesto ${it.p}</small>` : ""}${it.t ? `<br><small>${esc(it.ct)} · ${esc(it.t)}</small>` : ""}`;
        tip.style.left = dot.dataset.x + "px"; tip.style.top = dot.dataset.y + "px"; tip.hidden = false;
      };
      dot.addEventListener("pointerenter", verTip);
      dot.addEventListener("focus", verTip);
      dot.addEventListener("pointerleave", () => { tip.hidden = true; });
      dot.addEventListener("blur", () => { tip.hidden = true; });
      const accion = () => { tip.hidden = true; if (tipo === "asesoras") abrirFicha(it.k); else controles.tiendas?.mostrar(it.k); };
      dot.addEventListener("click", accion);
      dot.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); accion(); } });
      return { it, dot };
    });

    // Enjambre: cada punto busca el carril libre más cercano a la línea central.
    function ubicar() {
      const W = box.clientWidth, top = 34, H = box.clientHeight - top - 6;
      const base = ordenados.length > 140 ? 9 : ordenados.length > 60 ? 12 : 16;
      const colocados = [];
      puntos.forEach(({ it, dot }) => {
        const r = (it.mia ? 20 : base) / 2;
        const px = x(it.c) / 100 * W;
        const centro = top + H / 2;
        let py = centro;
        for (let k = 0; k < 60; k++) {
          const off = Math.ceil(k / 2) * (base + 1) * (k % 2 ? 1 : -1);
          const cand = centro + off;
          if (cand < top + r || cand > top + H - r) continue;
          if (!colocados.some(p => Math.abs(p.x - px) < p.r + r + 1 && Math.hypot(p.x - px, p.y - cand) < p.r + r + 1)) { py = cand; break; }
        }
        colocados.push({ x: px, y: py, r });
        dot.style.width = dot.style.height = it.mia ? "" : base + "px";
        if (!it.mia) dot.style.margin = `-${base / 2}px 0 0 -${base / 2}px`;
        dot.style.setProperty("--x", px + "px");
        dot.style.setProperty("--y", py + "px");
        dot.dataset.x = px; dot.dataset.y = py;
      });
    }
    ubicar();
    requestAnimationFrame(() => box.classList.add("go"));
    setTimeout(() => box.classList.add("go"), 120);
    // Al terminar de caer, cada punto queda quieto para que el hover no repita la animación.
    puntos.forEach(({ dot }) => dot.addEventListener("animationend", () => dot.classList.add("ok"), { once: true }));
    setTimeout(() => puntos.forEach(({ dot }) => dot.classList.add("ok")), 2200);
    if ("ResizeObserver" in window) {
      let ancho = box.clientWidth;
      new ResizeObserver(() => { if (Math.abs(box.clientWidth - ancho) > 4) { ancho = box.clientWidth; ubicar(); } }).observe(box);
    }
  }

  // ---------- Ficha de asesora ----------
  const ficha = document.getElementById("rkFicha");
  const fichaBody = document.getElementById("rkFichaBody");
  function abrirFicha(key) {
    const a = asesoras.find(x => x.k === key);
    if (!a || !ficha || !fichaBody) return;
    const deTienda = asesoras.filter(x => x.s === a.s);
    const conMeta = asesoras.filter(x => !x.sm);
    const tiendaConMeta = deTienda.filter(x => !x.sm).sort((p, q) => q.c - p.c);
    const posTienda = a.sm ? null : tiendaConMeta.findIndex(x => x.k === a.k) + 1;
    const promedio = campo => {
      const vals = deTienda.map(x => Number(x[campo])).filter(Number.isFinite);
      return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
    };
    const comparar = (campo, valor) => {
      if (deTienda.length < 2) return '<em class="eq">Única asesora de la tienda en esta consulta</em>';
      const p = promedio(campo);
      if (!p) return '<em class="eq">Sin promedio de tienda</em>';
      const d = (valor / p - 1) * 100;
      if (Math.abs(d) < 0.5) return '<em class="eq">Igual al promedio de la tienda</em>';
      return `<em class="${d > 0 ? "up" : "down"}">${d > 0 ? "▲" : "▼"} ${Math.abs(d).toLocaleString("es-CO", { maximumFractionDigits: 1 })}% vs promedio de la tienda</em>`;
    };
    const kpis = [];
    if (!esTienda && a.v != null) kpis.push(["Ventas", money(a.v), comparar("v", a.v)]);
    kpis.push(["Meta al corte", a.sm ? "Sin meta" : money(a.m), ""]);
    kpis.push(["Facturas", entero(a.f), comparar("f", a.f)]);
    kpis.push(["Unidades", entero(a.u), comparar("u", a.u)]);
    if (!esTienda && a.tk != null) kpis.push(["Ticket promedio", money(a.tk), comparar("tk", a.tk)]);
    kpis.push(["UPT", Number(a.upt || 0).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), comparar("upt", a.upt)]);
    const est = a.sm ? "sinmeta" : estadoDe(a.c);
    const largo = 2 * Math.PI * 38, final = a.sm ? 0 : largo * Math.min(a.c, 1);
    let paraMeta = "Sin meta asignada";
    if (!a.sm) {
      if (esTienda) { const pts = (a.c - 1) * 100; paraMeta = `${pts >= 0 ? "Superó por" : "Le faltan"} ${Math.abs(pts).toLocaleString("es-CO", { maximumFractionDigits: 1 })} pts`; }
      else if (a.v != null) { const dif = a.v - a.m; paraMeta = `${dif >= 0 ? "Superó la meta por" : "Le faltan"} ${money(Math.abs(dif))}`; }
    }
    fichaBody.innerHTML =
      `<div class="rk-ficha-head"><span class="rk-avatar">${esc(iniciales(a.n))}</span><div><h3 id="rkFichaTitulo">${esc(a.n)}</h3><small>${esc(a.ct)} · ${esc(a.t)}</small></div>` +
      `<div class="rk-ficha-ring"><svg viewBox="0 0 92 92" aria-hidden="true"><circle class="bg" cx="46" cy="46" r="38"/><circle class="fg" cx="46" cy="46" r="38" style="stroke:${COLOR[est]};stroke-dasharray:0 ${largo}"/></svg><div><b>${a.sm ? "—" : pct(a.c)}</b><small>cumplimiento</small></div></div></div>` +
      `<div class="rk-ficha-pos">${a.sm ? "<span>Sin meta asignada</span>" : `<span>Puesto ${a.p} de ${conMeta.length}</span><span>${posTienda}º de ${tiendaConMeta.length} en su tienda</span>`}<span>${esc(paraMeta)}</span></div>` +
      `<div class="rk-ficha-grid">${kpis.map(([l, v, c], i) => `<div class="rk-ficha-kpi" style="--i:${i * 50}ms"><small>${esc(l)}</small><strong>${esc(v)}</strong>${c}</div>`).join("")}</div>` +
      `<p class="rk-ficha-note">Promedios calculados con las asesoras de su tienda que aparecen en esta consulta.</p>`;
    if (typeof ficha.showModal === "function") ficha.showModal(); else ficha.setAttribute("open", "");
    setTimeout(() => { const fg = fichaBody.querySelector(".fg"); if (fg) fg.style.strokeDasharray = `${final} ${largo}`; }, 40);
  }
  page.addEventListener("click", e => {
    const b = e.target.closest("[data-ficha]");
    if (b) abrirFicha(b.dataset.ficha);
  });
  ficha?.addEventListener("click", e => { if (e.target === ficha) ficha.close(); });

  abrirTab(location.hash === "#asesoras" ? "asesoras" : "tiendas");
  window.addEventListener("hashchange", () => abrirTab(location.hash === "#asesoras" ? "asesoras" : "tiendas"));
});
