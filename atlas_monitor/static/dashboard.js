const fmt = (n) => Number(n || 0).toLocaleString('en-US');

function platformClass(platform) {
  return `platform-badge platform-badge--${platform}`;
}

function scoreColor(score) {
  if (score >= 66) return 'var(--green)';
  if (score >= 33) return 'var(--amber)';
  return 'var(--red)';
}

/* --- VU-meter style gauge: semicircle arc + needle, built as raw SVG --- */
function gaugeSVG(score) {
  const clamped = Math.max(0, Math.min(100, score));
  const angle = -90 + (clamped / 100) * 180; // -90deg (0) .. +90deg (100)
  const rad = (angle * Math.PI) / 180;
  const cx = 60, cy = 62, r = 46;
  const needleX = cx + r * Math.sin(rad);
  const needleY = cy - r * Math.cos(rad);
  const color = scoreColor(clamped);

  const arc = (startDeg, endDeg, colorVar) => {
    const toXY = (deg) => {
      const rr = (deg * Math.PI) / 180;
      return [cx + r * Math.sin(rr), cy - r * Math.cos(rr)];
    };
    const [x1, y1] = toXY(startDeg);
    const [x2, y2] = toXY(endDeg);
    const largeArc = endDeg - startDeg > 180 ? 1 : 0;
    return `<path d="M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}"
      stroke="${colorVar}" stroke-width="8" fill="none" stroke-linecap="round" opacity="0.35"/>`;
  };

  return `
  <svg width="120" height="76" viewBox="0 0 120 76">
    ${arc(-90, -30, 'var(--red)')}
    ${arc(-30, 30, 'var(--amber)')}
    ${arc(30, 90, 'var(--green)')}
    <line x1="${cx}" y1="${cy}" x2="${needleX}" y2="${needleY}"
      stroke="${color}" stroke-width="3" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="4" fill="${color}"/>
  </svg>`;
}

function meterLine(label, value) {
  const pct = Math.max(0, Math.min(100, value));
  return `
    <div class="meter-line">
      <span class="meter-label">${label}</span>
      <span class="meter-track"><span class="meter-fill" style="width:${pct}%;background:${scoreColor(pct)}"></span></span>
      <span class="meter-value">${pct.toFixed(0)}</span>
    </div>`;
}

function renderPosts(posts) {
  const rack = document.getElementById('rack');
  if (!posts.length) {
    rack.innerHTML = `<div class="empty-state">
      No posts tracked yet. Log a reading above, or run
      <code>python scripts/seed_demo_data.py</code> to see sample data.
    </div>`;
    return;
  }

  rack.innerHTML = posts.map((p) => {
    const latest = p.latest || { views: 0, likes: 0, comments: 0, shares: 0 };
    const vs = p.viral_score;
    return `
    <article class="channel" data-id="${p.id}" data-title="${p.track_title || p.external_id}">
      <div class="channel-top">
        <span class="${platformClass(p.platform)}">${p.platform}</span>
        <span class="gauge-score" style="color:${scoreColor(vs.score)}">${vs.score.toFixed(1)}</span>
      </div>
      <h3 class="channel-title">${p.track_title || '(untitled)'}</h3>
      <p class="channel-artist">${p.artist || p.external_id}</p>
      <div class="gauge-wrap">${gaugeSVG(vs.score)}</div>
      <div class="meter-row">
        ${meterLine('Engage', vs.engagement)}
        ${meterLine('Velocity', vs.velocity)}
        ${meterLine('Scale', vs.scale)}
      </div>
      <div class="channel-metrics">
        <div><span class="k">Views</span>${fmt(latest.views)}</div>
        <div><span class="k">Likes</span>${fmt(latest.likes)}</div>
        <div><span class="k">Comments</span>${fmt(latest.comments)}</div>
        <div><span class="k">Shares</span>${fmt(latest.shares)}</div>
      </div>
    </article>`;
  }).join('');

  rack.querySelectorAll('.channel').forEach((el) => {
    el.addEventListener('click', () => openDetail(el.dataset.id, el.dataset.title));
  });
}

function renderSummary(s) {
  document.getElementById('statPosts').textContent = fmt(s.total_posts);
  document.getElementById('statViews').textContent = fmt(s.total_views);
  document.getElementById('statEngagement').textContent = fmt(s.total_engagement_actions);
  document.getElementById('statAvgScore').textContent = s.average_viral_score.toFixed(1);
}

async function loadAll() {
  const [posts, summary] = await Promise.all([
    fetch('/api/posts').then((r) => r.json()),
    fetch('/api/summary').then((r) => r.json()),
  ]);
  renderPosts(posts);
  renderSummary(summary);
}

/* --------------------------------------------------------- detail --- */

function historyChartSVG(snapshots) {
  const W = 800, H = 240, pad = 30;
  if (snapshots.length < 2) {
    return `<text x="20" y="30" fill="var(--text-muted)" font-size="13">Not enough readings yet for a trend line.</text>`;
  }
  const scores = snapshots.map((s) => s.viral_score);
  const maxScore = Math.max(100, ...scores);
  const stepX = (W - pad * 2) / (snapshots.length - 1);

  const points = scores.map((s, i) => {
    const x = pad + i * stepX;
    const y = H - pad - (s / maxScore) * (H - pad * 2);
    return [x, y];
  });

  const path = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const dots = points.map(([x, y]) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="var(--green)"/>`).join('');
  const gridLines = [0.25, 0.5, 0.75].map((f) => {
    const y = H - pad - f * (H - pad * 2);
    return `<line x1="${pad}" y1="${y}" x2="${W - pad}" y2="${y}" stroke="var(--border)" stroke-width="1"/>`;
  }).join('');

  return `
    ${gridLines}
    <line x1="${pad}" y1="${H - pad}" x2="${W - pad}" y2="${H - pad}" stroke="var(--border)" stroke-width="1.5"/>
    <path d="${path}" fill="none" stroke="var(--green)" stroke-width="2.5"/>
    ${dots}
  `;
}

async function openDetail(postId, title) {
  const data = await fetch(`/api/posts/${postId}/history`).then((r) => r.json());
  const panel = document.getElementById('detailPanel');
  document.getElementById('detailTitle').textContent = `${title} — Viral Score history`;
  document.getElementById('historyChart').innerHTML = historyChartSVG(data.snapshots);
  panel.hidden = false;
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

document.getElementById('closeDetail').addEventListener('click', () => {
  document.getElementById('detailPanel').hidden = true;
});

/* ---------------------------------------------------------- actions --- */

document.getElementById('refreshBtn').addEventListener('click', loadAll);

document.getElementById('resetBtn').addEventListener('click', async () => {
  if (!confirm('This clears all posts and metrics from the database. Continue?')) return;
  await fetch('/api/reset', { method: 'POST' });
  await loadAll();
});

document.getElementById('ingestForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  ['views', 'likes', 'comments', 'shares'].forEach((k) => { payload[k] = Number(payload[k]); });

  const status = document.getElementById('ingestStatus');
  status.textContent = 'Saving...';
  const res = await fetch('/api/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    status.textContent = 'Logged.';
    form.reset();
    await loadAll();
    setTimeout(() => { status.textContent = ''; }, 2000);
  } else {
    const err = await res.json();
    status.textContent = `Error: ${err.error || 'failed'}`;
  }
});

loadAll();
