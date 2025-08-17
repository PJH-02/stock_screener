# Extended Turtle Trading Stock Screener

A fully automated stock screener implementing Extended Turtle Trading signals that runs entirely on GitHub infrastructure, monitoring both Korean (KRX) and US stock markets with real-time breakout detection hosted on GitHub Pages.

## 🐢 What is Turtle Trading?

The Turtle Trading system is a trend-following strategy based on breakout signals. This screener implements an extended version with two complementary signal types:

- **Signal 1 (20-day):** Buy when price breaks above 20-day high, exit when below 10-day low
- **Signal 2 (55-day):** Buy when price breaks above 55-day high, exit when below 20-day low

## 📊 Live Demo

Visit the live screener: `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME`

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

**KRX Stocks (25 tickers)**
- Samsung Electronics, SK Hynix, NAVER, Kakao
- Major financials: Shinhan, Hana, KB Financial
- Industrials: LG Chem, Hyundai Motor, POSCO
- Technology leaders and blue chips

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

### Adding More Stocks
Expand the ticker universe in `get_ticker_universe()`:
```python
# Add KRX stocks
krx_tickers = [
    '005930.KS',  # Samsung Electronics
    'YOUR_TICKER.KS',  # Add your KRX ticker here
]

# Add US stocks  
us_tickers = [
    'AAPL', 'MSFT',
    'YOUR_TICKER',  # Add your US ticker here
]
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

## 📈 Performance Considerations

### System Performance
- **Processing Time**: ~18 seconds for 67 stocks (KRX + US combined)
- **API Efficiency**: 1 call per ticker, built-in retry logic
- **Data Volume**: 200 days × 67 tickers = ~13,400 data points per run
- **Update Frequency**: Every 15 minutes during market hours

### GitHub Limitations
- **Execution Time**: 6-hour maximum per job (far more than needed)
- **API Rate Limits**: Yahoo Finance free tier, respectful usage
- **Storage**: Static JSON files, minimal repository growth
- **Concurrent Jobs**: Limited to prevent resource abuse

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

### Common Issues

**No signals appearing?**
- Turtle signals are less frequent than other indicators
- Check during high volatility periods for more breakouts
- Verify both KRX and US market hours overlap

**Workflow not running?**
- Ensure GitHub Actions are enabled in repository settings
- Check for proper YAML syntax in workflow file
- Verify the schedule aligns with market hours (UTC time)

**Data loading errors?**
- Yahoo Finance API occasionally experiences downtime
- Check network connectivity and API rate limits
- Look for error details in GitHub Actions logs

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

## 🤝 Contributing

Contributions welcome! Areas for enhancement:
- Additional markets (European, Asian stocks)
- More sophisticated position sizing rules
- Portfolio-level risk management
- Backtesting capabilities
- Performance analytics

### Development Setup
```bash
# Clone repository
git clone https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git

# Install dependencies  
pip install -r requirements.txt

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

The original Turtle Traders were selected and trained professionals trading with substantial capital and sophisticated risk management. Retail implementation requires careful consideration of these factors.# Golden Cross Stock Screener

A fully automated stock screener that runs entirely on GitHub infrastructure, detecting Golden Cross patterns in real-time and hosting results on GitHub Pages.

## 🎯 What is a Golden Cross?

A Golden Cross occurs when a stock's 50-day Simple Moving Average (SMA) crosses above its 200-day SMA, indicating potential bullish momentum. This screener automatically identifies these patterns across major US stocks.

## 📊 Live Demo

Visit the live screener: `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME`

## 🚀 Features

- **Automated Screening**: Runs every 15 minutes during market hours via GitHub Actions
- **Real-time Updates**: Fresh data automatically committed and deployed
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Dark/Light Mode**: Toggle themes with persistent preferences
- **Technical Analysis**: 50-day and 200-day SMA calculations
- **Smart Filtering**: 
  - Volume ≥ 500,000 shares
  - Price ≥ $5 (excludes penny stocks)
  - Golden Cross within last 3 trading sessions

## 🛠️ Quick Setup

1. **Fork this repository** to your GitHub account

2. **Enable GitHub Pages**:
   - Go to repository Settings → Pages
   - Source: "Deploy from a branch"
   - Branch: `main`, folder: `/public`

3. **Enable GitHub Actions**:
   - Go to repository Settings → Actions → General
   - Allow all actions and reusable workflows

4. **Customize tickers** (optional):
   - Edit `tickers.txt` to add/remove stock symbols
   - One ticker per line

5. **Deploy**:
   - Push any change to trigger first workflow run
   - Or manually trigger via Actions tab → "Stock Screener" → "Run workflow"

That's it! Your screener will be live at `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME`

## 📁 Project Structure

```
├── .github/workflows/
│   └── screener.yml          # GitHub Actions workflow
├── public/                   # Static website files
│   ├── index.html           # Main HTML page
│   ├── style.css            # Responsive CSS with dark mode
│   ├── script.js            # JavaScript app logic
│   └── data/                # Auto-generated data
│       └── screener_results.json
├── run_screener.py          # Python screening logic
├── requirements.txt         # Python dependencies
├── tickers.txt             # Stock symbols to analyze
└── README.md               # This file
```

## ⚙️ How It Works

### Backend Processing
1. **Data Collection**: Fetches 1 year of OHLCV data via Yahoo Finance API
2. **Technical Analysis**: Calculates 50-day and 200-day SMAs using pandas
3. **Pattern Detection**: Identifies Golden Cross signals in last 3 trading sessions
4. **Filtering**: Applies volume and price filters to exclude low-quality stocks
5. **Output Generation**: Creates JSON results with metadata and filtered stocks

