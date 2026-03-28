# Research: 013 Sector ETF confirmation

## 1. Unmapped leader symbol when gate enabled

**Decision**: **Pass** the sector gate (allow trade) with **warning** log; snapshot records `sector_etf_symbol: null` and no MA/return fields.

**Rationale**: Spec recommends not breaking batch runs for a few unmapped tick ETF candidates.

**Alternatives**: Strict fail-all — rejected for MVP friction.

## 2. Insufficient ETF price history

**Decision**: **Fail** gate (skip trade); increment `skipped_sector_confirmation_count` and `skipped_count`.

**Rationale**: Conservative; avoids trading when sector context is unknown.

## 3. Decision date for sector bar

**Decision**: Use **follower entry date** (same calendar day as simulated entry: `same_close` = signal date; `next_open` = first trading day after signal).

**Rationale**: FR-4 gates at simulation entry time; aligns with when capital would deploy.

## 4. `ma_above` definition (no look-ahead)

**Decision**: `MA = mean(close on prior `sector_trend_window` **trading** days strictly before `as_of`)`. Pass if `close(as_of) > MA` when `require_positive_trend`; if `require_positive_trend` is false, pass if `close(as_of) >= MA`.

**Rationale**: “Prior” window avoids same-day leakage in MA denominator interpretation.

**Alternatives**: Include as_of in MA — rejected to match spec “prior trading days”.

## 5. `rolling_return`

**Decision**: `return_pct = (close(as_of) / close(as_of_minus_window) - 1) * 100` where `as_of_minus_window` is the date **sector_trend_window** trading days **before** as_of on the **ETF** calendar. Pass if `return_pct >= minimum_sector_return_pct`; if `require_positive_trend`, additionally require `return_pct > 0` when `minimum_sector_return_pct <= 0`.

**Rationale**: Simple interpretable momentum.

## 6. `combined`

**Decision**: Both `ma_above` and `rolling_return` must pass (**single** `sector_trend_window` for both).

## 7. ETF ingestion

**Decision**: Document in **quickstart** that mapped ETFs must exist in `stocks` + `price_data` (same as equities); optional seed snippet; no new job.
