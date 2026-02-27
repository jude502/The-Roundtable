const API = 'http://localhost:8080'

// ── Window drag (IPC-based for Electron v40+) ─────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const header = document.getElementById('header-drag')
  if (!header || !window.electronAPI) return

  let dragging = false

  header.addEventListener('mousedown', (e) => {
    if (e.target.closest('button, input, a, [data-no-drag]')) return
    if (e.button !== 0) return
    dragging = true
    window.electronAPI.dragStart(e.screenX, e.screenY)
    e.preventDefault()
  })

  document.addEventListener('mousemove', (e) => {
    if (!dragging) return
    window.electronAPI.dragMove(e.screenX, e.screenY)
  })

  document.addEventListener('mouseup', () => {
    if (!dragging) return
    dragging = false
    window.electronAPI.dragEnd()
  })
})

// ── State ────────────────────────────────────────────────────────────────────

let availableModels = []
let selectedModels = new Set()
let selectedRounds = 1
let activeStream = null

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  await loadModels()
  await loadSettingsPreview()
}

async function loadModels() {
  try {
    const r = await fetch(`${API}/models`)
    availableModels = await r.json()
    renderModelChips()
    // Auto-select all available models
    availableModels.forEach(m => { if (m.available) selectedModels.add(m.id) })
    updateChipStates()
    updateCostHint()
  } catch {
    document.getElementById('model-selector').innerHTML =
      '<span style="color:#6b6b8a;font-size:13px">Server not running — start with: python main.py</span>'
  }
}

function renderModelChips() {
  const container = document.getElementById('model-selector')
  container.innerHTML = availableModels.map(m => `
    <div class="model-chip ${m.available ? '' : 'unavailable'}"
         id="chip-${m.id}"
         style="--model-color: ${m.color}"
         onclick="${m.available ? `toggleModel('${m.id}')` : 'showNoKey()'}">
      <div class="model-dot"></div>
      <span>${m.name}</span>
      <div class="chip-check"></div>
    </div>`).join('')
}

function updateChipStates() {
  availableModels.forEach(m => {
    const chip = document.getElementById(`chip-${m.id}`)
    if (!chip) return
    chip.classList.toggle('selected', selectedModels.has(m.id))
  })
}

function toggleModel(id) {
  if (selectedModels.has(id)) {
    if (selectedModels.size <= 1) return // keep at least 1
    selectedModels.delete(id)
  } else {
    selectedModels.add(id)
  }
  updateChipStates()
  updateCostHint()
}

function setRounds(n) {
  selectedRounds = n
  document.querySelectorAll('.round-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.rounds) === n)
  })
  updateCostHint()
}

function updateCostHint() {
  const n = selectedModels.size
  const r = selectedRounds
  // Rough: round 1 = ~$0.005/model, round 2+ adds context so ~$0.015/model
  const est = n * 0.005 + n * (r - 1) * 0.015
  document.getElementById('cost-hint').textContent =
    n > 0 ? `~$${est.toFixed(3)} estimated` : ''
}

function showNoKey() {
  openSettings()
}

function handleKey(e) {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) startDebate()
}

// ── Debate ───────────────────────────────────────────────────────────────────

