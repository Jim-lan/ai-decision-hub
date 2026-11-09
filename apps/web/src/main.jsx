import React, {useEffect, useRef, useState} from 'react'
import {createRoot} from 'react-dom/client'
import '@fontsource-variable/inter'
import './style.css'

async function api(path, body) {
  const res = await fetch('/v1' + path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', ...body.headers},
    body: JSON.stringify(body.data ?? body)
  })
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('session-ended'))
    const error = await res.json().catch(() => ({}))
    throw new Error(error.title || 'Could not reach the workspace')
  }
  return res.status === 204 ? null : res.json()
}

function Brand() {
  return <div className="brand"><span className="mark" aria-hidden="true">◧</span> Decision Hub</div>
}

function ErrorNote({message}) {
  return message ? <p role="alert" className="error">{message}</p> : null
}

function Login({onLogin}) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  async function submit(e) {
    e.preventDefault()
    const password = new FormData(e.currentTarget).get('password')
    setBusy(true)
    try { await api('/auth/login', {password}); onLogin() }
    catch (err) { setError(err.message); setBusy(false) }
  }
  return <main className="entry"><div className="entryInner"><Brand/>
    <h1>Open your workspace</h1><p className="intro">Sign in to your projects and conversations.</p>
    <form onSubmit={submit}><label>Owner password<input name="password" type="password" autoComplete="current-password" required autoFocus /></label>
    <ErrorNote message={error}/><button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button></form>
  </div></main>
}

function NewItem({label, onCreate}) {
  const [open,setOpen]=useState(false), [busy,setBusy]=useState(false), [error,setError]=useState('')
  if (!open) return <button className="quiet" onClick={()=>setOpen(true)}>+ {label}</button>
  async function submit(e) {
    e.preventDefault()
    const value=new FormData(e.currentTarget).get('value').trim()
    if (!value || busy) return
    setBusy(true)
    try { await onCreate(value); setOpen(false); setError('') }
    catch(err) { setError(err.message) }
    finally { setBusy(false) }
  }
  return <form className="newItem" onSubmit={submit}><label>{label}<input name="value" autoFocus required maxLength={160}/></label>
    <ErrorNote message={error}/><div className="actions"><button disabled={busy}>Create</button><button type="button" className="quiet" onClick={()=>setOpen(false)}>Cancel</button></div></form>
}

function ManualTarget({run, target, original, reload}) {
  const [busy,setBusy]=useState(false), [error,setError]=useState('')
  async function submit(e) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    setBusy(true)
    try {
      await api('/runs/'+run.run_id+'/manual-responses', {target_id:target.target_id,
        model_family:data.get('family').trim() || 'unknown', content:data.get('content')})
      await reload()
    } catch(err) {setError(err.message)}
    finally {setBusy(false)}
  }
  return <details className="target"><summary>{target.model_id}<small>{original ? 'Imported' : target.status==='missing'?'Deadline passed':'Awaiting import'}</small></summary>
    {original ? <><p className="meta">Manual import · User-declared identity · {original.model_family}</p><p className="original">{original.content}</p></> :
      target.status === 'awaiting_manual' && <form onSubmit={submit}><label>Model family (optional)<input name="family" maxLength={160}/></label>
        <label>Original response<textarea name="content" required maxLength={64000} rows="5"/></label>
        <ErrorNote message={error}/><button disabled={busy}>Save original</button></form>}
  </details>
}

function Thread({item}) {
  const [history,setHistory]=useState(null), [runs,setRuns]=useState([]), [originals,setOriginals]=useState([]), [error,setError]=useState('')
  const [question,setQuestion]=useState(''), [models,setModels]=useState(''), [busy,setBusy]=useState(false)
  const request=useRef(null)
  async function reload() {
    let cursor=null, rows=[]
    do {
      const page=await api('/conversations/'+item.conversation_id+'/messages?limit=100'+(cursor?'&cursor='+encodeURIComponent(cursor):''))
      rows.push(...page.items); cursor=page.next_cursor
    } while (cursor)
    const latest=await api('/conversations/'+item.conversation_id+'/runs')
    const answers=await Promise.all(latest.map(r=>api('/runs/'+r.run_id+'/responses')))
    setHistory(rows);setRuns(latest);setOriginals(answers.flat())
  }
  useEffect(()=>{reload().catch(err=>setError(err.message))},[item.conversation_id])
  async function submit(e) {
    e.preventDefault()
    if (!question.trim() || busy) return
    setBusy(true);setError('')
    try {
      const targets=models.split(',').map(s=>s.trim()).filter(Boolean)
      if (targets.length) {
        const data={conversation_id:item.conversation_id,question,model_targets:targets.map(model_id=>({provider:'manual',model_id}))}
        const signature=JSON.stringify(data)
        if (request.current?.signature!==signature) request.current={signature,key:crypto.randomUUID()}
        await api('/runs',{headers:{'Idempotency-Key':request.current.key},data})
      } else {
        await api('/conversations/'+item.conversation_id+'/messages',{content:question})
      }
      setQuestion('');setModels('');request.current=null
      await reload()
    } catch(err) {setError(err.message)}
    finally {setBusy(false)}
  }
  return <section className="thread"><header><h1>{item.title}</h1></header>
    <ErrorNote message={error}/>
    {history === null ? <p>Loading history…</p> : history.length===0 ? <div className="empty"><h2>Start with a question</h2><p>Add model names below to collect independent answers by hand.</p></div> :
      <div className="history">{history.map(m=>{
        const run=runs.find(r=>r.message_id===m.message_id)
        return <article key={m.message_id}><div className="meta">Your question <span>·</span> {new Date(m.created_at).toLocaleString()}</div>
          <p className="original">{m.content}</p>{run && run.targets.map(t=><ManualTarget key={t.target_id} run={run} target={t} original={originals.find(o=>o.target_id===t.target_id)} reload={reload}/>)}</article>
      })}</div>}
    <form className="composer" onSubmit={submit}><label>Question<textarea value={question} onChange={e=>setQuestion(e.target.value)} required maxLength={64000} rows="3" placeholder="What are you deciding?"/></label>
      <label>Manual model names <small>(optional, comma-separated)</small><input value={models} onChange={e=>setModels(e.target.value)} placeholder="e.g. Gemini, Claude"/></label>
      <button disabled={busy || !question.trim()}>{busy?'Saving…':models.trim()?'Start comparison':'Save question'}</button></form>
  </section>
}

