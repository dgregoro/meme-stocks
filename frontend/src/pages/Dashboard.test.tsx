import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Dashboard } from './Dashboard'
import * as apiModule from '../services/api'

vi.mock('../services/api', () => ({
  api: {
    analysisDaily: vi.fn(),
    listNotifications: vi.fn(),
    getJobRuns: vi.fn(),
  },
}))

const api = apiModule.api

const mockAnalysisRows = [
  {
    symbol: 'GME',
    sentiment_score: 0.4,
    mention_count: 50,
    price_trend: 'uptrend',
    composite_score: 0.85,
  },
  {
    symbol: 'AMC',
    sentiment_score: -0.3,
    mention_count: 30,
    price_trend: 'sideways',
    composite_score: 0.45,
  },
  {
    symbol: 'AAPL',
    sentiment_score: null,
    mention_count: 10,
    price_trend: 'downtrend',
    composite_score: 0.2,
  },
]

describe('Dashboard', () => {
  beforeEach(() => {
    vi.mocked(api.analysisDaily).mockResolvedValue(mockAnalysisRows)
    vi.mocked(api.listNotifications).mockResolvedValue([
      { id: 1, read: false, stock_symbol: 'GME', type: 'volume', message: 'Spike', severity: 'high', created_at: '' },
      { id: 2, read: true, stock_symbol: 'AMC', type: 'price', message: 'Move', severity: 'medium', created_at: '' },
    ])
    vi.mocked(api.getJobRuns).mockResolvedValue([
      { id: 1, job_name: 'reddit_collection', run_at: '2026-02-28T11:30:00.000Z' },
    ])
  })

  it('shows loading then daily analysis content', async () => {
    render(<Dashboard />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Daily Analysis' })).toBeInTheDocument()
    })
    expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
  })

  it('shows summary cards: stocks count, unread notifications, last run', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('Daily Analysis')).toBeInTheDocument()
    })
    expect(screen.getByText('Stocks in analysis')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Unread notifications')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('Last Reddit run')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTitle('2026-02-28T11:30:00.000Z')).toBeInTheDocument()
    })
  })

  it('shows error when API fails', async () => {
    vi.mocked(api.analysisDaily).mockRejectedValue(new Error('Network error'))
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeInTheDocument()
      expect(screen.getByText(/Network error/)).toBeInTheDocument()
    })
  })

  it('renders analysis table with sortable columns', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('GME')).toBeInTheDocument()
    })
    expect(screen.getByText('AMC')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /Symbol/ })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /Composite/ })).toBeInTheDocument()
  })

  it('sorts by column when header is clicked', async () => {
    const user = userEvent.setup()
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('GME')).toBeInTheDocument()
    })
    const symbolHeader = screen.getByRole('columnheader', { name: /Symbol/ })
    await user.click(symbolHeader)
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('AAPL')).toBeInTheDocument()
    expect(within(rows[1]).getByText('AMC')).toBeInTheDocument()
    expect(within(rows[2]).getByText('GME')).toBeInTheDocument()
  })

  it('shows sentiment scores with n/a for null', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('0.40')).toBeInTheDocument()
    })
    expect(screen.getByText('-0.30')).toBeInTheDocument()
    expect(screen.getByText('n/a')).toBeInTheDocument()
  })

  it('shows empty state when no analysis rows', async () => {
    vi.mocked(api.analysisDaily).mockResolvedValue([])
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('No analysis yet')).toBeInTheDocument()
    })
    expect(screen.getByText(/Daily analysis ranks stocks/)).toBeInTheDocument()
  })
})
