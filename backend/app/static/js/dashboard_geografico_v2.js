/* Dashboard Geográfico V2: mapa por indicador, contexto en pestañas, tarjetas
   gráfica/tabla, tablas ordenables y comparación. Mismas consultas y filtros. */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';
    const configNode = document.getElementById('geoV2Config');
    if (!configNode) return;
    const config = JSON.parse(configNode.textContent);
    const page = document.querySelector('.geo-v2-page');
    page?.classList.add('geo-js');
    let map = null;
    let grupos = [];
    let boundsTodas = null;
    let tiendasData = [];
    let selectedStoreId = null;
    let radarChartInstance = null;
    let contextController = null;
    let contextVersion = 0;
    let compareVersion = 0;
    let lastContext = null;
    let metricaMapa = 'cumplimiento';
    let metricaCiudad = 'ventas';
    let tabActual = 'des';
    let gaugeAnimado = null;
    const charts = {};
    const $ = id => document.getElementById(id);
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const num = (value, digits=0) => value === null || value === undefined || !Number.isFinite(Number(value)) ? 'N/D' : Number(value).toLocaleString('es-CO', {maximumFractionDigits:digits});
    const money = value => value == null ? 'N/D' : '$' + num(value);
    const moneyCorto = value => value == null ? 'N/D' : '$' + (Number(value)/1e6).toLocaleString('es-CO', {maximumFractionDigits: Math.abs(value) < 1e8 ? 1 : 0}) + ' M';
    const pct = value => value == null ? 'N/D' : num(value,1) + '%';
    const metric = (value, suffix='') => value == null ? 'N/D' : num(value,1) + suffix;
    const date = value => {
        const d = new Date(value);
        return !value || Number.isNaN(d.getTime()) ? 'Sin hora registrada' : d.toLocaleString('es-CO', {timeZone:'America/Bogota', dateStyle:'short', timeStyle:'short'});
    };

    // Semáforos: cumplimiento y score con cortes fijos; ventas y conversión por cuartiles de la selección.
    const COL = {ok:'#6B7D3F', mid:'#C9952F', low:'#C96F4A', bad:'#B55A4E', taupe:'#8B7D6B', goldD:'#A8865A', text:'#2D2A26', muted:'#6B6259'};
    const RAMPA_VENTAS = ['#D8CABB','#C5A880','#A8865A','#7A5F3E'];
    const RAMPA_BUENA = [COL.bad, COL.low, COL.mid, COL.ok];
    const nivelCumpl = v => v >= 1 ? 'ok' : v >= 0.9 ? 'mid' : v >= 0.8 ? 'low' : 'bad';
    const nivelScore = v => v >= 75 ? 'ok' : v >= 50 ? 'mid' : v >= 30 ? 'low' : 'bad';
    const nivelQ = (v,q) => v >= q[2] ? 'ok' : v >= q[1] ? 'mid' : v >= q[0] ? 'low' : 'bad';
    function cuartiles(valores) {
        const s = valores.filter(Number.isFinite).sort((a,b) => a-b);
        if (!s.length) return [0,0,0];
        const q = p => s[Math.floor(p*(s.length-1))];
        return [q(.25), q(.5), q(.75)];
    }
    function mediana(valores) {
        const s = [...valores].sort((a,b) => a-b), m = s.length >> 1;
        return s.length % 2 ? s[m] : (s[m-1]+s[m])/2;
    }

    function apiURL(name, extra={}, storeId=null) {
        let path = config.urls[name];
        if (name === 'contexto') path = path.replace(/\/0$/, '/' + encodeURIComponent(storeId));
        const url = new URL(path, window.location.origin);
        Object.entries({...config.filtros, ...extra}).forEach(([key,value]) => {
            if (value !== null && value !== undefined && value !== '') url.searchParams.set(key,value);
        });
        return url;
    }

    async function fetchJSON(name, extra={}, storeId=null, signal=null) {
        const controller = new AbortController();
        const abort = () => controller.abort();
        if (signal?.aborted) controller.abort();
        signal?.addEventListener('abort',abort,{once:true});
        const timer = setTimeout(abort, 15000);
        try {
            const response = await fetch(apiURL(name,extra,storeId), {
                credentials:'same-origin', signal:controller.signal, headers:{Accept:'application/json'}
            });
            if ([401,403].includes(response.status)) throw new Error('Tu sesión expiró o no tienes acceso. Vuelve a iniciar sesión.');
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || 'No se pudo completar la consulta.');
            }
            return await response.json();
        } finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort',abort);
        }
    }

    function errorText(error) {
        return error.name === 'AbortError' ? 'La consulta tardó demasiado. Vuelve a intentarlo.' : error.message;
    }

    // Ejecuta fn cuando el elemento entra en pantalla (con red de seguridad por si el navegador no avisa).
    function cuandoVisible(el, fn) {
        if (!el) { fn(); return; }
        let hecho = false;
        const correr = () => { if (hecho) return; hecho = true; try { fn(); } catch (_) { /* La sección conserva su tabla. */ } };
        if (!('IntersectionObserver' in window)) { correr(); return; }
        const io = new IntersectionObserver(entries => {
            if (entries.some(e => e.isIntersecting)) { io.disconnect(); correr(); }
        }, {threshold:.12});
        io.observe(el);
        setTimeout(() => { io.disconnect(); correr(); }, 2500);
    }

    // 0. Aparición al bajar y conteo de KPIs.
    document.querySelectorAll('.geo-rv').forEach(el => cuandoVisible(el, () => el.classList.add('in')));
    function contarKPIs() {
        document.querySelectorAll('.geo-v2-kpi-value').forEach(el => {
            const original = el.textContent;
            const m = original.trim().match(/^([^\d-]*)(-?[\d,]*\.?\d+)(.*)$/);
            if (!m) return;
            const final = Number(m[2].replace(/,/g,''));
            if (!Number.isFinite(final) || final === 0) return;
            const dec = (m[2].split('.')[1] || '').length;
            const fmt = v => m[1] + v.toLocaleString('en-US', {minimumFractionDigits:dec, maximumFractionDigits:dec}) + m[3];
            const t0 = performance.now(), dur = 1100;
            const paso = now => {
                const p = Math.min((now - t0)/dur, 1);
                el.textContent = p < 1 ? fmt(final * (1 - Math.pow(1-p, 3))) : original;
                if (p < 1) requestAnimationFrame(paso);
            };
            requestAnimationFrame(paso);
            setTimeout(() => { el.textContent = original; }, dur + 400);
        });
    }
    cuandoVisible(document.querySelector('.geo-v2-kpi-grid'), contarKPIs);

    // 1. Mapa Leaflet: tamaño por venta, color por indicador y coordenadas idénticas agrupadas.
    function initMap() {
        if (!$('mapContainer')) return;
        if (typeof L === 'undefined') {
            $('mapLoading').textContent = 'Mapa no disponible. Puedes consultar las tiendas en la lista.';
            cargarTiendas();
            return;
        }
        try {
            map = L.map('mapContainer', {scrollWheelZoom:false, zoomSnap:.25}).setView([4.6097,-74.0817],5);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom:19
            }).addTo(map);
            window.__geoMapa = map; // para el modo «Hilo de la red» (hilo3d/hilo_red.js)
            map.on('focus', () => map.scrollWheelZoom.enable());
            map.on('blur', () => map.scrollWheelZoom.disable());
        } catch (_) {
            map = null;
            $('mapLoading').textContent = 'Mapa no disponible. Usa la lista de tiendas.';
        }
        cargarTiendas();
    }

    function crearGrupo(stores) {
        const venta = stores.reduce((s,t) => s + Number(t.venta_actual || 0), 0);
        const prom = key => stores.reduce((s,t) => s + Number(t[key] || 0), 0) / stores.length;
        return {stores, lat:Number(stores[0].lat), lng:Number(stores[0].lng), venta,
            cumplimiento:prom('cumplimiento_pct'), conversion:prom('conversion'), score:prom('score'),
            criticas:stores.filter(t => Number(t.cumplimiento_pct || 0) < 0.8).length, marker:null};
    }

    function configMetrica(m) {
        if (m === 'cumplimiento') return {nombre:'Cumplimiento', valor:g => g.cumplimiento, fmt:v => pct(v*100), color:v => COL[nivelCumpl(v)],
            leyenda:[['100% o más',COL.ok],['90 a 99,9%',COL.mid],['80 a 89,9%',COL.low],['Menos de 80%',COL.bad]]};
        if (m === 'score') return {nombre:'Score', valor:g => g.score, fmt:v => num(v,1) + '/100', color:v => COL[nivelScore(v)],
            leyenda:[['75 a 100',COL.ok],['50 a 74,9',COL.mid],['30 a 49,9',COL.low],['0 a 29,9',COL.bad]]};
        const key = m === 'ventas' ? 'venta' : 'conversion';
        const fmt = m === 'ventas' ? moneyCorto : pct;
        const rampa = m === 'ventas' ? RAMPA_VENTAS : RAMPA_BUENA;
        const q = cuartiles(grupos.map(g => g[key]));
        return {nombre:m === 'ventas' ? 'Ventas' : 'Conversión', valor:g => g[key], fmt,
            color:v => rampa[v >= q[2] ? 3 : v >= q[1] ? 2 : v >= q[0] ? 1 : 0],
            leyenda:[[`${fmt(q[2])} o más`,rampa[3]],[`${fmt(q[1])} a ${fmt(q[2])}`,rampa[2]],[`${fmt(q[0])} a ${fmt(q[1])}`,rampa[1]],[`Menos de ${fmt(q[0])}`,rampa[0]]]};
    }

    function pintarMapa() {
        const cfg = configMetrica(metricaMapa);
        grupos.forEach(g => {
            const color = cfg.color(cfg.valor(g));
            g.marker?.getElement()?.querySelector('.geo-mk-dot')?.style.setProperty('--c', color);
            const titulo = g.stores.length > 1 ? `${g.stores.length} tiendas · ${esc(g.stores[0].ciudad || 'Ubicación compartida')}` : `${esc(g.stores[0].nombre)} <small>· ${esc(g.stores[0].ciudad || '')}</small>`;
            const promedio = g.stores.length > 1 ? ' (promedio)' : '';
            g.marker?.setTooltipContent(`<strong>${titulo}</strong><br>Venta ${esc(moneyCorto(g.venta))} · Cumpl. ${esc(pct(g.cumplimiento*100))}${promedio}` +
                `<br><small>${esc(cfg.nombre)}:</small> <strong>${esc(cfg.fmt(cfg.valor(g)))}</strong>${g.criticas ? `<br><small>${g.criticas} por debajo de 80% de cumplimiento</small>` : ''}`);
        });
        $('mapLegend').innerHTML = cfg.leyenda.map(([label,color]) => `<span class="geo-v2-legend-item"><span class="geo-v2-legend-dot" style="background:${color}"></span>${esc(label)}</span>`).join('') +
            `<span class="geo-legend-size"><i style="width:8px;height:8px"></i><i style="width:14px;height:14px"></i> tamaño = venta</span>`;
    }

    async function cargarTiendas() {
        const loading = $('mapLoading');
        try {
            const data = await fetchJSON('tiendas');
            if (!Array.isArray(data)) throw new Error('Respuesta de tiendas no válida.');
            tiendasData = data;
            grupos.forEach(g => g.marker && map?.removeLayer(g.marker));
            grupos = [];
            const selector = $('mapStoreSelect');
            selector.replaceChildren(new Option('Selecciona una tienda',''));
            const porUbicacion = new Map();
            [...tiendasData].sort((a,b) => String(a.nombre).localeCompare(String(b.nombre),'es')).forEach(tienda => {
                selector.add(new Option(tienda.nombre + (tienda.es_virtual ? ' · Virtual' : ''), tienda.id));
            });
            tiendasData.forEach(tienda => {
                if (tienda.es_virtual || tienda.lat == null || tienda.lng == null ||
                    !Number.isFinite(Number(tienda.lat)) || !Number.isFinite(Number(tienda.lng))) return;
                const key = `${tienda.lat},${tienda.lng}`;
                if (!porUbicacion.has(key)) porUbicacion.set(key,[]);
                porUbicacion.get(key).push(tienda);
            });
            grupos = [...porUbicacion.values()].map(crearGrupo).sort((a,b) => b.venta - a.venta);
            const maxVenta = Math.max(...grupos.map(g => g.venta), 1);
            if (map) {
                grupos.forEach((g,i) => {
                    const size = Math.round(16 + 26*Math.sqrt(Math.max(g.venta,0)/maxVenta));
                    const html = `<div class="geo-mk${g.criticas ? ' crit' : ''}" style="--d:${Math.min(i*60,1500)}ms"><div class="geo-mk-in">` +
                        `${g.criticas ? '<span class="geo-mk-ring"></span>' : ''}<span class="geo-mk-dot"></span>` +
                        `${g.stores.length > 1 ? `<span class="geo-mk-n">${g.stores.length}</span>` : ''}</div></div>`;
                    const marker = L.marker([g.lat,g.lng], {
                        icon:L.divIcon({className:'geo-mk-wrap', iconSize:[size,size], html}),
                        riseOnHover:true, keyboard:true, zIndexOffset:grupos.length - i,
                        title:g.stores.length > 1 ? `${g.stores.length} tiendas en ${g.stores[0].ciudad || 'la misma ubicación'}` : g.stores[0].nombre
                    }).addTo(map);
                    marker.bindTooltip('', {direction:'top', offset:[0,-size/2], className:'geo-tip'});
                    if (g.stores.length > 1) {
                        const popup = document.createElement('div');
                        const title = document.createElement('strong');
                        title.textContent = `${g.stores.length} tiendas · ${g.stores[0].ciudad || 'Ubicación compartida'}`;
                        popup.append(title);
                        g.stores.forEach(tienda => {
                            const button = document.createElement('button');
                            button.type = 'button'; button.className = 'geo-v2-point-button';
                            button.textContent = `${tienda.nombre} · ${pct(Number(tienda.cumplimiento_pct || 0)*100)}`;
                            button.addEventListener('click', () => seleccionarTienda(tienda.id));
                            popup.append(button);
                        });
                        marker.bindPopup(popup);
                    } else {
                        marker.on('click', () => seleccionarTienda(g.stores[0].id));
                    }
                    g.marker = marker;
                });
                if (grupos.length) {
                    boundsTodas = L.latLngBounds(grupos.map(g => [g.lat,g.lng])).pad(0.12);
                    map.fitBounds(boundsTodas, {maxZoom:14});
                }
            }
            pintarMapa();
            const virtuales = tiendasData.filter(t => t.es_virtual).length;
            const sinUbicacion = tiendasData.filter(t => !t.es_virtual && t.lat == null).length;
            $('mapSummary').textContent = `${tiendasData.length} tiendas con datos · ${grupos.length} ubicaciones · ${virtuales} virtual(es) · ${sinUbicacion} sin ubicación`;
            if (loading) loading.textContent = map ? (tiendasData.length ? '' : 'No hay tiendas con datos en esta selección.') : loading.textContent;
            // Comparación coherente con los mismos filtros y corte.
            ['compareA','compareB'].forEach((id,index) => {
                const node = $(id); node.replaceChildren();
                tiendasData.forEach(t => node.add(new Option(t.nombre,t.id)));
                node.selectedIndex = Math.min(index,tiendasData.length-1);
            });
            const scatterCard = $('traficoVentasChart')?.closest('.geo-v2-card');
            cuandoVisible(scatterCard, renderTraficoVentasChart);
            if (config.filtros.tienda && tiendasData.some(t => String(t.id) === String(config.filtros.tienda))) seleccionarTienda(config.filtros.tienda);
        } catch (error) {
            if (loading) loading.textContent = errorText(error);
            chartMessage('traficoVentasChart', errorText(error));
        }
        comparar();
    }

    function marcarSeleccion(storeId) {
        grupos.forEach(g => g.marker?.getElement()?.querySelector('.geo-mk')
            ?.classList.toggle('sel', storeId != null && g.stores.some(t => String(t.id) === String(storeId))));
    }

    function volarATienda(storeId) {
        const tienda = tiendasData.find(t => String(t.id) === String(storeId));
        marcarSeleccion(storeId);
        if (!map || !tienda || tienda.es_virtual || tienda.lat == null || !Number.isFinite(Number(tienda.lat))) return;
        map.flyTo([Number(tienda.lat), Number(tienda.lng)], tienda.precision_ubicacion === 'tienda' ? 14 : 12, {duration:1.1});
    }

    $('mapMetric')?.addEventListener('click', event => {
        const button = event.target.closest('button[data-m]');
        if (!button) return;
        activarSegmento($('mapMetric'), button);
        document.dispatchEvent(new CustomEvent('geo:modo', {detail: button.dataset.m}));
        if (button.dataset.m === 'red') return; // lo dibuja hilo3d/hilo_red.js
        metricaMapa = button.dataset.m;
        pintarMapa();
    });
    $('mapVerTodas')?.addEventListener('click', () => {
        if (map && boundsTodas) map.flyToBounds(boundsTodas, {duration:1, maxZoom:14});
    });

    function activarSegmento(seg, button) {
        seg.querySelectorAll('button').forEach(b => {
            const on = b === button;
            b.classList.toggle('on', on);
            b.setAttribute('aria-pressed', String(on));
        });
    }

    // 4. Comercial primero, externo después. Las respuestas obsoletas se descartan.
    async function seleccionarTienda(storeId) {
        contextController?.abort();
        contextController = new AbortController();
        const signal = contextController.signal;
        const version = ++contextVersion;
        selectedStoreId = Number(storeId);
        lastContext = null;
        $('mapStoreSelect').value = String(storeId);
        volarATienda(storeId);
        $('contextContent').innerHTML = '<p class="context-loading">Cargando datos comerciales…</p>';
        $('contextContent').setAttribute('aria-busy','true');
        $('radarSection').style.display = 'none';
        try {
            const contexto = await fetchJSON('contexto',{externo:0},storeId,signal);
            if (version !== contextVersion) return;
            lastContext = contexto;
            mostrarContexto(contexto,true);
            mostrarRadar(contexto);
            $('contextContent').setAttribute('aria-busy','false');
            await cargarContextoExterno(contexto,version,signal);
        } catch (error) {
            if (version !== contextVersion) return;
            $('contextContent').innerHTML = `<p class="context-error">${esc(errorText(error))}</p><button type="button" class="btn btn-outline-secondary" data-retry-context>Reintentar</button>`;
        } finally {
            if (version === contextVersion) $('contextContent').setAttribute('aria-busy','false');
        }
    }

    async function cargarContextoExterno(contexto,version,signal) {
        try {
            const externo = await fetchJSON('contexto',{solo_externo:1},contexto.id,signal);
            if (version !== contextVersion) return;
            lastContext = {...contexto,...externo};
            mostrarContexto(lastContext);
        } catch (error) {
            if (version !== contextVersion) return;
            mostrarContexto(contexto,false,errorText(error));
        }
    }

    const tile = (label,value,html=false) => `<div class="geo-tile"><small>${esc(label)}</small><strong>${html ? value : esc(value)}</strong></div>`;
    function sourceNote(value) {
        return `<p class="geo-v2-data-note">OpenWeather · ${esc(date(value.observado_en))} (Colombia)${value.desactualizado ? ' · Dato desactualizado; pendiente de renovación' : ''}</p>`;
    }
    function trafficNote(value) {
        return `<p class="geo-v2-data-note">TomTom · consulta ${esc(date(value.consultado_en))} (Colombia)${value.desactualizado ? ' · Último dato disponible' : ''}${value.parcial ? ' · Información parcial' : ''}</p>`;
    }
    function iconoClima(code) {
        if (code >= 200 && code < 300) return 'bi-cloud-lightning-rain';
        if (code >= 300 && code < 600) return 'bi-cloud-rain';
        if (code >= 600 && code < 700) return 'bi-cloud-snow';
        if (code >= 700 && code < 800) return 'bi-cloud-fog';
        if (code === 800) return 'bi-sun';
        if (code === 801 || code === 802) return 'bi-cloud-sun';
        return 'bi-clouds';
    }
    const nivelAQI = aqi => aqi <= 2 ? 'ok' : aqi === 3 ? 'mid' : aqi === 4 ? 'low' : 'bad';

    function panelDesempeno(c) {
        if (!c.datos_disponibles) return `<p class="text-muted">Sin datos comerciales en este corte.</p><div class="geo-lectura"><strong>Lectura comercial:</strong> ${esc(c.lectura)}</div>`;
        const cumpl = Number(c.cumplimiento_pct || 0);
        let html = '<div class="geo-tiles">' +
            tile('Ventas',money(c.venta_actual)) +
            tile('Cumplimiento',`<span class="geo-pill ${nivelCumpl(cumpl)}">${esc(pct(cumpl*100))}</span>`,true) +
            tile('Conversión',pct(c.conversion)) + tile('Tráfico',num(c.trafico)) +
            tile('Facturas',num(c.facturas)) + tile('Ticket promedio',money(c.ticket_promedio)) + '</div>';
        const names = {ventas:'Ventas',cumplimiento:'Cumplimiento',conversion:'Conversión',trafico:'Tráfico'};
        const detalle = Object.entries(c.score_detalle || {});
        if (detalle.length) {
            html += '<div class="geo-sub-t">Score por componente</div>' + detalle.map(([key,value]) => {
                const v = Number(value) || 0;
                return `<div class="geo-sbar"><span>${esc(names[key] || key)} · ${esc(num((c.score_pesos?.[key] || 0)*100))}%</span><div role="img" aria-label="${esc(names[key] || key)} ${esc(num(v,1))} de 100"><span style="--w:${Math.max(0,Math.min(v,100))/100};background:${COL[nivelScore(v)]}"></span></div><b>${esc(num(v,1))}</b></div>`;
            }).join('');
            html += '<p class="geo-v2-data-note">Referencias del score: ventas $100 millones, cumplimiento 100%, conversión 40%, tráfico 10.000 visitas. Es sensible al avance del corte y al tamaño de la tienda.</p>';
        }
        return html + `<div class="geo-lectura"><strong>Lectura comercial:</strong> ${esc(c.lectura)}</div>`;
    }

    function panelClima(c, cargando) {
        if (c.es_virtual) return '<p class="text-muted">Canal virtual: no tiene ubicación física, por eso no hay clima de zona.</p>';
        if (cargando) return '<p class="context-loading">Consultando clima y calidad del aire…</p>';
        const w = c.clima || {}, air = c.calidad_aire || {};
        let html = '';
        if (w.status === 'ok') {
            const code = Number(w.codigo_condicion);
            html += `<div class="geo-wx"><i class="bi ${iconoClima(code)}" aria-hidden="true"></i><div><b>${esc(metric(w.temperatura,' °C'))}</b><small>${esc(w.condicion || '')} · sensación ${esc(metric(w.sensacion_termica,' °C'))}</small></div></div>`;
            html += '<div class="geo-tiles">' + tile('Humedad',metric(w.humedad,'%')) + tile('Viento',metric(w.viento_kmh,' km/h')) +
                tile('Lluvia · última hora',w.lluvia_1h == null ? 'No reportada' : metric(w.lluvia_1h,' mm')) +
                (air.status === 'ok' ? tile('Calidad del aire',`<span class="geo-pill ${nivelAQI(Number(air.aqi))}">${esc(air.aqi)} · ${esc(air.categoria)}</span>`,true) : tile('Calidad del aire','No disponible')) + '</div>';
            if (!w.desactualizado && ((code >= 200 && code < 700) || w.lluvia_1h > 0)) html += '<p class="context-advice mt-2">Dato actual: condiciones meteorológicas potencialmente relevantes. Recomendación: revisar la operación de hoy; no atribuirles una caída histórica sin evidencia adicional.</p>';
            html += sourceNote(w);
        } else html += `<p class="text-muted">${esc(w.message || 'Datos meteorológicos no disponibles')}</p>`;
        if (air.status === 'ok') {
            html += `<details><summary>Ver contaminantes (µg/m³) · escala OpenWeather 1 a 5</summary><div class="geo-polu">${[['PM2.5','pm25'],['PM10','pm10'],['NO₂','no2'],['O₃','o3'],['SO₂','so2'],['CO','co'],['NO','no'],['NH₃','nh3']].map(([label,key]) => `<span>${esc(label)} <b>${esc(metric(air[key]))}</b></span>`).join('')}</div></details>` + sourceNote(air);
        } else if (w.status === 'ok') html += `<p class="text-muted">${esc(air.message || 'Calidad del aire no disponible')}</p>`;
        return html + '<p class="geo-v2-data-note">Contexto externo actual. No representa el tiempo meteorológico del periodo comercial seleccionado ni demuestra causas de variaciones de ventas.</p>';
    }

    function panelMovilidad(c, cargando) {
        if (c.es_virtual) return '<p class="text-muted">Canal virtual: sin movilidad vial.</p>';
        if (cargando) return '<p class="context-loading">Consultando movilidad…</p>';
        const mobility = c.movilidad || {};
        let html = '';
        if (mobility.status === 'ok') {
            if (mobility.congestion_pct != null) {
                const p = Math.max(0, Math.min(Number(mobility.congestion_pct) || 0, 100));
                html += `<div class="geo-tile"><small>Congestión estimada</small><strong>${esc(metric(mobility.congestion_pct,'%'))}${mobility.nivel ? ' · ' + esc(mobility.nivel) : ''}</strong>` +
                    `<div class="geo-meter" role="img" aria-label="Congestión ${esc(metric(mobility.congestion_pct,'%'))}"><i style="--p:${p}"></i></div><div class="geo-meter-scale"><span>Fluido</span><span>Moderado</span><span>Lento</span></div></div>`;
            } else if (mobility.nivel) html += tile('Estado del tráfico',mobility.nivel);
            const extra = [];
            if (mobility.velocidad_actual_kmh != null) extra.push(tile('Velocidad actual',metric(mobility.velocidad_actual_kmh,' km/h')));
            if (mobility.velocidad_libre_kmh != null) extra.push(tile('Velocidad sin tráfico',metric(mobility.velocidad_libre_kmh,' km/h')));
            if (mobility.demora_min != null) extra.push(tile('Demora del segmento',metric(mobility.demora_min,' min')));
            if (mobility.confianza_pct != null) extra.push(tile('Confianza del dato',metric(mobility.confianza_pct,'%')));
            if (extra.length) html += `<div class="geo-tiles mt-2">${extra.join('')}</div>`;
            if (mobility.cierre_vial) html += '<p class="context-advice mt-2">TomTom reporta cierre vial en el segmento cercano.</p>';
            if (mobility.message) html += `<p class="text-muted">${esc(mobility.message)}</p>`;
            html += trafficNote(mobility);
        } else html += `<p class="text-muted">${esc(mobility.message || 'Movilidad no disponible')}</p>`;
        const events = Array.isArray(c.eventos) ? c.eventos : (Array.isArray(mobility.incidentes) ? mobility.incidentes : []);
        html += '<div class="geo-sub-t">Incidentes viales</div>' + (events.length ? events.map(e => {
            const place = [e.desde,e.hasta].filter(Boolean).join(' → ');
            const detail = [e.categoria,e.severidad ? `severidad ${e.severidad}` : '',e.demora_min != null ? `${num(e.demora_min,1)} min de demora` : '',e.longitud_km != null ? `${num(e.longitud_km,2)} km` : ''].filter(Boolean).join(' · ');
            return `<div class="context-event"><strong>${esc(e.nombre || 'Incidente vial')}</strong>${place ? `<small class="d-block">${esc(place)}</small>` : ''}<span>${esc(detail)}</span></div>`;
        }).join('') : '<p class="text-muted mb-0">Sin incidentes vigentes reportados en el área.</p>');
        return html;
    }

    function mostrarContexto(c,cargando=false,errorExterno='') {
        const precision = {tienda:'Coordenadas de tienda',ciudad:'Ubicación aproximada por ciudad',virtual:'Canal virtual · sin ubicación física',sin_ubicacion:'Ubicación no disponible'};
        const animar = gaugeAnimado !== c.id;
        gaugeAnimado = c.id;
        const score = Math.max(0, Math.min(Number(c.score) || 0, 100));
        const largo = 2*Math.PI*34, final = largo*score/100;
        const gauge = c.datos_disponibles ? `<div class="geo-gauge" title="Opportunity Score"><svg viewBox="0 0 80 80" aria-hidden="true"><circle class="g-bg" cx="40" cy="40" r="34"/><circle class="g-fg" cx="40" cy="40" r="34" style="stroke:${COL[nivelScore(score)]};stroke-dasharray:${animar ? 0 : final} ${largo}"/></svg><div class="g-val"><b>${esc(num(score,0))}</b><small>score</small></div></div>` : '';
        const tabs = [['des','bi-graph-up','Desempeño'],['cli','bi-cloud-sun','Clima'],['mov','bi-sign-turn-right','Movilidad']];
        let html = `<div class="geo-cx${animar ? ' anim' : ''}">` +
            `<div class="geo-cx-head"><div><h4>${esc(c.nombre)}</h4><div class="geo-cx-sub">${esc(c.codigo)} · ${esc(c.ciudad || 'N/D')} <span class="geo-chip">${esc(c.clima_zona || 'Sin clima')}</span></div>` +
            `<p class="geo-v2-data-note">${esc(precision[c.precision_ubicacion] || '')}${c.lat != null ? ` · ${esc(num(c.lat,4))}, ${esc(num(c.lng,4))}` : ''}</p></div>${gauge}</div>` +
            `<p class="context-period">${esc(c.periodo)}</p>` +
            `<div class="geo-cx-tabs" role="tablist" aria-label="Información de la tienda">${tabs.map(([id,icon,label]) => `<button type="button" role="tab" id="geoTab-${id}" aria-controls="geoPane-${id}" data-tab="${id}" aria-selected="false" tabindex="-1"><i class="bi ${icon}" aria-hidden="true"></i> ${label}</button>`).join('')}</div>` +
            `<div class="geo-cx-pane" role="tabpanel" id="geoPane-des" aria-labelledby="geoTab-des" data-pane="des" hidden>${panelDesempeno(c)}</div>` +
            `<div class="geo-cx-pane" role="tabpanel" id="geoPane-cli" aria-labelledby="geoTab-cli" data-pane="cli" hidden>${panelClima(c,cargando)}</div>` +
            `<div class="geo-cx-pane" role="tabpanel" id="geoPane-mov" aria-labelledby="geoTab-mov" data-pane="mov" hidden>${panelMovilidad(c,cargando)}</div>`;
        if (errorExterno) html += `<p class="text-muted">${esc(errorExterno)}</p>`;
        if (!cargando && !c.es_virtual && c.lat != null) html += '<div class="geo-cx-foot"><button type="button" class="btn btn-sm btn-outline-secondary" data-refresh-external><i class="bi bi-arrow-clockwise"></i> Actualizar contexto</button></div>';
        html += '</div>';
        $('contextContent').innerHTML = html;
        activarTab(tabActual, false);
        if (animar) setTimeout(() => {
            const fg = $('contextContent').querySelector('.g-fg');
            if (fg) fg.style.strokeDasharray = `${final} ${largo}`;
        }, 40);
    }

    function activarTab(tab, foco=false) {
        tabActual = tab;
        $('contextContent').querySelectorAll('[data-tab]').forEach(b => {
            const on = b.dataset.tab === tab;
            b.setAttribute('aria-selected', String(on));
            b.tabIndex = on ? 0 : -1;
            if (on && foco) b.focus();
        });
        $('contextContent').querySelectorAll('[data-pane]').forEach(p => { p.hidden = p.dataset.pane !== tab; });
    }
    $('contextContent')?.addEventListener('keydown', event => {
        const actual = event.target.closest('[data-tab]');
        if (!actual || !['ArrowLeft','ArrowRight'].includes(event.key)) return;
        const orden = ['des','cli','mov'];
        const i = (orden.indexOf(actual.dataset.tab) + (event.key === 'ArrowRight' ? 1 : -1) + orden.length) % orden.length;
        activarTab(orden[i], true);
    });

    function mostrarRadar(contexto) {
        if (!contexto.datos_disponibles || !contexto.radar || typeof Chart === 'undefined') return;
        const labels = Object.keys(contexto.radar);
        if (!labels.length) return;
        $('radarSection').style.display = 'block';
        if (radarChartInstance) radarChartInstance.destroy();
        radarChartInstance = new Chart($('radarChart'), {
            type:'radar', data:{labels,datasets:[{label:contexto.nombre,data:labels.map(l => contexto.radar[l].score),backgroundColor:'rgba(197,168,128,.2)',borderColor:'#8B7D6B',borderWidth:2,pointBackgroundColor:'#8B7D6B'}]},
            options:{responsive:true,maintainAspectRatio:false,scales:{r:{beginAtZero:true,max:100,ticks:{stepSize:20}}},plugins:{legend:{display:false}}}
        });
    }

    // 7. Alertas y oportunidades conservan sus listas y tipos originales.
    async function cargarOportunidadesYAlertas() {
        await Promise.all(['oportunidades','alertas'].map(async name => {
            try {
                const items = await fetchJSON(name);
                if (!Array.isArray(items)) throw new Error('Respuesta no válida.');
                if (name === 'oportunidades') renderOportunidades(items); else renderAlertas(items);
            } catch (error) {
                $(name === 'oportunidades' ? 'oportunidadesList' : 'alertasList').innerHTML = `<p class="text-muted">${esc(errorText(error))}</p>`;
            }
        }));
    }
    function renderList(items,containerId,countId,empty) {
        $(countId).textContent = String(items.length);
        $(containerId).innerHTML = items.length ? items.map(item => {
            const type = ['danger','warning','info','success'].includes(item.tipo) ? item.tipo : 'info';
            return `<div class="geo-v2-list-item alert-${type}"><div class="geo-v2-list-item-title">${esc(item.titulo)}</div><div class="geo-v2-list-item-desc">${esc(item.descripcion)}</div><small>${esc(item.evidencia || 'Dato comercial')}</small><p class="mb-0 mt-2">${esc(item.recomendacion || '')}</p></div>`;
        }).join('') : `<p class="text-muted">${esc(empty)}</p>`;
    }
    function renderOportunidades(items) { renderList(items,'oportunidadesList','oppCount','No hay oportunidades detectadas para esta selección.'); }
    function renderAlertas(items) { renderList(items,'alertasList','alertCount','No hay alertas detectadas para esta selección.'); }

    // Gráficas.
    const TIP = {backgroundColor:COL.text, padding:10, cornerRadius:8, displayColors:false};
    const GRID = 'rgba(139,125,107,.1)';
    function chartMessage(id,message) {
        const canvas = $(id);
        if (!canvas) return;
        canvas.hidden = true;
        const parent = canvas.parentNode;
        let messageNode = parent.querySelector('.chart-message');
        if (!messageNode) { messageNode=document.createElement('p'); messageNode.className='chart-message text-muted'; parent.append(messageNode); }
        messageNode.textContent = message;
    }
    function drawChart(id,options) {
        if (!$(id)) return;
        if (typeof Chart === 'undefined') { chartMessage(id,'No se pudo cargar la biblioteca de gráficos. Los datos siguen disponibles en las tablas.'); return; }
        charts[id]?.destroy();
        $(id).hidden = false;
        $(id).parentNode.querySelector('.chart-message')?.remove();
        options.options = options.options || {};
        options.options.animation = {duration:900, easing:'easeOutQuart'};
        charts[id] = new Chart($(id),options);
    }

    function renderCiudadChart() {
        const ciudades = config.ciudades || [];
        if (!ciudades.length) { chartMessage('ciudadChart','Sin datos para esta selección.'); return; }
        const qConv = cuartiles(ciudades.map(c => Number(c.conversion)));
        const cfg = {
            ventas:{label:'Ventas', v:c => Number(c.ventas), f:money, corto:moneyCorto, color:() => COL.goldD},
            cumplimiento:{label:'Cumplimiento', v:c => Number(c.cumplimiento)*100, f:pct, corto:v => num(v,0) + '%', color:c => COL[nivelCumpl(Number(c.cumplimiento))]},
            conversion:{label:'Conversión', v:c => Number(c.conversion), f:pct, corto:v => num(v,0) + '%', color:c => COL[nivelQ(Number(c.conversion),qConv)]}
        }[metricaCiudad];
        const data = [...ciudades].sort((a,b) => cfg.v(b) - cfg.v(a));
        const box = $('ciudadChartBox');
        if (box) box.style.height = Math.max(300, data.length*30 + 60) + 'px';
        drawChart('ciudadChart',{type:'bar',
            data:{labels:data.map(c => c.ciudad), datasets:[{label:cfg.label, data:data.map(cfg.v),
                backgroundColor:data.map(c => cfg.color(c) + 'D9'), hoverBackgroundColor:data.map(c => cfg.color(c)), borderRadius:6, maxBarThickness:20}]},
            options:{indexAxis:'y', responsive:true, maintainAspectRatio:false,
                plugins:{legend:{display:false}, tooltip:{...TIP, callbacks:{label:ctx => {
                    const c = data[ctx.dataIndex];
                    return [`${cfg.label}: ${cfg.f(ctx.raw)}`, `${c.tiendas} tienda(s) · cumplimiento ${pct(Number(c.cumplimiento)*100)}`];
                }}}},
                scales:{x:{beginAtZero:true, grid:{color:GRID}, ticks:{callback:v => cfg.corto(v)}}, y:{grid:{display:false}, ticks:{color:COL.text, font:{weight:'600'}}}}}});
    }
    $('ciudadMetric')?.addEventListener('click', event => {
        const button = event.target.closest('button[data-m]');
        if (!button) return;
        activarSegmento($('ciudadMetric'), button);
        metricaCiudad = button.dataset.m;
        const card = $('ciudadCard');
        const grafica = card.querySelector('[data-view-toggle] button[data-v="g"]');
        if (grafica) cambiarVista(card, grafica);
        renderCiudadChart();
    });

    function colorClima(nombre) {
        const n = String(nombre || '').normalize('NFD').replace(/[̀-ͯ]/g,'').toUpperCase();
        if (n.includes('FRI')) return '#7C93A3';
        if (n.includes('TEMPL')) return '#6B7D3F';
        if (n.includes('CAL')) return '#C96F4A';
        if (n.includes('COST')) return '#C9952F';
        if (n.includes('VIRT')) return '#8B7D6B';
        return '#A8865A';
    }
    function renderClimaChart() {
        const climas = config.climas || [];
        if (!climas.length) { chartMessage('climaVentasChart','Sin datos para esta selección.'); return; }
        const total = climas.reduce((s,c) => s + Number(c.ventas || 0), 0);
        const data = [...climas].sort((a,b) => b.ventas - a.ventas);
        drawChart('climaVentasChart',{type:'bar',
            data:{labels:data.map(c => c.clima), datasets:[{label:'Ventas por clima de zona', data:data.map(c => c.ventas),
                backgroundColor:data.map(c => colorClima(c.clima) + 'D9'), hoverBackgroundColor:data.map(c => colorClima(c.clima)), borderRadius:8, maxBarThickness:46}]},
            options:{responsive:true, maintainAspectRatio:false,
                plugins:{legend:{display:false}, tooltip:{...TIP, callbacks:{label:ctx => {
                    const c = data[ctx.dataIndex];
                    return [`Ventas ${money(c.ventas)}${total ? ` (${pct(c.ventas/total*100)} del total)` : ''}`, `${c.tiendas} tienda(s) · cumplimiento ${pct(Number(c.cumplimiento)*100)}`];
                }}}},
                scales:{y:{beginAtZero:true, grid:{color:GRID}, ticks:{callback:v => moneyCorto(v)}}, x:{grid:{display:false}, ticks:{color:COL.text, font:{weight:'600'}}}}}});
    }

    function renderTraficoVentasChart() {
        const puntos = tiendasData.filter(t => !t.es_virtual && Number(t.trafico) > 0);
        if (puntos.length < 2) { chartMessage('traficoVentasChart','Sin datos suficientes de tráfico para esta selección.'); return; }
        const mx = mediana(puntos.map(t => Number(t.trafico))), my = mediana(puntos.map(t => Number(t.venta_actual)));
        const zona = t => Number(t.trafico) >= mx ? (Number(t.venta_actual) >= my ? 'ok' : 'bad') : (Number(t.venta_actual) >= my ? 'mid' : 'low');
        const maxVenta = Math.max(...puntos.map(t => Number(t.venta_actual)), 1);
        const conNombre = new Set([
            ...puntos.filter(t => zona(t) === 'bad').sort((a,b) => b.trafico - a.trafico).slice(0,4).map(t => t.id),
            ...[...puntos].sort((a,b) => b.venta_actual - a.venta_actual).slice(0,2).map(t => t.id)
        ]);
        const cuadrantes = {id:'geoCuadrantes',
            beforeDatasetsDraw(chart) {
                const {ctx, chartArea:a, scales:{x,y}} = chart;
                const px = Math.min(Math.max(x.getPixelForValue(mx), a.left), a.right), py = Math.min(Math.max(y.getPixelForValue(my), a.top), a.bottom);
                ctx.save();
                [[px,a.top,a.right-px,py-a.top,'rgba(107,125,63,.07)'],[a.left,a.top,px-a.left,py-a.top,'rgba(201,149,47,.06)'],
                 [px,py,a.right-px,a.bottom-py,'rgba(181,90,78,.08)'],[a.left,py,px-a.left,a.bottom-py,'rgba(139,125,107,.05)']]
                    .forEach(([x0,y0,w,h,color]) => { ctx.fillStyle = color; ctx.fillRect(x0,y0,w,h); });
                ctx.setLineDash([5,5]); ctx.strokeStyle = 'rgba(139,125,107,.55)'; ctx.lineWidth = 1;
                ctx.beginPath(); ctx.moveTo(px,a.top); ctx.lineTo(px,a.bottom); ctx.moveTo(a.left,py); ctx.lineTo(a.right,py); ctx.stroke();
                ctx.setLineDash([]); ctx.font = '700 11px Inter, sans-serif';
                const rotulo = (texto,x0,y0,alinear,color) => { ctx.textAlign = alinear; ctx.fillStyle = color; ctx.fillText(texto,x0,y0); };
                rotulo('Estrellas', a.right-8, a.top+16, 'right', COL.ok);
                rotulo('Venden con poco tráfico', a.left+8, a.top+16, 'left', '#8E6512');
                rotulo('Mucha gente, poca venta', a.right-8, a.bottom-10, 'right', COL.bad);
                rotulo('Por impulsar', a.left+8, a.bottom-10, 'left', COL.muted);
                ctx.restore();
            },
            afterDatasetsDraw(chart) {
                const {ctx, chartArea:a} = chart;
                ctx.save(); ctx.font = '600 11px Inter, sans-serif'; ctx.fillStyle = COL.text;
                chart.getDatasetMeta(0).data.forEach((pt,i) => {
                    const t = puntos[i];
                    if (!conNombre.has(t.id)) return;
                    const derecha = pt.x > a.right - 120;
                    ctx.textAlign = derecha ? 'right' : 'left';
                    ctx.fillText(t.nombre, pt.x + (derecha ? -10 : 10), pt.y + 4);
                });
                ctx.restore();
            }};
        drawChart('traficoVentasChart',{type:'scatter',
            data:{datasets:[{label:'Tiendas', data:puntos.map(t => ({x:Number(t.trafico), y:Number(t.venta_actual)})),
                backgroundColor:puntos.map(t => COL[zona(t)] + 'CC'), borderColor:'#fff', borderWidth:1.5,
                pointRadius:puntos.map(t => 5 + 6*Math.sqrt(Math.max(t.venta_actual,0)/maxVenta)),
                pointHoverRadius:puntos.map(t => 8 + 6*Math.sqrt(Math.max(t.venta_actual,0)/maxVenta))}]},
            options:{responsive:true, maintainAspectRatio:false, layout:{padding:{right:16, top:4}},
                onClick:(event,elements) => { if (elements.length) { seleccionarTienda(puntos[elements[0].index].id); irAlMapa(); } },
                onHover:(event,elements) => { event.native.target.style.cursor = elements.length ? 'pointer' : 'default'; },
                plugins:{legend:{display:false}, tooltip:{...TIP, callbacks:{title:items => puntos[items[0].dataIndex].nombre,
                    label:ctx => { const t = puntos[ctx.dataIndex]; return [`${money(t.venta_actual)} · ${num(t.trafico)} visitas`, `Conversión ${pct(t.conversion)}`]; }}}},
                scales:{x:{title:{display:true, text:'Visitas a tienda'}, grid:{color:GRID}, ticks:{callback:v => num(v)}},
                        y:{title:{display:true, text:'Ventas'}, grid:{color:GRID}, ticks:{callback:v => moneyCorto(v)}}}},
            plugins:[cuadrantes]});
    }

    function renderLineasChart() {
        const lineas = config.lineas || [];
        if (!lineas.length) { chartMessage('evolucionLineasChart','Sin registros mensuales por línea para esta selección.'); return; }
        drawChart('evolucionLineasChart',{type:'bar',data:{labels:lineas.map(l=>l.linea),datasets:[{label:String(config.anioAnterior),data:lineas.map(l=>l.venta_anterior),backgroundColor:'#D8CABB',borderRadius:4},{label:String(config.anio),data:lineas.map(l=>l.venta_actual),backgroundColor:'#A8865A',borderRadius:4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{tooltip:{...TIP,displayColors:true,callbacks:{label:c => `${c.dataset.label}: ${money(c.raw)}`}}},scales:{y:{beginAtZero:true,grid:{color:GRID},ticks:{callback:v=>moneyCorto(v)}},x:{grid:{display:false}}}}});
    }

    // Tarjetas con vista Gráfica / Tabla.
    function cambiarVista(card, button) {
        activarSegmento(button.closest('[data-view-toggle]'), button);
        card.querySelectorAll('.geo-view').forEach(v => v.classList.toggle('on', v.dataset.view === button.dataset.v));
    }
    document.querySelectorAll('[data-view-toggle]').forEach(seg => seg.addEventListener('click', event => {
        const button = event.target.closest('button[data-v]');
        if (button) cambiarVista(seg.closest('.geo-v2-card'), button);
    }));

    // Tablas ordenables y semáforo de conversión por cuartiles.
    function hacerOrdenable(table) {
        const head = table.tHead?.rows[0], body = table.tBodies[0];
        if (!head || !body) return;
        const ths = [...head.cells];
        let columna = -1, dir = 1;
        ths.forEach((th,i) => {
            if (!th.dataset.sort) return;
            th.classList.add('geo-sortable');
            th.tabIndex = 0;
            th.setAttribute('aria-sort','none');
            th.insertAdjacentHTML('beforeend','<i class="bi bi-chevron-expand" aria-hidden="true"></i>');
            const ordenar = () => {
                if (columna === i) dir = -dir;
                else { columna = i; dir = th.dataset.first === 'asc' || th.dataset.sort === 'text' ? 1 : -1; }
                const filas = [...body.rows].filter(r => r.cells.length === ths.length);
                filas.sort((a,b) => {
                    const va = a.cells[i].dataset.v ?? '', vb = b.cells[i].dataset.v ?? '';
                    if (th.dataset.sort === 'text') return va.localeCompare(vb,'es') * dir;
                    const na = va === '' ? null : Number(va), nb = vb === '' ? null : Number(vb);
                    if (na === null && nb === null) return 0;
                    if (na === null) return 1;
                    if (nb === null) return -1;
                    return (na - nb) * dir;
                });
                filas.forEach(r => body.appendChild(r));
                ths.forEach((h,j) => {
                    const icono = h.querySelector('i.bi');
                    if (!icono) return;
                    const activa = j === columna;
                    icono.className = 'bi ' + (activa ? (dir < 0 ? 'bi-caret-down-fill' : 'bi-caret-up-fill') : 'bi-chevron-expand');
                    h.classList.toggle('on', activa);
                    h.setAttribute('aria-sort', activa ? (dir < 0 ? 'descending' : 'ascending') : 'none');
                });
            };
            th.addEventListener('click', ordenar);
            th.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); ordenar(); } });
        });
    }
    function semaforoConversion(table) {
        const celdas = [...table.querySelectorAll('td[data-conv]')];
        const valores = celdas.map(c => Number(c.dataset.v)).filter(v => Number.isFinite(v) && v > 0);
        if (valores.length < 2) return;
        const q = cuartiles(valores);
        celdas.forEach(c => {
            const v = Number(c.dataset.v), pill = c.querySelector('.geo-pill');
            if (pill && Number.isFinite(v) && v > 0) pill.className = 'geo-pill ' + nivelQ(v,q);
        });
    }
    document.querySelectorAll('table[data-sortable]').forEach(table => { hacerOrdenable(table); semaforoConversion(table); });

    $('rankingSearch')?.addEventListener('input', function () {
        const texto = this.value.toLowerCase().trim();
        let visibles = 0;
        document.querySelectorAll('#rankingTable tbody tr[data-search]').forEach(row => {
            const ver = !texto || row.dataset.search.includes(texto);
            row.hidden = !ver;
            if (ver) visibles++;
        });
        $('rankingEmpty').hidden = visibles > 0;
    });

    // 9. Comparación: dos tarjetas frente a frente; respuestas fuera de orden se descartan.
    async function comparar() {
        const idA = $('compareA')?.value, idB = $('compareB')?.value, results = $('compareResults');
        if (!results) return;
        const version = ++compareVersion;
        if (!idA || !idB || idA === idB) { results.innerHTML = '<p class="text-muted">Selecciona dos tiendas diferentes.</p>'; return; }
        results.innerHTML = '<p class="context-loading">Comparando tiendas…</p>';
        try {
            const data = await fetchJSON('comparacion',{ids:`${idA},${idB}`});
            if (version !== compareVersion) return;
            const [a,b] = data.tiendas || [];
            if (!a || !b) throw new Error('No se pudo completar la comparación.');
            const fields = [['Ventas','ventas',money],['Cumplimiento','cumplimiento',v => pct(v*100)],['Conversión','conversion',pct],
                ['Visitas','trafico',num],['Facturas','facturas',num],['Ticket promedio','ticket_promedio',money],['Opportunity Score','score',v => num(v,1) + '/100']];
            let ganaA = 0, ganaB = 0;
            const filas = fields.map(([label,key,format]) => {
                const va = Number(a[key]), vb = Number(b[key]);
                const max = Math.max(Math.abs(va) || 0, Math.abs(vb) || 0) || 1;
                const wa = va > vb, wb = vb > va;
                ganaA += wa; ganaB += wb;
                const ancho = v => Math.max((Math.abs(v) || 0)/max, 0.02).toFixed(3);
                return `<div class="geo-cmp-row"><span class="a ${wa ? 'w' : ''}">${esc(format(a[key]))}</span>` +
                    `<div class="geo-cmp-mid"><small>${esc(label)}</small><div class="geo-bf" aria-hidden="true"><span><i class="${wa ? 'w' : ''}" style="--w:${ancho(va)}"></i></span><span><i class="${wb ? 'w' : ''}" style="--w:${ancho(vb)}"></i></span></div></div>` +
                    `<span class="${wb ? 'w' : ''}">${esc(format(b[key]))}</span></div>`;
            }).join('');
            const tarjeta = (t,gana,otro) => `<div class="geo-cmp-card ${gana > otro ? 'win' : ''}"><b>${esc(t.nombre)}</b><small>${esc(t.periodo)}</small><span class="geo-crown">${gana > otro ? '<i class="bi bi-trophy-fill" aria-hidden="true"></i> ' : ''}Mejor en ${gana} de ${fields.length}</span></div>`;
            results.innerHTML = `<div class="geo-cmp-head">${tarjeta(a,ganaA,ganaB)}${tarjeta(b,ganaB,ganaA)}</div>${filas}`;
        } catch (error) { if (version === compareVersion) results.innerHTML = `<p class="text-muted">${esc(errorText(error))}</p>`; }
    }
    ['compareA','compareB'].forEach(id => $(id)?.addEventListener('change', comparar));

    function irAlMapa() {
        const destino = window.innerWidth > 1200 ? $('mapCard') : $('contextPanel');
        destino?.scrollIntoView({behavior:'smooth', block:'start'});
    }

    $('closeContext')?.addEventListener('click',function () {
        ++contextVersion;
        contextController?.abort();
        $('contextContent').innerHTML='<p class="text-muted">Selecciona una tienda en el mapa para ver su contexto.</p>';
        $('contextContent').setAttribute('aria-busy','false');
        $('radarSection').style.display='none';
        radarChartInstance?.destroy(); radarChartInstance=null;
        selectedStoreId=null; lastContext=null; gaugeAnimado=null; $('mapStoreSelect').value='';
        marcarSeleccion(null);
    });
    $('mapStoreSelect')?.addEventListener('change',function () { if (this.value) seleccionarTienda(this.value); });
    page?.addEventListener('click',function (event) {
        const button=event.target.closest('[data-store-id]');
        if (button) { seleccionarTienda(button.dataset.storeId); irAlMapa(); }
        const tab=event.target.closest('[data-tab]');
        if (tab) activarTab(tab.dataset.tab);
        if (event.target.closest('[data-retry-context]') && selectedStoreId) seleccionarTienda(selectedStoreId);
        if (event.target.closest('[data-refresh-external]') && lastContext) {
            contextController?.abort(); contextController=new AbortController();
            const version=++contextVersion;
            mostrarContexto(lastContext,true);
            cargarContextoExterno(lastContext,version,contextController.signal);
        }
    });
    // Un fallo de Leaflet o de un gráfico no cancela las otras secciones.
    initMap();
    cargarOportunidadesYAlertas();
    cuandoVisible($('ciudadCard'), renderCiudadChart);
    cuandoVisible($('climaCard'), renderClimaChart);
    cuandoVisible($('evolucionLineasChart')?.closest('.geo-v2-card'), renderLineasChart);
});