function Conversations({project}) {
  const [items,setItems]=useState(null), [active,setActive]=useState(''), [error,setError]=useState('')
  const key='hub.conversation.'+project.project_id
  useEffect(()=>{
    api('/projects/'+project.project_id+'/conversations').then(data=>{
      setItems(data)
      setActive(data.find(i=>i.conversation_id===localStorage.getItem(key))?.conversation_id || data[0]?.conversation_id || '')
    }).catch(err=>setError(err.message))
  },[key])
  function select(id){setActive(id);localStorage.setItem(key,id)}
  async function create(title) {
    const row=await api('/conversations',{title,project_id:project.project_id})
    setItems(prev=>[...(prev||[]),row]);select(row.conversation_id)
  }
  const selected=items?.find(i=>i.conversation_id===active)
  return <div className="workspace"><aside><h2>{project.name}</h2><h3>Conversations</h3>
    <nav aria-label="Conversations">{items?.map(i=><button className={active===i.conversation_id?'selected':'navlink'} key={i.conversation_id} onClick={()=>select(i.conversation_id)}>{i.title}</button>)}</nav>
    <NewItem label="New conversation" onCreate={create}/><ErrorNote message={error}/></aside>
    {selected ? <Thread key={selected.conversation_id} item={selected}/> : <section className="thread empty"><h1>{items===null?'Loading conversations…':'No conversations yet'}</h1><p>Create a conversation to save the first question in this project.</p></section>}</div>
}

function Workspace({logout}) {
  const [items,setItems]=useState(null), [active,setActive]=useState(''), [error,setError]=useState('')
  useEffect(()=>{
    api('/projects').then(data=>{setItems(data);setActive(data.find(i=>i.project_id===localStorage.getItem('hub.project'))?.project_id || data[0]?.project_id || '')}).catch(e=>setError(e.message))
  },[])
  function select(id){setActive(id);localStorage.setItem('hub.project',id)}
  async function create(name) {
    const row=await api('/projects',{name});setItems(prev=>[...(prev||[]),row]);select(row.project_id)
  }
  const project=items?.find(p=>p.project_id===active)
  return <><header className="top"><Brand/><button className="quiet" onClick={()=>api('/auth/logout',{}).then(logout).catch(err=>setError(err.message))}>Sign out</button></header>
    <main className="shell"><div className="projects"><label>Project<select value={active} onChange={e=>select(e.target.value)} disabled={!items?.length}>
      {!items?.length && <option value="">Select a project</option>}{items?.map(p=><option key={p.project_id} value={p.project_id}>{p.name}</option>)}</select></label>
      <NewItem label="New project" onCreate={create}/></div><ErrorNote message={error}/>
      {project ? <Conversations key={active} project={project}/> : <div className="empty welcome"><h1>{items===null?'Loading workspace…':'Your projects'}</h1><p>Create a project to keep its questions and original responses together.</p></div>}
    </main></>
}

function App() {
  const [auth,setAuth]=useState(null), [error,setError]=useState('')
  useEffect(()=>{
    const end=()=>setAuth(false)
    window.addEventListener('session-ended',end)
    fetch('/v1/auth/session').then(r=>{if(r.ok || r.status===401)setAuth(r.ok);else throw new Error('Workspace unavailable')}).catch(err=>setError(err.message))
    return ()=>window.removeEventListener('session-ended',end)
  },[])
  if(error)return <main className="entry"><ErrorNote message={error}/></main>
  if(auth===null)return <main className="entry"><Brand/></main>
  return auth?<Workspace logout={()=>setAuth(false)}/>:<Login onLogin={()=>setAuth(true)}/>
}
createRoot(document.getElementById('root')).render(<App/>)
