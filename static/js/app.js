/* Pixel Plates - Full App */
const API = '';
let currentUser = null;
let currentToken = null;
let chartRange = 'week';
let lbPeriod = 'daily';

// Init
(function init() {
  const saved = localStorage.getItem('pixelplates_user');
  if (saved) {
    try {
      currentUser = JSON.parse(saved);
      currentToken = currentUser.token;
      if (currentUser.role === 'trainer') {
        showScreen('app');
        goPage('overview');
      } else if (currentUser.approved) {
        if (currentUser.onboarded) {
          showScreen('app');
          goPage('overview');
        } else {
          showScreen('onboard');
        }
      } else {
        showScreen('pending');
      }
    } catch(e) { localStorage.removeItem('pixelplates_user'); }
  }
})();

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id + '-screen').classList.add('active');
}

function goPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelector(`.nav-btn[data-page="${name}"]`).classList.add('active');
  if (name === 'overview') { loadOverview(); loadMeals(); checkStreak(); }
  if (name === 'leaderboard') { loadLeaderboard(); }
  if (name === 'profile') { loadProfile(); }
  if (name === 'analytics') { loadChart(); }
}

function showAuthTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.auth-form').forEach(f => f.classList.add('hidden'));
  if (tab === 'login') {
    document.querySelector('.tab-bar .tab:first-child').classList.add('active');
    document.getElementById('login-form').classList.remove('hidden');
  } else {
    document.querySelector('.tab-bar .tab:last-child').classList.add('active');
    document.getElementById('register-form').classList.remove('hidden');
  }
}

function logoutUser() {
  localStorage.removeItem('pixelplates_user');
  currentUser = null;
  showScreen('auth');
}

// === REGISTER ===
document.getElementById('register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('reg-name').value;
  const email = document.getElementById('reg-email').value;
  const password = document.getElementById('reg-password').value;
  const trainerCode = document.getElementById('reg-trainer-code').value;
  if (password.length < 4) { document.getElementById('reg-error').textContent = 'Password too short'; return; }
  try {
    const f = new FormData(); f.append('email', email); f.append('name', name); f.append('password', password);
    if (trainerCode) f.append('trainer_code', trainerCode);
    const resp = await fetch(API + '/api/auth/register', { method: 'POST', body: f });
    const data = await resp.json();
    if (!resp.ok) { document.getElementById('reg-error').textContent = data.detail || 'Failed'; return; }
    const lf = new FormData(); lf.append('email', email); lf.append('password', password);
    const lr = await fetch(API + '/api/auth/login', { method: 'POST', body: lf });
    const ld = await lr.json();
    if (lr.ok) {
      currentUser = ld; currentToken = ld.token; currentUser.name = name;
      currentUser.approved = ld.approved;
      currentUser.role = ld.role;
      localStorage.setItem('pixelplates_user', JSON.stringify(currentUser));
      if (ld.role === 'trainer') {
        document.getElementById('reg-error').textContent = '✅ Trainer account created!';
        showScreen('onboard');
      } else if (ld.approved) {
        showScreen('onboard');
      } else {
        showScreen('pending');
      }
    }
  } catch(e) { document.getElementById('reg-error').textContent = 'Connection error'; }
});

// === LOGIN ===
document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  try {
    const f = new FormData(); f.append('email', email); f.append('password', password);
    const resp = await fetch(API + '/api/auth/login', { method: 'POST', body: f });
    const data = await resp.json();
    if (!resp.ok) {
      if (resp.status === 403) {
        document.getElementById('login-error').textContent = data.detail || 'Account pending approval';
        // If they have a saved user with this email, show pending
        showScreen('pending');
        return;
      }
      document.getElementById('login-error').textContent = data.detail || 'Invalid';
      return;
    }
    currentUser = data; currentToken = data.token;
    currentUser.approved = data.approved;
    currentUser.role = data.role;
    localStorage.setItem('pixelplates_user', JSON.stringify(currentUser));
    if (data.role === 'trainer' || data.approved) {
      const ur = await fetch(API + '/api/user/' + data.user_id);
      const ud = await ur.json();
      if (ud.onboarded) {
        currentUser.onboarded = true;
        localStorage.setItem('pixelplates_user', JSON.stringify(currentUser));
        showScreen('app'); goPage('overview');
      } else { showScreen('onboard'); }
    } else {
      showScreen('pending');
    }
  } catch(e) { document.getElementById('login-error').textContent = 'Connection error'; }
});

