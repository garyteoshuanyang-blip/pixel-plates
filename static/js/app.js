/* Pixel Plates - Full App */
const API = '';
let currentUser = null;
let currentToken = null;
let chartRange = 'week';
let lbPeriod = 'daily';
let cdDays = 7;
let myLogDays = 7;
let selectedClientId = null;

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
        const clientsBtn = document.getElementById('nav-myclients');
        if (clientsBtn) clientsBtn.style.display = 'block';
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
  // Goal change listener — show/hide custom adjustment
  const goalSelect = document.getElementById('o-goal');
  if (goalSelect) {
    goalSelect.addEventListener('change', function() {
      document.getElementById('custom-adj-field').classList.toggle('hidden', this.value !== 'custom');
    });
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
  const navBtn = document.querySelector(`.nav-btn[data-page="${name}"]`);
  if (navBtn) navBtn.classList.add('active');
  if (name === 'overview') { loadOverview(); loadMeals(); checkStreak(); }
  if (name === 'leaderboard') { loadLeaderboard(); }
  if (name === 'profile') { loadProfile(); loadAchievements(); }
  if (name === 'analytics') { loadChart(); loadMyFoodLog(); }
  if (name === 'myclients') { loadMyClients(); }
  if (name === 'clientdetail') { loadClientDetail(); }
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
        const clientsBtn = document.getElementById('nav-myclients');
        if (clientsBtn) clientsBtn.style.display = 'block';
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
        if (data.role === 'trainer') {
          const clientsBtn = document.getElementById('nav-myclients');
          if (clientsBtn) clientsBtn.style.display = 'block';
        }
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
  if (document.getElementById('o-goal').value === 'custom') {
    f.append('custom_adj', document.getElementById('o-custom-adj').value || 0);
  }
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
        <button class="meal-btn" onclick="openEditMeal(${m.id},'${(m.food_name||'').replace(/'/g, "\\'")}',${m.calories},${m.protein},${m.carbs},${m.fat})">✏️</button>
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

function streakEmoji(days) {
  if (days >= 30) return '🔥🔥🔥';
  if (days >= 14) return '🔥🔥';
  if (days >= 7) return '🔥';
  if (days >= 3) return '⚡';
  if (days >= 1) return '📅';
  return '';
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

    try {
      const mr = await fetch(API + `/api/leaderboard/my-rank/${currentUser.user_id}?period=${lbPeriod}`);
      const md = await mr.json();
      const myStreakEmoji = streakEmoji(md.days_logged);
      myRank.innerHTML = `<div class="my-rank-inner">
        <span class="my-rank-pos">#${md.rank} of ${md.total_participants}</span>
        <span class="my-rank-pts">🏆 ${md.total_points} pts</span>
        <span class="my-rank-detail">${md.days_logged}d · 🎯${md.cal_points} 🥩${md.pro_points} 🍚${md.carb_points} 🧈${md.fat_points}</span>
      </div>`;
    } catch(e) {
      myRank.innerHTML = '<p class="muted">Log meals to earn points!</p>';
    }

    const lb = data.leaderboard;
    if (!lb.length) {
      list.innerHTML = '<p class="muted">No entries yet this ' + lbPeriod + '</p>';
      return;
    }

    const maxPts = lb.length > 0 ? lb[0].total_points : 1;
    list.innerHTML = lb.map((r, i) => {
      const medal = i === 0 ? '👑🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${r.rank}`;
      const barW = Math.max(8, (r.total_points / maxPts) * 100);
      const isMe = r.user_id === currentUser.user_id;
      const se = streakEmoji(r.streak || 0);
      const streakHtml = se ? ` <span class="lb-streak" title="${r.streak}d streak">${se}</span>` : '';
      const kingIcon = r.days_as_king > 0 && i !== 0 ? ` <span class="lb-former-king" title="Was #1 for ${r.days_as_king}d">👑</span>` : '';
      return `<div class="lb-row ${isMe ? 'lb-row-me' : ''}">
        <span class="lb-rank">${medal}</span>
        <span class="lb-name">${r.name}${streakHtml}${kingIcon}${isMe ? ' (you)' : ''}</span>
        <span class="lb-pts">${r.total_points} pts</span>
        <div class="lb-bar-bg"><div class="lb-bar-fill" style="width:${barW}%"></div></div>
        <span class="lb-detail">${r.days_logged}d · 🎯${r.cal_points} 🥩${r.pro_points} 🍚${r.carb_points} 🧈${r.fat_points}${r.streak ? ' · 🔥' + r.streak + 'd' : ''}</span>
      </div>`;
    }).join('');

  } catch(e) {}
}

