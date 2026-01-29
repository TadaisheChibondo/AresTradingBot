import flet as ft
from bot.engine import TradingEngine
import time
import webbrowser
import os

def main(page: ft.Page):
    page.title = "Ares Terminal Pro"
    page.theme_mode = "dark"
    page.window_width = 1100
    page.window_height = 800
    page.padding = 0
    
    bot_engine = TradingEngine()

    # SHARED
    status_icon = ft.Icon(ft.Icons.CIRCLE, color="red", size=15)
    status_text = ft.Text(value="OFFLINE", color="grey")

    # ==========================
    # TAB 1: TERMINAL (RESIZED)
    # ==========================
    txt_live_balance = ft.Text("$0.00", size=25, weight="bold", color="green")
    txt_live_equity = ft.Text("$0.00", size=25, weight="bold", color="cyan")
    txt_live_id = ft.Text("---", size=16, color="grey")
    
    stats_container = ft.Container(
        content=ft.Row([
            ft.Column([ft.Text("Account Balance", size=12, color="grey"), txt_live_balance], alignment="center"),
            ft.Container(width=1, height=40, bgcolor="grey"),
            ft.Column([ft.Text("Live Equity", size=12, color="grey"), txt_live_equity], alignment="center"),
            ft.Container(width=1, height=40, bgcolor="grey"),
            ft.Column([ft.Text("Connected Account", size=12, color="grey"), txt_live_id], alignment="center"),
        ], alignment="spaceEvenly"),
        bgcolor="#1a1a1a", padding=15, border_radius=10
    )

    # UPDATED: Increased Height to 350
    chart_data = [ft.LineChartData(data_points=[ft.LineChartDataPoint(0, 0)], color="cyan", stroke_width=2)]
    live_chart = ft.LineChart(data_series=chart_data, min_y=0, max_y=1000, expand=True)
    chart_container = ft.Container(content=live_chart, bgcolor="#111111", height=350, padding=10, border_radius=10)

    # UPDATED: Increased Height to 250
    log_view = ft.ListView(expand=True, spacing=5, padding=10, auto_scroll=True)
    log_container = ft.Container(content=log_view, bgcolor="#111111", height=250, border_radius=10)

    def toggle_bot(e):
        if not bot_engine.is_running:
            if not bot_engine.account_info:
                 if bot_engine.connect_mt5():
                     status_text.value = "ONLINE"; status_text.color = "cyan"; status_icon.color = "cyan"
                 else:
                    page.snack_bar = ft.SnackBar(ft.Text("⚠️ Connect MT5 First!")); page.snack_bar.open=True; page.update(); return
            bot_engine.start()
            start_btn.text = "STOP ENGINE"; start_btn.icon = ft.Icons.STOP; start_btn.bgcolor = "red"
        else:
            bot_engine.stop()
            start_btn.text = "START ENGINE"; start_btn.icon = ft.Icons.PLAY_ARROW; start_btn.bgcolor = "green"
        page.update()

    start_btn = ft.ElevatedButton(text="START ENGINE", icon=ft.Icons.PLAY_ARROW, bgcolor="green", color="white", height=50, width=200, on_click=toggle_bot)

    tab_terminal = ft.Container(
        content=ft.Column([
            ft.Text("Live Dashboard", size=16, weight="bold"),
            stats_container,
            ft.Container(height=10),
            ft.Text("Real-Time Equity Curve", size=16, weight="bold"),
            chart_container,
            ft.Text("Live Logs", size=16, weight="bold"),
            log_container,
            ft.Container(start_btn, alignment=ft.alignment.center, padding=10)
        ], scroll=ft.ScrollMode.AUTO), padding=20
    )

    # ==========================
    # TAB 2: CONFIGURATION
    # ==========================
    txt_acc_status = ft.Text("Disconnected", size=16, color="grey")
    def connect_mt5_click(e):
        if bot_engine.connect_mt5():
            txt_acc_status.value = f"Connected: {bot_engine.account_info['login']}"
            txt_acc_status.color = "green"
            status_text.value = "ONLINE"; status_text.color = "cyan"; status_icon.color = "cyan"
            txt_live_id.value = str(bot_engine.account_info['login'])
            txt_live_balance.value = f"${bot_engine.account_info['balance']:,.2f}"
            txt_live_equity.value = f"${bot_engine.account_info['equity']:,.2f}"
        else:
            txt_acc_status.value = "Connection Failed"; txt_acc_status.color = "red"
        page.update()

    indices_checks = []
    for symbol in bot_engine.SYMBOLS:
        is_checked = symbol in bot_engine.config["active_indices"]
        indices_checks.append(ft.Checkbox(label=symbol, value=is_checked))

    input_email = ft.TextField(label="Gmail Address", value=bot_engine.config.get("email_address", ""), width=300)
    input_app_pass = ft.TextField(label="App Password", value=bot_engine.config.get("app_password", ""), width=300, password=True, can_reveal_password=True)
    check_email = ft.Checkbox(label="Enable Email Alerts", value=bot_engine.config.get("enable_email", False))

    def save_config(e):
        try: bot_engine.config["lot_size"] = float(input_lots.value)
        except: pass
        bot_engine.config["active_indices"] = [c.label for c in indices_checks if c.value]
        bot_engine.config["email_address"] = input_email.value
        bot_engine.config["app_password"] = input_app_pass.value
        bot_engine.config["enable_email"] = check_email.value
        bot_engine.save_settings()
        page.snack_bar = ft.SnackBar(ft.Text(f"✅ Saved!")); page.snack_bar.open=True; page.update()

    input_lots = ft.TextField(label="Lot Size", value=str(bot_engine.config["lot_size"]), width=150)
    btn_save = ft.ElevatedButton("SAVE CONFIG", icon=ft.Icons.SAVE, on_click=save_config)

    tab_config = ft.Container(
        content=ft.Column([
            ft.Text("Account Connection", size=18, weight="bold"),
            ft.Row([ft.ElevatedButton("DETECT ACCOUNT", icon=ft.Icons.REFRESH, on_click=connect_mt5_click), txt_acc_status]),
            ft.Divider(),
            ft.Text("Risk Management", size=18, weight="bold"),
            input_lots,
            ft.Divider(),
            ft.Text("Notifications", size=18, weight="bold"),
            input_email, input_app_pass, check_email,
            ft.Divider(),
            ft.Text("Active Indices", size=18, weight="bold"),
            ft.Column(indices_checks),
            ft.Container(height=20),
            btn_save
        ], scroll=ft.ScrollMode.AUTO), padding=30
    )

    # ==========================
    # TAB 3: ANALYTICS (FIXED)
    # ==========================
    txt_bt_profit = ft.Text("$0.00", size=20, weight="bold", color="white")
    txt_bt_winrate = ft.Text("0.0%", size=20, weight="bold", color="white")
    txt_bt_balance = ft.Text("$0.00", size=20, weight="bold", color="white")
    txt_bt_trades = ft.Text("0", size=20, weight="bold", color="white")

    bt_stats_container = ft.Container(
        content=ft.Row([
            ft.Column([ft.Text("Net Profit", color="grey"), txt_bt_profit], horizontal_alignment="center"),
            ft.Column([ft.Text("Win Rate", color="grey"), txt_bt_winrate], horizontal_alignment="center"),
            ft.Column([ft.Text("Final Bal", color="grey"), txt_bt_balance], horizontal_alignment="center"),
            ft.Column([ft.Text("Trades", color="grey"), txt_bt_trades], horizontal_alignment="center"),
        ], alignment="spaceEvenly"),
        bgcolor="#222222", padding=20, border_radius=10, visible=False 
    )

    dd_symbol = ft.Dropdown(options=[ft.dropdown.Option(s) for s in bot_engine.SYMBOLS], width=200, label="Symbol")
    txt_bt_status = ft.Text("Select a symbol to test.", color="grey")
    
    # 1. Run Backtest -> Updates Mini Terminal AND Opens Report
    def run_bt(e):
        if not dd_symbol.value: return
        txt_bt_status.value = "Running Simulation..."
        bt_stats_container.visible = False
        page.update()
        
        summary, report_path = bot_engine.run_backtest(dd_symbol.value) # Returns tuple now
        
        if isinstance(summary, str): 
             txt_bt_status.value = f"Error: {summary}"
        else:
            # Update UI
            txt_bt_profit.value = f"${summary['net_profit']:.2f}"
            txt_bt_profit.color = "green" if summary['net_profit'] >= 0 else "red"
            txt_bt_winrate.value = f"{summary['win_rate']:.1f}%"
            txt_bt_balance.value = f"${summary['final_balance']:.2f}"
            txt_bt_trades.value = str(summary['total_trades'])
            bt_stats_container.visible = True
            
            # Open Report
            txt_bt_status.value = "✅ Backtest Complete! Report Opened."
            webbrowser.open(f"file://{report_path}")
        page.update()

    btn_backtest = ft.ElevatedButton("RUN BACKTEST (REPORT + STATS)", icon=ft.Icons.HISTORY, on_click=run_bt)

    # 2. Run Monte Carlo -> Updates Mini Terminal AND Opens Report
    def run_mc(e):
        txt_bt_status.value = "Running Stress Test..."
        bt_stats_container.visible = False
        page.update()
        
        summary, report_path = bot_engine.run_monte_carlo() # Returns tuple now
        
        # Update UI with Median Stats
        txt_bt_profit.value = f"${summary['net_profit']:.2f}"
        txt_bt_profit.color = "green" if summary['net_profit'] >= 0 else "red"
        txt_bt_winrate.value = f"{summary['win_rate']:.1f}%"
        txt_bt_balance.value = f"${summary['final_balance']:.2f}"
        txt_bt_trades.value = str(summary['total_trades'])
        bt_stats_container.visible = True
        
        # Open Report
        webbrowser.open(f"file://{report_path}")
        txt_bt_status.value = "✅ Stress Test Complete! Report Opened."
        page.update()

    btn_mc = ft.ElevatedButton("RUN RISK SIMULATION (REPORT + STATS)", icon=ft.Icons.SHUFFLE, on_click=run_mc)

    tab_analytics = ft.Container(
        content=ft.Column([
            ft.Text("Strategy Analytics", size=18, weight="bold"),
            dd_symbol,
            ft.Container(height=10),
            ft.Row([btn_backtest, btn_mc]),
            txt_bt_status,
            ft.Divider(),
            bt_stats_container,
        ], scroll=ft.ScrollMode.AUTO), padding=30
    )

    # ==========================
    # TAB 4: ABOUT
    # ==========================
    def open_email(e): webbrowser.open("mailto:tadaishechibondo@gmail.com")
    def open_phone(e): webbrowser.open("tel:+263789956550")

    tab_about = ft.Container(
        content=ft.Column([
            ft.Container(content=ft.Column([
                ft.Icon(ft.Icons.ROCKET_LAUNCH, size=50, color="cyan"),
                ft.Text("Ares Terminal Pro", size=30, weight="bold", color="white"),
                ft.Text("Version 2.0.0 (Stable)", color="grey"),
                ft.Text("© 2026 Ares Corp. All Rights Reserved.", size=12, color="grey"),
            ], horizontal_alignment="center"), alignment=ft.alignment.center, padding=40),
            ft.Divider(),
            ft.Container(content=ft.Column([
                ft.Text("About the Developer", size=18, weight="bold"), ft.Container(height=10),
                ft.Row([ft.Icon(ft.Icons.PERSON, color="cyan"), ft.Text("Tadaishe Chibondo", size=16)]),
                ft.Text("Specialized in Algorithmic Trading Systems and High-Frequency Scalping strategies.", color="grey", size=12),
            ]), padding=20, bgcolor="#1a1a1a", border_radius=10),
            ft.Container(height=20),
            ft.Container(content=ft.Column([
                ft.Text("Contact Support", size=18, weight="bold"), ft.Container(height=10),
                ft.Row([ft.ElevatedButton("EMAIL SUPPORT", icon=ft.Icons.EMAIL, on_click=open_email), ft.ElevatedButton("CALL / WHATSAPP", icon=ft.Icons.PHONE, on_click=open_phone),])
            ]), padding=20, bgcolor="#1a1a1a", border_radius=10),
        ], scroll=ft.ScrollMode.AUTO), padding=30
    )

    # ==========================
    # MAIN ASSEMBLY
    # ==========================
    header = ft.Container(content=ft.Row([
            ft.Icon(ft.Icons.TRENDING_UP, color="cyan", size=30),
            ft.Text("ARES TERMINAL PRO", size=20, weight="bold"),
            ft.Container(expand=True), status_icon, status_text
        ]), padding=15, bgcolor="#1f2630")

    tabs = ft.Tabs(selected_index=0, tabs=[
        ft.Tab(text="TERMINAL", content=tab_terminal),
        ft.Tab(text="CONFIGURATION", content=tab_config),
        ft.Tab(text="ANALYTICS", content=tab_analytics),
        ft.Tab(text="ABOUT", content=tab_about),
    ], expand=True)

    page.add(header, tabs)

    def update_ui():
        while True:
            if bot_engine.logs:
                log_view.controls.clear()
                for log in bot_engine.logs[:30]: log_view.controls.append(ft.Text(log, font_family="Consolas", size=12))
                log_view.update()
            if bot_engine.account_info:
                 txt_live_balance.value = f"${bot_engine.account_info.get('balance', 0):,.2f}"
                 txt_live_equity.value = f"${bot_engine.account_info.get('equity', 0):,.2f}"
                 txt_live_id.value = str(bot_engine.account_info.get('login', '---'))
            if bot_engine.equity_history:
                points = [ft.LineChartDataPoint(i, pt["value"]) for i, pt in enumerate(bot_engine.equity_history)]
                live_chart.data_series[0].data_points = points
                if points:
                     vals = [p.y for p in points]
                     live_chart.min_y = min(vals) * 0.99
                     live_chart.max_y = max(vals) * 1.01
            try: page.update()
            except: pass
            time.sleep(0.5)

    page.run_thread(update_ui)

if __name__ == "__main__":
    ft.app(target=main)