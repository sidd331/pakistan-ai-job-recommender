/* ==========================================================================
   Pakistan Job AI — Single-Page Application Controller
   ==========================================================================
   Handles: auth state, API calls, dynamic rendering, routing, file upload,
   filtering/sorting, and toast notifications.
   ========================================================================== */

// -------------------------------------------------------------------------
// STATE & THEME
// -------------------------------------------------------------------------
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const themes = ['dark', 'light', 'gradient', 'glass'];
    themes.forEach(t => {
        const btn = document.getElementById(`theme-${t}-btn`);
        if (btn) {
            btn.className = theme === t ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm';
        }
    });
}

// Initialize theme immediately
const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

const state = {
    user: null,
    profile: null,
    matches: [],
    jobs: [],
    stats: null,
    filters: { source: '', location: '', search: '', sort: 'date' },
    loading: { profile: false, matches: false, jobs: false, upload: false },
    filtersData: { sources: [], locations: [] },
    _uploadZoneInitialized: false,   // prevent duplicate listeners
    _uploadInProgress: false,        // prevent concurrent uploads
};

// -------------------------------------------------------------------------
// PORTAL URLS — used as fallback when direct job link is missing
// -------------------------------------------------------------------------
const SOURCE_URLS = {
    'rozee.pk': 'https://www.rozee.pk',
    'mustakbil.com': 'https://www.mustakbil.com',
    'fpsc': 'https://www.fpsc.gov.pk',
    'kppsc': 'https://www.kppsc.gov.pk',
    'spsc': 'https://www.spsc.gos.pk',
    'ajkpsc': 'https://www.ajkpsc.gov.pk',
};

// -------------------------------------------------------------------------
// API CLIENT
// -------------------------------------------------------------------------
const api = {
    async request(method, url, data = null, isFormData = false) {
        const opts = {
            method,
            credentials: 'same-origin',
            headers: {},
        };
        if (data && !isFormData) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(data);
        } else if (data && isFormData) {
            opts.body = data;
        }
        const res = await fetch(url, opts);
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(json.error || `Request failed (${res.status})`);
        }
        return json;
    },

    // Auth
    register: (email, password, name) => api.request('POST', '/auth/register', { email, password, name }),
    login: (email, password) => api.request('POST', '/auth/login', { email, password }),
    logout: () => api.request('POST', '/auth/logout'),
    me: () => api.request('GET', '/auth/me'),

    // Profile
    uploadResume: (formData) => api.request('POST', '/api/upload-resume', formData, true),
    getProfile: () => api.request('GET', '/api/profile'),
    deleteProfile: () => api.request('DELETE', '/api/profile'),

    // Jobs & Matches
    getJobs: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return api.request('GET', `/api/jobs${qs ? '?' + qs : ''}`);
    },
    getMatches: () => api.request('GET', '/api/matches'),
    triggerMatch: () => api.request('POST', '/api/match'),

    // Misc
    getStats: () => api.request('GET', '/api/stats'),
    getFilters: () => api.request('GET', '/api/filters'),
    getConfig: () => api.request('GET', '/api/config'),
    updateSettings: (data) => api.request('PUT', '/api/settings', data),

    // Admin
    adminGetDashboard: () => api.request('GET', '/api/admin/dashboard'),
    adminGetUsers: () => api.request('GET', '/api/admin/users'),
    adminGetJobs: () => api.request('GET', '/api/admin/jobs'),
    adminGetUserProfile: (id) => api.request('GET', `/api/admin/users/${id}/profile`),
    adminToggleUser: (id) => api.request('POST', `/api/admin/users/${id}/toggle`),
    adminDeleteUser: (id) => api.request('DELETE', `/api/admin/users/${id}`),
    adminTriggerSync: () => api.request('POST', '/api/admin/trigger/sync'),
    adminTriggerMatches: () => api.request('POST', '/api/admin/trigger/matches'),
    adminTriggerNotifications: () => api.request('POST', '/api/admin/trigger/notifications'),
    adminGetCustomSources: () => api.request('GET', '/api/admin/custom-sources'),
    adminAddCustomSource: (name, url) => api.request('POST', '/api/admin/custom-sources', {name, url}),
    adminDeleteCustomSource: (id) => api.request('DELETE', `/api/admin/custom-sources/${id}`),
};

