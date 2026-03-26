/* ===================================================================
   Interactive dashboard – pure Plotly.js, no server required.
   Loads synthetic JSON and renders the same charts as the Dash app.
   =================================================================== */

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor:  'rgba(0,0,0,0)',
  font: { family: 'Inter, sans-serif', color: '#c8d8c0', size: 13 },
  margin: { l: 50, r: 30, t: 40, b: 50 },
  colorway: [
    '#4ade80','#38bdf8','#facc15','#f472b6','#a78bfa',
    '#fb923c','#34d399','#60a5fa','#f87171','#c084fc',
  ],
};

const PLOTLY_CONFIG = { responsive: true, displayModeBar: false };

let RAW_CLEANED = [];
let RAW_MERGED  = [];

/* ──────────── Bootstrap ──────────── */

Promise.all([
  fetch('data/synthetic_cleaned.json').then(r => r.json()),
  fetch('data/synthetic_merged.json').then(r => r.json()),
]).then(([cleaned, merged]) => {
  RAW_CLEANED = cleaned;
  RAW_MERGED  = merged;
  populateFilters();
  renderAll();
});

/* ──────────── Filters ──────────── */

function populateFilters() {
  const years  = [...new Set(RAW_CLEANED.map(r => r.year))].sort();
  const traits = [...new Set(RAW_CLEANED.map(r => r.TRAIT))].sort();

  const ySel = document.getElementById('yearFilter');
  years.forEach(y => {
    const o = document.createElement('option');
    o.value = y; o.textContent = y;
    ySel.appendChild(o);
  });

  const tSel = document.getElementById('traitFilter');
  traits.forEach(t => {
    const o = document.createElement('option');
    o.value = t; o.textContent = t;
    tSel.appendChild(o);
  });

  ySel.addEventListener('change', renderAll);
  tSel.addEventListener('change', renderAll);
}

function filtered() {
  const yVal = document.getElementById('yearFilter').value;
  const tVal = document.getElementById('traitFilter').value;
  let d = RAW_CLEANED;
  if (yVal !== 'ALL') d = d.filter(r => r.year == yVal);
  if (tVal !== 'ALL') d = d.filter(r => r.TRAIT === tVal);
  return d;
}

function filteredMerged() {
  const yVal = document.getElementById('yearFilter').value;
  const tVal = document.getElementById('traitFilter').value;
  let d = RAW_MERGED;
  if (yVal !== 'ALL') d = d.filter(r => r.trait_year == yVal);
  if (tVal !== 'ALL') d = d.filter(r => r.TRAIT === tVal);
  return d;
}

/* ──────────── Render All ──────────── */

function renderAll() {
  const data = filtered();
  renderTreemap(data);
  renderDonut(data);
  renderHistogram(data);
  renderStability(RAW_CLEANED);
  renderTrend(RAW_CLEANED);
  renderKPI(RAW_CLEANED);
  renderYield(filteredMerged());
  renderTable(RAW_CLEANED);
}

/* ──────────── Treemap ──────────── */

function renderTreemap(data) {
  const counts = {};
  data.forEach(r => {
    const key = r.year + '|' + r.PLF;
    counts[key] = (counts[key] || 0) + 1;
  });

  const labels = [], parents = [], values = [], ids = [];
  const yearTotals = {};

  Object.entries(counts).forEach(([k, v]) => {
    const [yr, plf] = k.split('|');
    yearTotals[yr] = (yearTotals[yr] || 0) + v;
  });

  Object.keys(yearTotals).sort().forEach(yr => {
    ids.push(yr);
    labels.push(yr);
    parents.push('');
    values.push(0);
  });

  Object.entries(counts).forEach(([k, v]) => {
    const [yr, plf] = k.split('|');
    const id = k;
    ids.push(id);
    labels.push(String(plf));
    parents.push(yr);
    values.push(v);
  });

  const trace = {
    type: 'treemap',
    ids, labels, parents, values,
    branchvalues: 'total',
    textinfo: 'label+value',
    marker: {
      colorscale: [[0, '#1a3a1a'], [0.5, '#4ade80'], [1, '#86efac']],
      colors: values,
    },
    hovertemplate: '%{label}: %{value}<extra></extra>',
  };

  Plotly.react('treemapChart', [trace], {
    ...PLOTLY_LAYOUT_BASE,
    margin: { l: 10, r: 10, t: 10, b: 10 },
  }, PLOTLY_CONFIG);
}

/* ──────────── Donut ──────────── */

