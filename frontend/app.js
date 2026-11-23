// Theme Management
const themeToggle = document.getElementById('theme-toggle');
const icon = themeToggle.querySelector('i');

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (theme === 'dark') {
        icon.classList.replace('fa-moon', 'fa-sun');
    } else {
        icon.classList.replace('fa-sun', 'fa-moon');
    }
}

// Initial theme
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
let currentTheme = prefersDark ? 'dark' : 'light';
setTheme(currentTheme);

themeToggle.addEventListener('click', () => {
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    setTheme(currentTheme);
});

// View Management
const views = {
    upload: document.getElementById('upload-view'),
    progress: document.getElementById('progress-view'),
    dashboard: document.getElementById('dashboard-view')
};

let loadingTimer = null;
let animationTimer = null;
let elapsedTime = 0;
const animations = [
    { className: 'anim-spinner', count: 0 },
    { className: 'anim-double-bounce', count: 0 },
    { className: 'anim-wave', count: 5 },
    { className: 'anim-chasing-dots', count: 0 },
    { className: 'anim-pulse-ring', count: 0 },
    { className: 'anim-folding-cube', count: 4 },
    { className: 'anim-ripple', count: 0 },
    { className: 'anim-hourglass', count: 0 },
    { className: 'anim-dual-ring', count: 0 },
    { className: 'anim-grid', count: 9 },
    { className: 'anim-heartbeat', count: 0 },
    { className: 'anim-orbit', count: 0 },
    { className: 'anim-pendulum', count: 2 },
    { className: 'anim-stretch', count: 3 },
    { className: 'anim-bouncing-balls', count: 3 },
    { className: 'anim-rot-sq', count: 0 },
    { className: 'anim-coin', count: 0 },
    { className: 'anim-radar', count: 0 },
    { className: 'anim-dna', count: 2 },
    { className: 'anim-typing', count: 2 },
    { className: 'anim-expanding', count: 3 }
];
let currentAnimationIndex = 0;

let cpuHistory = [];
let cpuPollInterval = null;

function initCpuChart() {
    cpuHistory = [];
    Plotly.newPlot('cpu-graph-container', [{
        y: cpuHistory,
        type: 'scatter',
        mode: 'lines',
        line: {color: '#10b981', shape: 'spline', width: 2},
        fill: 'tozeroy',
        fillcolor: 'rgba(16, 185, 129, 0.1)'
    }], {
        margin: {t: 0, r: 0, l: 0, b: 0},
        xaxis: {visible: false},
        yaxis: {range: [0, 100], visible: false},
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        staticPlot: true
    }, {responsive: true});
    
    if (cpuPollInterval) clearInterval(cpuPollInterval);
    cpuPollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/system_stats');
            const data = await res.json();
            cpuHistory.push(data.cpu_percent);
            if (cpuHistory.length > 50) cpuHistory.shift();
            Plotly.update('cpu-graph-container', {y: [cpuHistory]});
        } catch(e) {}
    }, 1000);
}

function stopCpuChart() {
    if (cpuPollInterval) clearInterval(cpuPollInterval);
}

function startLoadingUI() {
    elapsedTime = 0;
    const elapsedSpan = document.getElementById('progress-elapsed');
    if (elapsedSpan) elapsedSpan.textContent = `Прошло: 0 сек`;
    
    if (loadingTimer) clearInterval(loadingTimer);
    loadingTimer = setInterval(() => {
        elapsedTime++;
        if (elapsedSpan) elapsedSpan.textContent = `Прошло: ${elapsedTime} сек`;
    }, 1000);

    const spinnerContainer = document.getElementById('dynamic-spinner-container');
    if (animationTimer) clearInterval(animationTimer);
    animationTimer = setInterval(() => {
        if (!spinnerContainer) return;
        currentAnimationIndex = (currentAnimationIndex + 1) % animations.length;
        const anim = animations[currentAnimationIndex];
        let innerHTML = `<div class="${anim.className}">`;
        for(let i=0; i<anim.count; i++) {
            innerHTML += `<div></div>`;
        }
        innerHTML += `</div>`;
        spinnerContainer.innerHTML = innerHTML;
    }, 3000);
    
    initCpuChart();
    document.getElementById('live-facts-container').style.display = 'none';
}

function stopLoadingUI() {
    if (loadingTimer) clearInterval(loadingTimer);
    if (animationTimer) clearInterval(animationTimer);
    stopCpuChart();
}

function showView(viewName) {
    Object.values(views).forEach(v => v.classList.remove('active'));
    views[viewName].classList.add('active');
    
    if (viewName === 'progress') {
        startLoadingUI();
    } else {
        stopLoadingUI();
    }
}

// File Upload Handling
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const btnBrowse = document.getElementById('btn-browse');

btnBrowse.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

// HF Token Auth UI
const hfTokenInputMode = document.getElementById('hf-token-input-mode');
const hfTokenStatusMode = document.getElementById('hf-token-status-mode');
const hfTokenInput = document.getElementById('hf-token-input');
const hfToggleEye = document.getElementById('hf-token-toggle-eye');
const hfBtnSave = document.getElementById('hf-btn-save');
const hfBtnDelete = document.getElementById('hf-btn-delete');
const hfMaskedDisplay = document.getElementById('hf-token-masked-display');
const hfAuthMessage = document.getElementById('hf-auth-message');

function showHfMessage(msg, isError = false) {
    hfAuthMessage.textContent = msg;
    hfAuthMessage.style.color = isError ? 'var(--error)' : 'var(--primary)';
}

