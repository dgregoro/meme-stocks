import axios from 'axios'

// Empty string = same-origin (container build); unset = dev default to backend
const BASE_URL =
  import.meta.env.VITE_API_BASE_URL === ''
    ? ''
    : (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000')

export type AnalysisRow = {
  symbol: string
  sentiment_score: number | null
  mention_count: number
  price_trend: string
  composite_score: number
}

export type Stock = {
  symbol: string
  name: string
  sector: string | null
  market_cap: number | null
}

export type Sentiment = {
  stock_symbol: string
  score: number | null
  mention_count: number
  window_hours: number
  classification: string
}

export type RedditMention = {
  id: string
  subreddit: string
  title: string
  url: string
  author: string
  upvotes: number
  comments: number
  posted_at: string
  collected_at: string
}

export type PricePoint = {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export type NotificationItem = {
  id: number
  stock_symbol: string
  type: string
  message: string
  severity: string
  created_at: string
  read: boolean
}

export type Trade = {
  id: number
  stock_symbol: string
  action: 'buy' | 'sell'
  quantity: number
  entry_price: number
  exit_price: number | null
  instrument_type?: string
  option_type?: string | null
  strike_price?: number | null
  expiry_date?: string | null
}

export type CreateTradePayload = {
  stock_symbol: string
  action: 'buy' | 'sell'
  quantity: number
  price: number
  notes?: string
  instrument_type?: 'stock' | 'option'
  option_type?: 'call' | 'put'
  strike_price?: number
  expiry_date?: string // YYYY-MM-DD
}

export type PortfolioSummary = {
  total_positions: number
  open_positions: number
  closed_positions: number
  realized_pl: number
  unrealized_pl: number
  win_rate: number | null
  average_win: number | null
  average_loss: number | null
}

export type JobRun = {
  id: number
  job_name: string
  run_at: string
}

export type JobStatus = {
  job_id: string
  schedule: string | null
  last_start_utc: string | null
  last_end_utc: string | null
  last_success_utc: string | null
  last_status: 'success' | 'failure' | 'running' | 'never'
  last_error: string | null
  duration_seconds: number | null
}

export type RedditCollectionStatus = {
  posts_last_1h: number
  posts_last_24h: number
  mentions_last_1h: number
  mentions_last_24h: number
  newest_post_posted_at_utc: string | null
  newest_post_collected_at_utc: string | null
  oldest_post_collected_at_utc: string | null
}

export type PriceCollectionStatus = {
  newest_price_date: string | null
  price_rows_last_7d: number
  price_rows_last_30d: number
}

export type DailyFeatureStatus = {
  newest_trading_day: string | null
  rows_last_7d: number
  rows_last_30d: number
}

export type CollectionStatus = {
  server_time_utc: string
  market_time_local: string
  jobs: JobStatus[]
  reddit: RedditCollectionStatus
  prices: PriceCollectionStatus
  daily_features: DailyFeatureStatus
}

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
})

function handle<T>(p: Promise<{ data: T }>): Promise<T> {
  return p.then((r) => r.data).catch((e) => {
    const msg =
      e?.response?.data?.detail?.message ||
      e?.response?.data?.detail ||
      e?.message ||
      'Unknown error'
    throw new Error(msg)
  })
}

export const api = {
  health: () => handle(client.get<{ status: string }>('/health')),
  analysisDaily: () => handle(client.get<AnalysisRow[]>('/api/analysis/daily')),
  listStocks: () => handle(client.get<Stock[]>('/api/stocks')),
  getStock: (symbol: string) => handle(client.get<Stock>(`/api/stocks/${symbol}`)),
  getSentiment: (symbol: string) =>
    handle(client.get<Sentiment>(`/api/stocks/${symbol}/sentiment`)),
  getMentions: (symbol: string, limit = 20) =>
    handle(client.get<RedditMention[]>(`/api/stocks/${symbol}/mentions`, { params: { limit } })),
  getPrices: (symbol: string) =>
    handle(client.get<PricePoint[]>(`/api/stocks/${symbol}/prices`)),
  listNotifications: () => handle(client.get<NotificationItem[]>('/api/notifications')),
  createTrade: (payload: CreateTradePayload) =>
    handle(client.post<Trade>('/api/trades', payload)),
  listTrades: () => handle(client.get<Trade[]>('/api/trades')),
  closeTrade: (id: number, exit_price: number) =>
    handle(client.post<Trade>(`/api/trades/${id}/close`, { exit_price })),
  getPortfolio: () => handle(client.get<PortfolioSummary>('/api/portfolio')),
  getJobRuns: (jobName: string, limit = 1) =>
    handle(
      client.get<JobRun[]>(`/api/jobs/${encodeURIComponent(jobName)}/runs`, {
        params: { limit },
      }),
    ),
  getCollectionStatus: () =>
    handle(client.get<CollectionStatus>('/api/status/collection')),
}
