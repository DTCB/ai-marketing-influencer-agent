import {ArrowDown, ArrowDownRight, ArrowRight, Check, ChevronRight, CircleDollarSign, ClipboardList, FileText, Flower2, LineChart} from 'lucide-react'
import serumImage from '../assets/serum.webp'
import {caseInfo, count, demo, money, percent, views} from './model'
import type {Conditions, Plan, Review} from './model'

export function PlanComparison({plan}: {plan: Plan}) {
  if (!plan.selected.length || !plan.removed.length || !plan.added.length) return null
  const difference = plan.comparison_quote - plan.selected_quote
  const oneSwap = plan.removed.length === 1 && plan.added.length === 1
  return <div className="comparison">
    <div className="eyebrow"><ArrowDownRight size={16} /> {difference >= 0 ? `报价节省 ${money(difference)}` : `报价增加 ${money(-difference)}`}</div>
    <p><strong>{plan.removed.map(creator => creator.creator_name).join('、')}</strong> 换为 <strong>{plan.added.map(creator => creator.creator_name).join('、')}</strong>，名单报价由 {money(plan.comparison_quote)} 调整至 {money(plan.selected_quote)}。</p>
    {oneSwap && <small>替换席位的样例历史均播由 {views(plan.removed[0].avg_views)}调整为 {views(plan.added[0].avg_views)}。</small>}
  </div>
}

export function Metric({label, value, detail}: {label: string; value: string; detail?: string}) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}

export function GoalMetrics({review, conditions}: {review: Review; conditions: Conditions}) {
  return <div className="metric-group goal-group">
    <Metric label="收藏率" value={percent(review.save_rate.actual)} detail={`目标 ≥ ${percent(conditions.save_rate_target)} · ${review.save_rate.status}`} />
    <Metric label="单次转化成本" value={money(review.cpa.actual)} detail={`目标 ≤ ${money(conditions.cpa_target)} · ${review.cpa.status}`} />
  </div>
}

function CaseNavigation() {
  return <nav className="case-index" aria-label="案例章节">
    <a href="#selection-result"><CircleDollarSign size={19} /><span>预算内选人</span><ChevronRight size={16} /></a>
    <a href="#cooperation-result"><FileText size={19} /><span>达人合作 Brief</span><ChevronRight size={16} /></a>
    <a href="#review-result"><LineChart size={19} /><span>模拟投放复盘</span><ChevronRight size={16} /></a>
  </nav>
}

export function CasePage() {
  const {plan, campaign, conditions} = demo
  const caseCreators = plan.selected.filter(creator => ['C001', 'C002'].includes(creator.creator_id))
  const {review} = campaign
  return <main id="main-content" className="shell case-shell" tabIndex={-1}>
    <section className="hero" aria-labelledby="case-title">
      <div className="hero-copy">
        <div className="eyebrow hero-eyebrow"><Flower2 size={15} /> 清颜实验室 <span className="eyebrow-dot" /> 小红书种草案例</div>
        <h1 id="case-title">小红书达人<br className="hero-break" />投放工作台</h1>
        <p>{caseInfo.product_name}如何在 {money(conditions.budget_total)} 预算内选定 {conditions.expected_creator_count} 位达人？从推荐依据、合作 Brief 到模拟投后复盘，体验完整投放流程。</p>
        <div className="actions hero-actions">
          <a className="button primary" href="#workspace">试着调整方案 <ArrowRight size={17} /></a>
          <a className="button quiet" href="#selection-result">查看完整案例 <ArrowDown size={16} /></a>
        </div>
      </div>
      <div className="hero-image">
        <img src={serumImage} alt="摆放在浅色石台上的玫瑰色修护精华滴管瓶" width={320} height={320} fetchPriority="high" />
        <div className="product-caption"><div><strong>{caseInfo.product_name}</strong><span>护肤新品投放 · 演示案例</span></div><Flower2 size={24} strokeWidth={1.3} /></div>
      </div>
    </section>

    <CaseNavigation />

    <section className="case-section" id="selection-result" aria-labelledby="selection-title">
      <div className="section-title"><div className="section-icon"><CircleDollarSign size={23} /></div><h2 id="selection-title">在 {money(conditions.budget_total)} 内选 {plan.selected.length} 位达人</h2></div>
      <div className="panel case-selection">
        <div className="metric-group outcome">
          <Metric label="按综合分直接选" value={money(plan.baseline_quote)} detail="原始名单" />
          <Metric label="预算内名单" value={money(plan.selected_quote)} detail={`预算剩余 ${money(conditions.budget_total - plan.selected_quote)}`} />
          <Metric label="合作人数" value={`${plan.selected.length} 位`} />
        </div>
        <PlanComparison plan={plan} />
        <ul className="roster-tags" aria-label="预算内达人名单">{plan.selected.map(creator => <li key={creator.creator_id}><Check size={14} /> {creator.creator_name}</li>)}</ul>
      </div>
    </section>

    <section className="case-section" id="cooperation-result" aria-labelledby="cooperation-title">
      <div className="section-title"><div className="section-icon"><ClipboardList size={23} /></div><h2 id="cooperation-title">按达人风格写合作 Brief</h2></div>
      <div className="case-briefs">{caseCreators.map(creator => {
        const brief = campaign.briefs[creator.creator_id]
        return <article className="panel case-brief" key={creator.creator_id}>
          <span className="pill">{creator.content_style}</span><h3>{brief.title}</h3><div className="muted creator-byline">{creator.creator_name}</div>
          <p>{brief.delivery}</p>
          <details><summary>查看审稿要点</summary><p>{brief.review_notes}</p></details>
        </article>
      })}</div>
    </section>

    <section className="case-section" id="review-result" aria-labelledby="review-title">
      <div className="section-title"><div className="section-icon"><LineChart size={23} /></div><h2 id="review-title">用模拟数据判断是否复投</h2></div>
      <div className="panel case-review">
        <div className="between"><h3>投放目标</h3><span className="pill">数据已回收 {review.received_count}/{plan.selected.length} 位</span></div>
        <GoalMetrics review={review} conditions={conditions} />
        {review.next_candidate && <div className="comparison"><strong>复投候选 · {review.next_candidate.creator_name}</strong><p>模拟单次转化成本 {money(review.next_candidate.cpa)}，在具备可用转化数据的达人中最低。</p></div>}
        <p className="muted review-footnote">共记录 {count(review.summary.conversions)} 次模拟转化。结论仅基于已回收的演示数据。</p>
      </div>
    </section>
  </main>
}