async function loadHfTokenStatus() {
    try {
        const res = await fetch('/api/hf-token/status');
        const data = await res.json();
        if (data.is_set) {
            hfTokenInputMode.style.display = 'none';
            hfTokenStatusMode.style.display = 'flex';
            hfMaskedDisplay.textContent = data.masked_token;
            hfAuthMessage.textContent = '';
        } else {
            hfTokenInputMode.style.display = 'flex';
            hfTokenStatusMode.style.display = 'none';
            hfTokenInput.value = '';
        }
    } catch (e) {
        console.error("Failed to load HF token status", e);
    }
}

hfToggleEye.addEventListener('click', () => {
    if (hfTokenInput.type === 'password') {
        hfTokenInput.type = 'text';
        hfToggleEye.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        hfTokenInput.type = 'password';
        hfToggleEye.classList.replace('fa-eye-slash', 'fa-eye');
    }
});

hfBtnSave.addEventListener('click', async () => {
    const token = hfTokenInput.value.trim();
    if (!token) {
        showHfMessage("Введите токен", true);
        return;
    }
    
    hfBtnSave.disabled = true;
    showHfMessage("Проверка токена...");
    
    try {
        // Validate
        let res = await fetch('/api/hf-token/validate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token})
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Невалидный токен");
        }
        
        const valData = await res.json();
        const successMsg = valData.message;
        
        // Save
        res = await fetch('/api/hf-token', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token})
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Ошибка сохранения");
        }
        
        showHfMessage(successMsg);
        await loadHfTokenStatus();
        
    } catch (e) {
        showHfMessage(e.message, true);
    } finally {
        hfBtnSave.disabled = false;
    }
});

hfBtnDelete.addEventListener('click', async () => {
    try {
        hfBtnDelete.disabled = true;
        const res = await fetch('/api/hf-token', { method: 'DELETE' });
        if (!res.ok) throw new Error("Ошибка удаления");
        await loadHfTokenStatus();
        showHfMessage("Токен удалён");
    } catch (e) {
        showHfMessage(e.message, true);
    } finally {
        hfBtnDelete.disabled = false;
    }
});

// Load on start
loadHfTokenStatus();

// Advanced Settings UI
const settingsToggle = document.getElementById('advanced-settings-toggle');
const settingsPanel = document.getElementById('advanced-settings-panel');
const llmModeRadios = document.querySelectorAll('input[name="llm_mode"]');
const llmModelContainer = document.getElementById('llm-model-container');
const advancedLlmModelContainer = document.getElementById('advanced-llm-model-container');
const fetchOllamaBtn = document.getElementById('fetch-ollama-btn');
const llmModelSelect = document.getElementById('llm-model-select');
const advancedLlmModelSelect = document.getElementById('advanced-llm-model-select');

// Load saved settings
const savedMode = localStorage.getItem('llm_mode') || 'none';

function updateLlmUI(mode) {
    llmModelContainer.style.display = mode === 'light' ? 'flex' : 'none';
    advancedLlmModelContainer.style.display = mode === 'advanced' ? 'flex' : 'none';
}

llmModeRadios.forEach(r => {
    if (r.value === savedMode) r.checked = true;
    r.addEventListener('change', (e) => {
        if (e.target.checked) {
            localStorage.setItem('llm_mode', e.target.value);
            updateLlmUI(e.target.value);
            if (e.target.value !== 'none') fetchOllamaModels();
        }
    });
});
updateLlmUI(savedMode);

settingsToggle.addEventListener('click', () => {
    settingsPanel.style.display = settingsPanel.style.display === 'none' ? 'block' : 'none';
});

async function fetchOllamaModels() {
    try {
        const res = await fetch('http://localhost:11434/api/tags');
        if (!res.ok) throw new Error("Ollama is not running");
        const data = await res.json();
        const models = data.models || [];
        if (models.length > 0) {
            // Light models
            llmModelSelect.innerHTML = models.map(m => `<option value="${m.name}">${m.name}</option>`).join('');
            const savedLight = localStorage.getItem('llm_model');
            if (savedLight && models.some(m => m.name === savedLight)) {
                llmModelSelect.value = savedLight;
            }
            
            // Advanced models
            advancedLlmModelSelect.innerHTML = models.map(m => `<option value="${m.name}">${m.name}${m.name.startsWith('gemma4:31b') ? ' (рекомендуется)' : ''}</option>`).join('');
            const savedAdv = localStorage.getItem('advanced_llm_model');
            if (savedAdv && models.some(m => m.name === savedAdv)) {
                advancedLlmModelSelect.value = savedAdv;
            } else if (models.some(m => m.name.startsWith('gemma4:31b'))) {
                advancedLlmModelSelect.value = models.find(m => m.name.startsWith('gemma4:31b')).name;
            }
        }
    } catch (err) {
        console.warn("Could not fetch Ollama models:", err);
    }
}

fetchOllamaBtn.addEventListener('click', fetchOllamaModels);
llmModelSelect.addEventListener('change', (e) => {
    localStorage.setItem('llm_model', e.target.value);
});
advancedLlmModelSelect.addEventListener('change', (e) => {
    localStorage.setItem('advanced_llm_model', e.target.value);
});

// If initially checked, try fetching
if (savedMode !== 'none') fetchOllamaModels();

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFile(e.target.files[0]);
    }
});

let currentFileForUpload = null;
let currentTaskId = null;

