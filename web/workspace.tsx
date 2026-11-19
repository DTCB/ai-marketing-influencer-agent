import {ArrowRight, Check, ChevronRight, Clipboard, ClipboardList, Download, FileText, Plus, RotateCcw, Sparkles, X} from 'lucide-react'
import {useState} from 'react'
import type {FormEvent, ReactNode} from 'react'
import {GoalMetrics, Metric, PlanComparison} from './case'
import {caseInfo, count, demo, money, percent, request, sameConditions, tags, views} from './model'
import type {AiResponse, AiTask, BriefCard, Campaign, Conditions, ParsedBrief, Plan, ReviewRow, WorkspaceState} from './model'

const asPercent = (value: number) => Number((value * 100).toFixed(8))

function Field({label, children}: {label: string; children: ReactNode}) {
  return <label className="field"><span>{label}</span>{children}</label>
}

export function Alert({message}: {message: string}) {
  return <p className="alert" role="status">{message}</p>
}

type ApplyConditions = (conditions: Conditions) => Promise<boolean>

function BriefParser({conditions, apply, busy, aiAvailable}: {conditions: Conditions; apply: ApplyConditions; busy: boolean; aiAvailable: boolean}) {
  const [sentence, setSentence] = useState('')
  const [preview, setPreview] = useState<ParsedBrief | null>(null)
  const [excludeCreator, setExcludeCreator] = useState(false)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const gentle = demo.creators.find(creator => creator.creator_id === 'C004')
  const sharp = demo.creators.find(creator => creator.creator_id === 'C013')
  const alreadyExcluded = Boolean(sharp && conditions.excluded_creator_ids.includes(sharp.creator_id))

  function showPreview(parsed: ParsedBrief, notice: string) {
    setPreview({ ...parsed, budget: parsed.budget ?? conditions.budget_total, count: parsed.count ?? conditions.expected_creator_count })
    setExcludeCreator(false)
    setMessage(notice)
  }

  async function parse(event: FormEvent) {
    event.preventDefault()
    if (!aiAvailable || pending || !sentence.trim()) return
    setPending(true)
    try {
      const result = await request<AiResponse>('/api/ai', {task: 'brief', sentence, conditions})
      showPreview(result.parsed ?? {budget: null, count: null, tone: null, uncertainties: []},
        result.message ?? (result.mode === 'live' ? '已解析，请核对预览后应用。' : '可手动调整预览，或载入内置示例。'))
    } catch (error) {
      showPreview({budget: null, count: null, tone: null, uncertainties: []}, (error as Error).message)
    } finally {
      setPending(false)
    }
  }

  async function applyPreview(event: FormEvent) {
    event.preventDefault()
    if (preview?.budget == null || preview.count == null) return
    const excluded_creator_ids = excludeCreator && preview.tone === 'gentle' && sharp && !alreadyExcluded
      ? [...conditions.excluded_creator_ids, sharp.creator_id] : conditions.excluded_creator_ids
    const applied = await apply({...conditions, budget_total: preview.budget, expected_creator_count: preview.count, excluded_creator_ids})
    if (applied) {
      setExcludeCreator(false)
      setMessage('已应用到工作台。')
    }
  }

  return <details className="parser"><summary><Sparkles size={16} /> 用一句话调整方案 <ChevronRight size={15} className="disclosure-chevron" /></summary>
    <div className="detail-body">
      <form onSubmit={parse} className="form-stack">
        <Field label="一句话 Brief"><textarea placeholder={demo.brief_example.sentence} value={sentence} onChange={event => setSentence(event.target.value)} rows={2} maxLength={1200} /></Field>
        {!aiAvailable && <p className="mini-note">当前可载入内置示例或手动编辑。</p>}
        <div className="actions">
          {aiAvailable && <button className="button secondary small" disabled={pending || !sentence.trim()} type="submit">{pending ? '正在解析…' : '解析 Brief'}</button>}
          <button className="button secondary small" disabled={pending} type="button" onClick={() => {
            setSentence(demo.brief_example.sentence)
            showPreview(demo.brief_example, '已载入示例，请核对后应用。')
          }}>载入示例</button>
          <button className="button quiet small" disabled={pending} type="button" onClick={() => showPreview({budget: null, count: null, tone: null, uncertainties: []}, '可以直接编辑下方条件。')}>手动编辑</button>
        </div>
      </form>
      {message && <Alert message={message} />}
      {preview && <form className="form-stack brief-preview" onSubmit={applyPreview}>
        {preview.uncertainties.map(note => <p className="mini-note" key={note}>待确认 · {note}</p>)}
        <Field label="预览预算（元）"><input type="number" required min={0} step={1} value={preview.budget ?? ''} onChange={event => setPreview({...preview, budget: event.target.value ? event.target.valueAsNumber : null})} /></Field>
        <Field label="预览合作人数"><input type="number" required min={1} step={1} value={preview.count ?? ''} onChange={event => setPreview({...preview, count: event.target.value ? event.target.valueAsNumber : null})} /></Field>
        <Field label="预览内容调性"><select value={preview.tone ?? ''} onChange={event => {setPreview({...preview, tone: event.target.value === 'gentle' ? 'gentle' : null}); setExcludeCreator(false)}}><option value="">未指定</option><option value="gentle">偏好温和表达</option></select></Field>
        {preview.tone === 'gentle' && <div className="tone-evidence">
          {gentle && <p><strong>{gentle.creator_name}</strong> · {gentle.risk_note}</p>}
          {sharp && <p><strong>{sharp.creator_name}</strong> · {sharp.risk_note}</p>}
          {sharp && (alreadyExcluded ? <p className="muted">{sharp.creator_name}已排除</p> : <label className="checkbox"><input type="checkbox" checked={excludeCreator} onChange={event => setExcludeCreator(event.target.checked)} /> 本轮暂不合作 · {sharp.creator_name}</label>)}
        </div>}
        <button type="submit" className="button primary small" disabled={busy}>应用并重算</button>
      </form>}
    </div>
  </details>
}

