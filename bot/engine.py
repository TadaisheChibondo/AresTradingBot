import MetaTrader5 as mt5
import pandas as pd
import pandas_ta_classic as ta
import numpy as np
import datetime
import time
import threading
import json
import os
import random
import smtplib
import ssl
import webbrowser
from email.message import EmailMessage
from dotenv import load_dotenv
from scipy.signal import argrelextrema

load_dotenv()


class TradingEngine:
    """
    Trend Alignment Hunter — Boom & Crash Markets
    ─────────────────────────────────────────────────
    Multi-timeframe trend-aware strategy.
    • Boom  → Long only (Buy near Support, EMA, or Oversold RSI during Uptrend)
    • Crash → Short only (Sell near Resistance, EMA, or Overbought RSI during Downtrend)
    """

    def __init__(self):
        self.is_running = False
        self.thread = None
        self.logs = []
        self.status = "OFFLINE"
        self.account_info = {}

        # Live Analytics
        self.equity_history = []
        self.max_equity = 0.0
        self.current_drawdown = 0.0
        self.last_email_time = datetime.datetime.now()

        # Daily loss guard
        self.daily_loss = 0.0
        self.last_trading_day = datetime.date.today()

        # Configuration (updated from the app's UI layer)
        self.config = {
            "risk_pct": 1.0,  
            "active_indices": [],
            "email_address": "",
            "app_password": "",
            "enable_email": False,
        }

        # ── Per-symbol fixed params ──────────────────────────────────
        self.STRATEGY_PARAMS = {
            'Boom 1000 Index': {'direction': 'BUY',  'sl': 3.5, 'cooldown': 60, 'zone': 3.0, 'ema': 8.0, 'rsi_oversold': 35, 'rsi_overbought': 65, 'magic': 100100},
            'Boom 900 Index':  {'direction': 'BUY',  'sl': 3.5, 'cooldown': 60, 'zone': 4.0, 'ema': 4.0, 'rsi_oversold': 30, 'rsi_overbought': 70, 'magic': 100900},
            'Boom 500 Index':  {'direction': 'BUY',  'sl': 3.5, 'cooldown': 60, 'zone': 5.0, 'ema': 6.0, 'rsi_oversold': 30, 'rsi_overbought': 70, 'magic': 100500},
            'Crash 1000 Index':{'direction': 'SELL', 'sl': 2.5, 'cooldown': 15, 'zone': 5.0, 'ema': 6.0, 'rsi_oversold': 30, 'rsi_overbought': 70, 'magic': 200100},
            'Crash 900 Index': {'direction': 'SELL', 'sl': 3.0, 'cooldown': 30, 'zone': 5.0, 'ema': 6.0, 'rsi_oversold': 35, 'rsi_overbought': 65, 'magic': 200900},
            'Crash 500 Index': {'direction': 'SELL', 'sl': 3.0, 'cooldown': 15, 'zone': 5.0, 'ema': 6.0, 'rsi_oversold': 30, 'rsi_overbought': 70, 'magic': 200500}
        }
        
        self.SYMBOLS = list(self.STRATEGY_PARAMS.keys())

        # Cooldown: Tracks last trade execution time per symbol
        self.cooldown_tracker = {}

        self.load_settings()
        if not self.config["active_indices"]:
            self.config["active_indices"] = self.SYMBOLS.copy()

    # ════════════════════════════════════════════════════════════════
    # UTILITY
    # ════════════════════════════════════════════════════════════════

    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)
        self.logs.insert(0, entry)
        if len(self.logs) > 100:
            self.logs.pop()

    def save_settings(self):
        try:
            with open("user_config.json", "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def load_settings(self):
        if os.path.exists("user_config.json"):
            try:
                with open("user_config.json", "r") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass

    def send_email(self, subject, body):
        if not self.config["enable_email"] or not self.config["app_password"]:
            return
        msg = EmailMessage()
        msg["From"] = self.config["email_address"]
        msg["To"]   = self.config["email_address"]
        msg["Subject"] = subject
        msg.set_content(body)
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(self.config["email_address"], self.config["app_password"])
                smtp.send_message(msg)
        except Exception:
            pass

    def _reset_daily_loss_if_new_day(self):
        today = datetime.date.today()
        if today != self.last_trading_day:
            self.daily_loss = 0.0
            self.last_trading_day = today
            self.log("📅 New trading day — daily loss counter reset.")

    # ════════════════════════════════════════════════════════════════
    # STRATEGY LOGIC
    # ════════════════════════════════════════════════════════════════

    def get_market_data(self, symbol):
        """
        Fetches dual-timeframe data for one symbol and computes all
        indicators required by the Trend Alignment Hunter strategy.
        """
        cfg = self.STRATEGY_PARAMS[symbol]

        # ── H1: Support and Resistance Zones ────────────────────────
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 500)
        if rates_h1 is None or len(rates_h1) < 20:
            self.log(f"⚠️  {symbol}: insufficient H1 data.")
            return None

        df_h1 = pd.DataFrame(rates_h1)
        n = 5
        df_h1['Swing_High'] = df_h1.iloc[argrelextrema(df_h1['high'].values, np.greater_equal, order=n)[0]]['high']
        df_h1['Swing_Low'] = df_h1.iloc[argrelextrema(df_h1['low'].values, np.less_equal, order=n)[0]]['low']
        df_h1['Active_Res'] = df_h1['Swing_High'].ffill()
        df_h1['Active_Sup'] = df_h1['Swing_Low'].ffill()

        # ── M1: Trend, RSI, and ATR Entry Triggers ──────────────────
        rates_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 300)
        if rates_m1 is None or len(rates_m1) < 250:
            self.log(f"⚠️  {symbol}: insufficient M1 data.")
            return None

        df_m1 = pd.DataFrame(rates_m1)
        df_m1['EMA20'] = ta.ema(df_m1['close'], length=20)
        df_m1['EMA50'] = ta.ema(df_m1['close'], length=50)
        df_m1['EMA200'] = ta.ema(df_m1['close'], length=200)
        df_m1['RSI'] = ta.rsi(df_m1['close'], length=14)
        df_m1['ATR'] = ta.atr(df_m1['high'], df_m1['low'], df_m1['close'], length=14)
        df_m1['ATR_SMA'] = df_m1['ATR'].rolling(window=10).mean()

        curr_m1 = df_m1.iloc[-1]
        prev_m1 = df_m1.iloc[-2]
        curr_h1 = df_h1.iloc[-1]
        
        vol_ok = curr_m1['ATR'] > curr_m1['ATR_SMA'] if not pd.isna(curr_m1['ATR_SMA']) else False

        return {
            "current_price": curr_m1['close'],
            "active_res":    curr_h1['Active_Res'],
            "active_sup":    curr_h1['Active_Sup'],
            "ema20":         curr_m1['EMA20'],
            "ema50":         curr_m1['EMA50'],
            "ema200":        curr_m1['EMA200'],
            "rsi_prev":      prev_m1['RSI'],
            "atr":           curr_m1['ATR'],
            "vol_ok":        vol_ok,
        }

    def check_entry_signal(self, symbol, data):
        """
        Evaluates the decoupled triggers with the strict trend filter.
        """
        cfg = self.STRATEGY_PARAMS[symbol]
        MODE = cfg["direction"]
        current_price = data["current_price"]

        # 1. Define Valid Zones
        zone_size = (data["atr"] * cfg["zone"]) if not pd.isna(data["atr"]) else 1.0
        near_sup = abs(current_price - data["active_sup"]) < zone_size if not pd.isna(data["active_sup"]) else False
        near_res = abs(current_price - data["active_res"]) < zone_size if not pd.isna(data["active_res"]) else False

        near_ema = (abs(current_price - data["ema20"]) < cfg["ema"]) or \
                   (abs(current_price - data["ema50"]) < cfg["ema"]) or \
                   (abs(current_price - data["ema200"]) < cfg["ema"])

        rsi_signal = data["rsi_prev"] <= cfg["rsi_oversold"] if MODE == 'BUY' else data["rsi_prev"] >= cfg["rsi_overbought"]

        # 2. Check Trend Filter
        is_uptrend = current_price > data["ema200"]
        is_downtrend = current_price < data["ema200"]
        trend_ok = (MODE == 'BUY' and is_uptrend) or (MODE == 'SELL' and is_downtrend)

        # 3. Final Evaluation
        valid_trigger = (near_sup if MODE == 'BUY' else near_res) or near_ema or rsi_signal

        if valid_trigger and data["vol_ok"] and trend_ok:
            return True
        return False

    def calculate_lot_size(self, sl_distance_points, symbol):
        """
        Dynamic position sizing based on risk %.
        """
        acc = mt5.account_info()
        if not acc:
            return 0.2  # fallback

        equity = acc.equity
        risk_amt = equity * (self.config["risk_pct"] / 100.0)

        info = mt5.symbol_info(symbol)
        if not info:
            return 0.2

        point_value_per_lot = info.point * info.trade_contract_size
        if sl_distance_points <= 0 or point_value_per_lot <= 0:
            return 0.2

        raw_lots = risk_amt / (sl_distance_points * point_value_per_lot)
        step = info.volume_step if info.volume_step > 0 else 0.01
        lots = max(info.volume_min, min(info.volume_max, raw_lots))
        lots = round(lots / step) * step
        return round(lots, 2)

    def execute_trade(self, symbol, data):
        """
        Sends a market order with fixed absolute SL distance. No hard TP to allow Quick Scalp.
        """
        cfg       = self.STRATEGY_PARAMS[symbol]
        direction = cfg["direction"]

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return

        price = tick.ask if direction == "BUY" else tick.bid
        sl_dist_abs = cfg["sl"]
        sl = price - sl_dist_abs if direction == "BUY" else price + sl_dist_abs
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        info = mt5.symbol_info(symbol)
        if not info: return
        
        sl_distance_points = sl_dist_abs / info.point
        lots = self.calculate_lot_size(sl_distance_points, symbol)

        request = {
            "action":      mt5.TRADE_ACTION_DEAL,
            "symbol":      symbol,
            "volume":      lots,
            "type":        order_type,
            "price":       price,
            "sl":          round(sl, info.digits),
            "deviation":   20,
            "magic":       cfg["magic"],
            "comment":     "TrendAlignHunter",
            "type_time":   mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            self.log(f"⚡ OPENED  {symbol} | {direction} | Entry={price:.2f}  SL={sl:.2f}  Lots={lots}")
            self.cooldown_tracker[symbol] = datetime.datetime.now()
            self.send_email(
                f"TAH Trade Opened: {symbol}",
                f"{direction} @ {price:.2f}\nSL={sl:.2f}\nLots={lots}",
            )
        else:
            code = res.retcode if res else "N/A"
            self.log(f"⚠️  Order failed: {symbol} | retcode={code}")

    def manage_positions(self):
        """
        Quick Scalp Manager: Immediately closes any position that drops into profit.
        """
        positions = mt5.positions_get()
        if not positions:
            return

        valid_magics = {p["magic"] for p in self.STRATEGY_PARAMS.values()}

        for pos in positions:
            if pos.magic not in valid_magics:
                continue

            # Quick Scalp Execution
            if pos.profit > 0:
                symbol = pos.symbol
                tick = mt5.symbol_info_tick(symbol)
                close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                
                request = {
                    "action":   mt5.TRADE_ACTION_DEAL,
                    "symbol":   symbol,
                    "volume":   pos.volume,
                    "type":     close_type,
                    "position": pos.ticket,
                    "price":    close_price,
                    "magic":    pos.magic,
                    "comment":  "Quick Scalp Exit",
                }
                res = mt5.order_send(request)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    self.log(f"🔒 CLOSED {symbol} | Quick Scalp | PnL=+{pos.profit:.2f}")

    def _position_open(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            cfg = self.STRATEGY_PARAMS.get(symbol)
            if cfg:
                return any(p.magic == cfg["magic"] for p in positions)
        return False

    def _daily_limit_breached(self):
        acc = mt5.account_info()
        if not acc:
            return False
        limit = acc.equity * 0.03
        if self.daily_loss >= limit:
            self.log(f"🚫 Daily loss limit hit (${self.daily_loss:.2f} ≥ ${limit:.2f}) — no more trades today.")
            return True
        return False

    # ════════════════════════════════════════════════════════════════
    # REPORT GENERATOR
    # ════════════════════════════════════════════════════════════════

    def generate_html_report(self, title, symbol, stats, final_bal, initial_balance):
        if not os.path.exists("reports"):
            os.makedirs("reports")

        df_trades = stats["trades_df"]
        df_monthly = stats["monthly_df"]
        max_dd = stats["max_dd_global"]
        risk_stats = stats.get("risk_stats", {})

        total_trades = len(df_trades)
        wins         = len(df_trades[df_trades["PnL"] > 0])
        win_rate     = (wins / total_trades * 100) if total_trades > 0 else 0
        net_profit   = final_bal - initial_balance
        profit_factor = 0.0
        gross_win  = df_trades[df_trades["PnL"] > 0]["PnL"].sum()
        gross_loss = abs(df_trades[df_trades["PnL"] < 0]["PnL"].sum())
        if gross_loss > 0:
            profit_factor = gross_win / gross_loss

        chart_labels = [t.strftime("%Y-%m-%d %H:%M") for t in df_trades["Time"]]
        chart_data   = df_trades["Balance"].tolist()

        risk_html = ""
        for bal, prob in risk_stats.items():
            color = "green" if prob < 1 else "orange" if prob < 10 else "red"
            risk_html += (
                f"<div class='risk-item'>"
                f"<span class='risk-label'>Start ${bal}</span>"
                f"<span class='risk-val {color}'>{prob:.1f}% Ruin</span>"
                f"</div>"
            )
        risk_section = f"<div class='risk-grid'>{risk_html}</div>" if risk_html else ""

        monthly_html = ""
        for _, row in df_monthly.iterrows():
            bg = "green" if row["Net_Profit"] >= 0 else "red"
            monthly_html += (
                f"<div class='month-card {bg}'>"
                f"<div class='month-date'>{row['Month']}</div>"
                f"<div class='month-profit'>${row['Net_Profit']:.2f}</div>"
                f"<div class='month-detail'>{row['Trades']} trades</div>"
                f"</div>"
            )

        trade_rows = ""
        for _, t in df_trades.tail(300).iterrows():
            cls = "win-text" if t["PnL"] > 0 else "loss-text"
            trade_rows += (
                f"<tr>"
                f"<td>{t['Time'].strftime('%Y-%m-%d %H:%M')}</td>"
                f"<td>{t.get('Type','–')}</td>"
                f"<td>{t.get('Entry',0):.2f}</td>"
                f"<td>{t.get('Reason','–')}</td>"
                f"<td class='{cls}'>${t['PnL']:.2f}</td>"
                f"<td>${t['Balance']:.2f}</td>"
                f"</tr>"
            )

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{title} — {symbol}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body{{font-family:'Segoe UI',sans-serif;background:#f0f2f5;color:#333;}}
  .container{{max-width:1200px;margin:40px auto;background:#fff;padding:40px;border-radius:16px;}}
  h1{{margin-bottom:8px;}} .subtitle{{color:#666;margin-bottom:24px;}}
  .stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px;}}
  .stat-card{{background:#fff;padding:24px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);text-align:center;border-left:5px solid #3498db;}}
  .stat-label{{font-size:.8em;color:#666;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;}}
  .stat-val{{font-size:1.8em;font-weight:700;}} .green{{color:#27ae60;}} .red{{color:#c0392b;}} .amber{{color:#e67e22;}}
  .risk-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px;}}
  .risk-item{{background:#fff;padding:14px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.06);text-align:center;}}
  .risk-label{{display:block;font-size:.75em;color:#888;margin-bottom:4px;}}
  .risk-val{{font-weight:700;}}
  .monthly-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:32px;}}
  .month-card{{padding:18px;border-radius:10px;color:#fff;text-align:center;}}
  .month-card.green{{background:#2ecc71;}} .month-card.red{{background:#e74c3c;}}
  .month-date{{font-size:.8em;opacity:.85;}} .month-profit{{font-size:1.3em;font-weight:700;margin:4px 0;}}
  .month-detail{{font-size:.75em;opacity:.75;}}
  table{{width:100%;border-collapse:separate;border-spacing:0;font-size:.88em;}}
  th{{background:#f8fafc;color:#4a5568;padding:14px;text-align:left;border-bottom:2px solid #edf2f7;}}
  td{{padding:11px 14px;border-bottom:1px solid #edf2f7;}}
  .win-text{{color:#27ae60;font-weight:600;}} .loss-text{{color:#e74c3c;font-weight:600;}}
  .strategy-tag{{display:inline-block;background:#2c3e50;color:#fff;padding:4px 12px;border-radius:20px;font-size:.75em;margin-bottom:20px;}}
</style></head><body><div class="container">
<h1>{title}: {symbol}</h1>
<div class="subtitle">Trend Alignment Hunter · H1/M1 Scalping</div>
<span class="strategy-tag">EMA200 Filter · Support/RSI Bounces · Quick Scalp Exit</span>
{risk_section}
<div class="stats-grid">
  <div class="stat-card"><div class="stat-label">Net Profit</div>
    <div class="stat-val {'green' if net_profit>=0 else 'red'}">${net_profit:.2f}</div></div>
  <div class="stat-card"><div class="stat-label">Win Rate</div>
    <div class="stat-val">{win_rate:.1f}%</div></div>
  <div class="stat-card"><div class="stat-label">Profit Factor</div>
    <div class="stat-val {'green' if profit_factor>=1.5 else 'amber'}">{profit_factor:.2f}</div></div>
  <div class="stat-card"><div class="stat-label">Max Drawdown</div>
    <div class="stat-val red">-${max_dd:.2f}</div></div>
  <div class="stat-card"><div class="stat-label">Total Trades</div>
    <div class="stat-val">{total_trades}</div></div>
  <div class="stat-card"><div class="stat-label">Final Balance</div>
    <div class="stat-val">${final_bal:.2f}</div></div>
</div>
<div style="margin:32px 0"><canvas id="equityChart"></canvas></div>
<h3>Monthly Performance</h3>
<div class="monthly-grid">{monthly_html}</div>
<h3>Trade History (Last 300)</h3>
<table><thead><tr>
  <th>Time</th><th>Direction</th><th>Entry</th><th>Exit Reason</th><th>PnL</th><th>Balance</th>
</tr></thead><tbody>{trade_rows}</tbody></table>
</div>
<script>
new Chart(document.getElementById('equityChart'),{{
  type:'line',
  data:{{
    labels:{chart_labels},
    datasets:[{{
      label:'Equity Curve',
      data:{chart_data},
      borderColor:'#2c3e50',borderWidth:2,
      pointRadius:0,tension:0.1,
      fill:true,backgroundColor:'rgba(44,62,80,.06)'
    }}]
  }},
  options:{{responsive:true,plugins:{{legend:{{display:false}}}},
    scales:{{x:{{display:false}},y:{{grid:{{color:'#f0f0f0'}}}}}}}}
}});
</script></body></html>"""

        filename = f"reports/TAH_{symbol.replace(' ', '_')}_{int(time.time())}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        return os.path.abspath(filename)

    # ════════════════════════════════════════════════════════════════
    # ANALYTICS ENGINES
    # ════════════════════════════════════════════════════════════════

    def run_monte_carlo(self, symbol="Portfolio", start_balance=1000.0, win_rate=0.60, reward_ratio=1.5, risk=0.01):
        trades_list = []
        balance = start_balance
        peak    = start_balance
        max_dd  = 0.0
        current_date = datetime.datetime.now()

        for i in range(300):
            current_date += datetime.timedelta(hours=2)
            is_win   = random.random() < win_rate
            risk_amt = balance * risk
            pnl      = (risk_amt * reward_ratio) if is_win else -risk_amt
            balance += pnl
            if balance > peak: peak = balance
            dd = (peak - balance) / peak * 100 if peak > 0 else 0
            if dd > max_dd: max_dd = dd

            trades_list.append({
                "Time":    current_date,
                "PnL":     pnl,
                "Balance": max(balance, 0),
                "Type":    "SIM",
                "Entry":   1000.0,
                "Reason":  "MC_Sim",
            })
            if balance <= 0: break

        risk_stats = {}
        for test_bal in [500, 1000, 2000, 5000]:
            ruined = 0
            for _ in range(1000):
                sim = test_bal
                for _ in range(300):
                    if random.random() < win_rate:
                        sim += sim * risk * reward_ratio
                    else:
                        sim -= sim * risk
                    if sim < test_bal * 0.40:
                        ruined += 1
                        break
            risk_stats[test_bal] = (ruined / 1000) * 100

        df_trades = pd.DataFrame(trades_list)
        df_trades["Time"]  = pd.to_datetime(df_trades["Time"])
        df_trades["Month"] = df_trades["Time"].dt.strftime("%Y-%m")
        monthly_data = [
            {"Month": name, "Net_Profit": g["PnL"].sum(), "Trades": len(g)}
            for name, g in df_trades.groupby("Month")
        ]
        stats = {
            "trades_df":    df_trades,
            "monthly_df":   pd.DataFrame(monthly_data),
            "max_dd_global": max_dd,
            "risk_stats":   risk_stats,
        }
        return self.generate_html_report("Monte Carlo Simulation", symbol, stats, balance, start_balance)

    def run_backtest(self, symbol, days=30):
        if not mt5.initialize(): return "MT5 Not Connected", None
        cfg = self.STRATEGY_PARAMS.get(symbol)
        if not cfg: return f"Symbol {symbol} not supported.", None

        MODE = cfg["direction"]
        utc_to = datetime.datetime.now(datetime.timezone.utc)
        utc_from = utc_to - datetime.timedelta(days=days)

        rates_h1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, utc_from - datetime.timedelta(days=10), utc_to)
        if rates_h1 is None or len(rates_h1) < 20: return "Insufficient H1 data", None
        df_h1 = pd.DataFrame(rates_h1)
        df_h1["time"] = pd.to_datetime(df_h1["time"], unit="s")
        n = 5
        df_h1['Swing_High'] = df_h1.iloc[argrelextrema(df_h1['high'].values, np.greater_equal, order=n)[0]]['high']
        df_h1['Swing_Low'] = df_h1.iloc[argrelextrema(df_h1['low'].values, np.less_equal, order=n)[0]]['low']
        df_h1['Active_Res'] = df_h1['Swing_High'].ffill()
        df_h1['Active_Sup'] = df_h1['Swing_Low'].ffill()

        rates_m1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
        if rates_m1 is None or len(rates_m1) < 300: return "Insufficient M1 data", None
        df_m1 = pd.DataFrame(rates_m1)
        df_m1["time"] = pd.to_datetime(df_m1["time"], unit="s")
        df_m1['EMA20'] = ta.ema(df_m1['close'], length=20)
        df_m1['EMA50'] = ta.ema(df_m1['close'], length=50)
        df_m1['EMA200'] = ta.ema(df_m1['close'], length=200)
        df_m1['RSI'] = ta.rsi(df_m1['close'], length=14)
        df_m1['ATR'] = ta.atr(df_m1['high'], df_m1['low'], df_m1['close'], length=14)
        df_m1['ATR_SMA'] = df_m1['ATR'].rolling(window=10).mean()
        df_m1['Vol_Expansion'] = df_m1['ATR'] > df_m1['ATR_SMA']

        # Merge H1 data down to M1 correctly
        df_final = pd.merge_asof(df_m1, df_h1[['time', 'Active_Res', 'Active_Sup']], on='time', direction='backward')
        df_final.dropna(subset=['EMA200', 'RSI', 'ATR_SMA'], inplace=True)
        df_final.reset_index(drop=True, inplace=True)

        balance = 1000.0
        peak_bal = 1000.0
        max_dd = 0.0
        trades_list = []
        
        active_pos = None
        last_trade_time = None

        for i in range(1, len(df_final)):
            row = df_final.iloc[i]
            prev_row = df_final.iloc[i-1]
            current_price = row['close']

            if active_pos:
                closed = False
                reason = ""
                pnl = 0

                if (active_pos['type'] == 'BUY' and row['low'] <= active_pos['sl']) or \
                   (active_pos['type'] == 'SELL' and row['high'] >= active_pos['sl']):
                    # Simulate dynamically calculated risk amount
                    risk_amt = balance * (self.config["risk_pct"] / 100.0)
                    pnl = -risk_amt
                    closed = True; reason = "SL Hit"
                else:
                    is_profit = (current_price > active_pos['entry']) if active_pos['type'] == 'BUY' else (current_price < active_pos['entry'])
                    if is_profit:
                        risk_amt = balance * (self.config["risk_pct"] / 100.0)
                        diff = abs(current_price - active_pos['entry'])
                        # Proportional payout based on SL size relative to risk
                        pnl = (diff / cfg['sl']) * risk_amt 
                        closed = True; reason = "Quick Scalp"

                if closed:
                    balance += pnl
                    if balance > peak_bal: peak_bal = balance
                    dd = (peak_bal - balance) / peak_bal * 100 if peak_bal > 0 else 0
                    if dd > max_dd: max_dd = dd

                    trades_list.append({
                        "Time": row['time'], "PnL": pnl, "Balance": balance,
                        "Type": active_pos['type'], "Entry": active_pos['entry'], "Reason": reason
                    })
                    active_pos = None
                continue

            if last_trade_time and (row['time'] - last_trade_time).total_seconds() / 60 < cfg['cooldown']:
                continue

            zone_size = (row['ATR'] * cfg['zone']) if not pd.isna(row['ATR']) else 1.0
            near_sup = abs(current_price - row['Active_Sup']) < zone_size if not pd.isna(row['Active_Sup']) else False
            near_res = abs(current_price - row['Active_Res']) < zone_size if not pd.isna(row['Active_Res']) else False

            near_ema = (abs(current_price - row['EMA20']) < cfg['ema']) or \
                       (abs(current_price - row['EMA50']) < cfg['ema']) or \
                       (abs(current_price - row['EMA200']) < cfg['ema'])

            rsi_signal = prev_row['RSI'] <= cfg['rsi_oversold'] if MODE == 'BUY' else prev_row['RSI'] >= cfg['rsi_overbought']
            
            is_uptrend = current_price > row['EMA200']
            is_downtrend = current_price < row['EMA200']
            trend_ok = (MODE == 'BUY' and is_uptrend) or (MODE == 'SELL' and is_downtrend)
            
            valid_trigger = (near_sup if MODE == 'BUY' else near_res) or near_ema or rsi_signal

            if valid_trigger and row['Vol_Expansion'] and trend_ok:
                last_trade_time = row['time']
                sl = current_price - cfg['sl'] if MODE == 'BUY' else current_price + cfg['sl']
                active_pos = {'type': MODE, 'entry': current_price, 'sl': sl}

        if not trades_list:
            return "No trades found in backtest window.", None

        df_trades = pd.DataFrame(trades_list)
        df_trades["Month"] = df_trades["Time"].dt.strftime("%Y-%m")
        monthly_data = [{"Month": name, "Net_Profit": g["PnL"].sum(), "Trades": len(g)} for name, g in df_trades.groupby("Month")]
        
        stats = {
            "trades_df": df_trades,
            "monthly_df": pd.DataFrame(monthly_data),
            "max_dd_global": max_dd,
        }

        report_path = self.generate_html_report("Backtest Report", symbol, stats, balance, 1000.0)
        wins = len(df_trades[df_trades["PnL"] > 0])
        n = len(df_trades)
        
        summary = {
            "net_profit": round(balance - 1000.0, 2),
            "win_rate": round(wins / n * 100, 1) if n > 0 else 0,
            "final_balance": round(balance, 2),
            "total_trades": n,
            "profit_factor": round(df_trades[df_trades["PnL"] > 0]["PnL"].sum() / abs(df_trades[df_trades["PnL"] < 0]["PnL"].sum() or 1), 2),
        }
        return summary, report_path

    # ════════════════════════════════════════════════════════════════
    # LIVE ENGINE
    # ════════════════════════════════════════════════════════════════

    def connect_mt5(self):
        try:
            if mt5.initialize():
                info = mt5.account_info()
                if info:
                    self.account_info = {
                        "name": info.name, "login": info.login, "server": info.server,
                        "balance": info.balance, "equity": info.equity, "currency": info.currency,
                    }
                    self.log(f"✅ Connected: {info.name} | Balance: {info.balance}")
                    return True
            return False
        except Exception as e:
            self.log(f"⚠️  MT5 connect error: {e}")
            return False

    def start(self):
        self.is_running = True
        self.status = "RUNNING"
        self.log("🚀 Trend Alignment Hunter started — scanning markets...")
        self.send_email("TAH Bot Started", "Engine is now online.")
        self.thread = threading.Thread(target=self._run_logic, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self.status = "STOPPED"
        self.log("🛑 Engine stopped.")
        self.send_email("TAH Bot Stopped", "Engine is offline.")

    def _run_logic(self):
        """
        Main loop: scans all active pairs every 5 seconds. Evaluates directly on the ticking candle.
        """
        while self.is_running:
            try:
                acc = mt5.account_info()
                if acc:
                    self.account_info["balance"] = acc.balance
                    self.account_info["equity"]  = acc.equity
                    self.equity_history.append({"time": time.time(), "value": acc.equity})
                    if len(self.equity_history) > 200: self.equity_history.pop(0)
                    if acc.equity > self.max_equity: self.max_equity = acc.equity
                    if self.max_equity > 0:
                        self.current_drawdown = ((self.max_equity - acc.equity) / self.max_equity * 100)

                self._reset_daily_loss_if_new_day()
                self.manage_positions()

                if not self._daily_limit_breached():
                    for symbol in self.config["active_indices"]:
                        if not self.is_running: break
                        if symbol not in self.STRATEGY_PARAMS: continue

                        if self._position_open(symbol): continue

                        last_trade_time = self.cooldown_tracker.get(symbol)
                        if last_trade_time:
                            minutes_passed = (datetime.datetime.now() - last_trade_time).total_seconds() / 60.0
                            if minutes_passed < self.STRATEGY_PARAMS[symbol]['cooldown']:
                                continue

                        self.log(f"🔍 Scanning {symbol}...")
                        data = self.get_market_data(symbol)
                        if data is None: continue

                        if self.check_entry_signal(symbol, data):
                            self.log(f"✅ SIGNAL CONFIRMED — {symbol}")
                            self.execute_trade(symbol, data)

                time.sleep(5)
            except Exception as e:
                self.log(f"⚠️  Loop error: {e}")
                time.sleep(10)