async function handleFile(file, forceAction = null) {
    if (!file.name.endsWith('.json') && !file.name.endsWith('.txt') && !file.name.endsWith('.zip') && !file.name.endsWith('.enc')) {
        alert("Пожалуйста, загрузите файл с расширением .json, .txt, .zip или .enc");
        return;
    }
    currentFileForUpload = file;

    showView('progress');
    const formData = new FormData();
    formData.append('file', file);
    
    const modeEl = document.querySelector('input[name="llm_mode"]:checked');
    const llm_mode = modeEl ? modeEl.value : 'none';
    
    formData.append('llm_mode', llm_mode);
    formData.append('llm_model', llmModelSelect.value || 'qwen3:4b');
    formData.append('advanced_llm_model', advancedLlmModelSelect.value || 'gemma4:31b');
    const topicCountSelect = document.getElementById('topic-count-select');
    const embeddingQualitySelect = document.getElementById('embedding-quality-select');
    if (topicCountSelect) formData.append('topic_count', topicCountSelect.value);
    if (embeddingQualitySelect) formData.append('embedding_quality', embeddingQualitySelect.value);
    if (forceAction) {
        formData.append('force_action', forceAction);
    }

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            throw new Error((await res.json()).error || "Ошибка загрузки");
        }
        
        const data = await res.json();
        
        if (data.status === "needs_decision") {
            // Show modal
            document.getElementById('checkpoint-modal').style.display = 'block';
            let dateStr = new Date(data.last_updated).toLocaleString();
            document.getElementById('checkpoint-date-text').innerText = "Дата последнего анализа: " + dateStr;
            document.getElementById('checkpoint-hash-text').innerText = "Хэш файла: " + data.file_hash.substring(0, 8);
            window.currentFileHash = data.file_hash;
            return;
        }
        
        document.getElementById('checkpoint-modal').style.display = 'none';
        
        const sf = document.getElementById('source-format');
        if (data.source) {
            sf.style.display = 'block';
            sf.innerText = `Обнаружен формат: ${data.source === 'whatsapp' ? 'WhatsApp' : 'Telegram'}`;
        } else {
            sf.style.display = 'none';
        }
        currentTaskId = data.task_id;
        connectWebSocket(data.task_id);
    } catch (err) {
        showError("Ошибка отправки файла", err.message);
    }
}

// Modal event listeners
document.getElementById('btn-load-checkpoint').addEventListener('click', () => {
    document.getElementById('checkpoint-modal').style.display = 'none';
    if (currentFileForUpload) {
        handleFile(currentFileForUpload, "load");
    }
});

document.getElementById('btn-recalc-checkpoint').addEventListener('click', () => {
    document.getElementById('checkpoint-modal').style.display = 'none';
    if (currentFileForUpload) {
        handleFile(currentFileForUpload, "recalculate");
    }
});

document.getElementById('delete-checkpoint-btn').addEventListener('click', async () => {
    if (!window.currentFileHash) return;
    if (confirm("Вы уверены, что хотите удалить сохранённые данные анализа?")) {
        try {
            await fetch(`/api/checkpoints/${window.currentFileHash}`, { method: 'DELETE' });
            alert("Данные успешно удалены.");
            location.reload();
        } catch (err) {
            alert("Ошибка удаления");
        }
    }
});

function showError(title, message) {
    stopLoadingUI();
    const spinnerObj = document.getElementById('dynamic-spinner-container');
    if (spinnerObj) spinnerObj.style.display = 'none';
    document.getElementById('progress-stage').style.display = 'none';
    document.querySelector('.progress-bar-wrapper').style.display = 'none';
    document.querySelector('.progress-stats').style.display = 'none';
    
    const errContainer = document.getElementById('error-container');
    errContainer.style.display = 'block';
    document.getElementById('error-title').textContent = title;
    document.getElementById('error-message').textContent = message;
}

// WebSocket and Progress Tracking
function connectWebSocket(taskId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/status/${taskId}`;
    const ws = new WebSocket(wsUrl);

    const fill = document.getElementById('progress-fill');
    const stage = document.getElementById('progress-stage');
    const pct = document.getElementById('progress-percent');
    const eta = document.getElementById('progress-eta');

    ws.onmessage = (event) => {
        const status = JSON.parse(event.data);
        
        if (status.stage === "error") {
            showError("Ошибка обработки", status.error);
            ws.close();
            return;
        }

        stage.textContent = status.stage;
        fill.style.width = `${status.progress}%`;
        pct.textContent = `${Number(status.progress).toFixed(2)}%`;
        
        if (status.facts) {
            document.getElementById('live-facts-container').style.display = 'block';
            document.getElementById('fact-total-messages').textContent = status.facts.total_messages;
            document.getElementById('fact-most-active').textContent = status.facts.most_active;
            document.getElementById('fact-most-quiet').textContent = status.facts.most_quiet;
        }
        
        if (status.eta_seconds > 0) {
            eta.textContent = `Осталось: ~${status.eta_seconds} сек`;
        } else {
            eta.textContent = "";
        }

        if (status.is_done) {
            ws.close();
            fetchResults(taskId);
        }
    };

    ws.onerror = () => {
        // Fallback to polling if WS fails
        pollStatus(taskId);
    };
}

async function pollStatus(taskId) {
    const fill = document.getElementById('progress-fill');
    const stage = document.getElementById('progress-stage');
    const pct = document.getElementById('progress-percent');
    const eta = document.getElementById('progress-eta');

    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status/${taskId}`);
            const status = await res.json();
            
            if (status.stage === "error") {
                clearInterval(interval);
                showError("Ошибка обработки", status.error);
                return;
            }

            stage.textContent = status.stage;
            fill.style.width = `${status.progress}%`;
            pct.textContent = `${Number(status.progress).toFixed(2)}%`;
            eta.textContent = status.eta_seconds > 0 ? `Осталось: ~${status.eta_seconds} сек` : "";

            if (status.facts) {
                document.getElementById('live-facts-container').style.display = 'block';
                document.getElementById('fact-total-messages').textContent = status.facts.total_messages;
                document.getElementById('fact-most-active').textContent = status.facts.most_active;
                document.getElementById('fact-most-quiet').textContent = status.facts.most_quiet;
            }

            if (status.is_done) {
                clearInterval(interval);
                fetchResults(taskId);
            }
        } catch (e) {
            console.error(e);
        }
    }, 1000);
}