function ConditionsForm({plan, apply, reset, confirm, busy, aiAvailable, confirmed}: {plan: Plan; apply: ApplyConditions; reset: () => void; confirm: () => void; busy: boolean; aiAvailable: boolean; confirmed: boolean}) {
  const {conditions} = plan
  const [draft, setDraft] = useState(conditions)
  const [saveRateDraft, setSaveRateDraft] = useState(asPercent(conditions.save_rate_target))
  const hasChanges = !sameConditions({...draft, save_rate_target: saveRateDraft / 100}, conditions)
  const input = (field: 'budget_total' | 'expected_creator_count' | 'cpa_target', value: number) => setDraft({...draft, [field]: value})

  return <aside className="panel conditions-panel" aria-labelledby="conditions-title">
    <div className="section-title compact"><div className="section-icon"><ClipboardList size={20} /></div><h3 id="conditions-title">投放 Brief</h3></div>
    <p className="muted small-text">目标人群</p><div className="tag-list">{tags('target_audience').map(tag => <span className="pill" key={tag}>{tag}</span>)}</div>
    <BriefParser conditions={conditions} apply={apply} busy={busy} aiAvailable={aiAvailable} />
    <form className="form-stack" onSubmit={event => {event.preventDefault(); void apply({...draft, save_rate_target: saveRateDraft / 100})}}>
      <div className="input-group">
        <Field label="总预算（元）"><input type="number" required min={0} step={1} value={Number.isFinite(draft.budget_total) ? draft.budget_total : ''} onChange={event => input('budget_total', event.target.valueAsNumber)} /></Field>
        <Field label="合作人数"><input type="number" required min={1} step={1} value={Number.isFinite(draft.expected_creator_count) ? draft.expected_creator_count : ''} onChange={event => input('expected_creator_count', event.target.valueAsNumber)} /></Field>
      </div>
      <details><summary>设定复盘目标 <ChevronRight size={15} className="disclosure-chevron" /></summary><div className="detail-body form-stack">
        <p className="mini-note">默认值为案例演示目标，确认名单时一并保存。</p>
        <Field label="收藏率目标（%）"><input type="number" required min={0} max={100} step={0.01} value={Number.isFinite(saveRateDraft) ? saveRateDraft : ''} onChange={event => setSaveRateDraft(event.target.valueAsNumber)} /></Field>
        <Field label="单次转化成本上限（元）"><input type="number" required min={0} step={0.01} value={Number.isFinite(draft.cpa_target) ? draft.cpa_target : ''} onChange={event => input('cpa_target', event.target.valueAsNumber)} /></Field>
      </div></details>
      <div className="actions"><button className="button secondary" disabled={busy} type="submit">{busy ? '计算中…' : '重新计算'}</button><button className="button quiet" disabled={busy} type="button" onClick={() => {setDraft(demo.conditions); setSaveRateDraft(asPercent(demo.conditions.save_rate_target)); reset()}}><RotateCcw size={15} /> 恢复默认</button></div>
    </form>
    <details><summary>查看完整投放需求 <ChevronRight size={15} className="disclosure-chevron" /></summary><div className="detail-body"><p>品牌卖点 · {tags('key_selling_points').join('、')}</p><p>审稿规避 · {tags('avoid_categories').join('、')}</p></div></details>
    {conditions.excluded_creator_ids.length > 0 && <div className="excluded-list"><p className="muted small-text">本轮暂不合作</p>{conditions.excluded_creator_ids.map(id => {
      const creator = demo.creators.find(item => item.creator_id === id)
      return <button type="button" className="button quiet small" disabled={busy} key={id} onClick={() => void apply({...conditions, excluded_creator_ids: conditions.excluded_creator_ids.filter(current => current !== id)})}><RotateCcw size={14} /> 恢复 {creator?.creator_name ?? id}</button>
    })}</div>}
    {hasChanges && <p className="mini-note">投放条件有改动，请先重新计算。</p>}
    <button type="button" className="button primary full" disabled={busy || !plan.selected.length || hasChanges} onClick={confirm}>{confirmed ? '查看已确认名单' : '确认名单'} <ArrowRight size={17} /></button>
  </aside>
}

