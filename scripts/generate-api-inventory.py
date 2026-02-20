#!/usr/bin/env python3
"""Generate API inventory from FastAPI's OpenAPI schema.

Run from project root:
    python scripts/generate-api-inventory.py

Output: .api-inventory.md
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.main import app  # noqa: E402


def generate_inventory() -> str:
    """Generate markdown inventory from FastAPI app."""
    openapi = app.openapi()

    lines = [
        "# API Endpoint Inventory",
        "",
        "**Generated from**: FastAPI OpenAPI schema",
        f"**Total Endpoints**: {count_endpoints(openapi)}",
        "",
        "## Endpoints",
        "",
        "| Method | Path | Summary | Tags |",
        "|--------|------|---------|------|",
    ]

    paths = openapi.get("paths", {})
    for path, methods in sorted(paths.items()):
        for method, details in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                summary = details.get("summary", "-")
                tags = ", ".join(details.get("tags", ["-"]))
                lines.append(f"| {method.upper()} | `{path}` | {summary} | {tags} |")

    # Group by tag for easier reading
    lines.extend(
        [
            "",
            "## Endpoints by Category",
            "",
        ]
    )

    # Collect endpoints by tag
    by_tag: dict[str, list[tuple[str, str, str]]] = {}
    for path, methods in paths.items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                tags = details.get("tags", ["untagged"])
                summary = details.get("summary", "-")
                for tag in tags:
                    if tag not in by_tag:
                        by_tag[tag] = []
                    by_tag[tag].append((method.upper(), path, summary))

    for tag in sorted(by_tag.keys()):
        lines.append(f"### {tag}")
        lines.append("")
        lines.append("| Method | Path | Summary |")
        lines.append("|--------|------|---------|")
        for method, path, summary in sorted(by_tag[tag], key=lambda x: x[1]):
            lines.append(f"| {method} | `{path}` | {summary} |")
        lines.append("")

    # Add schema models section
    lines.extend(
        [
            "## Request/Response Models",
            "",
            "| Model | Description |",
            "|-------|-------------|",
        ]
    )

    schemas = openapi.get("components", {}).get("schemas", {})
    for name, schema in sorted(schemas.items()):
        desc = schema.get("description", schema.get("title", "-"))
        # Truncate long descriptions
        if len(desc) > 60:
            desc = desc[:57] + "..."
        lines.append(f"| `{name}` | {desc} |")

    lines.extend(
        [
            "",
            "## How This File is Generated",
            "",
            "This file is auto-generated from FastAPI's OpenAPI schema.",
            "",
            "To regenerate:",
            "```bash",
            "python scripts/generate-api-inventory.py",
            "```",
            "",
            "Or include in quality check by running:",
            "```bash",
            "./scripts/quality-check.sh",
            "```",
        ]
    )

    return "\n".join(lines)


def count_endpoints(openapi: dict) -> int:
    """Count total number of endpoints."""
    count = 0
    for path, methods in openapi.get("paths", {}).items():
        for method in methods:
            if method in ("get", "post", "put", "delete", "patch"):
                count += 1
    return count


if __name__ == "__main__":
    output_path = project_root / ".api-inventory.md"

    try:
        inventory = generate_inventory()
        output_path.write_text(inventory)
        print(f"API inventory written to: {output_path}")
        print(f"Total endpoints: {count_endpoints(app.openapi())}")
    except Exception as e:
        print(f"Error generating inventory: {e}", file=sys.stderr)
        sys.exit(1)
