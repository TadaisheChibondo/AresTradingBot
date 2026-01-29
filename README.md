# 📈 Ares Terminal Pro v2.0

> **A production-grade algorithmic trading platform engineered for high-frequency synthetic indices markets.**

![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![Flet](https://img.shields.io/badge/GUI-Flet-purple?style=for-the-badge)
![MetaTrader 5](https://img.shields.io/badge/Execution-MetaTrader5-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Stable-green?style=for-the-badge)

## 📖 Overview

**Ares Terminal Pro** is a full-stack desktop application that bridges the gap between complex quantitative execution and user-friendly analytics. Unlike standard "headless" trading scripts, Ares features a **multithreaded Python engine** capable of processing real-time tick data across 6+ simultaneous assets without UI latency.

The system integrates institutional-grade tools typically reserved for hedge funds, including **Monte Carlo simulations** for risk modeling, **linear regression** for automated technical analysis, and a **self-healing connection protocol** for 24/7 reliability.

---

## 🚀 Key Features

### 🧠 Quantitative Engine

- **Dynamic Trendline Algorithm:** Utilizes `scipy` linear regression to identify support/resistance zones dynamically from H1 market structures.
- **Multithreaded Architecture:** Decouples the High-Frequency Trading (HFT) loop from the GUI thread, ensuring zero lag during 100+ ticks/sec data bursts.
- **Smart Risk Management:** Automatically calculates lot sizes and "Risk of Ruin" probabilities before trade execution.

### 📊 Analytics & Backtesting

- **Historical Backtester:** Reconstructs historical market states from M1 data to simulate strategy performance with 99% logic accuracy.
- **Monte Carlo Simulator:** Runs 2,000+ iterations to statistically predict portfolio survivability and drawdown probabilities.
- **Interactive Reports:** Generates professional HTML5 reports with Equity Curves, Monthly Breakdowns, and Win Rate Heatmaps using `Chart.js`.

### 🛡️ Reliability & Telemetry

- **Heartbeat Monitor:** Autonomous telemetry agent sends hourly SMTP status reports (Balance, Equity, CPU Health) via email.
- **Self-Healing Connections:** Automatically detects broker disconnections and re-establishes MT5 sessions without user intervention.
- **Standalone Distribution:** Packaged using `PyInstaller` for deployment as a single portable `.exe` file.

---

## 🛠️ Tech Stack

- **Core Logic:** Python 3.12 (AsyncIO, Multithreading)
- **Interface:** Flet (Flutter-based Python UI)
- **Data Analysis:** Pandas, NumPy, SciPy
- **Execution:** MetaTrader 5 API (Direct Market Access)
- **Visualization:** Matplotlib, Chart.js (Web Reporting)
- **Packaging:** PyInstaller (Binary Compilation)

---

## 📸 Screenshots

|                                 **Live Terminal**                                 |                              **Analytics Dashboard**                               |
| :-------------------------------------------------------------------------------: | :--------------------------------------------------------------------------------: |
|                _Real-time equity curve and multi-asset scanning._                 |                  _Monte Carlo simulations and Backtest reports._                   |
| ![Terminal Screenshot](https://via.placeholder.com/600x350?text=Ares+Terminal+UI) | ![Analytics Screenshot](https://via.placeholder.com/600x350?text=Analytics+Report) |

---

## ⚡ Installation

### Prerequisites

- Python 3.10 or higher
- MetaTrader 5 Terminal (Installed & Logged In)

### Setup

1.  **Clone the Repository**

    ```bash
    git clone [https://github.com/Tadaishe/AresTradingBot.git](https://github.com/Tadaishe/AresTradingBot.git)
    cd AresTradingBot
    ```

2.  **Create Virtual Environment**

    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Application**
    ```bash
    python main.py
    ```

---

## 🧪 How to Use

1.  **Connect:** Open the App and click **"DETECT ACCOUNT"** in the Configuration tab. Ares will auto-bind to your active MT5 terminal.
2.  **Configure:** Select which Indices (e.g., Boom 1000, Crash 500) you want to trade.
3.  **Backtest:** Go to the **Analytics** tab, select a symbol, and click **"RUN BACKTEST"** to verify the strategy on historical data.
4.  **Deploy:** Click **"START ENGINE"** on the Terminal tab. The bot will begin scanning for setups immediately.

---

## ⚠️ Disclaimer

_Trading synthetic indices involves significant risk. This software is provided for educational and research purposes only. The "Risk of Ruin" calculations are statistical probabilities, not guarantees. Use at your own risk._

---

## 👨‍💻 Author

**Tadaishe Chibondo**

- **Role:** Lead Developer & Quant Engineer
- **Specialty:** Algorithmic Trading Systems, Full-Stack Python
- **Contact:** tadaishechibondo@gmail.com

---

_Copyright © 2026 Ares Corp. All Rights Reserved._
