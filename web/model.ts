import snapshot from './demo.json'

export interface Conditions {
  budget_total: number
  expected_creator_count: number
  excluded_creator_ids: string[]
  save_rate_target: number
  cpa_target: number
}

export interface Creator {
  creator_id: string
  creator_name: string
  content_style: string
  base_quote: number
  avg_views: number
  risk_note: string | null
  sample_post_title: string
  total_score?: number
  evidence?: string
}

export interface Plan {
  conditions: Conditions
  baseline: Creator[]
  selected: Creator[]
  candidate_count: number
  minimum_quote: number | null
  baseline_quote: number
  selected_quote: number
  budget_gap: number | null
  removed: Creator[]
  added: Creator[]
  comparison_quote: number
  comparison_score: number
  selected_score: number
}

export interface BriefCard {
  title: string
  delivery: string
  review_notes: string
}

export interface ReviewRow {
  creator_id: string
  creator_name: string
  received: boolean
  spend: number | null
  revenue: number | null
  conversions: number | null
  cpa: number | null
  base_quote: number
}

export interface Goal {
  actual: number | null
  status: string
}

export interface Review {
  rows: ReviewRow[]
  received_count: number
  summary: Record<'spend' | 'impressions' | 'clicks' | 'conversions' | 'revenue' | 'ctr' | 'cvr' | 'roi', number>
  save_rate: Goal
  cpa: Goal
  next_candidate: ReviewRow | null
}

export interface Campaign {
  plan: Plan
  briefs: Record<string, BriefCard>
  review: Review
}

export interface ParsedBrief {
  budget: number | null
  count: number | null
  tone: 'gentle' | null
  uncertainties: string[]
}

export type AiTask = 'brief' | 'recommendation' | 'review'

export interface AiResponse {
  mode: 'live' | 'demo'
  content?: string
  parsed?: ParsedBrief
  message?: string
}

interface Snapshot {
  case: Record<string, string | number>
  conditions: Conditions
  creators: Creator[]
  plan: Plan
  campaign: Campaign
  brief_example: ParsedBrief & {sentence: string}
}

export const demo = snapshot as Snapshot
export const caseInfo = demo.case

export interface WorkspaceState {
  plan: Plan
  campaign: Campaign | null
  briefs: Record<string, BriefCard>
  candidates: ReviewRow[]
}

const STORAGE_KEY = 'influencer-workspace:v1'

export function readWorkspace(): WorkspaceState {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved) as WorkspaceState
      if (Array.isArray(parsed.plan?.selected) && Array.isArray(parsed.candidates) && parsed.briefs) return parsed
    }
  } catch {
    // The demo can also run with browser storage disabled.
  }
  return {plan: demo.plan, campaign: null, briefs: {}, candidates: []}
}

export function saveWorkspace(state: WorkspaceState) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Keep the in-memory session usable if storage is unavailable.
  }
}

export async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  })
  const result = await response.json().catch(() => null)
  if (path === '/api/ai' && response.status === 429) {
    return {mode: 'demo', message: '实时 AI 额度已用完，可以继续使用示例和模板。', ...result} as T
  }
  if (!response.ok || !result) {
    if (typeof result?.detail === 'string') throw new Error(result.detail)
    throw new Error('暂时无法完成操作，请稍后重试。')
  }
  return result as T
}

export const money = (value: number | null | undefined) => value == null ? '—' : `¥${new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 2}).format(value)}`
export const count = (value: number | null) => value == null ? '—' : value.toLocaleString('zh-CN')
export const percent = (value: number | null) => value == null ? '—' : `${(value * 100).toFixed(2)}%`
export const views = (value: number) => `${(value / 10000).toLocaleString('zh-CN', {maximumFractionDigits: 1})} 万`
export const tags = (field: string) => String(caseInfo[field]).split('|')

export function sameConditions(left: Conditions, right: Conditions) {
  return left.budget_total === right.budget_total && left.expected_creator_count === right.expected_creator_count
    && left.save_rate_target === right.save_rate_target && left.cpa_target === right.cpa_target
    && [...left.excluded_creator_ids].sort().join(',') === [...right.excluded_creator_ids].sort().join(',')
}