### Frontend Application
- **Static Hosting**: Pure HTML/CSS/JavaScript hosted on GitHub Pages
- **Auto-refresh**: Updates every 15 minutes automatically
- **Responsive Design**: Mobile-first approach with CSS Grid/Flexbox
- **Theme Support**: Dark/light mode toggle with localStorage persistence
- **Error Handling**: Graceful degradation with informative error messages

### Automation Pipeline
- **Scheduled Runs**: Every 15 minutes during market hours (9:30 AM - 4:00 PM EST)
- **Smart Updates**: Only commits changes when new results are detected
- **Deployment**: Automatic GitHub Pages deployment on data changes
- **Optimization**: Cached dependencies and conditional execution

## 📋 Screening Criteria

The screener applies the following filters to identify high-quality Golden Cross signals:

| Filter | Criteria | Purpose |
|--------|----------|---------|
| **Golden Cross** | 50-day SMA crosses above 200-day SMA in last 3 sessions | Bullish technical signal |
| **Price Filter** | Stock price ≥ $5.00 | Exclude penny stocks |
| **Volume Filter** | Daily volume ≥ 500,000 shares | Ensure liquidity |
| **Data Quality** | Valid SMA calculations with sufficient history | Reliable technical analysis |

## 🔧 Configuration Options

### Customizing Tickers
Edit `tickers.txt` to modify the stock universe:
```
AAPL
MSFT
GOOGL
# Add your tickers here
```

### Adjusting Filters
Modify parameters in `run_screener.py`:
```python
self.min_volume = 500_000      # Minimum daily volume
self.min_price = 5.0           # Minimum stock price
self.lookback_days = 3         # Days to look back for Golden Cross
```

### Scheduling Changes
Update the cron schedule in `.github/workflows/screener.yml`:
```yaml
schedule:
  - cron: '*/15 14-21 * * 1-5'  # Every 15 minutes, market hours
```

## 🎨 Frontend Features

### Responsive Design
- **Mobile-first**: Optimized for smartphones and tablets
- **CSS Grid**: Dynamic layouts that adapt to screen size
- **Touch-friendly**: Large buttons and intuitive navigation

### Dark Mode Support
- **CSS Custom Properties**: Seamless theme switching
- **localStorage**: Remembers user preference
- **System Preference**: Respects OS dark mode setting

### Performance Optimizations
- **Lazy Loading**: Efficient DOM updates
- **Animations**: Smooth transitions with CSS transforms
- **Caching**: Proper HTTP headers for static assets

## 📈 Data Format

The screener outputs JSON data in the following structure:

```json
{
  "metadata": {
    "last_updated": "2025-08-12T14:00:00Z",
    "total_analyzed": 35,
    "total_passed_filters": 3,
    "processing_time_seconds": 12.34,
    "errors": ["BADTICKER"],
    "success_rate": 97.1
  },
  "filtered_stocks": [
    {
      "ticker": "AAPL",
      "cross_date": "2025-08-10",
      "current_price": 150.25,
      "volume": 75000000,
      "sma50": 148.50,
      "sma200": 145.75
    }
  ]
}
```

## 🚨 Troubleshooting

### Common Issues

**Workflow not running?**
- Check Actions are enabled in repository Settings
- Verify the workflow file is in `.github/workflows/`
- Look for syntax errors in the YAML file

**GitHub Pages not working?**
- Enable Pages in Settings → Pages
- Set source to "Deploy from a branch" → `main` → `/public`
- Wait 5-10 minutes for initial deployment

**No data showing?**
- Check the workflow logs in Actions tab
- Verify `tickers.txt` contains valid symbols
- Ensure Python dependencies are correct

**Data not updating?**
- Workflow only runs during market hours (Mon-Fri, 9:30 AM - 4:00 PM EST)
- Manual trigger available via Actions → "Run workflow"
- Check for API rate limiting from Yahoo Finance

### GitHub Actions Limitations

- **15-minute minimum**: GitHub Actions cron jobs have 15-minute granularity
- **Market hours**: Scheduled to run only during US trading hours
- **Rate limits**: Yahoo Finance API has usage limits
- **Execution time**: 6-hour maximum per job (more than sufficient)

## 🔐 Security Considerations

- **Public repository**: All code and data are publicly visible
- **No secrets required**: Uses free APIs with no authentication
- **Static hosting**: No server-side processing or databases
- **Safe dependencies**: Only well-established Python packages

## 📊 Performance Metrics

The system typically processes:
- **35 stocks** in ~12 seconds
- **API calls**: 1 per ticker (35 total)
- **Data volume**: ~252 days × 35 tickers = 8,820 data points
- **Output size**: ~2-5KB JSON file
- **Update frequency**: Every 15 minutes during market hours

## 🎯 Advanced Features

### Multi-timeframe Analysis
The system tracks Golden Cross signals across different timeframes:
- **1-day lookback**: Most recent crosses
- **3-day lookback**: Recent pattern confirmation
- **Historical tracking**: Date of actual crossover

### Statistical Insights
- **Success rate**: Percentage of tickers successfully analyzed
- **Processing metrics**: Execution time and error tracking
- **Market coverage**: Total stocks monitored

### Error Resilience
- **Retry logic**: Automatic retries for API failures
- **Graceful degradation**: Continues processing despite individual failures
- **Error reporting**: Detailed logging and user feedback

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

### Development Setup
```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git

# Install dependencies
pip install -r requirements.txt

# Run screener locally
python run_screener.py

# Serve frontend locally
cd public && python -m http.server 8000
```

## 📜 License

This project is open source and available under the MIT License.

## ⚠️ Disclaimer

This tool is for educational and informational purposes only. It is not financial advice. Golden Cross patterns are technical indicators that may not predict future price movements. Always conduct your own research and consult with financial professionals before making investment decisions.

Past performance does not guarantee future results. Stock prices can be volatile and may decline as well as advance.