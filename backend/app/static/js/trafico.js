/* Datos y mapas del histórico. No modifica dashboard.js ni sus animaciones. */
document.addEventListener('DOMContentLoaded', async () => {
  const root = document.getElementById('trafficPage');
  if (!root) return;
  const el = id => document.getElementById(id);
  const nf = new Intl.NumberFormat('es-CO', {maximumFractionDigits: 0});
  const pct = new Intl.NumberFormat('es-CO', {maximumFractionDigits: 2});
  const number = n => n == null ? '—' : nf.format(n);
  const percent = n => n == null ? '—' : pct.format(n) + '%';
  const days = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];
  const cell = (tag, value) => {const n = document.createElement(tag); n.textContent = value; return n;};
  const table = (headers, caption) => {
    const t = document.createElement('table'); t.className = 'traffic-table';
    t.append(cell('caption', caption));
    const tr = document.createElement('tr');
    headers.forEach(h => {const th = cell('th', h); th.scope = 'col'; tr.append(th);});
    const head = document.createElement('thead'); head.append(tr); t.append(head);
    t.append(document.createElement('tbody')); return t;
  };
  const iso = date => date.toISOString().slice(0,10);
  const preset = el('trafficPeriodPreset');
  const fromInput = el('trafficFrom');
  const toInput = el('trafficTo');
  const applyPreset = value => {
    if (!fromInput || !toInput || value === 'custom') return;
    const end = new Date(toInput.value + 'T12:00:00Z');
    const start = new Date(end);
    if (value === '7' || value === '30') start.setUTCDate(end.getUTCDate() - Number(value) + 1);
    if (value === 'month') start.setUTCDate(1);
    if (value === 'previous-month') {
      start.setUTCMonth(end.getUTCMonth() - 1, 1);
      end.setUTCDate(0);
    }
    fromInput.value = iso(start); toInput.value = iso(end);
  };
  if (preset && fromInput && toInput) {
    const distance = Math.round((new Date(toInput.value) - new Date(fromInput.value)) / 86400000) + 1;
    preset.value = distance === 7 ? '7' : distance === 30 ? '30' : 'custom';
    preset.addEventListener('change', () => applyPreset(preset.value));
    [fromInput,toInput].forEach(input => input.addEventListener('change', () => {preset.value='custom';}));
  }
  try {
    const response = await fetch(root.dataset.url + window.location.search, {credentials:'same-origin'});
    if (!response.ok) throw new Error(response.status === 401 ? 'La sesión venció. Inicia sesión nuevamente.' : 'No se pudo consultar el histórico. Revisa los filtros o intenta nuevamente.');
    const data = await response.json();
    const summary = data.resumen;
    el('trafficStatus').textContent = data.diario.length ? '' : 'No hay registros para estos filtros. Prueba otro periodo o consulta si el histórico ya fue importado.';
    el('trafficResults').hidden = false;
    el('trafficTotal').textContent = number(summary.trafico);
    el('invoiceTotal').textContent = number(summary.facturas);
    el('conversionTotal').textContent = percent(summary.conversion);
    el('ticketAverage').textContent = summary.ticket_promedio == null ? '—' : '$' + number(summary.ticket_promedio);
    el('ticketCoverage').textContent = summary.ticket_promedio == null
      ? 'No hay ventas y facturas coincidentes para estas fechas'
      : `${number(summary.ticket_dias_tienda)} días-tienda con ventas y facturas`;
    const cutoff = data.fuentes.fecha_corte_historico || 'sin corte registrado';
    const dailyNote = data.fuentes.diario_posterior_incluido
      ? ` El Excel principal completó ${number(summary.dias_facturas)} días-tienda sin facturas horarias y aportó ${number(summary.dias_trafico)} días-tienda de tráfico posteriores al ${cutoff}.`
      : ` Los totales diarios posteriores al ${cutoff} no se incluyen porque seleccionaste una franja horaria parcial.`;
    el('trafficCoverage').textContent = `Cobertura: ${number(summary.horas_trafico)} horas-tienda con tráfico y ${number(summary.horas_coincidentes)} coincidentes. Conversión calculada con ${number(summary.facturas_comparables)} facturas y ${number(summary.trafico_comparable)} visitas.` + dailyNote + (summary.conversion > 100 ? ' Atención: conversión superior al 100%; revisa la cobertura.' : '');
    const bestDay = [...data.diario].filter(v=>v.trafico!=null).sort((a,b)=>b.trafico-a.trafico)[0];
    const insight = el('trafficInsight')?.querySelector('span');
    if (insight) insight.textContent = bestDay
      ? `El día con mayor tráfico fue ${bestDay.fecha}, con ${number(bestDay.trafico)} personas y una conversión de ${percent(bestDay.conversion)}.`
      : 'No hay suficientes registros para generar una lectura rápida.';
    function change(value) {
      if (value == null) return {text:'—',className:'traffic-change'};
      const sign = value > 0 ? '+' : '';
      return {text:sign + pct.format(value) + '%',className:'traffic-change ' + (value > 0 ? 'up' : value < 0 ? 'down' : 'flat')};
    }
    function comparisonTable() {
      const comparison = data.comparacion;
      const current = comparison.periodo_actual;
      const previous = comparison.periodo_anterior;
      el('comparisonPeriod').textContent = `Periodo actual: ${current.desde} a ${current.hasta}. Año anterior: ${previous.desde} a ${previous.hasta}. Se mantienen la tienda, el día de semana y la calidad seleccionados.`;
      const headers = ['Tienda','Tráfico anterior','Tráfico actual','Variación tráfico','Tickets anteriores','Tickets actuales','Variación tickets'];
      const t = table(headers,'Comparación por tienda y total de la selección.');
      const rows = [{codigo:'',nombre:'TOTAL SELECCIÓN',...comparison.total},...comparison.tiendas];
      rows.forEach(row => {
        const tr = document.createElement('tr');
        const th = cell('th',row.codigo ? `${row.codigo} · ${row.nombre}` : row.nombre); th.scope='row';tr.append(th);
        const trafficChange = change(row.trafico.variacion);
        const invoiceChange = change(row.facturas.variacion);
        [
          {text:number(row.trafico.anterior)}, {text:number(row.trafico.actual)}, trafficChange,
          {text:number(row.facturas.anterior)}, {text:number(row.facturas.actual)}, invoiceChange
        ].forEach(item => {const td=cell('td',item.text);if(item.className)td.className=item.className;tr.append(td);});
        t.tBodies[0].append(tr);
      });
      el('yearComparison').replaceChildren(t);
    }
    comparisonTable();
    const hours = [...new Set([...(data.semana_hora||[]),...(data.tienda_hora||[])].map(v=>v.hora))].sort((a,b)=>a-b);
    function heat(target, rows, cells, rowKey, metric, caption) {
      const map = new Map(cells.map(v=>[`${v[rowKey]}:${v.hora}`,v[metric]]));
      const max = Math.max(0,...cells.map(v=>v[metric] || 0));
      const t = table(['',...hours.map(h=>`${String(h).padStart(2,'0')}:00`)], caption);
      for (const row of rows) {
        const tr = document.createElement('tr'); const th = cell('th', row.label); th.scope='row'; tr.append(th);
        for (const h of hours) {
          const v = map.get(`${row.id}:${h}`);
          const td = cell('td', number(v));
          const level = v == null || max === 0 ? 0 : v/max;
          td.style.background = v == null ? '#eeeae4' : `hsl(160 30% ${96-level*67}%)`;
          td.style.color = level > .55 ? 'white' : '#243f35';
          td.title = `${row.label}, ${h}:00–${h}:59: ${v == null ? 'sin registro' : number(v)}`;
          tr.append(td);
        }
        t.tBodies[0].append(tr);
      }
      el(target).replaceChildren(t);
    }
    function detail(target, rows, name, title) {
      const t = table([title,'Personas','Facturas','Conversión','Ticket promedio','Cobertura'], '«—» indica que el dato no está disponible para esa fila.');
      rows.forEach(v => {
        const tr = document.createElement('tr');const th = cell('th',name(v));th.scope='row';tr.append(th);
        const coverage = `${number(v.horas_coincidentes)} h / ${number(v.dias_coincidentes)} d`;
        [number(v.trafico),number(v.facturas),percent(v.conversion),v.ticket_promedio==null?'—':'$'+number(v.ticket_promedio),coverage].forEach(x=>tr.append(cell('td',x)));
        t.tBodies[0].append(tr);
      }); el(target).replaceChildren(t);
    }
    function drawHeat() {
      const metric = el('heatMetric').value;
      const stores = [...data.tiendas].sort((a,b)=>(b[metric] ?? -1)-(a[metric] ?? -1));
      heat('weekHeat', days.map((label,id)=>({label,id})), data.semana_hora,'dia',metric,'Acumulado por día de semana y hora');
      heat('storeHeat',stores.map(s=>({id:s.id,label:`${s.codigo} · ${s.nombre}`})),data.tienda_hora,'tienda',metric,'Acumulado por tienda y hora');
      detail('trafficRanking', stores, s=>`${s.codigo} · ${s.nombre}`, 'Tienda');
      const peak = [...data.semana_hora].filter(v=>v[metric]!=null).sort((a,b)=>b[metric]-a[metric])[0];
      el('heatPeak').textContent = peak ? `Mayor acumulado: ${days[peak.dia]}, ${peak.hora}:00–${peak.hora}:59 · ${number(peak[metric])} ${metric==='trafico'?'visitas':'facturas'}.` : 'No hay datos del indicador seleccionado.';
    }
    el('heatMetric').addEventListener('change',drawHeat); drawHeat();
    detail('trafficDaily',data.diario,v=>v.fecha,'Fecha');
    if (typeof Chart !== 'undefined' && data.diario.length) {
      const byDate = new Map(data.diario.map(v=>[v.fecha,v]));
      const series = [];
      for (let day = new Date(data.filtros.desde+'T00:00:00Z'); day <= new Date(data.filtros.hasta+'T00:00:00Z'); day.setUTCDate(day.getUTCDate()+1)) {
        const key = day.toISOString().slice(0,10);
        series.push(byDate.get(key) || {fecha:key,trafico:null,facturas:null});
      }
      try {
      new Chart(el('trafficChart'), {type:'line',data:{labels:series.map(v=>v.fecha),datasets:[
        {label:'Personas',data:series.map(v=>v.trafico),borderColor:'#0d5c75',backgroundColor:'#0d5c7518',borderWidth:3,pointRadius:2,tension:.3,fill:true,spanGaps:false,yAxisID:'y'},
        {label:'Facturas',data:series.map(v=>v.facturas),borderColor:'#e0a96d',backgroundColor:'#e0a96d18',borderWidth:2,pointRadius:2,tension:.3,fill:true,spanGaps:false,yAxisID:'y'},
        {label:'Conversión',data:series.map(v=>v.conversion),borderColor:'#2d6a4f',borderDash:[6,4],borderWidth:2,pointRadius:2,tension:.3,spanGaps:false,yAxisID:'percentage'}
      ]},options:{responsive:true,maintainAspectRatio:false,animation:!window.matchMedia('(prefers-reduced-motion: reduce)').matches,
        interaction:{mode:'index',intersect:false},scales:{y:{beginAtZero:true,grid:{color:'rgba(139,125,107,.12)'}},percentage:{beginAtZero:true,position:'right',grid:{drawOnChartArea:false},ticks:{callback:v=>v+'%'}},x:{grid:{display:false},ticks:{maxTicksLimit:8}}},plugins:{legend:{position:'bottom',labels:{usePointStyle:true,padding:18}}}}});
      } catch (_) {el('trafficChartFallback').hidden=false;}
    } else {el('trafficChartFallback').hidden=false;}
  } catch (error) {
    el('trafficResults').hidden=true;
    el('trafficStatus').textContent=error.message || 'No fue posible cargar los datos.';
  }
});