// === ACHIEVEMENTS ===
async function loadAchievements() {
  if (!currentUser) return;
  const container = document.getElementById('prof-achievements');
  if (!container) return;
  try {
    const resp = await fetch(API + `/api/achievements/${currentUser.user_id}`);
    const data = await resp.json();
    const achs = data.achievements;
    container.innerHTML = `<p style="font-size:11px;color:var(--text-dim);margin-bottom:6px">Unlocked ${data.unlocked_count}/${data.total_count}</p>
      <div class="ach-grid">${achs.map(a => {
        const pct = Math.min(100, (a.progress / a.total) * 100);
        return `<div class="ach-item ${a.unlocked ? 'ach-unlocked' : 'ach-locked'}">
          <span class="ach-emoji">${a.emoji}</span>
          <span class="ach-name">${a.name}</span>
          ${a.unlocked ? '<span class="ach-check">✅</span>' : `<div class="ach-progress-bg"><div class="ach-progress-fill" style="width:${pct}%"></div></div>`}
        </div>`;
      }).join('')}</div>`;
  } catch(e) {
    container.innerHTML = '<p class="muted">Could not load achievements</p>';
  }
}

// === PROFILE ===
async function loadProfile() {
  if (!currentUser) return;
  try {
    const resp = await fetch(API + '/api/user/' + currentUser.user_id);
    const u = await resp.json();
    if (!resp.ok) return;

    document.getElementById('prof-email').textContent = u.email || '';
    document.getElementById('prof-name').textContent = u.name || '';
    document.getElementById('prof-role').textContent = (u.role || '').charAt(0).toUpperCase() + (u.role || '').slice(1);
    document.getElementById('prof-points').textContent = u.total_points || 0;

    const stats = document.getElementById('prof-stats');
    stats.innerHTML = u.onboarded ? `
      <p>Age: <strong>${u.age}</strong></p>
      <p>Height: <strong>${u.height_cm} cm</strong></p>
      <p>Weight: <strong>${u.weight_kg} kg</strong></p>
      <p>Gender: <strong>${u.gender}</strong></p>
      <p>Activity: <strong>${u.activity_label || u.activity_level}</strong></p>
      <p>TDEE: <strong>${u.tdee} cal</strong></p>
      <p>Goal: <strong>${u.daily_calorie_goal} cal</strong> <span class="goal-label">${u.goal_label}</span></p>
      <p>🔥 Streak: <strong>${u.weekly_streak}d</strong> (best: ${u.longest_streak}d)</p>
    ` : '<p class="muted">Complete onboarding to see stats</p>';

    // Macro sliders
    const macroDiv = document.getElementById('prof-macro-sliders');
    if (macroDiv) {
      const p = u.protein_pct || 30;
      const c = u.carbs_pct || 40;
      const f = u.fat_pct || 30;
      macroDiv.innerHTML = `
        <div class="macro-slider-row">
          <label><span style="color:var(--accent)">🥩 Protein</span> <span id="mp-val">${p}%</span></label>
          <input type="range" id="mp-slider" min="10" max="60" value="${p}" oninput="document.getElementById('mp-val').textContent=this.value+'%'">
        </div>
        <div class="macro-slider-row">
          <label><span style="color:var(--gold)">🍚 Carbs</span> <span id="mc-val">${c}%</span></label>
          <input type="range" id="mc-slider" min="10" max="70" value="${c}" oninput="document.getElementById('mc-val').textContent=this.value+'%'">
        </div>
        <div class="macro-slider-row">
          <label><span style="color:var(--accent2)">🧈 Fat</span> <span id="mf-val">${f}%</span></label>
          <input type="range" id="mf-slider" min="10" max="60" value="${f}" oninput="document.getElementById('mf-val').textContent=this.value+'%'">
        </div>
        <p id="macro-total" style="font-size:11px;color:var(--text-dim);text-align:center"></p>`;
    }

    // Admin panel (trainer only)
    const panel = document.getElementById('admin-panel');
    if (panel) {
      if (u.role === 'trainer') {
        panel.classList.remove('hidden');
        loadPendingUsers();
      } else {
        panel.classList.add('hidden');
      }
    }
  } catch(e) {}
}

