"""S7 rule discovery: daily feature matrix + bounded quantile grid (research CLI only)."""

from __future__ import annotations

from backend.app.services.s7_rule_discovery.feature_matrix import (
    build_feature_matrix_rows,
    write_matrix_csv,
)
from backend.app.services.s7_rule_discovery.grid_search import (
    load_matrix_csv,
    run_quantile_rule_grid,
    run_search_from_matrix_path,
)

__all__ = [
    "build_feature_matrix_rows",
    "load_matrix_csv",
    "run_quantile_rule_grid",
    "run_search_from_matrix_path",
    "write_matrix_csv",
]
