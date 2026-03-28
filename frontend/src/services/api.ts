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

/** Legacy shape for /api/jobs/{job}/runs; prefer JobRunHistoryItem for /api/status/jobs/runs */
export type JobRun = {
  id: number
  job_name: string
  run_at: string
}

export type JobRunHistoryItem = {
  id: number | null
  job_name: string
  started_at_utc: string | null
  finished_at_utc: string | null
  success: boolean | null
  error_message: string | null
  duration_seconds: number | null
  summary?: string | null
  metrics?: Record<string, unknown> | null
}

export type JobStatus = {
  job_id: string
  schedule: string | null
  last_run_utc: string | null
  last_success_utc: string | null
  last_status: 'ran' | 'never'
  last_error: string | null
  duration_seconds: number | null
  last_run_summary?: string | null
  last_success_summary?: string | null
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

export type CollectionHealth = {
  reddit: 'ok' | 'stale' | 'empty'
  prices: 'ok' | 'stale' | 'empty'
  daily_features: 'ok' | 'stale' | 'empty'
  jobs: 'ok' | 'warning'
}

export type CollectionThresholds = {
  reddit_stale_after_minutes: number
  prices_stale_after_days: number
  features_stale_after_days: number
}

export type StaleSymbolStatus = {
  symbol: string
  last_reddit_collected_at_utc: string | null
  last_price_date: string | null
  last_daily_feature_day: string | null
  stale_reasons: string[]
}

export type CollectionStatus = {
  server_time_utc: string
  market_time_local: string
  jobs: JobStatus[]
  reddit: RedditCollectionStatus
  prices: PriceCollectionStatus
  daily_features: DailyFeatureStatus
  health: CollectionHealth
  thresholds: CollectionThresholds
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

// --- Causal / lead-lag evidence ---

export type LagCorrelation = {
  lag: number
  corr: number
  n: number
}

export type PredictiveResult = {
  metric: string
  value: number
}

export type PlaceboResult = {
  metric: string
  value: number
}

export type CausalEvidenceResponse =
  | {
      status?: 'ok'
      symbol: string
      freq: string
      start_utc: string
      end_utc: string
      sample_size: number
      mention_xcorr: LagCorrelation[]
      sentiment_xcorr: LagCorrelation[]
      predictive: PredictiveResult[]
      placebo: PlaceboResult[]
      notes: string[]
    }
  | {
      status: 'insufficient_data'
      symbol: string
      freq: string
      reason: string
      buckets_available: number
      min_required: number
      notes?: string[]
    }

export async function fetchCausalEvidence(args: {
  symbol: string
  days: number
  freq: '15min' | '1h' | '1d' | string
  maxLag: number
  includePlacebo: boolean
}): Promise<CausalEvidenceResponse> {
  const { symbol, days, freq, maxLag, includePlacebo } = args
  const data = await handle(
    client.get<CausalEvidenceResponse>(
      `/api/analysis/causal/${encodeURIComponent(symbol)}`,
      {
        params: {
          days,
          freq,
          max_lag: maxLag,
          include_placebo: includePlacebo,
        },
      },
    ),
  )
  if ('buckets_available' in data && 'reason' in data) {
    return { ...data, status: 'insufficient_data' }
  }
  return data
}

// ---

// --- Intraday ingestion ---

export type IntradayStatusResponse = {
  alpaca_feed: string
  free_plan_mode: boolean
  sip_delay_minutes: number
  end_time_safety_minutes: number
  effective_data_lag_minutes: number
  notes: string
  counts_by_status: Record<string, number>
  newest_last_ts: string | null
  oldest_last_ts: string | null
  latest_run: {
    id?: number
    started_at?: string
    ended_at?: string
    symbols_count?: number
    bars_written?: number
    errors_count?: number
    notes?: string
  } | null
  intraday_ingestion_enabled: boolean
  lock: Record<string, unknown>
}

export type RunOnceResponse = {
  symbols_processed: number
  bars_written: number
  errors_count: number
  start_utc: string | null
  end_utc: string | null
  safe_end_used: string | null
  feed: string
  free_plan_mode: boolean
}

export const getIntradayStatus = () =>
  handle(client.get<IntradayStatusResponse>('/api/intraday/status'))

export const runIntradayOnce = () =>
  handle(client.post<RunOnceResponse>('/api/intraday/run-once'))

// --- Research API ---

export type BuildDatasetRequest = {
  start_day: string
  end_day: string
  horizon?: number
  symbols?: string[] | null
}

export type BuildDatasetResponse = {
  path: string
  rows_written: number
  labels_rows_upserted: number
  features_rows_upserted: number
  git_sha: string | null
  dataset_version: string
}

export type DirectionalityResponse = {
  mentions_lead_returns_corr: number | null
  mentions_lead_returns_n: number
  returns_lead_mentions_corr: number | null
  returns_lead_mentions_n: number
}

export type EventStudyResponse = {
  spike_mean_fwd_return: number | null
  spike_n: number
  non_spike_mean_fwd_return: number | null
  non_spike_n: number
  spread: number | null
}

export type PredictivenessResponse = {
  baseline_direction_accuracy: number | null
  augmented_direction_accuracy: number | null
  baseline_ridge_rmse: number | null
  augmented_ridge_rmse: number | null
  n_train: number
  n_test: number
}

export const buildDataset = (payload: BuildDatasetRequest) =>
  handle(client.post<BuildDatasetResponse>('/api/research/build-dataset', payload))

export const runDirectionality = (payload: {
  dataset_path: string
  k?: number
  h?: number
}) =>
  handle(client.post<DirectionalityResponse>('/api/research/experiment/directionality', payload))

export const runEventStudy = (payload: {
  dataset_path: string
  window?: number
  threshold?: string
  horizon?: number
}) =>
  handle(client.post<EventStudyResponse>('/api/research/experiment/event-study', payload))

export const runPredictiveness = (payload: {
  dataset_path: string
  horizon?: number
  split_date?: string | null
}) =>
  handle(client.post<PredictivenessResponse>('/api/research/experiment/predictiveness', payload))

// ---

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
  getJobRunsHistory: (limit = 200) =>
    handle(
      client.get<JobRunHistoryItem[]>('/api/status/jobs/runs', {
        params: { limit },
      }),
    ),
  getJobRunsHistoryForJob: (jobName: string, limit = 50) =>
    handle(
      client.get<JobRunHistoryItem[]>(`/api/status/jobs/${encodeURIComponent(jobName)}/runs`, {
        params: { limit },
      }),
    ),
  getCollectionStatus: () =>
    handle(client.get<CollectionStatus>('/api/status/collection')),
  getStaleSymbols: (limit = 25) =>
    handle(
      client.get<StaleSymbolStatus[]>('/api/status/symbols/stale', {
        params: { limit },
      }),
    ),
  getIntradayStatus,
  runIntradayOnce,
  buildDataset,
  runDirectionality,
  runEventStudy,
  runPredictiveness,
}