export function SelectionView({state, apply, reset, confirm, busy, aiAvailable}: {state: WorkspaceState; apply: ApplyConditions; reset: () => void; confirm: () => void; busy: boolean; aiAvailable: boolean}) {
  const {plan} = state
  const {conditions} = plan
  return <div className="workspace-grid">
    <div className="roster-column">
      <div className="panel budget-panel">
        <h2>{money(conditions.budget_total)} 怎么选 {conditions.expected_creator_count} 位达人？</h2>
        {plan.selected.length ? <>
          <div className="metric-group outcome"><Metric label="方案报价" value={money(plan.selected_quote)} /><Metric label="推荐人数" value={`${plan.selected.length} 位`} /><Metric label="预算剩余" value={money(conditions.budget_total - plan.selected_quote)} /></div>
          {conditions.budget_total > 0 && <><progress value={plan.selected_quote} max={conditions.budget_total} aria-label="预算已使用金额" /><div className="between muted small-text"><span>{percent(plan.selected_quote / conditions.budget_total)} 已使用</span><span>预算上限 {money(conditions.budget_total)}</span></div></>}
        </> : <div className="alert" role="status">{plan.budget_gap !== null ? <><strong>预算缺口 {money(plan.budget_gap)}</strong><p>选择 {conditions.expected_creator_count} 位达人至少需要 {money(plan.minimum_quote)}。可提高预算或减少人数。</p></> : <><strong>候选达人不足</strong><p>当前有 {plan.candidate_count} 位可选达人，请减少人数或恢复排除的达人。</p></>}</div>}
      </div>
      <PlanComparison plan={plan} />
      {plan.selected.length > 0 && <section className="panel roster-list" aria-labelledby="roster-title"><div className="between section-title"><h3 id="roster-title">推荐达人名单</h3><span className="pill">{plan.selected.length} 位达人</span></div>
        {plan.selected.map(creator => <details key={creator.creator_id} className="creator-item"><summary><span className="creator-avatar" aria-hidden="true">{creator.creator_name.slice(0, 1)}</span><span className="creator-heading"><strong>{creator.creator_name}</strong><small>{creator.content_style}</small></span><strong>{money(creator.base_quote)}</strong><ChevronRight size={16} className="disclosure-chevron" /></summary>
          <div className="detail-body"><p>{creator.evidence || '样例创作者'}</p><p>代表作 · 《{creator.sample_post_title}》</p><p className="muted">均播 {views(creator.avg_views)}{creator.total_score !== undefined && ` · 综合分 ${creator.total_score.toFixed(2)}`}</p>{creator.risk_note && <p className="mini-note">档案备注 · {creator.risk_note}</p>}
            <button className="button secondary small" disabled={busy} type="button" onClick={() => void apply({...conditions, excluded_creator_ids: [...conditions.excluded_creator_ids, creator.creator_id]})}>暂不合作</button></div>
        </details>)}
      </section>}
      {plan.baseline.length > 0 && <details className="panel baseline"><summary>查看按分数排序的名单 · {money(plan.baseline_quote)} <ChevronRight className="disclosure-chevron" size={16} /></summary><div className="detail-body">{plan.baseline.map(creator => <div className="between row" key={creator.creator_id}><span>{creator.creator_name}</span><span>{money(creator.base_quote)} · {creator.total_score?.toFixed(2)} 分</span></div>)}</div></details>}
    </div>
    <ConditionsForm key={JSON.stringify(conditions)} plan={plan} apply={apply} reset={reset} confirm={confirm} busy={busy} aiAvailable={aiAvailable} confirmed={Boolean(state.campaign)} />
  </div>
}

