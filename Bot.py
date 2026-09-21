#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
import json
import math
import requests
from concurrent.futures import ThreadPoolExecutor

CONFIG = {
    "CYCLE_SEC": 60,
    "TF": "15m",
    "TOP_N": 3,
    "MIN_P": 90,
    "MIN_QVOL": 5_000_000,
    "MIN_ATR_PCT": 0.1,
    "USE_KUCOIN_LIST": True,
    "COOLDOWN_AFTER_CLOSE": 900,
    "TG_TOKEN": os.environ.get("TG_TOKEN", ""),
    "TG_CHAT": os.environ.get("TG_CHAT", ""),
    "CONCURRENCY": 8,
}

SES = requests.Session()
SF = "state_kucoin.json"
NAN = float("nan")
ISN = math.isnan

S = {"active": [], "history": [], "cool": {}}
try:
    S.update(json.load(open(SF)))
except Exception:
    pass
S.setdefault("active", [])

def save():
    try:
        json.dump(S, open(SF, "w"))
    except Exception:
        pass

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)

def fmt(x):
    if x is None or (isinstance(x, float) and ISN(x)):
        return "—"
    a = abs(float(x))
    if a == 0:
        d = 2
    elif a >= 1000:
        d = 2
    elif a >= 1:
        d = 4
    else:
        z = -int(math.floor(math.log10(a))) - 1
        d = min(8, max(4, z + 4))
    return f"{round(float(x), d):g}"

def card_signal(sym, dir_, entry, tp, sl, p_pct, slot_now, slot_max):
    arrow = "🟢 LONG" if dir_ == 1 else "🔴 SHORT"
    return (
        f"🎯 سیگنال جدید — {sym}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{arrow}\n"
        f"📍 ورود:     {fmt(entry)}\n"
        f"🎯 تارگت:    {fmt(tp)}\n"
        f"🛡 استاپ:    {fmt(sl)}\n"
        f"📊 احتمال:   {p_pct}%\n"
        f"📂 جای فعال:  {slot_now}/{slot_max}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 روی KuCoin دستی وارد شو"
    )

