# Extended Turtle Trading Stock Screener

A fully automated stock screener implementing Extended Turtle Trading signals that runs entirely on GitHub infrastructure, monitoring both Korean (KRX) and US stock markets with real-time breakout detection hosted on GitHub Pages.

## 🐢 What is Turtle Trading?

The Turtle Trading system is a trend-following strategy based on breakout signals. This screener implements an extended version with two complementary signal types:

- **Signal 1 (20-day):** Buy when price breaks above 20-day high, exit when below 10-day low
- **Signal 2 (55-day):** Buy when price breaks above 55-day high, exit when below 20-day low

## 📊 Live Demo

Visit the live screener: `https://PJH-02.github.io/stock_screener`

## 🚀 Key Features

- **Dual Market Coverage**: Korean (KRX) and US stock markets
- **Extended Turtle Signals**: Both 20-day and 55-day breakout systems
- **Real-time Updates**: Automated every 15 minutes during market hours
- **Smart Filtering**: Different volume thresholds for KRX (100K) vs US (200K)
- **Responsive Design**: Works seamlessly on all devices
- **Zero Configuration**: Ready to deploy immediately

## 🛠️ Quick Setup

1. **Fork this repository** to your GitHub account

2. **Enable GitHub Pages**:
   - Go to repository Settings → Pages
   - Source: "Deploy from a branch"
   - Branch: `main`, folder: `/public`

3. **Enable GitHub Actions**:
   - Go to repository Settings → Actions → General
   - Allow all actions and reusable workflows

4. **Deploy**:
   - Push any change to trigger first workflow run
   - Or manually trigger via Actions tab → "Turtle Trading Screener" → "Run workflow"

Your screener will be live at `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME`

## 📁 Project Structure

```
├── .github/workflows/
│   └── screener.yml          # GitHub Actions automation
├── public/                   # Static website files
│   ├── index.html           # Turtle Trading UI
│   ├── style.css            # Responsive design with themes
│   ├── script.js            # Frontend logic for signals
│   └── data/                # Auto-generated results
│       └── screener_results.json
├── run_screener.py          # Extended Turtle Trading engine
├── stock_classification.csv # KOSPI/KOSDAQ master list (local universe source)
├── requirements.txt         # Python dependencies
└── README.md               # This documentation
```

## ⚙️ Signal Logic

### Entry Signals

**Signal 1: 20-Day Breakout**
- **Entry**: Today's close > highest close of past 20 days
- **Exit**: Price falls below lowest close of past 10 days
- **Use Case**: Faster signals, more frequent trades

**Signal 2: 55-Day Breakout (11 weeks)**  
- **Entry**: Today's close > highest close of past 55 days
- **Exit**: Price falls below lowest close of past 20 days
- **Use Case**: Longer-term trends, fewer but stronger signals

### Market-Specific Filters

| Market | Price Filter | Volume Filter | Currency |
|--------|-------------|---------------|----------|
| **KRX** | ≥ ₩5,000 | ≥ 100,000 shares (20d avg) | Korean Won |
| **US** | ≥ $5.00 | ≥ 200,000 shares (20d avg) | US Dollar |

### Stock Universe

**KRX Stocks (all listed KOSPI/KOSDAQ in `stock_classification.csv`)**
- Universe is built from local CSV to avoid pykrx dependency/runtime issues
- Tickers are normalized to Yahoo format (`.KS` for KOSPI, `.KQ` for KOSDAQ)

**US Stocks (42 tickers)**
- Mega-cap tech: AAPL, MSFT, GOOGL, AMZN, TSLA, META
- Growth companies: UBER, SHOP, ZOOM, CRWD
- Cloud/SaaS: NOW, DDOG, SNOW, ZS
- Established tech: ORCL, INTC, CSCO, QCOM

## 📊 Data Output Structure

```json
{
  "metadata": {
    "total_analyzed": 67,
    "total_signals_found": 4,
    "krx_analyzed": 25,
    "us_analyzed": 42,
    "processing_time_seconds": 18.45
  },
  "signal_breakdown": {
    "signal1_count": 2,
    "signal2_count": 2
  },
  "filtered_stocks": [
    {
      "ticker": "005930.KS",
      "market": "KRX", 
      "current_price": 72500,
      "signals": {
        "signal1": {
          "entry": {
            "type": "BUY",
            "breakout_level": 71800,
            "exit_level": 68200,
            "date": "2025-08-12"
          }
        }
      }
    }
  ]
}
```

## 🎯 Frontend Features

### Signal Visualization
- **Signal Badges**: Clear indicators for Signal 1/2 and Entry/Exit
- **Market Badges**: KRX (red) vs US (teal) identification
- **Breakout Levels**: Shows key price levels for entry and exit decisions
- **Currency Formatting**: Automatic ₩/$ formatting based on market

### Advanced UI Features
- **Dark/Light Mode**: Persistent theme switching with system preference detection
- **Real-time Stats**: Animated counters showing signal breakdown by type
- **Mobile Optimization**: Touch-friendly interface with responsive grid layouts
- **Auto-refresh**: Updates every 15 minutes with visual loading indicators
- **Error Handling**: Graceful degradation with informative error messages

