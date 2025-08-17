# File: run_screener.py

import json
import os
import time
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from typing import List, Dict, Any, Optional, Tuple
import logging
from pykrx import stock
import FinanceDataReader as fdr


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TurtleTradingScreener:
    def __init__(self, output_file: str = 'public/data/screener_results.json'):
        self.output_file = output_file
        
        # Liquidity filters (20-day average volume)
        self.krx_min_volume = 100_000  # KRX stocks
        self.us_min_volume = 200_000   # US stocks
        
        # Turtle Trading parameters
        self.signal1_entry_period = 20    # Signal 1: 20-day breakout entry
        self.signal1_exit_period = 10     # Signal 1: 10-day exit
        self.signal2_entry_period = 55    # Signal 2: 55-day breakout entry (11 weeks)
        self.signal2_exit_period = 20     # Signal 2: 20-day exit (4 weeks)
        
        # Price filter
        self.min_price_usd = 5.0          # Minimum price for US stocks
        self.min_price_krw = 5000.0       # Minimum price for KRX stocks
        
    def get_ticker_universe(self) -> Tuple[List[str], List[str]]:
        """
        Retrieve ticker universes for both KRX and US markets.
        FRX: fetch all tickers from KOSPI/KOSDAQ
        US: fetch S&P 500/NASDAQ ticker
        The main processing loop is responsible for filtering by liquidity and price.
        Returns: (krx_tickers, us_tickers)
        """
        logger.info("Building ticker universe from public sources...")

        # KRX (Korean) stocks
        krx_tickers = []
        try:
            logger.info("Fetching KRX tickers (KOSPI, KOSDAQ)...")
            # Fetching all tickers from KOSPI and KOSDAQ
            kospi_tickers = [f"{ticker}.KS" for ticker in stock.get_market_ticker_list(market="KOSPI")]
            kosdaq_tickers = [f"{ticker}.KQ" for ticker in stock.get_market_ticker_list(market="KOSDAQ")]
            krx_tickers = kospi_tickers + kosdaq_tickers
            logger.info(f"Found {len(krx_tickers)} total KRX tickers.")
        except ImportError:
            logger.error("`pykrx` library is not installed. Please install it using `pip install pykrx` to fetch KRX tickers.")
            krx_tickers = []
        except Exception as e:
            logger.error(f"Could not fetch KRX tickers: {e}")
            krx_tickers = []

        # US stocks
        us_tickers = []
        try:
            logger.info("Fetching US tickers (NASDAQ, S&P500)")
            sp500_df = fdr.STockListing('S&P500')
            nasdaq_df = fdr.STockListing('NASDAQ')
            #Clean up for yfinance compatibility, e.g. BRK.B -> BRK-B
            sp500_df['Symbol'] = sp500_df['Symbol'].str.replace('.','-', regex=False)
            nasdaq_df['Symbol'] = nasdaq_df['Symbol'].str.replace('.','-', regex=False)
            us_tickers = sp500_df['Symbol'].tolist() + nasdaq_df['Symbol'].tolist()
            logger.info(f"Found {len(us_tickers)} total US tickers")
        except ImportError:
            logger.error("FinanceDataReader is not installed. Please install it using `pip install finance-datareader` to fetch US tickers.")
            us_tickers = []
        except Exception as e:
            logger.error(f"Could not fetch US tickers: {e}")
            us_tickers = []

        logger.info(f"Universe: {len(krx_tickers)} KRX tickers, {len(us_tickers)} US tickers")
        return krx_tickers, us_tickers
    
    def fetch_stock_data(self, ticker: str, retries: int = 3) -> Optional[pd.DataFrame]:
        """Fetch stock data with retry logic"""
        for attempt in range(retries):
            try:
                stock = yf.Ticker(ticker)
                # Fetch extended data to ensure we have enough for 55-day calculations
                end_date = datetime.now()
                start_date = end_date - timedelta(days=200)  # Buffer for weekends/holidays
                
                data = stock.history(start=start_date, end=end_date, interval='1d')
                
                if data.empty or len(data) < 60:  # Need at least 60 days for calculations
                    logger.warning(f"Insufficient data for {ticker}: {len(data) if not data.empty else 0} days")
                    return None
                
                return data
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {ticker}: {str(e)}")
                if attempt < retries - 1:
                    time.sleep(1)  # Brief pause before retry
                
        logger.error(f"Failed to fetch data for {ticker} after {retries} attempts")
        return None
    
    def calculate_turtle_signals(self, data: pd.DataFrame, ticker: str) -> Dict[str, Any]:
        """
        Calculate Extended Turtle Trading signals
        
        Signal 1: 20-day breakout entry, 10-day exit
        Signal 2: 55-day breakout entry, 20-day exit
        """
        if len(data) < self.signal2_entry_period + 1:
            logger.warning(f"Insufficient data for turtle signals: {ticker}")
            return None
            
        # Calculate rolling highs and lows for different periods
        data['High_20'] = data['High'].rolling(window=self.signal1_entry_period).max().shift(1)
        data['Low_20'] = data['Low'].rolling(window=self.signal1_entry_period).min().shift(1)
        data['Low_10'] = data['Low'].rolling(window=self.signal1_exit_period).min().shift(1)
        
        data['High_55'] = data['High'].rolling(window=self.signal2_entry_period).max().shift(1)
        data['Low_20_exit'] = data['Low'].rolling(window=self.signal2_exit_period).min().shift(1)
        
        # Calculate 20-day average volume for liquidity filter
        data['Volume_20_avg'] = data['Volume'].rolling(window=20).mean()
        
        # Get current values
        current_data = data.iloc[-1]
        current_price = float(current_data['Close'])
        current_volume_avg = float(current_data['Volume_20_avg']) if not pd.isna(current_data['Volume_20_avg']) else 0
        
        results = {
            'ticker': ticker,
            'current_price': current_price,
            'current_volume': int(current_data['Volume']),
            'volume_20_avg': int(current_volume_avg),
            'signals': {
                'signal1': {'entry': None, 'exit': None},
                'signal2': {'entry': None, 'exit': None}
            },
            'breakout_levels': {
                'high_20': float(current_data['High_20']) if not pd.isna(current_data['High_20']) else None,
                'low_20': float(current_data['Low_20']) if not pd.isna(current_data['Low_20']) else None,
                'high_55': float(current_data['High_55']) if not pd.isna(current_data['High_55']) else None,
                'low_10': float(current_data['Low_10']) if not pd.isna(current_data['Low_10']) else None,
                'low_20_exit': float(current_data['Low_20_exit']) if not pd.isna(current_data['Low_20_exit']) else None,
            }
        }
        
        # Check for Signal 1: 20-day breakout
        if (not pd.isna(current_data['High_20']) and not pd.isna(current_data['Low_20']) and 
            not pd.isna(current_data['Low_10'])):
            
            # Entry: Close breaks above 20-day high
            if current_price > current_data['High_20']:
                results['signals']['signal1']['entry'] = {
                    'type': 'BUY',
                    'price': current_price,
                    'breakout_level': float(current_data['High_20']),
                    'date': current_data.name.strftime('%Y-%m-%d'),
                    'exit_level': float(current_data['Low_10'])
                }
            
            # Exit: Close breaks below 20-day low  
            elif current_price < current_data['Low_20']:
                results['signals']['signal1']['exit'] = {
                    'type': 'SELL',
                    'price': current_price,
                    'breakdown_level': float(current_data['Low_20']),
                    'date': current_data.name.strftime('%Y-%m-%d')
                }
        
        # Check for Signal 2: 55-day breakout
        if (not pd.isna(current_data['High_55']) and not pd.isna(current_data['Low_20_exit'])):
            
            # Entry: Close breaks above 55-day high
            if current_price > current_data['High_55']:
                results['signals']['signal2']['entry'] = {
                    'type': 'BUY',
                    'price': current_price,
                    'breakout_level': float(current_data['High_55']),
                    'date': current_data.name.strftime('%Y-%m-%d'),
                    'exit_level': float(current_data['Low_20_exit'])
                }
        
        return results
    
    def passes_filters(self, analysis: Dict[str, Any]) -> bool:
        """
        Apply liquidity and price filters based on market
        """
        if not analysis:
            return False
            
        ticker = analysis['ticker']
        current_price = analysis['current_price']
        volume_avg = analysis['volume_20_avg']
        
        # Determine market and apply appropriate filters
        is_krx = ticker.endswith('.KS')
        
        if is_krx:
            # KRX filters
            if current_price < self.min_price_krw:  # Minimum 5,000 KRW
                return False
            if volume_avg < self.krx_min_volume:  # Minimum 100K shares average
                return False
        else:
            # US filters  
            if current_price < self.min_price_usd:  # Minimum $5 USD
                return False
            if volume_avg < self.us_min_volume:  # Minimum 200K shares average
                return False
        
        # Check if any signals are present
        signals = analysis['signals']
        has_signal = (signals['signal1']['entry'] is not None or 
                     signals['signal1']['exit'] is not None or
                     signals['signal2']['entry'] is not None)
        
        return has_signal
    
    def process_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Process a single ticker for Turtle Trading signals"""
        logger.info(f"Processing {ticker}")
        
        # Fetch data
        data = self.fetch_stock_data(ticker)
        if data is None:
            return None
        
        # Calculate turtle signals
        analysis = self.calculate_turtle_signals(data, ticker)
        if analysis is None:
            return None
        
        # Check filters
        if not self.passes_filters(analysis):
            return None
        
        # Format output for frontend
        return {
            'ticker': ticker,
            'market': 'KRX' if ticker.endswith('.KS') else 'US',
            'current_price': round(analysis['current_price'], 2),
            'volume_20_avg': analysis['volume_20_avg'],
            'signals': analysis['signals'],
            'breakout_levels': analysis['breakout_levels']
        }
    
    def run_screening(self) -> Dict[str, Any]:
        """Run the complete Turtle Trading screening process"""
        start_time = time.time()
        logger.info("Starting Turtle Trading screening process")
        
        # Get ticker universes
        krx_tickers, us_tickers = self.get_ticker_universe()
        all_tickers = krx_tickers + us_tickers
        
        if not all_tickers:
            logger.error("No tickers to process")
            return self._create_empty_results()
        
        # Process each ticker
        filtered_stocks = []
        errors = []
        krx_processed = 0
        us_processed = 0
        
        for ticker in all_tickers:
            try:
                result = self.process_ticker(ticker)
                if result:
                    filtered_stocks.append(result)
                    if result['market'] == 'KRX':
                        krx_processed += 1
                    else:
                        us_processed += 1
                        
            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                errors.append(ticker)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Separate signals by type for better organization
        signal1_stocks = []
        signal2_stocks = []
        
        for stock in filtered_stocks:
            if stock['signals']['signal1']['entry'] or stock['signals']['signal1']['exit']:
                signal1_stocks.append(stock)
            if stock['signals']['signal2']['entry']:
                signal2_stocks.append(stock)
        
        # Create results
        results = {
            'metadata': {
                'last_updated': datetime.utcnow().isoformat() + 'Z',
                'total_analyzed': len(all_tickers),
                'total_signals_found': len(filtered_stocks),
                'krx_analyzed': len(krx_tickers),
                'us_analyzed': len(us_tickers),
                'krx_with_signals': krx_processed,
                'us_with_signals': us_processed,
                'processing_time_seconds': round(processing_time, 2),
                'errors': errors,
                'success_rate': round((len(all_tickers) - len(errors)) / len(all_tickers) * 100, 1) if all_tickers else 0
            },
            'signal_breakdown': {
                'signal1_count': len(signal1_stocks),
                'signal2_count': len(signal2_stocks)
            },
            'filtered_stocks': sorted(filtered_stocks, key=lambda x: x['current_price'], reverse=True)
        }
        
        logger.info(f"Screening complete: {len(filtered_stocks)} stocks with Turtle signals")
        logger.info(f"Signal 1 (20-day): {len(signal1_stocks)}, Signal 2 (55-day): {len(signal2_stocks)}")
        return results
    
    def _create_empty_results(self) -> Dict[str, Any]:
        """Create empty results structure"""
        return {
            'metadata': {
                'last_updated': datetime.utcnow().isoformat() + 'Z',
                'total_analyzed': 0,
                'total_signals_found': 0,
                'krx_analyzed': 0,
                'us_analyzed': 0,
                'krx_with_signals': 0,
                'us_with_signals': 0,
                'processing_time_seconds': 0,
                'errors': [],
                'success_rate': 0
            },
            'signal_breakdown': {
                'signal1_count': 0,
                'signal2_count': 0
            },
            'filtered_stocks': []
        }
    
    def save_results(self, results: Dict[str, Any]) -> bool:
        """Save results to JSON file"""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            # Save results
            with open(self.output_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"Results saved to {self.output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            return False

def main():
    """Main execution function"""
    screener = TurtleTradingScreener()
    
    # Run screening
    results = screener.run_screening()
    
    # Save results
    success = screener.save_results(results)
    
    if success:
        logger.info("Turtle Trading screening completed successfully")
        total_signals = results['metadata']['total_signals_found']
        signal1_count = results['signal_breakdown']['signal1_count']
        signal2_count = results['signal_breakdown']['signal2_count']
        print(f"Found {total_signals} stocks with signals (Signal1: {signal1_count}, Signal2: {signal2_count})")
    else:
        logger.error("Turtle Trading screening failed")
        exit(1)

if __name__ == "__main__":
    main()