def card_win(sym, dir_, entry, tp, sl, px):
    arrow = "🟢 LONG" if dir_ == 1 else "🔴 SHORT"
    return (
        f"🎯 {sym} — تارگت خورد ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{arrow}\n"
        f"📍 ورود:     {fmt(entry)}\n"
        f"🎯 تارگت:    {fmt(tp)}  ← HIT\n"
        f"🛡 استاپ:    {fmt(sl)}\n"
        f"📊 قیمت:     {fmt(px)}\n"
        f"🔄 جا برای سیگنال جدید باز شد\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def card_loss(sym, dir_, entry, tp, sl, px):
    arrow = "🟢 LONG" if dir_ == 1 else "🔴 SHORT"
    return (
        f"💔 {sym} — استاپ خورد\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{arrow}\n"
        f"📍 ورود:     {fmt(entry)}\n"
        f"🎯 تارگت:    {fmt(tp)}\n"
        f"🛡 استاپ:    {fmt(sl)}  ← HIT\n"
        f"📊 قیمت:     {fmt(px)}\n"
        f"🔄 جا برای سیگنال جدید باز شد\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def card_be(sym, dir_, entry, tp, px):
    arrow = "🟢 LONG" if dir_ == 1 else "🔴 SHORT"
    return (
        f"🛡 {sym} — Breakeven\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{arrow}\n"
        f"📍 ورود:     {fmt(entry)}\n"
        f"🎯 تارگت:    {fmt(tp)}\n"
        f"🛡 استاپ:    {fmt(entry)}  ← MOVED\n"
        f"📊 قیمت:     {fmt(px)}\n"
        f"⚡ ریسک صفر شد\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def notify(card, priority="high"):
    if CONFIG["TG_TOKEN"] and CONFIG["TG_CHAT"]:
        try:
            SES.post(
                f"https://api.telegram.org/bot{CONFIG['TG_TOKEN']}/sendMessage",
                json={"chat_id": CONFIG["TG_CHAT"], "text": card},
                timeout=10,
            )
        except Exception as e:
            log(f"TG ERR {e}")
    else:
        log("TG_TOKEN یا TG_CHAT تنظیم نشده")

KU_CACHE = {"t": 0, "list": []}

def get_kucoin_symbols():
    if KU_CACHE["list"] and time.time() - KU_CACHE["t"] < 3600:
        return KU_CACHE["list"]
    try:
        r = SES.get("https://api.kucoin.com/api/v1/symbols", timeout=15)
        if r.ok:
            syms = [
                s["baseCurrency"] + "USDT"
                for s in r.json().get("data", [])
                if s.get("enableTrading") and s.get("quoteCurrency") == "USDT"
            ]
            if syms:
                KU_CACHE["t"] = time.time()
                KU_CACHE["list"] = syms
                log(f"📥 KuCoin: {len(syms)} ارز USDT")
                return syms
    except Exception as e:
        log(f"⚠ خطای KuCoin API: {e}")
    return KU_CACHE["list"] or [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "AVAXUSDT", "LINKUSDT", "DOGEUSDT", "LTCUSDT", "TRXUSDT",
        "UNIUSDT", "ATOMUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT",
        "SUIUSDT", "INJUSDT", "APTUSDT", "DOTUSDT", "FILUSDT",
    ]

def get_price(sym):
    try:
        r = SES.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}", timeout=10)
        if r.ok:
            return float(r.json()["price"])
    except Exception:
        pass
    try:
        r = SES.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}", timeout=10)
        if r.ok:
            return float(r.json()["price"])
    except Exception:
        pass
    return None

def get_klines(sym):
    u = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval={CONFIG['TF']}&limit=250"
    r = SES.get(u, timeout=20)
    if not r.ok:
        u = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={CONFIG['TF']}&limit=250"
        r = SES.get(u, timeout=20)
    r.raise_for_status()
    rows = [{
        "t": int(k[0]),
        "o": float(k[1]),
        "h": float(k[2]),
        "l": float(k[3]),
        "c": float(k[4]),
        "v": float(k[5]),
    } for k in r.json()]
    if len(rows) < 120:
        raise ValueError(sym)
    return rows

def sma(v, n):
    out = [NAN] * len(v)
    for i in range(n - 1, len(v)):
        out[i] = sum(v[i - n + 1:i + 1]) / n
    return out

def emaF(v, n):
    out = [NAN] * len(v)
    k = 2 / (n + 1)
    e = None
    c = 0
    for i, x in enumerate(v):
        if x is None or ISN(x):
            out[i] = e if e is not None else NAN
            continue
        if e is None:
            c += 1
            if c == n:
                e = sum(v[i - n + 1:i + 1]) / n
                out[i] = e
            else:
                out[i] = NAN
            continue
        e = x * k + e * (1 - k)
        out[i] = e
    return out

def atrF(h, l, c, n=14):
    out = [NAN] * len(c)
    a = None
    cnt = 0
    for i in range(1, len(c)):
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if ISN(tr):
            continue
        cnt += 1
        if cnt == n:
            s = 0.0
            for j in range(i - n + 1, i + 1):
                s += max(h[j] - l[j], abs(h[j] - c[j - 1]), abs(l[j] - c[j - 1]))
            a = s / n
        elif cnt > n:
            a = (a * (n - 1) + tr) / n
        out[i] = a
    return out

def chopF(h, l, c, n=14):
    out = [NAN] * len(c)
    for i in range(n, len(c)):
        s = 0.0
        hh = -math.inf
        ll = math.inf
        for j in range(i - n + 1, i + 1):
            s += max(h[j] - l[j], abs(h[j] - c[j - 1]), abs(l[j] - c[j - 1]))
            hh = max(hh, h[j])
            ll = min(ll, l[j])
        out[i] = 100 * math.log10(s / (hh - ll)) / math.log10(n) if (hh - ll) > 0 else 50
    return out

def cvdF(r):
    cv = 0.0
    out = []
    for x in r:
        g = (x["h"] - x["l"]) or 1e-12
        cv += ((x["c"] - x["o"]) / g) * x["v"]
        out.append(cv)
    return out

def effF(c, p=10):
    n = len(c)
    if n < p + 2:
        return 0.5
    net = abs(c[n - 2] - c[n - 2 - p])
    t = 0.0
    for i in range(n - 1 - p, n - 1):
        t += abs(c[i] - c[i - 1])
    return net / t if t > 0 else 0.5

def swingsF(r, k=3):
    hs, ls = [], []
    for i in range(k, len(r) - k):
        a = b = True
        for j in range(1, k + 1):
            if r[i]["h"] < r[i - j]["h"] or r[i]["h"] < r[i + j]["h"]:
                a = False
            if r[i]["l"] > r[i - j]["l"] or r[i]["l"] > r[i + j]["l"]:
                b = False
        if a:
            hs.append({"i": i, "p": r[i]["h"]})
        if b:
            ls.append({"i": i, "p": r[i]["l"]})
    return hs, ls

def fvgF(r):
    o = []
    for i in range(2, len(r)):
        if r[i]["l"] > r[i - 2]["h"]:
            o.append({"dir": 1, "top": r[i]["l"], "bot": r[i - 2]["h"], "i": i})
        elif r[i]["h"] < r[i - 2]["l"]:
            o.append({"dir": -1, "top": r[i - 2]["l"], "bot": r[i]["h"], "i": i})
    act = []
    for g in o:
        ok = True
        for j in range(g["i"] + 1, len(r)):
            if (g["dir"] == 1 and r[j]["c"] < g["bot"]) or (g["dir"] == -1 and r[j]["c"] > g["top"]):
                ok = False
                break
        if ok:
            act.append(g)
    return act[-3:]

def obF(r, ab):
    for i in range(len(r) - 2, max(3, len(r) - 40) - 1, -1):
        b = abs(r[i]["c"] - r[i]["o"])
        if b > 1.6 * ab:
            d = 1 if r[i]["c"] > r[i]["o"] else -1
            for j in range(i - 1, max(1, i - 6) - 1, -1):
                dj = 1 if r[j]["c"] > r[j]["o"] else -1
                if dj == -d:
                    return {
                        "dir": d,
                        "top": max(r[j]["o"], r[j]["c"]),
                        "bot": min(r[j]["o"], r[j]["c"]),
                        "i": j,
                    }
    return None

def resampleF(r, k):
    o = []
    for i in range(0, len(r) - len(r) % k, k):
        g = r[i:i + k]
        o.append({
            "o": g[0]["o"],
            "h": max(x["h"] for x in g),
            "l": min(x["l"] for x in g),
            "c": g[-1]["c"],
            "v": sum(x["v"] for x in g),
        })
    return o

def pBarrier(mu, sig, A, B):
    if not (sig > 0):
        return 0.5
    s2 = sig * sig
    if abs(mu) < 1e-12:
        return A / (A + B)
    num = 1 - math.exp(-2 * mu * A / s2)
    den = 1 - math.exp(-2 * mu * (A + B) / s2)
    if abs(den) < 1e-12:
        return A / (A + B)
    return max(0.0, min(1.0, num / den))

def analyze(rows):
    c = [r["c"] for r in rows]
    h = [r["h"] for r in rows]
    l = [r["l"] for r in rows]
    v = [r["v"] for r in rows]
    n = len(rows)
    a14 = atrF(h, l, c, 14)
    ch = chopF(h, l, c, 14)
    vs = sma(v, 20)
    cvd = cvdF(rows)
    sC, pC = rows[n - 2], rows[n - 3]
    px = rows[n - 1]["c"]
    atrV = a14[n - 2] if not ISN(a14[n - 2]) else px * 0.01
    ap = atrV / px * 100
    pv = vv = 0.0
    for i in range(n - 100, n):
        pv += ((h[i] + l[i] + c[i]) / 3) * v[i]
        vv += v[i]
    vwap = pv / vv if vv > 0 else NAN
    cvol, cavg = sC["v"], vs[n - 2]
    cvdS = cvd[n - 2] - cvd[n - 5]
    regime = "TRANSITION"
    if not ISN(ch[n - 2]):
        if ch[n - 2] < 38.2:
            regime = "TREND"
        elif ch[n - 2] > 61.8:
            regime = "RANGE"
    er = effF(c, 10)
    if regime == "TRANSITION" and ap > 4 and er < 0.2:
        regime = "RANGE"
    hsA, lsA = swingsF(rows, 3)
    hs = [s for s in hsA if s["i"] < n - 2]
    ls = [s for s in lsA if s["i"] < n - 2]
    structure = "MIXED"
    if len(hs) >= 2 and len(ls) >= 2:
        h1, h2 = hs[-2]["p"], hs[-1]["p"]
        l1, l2 = ls[-2]["p"], ls[-1]["p"]
        if h2 > h1 and l2 > l1:
            structure = "BULL"
        elif h2 < h1 and l2 < l1:
            structure = "BEAR"
    lsh = hs[-1]["p"] if hs else max(h[n - 30:n - 2])
    lsl = ls[-1]["p"] if ls else min(l[n - 30:n - 2])
    poolLow, poolHigh = math.inf, -math.inf
    for i in range(n - 20, n - 2):
        poolLow = min(poolLow, rows[i]["l"])
        poolHigh = max(poolHigh, rows[i]["h"])
    rangePos = (px - poolLow) / (poolHigh - poolLow) if (poolHigh - poolLow) > 0 else 0.5
    bullSweep = ((sC["l"] < poolLow or pC["l"] < poolLow) and sC["c"] > poolLow and sC["c"] > sC["o"])
    bearSweep = ((sC["h"] > poolHigh or pC["h"] > poolHigh) and sC["c"] < poolHigh and sC["c"] < sC["o"])
    ab = sma([abs(r["c"] - r["o"]) for r in rows], 20)[n - 2] or atrV * 0.5
    fvgs, ob = fvgF(rows), obF(rows, ab)

    def tz(d):
        for i in range(n - 6, n - 1):
            for g in fvgs:
                if g["dir"] == d and rows[i]["l"] <= g["top"] + 0.1 * atrV and rows[i]["l"] >= g["bot"] - 0.1 * atrV:
                    return 1
            if ob and ob["dir"] == d and rows[i]["l"] <= ob["top"] + 0.1 * atrV and rows[i]["l"] >= ob["bot"] - 0.1 * atrV:
                return 1
        return 0

    cr = (sC["h"] - sC["l"]) or 1e-12
    bE = sC["c"] > sC["o"] and pC["c"] < pC["o"] and sC["c"] > pC["o"] and sC["o"] <= pC["c"]
    bP = (min(sC["o"], sC["c"]) - sC["l"]) >= 2 * abs(sC["c"] - sC["o"]) and sC["c"] > sC["o"]
    sE = sC["c"] < sC["o"] and pC["c"] > pC["o"] and sC["c"] < pC["o"] and sC["o"] >= pC["c"]
    sP = (sC["h"] - max(sC["o"], sC["c"])) >= 2 * abs(sC["c"] - sC["o"]) and sC["c"] < sC["o"]
    trig = 0
    if bE or bP or (sC["c"] > sC["o"] and sC["c"] > pC["h"]):
        trig = 2
    elif sE or sP or (sC["c"] < sC["o"] and sC["c"] < pC["l"]):
        trig = -2
    elif sC["c"] > sC["o"] and sC["c"] >= sC["l"] + 0.5 * cr:
        trig = 1
    elif sC["c"] < sC["o"] and sC["c"] <= sC["h"] - 0.5 * cr:
        trig = -1
    bullT, bearT, strong = trig > 0, trig < 0, abs(trig) == 2
    disp = abs(sC["c"] - sC["o"]) > 1.5 * ab
    volX = cavg and not ISN(cavg) and cvol > cavg * 1.4
    dir_, pb = 0, ""
    if bullSweep and bullT:
        dir_, pb = 1, "SWEEP"
    elif bearSweep and bearT:
        dir_, pb = -1, "SWEEP"
    if not dir_ and (regime == "TREND" or er > 0.25):
        if structure == "BULL" and bullT and (tz(1) or strong):
            dir_, pb = 1, "PULLBACK"
        if not dir_ and structure == "BEAR" and bearT and (tz(-1) or strong):
            dir_, pb = -1, "PULLBACK"
    if not dir_ and regime != "RANGE" and (disp or volX):
        if sC["c"] > lsh and bullT:
            dir_, pb = 1, "BOS"
        elif sC["c"] < lsl and bearT:
            dir_, pb = -1, "BOS"
    if not dir_ and regime != "TREND" and bullT and rangePos <= 0.4:
        dir_, pb = 1, "FADE"
    if not dir_ and regime != "TREND" and bearT and rangePos >= 0.6:
        dir_, pb = -1, "FADE"
    if not dir_ and (volX or disp):
        d2 = 1 if sC["c"] > sC["o"] else (-1 if sC["c"] < sC["o"] else 0)
        d3 = 1 if pC["c"] > pC["o"] else (-1 if pC["c"] < pC["o"] else 0)
        if d2 and d2 == d3 and not (d2 == 1 and structure == "BEAR") and not (d2 == -1 and structure == "BULL"):
            dir_, pb = d2, "CONT"
    if not dir_ and not ISN(vwap):
        dv = px - vwap
        if dv < -2 * atrV and bullT:
            dir_, pb = 1, "VWAP"
        elif dv > 2 * atrV and bearT:
            dir_, pb = -1, "VWAP"
    if not dir_:
        w = 0.0
        if structure == "BULL":
            w += 2
        elif structure == "BEAR":
            w -= 2
        w += 1.5 if cvdS > 0 else (-1.5 if cvdS < 0 else 0)
        sd2 = ((sC["c"] - sC["o"]) / cr) * sC["v"]
        w += 1 if sd2 > 0 else (-1 if sd2 < 0 else 0)
        w += 1 if sC["c"] > sC["o"] else (-1 if sC["c"] < sC["o"] else 0)
        w += 1 if rangePos <= 0.3 else (-1 if rangePos >= 0.7 else 0)
        if not ISN(vwap):
            w += 0.5 if px > vwap else -0.5
        if w > 0.5:
            dir_, pb = 1, "HYBRID"
        elif w < -0.5:
            dir_, pb = -1, "HYBRID"
    r3l, r3h = math.inf, -math.inf
    for i in range(n - 3, n):
        r3l = min(r3l, rows[i]["l"])
        r3h = max(r3h, rows[i]["h"])
    if dir_ == 1 and px < r3l:
        dir_ = 0
    if dir_ == -1 and px > r3h:
        dir_ = 0
    sl = tp = be = None
    ds = 0.0
    if dir_:
        shelf = min(r3l, poolLow) if dir_ > 0 else max(r3h, poolHigh)
        ds = abs(px - shelf) + 0.25 * atrV
        ds = max(ds, 1.2 * atrV)
        ds = min(ds, 3.0 * atrV)
        sl = px - ds if dir_ > 0 else px + ds
        if dir_ > 0:
            a2 = [s["p"] for s in hs if s["p"] > px]
            pool = a2[0] if a2 else poolHigh
        else:
            b2 = [s["p"] for s in ls if s["p"] < px]
            pool = b2[-1] if b2 else poolLow
        dt = abs(pool - px)
        dt = min(dt, 0.8 * ds)
        dt = max(dt, 0.5 * ds)
        tp = px + dt if dir_ > 0 else px - dt
        be = px + 0.35 * ds if dir_ > 0 else px - 0.35 * ds
    m = 30
    diffs = [c[i] - c[i - 1] for i in range(n - m, n)]
    mean8 = sum(c[i] - c[i - 1] for i in range(n - 8, n)) / 8
    sd = math.sqrt(sum((x - mean8) ** 2 for x in diffs) / m)
    sd = max(sd, 0.4 * atrV)
    mu = 0.0
    if dir_:
        mu = 0.6 * dir_ * mean8
        mu += 0.08 * sd if (cvdS > 0) == (dir_ > 0) else -0.04 * sd
        mu += 0.08 * sd if volX else 0
        ht = resampleF(rows, 4)
        hc = [x["c"] for x in ht]
        he = emaF(hc, 20)
        htUp = hc[-1] > he[-1]
        mu += 0.10 * sd if ((htUp and dir_ == 1) or (not htUp and dir_ == -1)) else -0.12 * sd
        fit = (regime == "TREND" and pb in ("PULLBACK", "BOS", "CONT")) or \
              (regime == "RANGE" and pb in ("FADE", "SWEEP", "VWAP")) or pb in ("SWEEP", "HYBRID")
        mu += 0.06 * sd if fit else -0.08 * sd
        mu = max(-0.25 * sd, min(0.45 * sd, mu))
    spread = 0.0006 * px
    pShield = pBarrier(mu, sd, abs(px - sl) + spread, abs(be - px) - spread) if dir_ else 0.0
    return {"dir": dir_, "pb": pb, "entry": px, "sl": sl, "tp": tp, "be": be, "ds": ds, "p": pShield, "px": px}

def scan_one(sym):
    try:
        rows = get_klines(sym)
        n = len(rows)
        qv = sum(rows[i]["v"] * rows[i]["c"] for i in range(n - 96, n))
        if qv < CONFIG["MIN_QVOL"]:
            return None
        trs = []
        for i in range(n - 15, n):
            trs.append(max(
                rows[i]["h"] - rows[i]["l"],
                abs(rows[i]["h"] - rows[i - 1]["c"]),
                abs(rows[i]["l"] - rows[i - 1]["c"])
            ))
        atrV = sum(trs) / len(trs)
        px = rows[n - 1]["c"]
        atrPct = atrV / px * 100 if px else 0
        c12 = [rows[i]["c"] for i in range(n - 13, n - 1)]
        rng12 = max(c12) - min(c12)
        if atrPct < CONFIG["MIN_ATR_PCT"] or rng12 < 0.15 * atrV:
            return None
        return {"s": sym, "sig": analyze(rows)}
    except Exception:
        return None

def monitor_active():
    for a in list(S["active"]):
        px = get_price(a["sym"])
        if px is None:
            continue
        a["px"] = px
        sym = a["sym"].replace("USDT", "")

        if not a.get("beOn") and a.get("be"):
            if (a["dir"] == 1 and px >= a["be"]) or (a["dir"] == -1 and px <= a["be"]):
                a["sl"] = a["entry"]
                a["beOn"] = True
                log(f"🛡 {sym}: BE فعال شد")
                notify(card_be(sym, a["dir"], a["entry"], a["tp"], px))

        out = None
        if a["dir"] == 1 and px >= a["tp"]:
            out = "WIN"
        elif a["dir"] == -1 and px <= a["tp"]:
            out = "WIN"
        elif a["dir"] == 1 and px <= a["sl"]:
            out = "BE" if a.get("beOn") else "LOSS"
        elif a["dir"] == -1 and px >= a["sl"]:
            out = "BE" if a.get("beOn") else "LOSS"

        if out:
            if out == "WIN":
                notify(card_win(sym, a["dir"], a["entry"], a["tp"], a["sl"], px))
                log(f"🎯 {sym} → تارگت خورد | جا خالی شد")
            elif out == "BE":
                notify(card_be(sym, a["dir"], a["entry"], a["tp"], px))
                log(f"🛡 {sym} → BE بسته شد | جا خالی شد")
            else:
                notify(card_loss(sym, a["dir"], a["entry"], a["tp"], a["sl"], px))
                log(f"💔 {sym} → استاپ خورد | جا خالی شد")
            S["history"].insert(0, {"sym": a["sym"], "out": out, "t": time.time()})
            S["history"] = S["history"][:200]
            S["cool"][a["sym"]] = time.time() + CONFIG["COOLDOWN_AFTER_CLOSE"]
            S["active"].remove(a)
            save()

def scan_and_fill():
    slots = CONFIG["TOP_N"] - len(S["active"])
    if slots <= 0:
        log(f"📂 ظرفیت پر: {len(S['active'])}/{CONFIG['TOP_N']} فعال — اسکن جدید متوقف")
        return
    syms = get_kucoin_symbols()
    if not syms:
        return
    log(f"🔍 اسکن {len(syms)} ارز KuCoin | جاهای خالی: {slots}")
    with ThreadPoolExecutor(max_workers=CONFIG["CONCURRENCY"]) as ex:
        res_all = list(ex.map(scan_one, syms))
    res = [r for r in res_all if r]
    qual = sorted(
        [r for r in res if r["sig"]["dir"] and round(r["sig"]["p"] * 100) >= CONFIG["MIN_P"]],
        key=lambda r: -r["sig"]["p"]
    )
    log(f"✔ {len(res)} تحلیل | واجد ≥{CONFIG['MIN_P']}%: {len(qual)}")

    active_syms = {a["sym"] for a in S["active"]}
    for q in qual:
        if slots <= 0:
            break
        key = q["s"]
        if key in active_syms:
            continue
        if time.time() < S["cool"].get(key, 0):
            continue
        s = q["sig"]
        S["active"].append({
            "sym": key,
            "dir": s["dir"],
            "entry": s["px"],
            "tp": s["tp"],
            "sl": s["sl"],
            "be": s["be"],
            "beOn": False,
            "px": s["px"],
            "p": round(s["p"] * 100),
            "t": time.time(),
        })
        used = len(S["active"])
        notify(card_signal(
            key.replace("USDT", ""),
            s["dir"],
            s["px"],
            s["tp"],
            s["sl"],
            round(s["p"] * 100),
            used,
            CONFIG["TOP_N"]
        ))
        log(f"🎯 NEW {key} {'LONG' if s['dir'] == 1 else 'SHORT'} @ {fmt(s['px'])} | فعال: {used}/{CONFIG['TOP_N']}")
        active_syms.add(key)
        slots -= 1
    save()

def cycle():
    monitor_active()
    scan_and_fill()
    if S["active"]:
        parts = []
        for a in S["active"]:
            tag = "🟢" if a["dir"] == 1 else "🔴"
            parts.append(f"{tag}{a['sym'].replace('USDT', '')} @ {fmt(a.get('px'))}")
        log("ACTIVE: " + " | ".join(parts))

if __name__ == "__main__":
    log(f"🤖 ASI KuCoin v2 ▶ سقف {CONFIG['TOP_N']} پوزیشن فعال | فعال فعلی: {len(S['active'])}")
    notify(
        "🤖 ASI KuCoin v2\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 سقف فعال:    {CONFIG['TOP_N']}\n"
        f"🔓 فعال فعلی:    {len(S['active'])}\n"
        "🔄 سیگنال جدید فقط با جای خالی\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        while True:
            t0 = time.time()
            try:
                cycle()
            except Exception as e:
                log("ERR " + str(e))
            elapsed = time.time() - t0
            time.sleep(max(5, CONFIG["CYCLE_SEC"] - elapsed))
    except KeyboardInterrupt:
        save()
        log("⏸ خاموش شد — وضعیت ذخیره شد")