// -------------------------------------------------------------------------
// TOAST NOTIFICATIONS
// -------------------------------------------------------------------------
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: '✅', error: '❌', info: 'ℹ️', welcome: '🎉' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('exit');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// -------------------------------------------------------------------------
// WELCOME OVERLAY  (shown after registration)
// -------------------------------------------------------------------------
function showWelcomeOverlay(userName) {
    // Remove any existing welcome
    const existing = document.getElementById('welcome-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'welcome-overlay';
    overlay.innerHTML = `
        <div class="welcome-content">
            <div class="welcome-emoji">🎉</div>
            <h2>Welcome to Pakistan Job AI!</h2>
            <p>Your account has been created successfully, <strong>${escapeHtml(userName)}</strong>!</p>
            <div class="welcome-steps">
                <div class="welcome-step"><span>1️⃣</span> Upload your CV/Resume (PDF or DOCX)</div>
                <div class="welcome-step"><span>2️⃣</span> Our AI will extract your skills & experience</div>
                <div class="welcome-step"><span>3️⃣</span> Get matched with relevant jobs across Pakistan</div>
                <div class="welcome-step"><span>4️⃣</span> Receive email alerts for new matching jobs</div>
            </div>
            <button class="btn btn-primary btn-lg" onclick="dismissWelcome()">🚀 Let's Get Started</button>
        </div>`;
    document.body.appendChild(overlay);

    // Animate in
    requestAnimationFrame(() => overlay.classList.add('active'));
}

function dismissWelcome() {
    const overlay = document.getElementById('welcome-overlay');
    if (overlay) {
        overlay.classList.remove('active');
        setTimeout(() => overlay.remove(), 400);
    }
}

// -------------------------------------------------------------------------
// AUTH STATE MANAGEMENT
// -------------------------------------------------------------------------
async function checkAuth() {
    try {
        const data = await api.me();
        state.user = data.user;
    } catch {
        state.user = null;
    }
    renderApp();
    
    // CRITICAL FIX: Load dashboard data and filters if user is already logged in on page load
    if (state.user) {
        loadDashboardData();
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const errEl = document.getElementById('login-error');
    const btn = e.target.querySelector('button[type="submit"]');

    errEl.classList.remove('visible');
    btn.classList.add('loading');

    try {
        const data = await api.login(email, password);
        state.user = data.user;
        closeModal();
        showToast(`Welcome back, ${state.user.name}! 🎯 Your job assistant is ready.`, 'success', 5000);
        renderApp();
        loadDashboardData();
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('visible');
    } finally {
        btn.classList.remove('loading');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById('register-name').value.trim();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    const errEl = document.getElementById('register-error');
    const btn = e.target.querySelector('button[type="submit"]');

    errEl.classList.remove('visible');
    btn.classList.add('loading');

    try {
        const data = await api.register(email, password, name);
        state.user = data.user;
        closeModal();

        // Show prominent welcome overlay
        showWelcomeOverlay(state.user.name);
        showToast(`Account created! A welcome email has been sent to ${state.user.email} in real-time. 🎉`, 'success', 6000);

        renderApp();
        loadDashboardData();
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('visible');
    } finally {
        btn.classList.remove('loading');
    }
}

async function handleLogout() {
    try {
        await api.logout();
        state.user = null;
        state.profile = null;
        state.matches = [];
        state._uploadZoneInitialized = false;
        showToast('Logged out successfully. See you soon!', 'info');
        renderApp();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// -------------------------------------------------------------------------
// MODAL
// -------------------------------------------------------------------------
function openModal(mode = 'login') {
    const overlay = document.getElementById('auth-modal');
    overlay.classList.add('active');
    document.getElementById('login-form-section').style.display = mode === 'login' ? 'block' : 'none';
    document.getElementById('register-form-section').style.display = mode === 'register' ? 'block' : 'none';
    document.getElementById('modal-title').textContent = mode === 'login' ? 'Welcome Back' : 'Create Account';
    document.getElementById('modal-subtitle').textContent = mode === 'login'
        ? 'Sign in to your job assistant'
        : 'Start getting personalized job recommendations';

    // Clear previous errors
    document.getElementById('login-error').classList.remove('visible');
    document.getElementById('register-error').classList.remove('visible');
}

function closeModal() {
    document.getElementById('auth-modal').classList.remove('active');
}

function switchAuthMode(mode) {
    openModal(mode);
}

// -------------------------------------------------------------------------
// RESUME UPLOAD  (with guard against duplicates)
// -------------------------------------------------------------------------
function initUploadZone() {
    // Guard: only initialize once
    if (state._uploadZoneInitialized) return;

    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('resume-input');
    if (!zone || !input) return;

    state._uploadZoneInitialized = true;

    zone.addEventListener('click', (e) => {
        e.stopPropagation();
        input.click();
    });

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length) handleFileUpload(files[0]);
    });

    input.addEventListener('change', () => {
        if (input.files.length) {
            handleFileUpload(input.files[0]);
            input.value = ''; // reset so same file can be re-selected
        }
    });
}

async function handleFileUpload(file) {
    // Prevent concurrent uploads
    if (state._uploadInProgress) {
        showToast('Upload already in progress, please wait...', 'info');
        return;
    }

    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
        showToast('Please upload a PDF or DOCX file.', 'error');
        return;
    }
    if (file.size > 10 * 1024 * 1024) {
        showToast('File is too large. Maximum size is 10 MB.', 'error');
        return;
    }

    state._uploadInProgress = true;
    state.loading.upload = true;

    // Show upload zone container if hidden
    const uploadContainer = document.getElementById('upload-zone-container');
    if (uploadContainer) uploadContainer.style.display = 'block';

    renderUploadProgress(true, 'Uploading resume...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        // Simulate smooth progress
        let progress = 0;
        const interval = setInterval(() => {
            progress = Math.min(progress + Math.random() * 12, 85);
            updateProgressBar(progress);
        }, 300);

        updateProgressBar(20);
        renderUploadProgress(true, '📄 Parsing resume with AI...');

        const data = await api.uploadResume(formData);

        clearInterval(interval);
        updateProgressBar(95);
        renderUploadProgress(true, '🎯 Matching against job database...');

        state.profile = data.profile;

        // Small delay for visual feedback
        await new Promise(r => setTimeout(r, 500));
        updateProgressBar(100);

        // Show success message
        const skillCount = data.profile.skills ? data.profile.skills.length : 0;
        showToast(`✅ Resume parsed! Found ${skillCount} skills. ${data.matches_count} jobs matched.`, 'success', 5000);

        // Load and display matches
        await loadMatches();

        // Render the profile panel
        renderProfile();

        // Hide upload progress
        renderUploadProgress(false);

    } catch (err) {
        renderUploadProgress(false);
        showToast('❌ ' + err.message, 'error', 6000);
    } finally {
        state._uploadInProgress = false;
        state.loading.upload = false;
    }
}

function renderUploadProgress(show, statusText = '') {
    const el = document.getElementById('upload-progress');
    const statusEl = document.getElementById('upload-status');
    if (!el) return;
    if (show) {
        el.classList.add('active');
        if (statusEl) statusEl.textContent = statusText;
    } else {
        el.classList.remove('active');
        updateProgressBar(0);
    }
}

function updateProgressBar(pct) {
    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = pct + '%';
}

// -------------------------------------------------------------------------
// DATA LOADING
// -------------------------------------------------------------------------
async function loadDashboardData() {
    await Promise.all([
        loadStats(),
        loadProfile(),
        loadMatches(),
        loadJobs(),
        loadFilterOptions(),
    ]);
}

async function loadStats() {
    try {
        state.stats = await api.getStats();
        renderStats();
    } catch { }
}

async function loadProfile() {
    try {
        const data = await api.getProfile();
        state.profile = data.profile;
        renderProfile();
    } catch { }
}

async function loadMatches() {
    // Show skeleton loading
    state.loading.matches = true;
    renderMatches();

    try {
        const data = await api.getMatches();
        state.matches = data.matches || [];
    } catch {
        state.matches = [];
    }

    // CRITICAL FIX: set loading=false BEFORE rendering results
    state.loading.matches = false;
    renderMatches();
}

async function loadJobs() {
    state.loading.jobs = true;
    try {
        const params = {};
        if (state.filters.source) params.source = state.filters.source;
        if (state.filters.location) params.location = state.filters.location;
        if (state.filters.search) params.search = state.filters.search;
        if (state.filters.sort) params.sort = state.filters.sort;
        const data = await api.getJobs(params);
        state.jobs = data.jobs || [];
        renderJobsTable();
    } catch { }
    state.loading.jobs = false;
}

async function loadFilterOptions() {
    try {
        const data = await api.getFilters();
        state.filtersData = data;
        renderFilterOptions();
    } catch { }
}

// -------------------------------------------------------------------------
// RENDERING — MAIN APP
// -------------------------------------------------------------------------
function renderApp() {
    const landing = document.getElementById('landing-section');
    const dashboard = document.getElementById('dashboard-section');
    const navAuth = document.getElementById('nav-auth-buttons');
    const navUser = document.getElementById('nav-user-section');

    if (state.user) {
        landing.style.display = 'none';
        dashboard.classList.add('active');
        navAuth.style.display = 'none';
        navUser.style.display = 'flex';

        // User info
        document.getElementById('nav-user-name').textContent = state.user.name;
        document.getElementById('nav-user-avatar').textContent = (state.user.name || 'U')[0].toUpperCase();
        document.getElementById('dashboard-username').textContent = state.user.name.split(' ')[0];

        // Admin tab: completely hide for non-admin users
        const adminBtn = document.getElementById('nav-btn-admin');
        const adminTab = document.getElementById('tab-admin');
        if (adminBtn) {
            adminBtn.style.display = state.user.is_admin ? 'inline-block' : 'none';
        }
        if (adminTab) {
            // Non-admins can never even see the admin content
            adminTab.style.display = state.user.is_admin ? '' : 'none';
        }

        initUploadZone();
    } else {
        landing.style.display = 'flex';
        dashboard.classList.remove('active');
        navAuth.style.display = 'flex';
        navUser.style.display = 'none';
        loadLandingStats();
    }
}

async function loadLandingStats() {
    try {
        const data = await api.getStats();
        document.getElementById('hero-jobs-count').textContent = data.total_jobs || '0';
        document.getElementById('hero-sources-count').textContent = Object.keys(data.sources || {}).length || '6';
        document.getElementById('hero-users-count').textContent = data.total_users || '0';
    } catch { }
}

// -------------------------------------------------------------------------
// RENDERING — STATS
// -------------------------------------------------------------------------
function renderStats() {
    if (!state.stats) return;
    document.getElementById('stat-total-jobs').textContent = state.stats.total_jobs || 0;
    document.getElementById('stat-sources').textContent = Object.keys(state.stats.sources || {}).length;
    document.getElementById('stat-matches').textContent = state.matches.length;
    document.getElementById('stat-updated').textContent = state.stats.last_updated
        ? new Date(state.stats.last_updated).toLocaleDateString()
        : 'N/A';
}

// -------------------------------------------------------------------------
// RENDERING — PROFILE
// -------------------------------------------------------------------------
function renderProfile() {
    const panel = document.getElementById('profile-panel');
    const uploadZone = document.getElementById('upload-zone-container');

    if (!state.profile) {
        panel.classList.remove('active');
        if (uploadZone) uploadZone.style.display = 'block';
        return;
    }

    panel.classList.add('active');
    if (uploadZone) uploadZone.style.display = 'none';

    // Summary
    document.getElementById('profile-summary-text').textContent = state.profile.summary || 'Profile parsed from resume.';
    document.getElementById('profile-filename').textContent = state.profile.resume_filename || 'resume';

    // Skills
    renderChips('profile-skills', state.profile.skills || [], 'skill');
    // Education
    renderChips('profile-education', state.profile.education || [], 'education');
    // Locations
    renderChips('profile-locations', state.profile.locations || [], 'location');
    // Job Titles
    renderChips('profile-titles', state.profile.job_titles || [], 'title');
}

function renderChips(containerId, items, chipClass) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!items.length) {
        el.innerHTML = '<span class="text-muted" style="font-size:0.82rem;">None detected</span>';
        return;
    }
    el.innerHTML = items.map(item =>
        `<span class="chip ${chipClass}">${escapeHtml(item)}</span>`
    ).join('');
}