// Fetch and Render Results
async function fetchResults(taskId) {
    try {
        const res = await fetch(`/api/result/${taskId}`);
        if (!res.ok) throw new Error("Не удалось получить результаты");
        
        if (res.status === 202) {
            setTimeout(() => fetchResults(taskId), 1000);
            return;
        }
        
        const data = await res.json();
        renderDashboard(data);
        showView('dashboard');
    } catch (err) {
        showError("Ошибка", err.message);
    }
}

// Chart layout template respecting theme
function getLayoutTemplate(title) {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#f8fafc' : '#1f2937';
    const bgColor = isDark ? '#1e293b' : '#ffffff';
    const gridColor = isDark ? '#334155' : '#e5e7eb';

    return {
        title: { text: title, font: { color: textColor, family: 'Inter' } },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: textColor, family: 'Inter' },
        xaxis: { gridcolor: gridColor, zerolinecolor: gridColor },
        yaxis: { gridcolor: gridColor, zerolinecolor: gridColor },
        margin: { t: 50, l: 50, r: 20, b: 50 },
        autosize: true
    };
}

function renderDashboard(data) {
    const s = data.structural;
    const sem = data.semantic;
    
    // 1. Summary Cards
    const cards = document.getElementById('summary-cards');
    // Format response time
    let respTimeHtml = "0 сек";
    if (s.response_time) {
        const sec = s.response_time.median_seconds;
        if (sec < 60) {
            respTimeHtml = `${Math.round(sec)} сек`;
        } else if (sec < 3600) {
            respTimeHtml = `${Math.round(sec / 60)} мин`;
        } else {
            respTimeHtml = `${Math.floor(sec / 3600)} ч ${Math.round((sec % 3600)/60)} мин`;
        }
    }

    cards.innerHTML = `
        <div class="card">
            <div class="card-title">Сообщений</div>
            <div class="card-value">${data.total_messages.toLocaleString('ru-RU')}</div>
        </div>
        <div class="card">
            <div class="card-title">Участников</div>
            <div class="card-value">${data.participants.length}</div>
        </div>
        <div class="card">
            <div class="card-title">Средний ответ</div>
            <div class="card-value">${respTimeHtml}</div>
        </div>
        <div class="card">
            <div class="card-title">Макс. стрик</div>
            <div class="card-value">${s.longest_streak || 0} дн.</div>
        </div>
    `;

    // AI Summary
    const aiSummarySec = document.getElementById('ai-summary-section');
    const aiSummaryContent = document.getElementById('ai-summary-content');
    if (aiSummarySec && aiSummaryContent) {
        if (sem.ai_summary) {
            aiSummaryContent.innerHTML = `<p>${sem.ai_summary.replace(/\n/g, '<br>')}</p>`;
            aiSummarySec.style.display = 'block';
        } else {
            aiSummarySec.style.display = 'none';
        }
    }

    // 2. Message Shares (Pie)
    if (s.message_shares) {
        let palette = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];
        if (data.participants.length > 5) {
            palette = ['#8dd3c7','#ffffb3','#bebada','#fb8072','#80b1d3','#fdb462','#b3de69','#fccde5','#d9d9d9','#bc80bd','#ccebc5','#ffed6f'];
        }

        const layout = getLayoutTemplate('Доля сообщений (%)');
        
        Plotly.newPlot('chart-message-shares', [{
            values: Object.values(s.message_shares),
            labels: Object.keys(s.message_shares),
            type: 'pie',
            hole: 0.4,
            marker: { colors: palette },
            textinfo: 'label+percent',
            hoverinfo: 'label+value',
            hovertemplate: data.source === 'whatsapp' ? '%{label}<br>Сообщений: %{value}<br>(исключая отредактированные)<extra></extra>' : '%{label}<br>Сообщений: %{value}<extra></extra>'
        }], layout, {responsive: true});
    }

    // 3. Monthly Dynamics
    if (s.dynamics_monthly) {
        const traces = [];
        const months = Object.keys(s.dynamics_monthly).sort();
        
        data.participants.forEach(p => {
            const y = months.map(m => s.dynamics_monthly[m][p] || 0);
            traces.push({
                x: months, y: y, name: p, type: 'scatter', mode: 'lines+markers', line: {shape: 'spline'}
            });
        });

        Plotly.newPlot('chart-monthly-dynamics', traces, getLayoutTemplate('Динамика по месяцам'), {responsive: true});
    }

    // 4. Heatmap Activity
    if (s.heatmap_activity) {
        const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
        const hours = Array.from({length: 24}, (_, i) => `${i}:00`);
        
        Plotly.newPlot('chart-heatmap', [{
            z: s.heatmap_activity,
            x: hours,
            y: days,
            type: 'heatmap',
            colorscale: 'Blues'
        }], getLayoutTemplate('Тепловая карта активности'), {responsive: true});
    }

    // 5. Sentiment Timeline & Breaking Points
    if (sem.sentiment_timeline) {
        const weeks = Object.keys(sem.sentiment_timeline).sort();
        const y = weeks.map(w => sem.sentiment_timeline[w]);
        
        const layout = getLayoutTemplate('Тональность (Sentiment) по неделям');
        layout.shapes = [];
        if (sem.breaking_points_confirmed && sem.breaking_points_confirmed.length > 0) {
            sem.breaking_points_confirmed.forEach(date => {
                layout.shapes.push({ type: 'line', x0: date, x1: date, y0: 0, y1: 1, yref: 'paper', line: { color: 'rgba(16, 185, 129, 0.8)', width: 2, dash: 'solid' }});
            });
        }
        if (sem.breaking_points_rejected && sem.breaking_points_rejected.length > 0) {
            sem.breaking_points_rejected.forEach(date => {
                layout.shapes.push({ type: 'line', x0: date, x1: date, y0: 0, y1: 1, yref: 'paper', line: { color: 'rgba(239, 68, 68, 0.4)', width: 2, dash: 'dot' }});
            });
        }
        if (!sem.breaking_points_confirmed && sem.breaking_points && sem.breaking_points.length > 0) {
            sem.breaking_points.forEach(date => {
                layout.shapes.push({ type: 'line', x0: date, x1: date, y0: 0, y1: 1, yref: 'paper', line: { color: 'rgba(239, 68, 68, 0.5)', width: 2, dash: 'dashdot' }});
            });
        }
        
        Plotly.newPlot('chart-sentiment-timeline', [{
            x: weeks, y: y, type: 'scatter', mode: 'lines+markers', line: {color: '#10b981', shape: 'spline'}, fill: 'tozeroy', hovertemplate: '%{x}<br>Тональность: %{y:.2f}<extra></extra>'
        }], layout, {responsive: true});
    }
    
    // Emotional Portrait (Radar)
    if (sem.emotional_portrait) {
        const traces = [];
        const emotions = ['Радость', 'Грусть', 'Злость', 'Страх', 'Удивление'];
        const keys = ['emo_joy', 'emo_sadness', 'emo_anger', 'emo_fear', 'emo_surprise'];
        
        data.participants.forEach(p => {
            if (sem.emotional_portrait[p]) {
                const r = keys.map(k => sem.emotional_portrait[p][k]);
                // Close the loop
                r.push(r[0]);
                const theta = [...emotions, emotions[0]];
                
                traces.push({
                    type: 'scatterpolar',
                    r: r,
                    theta: theta,
                    fill: 'toself',
                    name: p
                });
            }
        });
        
        const layout = getLayoutTemplate('Эмоциональный портрет (CEDR)');
        layout.polar = { radialaxis: { visible: true, range: [0, 1] } };
        Plotly.newPlot('chart-emotional-portrait', traces, layout, {responsive: true});
    }
    
    // Emotional Arcs
    if (sem.emotional_arcs) {
        const periods = Object.keys(sem.emotional_arcs).sort();
        const emotions = periods.map(p => sem.emotional_arcs[p]);
        
        const colorMap = {
            'joy': '#f59e0b', 'sadness': '#3b82f6', 'anger': '#ef4444', 
            'fear': '#8b5cf6', 'surprise': '#10b981', 'no_emotion': '#9ca3af'
        };
        const textMap = {
            'joy': 'Радость', 'sadness': 'Грусть', 'anger': 'Злость', 
            'fear': 'Страх', 'surprise': 'Удивление', 'no_emotion': 'Нейтрально'
        };
        
        const colors = emotions.map(e => colorMap[e] || '#9ca3af');
        let texts = emotions.map(e => textMap[e] || e);
        
        if (sem.emotional_arcs_narrative) {
            texts = periods.map(p => {
                const arc = sem.emotional_arcs_narrative[p];
                if (arc && arc.title && arc.title !== arc.emotion) {
                    return `${arc.title} (${textMap[arc.emotion] || arc.emotion})`;
                }
                return textMap[arc.emotion] || arc.emotion;
            });
        }
        
        Plotly.newPlot('chart-emotional-arcs', [{
            x: periods,
            y: Array(periods.length).fill(1),
            type: 'bar',
            marker: { color: colors },
            text: texts,
            hoverinfo: 'x+text',
            textposition: 'inside'
        }], Object.assign(getLayoutTemplate('Эмоциональные "Арки" (доминирующая эмоция)'), {
            barmode: 'stack', yaxis: {visible: false, showgrid: false}, margin: {t: 30, b: 30, l: 10, r: 10}
        }), {responsive: true});
    }
    
    // Brightest Moments
    const momentsGrid = document.getElementById('bright-moments-grid');
    if (momentsGrid) {
        let html = '';
        if (sem.kindest_message) {
            html += `
            <div class="card" style="grid-column: span 1;">
                <div class="card-title"><i class="fas fa-sun" style="color:#f59e0b"></i> Самое доброе сообщение</div>
                <div style="font-style: italic; margin: 1rem 0;">"${sem.kindest_message.text}"</div>
                <div style="font-size: 0.85rem; color: var(--text-muted);">— ${sem.kindest_message.author}, ${sem.kindest_message.date.split(' ')[0]}</div>
            </div>`;
        }
        
        if (sem.warmest_dialogue) {
            html += `
            <div class="card" style="grid-column: span 1;">
                <div class="card-title"><i class="fas fa-fire" style="color:#f97316"></i> Самый тёплый диалог</div>
                <div style="display:flex; flex-direction:column; gap:0.5rem; margin-top:1rem; font-size:0.9rem;">
                    ${sem.warmest_dialogue.map(m => `
                        <div style="padding:0.5rem; border-radius:8px; background:var(--bg); border:1px solid var(--border);">
                            <div style="font-weight:bold; font-size:0.8rem; color:var(--text-muted);">${m.author_name}</div>
                            <div>${m.text}</div>
                        </div>
                    `).join('')}
                </div>
            </div>`;
        }
        
        if (sem.tensest_dialogue) {
            html += `
            <div class="card" style="grid-column: span 1;">
                <div class="card-title"><i class="fas fa-bolt" style="color:#ef4444"></i> Самый напряжённый диалог</div>
                <div style="display:flex; flex-direction:column; gap:0.5rem; margin-top:1rem; font-size:0.9rem;">
                    ${sem.tensest_dialogue.map(m => `
                        <div style="padding:0.5rem; border-radius:8px; background:var(--bg); border:1px solid var(--border);">
                            <div style="font-weight:bold; font-size:0.8rem; color:var(--text-muted);">${m.author_name}</div>
                            <div>${m.text}</div>
                        </div>
                    `).join('')}
                </div>
            </div>`;
        }
        momentsGrid.innerHTML = html;
    }
    
    // Search Setup
    const searchBtn = document.getElementById('semantic-search-btn');
    const searchInput = document.getElementById('semantic-search-input');
    const searchRes = document.getElementById('semantic-search-results');
    const searchList = document.getElementById('search-results-list');
    const searchSpinner = document.getElementById('search-spinner');
    
    if (searchBtn && currentTaskId) {
        searchBtn.onclick = async () => {
            const query = searchInput.value.trim();
            if (!query) return;
            
            searchRes.style.display = 'block';
            searchList.innerHTML = '';
            searchSpinner.style.display = 'block';
            
            try {
                const res = await fetch(`/api/search/${currentTaskId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query})
                });
                
                if (!res.ok) throw new Error("Search failed");
                const data = await res.json();
                
                searchSpinner.style.display = 'none';
                if (data.results && data.results.length > 0) {
                    searchList.innerHTML = data.results.map(r => `
                        <div style="padding: 0.8rem; border-radius: 8px; border: 1px solid var(--border); background: var(--bg);">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                                <strong>${r.author_name}</strong>
                                <span style="color: var(--text-muted); font-size: 0.8rem;">${r.datetime} (схожесть: ${(r.sim*100).toFixed(1)}%)</span>
                            </div>
                            <div>${r.text}</div>
                        </div>
                    `).join('');
                } else {
                    searchList.innerHTML = '<div>Ничего не найдено</div>';
                }
            } catch (err) {
                searchSpinner.style.display = 'none';
                searchList.innerHTML = `<div style="color:red">Ошибка поиска: ${err.message}</div>`;
            }
        };
    }

    // 6. Top Words (Bar)
    if (sem.top_words_overall) {
        const words = Object.keys(sem.top_words_overall).slice(0, 15).reverse();
        const counts = Object.values(sem.top_words_overall).slice(0, 15).reverse();
        
        Plotly.newPlot('chart-top-words', [{
            type: 'bar',
            x: counts,
            y: words,
            orientation: 'h',
            marker: {color: '#8b5cf6'}
        }], getLayoutTemplate('Топ популярных слов'), {responsive: true});
    }

    // 7. Emoji Categories & Top Emojis
    if (sem.top_emojis_overall) {
        const emojis = Object.keys(sem.top_emojis_overall).reverse();
        const counts = Object.values(sem.top_emojis_overall).reverse();
        Plotly.newPlot('chart-top-emojis-overall', [{
            type: 'bar', x: counts, y: emojis, orientation: 'h', marker: {color: '#f59e0b'}
        }], getLayoutTemplate('Топ Эмодзи (Общий)'), {responsive: true});
    }

    if (sem.top_emojis_author) {
        const traces = [];
        for (let [author, emj] of Object.entries(sem.top_emojis_author)) {
            const emojis = Object.keys(emj).reverse();
            const counts = Object.values(emj).reverse();
            traces.push({
                type: 'bar', x: counts, y: emojis, orientation: 'h', name: author
            });
        }
        const layout = getLayoutTemplate('Топ Эмодзи по авторам');
        layout.barmode = 'group';
        Plotly.newPlot('chart-top-emojis-authors', traces, layout, {responsive: true});
    }

    if (sem.exclusive_emojis) {
        const el = document.getElementById('stats-exclusive-emojis');
        let html = "<div style='font-size: 0.9rem;'><strong>Уникальные эмодзи:</strong><br>";
        for (let [author, emjs] of Object.entries(sem.exclusive_emojis)) {
            if (emjs && emjs.length > 0) {
                html += `<div style="margin-top:0.3rem;"><span style="color:var(--primary); font-weight:600;">${author}:</span> ${emjs.slice(0, 15).join(' ')}${emjs.length>15 ? '...' : ''}</div>`;
            }
        }
        html += "</div>";
        if (el) el.innerHTML = html;
    }

    if (sem.emoji_categories) {
        const traces = [];
        const categories = ['love', 'laugh', 'sad', 'surprise', 'anger'];
        const catNames = {'love': 'Любовь', 'laugh': 'Смех', 'sad': 'Грусть', 'surprise': 'Удивление', 'anger': 'Злость'};
        
        data.participants.forEach(p => {
            if(sem.emoji_categories[p]) {
                const y = categories.map(c => sem.emoji_categories[p][c] || 0);
                traces.push({
                    x: categories.map(c => catNames[c]),
                    y: y,
                    name: p,
                    type: 'bar'
                });
            }
        });
        
        const layout = getLayoutTemplate('Категории эмодзи');
        layout.barmode = 'group';
        Plotly.newPlot('chart-emoji-categories', traces, layout, {responsive: true});
    }

    // 8. Stats Boss
    const statsBoss = document.getElementById('stats-boss');
    
    let avgLens = "";
    data.participants.forEach(p => {
        const len = s.avg_char_length ? Math.round(s.avg_char_length[p] || 0) : 0;
        avgLens += `<div class="stat-item"><span class="stat-label">Ср. длина (${p}):</span><span class="stat-val">${len} симв.</span></div>`;
    });
    
    let bossHtml = avgLens;
    
    if (s.longest_monologue) {
        bossHtml += `<div class="stat-item"><span class="stat-label">Самый длинный монолог:</span> 
            <span class="stat-value">${s.longest_monologue.author} (${s.longest_monologue.count} сообщ. подряд)</span></div>`;
    }
    if (s.longest_message) {
        bossHtml += `<div class="stat-item"><span class="stat-label">Самое длинное сообщение:</span> 
            <span class="stat-value">${s.longest_message.author} (${s.longest_message.chars} симв.)</span></div>`;
    }
    if (s.initiations_percentage && Object.keys(s.initiations_percentage).length > 0) {
        const initiator = Object.keys(s.initiations_percentage)[0];
        bossHtml += `<div class="stat-item"><span class="stat-label">Чаще начинает диалог:</span> 
            <span class="stat-value">${initiator} (${Math.round(s.initiations_percentage[initiator])}%)</span></div>`;
    }
    if (s.closers_percentage && Object.keys(s.closers_percentage).length > 0) {
        const closer = Object.keys(s.closers_percentage)[0];
        bossHtml += `<div class="stat-item"><span class="stat-label">Чаще "закрывает" диалог:</span> 
            <span class="stat-value">${closer} (${Math.round(s.closers_percentage[closer])}%)</span></div>`;
    }
    if (sem.question_ratio && Object.keys(sem.question_ratio).length > 0) {
        const qAuth = Object.keys(sem.question_ratio).reduce((a, b) => sem.question_ratio[a] > sem.question_ratio[b] ? a : b);
        bossHtml += `<div class="stat-item"><span class="stat-label">Больше всех спрашивает:</span> 
            <span class="stat-value">${qAuth} (${Math.round(sem.question_ratio[qAuth])}% реплик - вопросы)</span></div>`;
    }
    if (sem.care_detected && Object.keys(sem.care_detected).length > 0) {
        const cAuth = Object.keys(sem.care_detected).reduce((a, b) => sem.care_detected[a] > sem.care_detected[b] ? a : b);
        bossHtml += `<div class="stat-item"><span class="stat-label">Чаще проявляет заботу:</span> 
            <span class="stat-value">${cAuth} (${sem.care_detected[cAuth]} раз)</span></div>`;
    }
    if (s.season_distribution && Object.keys(s.season_distribution).length > 0) {
        const topSeason = Object.keys(s.season_distribution)[0];
        bossHtml += `<div class="stat-item"><span class="stat-label">Самое активное время года:</span> 
            <span class="stat-value">${topSeason}</span></div>`;
    }
    if (s.favorite_day && s.quietest_day) {
        bossHtml += `<div class="stat-item"><span class="stat-label">Любимый день:</span> 
            <span class="stat-value">${s.favorite_day} (тихий: ${s.quietest_day})</span></div>`;
    }
    if (s.night_owl_index && Object.keys(s.night_owl_index).length > 0) {
        const nightOwl = Object.keys(s.night_owl_index).reduce((a, b) => s.night_owl_index[a] > s.night_owl_index[b] ? a : b);
        bossHtml += `<div class="stat-item"><span class="stat-label">Ночная сова:</span> 
            <span class="stat-value">${nightOwl} (${Math.round(s.night_owl_index[nightOwl])}% ночью)</span></div>`;
    }
    
    statsBoss.innerHTML = bossHtml;

    // 9. Stats Language
    const statsLang = document.getElementById('stats-language');
    let lexDiv = "";
    if (sem.lexical_diversity) {
        data.participants.forEach(p => {
            const val = ((sem.lexical_diversity[p] || 0) * 100).toFixed(1);
            lexDiv += `<div class="stat-item"><span class="stat-label">Словарное богатство (${p}):</span><span class="stat-val">${val}% уникальных</span></div>`;
        });
    }
    
    let slHtml = `
        ${lexDiv}
        <div class="stat-item"><span class="stat-label">${data.source === 'whatsapp' ? 'Удалённых сообщений (явные метки):' : 'Разрывов в ID (могут быть удалённые сообщения):'}</span><span class="stat-val">${data.source === 'whatsapp' ? '' : 'до '}${s.deleted_messages_estimate || 0}</span></div>
        <div class="stat-item"><span class="stat-label">Отредактировано ${data.source === 'whatsapp' ? '<span title="WhatsApp не сохраняет историю правок в экспорте" style="cursor:help;">(❓)</span>' : ''}:</span><span class="stat-val">${data.source === 'whatsapp' ? '0' : (s.edited_messages ? Object.values(s.edited_messages).reduce((a,b)=>a+b, 0) : 0)}</span></div>
    `;
    
    if (sem.slang_percentage) {
        slHtml += '<div style="margin-top:1rem;"><strong>Использование сленга:</strong><br>';
        for (let [k,v] of Object.entries(sem.slang_percentage)) {
            slHtml += `<div>${k}: ${v.toFixed(1)}% слов</div>`;
        }
        slHtml += '</div>';
    }
    
    if (sem.caps_percentage) {
        slHtml += '<div style="margin-top:0.5rem;"><strong>КАПСЛОК:</strong><br>';
        for (let [k,v] of Object.entries(sem.caps_percentage)) {
            slHtml += `<div>${k}: ${v.toFixed(1)}% сообщений</div>`;
        }
        slHtml += '</div>';
    }
    
    if (sem.apologies_count || sem.compliments_count) {
        slHtml += '<div style="margin-top:0.5rem;"><strong>Вежливость:</strong><br>';
        data.participants.forEach(p => {
            const ap = (sem.apologies_count && sem.apologies_count[p]) || 0;
            const co = (sem.compliments_count && sem.compliments_count[p]) || 0;
            slHtml += `<div>${p}: ${ap} извинений, ${co} комплиментов</div>`;
        });
        slHtml += '</div>';
    }
    
    if (sem.top_mentions) {
        slHtml += '<div style="margin-top:0.5rem;"><strong>Кого упоминаете чаще всего (NER):</strong><br>';
        for (let [k,v] of Object.entries(sem.top_mentions)) {
            slHtml += `<span style="display:inline-block; background:var(--border); padding:2px 6px; border-radius:4px; margin:2px; font-size: 0.85rem;">${k} (${v})</span>`;
        }
        slHtml += '</div>';
    }
    
    statsLang.innerHTML = slHtml;

    // Populate standalone cards
    const parasiteEl = document.getElementById('parasite-count');
    const profanityEl = document.getElementById('profanity-count');
    if (parasiteEl && sem.parasite_counts) {
        parasiteEl.textContent = Object.values(sem.parasite_counts).reduce((a,b)=>a+b, 0);
    }
    if (profanityEl && sem.profanity_counts) {
        profanityEl.textContent = Object.values(sem.profanity_counts).reduce((a,b)=>a+b, 0);
    }

    // 10. Topics
    const topicsGrid = document.getElementById('topics-grid');
    const topicWarning = document.getElementById('topic-warning');
    const topicIncludedPercent = document.getElementById('topic-included-percent');
    
    if (sem.topic_exclusion_percentage !== undefined) {
        const included = 100 - sem.topic_exclusion_percentage;
        if (sem.topic_exclusion_percentage > 60) {
            if (topicWarning) topicWarning.style.display = 'block';
            if (topicIncludedPercent) topicIncludedPercent.textContent = included.toFixed(1);
        } else {
            if (topicWarning) topicWarning.style.display = 'none';
        }
    }
    
    if (sem.umap_projection && sem.umap_projection.points && sem.umap_projection.points.length > 0) {
        const traces = [];
        const uniqueTopics = [...new Set(sem.umap_projection.topics)];
        
        uniqueTopics.forEach(t => {
            const indices = sem.umap_projection.topics.map((val, idx) => val === t ? idx : -1).filter(idx => idx !== -1);
            traces.push({
                x: indices.map(i => sem.umap_projection.points[i][0]),
                y: indices.map(i => sem.umap_projection.points[i][1]),
                mode: 'markers',
                type: 'scatter',
                name: t === -1 ? 'Вне кластеров' : `Тема ${t}`,
                text: indices.map(i => sem.umap_projection.texts[i]),
                hoverinfo: 'text+name',
                marker: { size: 6, opacity: 0.7 }
            });
        });
        
        const layout = getLayoutTemplate('Карта сообщений (UMAP)');
        layout.hovermode = 'closest';
        layout.xaxis = {showgrid: false, zeroline: false, visible: false};
        layout.yaxis = {showgrid: false, zeroline: false, visible: false};
        Plotly.newPlot('chart-umap', traces, layout, {responsive: true});
    }

    if (sem.clusters && sem.clusters.length > 0) {
        topicsGrid.innerHTML = sem.clusters.map(c => `
            <div class="topic-card">
                <h3 style="margin-bottom:0.5rem; color:var(--primary); font-size:1.1rem">${c.name || 'Тема'}</h3>
                ${c.description ? `<p style="font-size:0.9rem; color:var(--text); margin-bottom:0.5rem; font-style:italic;">${c.description}</p>` : ''}
                <div class="topic-tags">
                    ${c.top_words.map(w => `<span class="topic-tag">${w}</span>`).join('')}
                </div>
                <ul class="topic-examples">
                    ${c.examples.map(ex => `<li>"${ex.substring(0, 80)}${ex.length > 80 ? '...' : ''}"</li>`).join('')}
                </ul>
                <div style="margin-top:1rem; font-size:0.8rem; color:var(--text-muted)">
                    <i class="fas fa-layer-group"></i> Сообщений в кластере: ${c.size}
                </div>
            </div>
        `).join('');
    } else {
        topicsGrid.innerHTML = `<p>Недостаточно данных для выделения тем.</p>`;
    }

    // 11. Funny Finds
    const findsGrid = document.getElementById('funny-finds-grid');
    let findsHTML = "";

    if (sem.signature_phrases) {
        for (const [author, phrases] of Object.entries(sem.signature_phrases)) {
            findsHTML += `
                <div class="find-card">
                    <h3>Словечки ${author}</h3>
                    <p>${phrases.join(', ')}</p>
                </div>
            `;
        }
    }

    if (sem.couple_dictionary && sem.couple_dictionary.length > 0) {
        findsHTML += `
            <div class="find-card">
                <h3>Словарь пары</h3>
                <p>${sem.couple_dictionary.join(' • ')}</p>
            </div>
        `;
    }
    
    if (sem.top_mentions) {
        findsHTML += `
            <div class="find-card">
                <h3>Кого обсуждали</h3>
                <p>${Object.keys(sem.top_mentions).slice(0, 5).join(', ')}</p>
            </div>
        `;
    }

    if (s.fastest_response) {
        findsHTML += `
            <div class="find-card">
                <h3>Скорость света</h3>
                <p>Самый быстрый ответ (${s.fastest_response.time} сек):<br><i>"${s.fastest_response.text}"</i></p>
            </div>
        `;
    }

    findsGrid.innerHTML = findsHTML || "<p>Пока ничего забавного не найдено.</p>";

    // Redraw charts on resize and theme toggle
    window.addEventListener('resize', () => {
        const charts = [
            'chart-message-shares', 'chart-monthly-dynamics', 'chart-heatmap', 
            'chart-sentiment-timeline', 'chart-top-words', 'chart-emoji-categories',
            'chart-top-emojis-overall', 'chart-top-emojis-authors', 'chart-umap',
            'chart-emotional-portrait', 'chart-emotional-arcs'
        ];
        charts.forEach(id => {
            if (document.getElementById(id)) {
                try { Plotly.Plots.resize(id); } catch(e) {}
            }
        });
    });
}
