import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders title and message', () => {
    render(<EmptyState title="No data" message="Nothing here yet." />)
    expect(screen.getByText('No data')).toBeInTheDocument()
    expect(screen.getByText('Nothing here yet.')).toBeInTheDocument()
  })

  it('renders optional action', () => {
    render(<EmptyState title="Empty" message="Add one." action="Click the button above." />)
    expect(screen.getByText('Click the button above.')).toBeInTheDocument()
  })
})
