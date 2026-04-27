#!/usr/bin/env python3
"""Build elixir.land/index.html from source data.

Reads countries-110m.json (Natural Earth via world-atlas TopoJSON) and
jose_face.jpg, produces a single static index.html with embedded SVG paths
and base64 face image. Run from anywhere:

    python3 build/build.py
"""
import base64
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

random.seed(11)


# --- TopoJSON -> sketchy cartoon SVG paths ---------------------------------

VW, VH = 880, 440  # equirectangular viewBox

LAND_EPS, LAND_JITTER = 4.0, 1.6
BRAZIL_EPS, BRAZIL_JITTER = 1.5, 0.8
ICE_EPS, ICE_JITTER = 4.0, 1.2


def proj(lon, lat):
    return ((lon + 180) * VW / 360, (90 - lat) * VH / 180)


def perp_dist(pt, a, b):
    px, py = pt
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    qx, qy = ax + t * dx, ay + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


def douglas_peucker(points, eps):
    n = len(points)
    if n < 3:
        return points
    keep = [False] * n
    keep[0] = True
    keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        max_d, max_i = 0.0, -1
        for i in range(a + 1, b):
            d = perp_dist(points[i], points[a], points[b])
            if d > max_d:
                max_d, max_i = d, i
        if max_d > eps and max_i != -1:
            keep[max_i] = True
            stack.append((a, max_i))
            stack.append((max_i, b))
    return [p for p, k in zip(points, keep) if k]


def fmt(n):
    s = f'{n:.1f}'
    return s[:-2] if s.endswith('.0') else s


def jitter(x, y, amt):
    return (
        x + (random.random() - 0.5) * 2 * amt,
        y + (random.random() - 0.5) * 2 * amt,
    )


def load_arcs(topo):
    scale = topo['transform']['scale']
    trans = topo['transform']['translate']
    out = []
    for arc in topo['arcs']:
        pts, x, y = [], 0, 0
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * scale[0] + trans[0], y * scale[1] + trans[1]))
        out.append(pts)
    return out


def ring_d(ring, decoded, eps_px, jitter_amt):
    def arc_pts(idx):
        return list(reversed(decoded[~idx])) if idx < 0 else decoded[idx]

    pts = []
    for ai in ring:
        p = arc_pts(ai)
        if pts:
            p = p[1:]
        pts.extend(p)
    if len(pts) < 3:
        return ''
    pp = [proj(*p) for p in pts]
    # split at dateline crossings
    segs, cur = [], [pp[0]]
    for i in range(1, len(pp)):
        if abs(pp[i][0] - pp[i - 1][0]) > VW / 2:
            if len(cur) >= 3:
                segs.append(cur)
            cur = [pp[i]]
        else:
            cur.append(pp[i])
    if len(cur) >= 3:
        segs.append(cur)
    segs = [douglas_peucker(s, eps_px) for s in segs if len(s) >= 3]
    segs = [s for s in segs if len(s) >= 3]
    if jitter_amt > 0:
        segs = [[jitter(x, y, jitter_amt) for x, y in seg] for seg in segs]
    out = []
    for seg in segs:
        out.append(f'M{fmt(seg[0][0])} {fmt(seg[0][1])}')
        prev = seg[0]
        for x, y in seg[1:]:
            out.append(f'l{fmt(x - prev[0])} {fmt(y - prev[1])}')
            prev = (x, y)
        out.append('Z')
    return ''.join(out)


def geom_d(geom, decoded, eps_px, jitter_amt):
    if geom['type'] == 'Polygon':
        return ''.join(ring_d(r, decoded, eps_px, jitter_amt) for r in geom['arcs'])
    if geom['type'] == 'MultiPolygon':
        return ''.join(
            ring_d(r, decoded, eps_px, jitter_amt)
            for poly in geom['arcs']
            for r in poly
        )
    return ''