async function editName() {
  const current = document.getElementById('prof-name').textContent;
  const newName = prompt('Enter your new name:', current);
  if (!newName || newName.trim() === current) return;
  try {
    const fd = new FormData();
    fd.append('user_id', currentUser.user_id);
    fd.append('name', newName.trim());
    const resp = await fetch(API + '/api/user/rename', { method: 'POST', body: fd });
    if (resp.ok) {
      document.getElementById('prof-name').textContent = newName.trim();
      loadOverview();
    } else {
      const d = await resp.json();
      alert(d.detail || 'Failed to rename');
    }
  } catch(e) {
    alert('Connection error');
  }
}

async function saveMacros() {
  if (!currentUser) return;
  const p = parseInt(document.getElementById('mp-slider').value) || 30;
  const c = parseInt(document.getElementById('mc-slider').value) || 40;
  const f = parseInt(document.getElementById('mf-slider').value) || 30;
  const total = p + c + f;
  const status = document.getElementById('macro-save-status');
  if (Math.abs(total - 100) > 1) {
    status.textContent = '⚠️ Percentages must add up to 100%';
    return;
  }
  try {
    const fd = new FormData();
    fd.append('user_id', currentUser.user_id);
    fd.append('protein_pct', p);
    fd.append('carbs_pct', c);
    fd.append('fat_pct', f);
    const resp = await fetch(API + '/api/macros', { method: 'POST', body: fd });
    if (resp.ok) {
      status.textContent = '✅ Macros saved!';
      status.style.color = 'var(--success)';
    } else {
      const d = await resp.json();
      status.textContent = d.detail || 'Error saving';
      status.style.color = 'var(--danger)';
    }
  } catch(e) {
    status.textContent = 'Connection error';
  }
  setTimeout(() => { status.textContent = ''; }, 3000);
}

async function loadPendingUsers() {
  const list = document.getElementById('admin-pending-list');
  if (!list) return;
  try {
    const resp = await fetch(API + '/api/admin/pending-users');
    const users = await resp.json();
    if (!users.length) {
      list.innerHTML = '<p class="muted">No pending requests</p>';
      return;
    }
    list.innerHTML = users.map(u => `
      <div class="admin-user-row">
        <div class="admin-user-info">
          <strong>${u.name}</strong>
          <span class="admin-user-date">${u.email} · ${u.created_at ? new Date(u.created_at).toLocaleDateString() : ''}</span>
        </div>
        <div class="admin-user-actions">
          <button class="admin-btn admin-btn-approve" onclick="approveUser(${u.id})">✅ Approve</button>
          <button class="admin-btn admin-btn-deny" onclick="denyUser(${u.id})">❌ Deny</button>
        </div>
      </div>
    `).join('');
  } catch(e) {
    list.innerHTML = '<p class="muted">Could not load pending users</p>';
  }
}

async function approveUser(id) {
  try {
    await fetch(API + '/api/admin/approve/' + id, { method: 'POST' });
    loadPendingUsers();
  } catch(e) {}
}

async function denyUser(id) {
  try {
    await fetch(API + '/api/admin/deny/' + id, { method: 'POST' });
    loadPendingUsers();
  } catch(e) {}
}

// === ANALYTICS / CHART ===
function switchChart(range) {
  chartRange = range;
  document.querySelectorAll('#page-analytics .tab').forEach(t => t.classList.remove('active'));
  const idx = range === 'week' ? 0 : range === 'month' ? 1 : 2;
  document.querySelectorAll('#page-analytics .tab')[idx].classList.add('active');
  loadChart();
}

