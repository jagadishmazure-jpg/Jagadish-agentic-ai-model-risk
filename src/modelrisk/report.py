"""Plain-text tables for the CLI (and therefore for the pasted outputs in docs)."""

from __future__ import annotations

from typing import Any


def table(rows: list[dict[str, Any]], cols: list[str], headers: list[str] | None = None) -> str:
    headers = headers or cols
    cells = [[str(r.get(c, "")) for c in cols] for r in rows]
    widths = [max(len(h), *(len(row[i]) for row in cells)) if cells else len(h) for i, h in enumerate(headers)]
    line = lambda vals: "  ".join(v.ljust(w) for v, w in zip(vals, widths, strict=False)).rstrip()  # noqa: E731
    return "\n".join([line(headers), line(["-" * w for w in widths])] + [line(r) for r in cells])


def heatmap_text(grid: list[list[int]], title: str) -> str:
    out = [title, "impact \\ likelihood   1  2  3  4  5"]
    for i, row in enumerate(grid):
        out.append(f"        {5 - i}             " + "  ".join(str(v) if v else "." for v in row))
    return "\n".join(out)