## 🔧 Customization Options

### Modifying Signal Parameters
Edit parameters in `run_screener.py`:
```python
# Turtle Trading parameters
self.signal1_entry_period = 20    # Signal 1: 20-day breakout
self.signal1_exit_period = 10     # Signal 1: 10-day exit
self.signal2_entry_period = 55    # Signal 2: 55-day breakout  
self.signal2_exit_period = 20     # Signal 2: 20-day exit

# Volume filters
self.krx_min_volume = 100_000     # KRX minimum volume
self.us_min_volume = 200_000      # US minimum volume
```

### Scheduling Changes
Modify the GitHub Actions schedule:
```yaml
schedule:
  - cron: '*/15 14-21 * * 1-5'  # Every 15 min during market hours
```

## 🚨 Trading Signal Interpretation

### Signal 1 (20-day) - Short-term Momentum
- **Entry Signal**: Price breaks above 20-day high → Potential short-term uptrend
- **Exit Signal**: Price breaks below 20-day low → Short-term downtrend
- **Stop Loss**: 10-day low for positions opened on Signal 1 entry
- **Characteristics**: More frequent signals, faster response to market changes

### Signal 2 (55-day) - Long-term Trend
- **Entry Signal**: Price breaks above 55-day high → Strong long-term momentum
- **Stop Loss**: 20-day low for positions opened on Signal 2 entry  
- **Characteristics**: Fewer but potentially more reliable signals, follows major trends

### Risk Management
- **Position Sizing**: Original Turtle rules suggest 1-2% risk per position
- **Multiple Signals**: A stock can have both Signal 1 and Signal 2 active simultaneously
- **Exit Discipline**: Each signal type has its own exit rules - follow them strictly

## 🛡️ Risk Warnings

### Important Disclaimers
- **Educational Purpose**: This screener is for educational and research purposes only
- **Not Financial Advice**: Signals are technical indicators, not investment recommendations
- **Trend Following Risks**: Turtle Trading can experience extended drawdown periods
- **Whipsaw Risk**: False breakouts can trigger signals that quickly reverse
- **Market Conditions**: Works best in trending markets, struggles in sideways action

### Turtle Trading Characteristics
- **Drawdowns**: Historical Turtle systems experienced 50%+ drawdowns
- **Win Rate**: Typically 40-50% winning trades, profits from large winners
- **Psychological Challenge**: Requires discipline to follow mechanical rules
- **Market Dependency**: Performance varies significantly across different market regimes

## 🔐 Security & Privacy

- **Open Source**: All code is publicly visible on GitHub
- **No Authentication**: Uses free, public Yahoo Finance API
- **Static Hosting**: No server-side processing or user data collection
- **Safe Dependencies**: Only established, audited Python packages

## 🚨 Troubleshooting

**No signals appearing?**
- Ensure `stock_classification.csv` exists at repository root and contains KOSPI/KOSDAQ classification
- Ensure the **first CSV column** is the stock code column (e.g., `종목코드`) and includes market info column(s) like `시장구분` (or ticker values with `.KS`/`.KQ` suffix)
- Check if Yahoo Finance returns data for normalized tickers (`.KS`, `.KQ`)
- Check during high volatility periods for more breakouts

**Workflow not running?**
- Ensure GitHub Actions are enabled in repository settings
- Check for proper YAML syntax in workflow file

**Different results between runs?**
- Market data updates continuously during trading hours
- Breakout levels change as new daily highs/lows form
- This is normal behavior for real-time trading systems

## 📚 Further Learning

### Recommended Reading
- "Market Wizards" by Jack Schwager (original Turtle Traders interviews)
- "The Complete TurtleTrader" by Michael Covel
- "Way of the Turtle" by Curtis Faith (original Turtle Trader)

### Related Concepts
- **Donchian Channels**: The foundation of Turtle Trading breakouts
- **ATR (Average True Range)**: Used in original system for position sizing
- **Trend Following**: Broader category of trading strategies
- **Risk Management**: Critical for successful implementation

### Development Setup
```bash
# Clone repository
git clone https://github.com/PJH-02/stock_screener.git

# Install dependencies  
pip install -r requirements.txt

# Ensure KRX universe file exists
# stock_classification.csv (KOSPI/KOSDAQ master list)

# Test screener locally
python run_screener.py

# Serve frontend locally
cd public && python -m http.server 8000
```

## 📜 License

This project is open source and available under the MIT License.

## ⚠️ Final Disclaimer

**This is a technical analysis tool for educational purposes only.** 

The Turtle Trading system, while historically successful, involves significant risks:
- Large potential drawdowns (50%+ historically documented)
- Requires substantial capital and risk management discipline  
- Past performance does not predict future results
- Market conditions change and strategies may become less effective

**Always:**
- Conduct thorough research before making investment decisions
- Consider your risk tolerance and financial situation
- Consult with qualified financial professionals
- Never invest money you cannot afford to lose
- Understand that all trading involves risk of loss

The original Turtle Traders were selected and trained professionals trading with substantial capital and sophisticated risk management. Retail implementation requires careful consideration of these factors.