// === PENDING APPROVAL ===
async function checkPendingApproval() {
  if (!currentUser) return;
  const status = document.getElementById('pending-status');
  status.textContent = 'Checking...';
  try {
    const resp = await fetch(API + '/api/auth/login', {
      method: 'POST',
      body: new FormData(document.getElementById('login-form'))
    });
    // Actually let's just try to login with stored credentials
    // Re-login to check approval status
    const f = new FormData();
    f.append('email', currentUser.email || document.getElementById('login-email').value);
    f.append('password', currentUser._pendingPassword || '');
    // Simpler: fetch user info
    if (currentUser.user_id) {
      const ur = await fetch(API + '/api/user/' + currentUser.user_id);
      const ud = await ur.json();
      if (ud.approved) {
        currentUser.approved = true;
        localStorage.setItem('pixelplates_user', JSON.stringify(currentUser));
        if (ud.onboarded) {
          showScreen('app'); goPage('overview');
        } else {
          showScreen('onboard');
        }
        return;
      }
    }
    status.textContent = '⏳ Still pending. Remind your trainer!';
  } catch(e) {
    status.textContent = 'Could not check. Try again later.';
  }
  setTimeout(() => { status.textContent = ''; }, 3000);
}

// === ONBOARD ===
document.getElementById('onboard-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = new FormData();
  f.append('user_id', currentUser.user_id);
  f.append('age', document.getElementById('o-age').value);
  f.append('height_cm', document.getElementById('o-height').value);
  f.append('weight_kg', document.getElementById('o-weight').value);
  f.append('gender', document.getElementById('o-gender').value);
  f.append('activity_level', document.getElementById('o-activity').value);
  f.append('goal_type', document.getElementById('o-goal').value);
  try {
    const resp = await fetch(API + '/api/onboard', { method: 'POST', body: f });
    const data = await resp.json();
    if (!resp.ok) { alert(data.detail); return; }
    document.getElementById('o-tdee').textContent = data.tdee;
    document.getElementById('o-goal-val').textContent = data.daily_calorie_goal;
    document.getElementById('o-goal-label').textContent = 'Goal: ' + data.goal_label;
    if (data.macros) {
      const m = data.macros;
      document.getElementById('macro-bars-onboard').innerHTML =
        `<div class="macro-row"><span class="macro-label" style="color:var(--accent)">Protein</span><div class="macro-bar-bg"><div class="macro-bar-fill protein" style="width:${m.protein_pct}%"></div></div><span class="macro-value">${m.protein_g}g</span></div>` +
        `<div class="macro-row"><span class="macro-label" style="color:var(--gold)">Carbs</span><div class="macro-bar-bg"><div class="macro-bar-fill carbs" style="width:${m.carbs_pct}%"></div></div><span class="macro-value">${m.carbs_g}g</span></div>` +
        `<div class="macro-row"><span class="macro-label" style="color:var(--accent2)">Fat</span><div class="macro-bar-bg"><div class="macro-bar-fill fat" style="width:${m.fat_pct}%"></div></div><span class="macro-value">${m.fat_g}g</span></div>`;
    }
    document.getElementById('onboard-result').classList.remove('hidden');
    currentUser.onboarded = true;
    localStorage.setItem('pixelplates_user', JSON.stringify(currentUser));
  } catch(e) { alert('Connection error'); }
});

function reOnboard() { showScreen('onboard'); }

