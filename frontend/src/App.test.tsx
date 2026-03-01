import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
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
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    )
    await waitFor(() => { expect(screen.getByRole('heading', { name: /meme stocks/i })).toBeInTheDocument() })
    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    expect(nav).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Stocks' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Paper Trading' })).toBeInTheDocument()
  })

  it('marks Dashboard as current page by default', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    )
    await waitFor(() => { expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page') })
  })

  it('marks active tab with aria-current when switching', async () => {
    const user = userEvent.setup()
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    )
    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' })
    const stocksLink = screen.getByRole('link', { name: 'Stocks' })
    expect(dashboardLink).toHaveAttribute('aria-current', 'page')
    expect(stocksLink).not.toHaveAttribute('aria-current')

    await user.click(stocksLink)
    expect(stocksLink).toHaveAttribute('aria-current', 'page')
    expect(dashboardLink).not.toHaveAttribute('aria-current')
  })
})