async function startDebate() {
  const question = document.getElementById('question').value.trim()
  if (!question) return
  if (selectedModels.size === 0) { openSettings(); return }

  // Switch to debate view
  document.getElementById('setup-panel').style.display = 'none'
  const debateView = document.getElementById('debate-view')
  debateView.style.display = 'flex'
  document.getElementById('debate-question').textContent = `"${question}"`
  document.getElementById('rounds-container').innerHTML = ''
  document.getElementById('debate-status').textContent = 'Starting debate...'
  document.getElementById('start-btn').disabled = true

  const models = [...selectedModels].join(',')
  const showThinking = document.getElementById('show-thinking').checked
  const url = `${API}/debate/stream?question=${encodeURIComponent(question)}&models=${encodeURIComponent(models)}&rounds=${selectedRounds}&thinking=${showThinking}`

  // Track current round state per model
  const cardState = {}  // model_id -> { card, thinkingEl, bodyEl, color, text, thinkingText, inThinking }
  let currentRound = null

  const es = new EventSource(url)
  activeStream = es

  es.onmessage = (e) => {
    let d
    try { d = JSON.parse(e.data) } catch { return }

    if (d.type === 'round_start') {
      currentRound = d.round
      const roundSection = document.createElement('div')
      roundSection.className = 'round-section'
      const label = d.round === 1
        ? `Round ${d.round} of ${d.total_rounds} <span style="color:var(--muted);font-weight:400;font-size:10px;text-transform:none;letter-spacing:0">parallel</span>`
        : `Round ${d.round} of ${d.total_rounds}`
      roundSection.innerHTML = `
        <div class="round-label">${label}</div>
        <div class="round-cards" id="round-${d.round}-cards"></div>`
      document.getElementById('rounds-container').appendChild(roundSection)
      document.getElementById('debate-status').textContent =
        d.round === 1 ? 'All models answering simultaneously...' : 'Models are reading and responding...'
    }

    else if (d.type === 'model_start') {
      const card = document.createElement('div')
      card.className = 'model-card active'
      card.id = `card-${d.round}-${d.model_id}`
      card.style.setProperty('--model-color', d.color)
      card.innerHTML = `
        <div class="model-card-header">
          <div class="model-avatar">${d.avatar}</div>
          <div class="model-card-name">${d.model_name}</div>
          <div class="model-card-status" id="status-${d.round}-${d.model_id}">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
          </div>
        </div>
        <div class="model-card-body" id="body-${d.round}-${d.model_id}">
          <span class="cursor" style="--model-color:${d.color}"></span>
        </div>`
      document.getElementById(`round-${d.round}-cards`).appendChild(card)
      cardState[d.model_id] = {
        card,
        bodyEl: card.querySelector(`#body-${d.round}-${d.model_id}`),
        color: d.color,
        text: '',
        thinkingText: '',
        thinkingEl: null,
        inThinking: false,
      }
    }

    else if (d.type === 'thinking_start') {
      const state = cardState[d.model_id]
      if (!state) return
      state.inThinking = true
      // Insert thinking block before body
      const block = document.createElement('div')
      block.className = 'thinking-block'
      block.id = `thinking-${d.model_id}`
      block.innerHTML = `
        <div class="thinking-header" onclick="toggleThinking('${d.model_id}')">
          <em class="thinking-chevron">▾</em>
          Thinking
          <span id="thinking-words-${d.model_id}" style="margin-left:auto;font-weight:400;color:#8b5cf690;font-size:11px"></span>
        </div>
        <div class="thinking-content" id="thinking-content-${d.model_id}"></div>`
      state.card.querySelector('.model-card-body').before(block)
      state.thinkingEl = block.querySelector(`#thinking-content-${d.model_id}`)
    }

    else if (d.type === 'thinking_token') {
      const state = cardState[d.model_id]
      if (!state || !state.thinkingEl) return
      state.thinkingText += d.token
      state.thinkingEl.textContent = state.thinkingText
      const words = state.thinkingText.split(/\s+/).length
      const wEl = document.getElementById(`thinking-words-${d.model_id}`)
      if (wEl) wEl.textContent = `${words} words`
      state.thinkingEl.scrollTop = state.thinkingEl.scrollHeight
    }

    else if (d.type === 'text_start') {
      const state = cardState[d.model_id]
      if (state) state.inThinking = false
    }

    else if (d.type === 'token') {
      const state = cardState[d.model_id]
      if (!state) return
      state.text += d.token
      state.bodyEl.innerHTML = escapeHtml(state.text) +
        `<span class="cursor" style="--model-color:${state.color}"></span>`
      state.bodyEl.scrollIntoView({ block: 'nearest' })
    }

    else if (d.type === 'model_done') {
      const state = cardState[d.model_id]
      if (state) {
        state.bodyEl.innerHTML = escapeHtml(state.text)
        state.card.classList.remove('active')
        // Collapse thinking block
        const thinkingBlock = document.getElementById(`thinking-${d.model_id}`)
        if (thinkingBlock) thinkingBlock.classList.add('collapsed')
        const statusEl = document.getElementById(`status-${d.round}-${d.model_id}`)
        if (statusEl) statusEl.innerHTML = '<span style="color:var(--dim);font-size:12px">Done</span>'
      }
    }

    else if (d.type === 'round_done') {
      Object.keys(cardState).forEach(k => delete cardState[k])
    }

    else if (d.type === 'debate_done') {
      document.getElementById('debate-status').textContent = ''
      document.getElementById('start-btn').disabled = false
      es.close()
      activeStream = null
    }

    else if (d.type === 'error') {
      const state = cardState[d.model_id]
      if (state) {
        state.bodyEl.innerHTML = `<span style="color:#ff4d6a">Error: ${escapeHtml(d.message)}</span>`
      }
    }
  }

  es.onerror = () => {
    document.getElementById('debate-status').textContent = 'Connection lost.'
    document.getElementById('start-btn').disabled = false
    es.close()
    activeStream = null
  }
}

function resetDebate() {
  if (activeStream) { activeStream.close(); activeStream = null }
  document.getElementById('debate-view').style.display = 'none'
  document.getElementById('setup-panel').style.display = 'flex'
  document.getElementById('start-btn').disabled = false
  document.getElementById('debate-status').textContent = ''
}

function toggleThinking(modelId) {
  const block = document.getElementById(`thinking-${modelId}`)
  if (block) block.classList.toggle('collapsed')
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// ── Settings ─────────────────────────────────────────────────────────────────

function openSettings() {
  document.getElementById('settings-overlay').classList.add('open')
}

function closeSettings() {
  document.getElementById('settings-overlay').classList.remove('open')
}

async function loadSettingsPreview() {
  try {
    const r = await fetch(`${API}/settings`)
    const s = await r.json()
    if (s.ANTHROPIC_API_KEY) document.getElementById('key-anthropic').placeholder = s.ANTHROPIC_API_KEY
    if (s.OPENAI_API_KEY)    document.getElementById('key-openai').placeholder    = s.OPENAI_API_KEY
    if (s.GOOGLE_API_KEY)    document.getElementById('key-google').placeholder    = s.GOOGLE_API_KEY
    if (s.XAI_API_KEY)       document.getElementById('key-xai').placeholder       = s.XAI_API_KEY
    if (s.GROQ_API_KEY)      document.getElementById('key-groq').placeholder      = s.GROQ_API_KEY
  } catch {}
}

async function saveSettings() {
  const body = {
    anthropic: document.getElementById('key-anthropic').value.trim(),
    openai:    document.getElementById('key-openai').value.trim(),
    google:    document.getElementById('key-google').value.trim(),
    xai:       document.getElementById('key-xai').value.trim(),
    groq:      document.getElementById('key-groq').value.trim(),
  }
  await fetch(`${API}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  closeSettings()
  // Reload models to update availability
  await loadModels()
  await loadSettingsPreview()
}

// ── Boot ─────────────────────────────────────────────────────────────────────

init()