async function loadChart() {
  if (!currentUser) return;
  try {
    const resp = await fetch(API + `/api/history/${currentUser.user_id}?range=${chartRange}`);
    const data = await resp.json();
    if (!data.length) {
      document.getElementById('chart-summary').textContent = 'No data yet in this period';
      return;
    }
    const canvas = document.getElementById('chart-canvas');
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Draw bars
    const barCount = data.length;
    const barW = Math.min(20, (w - 30) / barCount);
    const maxCals = Math.max(...data.map(d => d.goal), 1);
    const pad = 20, bottom = h - pad, topPad = 10;
    const chartH = h - pad - topPad;

    // Draw baseline
    ctx.fillStyle = '#334455';
    ctx.fillRect(pad, bottom - 1, w - pad, 1);

    // Goal line (single line across chart, not per bar)
    const avgGoal = data.reduce((s, d) => s + d.goal, 0) / data.length;
    const goalLineY = bottom - (avgGoal / maxCals) * chartH;

    ctx.strokeStyle = '#ffd70044';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(pad, goalLineY);
    ctx.lineTo(w - 5, goalLineY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Goal label
    ctx.fillStyle = '#ffd70066';
    ctx.font = '7px Inter';
    ctx.textAlign = 'right';
    ctx.fillText('goal', w - 5, goalLineY - 2);

    data.forEach((d, i) => {
      const x = pad + i * (barW + 2);
      const calH = (d.calories / maxCals) * chartH;

      // Calorie bar
      ctx.fillStyle = d.goal_met ? '#4ade80' : '#e94560';
      ctx.fillRect(x, bottom - calH, barW, Math.max(calH, 1));

      // Label
      ctx.fillStyle = '#8899aa';
      ctx.font = '8px Inter';
      ctx.textAlign = 'center';
      ctx.fillText(d.label, x + barW / 2, h - 4);
    });

    // Summary
    const totalCals = data.reduce((s, d) => s + d.calories, 0);
    const avgCals = Math.round(totalCals / data.length);
    const metDays = data.filter(d => d.goal_met).length;
    document.getElementById('chart-summary').textContent =
      `📊 Avg ${avgCals} cal/day · ✅ ${metDays}/${data.length} days met goal`;
  } catch(e) {
    document.getElementById('chart-summary').textContent = 'Could not load chart data';
  }


  }


// === MY FOOD LOG (for clients to see own history) ===
function switchMyLogDays(days) {
  myLogDays = parseInt(days);
  document.querySelectorAll('#page-analytics .tab')[0].parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  // Find the tabs in the food log card specifically
  const cards = document.querySelectorAll('#page-analytics .card');
  if (cards[1]) {
    cards[1].querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    const tabs = cards[1].querySelectorAll('.tab');
    const idx = days === '7' ? 0 : days === '14' ? 1 : 2;
    if (tabs[idx]) tabs[idx].classList.add('active');
  }
  loadMyFoodLog();
}

async function loadMyFoodLog() {
  if (!currentUser) return;
  const container = document.getElementById('my-foodlog-list');
  if (!container) return;
  try {
    const resp = await fetch(API + '/api/trainer/client-detail/' + currentUser.user_id + '?days=' + myLogDays);
    const data = await resp.json();
    const days = data.days;
    if (!days.length) {
      container.innerHTML = '<p class="muted" style="padding:12px;text-align:center">No meals logged in this period.</p>';
      return;
    }
    container.innerHTML = days.map(d => {
      const calPct = Math.min(100, (d.calories / d.goal_calories) * 100);
      const proPct = Math.min(100, (d.protein / d.goal_protein) * 100);
      const carbPct = Math.min(100, (d.carbs / d.goal_carbs) * 100);
      const fatPct = Math.min(100, (d.fat / d.goal_fat) * 100);
      const status = d.goal_met ? '✅' : '❌';
      const dateLabel = new Date(d.date + 'T00:00:00+08:00').toLocaleDateString('en-SG', { weekday: 'short', day: 'numeric', month: 'short' });
      const mealsHtml = d.meals.map(m => {
        return `<div class="cd-meal">
          <div class="cd-meal-info">
            <span class="cd-meal-name">${m.food_name || 'Unknown'}</span>
            <span class="cd-meal-cal">${m.calories} cal</span>
            <span class="cd-meal-macros">P:${m.protein}g C:${m.carbs}g F:${m.fat}g</span>
          </div>
        </div>`;
      }).join('');
      return `<div class="cd-day">
        <div class="cd-day-header">
          <span><strong>${dateLabel}</strong> ${status}</span>
          <span class="cd-day-pts">🏆 ${d.total_points} pts</span>
        </div>
        <div class="cd-day-macros">
          <div class="cd-macro-row"><span class="cd-macro-label">Cal</span><div class="cd-bar-bg"><div class="cd-bar-fill" style="width:${calPct}%"></div></div><span class="cd-macro-val">${d.calories}/${d.goal_calories}</span></div>
          <div class="cd-macro-row"><span class="cd-macro-label" style="color:var(--accent)">P</span><div class="cd-bar-bg"><div class="cd-bar-fill protein" style="width:${proPct}%"></div></div><span class="cd-macro-val">${d.protein}/${d.goal_protein}g</span></div>
          <div class="cd-macro-row"><span class="cd-macro-label" style="color:var(--gold)">C</span><div class="cd-bar-bg"><div class="cd-bar-fill carbs" style="width:${carbPct}%"></div></div><span class="cd-macro-val">${d.carbs}/${d.goal_carbs}g</span></div>
          <div class="cd-macro-row"><span class="cd-macro-label" style="color:var(--accent2)">F</span><div class="cd-bar-bg"><div class="cd-bar-fill fat" style="width:${fatPct}%"></div></div><span class="cd-macro-val">${d.fat}/${d.goal_fat}g</span></div>
        </div>
        ${d.meals.length ? mealsHtml : '<p class="muted" style="padding:4px 0">No meals logged</p>'}
      </div>`;
    }).join('');
  } catch(e) {
    container.innerHTML = '<p class="muted" style="padding:12px;text-align:center">Could not load food log</p>';
  }
}

// === MY CLIENTS ===
function viewClientDetail(clientId, clientName) {
  selectedClientId = clientId;
  cdDays = 7;  // Reset to default 7 days
  document.getElementById('cd-client-name').textContent = '👤 ' + clientName;
  // Reset tabs to 7 Days active
  document.querySelectorAll('#page-clientdetail .tab').forEach(t => t.classList.remove('active'));
  const tabs = document.querySelectorAll('#page-clientdetail .tab');
  if (tabs[0]) tabs[0].classList.add('active');
  // Clear date picker
  const dp = document.getElementById('cd-date-picker');
  if (dp) dp.value = '';
  // Clear old data immediately
  const container = document.getElementById('cd-list');
  if (container) container.innerHTML = '<p class="muted" style="padding:20px;text-align:center">Loading...</p>';
  goPage('clientdetail');
}

function switchClientDays(days) {
  cdDays = parseInt(days);
  document.querySelectorAll('#page-clientdetail .tab').forEach(t => t.classList.remove('active'));
  const idx = days === '7' ? 0 : days === '14' ? 1 : 2;
  document.querySelectorAll('#page-clientdetail .tab')[idx].classList.add('active');
  // Set date picker to today
  const dp = document.getElementById('cd-date-picker');
  if (dp) dp.value = '';
  loadClientDetail();
}

function goToClientDate() {
  const datePicker = document.getElementById('cd-date-picker');
  if (!datePicker || !datePicker.value) return;
  cdDays = 1;
  loadClientDetail();
}

async function loadClientDetail() {
  if (!currentUser || !selectedClientId) return;
  const container = document.getElementById('cd-list');
  if (!container) return;
  try {
    const datePicker = document.getElementById('cd-date-picker');
    let url = API + '/api/trainer/client-detail/' + selectedClientId + '?days=' + cdDays;
    if (datePicker && datePicker.value) {
      url = API + '/api/trainer/client-detail/' + selectedClientId + '?days=1&date_str=' + datePicker.value;
    }
    const resp = await fetch(url);
    const data = await resp.json();
    const days = data.days;
    if (!days.length) {
      container.innerHTML = '<p class="muted">No meals logged in this period.</p>';
      return;
    }
    container.innerHTML = days.map(d => {
      const calPct = Math.min(100, (d.calories / d.goal_calories) * 100);
      const proPct = Math.min(100, (d.protein / d.goal_protein) * 100);
      const carbPct = Math.min(100, (d.carbs / d.goal_carbs) * 100);
      const fatPct = Math.min(100, (d.fat / d.goal_fat) * 100);
      const status = d.goal_met ? '✅' : '❌';
      const dateLabel = new Date(d.date + 'T00:00:00+08:00').toLocaleDateString('en-SG', { weekday: 'short', day: 'numeric', month: 'short' });
      const mealsHtml = d.meals.map(m => {
        return `<div class="cd-meal">
          <div class="cd-meal-info">
            <span class="cd-meal-name">${m.food_name || 'Unknown'}</span>
            <span class="cd-meal-cal">${m.calories} cal</span>
            <span class="cd-meal-macros">P:${m.protein}g C:${m.carbs}g F:${m.fat}g</span>
          </div>
        </div>`;
      }).join('');
      return `<div class="cd-day">
        <div class="cd-day-header">
          <span><strong>${dateLabel}</strong> ${status}</span>
          <span class="cd-day-pts">🏆 ${d.total_points} pts</span>
        </div>
        <div class="cd-day-macros">
          <div class="cd-macro-row"><span class="cd-macro-label">Cal</span><div class="cd-bar-bg"><div class="cd-bar-fill" style="width:${calPct}%"></div></div><span class="cd-macro-val">${d.calories}/${d.goal_calories}</span></div>
          <div class="cd-macro-row"><span class="cd-macro-label" style="color:var(--accent)">P</span><div class="cd-bar-bg"><div class="cd-bar-fill protein" style="width:${proPct}%"></div></div><span class="cd-macro-val">${d.protein}/${d.goal_protein}g</span></div>
          <div class="cd-macro-row"><span class="cd-macro-label" style="color:var(--gold)">C</span><div class="cd-bar-bg"><div class="cd-bar-fill carbs" style="width:${carbPct}%"></div></div><span class="cd-macro-val">${d.carbs}/${d.goal_carbs}g</span></div>
          <div class="cd-macro-row"><span class="cd-macro-label" style="color:var(--accent2)">F</span><div class="cd-bar-bg"><div class="cd-bar-fill fat" style="width:${fatPct}%"></div></div><span class="cd-macro-val">${d.fat}/${d.goal_fat}g</span></div>
        </div>
        ${d.meals.length ? mealsHtml : '<p class="muted" style="padding:4px 0">No meals logged</p>'}
      </div>`;
    }).join('');
  } catch(e) {
    container.innerHTML = '<p class="muted">Error loading client data</p>';
  }
}

// Also update the client detail to include a date summary at top
async function loadMyClients() {
  if (!currentUser) return;
  loadTrainerSummary();
  const list = document.getElementById('mc-client-list');
  try {
    const resp = await fetch(API + '/api/trainer/clients/' + currentUser.user_id);
    const clients = await resp.json();
    if (!clients.length) {
      list.innerHTML = '<p class="muted">No clients yet. Approve pending sign-ups in Profile.</p>';
      return;
    }
    list.innerHTML = clients.map(c => `
      <div class="client-row" onclick="viewClientDetail(${c.id}, '${c.name.replace(/'/g, "\\'")}')">
        <span class="client-name">${c.name}</span>
        <span class="client-pts">🏆 ${c.total_points} pts</span>
        <span class="client-arrow">▶</span>
      </div>
    `).join('');
  } catch(e) {
    list.innerHTML = '<p class="muted">Could not load clients</p>';
  }
}

// === EDIT MEAL ===
let editingMealId = null;
let _calManuallyEdited = false;

function autoCalcCalories() {
  const pro = parseFloat(document.getElementById('edit-protein').value) || 0;
  const carbs = parseFloat(document.getElementById('edit-carbs').value) || 0;
  const fat = parseFloat(document.getElementById('edit-fat').value) || 0;
  const cal = Math.round((pro * 4 + carbs * 4 + fat * 9) * 10) / 10;
  document.getElementById('edit-calories').value = cal;
  document.getElementById('edit-calc-badge').style.display = 'inline';
  _calManuallyEdited = false;
}

// Track manual calorie edits
document.addEventListener('focusin', function(e) {
  if (e.target && e.target.id === 'edit-calories') {
    _calManuallyEdited = true;
    document.getElementById('edit-calc-badge').style.display = 'none';
  }
});

function openEditMeal(id, name, cal, pro, carbs, fat) {
  editingMealId = id;
  document.getElementById('edit-food-name').value = name || '';
  document.getElementById('edit-calories').value = cal || 0;
  document.getElementById('edit-protein').value = pro || 0;
  document.getElementById('edit-carbs').value = carbs || 0;
  document.getElementById('edit-fat').value = fat || 0;
  document.getElementById('edit-error').textContent = '';
  _calManuallyEdited = false;
  autoCalcCalories();
  document.getElementById('edit-modal').classList.remove('hidden');
}

function closeEditMeal() {
  document.getElementById('edit-modal').classList.add('hidden');
  editingMealId = null;
}

document.getElementById('edit-meal-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!editingMealId) return;
  const f = new FormData();
  f.append('calories', document.getElementById('edit-calories').value);
  f.append('protein', document.getElementById('edit-protein').value);
  f.append('carbs', document.getElementById('edit-carbs').value);
  f.append('fat', document.getElementById('edit-fat').value);
  f.append('food_name', document.getElementById('edit-food-name').value);
  try {
    const resp = await fetch(API + '/api/meals/' + editingMealId, { method: 'PUT', body: f });
    const data = await resp.json();
    if (resp.ok) {
      closeEditMeal();
      loadMeals(); loadOverview();
    } else {
      document.getElementById('edit-error').textContent = data.detail || 'Error saving';
    }
  } catch(e) {
    document.getElementById('edit-error').textContent = 'Connection error';
  }
});