// === OVERVIEW ===
async function loadOverview() {
  if (!currentUser) return;
  try {
    const resp = await fetch(API + '/api/dashboard/' + currentUser.user_id);
    const d = await resp.json();
    if (!resp.ok) return;

    document.getElementById('ov-name').textContent = d.name || '';
    document.getElementById('ov-streak').textContent = d.streak;
    document.getElementById('ov-points').textContent = d.total_points;
    document.getElementById('ov-credits').textContent = d.credits;
    document.getElementById('ov-cal').textContent = d.today.total_calories;
    document.getElementById('ov-goal').textContent = d.today.goal;

    const pct = Math.min(100, (d.today.total_calories / d.today.goal) * 100);
    document.getElementById('ov-cal-progress').style.width = pct + '%';

    const s = document.getElementById('ov-status');
    if (d.today.goal_met) { s.textContent = '✅ Goal met!'; s.style.color = 'var(--success)'; }
    else if (d.today.meal_count > 0) {
      const r = d.today.goal - d.today.total_calories;
      s.textContent = r > 0 ? `🍽️ ${r} cal remaining` : `⚠️ Over by ${Math.abs(r)} cal`;
      s.style.color = 'var(--warn)';
    } else { s.textContent = '📸 Log a meal!'; s.style.color = 'var(--text-dim)'; }

    const t = d.today;
    document.getElementById('ov-macros').innerHTML =
      `<div class="macro-row"><span class="macro-label" style="color:var(--accent)">Protein</span>
        <div class="macro-bar-bg"><div class="macro-bar-fill protein" style="width:${Math.min(100,(t.total_protein/(t.goal_protein||1))*100)}%"></div></div>
        <span class="macro-value">${t.total_protein}/${t.goal_protein}g</span></div>` +
      `<div class="macro-row"><span class="macro-label" style="color:var(--gold)">Carbs</span>
        <div class="macro-bar-bg"><div class="macro-bar-fill carbs" style="width:${Math.min(100,(t.total_carbs/(t.goal_carbs||1))*100)}%"></div></div>
        <span class="macro-value">${t.total_carbs}/${t.goal_carbs}g</span></div>` +
      `<div class="macro-row"><span class="macro-label" style="color:var(--accent2)">Fat</span>
        <div class="macro-bar-bg"><div class="macro-bar-fill fat" style="width:${Math.min(100,(t.total_fat/(t.goal_fat||1))*100)}%"></div></div>
        <span class="macro-value">${t.total_fat}/${t.goal_fat}g</span></div>`;
  } catch(e) {}
}

// === MEALS ===
async function loadMeals() {
  if (!currentUser) return;
  try {
    const resp = await fetch(API + '/api/meals/' + currentUser.user_id);
    const meals = await resp.json();
    const list = document.getElementById('ov-meals');
    if (!meals.length) { list.innerHTML = '<p class="muted">No meals logged yet</p>'; return; }
    list.innerHTML = meals.map(m =>
      `<div class="meal-item">
        <span class="cal">${m.calories}</span>
        <span class="name">${m.food_name || 'Unknown'}<span class="meal-macros">P:${m.protein}g C:${m.carbs}g F:${m.fat}g</span></span>
        <span class="time">${m.time ? new Date(m.time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) : ''}</span>
        <button class="del-btn" onclick="deleteMeal(${m.id})">✕</button>
      </div>`).join('');
  } catch(e) {}
}

async function deleteMeal(id) {
  try { await fetch(API + '/api/meals/' + id, { method: 'DELETE' }); loadMeals(); loadOverview(); } catch(e) {}
}

// === MEAL FORM ===
document.getElementById('meal-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData();
  form.append('user_id', currentUser.user_id);
  const photo = document.getElementById('meal-photo-camera').files[0] || document.getElementById('meal-photo-gallery').files[0];
  const foodName = document.getElementById('meal-name').value;
  if (!photo && !foodName) { 
    document.getElementById('meal-result-text').textContent = 'Take a photo or type a food';
    document.getElementById('meal-result').classList.remove('hidden');
    return;
  }
  if (photo) form.append('photo', photo);
  else form.append('food_name', foodName);

  document.querySelector('#meal-form .btn').textContent = '⏳...';
  document.querySelector('#meal-form .btn').disabled = true;
  try {
    const resp = await fetch(API + '/api/meals', { method: 'POST', body: form });
    const data = await resp.json();
    const r = document.getElementById('meal-result');
    if (resp.ok) {
      document.getElementById('meal-result-text').innerHTML =
        `<strong>${data.food_name}</strong>: ${data.calories} cal · P:${data.protein}g C:${data.carbs}g F:${data.fat}g<br>
        Daily: ${data.daily_total}/${data.goal} cal · P:${data.daily_protein}/${data.goal_protein}g`;
      r.classList.remove('hidden');
      document.getElementById('meal-photo-camera').value = ''; document.getElementById('meal-photo-gallery').value = ''; document.getElementById('meal-name').value = '';
      document.getElementById('photo-preview').textContent = '';
      loadMeals(); loadOverview(); checkStreak();
    } else { document.getElementById('meal-result-text').textContent = data.detail || 'Error'; r.classList.remove('hidden'); }
  } catch(e) { document.getElementById('meal-result-text').textContent = 'Error'; document.getElementById('meal-result').classList.remove('hidden'); }
  document.querySelector('#meal-form .btn').textContent = '➕ Log Meal';
  document.querySelector('#meal-form .btn').disabled = false;
});

