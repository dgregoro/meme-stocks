import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from './App'
import * as apiModule from './services/api'

vi.mock('./services/api', () => ({
  api: {
    health: vi.fn(),
    analysisDaily: vi.fn(),
    listNotifications: vi.fn(),
    getJobRuns: vi.fn(),
    listStocks: vi.fn(),
    listTrades: vi.fn(),
    getPortfolio: vi.fn(),
  },
}))

const api = apiModule.api

describe('App', () => {
  beforeEach(() => {
    vi.mocked(api.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(api.analysisDaily).mockResolvedValue([])
    vi.mocked(api.listNotifications).mockResolvedValue([])
    vi.mocked(api.getJobRuns).mockResolvedValue([])
    vi.mocked(api.listStocks).mockResolvedValue([])
    vi.mocked(api.listTrades).mockResolvedValue([])
    vi.mocked(api.getPortfolio).mockResolvedValue({ total_value: 0, win_rate: null, positions: [] })
  })

  it('renders app title and main navigation', async () => {
    render(<App />)
    await waitFor(() => { expect(screen.getByRole('heading', { name: /meme stocks/i })).toBeInTheDocument() })
    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    expect(nav).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stocks' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Paper Trading' })).toBeInTheDocument()
  })

  it('marks Dashboard as current page by default', async () => {
    render(<App />)
    await waitFor(() => { expect(screen.getByRole('button', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page') })
  })

  it('marks active tab with aria-current when switching', async () => {
    const user = userEvent.setup()
    render(<App />)
    const dashboardBtn = screen.getByRole('button', { name: 'Dashboard' })
    const stocksBtn = screen.getByRole('button', { name: 'Stocks' })
    expect(dashboardBtn).toHaveAttribute('aria-current', 'page')
    expect(stocksBtn).not.toHaveAttribute('aria-current')

    await user.click(stocksBtn)
    expect(stocksBtn).toHaveAttribute('aria-current', 'page')
    expect(dashboardBtn).not.toHaveAttribute('aria-current')
  })
})
