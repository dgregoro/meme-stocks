# 017 — Mean Reversion with Context Filters

## Goal

Determine whether mean reversion after extreme moves becomes stronger and more stable when conditioned on:

- magnitude of move
- relative volume

## Hypotheses

- H1: Larger moves → stronger mean reversion
- H2: High-volume moves → stronger mean reversion
- H3: Combining magnitude + volume produces a more tradeable signal

## Non-goals

- No ML
- No paper trading
- No optimization loops

## Outputs

- evaluation by magnitude bucket
- evaluation by volume bucket
- evaluation by combined bucket (magnitude × volume)

## Success Criteria

- ≥100 events per key bucket (where applicable)
- median returns consistently positive (extreme_down) or negative (extreme_up)
- no sign flip across time splits
- not dominated by a few symbols
