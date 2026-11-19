import {ArrowRight, Flower2} from 'lucide-react'
import {useEffect, useRef, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {CasePage} from './case'
import {caseInfo, demo, readWorkspace, request, sameConditions, saveWorkspace} from './model'
import type {Campaign, Conditions, Plan} from './model'
import {Alert, CooperationView, ReviewView, SelectionView} from './workspace'
import './style.css'

const workspaceTabs = [{route: 'workspace', label: '选人'}, {route: 'brief', label: '合作内容'}, {route: 'review', label: '模拟复盘'}] as const
type Route = 'case' | typeof workspaceTabs[number]['route']

function readRoute(): Route {
  const hash = window.location.hash.slice(1)
  return workspaceTabs.find(tab => tab.route === hash)?.route ?? 'case'
}

function App() {
  const [route, setRoute] = useState(readRoute)
  const [state, setState] = useState(readWorkspace)
  const [busy, setBusy] = useState<'plan' | 'campaign' | null>(null)
  const [aiAvailable, setAiAvailable] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef(false)

  useEffect(() => {
    const onHashChange = () => setRoute(readRoute())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    const id = window.location.hash.slice(1)
    const anchor = route === 'case' && document.getElementById(id)
    if (anchor) anchor.scrollIntoView()
    else window.scrollTo({top: 0, behavior: 'instant'})
  }, [route])

  useEffect(() => saveWorkspace(state), [state])

  useEffect(() => {
    if (route === 'case') return
    let active = true
    request<{ai_available: boolean}>('/api/status').then(result => {
      if (active) setAiAvailable(result.ai_available === true)
    }).catch(() => {if (active) setAiAvailable(false)})
    return () => {active = false}
  }, [route])

  async function apply(conditions: Conditions) {
    if (inFlight.current) return false
    setError('')
    if (sameConditions(conditions, state.plan.conditions)) return true
    inFlight.current = true
    setBusy('plan')
    try {
      const plan = sameConditions(conditions, demo.conditions) ? demo.plan : await request<Plan>('/api/plan', conditions)
      setState(current => ({...current, plan, campaign: null}))
      return true
    } catch (error) {
      setError((error as Error).message)
      return false
    } finally {
      inFlight.current = false
      setBusy(null)
    }
  }

  function reset() {
    setError('')
    setState(current => ({...current, plan: demo.plan, campaign: null}))
  }

  async function confirm() {
    if (inFlight.current || !state.plan.selected.length) return
    setError('')
    if (state.campaign) {
      window.location.hash = 'brief'
      return
    }
    inFlight.current = true
    setBusy('campaign')
    try {
      const campaign = sameConditions(state.plan.conditions, demo.conditions)
        ? demo.campaign : await request<Campaign>('/api/campaign', state.plan.conditions)
      setState(current => ({...current, plan: campaign.plan, campaign}))
      if (readRoute() === 'workspace') window.location.hash = 'brief'
    } catch (error) {
      setError((error as Error).message)
    } finally {
      inFlight.current = false
      setBusy(null)
    }
  }

  return <>
    <a href="#main-content" className="skip-link" onClick={event => {event.preventDefault(); document.getElementById('main-content')?.focus()}}>跳至主要内容</a>
    <header className="site-header"><div className="shell header-content">
      <a className="brand" href="#case"><span className="brand-mark"><Flower2 size={22} strokeWidth={1.8} /></span><span>小红书达人投放助手</span></a>
      <nav className="site-nav" aria-label="站点导航"><a className={route === 'case' ? 'active' : ''} href="#case" aria-current={route === 'case' ? 'page' : undefined}>完整案例</a><a className={route !== 'case' ? 'active' : ''} href="#workspace" aria-current={route !== 'case' ? 'page' : undefined}>投放工作台</a></nav>
    </div></header>
    {route === 'case' ? <CasePage /> : <main id="main-content" className="shell workspace-shell" tabIndex={-1}>
      <div className="workspace-heading"><p className="eyebrow">{caseInfo.brand_name} · {caseInfo.preferred_platform} · 演示案例</p><h1>{caseInfo.product_name}</h1></div>
      <nav className="workspace-nav" aria-label="投放步骤">{workspaceTabs.map(tab => {
        const locked = tab.route !== 'workspace' && !state.campaign
        return locked ? <span key={tab.route} aria-disabled="true">{tab.label}</span> : <a className={route === tab.route ? 'active' : ''} key={tab.route} href={`#${tab.route}`} aria-current={route === tab.route ? 'step' : undefined}>{tab.label}</a>
      })}</nav>
      {error && <Alert message={error} />}
      {busy === 'campaign' && <p className="mini-note" role="status">正在确认名单…</p>}
      {route === 'workspace' && <SelectionView state={state} apply={apply} reset={reset} confirm={() => void confirm()} busy={Boolean(busy)} aiAvailable={aiAvailable} />}
      {route !== 'workspace' && !state.campaign && <div className="panel locked"><h2>请先确认投放名单</h2><a href="#workspace" className="button primary">进入选人 <ArrowRight size={16} /></a></div>}
      {route === 'brief' && state.campaign && <CooperationView campaign={state.campaign} savedBriefs={state.briefs} aiAvailable={aiAvailable} onSave={(id, brief) => setState(current => ({...current, briefs: {...current.briefs, [id]: brief}}))} />}
      {route === 'review' && state.campaign && <ReviewView campaign={state.campaign} candidates={state.candidates} aiAvailable={aiAvailable} addCandidate={row => setState(current => current.candidates.some(candidate => candidate.creator_id === row.creator_id) ? current : ({...current, candidates: [...current.candidates, row]}))} removeCandidate={id => setState(current => ({...current, candidates: current.candidates.filter(row => row.creator_id !== id)}))} />}
    </main>}
    <footer className="site-footer"><div className="shell between"><span><Flower2 size={16} /> 小红书达人投放助手</span><span>达人和投放数据均为模拟样例</span></div></footer>
  </>
}

createRoot(document.getElementById('root')!).render(<App />)
