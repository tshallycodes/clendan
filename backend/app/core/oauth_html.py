"""Shared HTML response for OAuth connection success."""
from fastapi.responses import HTMLResponse


def connected_page(integration_name: str, redirect_url: str) -> HTMLResponse:
    """Returns a styled Clendan-branded success page after OAuth connection completes.

    The page auto-redirects to redirect_url after 3 seconds and shows a manual
    'Go to Integrations' button as a fallback.
    """
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{integration_name} Connected — Clendan</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0a0a0a;
      color: #f0f0f0;
      font-family: 'IBM Plex Mono', 'Courier New', monospace;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
    }}
    .card {{
      border: 1px solid #2c2c2c;
      background: #111111;
      padding: 32px;
      max-width: 400px;
      width: 100%;
    }}
    .label {{
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: #666666;
      margin-bottom: 20px;
    }}
    .status-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }}
    .dot {{
      width: 8px;
      height: 8px;
      min-width: 8px;
      background: #00C853;
      border-radius: 50%;
    }}
    h1 {{
      font-size: 18px;
      font-weight: 700;
      color: #f0f0f0;
      letter-spacing: -0.02em;
    }}
    .sub {{
      font-size: 12px;
      color: #a0a0a0;
      margin-bottom: 28px;
      margin-top: 8px;
      line-height: 1.6;
    }}
    .btn {{
      display: block;
      background: #00C853;
      color: #000;
      padding: 12px 20px;
      font-family: inherit;
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
      text-align: center;
      letter-spacing: 0.02em;
    }}
    .btn:hover {{ background: #00a844; }}
    .wordmark {{
      font-size: 10px;
      color: #2c2c2c;
      text-align: center;
      margin-top: 32px;
      text-transform: uppercase;
      letter-spacing: 0.15em;
    }}
  </style>
</head>
<body>
  <div class="card">
    <p class="label">Integration Status</p>
    <div class="status-row">
      <div class="dot"></div>
      <h1>{integration_name} Connected</h1>
    </div>
    <p class="sub">
      Your {integration_name} account was connected successfully.<br>
      Data sync is running in the background.
    </p>
    <a class="btn" href="{redirect_url}">Go to Integrations</a>
    <p class="wordmark">Clendan</p>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)