function updatePhotoPreview() {
  const cam = document.getElementById('meal-photo-camera').files[0];
  const gal = document.getElementById('meal-photo-gallery').files[0];
  const f = cam || gal;
  document.getElementById('photo-preview').textContent = f ? '📸 ' + f.name : '';
}
document.getElementById('meal-photo-camera').addEventListener('change', updatePhotoPreview);
document.getElementById('meal-photo-gallery').addEventListener('change', updatePhotoPreview);

// === STREAK BONUS ===
async function checkStreak() {
  if (!currentUser) return;
  try {
    const f = new FormData(); f.append('user_id', currentUser.user_id);
    const resp = await fetch(API + '/api/check-streak', { method: 'POST', body: f });
    const d = await resp.json();
    if (d.bonus > 0) {
      document.getElementById('bonus-card').style.display = 'block';
      document.getElementById('bonus-content').textContent = d.message || `+${d.bonus} credits!`;
      setTimeout(() => document.getElementById('bonus-card').style.display = 'none', 5000);
      loadOverview();
    }
  } catch(e) {}
}

// === LEADERBOARD ===
function switchLeaderboard(period) {
  lbPeriod = period;
  document.querySelectorAll('#page-leaderboard .tab').forEach(t => t.classList.remove('active'));
  const tabs = ['daily','weekly','monthly','yearly'];
  document.querySelectorAll('#page-leaderboard .tab')[tabs.indexOf(period)].classList.add('active');
  loadLeaderboard();
}