function AIResult({task, conditions, creatorId, label, fallback, enabled}: {task: AiTask; conditions: Conditions; creatorId?: string; label: string; fallback: string; enabled: boolean}) {
  const [result, setResult] = useState<AiResponse | null>(null)
  const [pending, setPending] = useState(false)

  async function generate() {
    setPending(true)
    try {
      setResult(await request<AiResponse>('/api/ai', {task, conditions, creator_id: creatorId}))
    } catch (error) {
      setResult({mode: 'demo', message: (error as Error).message})
    } finally {
      setPending(false)
    }
  }

  return <div className="ai-result">
    {result?.mode === 'live' && <span className="pill"><Sparkles size={13} /> AI 生成 · 基于演示数据</span>}
    <p>{result?.content || fallback}</p>
    {result?.message && <Alert message={result.message} />}
    {enabled && <button className="button secondary small" onClick={() => void generate()} disabled={pending} type="button"><Sparkles size={15} /> {pending ? '正在生成…' : label}</button>}
  </div>
}

export function CooperationView({campaign, savedBriefs, onSave, aiAvailable}: {campaign: Campaign; savedBriefs: WorkspaceState['briefs']; onSave: (id: string, brief: BriefCard) => void; aiAvailable: boolean}) {
  const [selected, setSelected] = useState(campaign.plan.selected[0].creator_id)
  const current = campaign.plan.selected.find(creator => creator.creator_id === selected) ?? campaign.plan.selected[0]
  const brief = savedBriefs[current.creator_id] ?? campaign.briefs[current.creator_id]
  const {conditions} = campaign.plan
  return <div className="workspace-grid">
    <section className="panel brief-panel" aria-labelledby="cooperation-workspace-title">
      <div className="section-title"><div className="section-icon"><FileText size={21} /></div><h2 id="cooperation-workspace-title">达人合作内容</h2></div>
      <div className="between section-subtitle"><h3>{current.creator_name}</h3><span className="pill">{current.content_style} · {money(current.base_quote)}</span></div>
      <div className="comparison"><strong>入选证据</strong><p>样例代表作《{current.sample_post_title}》</p><AIResult key={current.creator_id} task="recommendation" conditions={conditions} creatorId={current.creator_id} label="生成 AI 推荐解释" fallback={current.evidence ?? ''} enabled={aiAvailable} /></div>
      <BriefEditor key={current.creator_id} name={current.creator_name} brief={brief} onSave={value => onSave(current.creator_id, value)} />
      <a className="button primary" href="#review">查看模拟复盘 <ArrowRight size={16} /></a>
    </section>
    <aside className="panel conditions-panel">
      <h3>已确认名单</h3><p className="muted">{campaign.plan.selected.length} 位 · 方案报价 {money(campaign.plan.selected_quote)}</p>
      <div className="creator-menu" aria-label="选择合作达人">{campaign.plan.selected.map(creator => <button type="button" className={creator.creator_id === current.creator_id ? 'active' : ''} key={creator.creator_id} onClick={() => setSelected(creator.creator_id)} aria-pressed={creator.creator_id === current.creator_id}>{creator.creator_name}<ChevronRight size={16} /></button>)}</div>
    </aside>
  </div>
}

