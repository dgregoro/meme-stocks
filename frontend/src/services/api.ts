import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

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
}

export type PortfolioSummary = {
  total_positions: number
  open_positions: number
  closed_positions: number
  realized_pl: number
  unrealized_pl: number
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
  getPrices: (symbol: string) =>
    handle(client.get<PricePoint[]>(`/api/stocks/${symbol}/prices`)),
  listNotifications: () => handle(client.get<NotificationItem[]>('/api/notifications')),
  createTrade: (payload: { stock_symbol: string; action: 'buy' | 'sell'; quantity: number; price: number; notes?: string }) =>
    handle(client.post<Trade>('/api/trades', payload)),
  listTrades: () => handle(client.get<Trade[]>('/api/trades')),
  closeTrade: (id: number, exit_price: number) =>
    handle(client.post<Trade>(`/api/trades/${id}/close`, { exit_price })),
  getPortfolio: () => handle(client.get<PortfolioSummary>('/api/portfolio')),
}