def build_paths():
    topo = json.loads((HERE / 'countries-110m.json').read_text())
    decoded = load_arcs(topo)
    brazil_d = ''
    antarctica_d = ''
    greenland_d = ''
    others = []
    for c in topo['objects']['countries']['geometries']:
        name = c.get('properties', {}).get('name', '')
        if name == 'Brazil':
            brazil_d = geom_d(c, decoded, BRAZIL_EPS, BRAZIL_JITTER)
        elif name == 'Antarctica':
            antarctica_d = geom_d(c, decoded, ICE_EPS, ICE_JITTER)
        elif name == 'Greenland':
            greenland_d = geom_d(c, decoded, ICE_EPS, ICE_JITTER)
        else:
            others.append(geom_d(c, decoded, LAND_EPS, LAND_JITTER))
    return {
        'brazil_d': brazil_d,
        'land_d': ''.join(others),
        'ice_d': antarctica_d + greenland_d,
    }


# --- HTML template ---------------------------------------------------------

# Target city: spin lands this point at the globe's center
SP_LON, SP_LAT = -46.63, -23.55  # São Paulo

ELIXIR_LOGO_D = (
    "M19.793 16.575c0 3.752-2.927 7.426-7.743 7.426-5.249 0-7.843-3.71-7.843-8.29 "
    "0-5.21 3.892-12.952 8-15.647a.397.397 0 0 1 .61.371 9.716 9.716 0 0 0 1.694 6.518c.522.795 1.092 1.478 1.763 2.352.94 1.227 1.637 1.906 2.644 3.842l.015.028a7.107 7.107 0 0 1 .86 3.4z"
)

POLE_H = 220
FLAG_W = 150
FLAG_H = 90


