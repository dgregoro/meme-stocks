import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LoadingSpinner } from './LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders with default message and role status', () => {
    render(<LoadingSpinner />)
    const status = screen.getByRole('status')
    expect(status).toBeInTheDocument()
    expect(status).toHaveTextContent('Loading...')
  })

  it('renders with custom message', () => {
    render(<LoadingSpinner message="Loading notifications…" />)
    const status = screen.getByRole('status')
    expect(status).toBeInTheDocument()
    expect(status).toHaveTextContent('Loading notifications…')
  })

  it('has aria-busy for assistive tech', () => {
    render(<LoadingSpinner />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true')
  })
})
