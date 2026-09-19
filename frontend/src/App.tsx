import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type Message = {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

type Tenant = {
  id: string
  label: string
  accent: string
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const defaultTenants: Tenant[] = [
  { id: 'tenant-1', label: 'Succeed', accent: 'amber' },
  { id: 'tenant-2', label: '16Digits', accent: 'blue' },
  
]

function App() {
  const [tenants, setTenants] = useState<Tenant[]>(defaultTenants)
  const [activeTenant, setActiveTenant] = useState(defaultTenants[0].id)
  const [messages, setMessages] = useState<Record<string, Message[]>>({})
  const [query, setQuery] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [isQuerying, setIsQuerying] = useState(false)
  const [isIngesting, setIsIngesting] = useState(false)
  const [notice, setNotice] = useState('')
  const [indexingId, setIndexingId] = useState<string | null>(null)
  const [isAddTenantOpen, setIsAddTenantOpen] = useState(false)
  const [newTenantName, setNewTenantName] = useState('')
  const [newTenantId, setNewTenantId] = useState('')
  const [tenantFormError, setTenantFormError] = useState('')

  const currentTenant = tenants.find((tenant) => tenant.id === activeTenant) ?? tenants[0]
  const currentMessages = messages[activeTenant] ?? []

  useEffect(() => {
    const stored = window.localStorage.getItem('multitenant-tenants')
    if (stored) setTenants(JSON.parse(stored))
  }, [])

  useEffect(() => {
    window.localStorage.setItem('multitenant-tenants', JSON.stringify(tenants))
  }, [tenants])

  function switchTenant(id: string) {
    setActiveTenant(id)
    setQuery('')
    setNotice('')
  }

  function openAddTenant() {
    setNewTenantName('')
    setNewTenantId('')
    setTenantFormError('')
    setIsAddTenantOpen(true)
  }

  function addTenant(event: FormEvent) {
    event.preventDefault()
    const label = newTenantName.trim()
    const id = newTenantId.trim().toLowerCase().replace(/\s+/g, '-')
    if (!label || !id) {
      setTenantFormError('Enter both a tenant name and tenant ID.')
      return
    }
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(id)) {
      setTenantFormError('Use lowercase letters, numbers, hyphens, or underscores for the ID.')
      return
    }
    if (tenants.some((tenant) => tenant.id === id)) {
      setTenantFormError('That tenant ID already exists.')
      return
    }
    const nextTenant = { id, label, accent: 'green' }
    setTenants((current) => [...current, nextTenant])
    setActiveTenant(id)
    setIsAddTenantOpen(false)
  }

  async function submitQuery(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || isQuerying) return
    setQuery('')
    setMessages((current) => ({
      ...current,
      [activeTenant]: [...(current[activeTenant] ?? []), { role: 'user', content: trimmed }],
    }))
    setIsQuerying(true)
    setNotice('')
    try {
      const response = await fetch(`${API_URL}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': activeTenant },
        body: JSON.stringify({ query: trimmed, top_k: 4 }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail ?? 'Unable to query the workspace.')
      setMessages((current) => ({
        ...current,
        [activeTenant]: [
          ...(current[activeTenant] ?? []),
          { role: 'assistant', content: data.answer, sources: data.sources },
        ],
      }))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Unable to reach the RAG service.')
    } finally {
      setIsQuerying(false)
    }
  }

  async function ingestFiles() {
    if (files.length === 0 || isIngesting) return
    const formData = new FormData()
    files.forEach((file) => formData.append('upload', file))
    setIsIngesting(true)
    setNotice('')
    try {
      const response = await fetch(`${API_URL}/api/ingest`, {
        method: 'POST',
        headers: { 'X-Tenant-ID': activeTenant },
        body: formData,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail ?? 'Unable to index this document.')
      const skipped = data.results.filter((result: { status: string }) => result.status === 'skipped').length
      const skippedMessage = skipped > 0 ? ` · ${skipped} skipped (no readable text)` : ''
      setNotice(`${data.documents} document${data.documents === 1 ? '' : 's'} added to ${currentTenant.label} · ${data.indexed_chunks} chunks indexed${skippedMessage}`)
      setIndexingId(data.indexing_id)
      setFiles([])
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Unable to upload the document.')
    } finally {
      setIsIngesting(false)
    }
  }

  return (
    <main className="app-shell">
      {indexingId && <div className="modal-backdrop" role="presentation"><section className="success-modal" role="dialog" aria-modal="true" aria-labelledby="index-created-title"><button className="modal-close" onClick={() => setIndexingId(null)} aria-label="Close">×</button><div className="success-mark">✓</div><p className="modal-eyebrow">Index created</p><h2 id="index-created-title">Your documents are ready</h2><p className="modal-copy">This indexing operation is now available in <strong>{currentTenant.label}</strong>.</p><div className="index-id"><span>Indexing ID</span><strong>{indexingId}</strong></div><button className="modal-done" onClick={() => setIndexingId(null)}>Done</button></section></div>}
      {isAddTenantOpen && <div className="modal-backdrop" role="presentation"><form className="tenant-modal" role="dialog" aria-modal="true" aria-labelledby="add-tenant-title" onSubmit={addTenant}><button type="button" className="modal-close" onClick={() => setIsAddTenantOpen(false)} aria-label="Close">×</button><p className="modal-eyebrow">New workspace</p><h2 id="add-tenant-title">Add a tenant</h2><p className="modal-copy">Create a private workspace for a new organization.</p><label className="form-field"><span>Tenant name</span><input autoFocus value={newTenantName} onChange={(event) => setNewTenantName(event.target.value)} placeholder="e.g. Acme Operations" /></label><label className="form-field"><span>Tenant ID</span><input value={newTenantId} onChange={(event) => setNewTenantId(event.target.value)} placeholder="e.g. acme-ops" /><small>Used to isolate documents and queries.</small></label>{tenantFormError && <p className="form-error">{tenantFormError}</p>}<div className="tenant-modal-actions"><button type="button" className="modal-cancel" onClick={() => setIsAddTenantOpen(false)}>Cancel</button><button type="submit" className="modal-done">Create tenant</button></div></form></div>}
      <aside className="sidebar">
        <div className="brand-mark"><span>◒</span><div><strong>Multitenet RAG</strong><small>knowledge workspaces</small></div></div>
        <div className="sidebar-label">Your tenants <span>{tenants.length}</span></div>
        <nav className="tenant-list" aria-label="Tenants">
          {tenants.map((tenant) => (
            <button key={tenant.id} className={`tenant-button ${tenant.id === activeTenant ? 'active' : ''}`} onClick={() => switchTenant(tenant.id)}>
              <span className={`tenant-avatar ${tenant.accent}`}>{tenant.label.slice(0, 1).toUpperCase()}</span>
              <span><strong>{tenant.label}</strong><small>{tenant.id}</small></span>
              {tenant.id === activeTenant && <i />}
            </button>
          ))}
        </nav>
        <button className="add-tenant" onClick={openAddTenant}><span>+</span> Add tenant</button>
        <div className="sidebar-footer"><span className="status-dot" /> API connected <small>v0.1 local</small></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div className="breadcrumb"><span>Workspaces</span><b>/</b><strong>{currentTenant.label}</strong></div><div className="top-actions"><button className="icon-button" title="Search">⌕</button><span className="user-avatar">AK</span></div></header>
        <div className="workspace-content">
          <div className="workspace-heading"><div><p className="eyebrow">Active workspace <span className={`mini-dot ${currentTenant.accent}`} /></p><h1>{currentTenant.label}</h1><p className="description">Ask questions against this tenant's private knowledge base.</p></div><div className="tenant-switch"><label htmlFor="tenant-select">Switch tenant</label><select id="tenant-select" value={activeTenant} onChange={(event) => switchTenant(event.target.value)}>{tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.label}</option>)}</select></div></div>

          <div className="content-grid">
            <section className="chat-panel">
              <div className="panel-heading"><div><h2>Knowledge assistant</h2><p>Grounded answers from indexed documents</p></div><span className="live-badge"><i /> live</span></div>
              <div className="messages">
                {currentMessages.length === 0 && <div className="empty-state"><div className="empty-icon">✦</div><h3>Start with a question</h3><p>Your conversation is private to <strong>{currentTenant.label}</strong>. Try asking about a policy, project, or document.</p><div className="suggestions"><button onClick={() => setQuery('What documents are available?')}>What documents are available?</button><button onClick={() => setQuery('Summarize the key points')}>Summarize the key points</button></div></div>}
                {currentMessages.map((message, index) => <article className={`message ${message.role}`} key={`${message.role}-${index}`}><span className="message-label">{message.role === 'user' ? 'You' : 'Atlas'}</span><p>{message.content}</p>{message.sources && message.sources.length > 0 && <div className="sources">Sources {message.sources.map((source) => <span key={source}>▧ {source}</span>)}</div>}</article>)}
                {isQuerying && <div className="message assistant thinking"><span className="message-label">MultiTenet RAG</span><p><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></p></div>}
              </div>
              <form className="composer" onSubmit={submitQuery}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Ask ${currentTenant.label} anything...`} /><button type="submit" disabled={!query.trim() || isQuerying} title="Send question">↑</button></form>
            </section>

            <aside className="ingest-panel"><div className="panel-heading"><div><h2>Knowledge base</h2><p>Private to this tenant</p></div><span className="lock">⌑</span></div><div className="upload-zone"><div className="upload-icon">↥</div><h3>Index documents</h3><p>Choose multiple PDF or TXT files at once</p><label className="file-picker">{files.length > 0 ? `${files.length} document${files.length === 1 ? '' : 's'} selected` : 'Choose documents'}<input type="file" accept=".pdf,.txt" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} /></label>{files.length > 0 && <div className="selected-files">{files.map((file) => <span key={`${file.name}-${file.lastModified}`}>{file.name}</span>)}</div>}{files.length > 0 && <button className="index-button" onClick={ingestFiles} disabled={isIngesting}>{isIngesting ? `Indexing ${files.length}...` : `Index ${files.length} document${files.length === 1 ? '' : 's'}`}</button>}</div><div className="base-note"><span>◈</span><div><strong>Tenant isolation on</strong><p>Every document is indexed for <b>{currentTenant.id}</b>.</p></div></div>{notice && <p className="notice">{notice}</p>}</aside>
          </div>
        </div>
      </section>
    </main>
  )
}

export default App