async function loadLeaderboard() {
  if (!currentUser) return;
  try {
    const resp = await fetch(API + `/api/leaderboard?period=${lbPeriod}`);
    const data = await resp.json();
    const list = document.getElementById('lb-list');
    const myRank = document.getElementById('lb-my-rank');

    // My rank
    try {
      const mr = await fetch(API + `/api/leaderboard/my-rank/${currentUser.user_id}?period=${lbPeriod}`);
      const md = await mr.json();
      myRank.innerHTML = `<div class="my-rank-inner">
        <span class="my-rank-pos">#${md.rank} of ${md.total_participants}</span>
        <span class="my-rank-pts">🏆 ${md.total_points} pts</span>
        <span class="my-rank-detail">${md.days_logged} days · 🎯${md.cal_points} 🥩${md.pro_points} 🍚${md.carb_points} 🧈${md.fat_points}</span>
      </div>`;
    } catch(e) {
      myRank.innerHTML = '<p class="muted">Log meals to earn points!</p>';
    }

    // Leaderboard list
    const lb = data.leaderboard;
    if (!lb.length) {
      list.innerHTML = '<p class="muted">No entries yet this ${lbPeriod}</p>';
      return;
    }

    const maxPts = lb.length > 0 ? lb[0].total_points : 1;
    list.innerHTML = lb.map((r, i) => {
      const medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${r.rank}`;
      const barW = Math.max(8, (r.total_points / maxPts) * 100);
      const isMe = r.user_id === currentUser.user_id;
      return `<div class="lb-row ${isMe ? 'lb-row-me' : ''}">
        <span class="lb-rank">${medal}</span>
        <span class="lb-name">${r.name}${isMe ? ' (you)' : ''}</span>
        <span class="lb-pts">${r.total_points} pts</span>
        <div class="lb-bar-bg"><div class="lb-bar-fill" style="width:${barW}%"></div></div>
        <span class="lb-detail">${r.days_logged}d · 🎯${r.cal_points} 🥩${r.pro_points} 🍚${r.carb_points} 🧈${r.fat_points}</span>
      </div>`;
    }).join('');
  } catch(e) {}
}

// === ADMIN PANEL ===
async function loadAdminPanel() {
  const panel = document.getElementById('admin-panel');
  if (!panel) return;
  panel.classList.remove('hidden');
  const list = document.getElementById('admin-pending-list');
  try {
    const resp = await fetch(API + '/api/admin/pending-users');
    const users = await resp.json();
    if (!users.length) {
      list.innerHTML = '<p class="muted">No pending requests</p>';
      return;
    }
    list.innerHTML = users.map(u => `
      <div class="admin-user-row">
        <span class="admin-user-info"><strong>${u.name}</strong> · ${u.email}</span>
        <span class="admin-user-date">${u.created_at ? new Date(u.created_at).toLocaleDateString() : ''}</span>
        <div class="admin-user-actions">
          <button class="admin-btn admin-btn-approve" onclick="approveUser(${u.id})">✅ Approve</button>
          <button class="admin-btn admin-btn-deny" onclick="denyUser(${u.id})">❌ Deny</button>
        </div>
      </div>
    `).join('');
  } catch(e) {
    list.innerHTML = '<p class="muted">Could not load</p>';
  }
}

async function approveUser(id) {
  try {
    const resp = await fetch(API + '/api/admin/approve/' + id, { method: 'POST' });
    if (resp.ok) loadAdminPanel();
  } catch(e) {}
}

async function denyUser(id) {
  if (!confirm('Remove this user?')) return;
  try {
    const resp = await fetch(API + '/api/admin/deny/' + id, { method: 'POST' });
    if (resp.ok) loadAdminPanel();
  } catch(e) {}
}

// === PROFILE ===
async function loadProfile() {
  if (!currentUser) return;
  try {
    const resp = await fetch(API + '/api/user/' + currentUser.user_id);
    const d = await resp.json();
    if (!resp.ok) return;
    document.getElementById('prof-email').textContent = d.email;
    document.getElementById('prof-name').textContent = d.name;
    document.getElementById('prof-role').textContent = d.role === 'trainer' ? '👑 Trainer' : 'Client';
    document.getElementById('prof-points').textContent = d.total_points || 0;
    document.getElementById('prof-stats').innerHTML =
      `<p>Age: <strong>${d.age}</strong></p>
       <p>Height: <strong>${d.height_cm} cm</strong></p>
       <p>Weight: <strong>${d.weight_kg} kg</strong></p>
       <p>Gender: <strong>${d.gender}</strong></p>
       <p>Activity: <strong>${d.activity_label || d.activity_level}</strong></p>
       <p>Goal: <strong>${d.goal_label || d.goal_type}</strong></p>
       <p>TDEE: <strong>${d.tdee} cal</strong> → Daily: <strong>${d.daily_calorie_goal} cal</strong></p>`;

    // Load macro sliders
    const p = d.protein_pct || 30;
    const c = d.carbs_pct || 40;
    const f2 = d.fat_pct || 30;
    const cal = d.daily_calorie_goal || 2000;

    document.getElementById('prof-macro-sliders').innerHTML =
      `<div class="macro-slider-row"><label><span style="color:var(--accent)">🥩 Protein</span><span id="slider-p-val">${p}%</span></label>
        <input type="range" id="slider-p" min="10" max="80" value="${p}" oninput="updateSliders()"></div>
       <div class="macro-slider-row"><label><span style="color:var(--gold)">🍚 Carbs</span><span id="slider-c-val">${c}%</span></label>
        <input type="range" id="slider-c" min="5" max="80" value="${c}" oninput="updateSliders()"></div>
       <div class="macro-slider-row"><label><span style="color:var(--accent2)">🧈 Fat</span><span id="slider-f-val">${f2}%</span></label>
        <input type="range" id="slider-f" min="5" max="60" value="${f2}" oninput="updateSliders()"></div>
       <div id="macro-slider-preview" style="margin-top:6px;font-size:12px;color:var(--text-dim);text-align:center">
        ${p}% P · ${c}% C · ${f2}% F → P:${Math.round(cal*p/100/4)}g · C:${Math.round(cal*c/100/4)}g · F:${Math.round(cal*f2/100/9)}g</div>`;

    // Load admin panel if trainer
    if (d.role === 'trainer') {
      loadAdminPanel();
    }
  } catch(e) {}
}

function updateSliders() {
  let p = parseInt(document.getElementById('slider-p').value);
  let c = parseInt(document.getElementById('slider-c').value);
  let f = parseInt(document.getElementById('slider-f').value);
  const total = p + c + f;
  if (total > 100) {
    const excess = total - 100;
    if (p >= c && p >= f) p = Math.max(10, p - excess);
    else if (c >= p && c >= f) c = Math.max(5, c - excess);
    else f = Math.max(5, f - excess);
  }
  document.getElementById('slider-p').value = p; document.getElementById('slider-c').value = c; document.getElementById('slider-f').value = f;
  document.getElementById('slider-p-val').textContent = p + '%';
  document.getElementById('slider-c-val').textContent = c + '%';
  document.getElementById('slider-f-val').textContent = f + '%';
  const cal = 2211; // approximate, gets recalculated on save
  document.getElementById('macro-slider-preview').textContent =
    `${p}% P · ${c}% C · ${f}% F → P:${Math.round(cal*p/100/4)}g · C:${Math.round(cal*c/100/4)}g · F:${Math.round(cal*f/100/9)}g`;
}

async function saveMacros() {
  const p = parseInt(document.getElementById('slider-p').value);
  const c = parseInt(document.getElementById('slider-c').value);
  const f = parseInt(document.getElementById('slider-f').value);
  if (p + c + f !== 100) {
    document.getElementById('macro-save-status').textContent = `⚠️ Must be 100% (${p+c+f}%)`; return; }
  const form = new FormData();
  form.append('user_id', currentUser.user_id);
  form.append('protein_pct', p); form.append('carbs_pct', c); form.append('fat_pct', f);
  try {
    const resp = await fetch(API + '/api/macros', { method: 'POST', body: form });
    if (resp.ok) {
      document.getElementById('macro-save-status').textContent = '✅ Saved!';
      document.getElementById('macro-save-status').style.color = 'var(--success)';
      setTimeout(() => document.getElementById('macro-save-status').textContent = '', 3000);
    } else { document.getElementById('macro-save-status').textContent = (await resp.json()).detail || 'Error'; }
  } catch(e) { document.getElementById('macro-save-status').textContent = 'Connection error'; }
}

// === ANALYTICS CHART ===
function switchChart(range) {
  chartRange = range;
  document.querySelectorAll('#page-analytics .tab').forEach(t => t.classList.remove('active'));
  const tabs = document.querySelectorAll('#page-analytics .tab');
  const idx = range === 'week' ? 0 : range === 'month' ? 1 : 2;
  tabs[idx].classList.add('active');
  loadChart();
}

async function loadChart() {
  if (!currentUser) return;
  try {
    const resp = await fetch(API + `/api/history/${currentUser.user_id}?range=${chartRange}`);
    const data = await resp.json();
    drawChart(data);
    const met = data.filter(d => d.goal_met).length;
    const total = data.filter(d => d.calories > 0).length;
    const avg = total > 0 ? Math.round(data.filter(d => d.calories > 0).reduce((s,d) => s+d.calories, 0) / total) : 0;
    document.getElementById('chart-summary').textContent =
      `📊 Days tracked: ${total} · Goal met: ${met} · Avg: ${avg} cal/day`;
  } catch(e) {}
}

function drawChart(data) {
  const canvas = document.getElementById('chart-canvas');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (!data.length) {
    ctx.fillStyle = '#8899aa'; ctx.font = '14px Inter'; ctx.textAlign = 'center';
    ctx.fillText('No data yet — log some meals!', w/2, h/2);
    return;
  }

  const pad = {top: 20, bottom: 25, left: 35, right: 10};
  const cx = w - pad.left - pad.right;
  const cy = h - pad.top - pad.bottom;

  const maxCal = Math.max(...data.map(d => Math.max(d.calories, d.goal || 2000))) * 1.15;
  const barW = Math.min(16, cx / data.length - 3);

  // Grid lines
  ctx.strokeStyle = '#2a3a5e'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + cy * (1 - i/4);
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w - pad.right, y); ctx.stroke();
    ctx.fillStyle = '#8899aa'; ctx.font = '9px Inter'; ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxCal * i / 4), pad.left - 5, y + 3);
  }

  // Goal line
  if (data[0].goal) {
    const goalY = pad.top + cy * (1 - data[0].goal / maxCal);
    ctx.strokeStyle = '#0f9b8e'; ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(pad.left, goalY); ctx.lineTo(w - pad.right, goalY); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#0f9b8e'; ctx.font = '9px Inter'; ctx.textAlign = 'left';
    ctx.fillText('Goal', w - pad.right - 30, goalY - 3);
  }

  // Bars
  data.forEach((d, i) => {
    const x = pad.left + i * (barW + 3) + cx / data.length / 2 - barW / 2;
    const barH = (d.calories / maxCal) * cy;
    const y = pad.top + cy - barH;
    ctx.fillStyle = d.goal_met ? '#4ade80' : '#e94560';
    ctx.fillRect(x, y, barW, barH);
    // Label
    ctx.fillStyle = '#8899aa'; ctx.font = '8px Inter'; ctx.textAlign = 'center';
    if (data.length <= 8) ctx.fillText(d.label, x + barW/2, h - 5);
  });
}

// Auto refresh
setInterval(() => {
  if (currentUser && document.getElementById('page-overview').classList.contains('active')) {
    loadOverview(); loadMeals();
  }
}, 30000);

console.log('🟢 Pixel Plates loaded!');