// === TRAINER SUMMARY ===
async function loadTrainerSummary() {
  if (!currentUser || currentUser.role !== 'trainer') return;
  const container = document.getElementById('mc-summary-list');
  if (!container) return;
  try {
    const resp = await fetch(API + '/api/trainer/summary/' + currentUser.user_id);
    const data = await resp.json();
    const clients = data.clients;
    if (!clients.length) {
      container.innerHTML = '<p class="muted">No data yet this week</p>';
      return;
    }
    container.innerHTML = clients.map(c => {
      const barW = Math.min(100, c.hit_rate);
      const streakEmoji = c.streak >= 5 ? '🔥' : c.streak >= 3 ? '⚡' : '📅';
      return `<div class="summary-row">
        <div class="summary-left">
          <span class="summary-name">${c.name}</span>
          <span class="summary-streak">${streakEmoji} ${c.streak}d streak</span>
        </div>
        <div class="summary-right">
          <span class="summary-pts">🏆 ${c.total_points}</span>
          <div class="summary-bar-bg"><div class="summary-bar-fill" style="width:${barW}%"></div></div>
          <span class="summary-pct">${c.hit_rate}%</span>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    container.innerHTML = '<p class="muted">Could not load summary</p>';
  }
}

// Override loadMyClients to also load summary
const origLoadMyClients = loadMyClients;
loadMyClients = function() {
  if (!currentUser) return;
  loadTrainerSummary();
  origLoadMyClients();
};

// Auto refresh
setInterval(() => {
  if (currentUser && document.getElementById('page-overview').classList.contains('active')) {
    loadOverview(); loadMeals();
  }
}, 30000);

console.log('🟢 Pixel Plates loaded!');