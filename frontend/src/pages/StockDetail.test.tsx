import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { StockDetail } from './StockDetail'
import * as apiModule from '../services/api'

vi.mock('../services/api', () => ({
  api: {
    getSentiment: vi.fn(),
    getPrices: vi.fn(),
    getMentions: vi.fn(),
  },
}))

const api = apiModule.api

function renderStockDetail(symbol: string) {
  return render(
    <MemoryRouter initialEntries={[`/stocks/${symbol}`]}>
      <Routes>
        <Route path="/stocks/:symbol" element={<StockDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('StockDetail', () => {
  beforeEach(() => {
    vi.mocked(api.getSentiment).mockResolvedValue({
      stock_symbol: 'AAPL',
      score: 0.35,
      mention_count: 20,
      window_hours: 24,
      classification: 'positive',
    })
    vi.mocked(api.getPrices).mockResolvedValue([
      { date: '2026-02-01', open: 100, high: 102, low: 99, close: 101, volume: 1e6 },
      { date: '2026-02-02', open: 101, high: 103, low: 100, close: 102, volume: 1.2e6 },
    ])
    vi.mocked(api.getMentions).mockResolvedValue([
      { id: '1', subreddit: 'wallstreetbets', title: 'AAPL to the moon', url: '/r/wsb/1', author: 'u1', upvotes: 100, comments: 10, posted_at: '', collected_at: '' },
    ])
  })

  it('shows loading then content with symbol, chart, sentiment, and mentions', async () => {
    renderStockDetail('AAPL')
    await waitFor(() => { expect(screen.getByRole('link', { name: '← Back to list' })).toBeInTheDocument() })
    expect(screen.getByRole('link', { name: '← Back to list' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Price' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Sentiment' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Recent Reddit mentions' })).toBeInTheDocument()
    expect(screen.getByText(/positive/)).toBeInTheDocument()
    expect(screen.getByText(/0.35/)).toBeInTheDocument()
    expect(screen.getByText(/r\/wallstreetbets/)).toBeInTheDocument()
  })

  it('shows no price data when prices empty', async () => {
    vi.mocked(api.getPrices).mockResolvedValue([])
    renderStockDetail('GME')
    await waitFor(() => { expect(screen.getByText('GME')).toBeInTheDocument() })
    expect(screen.getByText('No price data')).toBeInTheDocument()
  })

  it('shows error when API fails', async () => {
    vi.mocked(api.getSentiment).mockRejectedValue(new Error('Network error'))
    renderStockDetail('XYZ')
    await waitFor(() => { expect(screen.getByText(/Error:/)).toBeInTheDocument() })
    expect(screen.getByRole('alert')).toHaveTextContent('Network error')
  })
})