function renderDonut(data) {
  const totals = {};
  data.forEach(r => { totals[r.company] = (totals[r.company] || 0) + r.qty; });

  let entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);
  if (entries.length > 8) {
    const top8 = entries.slice(0, 8);
    const otherSum = entries.slice(8).reduce((s, e) => s + e[1], 0);
    entries = [...top8, ['Other', otherSum]];
  }

  const trace = {
    type: 'pie', hole: 0.45,
    labels: entries.map(e => e[0]),
    values: entries.map(e => e[1]),
    textinfo: 'percent+label',
    textposition: 'inside',
    marker: { line: { color: '#0f1a0f', width: 2 } },
  };

  Plotly.react('donutChart', [trace], {
    ...PLOTLY_LAYOUT_BASE,
    showlegend: false,
    margin: { l: 20, r: 20, t: 20, b: 20 },
  }, PLOTLY_CONFIG);
}

/* ──────────── Histogram ──────────── */

function renderHistogram(data) {
  const qtys = data.map(r => r.qty);
  const mean = qtys.reduce((a, b) => a + b, 0) / (qtys.length || 1);
  const threshold = mean * 0.5;

  const trace = {
    x: qtys, type: 'histogram', nbinsx: 30,
    marker: { color: '#4ade80', line: { color: '#1a3a1a', width: 1 } },
  };

  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { title: 'Quantity', gridcolor: 'rgba(255,255,255,0.05)' },
    yaxis: { title: 'Count',    gridcolor: 'rgba(255,255,255,0.05)' },
    shapes: [{
      type: 'line', yref: 'paper',
      x0: threshold, x1: threshold, y0: 0, y1: 1,
      line: { dash: 'dash', color: '#facc15', width: 2 },
    }],
    annotations: [{
      x: threshold, y: 1, yref: 'paper', text: `50% mean = ${Math.round(threshold)}`,
      showarrow: false, font: { color: '#facc15', size: 11 }, yanchor: 'bottom',
    }],
    bargap: 0.05,
  };

  Plotly.react('histChart', [trace], layout, PLOTLY_CONFIG);
}

/* ──────────── Stability (CV) ──────────── */

function computeConsistency(data, minYears) {
  const grouped = {};
  data.forEach(r => {
    const k = r.PLF;
    if (!grouped[k]) grouped[k] = {};
    grouped[k][r.year] = (grouped[k][r.year] || 0) + r.qty;
  });

  const results = [];
  Object.entries(grouped).forEach(([plf, yearMap]) => {
    const years = Object.keys(yearMap).map(Number).sort();
    const vals  = years.map(y => yearMap[y]);
    if (years.length < minYears) return;

    const n    = vals.length;
    const mean = vals.reduce((a, b) => a + b, 0) / n;
    const sd   = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / n);
    const cv   = mean > 0 ? sd / mean : NaN;

    const xMean = years.reduce((a, b) => a + b, 0) / n;
    const num = years.reduce((s, x, i) => s + (x - xMean) * (vals[i] - mean), 0);
    const den = years.reduce((s, x) => s + (x - xMean) ** 2, 0);
    const slope = den !== 0 ? num / den : 0;

    results.push({ plf: String(plf), n_years: n, mean, sd, cv, slope });
  });

  return results;
}

function renderStability(data) {
  const cons = computeConsistency(data, 3);
  const sorted = cons.filter(r => !isNaN(r.cv)).sort((a, b) => a.cv - b.cv).slice(0, 25);

  const trace = {
    x: sorted.map(r => r.plf),
    y: sorted.map(r => r.cv),
    type: 'bar',
    marker: { color: sorted.map(r => r.cv), colorscale: [[0,'#4ade80'],[1,'#f87171']], showscale: false },
  };

  Plotly.react('stabilityChart', [trace], {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { title: 'PLF', tickangle: -35, gridcolor: 'rgba(255,255,255,0.05)' },
    yaxis: { title: 'CV (sd/mean)', tickformat: '.2f', gridcolor: 'rgba(255,255,255,0.05)' },
  }, PLOTLY_CONFIG);
}

/* ──────────── Trend (slope) ──────────── */

function renderTrend(data) {
  const cons = computeConsistency(data, 3);
  const sorted = cons
    .filter(r => !isNaN(r.slope))
    .sort((a, b) => Math.abs(b.slope) - Math.abs(a.slope))
    .slice(0, 25);

  const trace = {
    x: sorted.map(r => r.plf),
    y: sorted.map(r => r.slope),
    type: 'bar',
    marker: {
      color: sorted.map(r => r.slope),
      colorscale: [[0,'#f87171'],[0.5,'#fcd34d'],[1,'#4ade80']],
      cmid: 0, showscale: false,
    },
  };

  Plotly.react('trendChart', [trace], {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { title: 'PLF', tickangle: -35, gridcolor: 'rgba(255,255,255,0.05)' },
    yaxis: { title: 'Slope (qty/year)', gridcolor: 'rgba(255,255,255,0.05)' },
  }, PLOTLY_CONFIG);
}

/* ──────────── KPI Gauge ──────────── */

