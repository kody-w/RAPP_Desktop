import { useState, useEffect } from 'react'
import { invoke } from '@tauri-apps/api/tauri'

type Page = 'home' | 'store' | 'hub' | 'projects' | 'settings'

interface Agent {
  id: string; name: string; description: string; version: string;
  icon?: string; path: string; filename: string; features?: string[];
}

interface Skill {
  id: string; name: string; description: string; version: string;
  icon?: string; path: string; features?: string[];
}

interface Implementation {
  id: string; name: string; description: string; version: string;
  icon?: string; repo: string; features?: string[];
}

interface Project {
  name: string; path: string; created: string;
}

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [agents, setAgents] = useState<Agent[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [implementations, setImplementations] = useState<Implementation[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [showNewProject, setShowNewProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')

  useEffect(() => {
    loadProjects()
  }, [])

  useEffect(() => {
    if (page === 'store') loadStore()
    if (page === 'hub') loadHub()
  }, [page])

  async function loadStore() {
    setLoading(true)
    try {
      const data = await invoke<string>('fetch_manifest', {
        url: 'https://raw.githubusercontent.com/kody-w/RAPP_Store/main/manifest.json'
      })
      const manifest = JSON.parse(data)
      setAgents(manifest.agents || [])
      setSkills(manifest.skills || [])
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  async function loadHub() {
    setLoading(true)
    try {
      const data = await invoke<string>('fetch_manifest', {
        url: 'https://raw.githubusercontent.com/kody-w/RAPP_Hub/main/manifest.json'
      })
      const manifest = JSON.parse(data)
      setImplementations(manifest.implementations || [])
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  async function loadProjects() {
    try {
      const list = await invoke<Project[]>('list_projects')
      setProjects(list)
    } catch (e) { console.error(e) }
  }

  async function installAgent(agent: Agent) {
    try {
      await invoke('install_agent', { agentId: agent.id, path: agent.path, filename: agent.filename })
      alert(`Installed ${agent.name}`)
    } catch (e) { alert(`Error: ${e}`) }
  }

  async function installSkill(skill: Skill) {
    try {
      await invoke('install_skill', { skillId: skill.id, path: skill.path })
      alert(`Installed ${skill.name}`)
    } catch (e) { alert(`Error: ${e}`) }
  }

  async function cloneImpl(impl: Implementation) {
    try {
      await invoke('clone_implementation', { repo: impl.repo, name: impl.id })
      alert(`Cloned ${impl.name}`)
      loadProjects()
    } catch (e) { alert(`Error: ${e}`) }
  }

  async function createProject() {
    if (!newProjectName.trim()) return
    try {
      await invoke('create_project', { name: newProjectName })
      setNewProjectName('')
      setShowNewProject(false)
      loadProjects()
    } catch (e) { alert(`Error: ${e}`) }
  }

  async function openProject(path: string) {
    await invoke('open_path', { path })
  }

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.description.toLowerCase().includes(search.toLowerCase())
  )
  const filteredSkills = skills.filter(s =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.description.toLowerCase().includes(search.toLowerCase())
  )
  const filteredImpls = implementations.filter(i =>
    i.name.toLowerCase().includes(search.toLowerCase()) ||
    i.description.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">🤖</span>
          <h1>RAPP</h1>
        </div>
        <nav className="nav">
          <button className={`nav-item ${page === 'home' ? 'active' : ''}`} onClick={() => setPage('home')}>
            <span className="nav-icon">🏠</span> Home
          </button>
          <button className={`nav-item ${page === 'store' ? 'active' : ''}`} onClick={() => setPage('store')}>
            <span className="nav-icon">📦</span> Store
          </button>
          <button className={`nav-item ${page === 'hub' ? 'active' : ''}`} onClick={() => setPage('hub')}>
            <span className="nav-icon">🌐</span> Hub
          </button>
          <button className={`nav-item ${page === 'projects' ? 'active' : ''}`} onClick={() => setPage('projects')}>
            <span className="nav-icon">📁</span> Projects
          </button>
          <button className={`nav-item ${page === 'settings' ? 'active' : ''}`} onClick={() => setPage('settings')}>
            <span className="nav-icon">⚙️</span> Settings
          </button>
        </nav>
      </aside>

      <main className="main">
        {page === 'home' && (
          <>
            <header className="header"><h2>Welcome to RAPP</h2></header>
            <div className="content">
              <div className="welcome">
                <div className="welcome-icon">🚀</div>
                <h2>Rapid AI Agent Production Pipeline</h2>
                <p>Build production-ready AI agents in minutes</p>
                <div className="quick-actions">
                  <div className="quick-action" onClick={() => setPage('store')}>
                    <div className="quick-action-icon">📦</div>
                    <h4>Browse Store</h4>
                    <p>Install agents & skills</p>
                  </div>
                  <div className="quick-action" onClick={() => setPage('hub')}>
                    <div className="quick-action-icon">🌐</div>
                    <h4>Explore Hub</h4>
                    <p>Find implementations</p>
                  </div>
                  <div className="quick-action" onClick={() => { setPage('projects'); setShowNewProject(true) }}>
                    <div className="quick-action-icon">✨</div>
                    <h4>New Project</h4>
                    <p>Start from scratch</p>
                  </div>
                </div>
              </div>
              <div className="stats-row" style={{ justifyContent: 'center', marginTop: '2rem' }}>
                <div className="stat-card">
                  <div className="stat-value">{projects.length}</div>
                  <div className="stat-label">Projects</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{agents.length || '—'}</div>
                  <div className="stat-label">Agents</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{skills.length || '—'}</div>
                  <div className="stat-label">Skills</div>
                </div>
              </div>
            </div>
          </>
        )}

        {page === 'store' && (
          <>
            <header className="header">
              <h2>RAPP Store</h2>
              <div className="search-box">
                <span className="search-icon">🔍</span>
                <input placeholder="Search agents & skills..." value={search} onChange={e => setSearch(e.target.value)} />
              </div>
            </header>
            <div className="content">
              {loading ? (
                <div className="loading"><div className="spinner" /> Loading...</div>
              ) : (
                <>
                  <h3 style={{ marginBottom: '1rem' }}>Agents ({filteredAgents.length})</h3>
                  <div className="card-grid">
                    {filteredAgents.map(agent => (
                      <div key={agent.id} className="card">
                        <div className="card-header">
                          <span className="card-icon">{agent.icon || '🤖'}</span>
                          <div>
                            <div className="card-title">{agent.name}</div>
                            <span className="card-badge badge-agent">Agent</span>
                          </div>
                        </div>
                        <p className="card-desc">{agent.description}</p>
                        <div className="card-tags">
                          {agent.features?.slice(0, 3).map((f, i) => <span key={i} className="tag">{f}</span>)}
                        </div>
                        <div className="card-actions">
                          <button className="btn btn-primary" onClick={() => installAgent(agent)}>Install</button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <h3 style={{ margin: '2rem 0 1rem' }}>Skills ({filteredSkills.length})</h3>
                  <div className="card-grid">
                    {filteredSkills.map(skill => (
                      <div key={skill.id} className="card">
                        <div className="card-header">
                          <span className="card-icon">{skill.icon || '✨'}</span>
                          <div>
                            <div className="card-title">{skill.name}</div>
                            <span className="card-badge badge-skill">Skill</span>
                          </div>
                        </div>
                        <p className="card-desc">{skill.description}</p>
                        <div className="card-tags">
                          {skill.features?.slice(0, 3).map((f, i) => <span key={i} className="tag">{f}</span>)}
                        </div>
                        <div className="card-actions">
                          <button className="btn btn-primary" onClick={() => installSkill(skill)}>Install</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </>
        )}

        {page === 'hub' && (
          <>
            <header className="header">
              <h2>RAPP Hub</h2>
              <div className="search-box">
                <span className="search-icon">🔍</span>
                <input placeholder="Search implementations..." value={search} onChange={e => setSearch(e.target.value)} />
              </div>
            </header>
            <div className="content">
              {loading ? (
                <div className="loading"><div className="spinner" /> Loading...</div>
              ) : (
                <div className="card-grid">
                  {filteredImpls.map(impl => (
                    <div key={impl.id} className="card">
                      <div className="card-header">
                        <span className="card-icon">{impl.icon || '🏠'}</span>
                        <div>
                          <div className="card-title">{impl.name}</div>
                          <span className="card-badge badge-impl">Implementation</span>
                        </div>
                      </div>
                      <p className="card-desc">{impl.description}</p>
                      <div className="card-tags">
                        {impl.features?.slice(0, 3).map((f, i) => <span key={i} className="tag">{f}</span>)}
                      </div>
                      <div className="card-actions">
                        <button className="btn btn-primary" onClick={() => cloneImpl(impl)}>Clone</button>
                        <a href={impl.repo} target="_blank" rel="noopener" className="btn btn-secondary">View</a>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {page === 'projects' && (
          <>
            <header className="header">
              <h2>My Projects</h2>
              <button className="btn btn-primary" onClick={() => setShowNewProject(true)}>+ New Project</button>
            </header>
            <div className="content">
              {projects.length === 0 ? (
                <div className="welcome">
                  <div className="welcome-icon">📁</div>
                  <h2>No Projects Yet</h2>
                  <p>Create a new project or clone one from RAPP Hub</p>
                  <div className="quick-actions">
                    <div className="quick-action" onClick={() => setShowNewProject(true)}>
                      <div className="quick-action-icon">✨</div>
                      <h4>New Project</h4>
                    </div>
                    <div className="quick-action" onClick={() => setPage('hub')}>
                      <div className="quick-action-icon">🌐</div>
                      <h4>Browse Hub</h4>
                    </div>
                  </div>
                </div>
              ) : (
                projects.map(project => (
                  <div key={project.name} className="project-item">
                    <div className="project-info">
                      <h3>{project.name}</h3>
                      <p>{project.path}</p>
                    </div>
                    <div className="card-actions">
                      <button className="btn btn-secondary" onClick={() => openProject(project.path)}>Open</button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {page === 'settings' && (
          <>
            <header className="header"><h2>Settings</h2></header>
            <div className="content">
              <div className="card" style={{ maxWidth: 500 }}>
                <h3 style={{ marginBottom: '1rem' }}>RAPP Configuration</h3>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  Configure your RAPP installation and Azure deployment.
                </p>
                <a href="https://github.com/kody-w/rapp-installer" target="_blank" rel="noopener" className="btn btn-primary">
                  View Installer Docs
                </a>
              </div>
            </div>
          </>
        )}
      </main>

      {showNewProject && (
        <div className="modal-overlay" onClick={() => setShowNewProject(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>New Project</h3>
              <button className="modal-close" onClick={() => setShowNewProject(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <div className="input-group">
                <label>Project Name</label>
                <input value={newProjectName} onChange={e => setNewProjectName(e.target.value)} placeholder="my-rapp-project" />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowNewProject(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={createProject}>Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
