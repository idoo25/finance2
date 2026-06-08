"""A single self-contained HTML dashboard.

Renders one live snapshot so you can *see* every source with your own eyes:
each raw quote, what was accepted or rejected and why, the median asset price,
the FX rates, and the resulting index. Fetching happens server-side (on the
machine running this app), so there are no CORS issues and it uses that
machine's network -- run it where the internet is open and set GPMI_USE_MOCK=0
to see live data.
"""
from __future__ import annotations

import html
from datetime import timezone

from ..adapters import USE_MOCK
from ..core.types import utcnow
from ..pipeline import SnapshotResult


def _age(ts) -> str:
    if ts is None:
        return "-"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    secs = (utcnow() - ts).total_seconds()
    if secs < 90 * 60:
        return f"{secs/60:.0f} min"
    if secs < 48 * 3600:
        return f"{secs/3600:.1f} h"
    return f"{secs/86400:.1f} d"


def _fmt(x) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    return f"{x:,.4f}" if abs(x) < 1000 else f"{x:,.2f}"


_STATUS_COLOR = {"ok": "#1a7f37", "valid": "#1a7f37", "degraded": "#9a6700",
                 "frozen": "#cf222e"}


def render_dashboard(result: SnapshotResult) -> str:
    idx = result.index
    mode = "MOCK (offline sample data)" if USE_MOCK else "LIVE (keyless real sources)"
    mode_color = "#9a6700" if USE_MOCK else "#1a7f37"
    sc = _STATUS_COLOR.get(idx.status.value, "#57606a")

    # group raws by asset
    by_asset: dict[str, list] = {}
    for r in result.raws:
        if r.asset_id.startswith("fx_"):
            continue
        by_asset.setdefault(r.asset_id, []).append(r)

    rows = []
    for asset_id, ap in result.asset_prices.items():
        astatus = ap.status.value
        acolor = _STATUS_COLOR.get(astatus, "#57606a")
        raws = by_asset.get(asset_id, [])
        first = True
        if not raws:
            rows.append(f"<tr><td>{asset_id}</td><td colspan='6' class='muted'>no sources returned data</td>"
                        f"<td style='color:{acolor}'>{astatus}</td><td>—</td></tr>")
            continue
        for r in raws:
            ok = "✓" if r.is_valid else "✗"
            okc = "#1a7f37" if r.is_valid else "#cf222e"
            reason = r.rejection_reason or ""
            asset_cell = (f"<td rowspan='{len(raws)}'><b>{asset_id}</b></td>" if first else "")
            median_cell = (f"<td rowspan='{len(raws)}'>{_fmt(ap.median_price_usd)}<br>"
                           f"<span style='color:{acolor}'>{astatus}</span> "
                           f"({ap.valid_source_count}/{ap.source_count})</td>" if first else "")
            rows.append(
                f"<tr>{asset_cell}"
                f"<td>{html.escape(r.source_id)}</td>"
                f"<td>{html.escape(r.region)}</td>"
                f"<td class='num'>{_fmt(r.price)} {r.currency}</td>"
                f"<td class='muted'>{html.escape(r.unit)}</td>"
                f"<td>{_age(r.timestamp)}</td>"
                f"<td style='color:{okc};font-weight:bold'>{ok} <span class='muted'>{reason}</span></td>"
                f"{median_cell}</tr>"
            )
            first = False

    fx_rows = []
    for ccy, fx in result.fx_rates.items():
        fc = _STATUS_COLOR.get(fx.status.value, "#57606a")
        fx_rows.append(
            f"<tr><td><b>{ccy}</b></td><td class='num'>{_fmt(fx.rate)}</td>"
            f"<td>{fx.source_count}</td><td style='color:{fc}'>{fx.status.value}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FreeGPMI — live source dashboard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background:#f6f8fa; color:#1f2328; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
  h1 {{ margin: 0 0 4px; font-size: 22px; }}
  .mode {{ display:inline-block; padding:2px 10px; border-radius:12px; color:#fff; font-size:12px; font-weight:600; background:{mode_color}; }}
  .card {{ background:#fff; border:1px solid #d0d7de; border-radius:10px; padding:18px 20px; margin:16px 0; }}
  .big {{ font-size:40px; font-weight:700; color:{sc}; }}
  .meta {{ color:#57606a; font-size:13px; }}
  table {{ border-collapse: collapse; width:100%; font-size:13px; }}
  th, td {{ text-align:left; padding:6px 10px; border-bottom:1px solid #eaeef2; vertical-align:top; }}
  th {{ background:#f6f8fa; position:sticky; top:0; }}
  .num {{ text-align:right; font-variant-numeric: tabular-nums; }}
  .muted {{ color:#8c959f; font-size:12px; }}
  a.btn {{ display:inline-block; margin-top:8px; padding:6px 14px; background:#0969da; color:#fff; border-radius:6px; text-decoration:none; font-size:13px; }}
</style></head>
<body><div class="wrap">
  <h1>FreeGPMI — live source dashboard</h1>
  <span class="mode">{mode}</span>

  <div class="card">
    <div class="big">{_fmt(idx.value)}</div>
    <div>status: <b style="color:{sc}">{idx.status.value.upper()}</b> ·
         quality {_fmt(idx.quality_score)} ·
         pairs {idx.valid_pairs}/{idx.expected_pairs}</div>
    <div class="meta">base {idx.base_date} · computed {idx.timestamp.isoformat(timespec='seconds')}
         · oldest source {_age(idx.oldest_source_ts)} · degraded/frozen: {', '.join(idx.degraded_assets) or 'none'}</div>
    <a class="btn" href="">↻ refresh (new snapshot)</a>
  </div>

  <div class="card">
    <h3>Assets — every raw source quote</h3>
    <table>
      <tr><th>asset</th><th>source</th><th>region</th><th class="num">raw price</th>
          <th>unit</th><th>age</th><th>accepted?</th><th>median (USD) / status</th></tr>
      {''.join(rows)}
    </table>
  </div>

  <div class="card">
    <h3>FX — units of currency per 1 USD (median of sources)</h3>
    <table>
      <tr><th>currency</th><th class="num">rate</th><th>sources</th><th>status</th></tr>
      {''.join(fx_rows)}
    </table>
  </div>

  <p class="meta">Fetched server-side by this app. In MOCK mode the numbers come
  from <code>data/mock</code>; set <code>GPMI_USE_MOCK=0</code> and run where the
  internet is open to pull live data from Stooq, Yahoo, ECB and Frankfurter.</p>
</div></body></html>"""