function renderKPI(data) {
  const cons = computeConsistency(data, 3);
  const stable = cons.filter(r => r.cv <= 0.40 && r.n_years >= 3).length;
  const pct = cons.length > 0 ? (100 * stable / cons.length) : 0;

  const trace = {
    type: 'indicator', mode: 'gauge+number',
    value: pct,
    number: { suffix: '%', valueformat: '.1f', font: { size: 38, color: '#4ade80' } },
    title: { text: 'CV ≤ 0.40 & ≥ 3 yrs', font: { size: 14, color: '#b0c4a8' } },
    gauge: {
      axis: { range: [0, 100], tickcolor: '#4a6a4a' },
      bar: { color: '#4ade80', thickness: 0.35 },
      bgcolor: '#1c2e1c',
      borderwidth: 0,
      steps: [
        { range: [0, 40],  color: 'rgba(248,113,113,0.15)' },
        { range: [40, 70], color: 'rgba(252,211,77,0.12)' },
        { range: [70, 100],color: 'rgba(74,222,128,0.12)' },
      ],
    },
  };

  Plotly.react('kpiGauge', [trace], {
    ...PLOTLY_LAYOUT_BASE,
    margin: { l: 30, r: 30, t: 40, b: 20 },
  }, PLOTLY_CONFIG);
}

/* ──────────── Yield by Maturity ──────────── */

function renderYield(data) {
  if (data.length === 0) {
    Plotly.react('yieldChart', [], {
      ...PLOTLY_LAYOUT_BASE,
      annotations: [{ text: 'No yield data for selected filters', showarrow: false, font: { size: 16, color: '#b0c4a8' }, xref: 'paper', yref: 'paper', x: .5, y: .5 }],
    }, PLOTLY_CONFIG);
    return;
  }

  const byMat = {};
  data.forEach(r => {
    const acres = r.Sum_of_Female_Acres;
    const bushels = r.Sum_of_Actual_Bushels;
    if (!acres || !bushels || acres === 0) return;
    const yld = bushels / acres;
    const mat = r.MATURITY;
    if (mat == null) return;
    if (!byMat[mat]) byMat[mat] = [];
    byMat[mat].push(yld);
  });

  const mats = Object.keys(byMat).map(Number).sort((a, b) => a - b);
  const means = [], ciLo = [], ciHi = [];

  mats.forEach(m => {
    const arr = byMat[m];
    const n = arr.length;
    const mean = arr.reduce((a, b) => a + b, 0) / n;
    const sd = Math.sqrt(arr.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1 || 1));
    const se = sd / Math.sqrt(n);
    means.push(mean);
    ciLo.push(mean - 1.96 * se);
    ciHi.push(mean + 1.96 * se);
  });

  const traces = [
    { x: mats, y: ciHi, mode: 'lines', line: { width: 0 }, showlegend: false, hoverinfo: 'skip' },
    { x: mats, y: ciLo, mode: 'lines', line: { width: 0 }, fill: 'tonexty', fillcolor: 'rgba(74,222,128,0.15)', name: '95% CI', hoverinfo: 'skip' },
    { x: mats, y: means, mode: 'lines+markers', name: 'Mean Yield', line: { color: '#4ade80', width: 2 }, marker: { size: 6, color: '#4ade80' } },
  ];

  Plotly.react('yieldChart', traces, {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { title: 'Relative Maturity', gridcolor: 'rgba(255,255,255,0.05)' },
    yaxis: { title: 'Yield (bu / acre)', gridcolor: 'rgba(255,255,255,0.05)' },
    showlegend: true,
    legend: { font: { color: '#b0c4a8' }, bgcolor: 'rgba(0,0,0,0)' },
  }, PLOTLY_CONFIG);
}

/* ──────────── Summary Table ──────────── */

function renderTable(data) {
  const grouped = {};
  data.forEach(r => {
    const k = r.PLF;
    if (!grouped[k]) grouped[k] = {};
    grouped[k][r.year] = (grouped[k][r.year] || 0) + 1;
  });

  const years = [...new Set(data.map(r => r.year))].sort();

  const rows = Object.entries(grouped).map(([plf, ymap]) => {
    const row = { PLF: plf };
    let total = 0, appearing = 0;
    years.forEach(y => {
      const v = ymap[y] || 0;
      row[y] = v;
      total += v;
      if (v > 0) appearing++;
    });
    row.appearances = appearing;
    row.total = total;
    return row;
  }).sort((a, b) => b.appearances - a.appearances || b.total - a.total);

  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');
  thead.innerHTML = '';
  tbody.innerHTML = '';

  const hRow = document.createElement('tr');
  ['PLF', ...years, 'Appearances', 'Total'].forEach(h => {
    const th = document.createElement('th');
    th.textContent = h;
    hRow.appendChild(th);
  });
  thead.appendChild(hRow);

  rows.slice(0, 60).forEach(r => {
    const tr = document.createElement('tr');
    [r.PLF, ...years.map(y => r[y]), r.appearances, r.total].forEach(v => {
      const td = document.createElement('td');
      td.textContent = v;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}