def render_html(paths, face_b64):
    sp_x = (SP_LON + 180) * VW / 360
    sp_y = (90 - SP_LAT) * VH / 180
    t_end = round(220 - (VW + sp_x))
    t_start = t_end + 565
    flag_offset_y = sp_y - 220
    return TEMPLATE.format(
        T_START=t_start,
        T_END=t_end,
        flag_offset_y_minus_45=f'{flag_offset_y - 45:.0f}',
        flag_offset_y=f'{flag_offset_y:.0f}',
        POLE_H=POLE_H,
        POLE_H_PLUS_4=POLE_H + 4,
        POLE_H_MINUS_4=POLE_H - 4,
        POLE_H_MINUS_20=POLE_H - 20,
        POLE_H_MINUS_30=POLE_H - 30,
        POLE_H_MINUS_50=POLE_H - 50,
        POLE_H_MINUS_60=POLE_H - 60,
        POLE_H_MINUS_80=POLE_H - 80,
        FLAG_W=FLAG_W,
        FLAG_W_MINUS_14=FLAG_W - 14,
        FLAG_W_MINUS_10=FLAG_W - 10,
        FLAG_W_MINUS_8=FLAG_W - 8,
        FLAG_W_MINUS_7=FLAG_W - 7,
        FLAG_W_MINUS_4=FLAG_W - 4,
        FLAG_W_MINUS_3=FLAG_W - 3,
        FLAG_W_MINUS_2=FLAG_W - 2,
        FLAG_W_MINUS_1=FLAG_W - 1,
        FLAG_H=FLAG_H,
        FLAG_H_MINUS_2=FLAG_H - 2,
        FLAG_H_MINUS_10=FLAG_H - 10,
        ELIXIR_LOGO_D=ELIXIR_LOGO_D,
        face_b64=face_b64,
        **paths,
    )


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>elixir.land</title>
  <meta name="description" content="where Elixir meets Brazil">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --elixir: #4b275f;
      --elixir-glow: #b589c4;
      --ocean-deep: #0c2d4e;
    }}

    html, body {{ height: 100%; overflow: hidden; }}

    body {{
      background: radial-gradient(ellipse at 50% 40%, #1b1038 0%, #0a0418 60%, #020108 100%);
      color: #fff;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      display: flex; align-items: center; justify-content: center;
    }}

    .stars {{
      position: fixed; inset: 0; pointer-events: none;
      background-image:
        radial-gradient(1px 1px at 20% 30%, #fff 50%, transparent 100%),
        radial-gradient(1px 1px at 75% 15%, #fff 50%, transparent 100%),
        radial-gradient(1px 1px at 40% 80%, #fff 50%, transparent 100%),
        radial-gradient(2px 2px at 85% 70%, #fff 50%, transparent 100%),
        radial-gradient(1px 1px at 10% 60%, #fff 50%, transparent 100%),
        radial-gradient(1px 1px at 55% 45%, #fff 50%, transparent 100%),
        radial-gradient(1px 1px at 90% 40%, #fff 50%, transparent 100%),
        radial-gradient(1px 1px at 30% 10%, #fff 50%, transparent 100%),
        radial-gradient(2px 2px at 65% 90%, #fff 50%, transparent 100%),
        radial-gradient(1px 1px at 5% 90%, #fff 50%, transparent 100%);
      opacity: 0.6;
      animation: twinkle 6s ease-in-out infinite;
    }}
    @keyframes twinkle {{ 0%, 100% {{ opacity: 0.4; }} 50% {{ opacity: 0.85; }} }}

    .scene {{
      position: relative;
      width: 520px; height: 520px;
      animation: scene-zoom 10s cubic-bezier(0.4, 0, 0.3, 1) forwards;
    }}

    @keyframes scene-zoom {{
      0%, 40% {{ transform: scale(1) translateY(0); }}
      58%     {{ transform: scale(1.4) translateY(20px); }}
      100%    {{ transform: scale(1.4) translateY(20px); }}
    }}

    .atmosphere {{
      position: absolute;
      top: 50%; left: 50%;
      width: 520px; height: 520px;
      margin-left: -260px; margin-top: -260px;
      border-radius: 50%;
      background: radial-gradient(circle,
        rgba(120, 180, 240, 0) 58%,
        rgba(120, 180, 240, 0.18) 68%,
        rgba(160, 130, 220, 0.30) 76%,
        rgba(160, 130, 220, 0) 86%);
      pointer-events: none;
      filter: blur(1px);
      animation: pulse 4s ease-in-out infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 0.75; transform: scale(1); }}
      50%      {{ opacity: 1;    transform: scale(1.025); }}
    }}

    .globe {{
      position: absolute;
      top: 50%; left: 50%;
      width: 440px; height: 440px;
      margin-left: -220px; margin-top: -220px;
      border-radius: 50%;
      overflow: hidden;
      background: var(--ocean-deep);
      box-shadow:
        inset -18px -30px 70px 5px rgba(0, 0, 0, 0.60),
        inset 22px 20px 50px rgba(180, 220, 255, 0.12),
        0 0 50px rgba(100, 160, 220, 0.25),
        0 0 140px rgba(75, 39, 95, 0.4);
    }}

    .map-track {{
      position: absolute;
      top: 0; left: 0; height: 100%;
      width: 2640px;
      display: flex;
      transform: translateX({T_START}px);
      animation: spin 4.4s cubic-bezier(0.15, 0.65, 0.25, 1) forwards;
    }}

    .map {{ width: 880px; height: 100%; flex: 0 0 auto; display: block; }}

    @keyframes spin {{
      0%   {{ transform: translateX({T_START}px); }}
      100% {{ transform: translateX({T_END}px); }}
    }}

    .lighting {{
      position: absolute; inset: 0;
      border-radius: 50%;
      pointer-events: none;
      background:
        radial-gradient(circle at 32% 26%, rgba(255, 255, 255, 0.42) 0%, rgba(255, 255, 255, 0) 38%),
        radial-gradient(circle at 76% 82%, rgba(0, 0, 0, 0.68) 10%, rgba(0, 0, 0, 0) 65%),
        radial-gradient(circle at 50% 50%, rgba(0, 0, 0, 0) 55%, rgba(0, 0, 0, 0.35) 100%);
    }}

    .wire {{
      position: absolute; inset: 0;
      pointer-events: none;
      opacity: 0.16;
      mix-blend-mode: screen;
    }}

    .brazil-pulse {{
      position: absolute;
      top: 50%; left: 50%;
      width: 90px; height: 90px;
      margin-left: -45px;
      margin-top: {flag_offset_y_minus_45}px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(181, 137, 196, 0.95) 0%, rgba(181, 137, 196, 0) 70%);
      opacity: 0;
      animation:
        brazil-pulse 1.4s ease-out 3.8s forwards,
        brazil-pulse-loop 2.5s ease-in-out 5.2s infinite;
      pointer-events: none;
      mix-blend-mode: screen;
    }}
    @keyframes brazil-pulse {{
      0%   {{ opacity: 0; transform: scale(0.3); }}
      60%  {{ opacity: 1; transform: scale(1.2); }}
      100% {{ opacity: 0.9; transform: scale(1); }}
    }}
    @keyframes brazil-pulse-loop {{
      0%, 100% {{ opacity: 0.6; transform: scale(1); }}
      50%      {{ opacity: 1;   transform: scale(1.25); }}
    }}

    .flag-wrap {{
      position: absolute;
      top: 50%; left: 50%;
      margin-left: -2px;
      margin-top: {flag_offset_y}px;
      width: 4px; height: 0;
      pointer-events: none; z-index: 5;
    }}

    .bobblehead {{
      position: absolute;
      left: 50%; top: 0;
      width: 90px; height: 90px;
      margin-left: -84px;
      margin-top: -50px;
      z-index: 6;
      opacity: 0;
      transform-origin: center bottom;
      animation: bobble-in 0.8s cubic-bezier(0.25, 1.4, 0.4, 1) 4.6s forwards;
      filter: drop-shadow(0 5px 8px rgba(0,0,0,0.55));
    }}
    @keyframes bobble-in {{
      0%   {{ opacity: 0; transform: translateY(50px) scale(0.4) rotate(-8deg); }}
      60%  {{ opacity: 1; transform: translateY(-4px) scale(1.05) rotate(2deg); }}
      100% {{ opacity: 1; transform: translateY(0) scale(1) rotate(0); }}
    }}
    .bobble-head {{
      transform-origin: 35px 56px;
      animation: head-bobble 1.8s ease-in-out 5.5s infinite;
    }}
    @keyframes head-bobble {{
      0%, 100% {{ transform: rotate(-6deg); }}
      50%      {{ transform: rotate(6deg); }}
    }}

    .pole {{
      position: absolute;
      left: 50%; top: 0;
      width: 3px; height: 0;
      margin-left: -1.5px;
      background: linear-gradient(to top, #9a7faf 0%, #d9c2e4 100%);
      border-radius: 3px;
      box-shadow: 0 0 8px rgba(181, 137, 196, 0.7);
      animation: pole-rise 1.0s cubic-bezier(0.2, 0.7, 0.2, 1) 5.6s forwards;
    }}
    @keyframes pole-rise {{
      0%   {{ height: 0; top: 0; }}
      100% {{ height: {POLE_H}px; top: -{POLE_H}px; }}
    }}

    .finial {{
      position: absolute;
      left: 50%; top: 0;
      width: 8px; height: 8px;
      margin-left: -4px;
      margin-top: -{POLE_H_PLUS_4}px;
      border-radius: 50%;
      background: radial-gradient(circle at 30% 30%, #ffe082, #c69612);
      box-shadow: 0 0 6px rgba(255, 200, 80, 0.9);
      opacity: 0;
      animation: finial-in 0.4s ease-out 6.4s forwards;
    }}
    @keyframes finial-in {{
      0% {{ opacity: 0; transform: scale(0.2); }}
      100% {{ opacity: 1; transform: scale(1); }}
    }}

    .flag-banner {{
      position: absolute;
      left: 50%; top: 0;
      width: {FLAG_W}px; height: {FLAG_H}px;
      margin-left: 0;
      margin-top: -{POLE_H_MINUS_4}px;
      transform-origin: left center;
      transform: scaleX(0);
      opacity: 0;
      animation:
        flag-unfurl 1.2s cubic-bezier(0.25, 0.85, 0.4, 1) 6.6s forwards,
        flag-wave 4.5s ease-in-out 8.0s infinite;
      filter: drop-shadow(0 6px 14px rgba(0,0,0,0.45));
    }}
    @keyframes flag-unfurl {{
      0%   {{ transform: scaleX(0) skewY(0deg); opacity: 0; }}
      25%  {{ opacity: 1; }}
      100% {{ transform: scaleX(1) skewY(0deg); opacity: 1; }}
    }}
    @keyframes flag-wave {{
      0%, 100% {{ transform: scaleX(1) skewY(-0.6deg) translateY(0); }}
      50%      {{ transform: scaleX(1) skewY(0.6deg)  translateY(-2px); }}
    }}

    .sparkle {{
      position: absolute;
      top: 50%; left: 50%;
      width: 5px; height: 5px;
      margin-left: -2.5px; margin-top: -2.5px;
      border-radius: 50%;
      background: #fff;
      box-shadow: 0 0 8px #fff, 0 0 18px var(--elixir-glow);
      opacity: 0;
      animation: sparkle 3s ease-out 7.4s infinite;
    }}
    .sparkle.s2 {{ animation-delay: 7.8s;  margin-top: -{POLE_H_MINUS_20}px; margin-left: 80px; }}
    .sparkle.s3 {{ animation-delay: 8.2s;  margin-top: -{POLE_H_MINUS_60}px; margin-left: 30px; }}
    .sparkle.s4 {{ animation-delay: 8.6s;  margin-top: -{POLE_H_MINUS_30}px; margin-left: 130px; }}
    .sparkle.s5 {{ animation-delay: 9.0s;  margin-top: -{POLE_H_MINUS_80}px; margin-left: 60px; }}
    .sparkle.s1 {{                          margin-top: -{POLE_H_MINUS_50}px; margin-left: 100px; }}

    @keyframes sparkle {{
      0%   {{ opacity: 0; transform: scale(0.2) translateY(0); }}
      30%  {{ opacity: 1; transform: scale(1) translateY(-12px); }}
      100% {{ opacity: 0; transform: scale(0.3) translateY(-40px); }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      * {{ animation-duration: 0.01s !important; animation-iteration-count: 1 !important; }}
    }}

    @media (max-width: 600px) {{
      .scene {{ transform: scale(0.75); }}
    }}
  </style>
</head>
<body>
  <div class="stars"></div>

  <svg width="0" height="0" style="position:absolute" aria-hidden="true">
    <defs>
      <linearGradient id="oceanGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stop-color="#3682b4"/>
        <stop offset="50%" stop-color="#1d5584"/>
        <stop offset="100%" stop-color="#0c2d4e"/>
      </linearGradient>
      <linearGradient id="landGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stop-color="#83c470"/>
        <stop offset="55%" stop-color="#4f9a4d"/>
        <stop offset="100%" stop-color="#2c6932"/>
      </linearGradient>
      <linearGradient id="brazilGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stop-color="#d4f288"/>
        <stop offset="100%" stop-color="#6ab441"/>
      </linearGradient>
      <radialGradient id="iceGrad" cx="0.5" cy="0.5" r="0.6">
        <stop offset="0%"  stop-color="#fafdff"/>
        <stop offset="100%" stop-color="#c3d1dc"/>
      </radialGradient>

      <linearGradient id="polarTop" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stop-color="#fafdff" stop-opacity="0.98"/>
        <stop offset="55%"  stop-color="#e3ecf3" stop-opacity="0.92"/>
        <stop offset="100%" stop-color="#dde6ed" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="polarBottom" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stop-color="#dde6ed" stop-opacity="0"/>
        <stop offset="45%"  stop-color="#e3ecf3" stop-opacity="0.92"/>
        <stop offset="100%" stop-color="#fafdff" stop-opacity="0.98"/>
      </linearGradient>

      <symbol id="world-map" viewBox="0 0 880 440">
        <rect width="880" height="440" fill="url(#oceanGrad)"/>

        <g stroke="rgba(255,255,255,0.05)" stroke-width="1" fill="none">
          <line x1="0" y1="88"  x2="880" y2="88"/>
          <line x1="0" y1="132" x2="880" y2="132"/>
          <line x1="0" y1="176" x2="880" y2="176"/>
          <line x1="0" y1="220" x2="880" y2="220"/>
          <line x1="0" y1="264" x2="880" y2="264"/>
          <line x1="0" y1="308" x2="880" y2="308"/>
          <line x1="0" y1="352" x2="880" y2="352"/>
          <line x1="73"  y1="0" x2="73"  y2="440"/>
          <line x1="147" y1="0" x2="147" y2="440"/>
          <line x1="220" y1="0" x2="220" y2="440"/>
          <line x1="293" y1="0" x2="293" y2="440"/>
          <line x1="367" y1="0" x2="367" y2="440"/>
          <line x1="440" y1="0" x2="440" y2="440"/>
          <line x1="513" y1="0" x2="513" y2="440"/>
          <line x1="587" y1="0" x2="587" y2="440"/>
          <line x1="660" y1="0" x2="660" y2="440"/>
          <line x1="733" y1="0" x2="733" y2="440"/>
          <line x1="807" y1="0" x2="807" y2="440"/>
        </g>

        <path fill="url(#iceGrad)" stroke="#3a4a5e" stroke-width="1.1" stroke-linejoin="round" stroke-linecap="round" fill-rule="evenodd" d="{ice_d}"/>

        <path fill="url(#landGrad)" stroke="#0a0e0c" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round" fill-rule="evenodd" d="{land_d}"/>

        <path fill="none" stroke="#0a0e0c" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round" opacity="0.5" d="{brazil_d}"/>
        <path fill="url(#brazilGrad)" stroke="#0a0e0c" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" d="{brazil_d}"/>

        <rect x="0" y="0"   width="880" height="56" fill="url(#polarTop)"/>
        <rect x="0" y="384" width="880" height="56" fill="url(#polarBottom)"/>
      </symbol>
    </defs>
  </svg>

  <div class="scene">
    <div class="atmosphere"></div>

    <div class="globe">
      <div class="map-track">
        <svg class="map" viewBox="0 0 880 440" aria-hidden="true"><use href="#world-map"/></svg>
        <svg class="map" viewBox="0 0 880 440" aria-hidden="true"><use href="#world-map"/></svg>
        <svg class="map" viewBox="0 0 880 440" aria-hidden="true"><use href="#world-map"/></svg>
      </div>

      <svg class="wire" viewBox="-220 -220 440 440" preserveAspectRatio="none" aria-hidden="true">
        <g fill="none" stroke="#bfe3ff" stroke-width="1">
          <circle cx="0" cy="0" r="218"/>
          <ellipse cx="0" cy="-189" rx="109" ry="15"/>
          <ellipse cx="0" cy="-154" rx="156" ry="22"/>
          <ellipse cx="0" cy="-109" rx="189" ry="28"/>
          <ellipse cx="0" cy="-56"  rx="211" ry="32"/>
          <ellipse cx="0" cy="0"    rx="218" ry="34"/>
          <ellipse cx="0" cy="56"   rx="211" ry="32"/>
          <ellipse cx="0" cy="109"  rx="189" ry="28"/>
          <ellipse cx="0" cy="154"  rx="156" ry="22"/>
          <ellipse cx="0" cy="189"  rx="109" ry="15"/>
          <ellipse cx="0" cy="0" rx="56"  ry="218"/>
          <ellipse cx="0" cy="0" rx="109" ry="218"/>
          <ellipse cx="0" cy="0" rx="156" ry="218"/>
          <ellipse cx="0" cy="0" rx="189" ry="218"/>
        </g>
      </svg>

      <div class="lighting"></div>
      <div class="brazil-pulse"></div>
    </div>

    <div class="flag-wrap">
      <div class="pole"></div>

      <svg class="bobblehead" viewBox="0 0 90 90" xmlns="http://www.w3.org/2000/svg" aria-label="José Valim">
        <defs>
          <clipPath id="headClip">
            <circle cx="35" cy="28" r="26"/>
          </clipPath>
        </defs>

        <path d="M 18 56 Q 18 53, 22 53 L 48 53 Q 52 53, 52 56 L 54 90 L 16 90 Z"
              fill="#5a3270" stroke="#1a0a30" stroke-width="1.4" stroke-linejoin="round"/>

        <path d="M 28 53 L 35 62 L 42 53"
              fill="#3d1f52" stroke="#1a0a30" stroke-width="1"/>

        <path d="M 16 55 Q 13 60, 14 67 Q 19 70, 25 67 Q 25 60, 22 55 Z"
              fill="#5a3270" stroke="#1a0a30" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M 14 66 Q 13 76, 14 84 Q 17 88, 22 86 Q 24 76, 25 66 Z"
              fill="#f4d4b4" stroke="#1a0a30" stroke-width="1.2" stroke-linejoin="round"/>

        <path d="M 47 55 Q 56 53, 60 60 Q 60 65, 53 64 Q 49 60, 47 56 Z"
              fill="#5a3270" stroke="#1a0a30" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M 53 61 Q 66 59, 78 51 Q 84 52, 82 56 Q 70 64, 56 65 Z"
              fill="#f4d4b4" stroke="#1a0a30" stroke-width="1.2" stroke-linejoin="round"/>

        <ellipse cx="84" cy="50" rx="5" ry="6.5" fill="#f4d4b4" stroke="#1a0a30" stroke-width="1.2"/>

        <g class="bobble-head">
          <circle cx="35" cy="28" r="28" fill="#1a0a30"/>
          <image href="data:image/jpeg;base64,{face_b64}"
                 x="9" y="2" width="52" height="52"
                 clip-path="url(#headClip)"
                 preserveAspectRatio="xMidYMid slice"/>
          <circle cx="35" cy="28" r="26" fill="none" stroke="#1a0a30" stroke-width="1.6"/>
        </g>
      </svg>

      <div class="finial"></div>

      <svg class="flag-banner" viewBox="0 0 {FLAG_W} {FLAG_H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="fabric" x1="0" y1="0" x2="1" y2="0.2">
            <stop offset="0%"  stop-color="#fbf3fc"/>
            <stop offset="40%" stop-color="#ffffff"/>
            <stop offset="100%" stop-color="#e7d4ee"/>
          </linearGradient>
          <linearGradient id="fabricShade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"  stop-color="rgba(0,0,0,0)"/>
            <stop offset="50%" stop-color="rgba(0,0,0,0)"/>
            <stop offset="100%" stop-color="rgba(0,0,0,0.18)"/>
          </linearGradient>
          <linearGradient id="dropBody" x1="22%" y1="10%" x2="88%" y2="95%">
            <stop offset="0%"   stop-color="#a078b8"/>
            <stop offset="28%"  stop-color="#7a4e96"/>
            <stop offset="58%"  stop-color="#4a2568"/>
            <stop offset="85%"  stop-color="#28103e"/>
            <stop offset="100%" stop-color="#140622"/>
          </linearGradient>
          <linearGradient id="flameWisp" x1="35%" y1="0%" x2="45%" y2="100%">
            <stop offset="0%"   stop-color="#efdcf6" stop-opacity="0.78"/>
            <stop offset="25%"  stop-color="#c9a5dc" stop-opacity="0.55"/>
            <stop offset="60%"  stop-color="#8a5fa0" stop-opacity="0.18"/>
            <stop offset="100%" stop-color="#8a5fa0" stop-opacity="0"/>
          </linearGradient>
          <radialGradient id="bottomShine" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stop-color="#ffffff" stop-opacity="1"/>
            <stop offset="40%"  stop-color="#ffffff" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="edgeDark" cx="45%" cy="45%" r="58%">
            <stop offset="55%"  stop-color="#000" stop-opacity="0"/>
            <stop offset="92%"  stop-color="#000" stop-opacity="0.32"/>
            <stop offset="100%" stop-color="#000" stop-opacity="0.5"/>
          </radialGradient>
          <clipPath id="dropClip">
            <path d="{ELIXIR_LOGO_D}" transform="translate(53 18) scale(2)"/>
          </clipPath>
        </defs>

        <path d="M 0 2 L {FLAG_W_MINUS_14} 0 Q {FLAG_W_MINUS_4} 14, {FLAG_W_MINUS_10} 24 Q {FLAG_W_MINUS_2} 38, {FLAG_W_MINUS_8} 50 Q {FLAG_W_MINUS_1} 62, {FLAG_W_MINUS_7} 76 Q {FLAG_W_MINUS_3} 86, {FLAG_W_MINUS_14} {FLAG_H_MINUS_2} L 0 {FLAG_H} Z"
              fill="url(#fabric)" stroke="#9a7faf" stroke-width="0.6"/>

        <path d="M 0 2 L {FLAG_W_MINUS_14} 0 Q {FLAG_W_MINUS_4} 14, {FLAG_W_MINUS_10} 24 Q {FLAG_W_MINUS_2} 38, {FLAG_W_MINUS_8} 50 Q {FLAG_W_MINUS_1} 62, {FLAG_W_MINUS_7} 76 Q {FLAG_W_MINUS_3} 86, {FLAG_W_MINUS_14} {FLAG_H_MINUS_2} L 0 {FLAG_H} Z"
              fill="url(#fabricShade)" opacity="0.6"/>

        <g stroke="rgba(122, 78, 150, 0.12)" stroke-width="0.5" fill="none">
          <line x1="30" y1="2" x2="30" y2="{FLAG_H_MINUS_2}"/>
          <line x1="60" y1="2" x2="60" y2="{FLAG_H_MINUS_2}"/>
          <line x1="90" y1="2" x2="90" y2="{FLAG_H_MINUS_2}"/>
          <line x1="118" y1="2" x2="118" y2="{FLAG_H_MINUS_2}"/>
        </g>

        <rect x="0" y="0" width="6" height="{FLAG_H}" fill="#7a4e96" opacity="0.4"/>
        <circle cx="3" cy="10" r="1.6" fill="#3d1f52" opacity="0.55"/>
        <circle cx="3" cy="{FLAG_H_MINUS_10}" r="1.6" fill="#3d1f52" opacity="0.55"/>

        <g transform="translate(53 18) scale(2)">
          <path d="{ELIXIR_LOGO_D}" fill="url(#dropBody)"/>
        </g>

        <g clip-path="url(#dropClip)">
          <path d="M75 24 C68 30 60 40 56 50 C53 60 56 70 62 76 C58 68 58 56 62 46 C66 36 70 30 75 24 Z" fill="url(#flameWisp)"/>
          <path d="M82 30 C76 36 70 46 70 56 C70 65 75 73 82 76 C77 68 76 58 79 50 C82 42 84 36 82 30 Z" fill="url(#flameWisp)" opacity="0.7"/>
        </g>

        <g transform="translate(53 18) scale(2)">
          <path d="{ELIXIR_LOGO_D}" fill="url(#edgeDark)"/>
        </g>

        <ellipse cx="84" cy="68" rx="3" ry="1.5" fill="url(#bottomShine)"/>

        <g transform="translate(53 18) scale(2)">
          <path d="{ELIXIR_LOGO_D}" fill="none" stroke="#160722" stroke-width="0.18" stroke-linejoin="round" opacity="0.7"/>
        </g>
      </svg>

      <div class="sparkle s1"></div>
      <div class="sparkle s2"></div>
      <div class="sparkle s3"></div>
      <div class="sparkle s4"></div>
      <div class="sparkle s5"></div>
    </div>
  </div>
</body>
</html>
'''


def main():
    paths = build_paths()
    face_b64 = base64.b64encode((HERE / 'jose_face.jpg').read_bytes()).decode()
    html = render_html(paths, face_b64)
    out = ROOT / 'index.html'
    out.write_text(html)
    print(f'wrote {out} ({len(html)} bytes)')
    print(f'  brazil_d: {len(paths["brazil_d"])}, '
          f'land_d: {len(paths["land_d"])}, ice_d: {len(paths["ice_d"])}')


if __name__ == '__main__':
    main()
