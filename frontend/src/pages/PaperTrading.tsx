import React, { useEffect, useState } from 'react'
import { api, CreateTradePayload, PortfolioSummary, Trade } from '../services/api'

export const PaperTrading: React.FC = () => {
  const [symbol, setSymbol] = useState('GME')
  const [action, setAction] = useState<'buy' | 'sell'>('buy')
  const [quantity, setQuantity] = useState(1)
  const [price, setPrice] = useState(10)
  const [instrumentType, setInstrumentType] = useState<'stock' | 'option'>('stock')
  const [optionType, setOptionType] = useState<'call' | 'put'>('call')
  const [strikePrice, setStrikePrice] = useState(20)
  const [expiryDate, setExpiryDate] = useState('')
  const [trades, setTrades] = useState<Trade[]>([])
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const refresh = () => {
    api.listTrades().then(setTrades).catch((e) => setError(String(e)))
    api.getPortfolio().then(setSummary).catch((e) => setError(String(e)))
  }

  useEffect(() => {
    refresh()
  }, [])

  const submit = async () => {
    setError(null)
    setSuccess(null)
    const payload: CreateTradePayload = {
      stock_symbol: symbol,
      action,
      quantity,
      price,
      instrument_type: instrumentType,
    }
    if (instrumentType === 'option') {
      payload.option_type = optionType
      payload.strike_price = strikePrice
      payload.expiry_date = expiryDate || undefined
    }
    try {
      await api.createTrade(payload)
      refresh()
      setSuccess('Trade created.')
      setTimeout(() => setSuccess(null), 5000)
    } catch (e: unknown) {
      setError(String(e))
    }
  }

  const doClose = async (id: number) => {
    const exit = Number(prompt('Exit price?'))
    if (!exit || isNaN(exit)) return
    setError(null)
    setSuccess(null)
    try {
      await api.closeTrade(id, exit)
      refresh()
      setSuccess('Position closed.')
      setTimeout(() => setSuccess(null), 5000)
    } catch (e: unknown) {
      setError(String(e))
    }
  }

  return (
    <div>
      <h3>Paper Trading</h3>
      {error && (
        <div style={{ color: '#b91c1c', padding: '8px 12px', marginBottom: 12, backgroundColor: '#fef2f2', borderRadius: 6 }} role="alert">
          Error: {error}
        </div>
      )}
      {success && (
        <div style={{ color: '#166534', padding: '8px 12px', marginBottom: 12, backgroundColor: '#dcfce7', borderRadius: 6 }} role="status">
          {success}
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="Symbol" />
        <select value={action} onChange={(e) => setAction(e.target.value as 'buy' | 'sell')}>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <select value={instrumentType} onChange={(e) => setInstrumentType(e.target.value as 'stock' | 'option')}>
          <option value="stock">Stock</option>
          <option value="option">Option</option>
        </select>
        {instrumentType === 'option' && (
          <>
            <select value={optionType} onChange={(e) => setOptionType(e.target.value as 'call' | 'put')}>
              <option value="call">Call</option>
              <option value="put">Put</option>
            </select>
            <input
              type="number"
              step="0.01"
              placeholder="Strike"
              value={strikePrice}
              onChange={(e) => setStrikePrice(Number(e.target.value))}
              min={0.01}
            />
            <input
              type="date"
              placeholder="Expiry"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
            />
          </>
        )}
        <input type="number" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} min={1} title={instrumentType === 'option' ? 'Contracts' : 'Shares'} />
        <input type="number" step="0.01" value={price} onChange={(e) => setPrice(Number(e.target.value))} min={0.01} title={instrumentType === 'option' ? 'Premium per share' : 'Price'} />
        <button onClick={submit}>Create Trade</button>
      </div>

      <div style={{ marginBottom: 12 }}>
        <strong>Portfolio:</strong>{' '}
        {summary
          ? `open ${summary.open_positions}, closed ${summary.closed_positions}, realized ${summary.realized_pl}, unrealized ${summary.unrealized_pl}` +
            (summary.win_rate != null
              ? ` | win rate ${(summary.win_rate * 100).toFixed(1)}%`
              : '') +
            (summary.average_win != null ? ` | avg win $${summary.average_win}` : '') +
            (summary.average_loss != null ? ` | avg loss $${summary.average_loss}` : '')
          : 'Loading…'}
      </div>

      <table cellPadding={6}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Symbol</th>
            <th>Type</th>
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
              <td>
                {t.stock_symbol}
                {t.instrument_type === 'option' && t.option_type && t.strike_price && (
                  <small> {t.option_type} ${t.strike_price}</small>
                )}
              </td>
              <td>{t.instrument_type === 'option' ? 'Option' : 'Stock'}</td>
              <td>{t.action}</td>
              <td>{t.quantity}{t.instrument_type === 'option' ? ' contracts' : ''}</td>
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
