import React, { useEffect, useState } from 'react'
import { api, PortfolioSummary, Trade } from '../services/api'

export const PaperTrading: React.FC = () => {
  const [symbol, setSymbol] = useState('GME')
  const [action, setAction] = useState<'buy' | 'sell'>('buy')
  const [quantity, setQuantity] = useState(1)
  const [price, setPrice] = useState(10)
  const [trades, setTrades] = useState<Trade[]>([])
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = () => {
    api.listTrades().then(setTrades).catch((e) => setError(String(e)))
    api.getPortfolio().then(setSummary).catch((e) => setError(String(e)))
  }

  useEffect(() => {
    refresh()
  }, [])

  const submit = async () => {
    setError(null)
    try {
      await api.createTrade({ stock_symbol: symbol, action, quantity, price })
      refresh()
    } catch (e: any) {
      setError(String(e))
    }
  }

  const doClose = async (id: number) => {
    const exit = Number(prompt('Exit price?'))
    if (!exit || isNaN(exit)) return
    try {
      await api.closeTrade(id, exit)
      refresh()
    } catch (e: any) {
      setError(String(e))
    }
  }

  return (
    <div>
      <h3>Paper Trading</h3>
      {error && <div style={{ color: 'red' }}>Error: {error}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="Symbol" />
        <select value={action} onChange={(e) => setAction(e.target.value as any)}>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <input type="number" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} min={1} />
        <input type="number" step="0.01" value={price} onChange={(e) => setPrice(Number(e.target.value))} min={0.01} />
        <button onClick={submit}>Create Trade</button>
      </div>

      <div style={{ marginBottom: 12 }}>
        <strong>Portfolio:</strong>{' '}
        {summary
          ? `open ${summary.open_positions}, closed ${summary.closed_positions}, realized ${summary.realized_pl}, unrealized ${summary.unrealized_pl}`
          : 'Loading…'}
      </div>

      <table cellPadding={6}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Symbol</th>
            <th>Action</th>
            <th>Qty</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id}>
              <td>{t.id}</td>
              <td>{t.stock_symbol}</td>
              <td>{t.action}</td>
              <td>{t.quantity}</td>
              <td>{t.entry_price}</td>
              <td>{t.exit_price ?? '-'}</td>
              <td>{t.exit_price == null && <button onClick={() => doClose(t.id)}>Close</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