function BriefEditor({name, brief, onSave}: {name: string; brief: BriefCard; onSave: (value: BriefCard) => void}) {
  const [draft, setDraft] = useState(brief)
  const [message, setMessage] = useState('')
  const changed = draft.title !== brief.title || draft.delivery !== brief.delivery || draft.review_notes !== brief.review_notes
  const briefText = ['达人合作 Brief', `${caseInfo.brand_name} · ${caseInfo.product_name}`, `${name} · ${caseInfo.preferred_platform} · ${caseInfo.campaign_goal}`, '', `选题\n${brief.title}`, `\n交付要求\n${brief.delivery}`, `\n审稿要点\n${brief.review_notes}`].join('\n')

  async function copy() {
    try { await navigator.clipboard.writeText(briefText); setMessage('已复制 Brief。') }
    catch { setMessage('浏览器未授予剪贴板权限，可选择全文复制或下载。') }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([briefText], {type: 'text/plain;charset=utf-8'}))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${name}-合作Brief.txt`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return <div className="brief-editor">
    <form className="form-stack" onSubmit={event => {event.preventDefault(); onSave(draft); setMessage('Brief 已保存。')}}>
      <Field label="选题"><input type="text" value={draft.title} onChange={event => setDraft({...draft, title: event.target.value})} /></Field>
      <Field label="交付要求"><textarea rows={3} value={draft.delivery} onChange={event => setDraft({...draft, delivery: event.target.value})} /></Field>
      <Field label="审稿要点"><textarea rows={3} value={draft.review_notes} onChange={event => setDraft({...draft, review_notes: event.target.value})} /></Field>
      <button className="button secondary" type="submit" disabled={!changed}><Check size={16} /> 保存 Brief</button>
    </form>
    <details><summary>查看 Brief 全文 <ChevronRight size={15} className="disclosure-chevron" /></summary><pre className="brief-export">{briefText}</pre></details>
    <div className="actions"><button className="button quiet" type="button" disabled={changed} onClick={() => void copy()}><Clipboard size={16} /> 复制 Brief</button><button className="button secondary" type="button" disabled={changed} onClick={download}><Download size={16} /> 下载 Brief</button></div>
    {changed && <p className="mini-note">请保存修改后再复制或下载。</p>}
    {message && <p className="mini-note" role="status">{message}</p>}
  </div>
}

export function ReviewView({campaign, candidates, addCandidate, removeCandidate, aiAvailable}: {campaign: Campaign; candidates: ReviewRow[]; addCandidate: (row: ReviewRow) => void; removeCandidate: (id: string) => void; aiAvailable: boolean}) {
  const {plan, review} = campaign
  const {conditions} = plan
  const {summary, next_candidate: next} = review
  const pending = review.rows.filter(row => !row.received)
  const fallback = next ? `${next.creator_name}的模拟单次转化成本为 ${money(next.cpa)}，在具备可用数据的达人中最低，可加入下一轮候选。` : '已回收数据暂无法计算单次转化成本，先核对转化口径和数据回收进度。'

  return <section className="panel review-panel" aria-labelledby="review-workspace-title">
    <div className="between section-title"><h2 id="review-workspace-title">模拟投后复盘</h2><span className="pill">数据已回收 {review.received_count}/{plan.selected.length} 位</span></div>
    <div className="metric-group review-summary"><Metric label="已回收花费" value={review.received_count ? money(summary.spend) : '—'} /><Metric label="已回收归因收入" value={review.received_count ? money(summary.revenue) : '—'} /><Metric label="收入 ÷ 花费" value={summary.spend ? `${summary.roi.toFixed(2)} 倍` : '—'} /></div>
    <h3>投放目标</h3><GoalMetrics review={review} conditions={conditions} />
    <div className="table-wrap"><table><thead><tr><th scope="col">达人</th><th scope="col">回收状态</th><th scope="col">计划报价</th><th scope="col">模拟花费</th><th scope="col">转化数</th><th scope="col">单次转化成本</th></tr></thead><tbody>{review.rows.map(row => <tr key={row.creator_id}><th scope="row">{row.creator_name}</th><td><span className={row.received ? 'pill received' : 'pill'}>{row.received ? '已回收' : '待回收'}</span></td><td>{money(row.base_quote)}</td><td>{money(row.spend)}</td><td>{count(row.conversions)}</td><td>{money(row.cpa)}</td></tr>)}</tbody></table></div>
    {pending.length > 0 && <Alert message={`待回收达人：${pending.map(row => row.creator_name).join('、')}。补齐记录后再评估复投机会。`} />}
    {review.received_count > 0 && <p className="muted review-footnote">已回收范围 · 曝光 {count(summary.impressions)} · 点击 {count(summary.clicks)} · 点击率 {summary.impressions ? percent(summary.ctr) : '—'} · 转化率 {summary.clicks ? percent(summary.cvr) : '—'}</p>}
    <div className="comparison next-round"><h3>下一轮建议</h3><AIResult task="review" conditions={conditions} label="生成 AI 复盘摘要" fallback={fallback} enabled={aiAvailable && review.received_count > 0} />
    {next && !candidates.some(candidate => candidate.creator_id === next.creator_id) && <button type="button" className="button secondary small" onClick={() => addCandidate(next)}><Plus size={16} /> 将{next.creator_name}加入下一轮候选</button>}
    </div>
    {candidates.length > 0 && <div className="saved-candidates"><h3>下一轮复投候选</h3>{candidates.map(candidate => <div className="between row" key={candidate.creator_id}><span><strong>{candidate.creator_name}</strong> · 单次转化成本 {money(candidate.cpa)}</span><button type="button" className="button quiet small" onClick={() => removeCandidate(candidate.creator_id)} aria-label={`移除 ${candidate.creator_name}`}><X size={16} /> 移除</button></div>)}</div>}
  </section>
}
