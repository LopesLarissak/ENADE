import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || '/api';
const SESSION = 'enade-session';
function Highlight({ text }) {
  const parts = String(text || '').split(/(<mark>|<\/mark>)/g);
  let marked = false;
  return <>{parts.map((part, i) => { if (part === '<mark>') { marked = true; return null; } if (part === '</mark>') { marked = false; return null; } return marked ? <mark key={i}>{part}</mark> : <React.Fragment key={i}>{part}</React.Fragment>; })}</>;
}
function App() {
  const [token, setToken] = useState(localStorage.getItem('enade-token') || '');
  const [user, setUser] = useState(JSON.parse(localStorage.getItem('enade-user') || 'null'));
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [filters, setFilters] = useState({ q: '', area: '', course: '', year: '', exam_type: '', question_type: '', competency: '' });
  const [items, setItems] = useState([]); const [total, setTotal] = useState(0);
  const [cart, setCart] = useState([]); const [page, setPage] = useState(1);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const headers = useMemo(() => token ? { Authorization: `Bearer ${token}` } : {}, [token]);
  async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } });
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Erro HTTP ${response.status}`); }
    return response;
  }
  async function login(e) {
    e.preventDefault(); setError('');
    try {
      const response = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(credentials) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Falha no login');
      localStorage.setItem('enade-token', data.access_token); localStorage.setItem('enade-user', JSON.stringify(data.user));
      setToken(data.access_token); setUser(data.user); setNotice('Autenticação realizada.');
    } catch (err) { setError(err.message); }
  }
  function logout() { localStorage.removeItem('enade-token'); localStorage.removeItem('enade-user'); setToken(''); setUser(null); setCart([]); }
  async function search(e, requestedPage = page) {
    e?.preventDefault(); setError(''); setNotice('');
    try {
      const params = new URLSearchParams({ page: String(requestedPage), size: '10' });
      Object.entries(filters).forEach(([k, v]) => { if (v !== '') params.set(k, v); });
      const data = await (await request(`/questions?${params}`)).json(); setItems(data.items || []); setTotal(data.total || 0);
    } catch (err) { setError(err.message); }
  }
  async function addToCart(id) {
    if (!token) { setError('Entre com sua conta para montar uma lista.'); return; }
    try { const data = await (await request(`/cart/${SESSION}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_id: id }) })).json(); setCart(data.items); setNotice('Questão adicionada à lista.'); }
    catch (err) { setError(err.message); }
  }
  async function loadCart() { try { const data = await (await request(`/cart/${SESSION}`)).json(); setCart(data.items); } catch (err) { setError(err.message); } }
  async function removeCart(id) { try { const data = await (await request(`/cart/${SESSION}/${id}`, { method: 'DELETE' })).json(); setCart(data.items); } catch (err) { setError(err.message); } }
  async function exportFile(kind) {
    try { const response = await request(`/cart/${SESSION}/export.${kind}`); const blob = await response.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `simulado-enade.${kind}`; a.click(); URL.revokeObjectURL(url); }
    catch (err) { setError(err.message); }
  }
  return <main>
    <header><div><h1>Acervo ENADE</h1><p>Busca distribuída de provas e questões desde 2004</p></div>{user ? <div className="account"><span>{user.username} · {user.role}</span><button className="secondary" onClick={logout}>Sair</button></div> : null}</header>
    {!user && <form className="login" onSubmit={login}><h2>Acesso institucional (LDAP)</h2><input aria-label="Usuário" placeholder="Usuário LDAP" value={credentials.username} onChange={e => setCredentials({ ...credentials, username: e.target.value })} required/><input aria-label="Senha" placeholder="Senha" type="password" value={credentials.password} onChange={e => setCredentials({ ...credentials, password: e.target.value })} required/><button>Entrar</button><small>Laboratório: estudante / Estudante@123 · professor / Professor@123</small></form>}
    <section className="panel"><h2>Pesquisar questões</h2><form onSubmit={search} className="filters"><input className="wide" value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} placeholder="Tema, enunciado, fórmula ou competência"/><input value={filters.area} onChange={e => setFilters({ ...filters, area: e.target.value })} placeholder="Área"/><input value={filters.course} onChange={e => setFilters({ ...filters, course: e.target.value })} placeholder="Curso"/><input value={filters.year} onChange={e => setFilters({ ...filters, year: e.target.value })} placeholder="Ano" type="number"/><select value={filters.exam_type} onChange={e => setFilters({ ...filters, exam_type: e.target.value })}><option value="">Tipo de prova</option><option>FG</option><option>CE</option></select><select value={filters.question_type} onChange={e => setFilters({ ...filters, question_type: e.target.value })}><option value="">Tipo de questão</option><option value="objetiva">Objetiva</option><option value="discursiva">Discursiva</option></select><input value={filters.competency} onChange={e => setFilters({ ...filters, competency: e.target.value })} placeholder="Competência"/><button>Buscar</button></form></section>
    {error && <p className="alert" role="alert">{error}</p>}{notice && <p className="notice">{notice}</p>}
    <div className="results-head"><h2>Resultados <small>({total})</small></h2><button className="secondary" onClick={loadCart}>Minha lista ({cart.length})</button></div>
    {items.map(({ id, question, highlight }) => <article key={id}><div className="meta">{question.course} · {question.year || 'Ano não informado'} · {question.exam_type} · {question.question_type} · {question.source_pdf}, página {question.source_page}{question.annulled ? ' · ANULADA' : ''}</div><p>{highlight?.statement?.length ? <Highlight text={highlight.statement.join(' … ')} /> : question.statement}</p>{question.structured_media?.length > 0 && <small className="warning">Representação matemática candidata disponível para validação: {question.structured_media.length} elemento(s).</small>}{question.alternatives?.length > 0 && <ol type="A">{question.alternatives.map((a, i) => <li key={i}>{a.replace(/^[A-E][).]\s*/, '')}</li>)}</ol>}{question.media_review_required && <small className="warning">Contém mídia que requer revisão/conversão.</small>}<button className="secondary" onClick={() => addToCart(id)}>Adicionar à lista</button></article>)}
    <nav className="pagination"><button className="secondary" disabled={page <= 1} onClick={() => { const next = page - 1; setPage(next); search(null, next); }}>Anterior</button><span>Página {page}</span><button className="secondary" disabled={page * 10 >= total} onClick={() => { const next = page + 1; setPage(next); search(null, next); }}>Próxima</button></nav>
    {cart.length > 0 && <section className="panel"><h2>Lista de questões</h2>{cart.map(id => <div className="cart-row" key={id}><code>{id}</code><button className="secondary" onClick={() => removeCart(id)}>Remover</button></div>)}{user?.role === 'PROFESSOR' && <div className="actions"><button onClick={() => exportFile('json')}>Exportar JSON</button><button onClick={() => exportFile('pdf')}>Exportar PDF</button></div>}</section>}
    {user?.role === 'PROFESSOR' && <section className="panel"><h2>Painel do professor</h2><p>Indicadores e agregações analíticas protegidos por perfil.</p><a href={`${API}/analytics/courses`} target="_blank" rel="noreferrer">Distribuição por curso (JSON)</a> · <a href={`${API}/analytics/competencies/timeline`} target="_blank" rel="noreferrer">Competências por ano</a></section>}
    <footer>Plataforma acadêmica demonstrativa · API OpenAPI em <a href={`${API}/docs`} target="_blank" rel="noreferrer">/docs</a></footer>
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