// -------------------------------------------------------------------------
// RENDERING — MATCHES
// -------------------------------------------------------------------------
function renderMatches() {
    const grid = document.getElementById('matches-grid');
    if (!grid) return;

    // Show loading skeleton
    if (state.loading.matches) {
        grid.innerHTML = Array(6).fill('<div class="skeleton skeleton-card"></div>').join('');
        return;
    }

    // No matches available
    if (!state.matches.length) {
        const hasProfile = state.profile !== null;
        if (hasProfile) {
            // User has uploaded a resume but no matches
            grid.innerHTML = `
                <div class="empty-state" style="grid-column:1/-1;">
                    <span class="empty-icon">📭</span>
                    <h3>No matching jobs found right now</h3>
                    <p>We couldn't find strong matches for your profile at the moment. 
                    Don't worry — we monitor <strong>6 job portals</strong> and check for new jobs every 6 hours.</p>
                    <p style="color:var(--color-primary-light);margin-top:8px;">
                        📧 We'll notify you by email when new jobs matching your skills appear!
                    </p>
                    <button class="btn btn-outline mt-2" onclick="handleRematch()">🔄 Try Matching Again</button>
                </div>`;
        } else {
            // User hasn't uploaded resume yet
            grid.innerHTML = `
                <div class="empty-state" style="grid-column:1/-1;">
                    <span class="empty-icon">📄</span>
                    <h3>Upload your resume to get started</h3>
                    <p>Once you upload your CV, our AI will analyze your skills and match you with the most relevant jobs from across Pakistan.</p>
                </div>`;
        }
        return;
    }

    // Check if all scores are very low (under 5%)
    const bestScore = Math.max(...state.matches.map(m => m.score));
    const meaningfulMatches = state.matches.filter(m => m.score >= 5);

    if (meaningfulMatches.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column:1/-1;">
                <span class="empty-icon">📭</span>
                <h3>No strong matches found</h3>
                <p>Your profile doesn't closely match the current job listings. This can happen when:
                </p>
                <ul style="text-align:left;max-width:420px;margin:8px auto;color:var(--text-secondary);font-size:0.9rem;line-height:1.8;">
                    <li>Your resume format wasn't parsed perfectly — try re-uploading</li>
                    <li>Current listings don't match your specific skills</li>
                    <li>New relevant jobs haven't been posted yet</li>
                </ul>
                <p style="color:var(--color-primary-light);margin-top:12px;">
                    📧 We'll send you an email notification when new matching jobs appear!
                </p>
                <div style="display:flex;gap:10px;justify-content:center;margin-top:16px;flex-wrap:wrap;">
                    <button class="btn btn-outline" onclick="handleUpdateResume()">📄 Re-upload Resume</button>
                    <button class="btn btn-accent" onclick="handleRematch()">🔄 Refresh Matches</button>
                </div>
            </div>`;
        return;
    }

    // Update stats
    const statEl = document.getElementById('stat-matches');
    if (statEl) statEl.textContent = meaningfulMatches.length;

    // Only show top 30 matches for performance, sorted by score
    const displayMatches = meaningfulMatches.slice(0, 30);
    grid.innerHTML = displayMatches.map(m => renderJobCard(m)).join('');

    // Animate score circles after DOM insertion
    requestAnimationFrame(() => {
        document.querySelectorAll('.score-fill').forEach(circle => {
            const offset = circle.dataset.offset;
            circle.style.strokeDashoffset = offset;
        });
    });
}

function getApplyLink(job) {
    // 1. Direct job link (best case)
    if (job.link && job.link.trim() && job.link !== 'nan' && job.link.startsWith('http')) {
        return job.link.trim();
    }
    // 2. Fallback: source portal homepage
    const sourceKey = (job.source || '').toLowerCase().replace(/[^a-z.]/g, '');
    for (const [key, url] of Object.entries(SOURCE_URLS)) {
        if (sourceKey.includes(key.replace('.', ''))) return url;
    }
    // 3. Final fallback
    return '';
}

function renderJobCard(match) {
    const job = match.job;
    const score = match.score;
    const scoreClass = score >= 70 ? 'score-high' : score >= 40 ? 'score-med' : 'score-low';
    const circumference = 2 * Math.PI * 24; // r=24
    const offset = circumference - (score / 100) * circumference;
    const sourceSlug = (job.source || '').toLowerCase().replace(/[^a-z]/g, '');
    const link = getApplyLink(job);
    const hasDirectLink = job.link && job.link.trim() && job.link !== 'nan' && job.link.startsWith('http');

    return `
    <div class="job-card">
        <div class="job-card-header">
            <div class="job-card-title">${escapeHtml(job.title || 'Untitled')}</div>
            <div class="score-circle ${scoreClass}">
                <svg viewBox="0 0 52 52">
                    <circle class="score-bg" cx="26" cy="26" r="24"/>
                    <circle class="score-fill" cx="26" cy="26" r="24"
                            style="stroke-dasharray:${circumference}"
                            data-offset="${offset}"/>
                </svg>
                <span class="score-label">${Math.round(score)}%</span>
            </div>
        </div>
        <div class="job-card-meta">
            <div class="job-meta-item">
                <span class="meta-icon">🏢</span>
                <span>${escapeHtml(job.company || 'N/A')}</span>
            </div>
            <div class="job-meta-item">
                <span class="meta-icon">📍</span>
                <span>${escapeHtml(job.location || 'Pakistan')}</span>
            </div>
            <div class="job-meta-item">
                <span class="meta-icon">🌐</span>
                <span class="source-badge ${sourceSlug}">${escapeHtml(job.source || 'Unknown')}</span>
            </div>
            ${job.deadline && job.deadline !== 'nan' ? `
            <div class="job-meta-item">
                <span class="meta-icon">⏰</span>
                <span>${escapeHtml(job.deadline)}</span>
            </div>` : ''}
        </div>
        <div class="job-card-actions">
            ${link
                ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener" class="btn btn-primary btn-sm">
                    ${hasDirectLink ? 'Apply Now →' : 'View on ' + escapeHtml(job.source || 'Portal') + ' →'}
                  </a>`
                : `<span class="btn btn-outline btn-sm" style="opacity:0.5;pointer-events:none;">No Link Available</span>`
            }
        </div>
    </div>`;
}

// -------------------------------------------------------------------------
// RENDERING — JOBS TABLE
// -------------------------------------------------------------------------
function renderJobsTable() {
    const tbody = document.getElementById('jobs-tbody');
    if (!tbody) return;

    if (!state.jobs.length) {
        tbody.innerHTML = `
            <tr><td colspan="6" class="text-center text-muted" style="padding:40px;">
                No jobs found matching your filters.
            </td></tr>`;
        return;
    }

    tbody.innerHTML = state.jobs.map((job) => {
        const link = getApplyLink(job);
        const hasDirectLink = job.link && job.link.trim() && job.link !== 'nan' && job.link.startsWith('http');
        const sourceSlug = (job.source || '').toLowerCase().replace(/[^a-z]/g, '');
        return `
        <tr>
            <td class="job-title-cell">${escapeHtml(job.title || 'Untitled')}</td>
            <td>${escapeHtml(job.company || 'N/A')}</td>
            <td>${escapeHtml(job.location || '-')}</td>
            <td><span class="source-badge ${sourceSlug}">${escapeHtml(job.source || '-')}</span></td>
            <td>${escapeHtml(job.date_scraped ? job.date_scraped.split(' ')[0] : '-')}</td>
            <td>
                ${link
                    ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener" class="apply-link">
                        ${hasDirectLink ? 'Apply →' : 'Visit Portal →'}
                      </a>`
                    : '<span class="text-muted">—</span>'}
            </td>
        </tr>`;
    }).join('');

    document.getElementById('jobs-count').textContent = `${state.jobs.length} jobs`;
}

function renderFilterOptions() {
    const sourceSelect = document.getElementById('filter-source');
    const locationSelect = document.getElementById('filter-location');

    if (sourceSelect && state.filtersData.sources) {
        const current = sourceSelect.value;
        sourceSelect.innerHTML = '<option value="">All Sources</option>'
            + state.filtersData.sources.map(s =>
                `<option value="${escapeHtml(s)}" ${s === current ? 'selected' : ''}>${escapeHtml(s)}</option>`
            ).join('');
    }

    if (locationSelect && state.filtersData.locations) {
        const current = locationSelect.value;
        const locations = [...new Set(state.filtersData.locations)].slice(0, 30);
        locationSelect.innerHTML = '<option value="">All Locations</option>'
            + locations.map(l =>
                `<option value="${escapeHtml(l)}" ${l === current ? 'selected' : ''}>${escapeHtml(l)}</option>`
            ).join('');
    }
}

// -------------------------------------------------------------------------
// TABS
// -------------------------------------------------------------------------
function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(panel => {
        panel.classList.toggle('active', panel.id === `tab-${tabName}`);
    });

    if (tabName === 'jobs' && !state.jobs.length) {
        loadJobs();
    } else if (tabName === 'admin' && state.user && state.user.is_admin) {
        loadAdminDashboard();
        loadAdminUsers();
        loadAdminJobs();
        if (typeof loadAdminCustomSources === 'function') loadAdminCustomSources();
    }
}

// -------------------------------------------------------------------------
// SETTINGS
// -------------------------------------------------------------------------
async function toggleNotifications(checkbox) {
    try {
        await api.updateSettings({ email_notifications: checkbox.checked });
        showToast(checkbox.checked ? 'Email notifications enabled.' : 'Email notifications disabled.', 'info');
    } catch (err) {
        checkbox.checked = !checkbox.checked;
        showToast(err.message, 'error');
    }
}

async function handleUpdateResume() {
    const updateInput = document.getElementById('resume-input-update');
    if (!updateInput) {
        // Fallback to main input
        const mainInput = document.getElementById('resume-input');
        if (mainInput) mainInput.click();
        return;
    }
    // Attach handler if not yet done
    if (!updateInput._handlerSet) {
        updateInput.addEventListener('change', () => {
            if (updateInput.files.length) {
                handleFileUpload(updateInput.files[0]);
                updateInput.value = '';
            }
        });
        updateInput._handlerSet = true;
    }
    updateInput.click();
}

async function handleDeleteProfile() {
    if (!confirm('Are you sure? This will delete your resume and all match data.')) return;
    try {
        await api.deleteProfile();
        state.profile = null;
        state.matches = [];
        renderProfile();
        renderMatches();
        showToast('Profile deleted.', 'info');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleRematch() {
    const btn = document.getElementById('rematch-btn');
    if (btn) btn.classList.add('loading');
    try {
        await api.triggerMatch();
        await loadMatches();
        if (state.matches.filter(m => m.score >= 5).length > 0) {
            showToast('🎯 Matching refreshed! Check your updated recommendations.', 'success');
        } else {
            showToast('Matching complete. No strong matches found yet — we\'ll notify you by email.', 'info', 5000);
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
    if (btn) btn.classList.remove('loading');
}

// -------------------------------------------------------------------------
// FILTER & SORT HANDLERS
// -------------------------------------------------------------------------
let searchDebounce = null;
function handleSearchInput(value) {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
        state.filters.search = value;
        loadJobs();
    }, 400);
}

function handleSourceFilter(value) {
    state.filters.source = value;
    loadJobs();
}

function handleLocationFilter(value) {
    state.filters.location = value;
    loadJobs();
}

function handleSortFilter(value) {
    state.filters.sort = value;
    loadJobs();
}

// -------------------------------------------------------------------------
// ADMIN CONTROLS
// -------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// ADMIN — DASHBOARD STATS
// ---------------------------------------------------------------------------
async function loadAdminDashboard() {
    try {
        const data = await api.adminGetDashboard();
        const el = (id) => document.getElementById(id);
        if (el('admin-stat-users')) el('admin-stat-users').textContent = data.total_users || 0;
        if (el('admin-stat-jobs')) el('admin-stat-jobs').textContent = data.active_jobs || 0;
        if (el('admin-stat-matches')) el('admin-stat-matches').textContent = data.total_matches || 0;
        if (el('admin-stat-email')) {
            el('admin-stat-email').textContent = data.mail_configured ? 'Active' : 'Off';
            const icon = el('admin-email-icon');
            if (icon) {
                icon.style.background = data.mail_configured
                    ? 'rgba(0,200,83,0.15)' : 'rgba(244,67,54,0.15)';
                icon.style.color = data.mail_configured ? '#00c853' : '#f44336';
            }
        }
    } catch { }
}

// ---------------------------------------------------------------------------
// ADMIN — USER MANAGEMENT (admin's own account excluded server-side)
// ---------------------------------------------------------------------------
async function loadAdminUsers() {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Loading users...</td></tr>';

    try {
        const data = await api.adminGetUsers();
        if (!data.users.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted" style="padding:30px;">No other users registered yet.</td></tr>';
            return;
        }

        tbody.innerHTML = data.users.map(u => `
            <tr>
                <td><strong>${escapeHtml(u.name)}</strong></td>
                <td>${escapeHtml(u.email)}</td>
                <td>${escapeHtml(u.auth_provider)}</td>
                <td>
                    <span class="chip ${u.is_active ? 'education' : 'skill'}" style="margin:0">
                        ${u.is_active ? 'Active' : 'Disabled'}
                    </span>
                </td>
                <td>
                    ${u.has_resume
                        ? `<span class="chip title" style="margin:0;cursor:pointer;" onclick="adminViewProfile(${u.id})" title="Click to view">📄 ${escapeHtml(u.resume_filename || 'Uploaded')}</span>`
                        : '<span class="text-muted">None</span>'
                    }
                </td>
                <td>${u.job_matches_count || 0}</td>
                <td style="white-space:nowrap;">
                    <button class="btn btn-outline btn-sm" onclick="adminToggleUser(${u.id})">
                        ${u.is_active ? '🚫 Disable' : '✅ Enable'}
                    </button>
                    <button class="btn btn-ghost btn-sm" style="color:var(--color-error)" onclick="adminDeleteUser(${u.id})">
                        🗑️ Delete
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-error text-center">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function adminViewProfile(userId) {
    try {
        const data = await api.adminGetUserProfile(userId);
        const p = data.profile;
        const skills = (p.skills || []).join(', ') || 'None';
        const locations = (p.locations || []).join(', ') || 'None';
        const education = (p.education || []).join(', ') || 'None';
        const titles = (p.job_titles || []).join(', ') || 'None';
        alert(
            `📄 Resume Profile — ${p.user_name}\n` +
            `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
            `📧 Email: ${p.user_email}\n` +
            `📝 File: ${p.resume_filename}\n` +
            `📊 Summary: ${p.summary}\n\n` +
            `🛠️ Skills: ${skills}\n` +
            `🎓 Education: ${education}\n` +
            `📍 Locations: ${locations}\n` +
            `💼 Job Titles: ${titles}\n` +
            `📅 Experience: ${p.experience_years || 0} years\n` +
            `🕐 Last Updated: ${p.updated_at || 'N/A'}`
        );
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ---------------------------------------------------------------------------
// ADMIN — JOB SOURCE MONITORING
// ---------------------------------------------------------------------------
async function loadAdminJobs() {
    const tbody = document.getElementById('admin-jobs-tbody');
    if (!tbody) return;

    try {
        const data = await api.adminGetJobs();
        if (!data.sources || !data.sources.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No job data available.</td></tr>';
            return;
        }

        let totalRow = { active: 0, closed: 0, total: 0 };
        tbody.innerHTML = data.sources.map(s => {
            totalRow.active += s.active;
            totalRow.closed += s.closed;
            totalRow.total += s.total;
            const sourceSlug = (s.source || '').toLowerCase().replace(/[^a-z]/g, '');
            return `
            <tr>
                <td><span class="source-badge ${sourceSlug}">${escapeHtml(s.source)}</span></td>
                <td style="color:#00c853;font-weight:600;">${s.active}</td>
                <td style="color:var(--text-secondary);">${s.closed}</td>
                <td><strong>${s.total}</strong></td>
            </tr>`;
        }).join('') + `
            <tr style="border-top:2px solid var(--border);font-weight:700;">
                <td>TOTAL</td>
                <td style="color:#00c853;">${totalRow.active}</td>
                <td>${totalRow.closed}</td>
                <td>${totalRow.total}</td>
            </tr>`;
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-error text-center">${escapeHtml(err.message)}</td></tr>`;
    }
}

// ---------------------------------------------------------------------------
// ADMIN — USER ACTIONS
// ---------------------------------------------------------------------------
async function adminToggleUser(id) {
    try {
        const res = await api.adminToggleUser(id);
        showToast(res.message, 'success');
        loadAdminUsers();
        loadAdminDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function adminDeleteUser(id) {
    if (!confirm('Are you sure you want to permanently delete this user? This cannot be undone.')) return;
    try {
        const res = await api.adminDeleteUser(id);
        showToast(res.message, 'success');
        loadAdminUsers();
        loadAdminDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ---------------------------------------------------------------------------
// ADMIN — SYSTEM TRIGGERS
// ---------------------------------------------------------------------------
async function adminTriggerSync() {
    showToast('Starting background sync...', 'info');
    try {
        const res = await api.adminTriggerSync();
        showToast(res.message, 'success', 6000);
        loadAdminDashboard();
        loadAdminJobs();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function adminTriggerMatches() {
    showToast('Starting global matching process...', 'info');
    try {
        const res = await api.adminTriggerMatches();
        showToast(res.message, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function adminTriggerNotifications() {
    showToast('Sweeping for pending notifications...', 'info');
    try {
        const res = await api.adminTriggerNotifications();
        showToast(res.message, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ---------------------------------------------------------------------------
// ADMIN — CUSTOM JOB SOURCES
// ---------------------------------------------------------------------------
async function loadAdminCustomSources() {
    const tbody = document.getElementById('admin-custom-sources-tbody');
    if (!tbody) return;
    try {
        const data = await api.adminGetCustomSources();
        if (!data.sources || !data.sources.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No custom sources added yet.</td></tr>';
            return;
        }
        tbody.innerHTML = data.sources.map(s => `
            <tr>
                <td><strong>${escapeHtml(s.name)}</strong></td>
                <td><a href="${escapeHtml(s.url)}" target="_blank" style="color:var(--color-primary-light);">${escapeHtml(s.url)}</a></td>
                <td>${new Date(s.created_at).toLocaleDateString()}</td>
                <td>
                    <button class="btn btn-ghost btn-sm" style="color:var(--color-error)" onclick="adminDeleteCustomSource(${s.id})">🗑️ Delete</button>
                </td>
            </tr>
        `).join('');
    } catch(err) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-error text-center">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function adminAddCustomSource() {
    const nameEl = document.getElementById('custom-source-name');
    const urlEl = document.getElementById('custom-source-url');
    if (!nameEl.value || !urlEl.value) return showToast('Please fill out both Name and URL.', 'error');
    
    try {
        await api.adminAddCustomSource(nameEl.value, urlEl.value);
        showToast('Custom source added successfully!', 'success');
        nameEl.value = ''; 
        urlEl.value = '';
        loadAdminCustomSources();
    } catch(err) {
        showToast(err.message, 'error');
    }
}

async function adminDeleteCustomSource(id) {
    if (!confirm('Are you sure you want to delete this custom source?')) return;
    try {
        await api.adminDeleteCustomSource(id);
        showToast('Custom source deleted.', 'info');
        loadAdminCustomSources();
    } catch(err) {
        showToast(err.message, 'error');
    }
}

// -------------------------------------------------------------------------
// UTILITIES
// -------------------------------------------------------------------------
function escapeHtml(str) {
    if (!str) return '';
    const s = String(str);
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return s.replace(/[&<>"']/g, c => map[c]);
}

// -------------------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadFeatureConfig();  // hide/show Google button and email notices
    setTheme(savedTheme); // apply active state to theme buttons

    // Modal close on backdrop click
    document.getElementById('auth-modal').addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) closeModal();
    });

    // Keyboard escape to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
});

// -------------------------------------------------------------------------
// FEATURE CONFIG — show/hide Google OAuth button, email notices
// -------------------------------------------------------------------------
async function loadFeatureConfig() {
    try {
        const config = await api.getConfig();

        // Google OAuth button
        const googleBtn = document.getElementById('google-auth-btn');
        const divider = googleBtn ? googleBtn.nextElementSibling : null;
        if (googleBtn) {
            // Instead of hiding the button, we keep it visible to show the feature exists.
            // If not configured, we intercept the click to provide helpful instructions.
            if (!config.google_oauth_enabled) {
                googleBtn.onclick = (e) => {
                    e.preventDefault();
                    showToast('⚠️ Google OAuth is not configured yet. Please add your GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the .env file.', 'info', 7000);
                };
            } else {
                googleBtn.style.display = '';
                if (divider && divider.classList.contains('divider')) {
                    divider.style.display = '';
                }
            }
        }
    } catch {
        // Config endpoint unavailable — fallback
        const googleBtn = document.getElementById('google-auth-btn');
        if (googleBtn) {
            googleBtn.onclick = (e) => {
                e.preventDefault();
                showToast('Unable to connect to configuration server.', 'error');
            };
        }
    }
}
