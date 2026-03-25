# File: run_screener.py

import json
import os
import time
import re
from datetime import datetime, timedelta, timezone
import pandas as pd
import yfinance as yf
from typing import List, Dict, Any, Optional, Tuple
import logging
import FinanceDataReader as fdr
import certifi
from curl_cffi import requests as curl_requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TurtleTradingScreener:
    def __init__(
        self,
        output_file: str = 'public/data/screener_results.json',
        krx_classification_file: str = 'stock_classification.csv',
        no_data_cache_file: str = '.cache/yfinance_no_data_cache.json',
    ):
        self.output_file = output_file
        self.krx_classification_file = krx_classification_file
        self.no_data_cache_file = no_data_cache_file
        
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

        # KRX name changer
        self.krx_ticker_map: Dict[str, str] = {}
        self._krx_listing_lookup: Optional[Tuple[Dict[str, str], Dict[str, str]]] = None
        self._yf_rate_limited_until = 0.0

        # Downloader pacing
        self.batch_size = 50
        self.batch_pause_seconds = 1
        self.batch_failure_cooldown_seconds = 8
        self.rate_limit_cooldown_seconds = 20
        self.history_period = '240d'
        self.no_data_skip_threshold = 3
        self.no_data_skip_ttl_days = 14
        self._cache_skipped_tickers = 0
        self._yf_session = None
        self._sanitized_ca_bundle_envs: List[str] = []
        self._sanitize_ca_bundle_environment()
        self._no_data_cache = self._load_no_data_cache()

    def _find_column(self, columns: List[str], candidates: List[str]) -> Optional[str]:
        """Find first matching column name from candidates (case-insensitive)."""
        lower_map = {col.lower(): col for col in columns}
        for candidate in candidates:
            if candidate.lower() in lower_map:
                return lower_map[candidate.lower()]
        return None

    def _sanitize_ca_bundle_environment(self) -> None:
        """Replace invalid CA-bundle env vars with certifi's current bundle path."""
        certifi_bundle = certifi.where()

        for env_key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            configured_path = os.environ.get(env_key)
            if not configured_path:
                continue

            if os.path.exists(configured_path):
                continue

            logger.warning(
                f"Invalid CA bundle path in {env_key}: {configured_path}. "
                f"Overriding with certifi bundle: {certifi_bundle}"
            )
            os.environ[env_key] = certifi_bundle
            self._sanitized_ca_bundle_envs.append(env_key)

    def _get_yfinance_session(self):
        """Create a curl_cffi session pinned to certifi's bundle."""
        if self._yf_session is None:
            self._yf_session = curl_requests.Session(
                impersonate='chrome',
                verify=certifi.where(),
            )
        return self._yf_session

    def _load_no_data_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load persisted no-data ticker cache."""
        if not os.path.exists(self.no_data_cache_file):
            return {}

        try:
            with open(self.no_data_cache_file, 'r', encoding='utf-8') as f:
                payload = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read no-data cache file {self.no_data_cache_file}: {e}")
            return {}

        tickers = payload.get('tickers', {}) if isinstance(payload, dict) else {}
        return tickers if isinstance(tickers, dict) else {}

    def _save_no_data_cache(self) -> None:
        """Persist no-data ticker cache to disk."""
        os.makedirs(os.path.dirname(self.no_data_cache_file), exist_ok=True)
        payload = {
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'tickers': self._no_data_cache,
        }
        with open(self.no_data_cache_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)

    def _parse_cache_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse persisted cache timestamps safely."""
        if not value:
            return None

        text = str(value).strip()
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'

        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _cache_entry_is_active(self, entry: Dict[str, Any]) -> bool:
        """Return True when a cached no-data entry is still fresh."""
        updated_at = self._parse_cache_timestamp(entry.get('updated_at'))
        if updated_at is None:
            return False

        age = datetime.now(updated_at.tzinfo) - updated_at
        return age <= timedelta(days=self.no_data_skip_ttl_days)

    def _should_skip_ticker_from_cache(self, ticker: str) -> bool:
        """Return True when a ticker has repeatedly had no usable data recently."""
        entry = self._no_data_cache.get(ticker)
        if not entry:
            return False

        if not self._cache_entry_is_active(entry):
            self._no_data_cache.pop(ticker, None)
            return False

        return int(entry.get('count', 0)) >= self.no_data_skip_threshold

    def _record_no_data_ticker(self, ticker: str, reason: str) -> None:
        """Increment persisted no-data count for a ticker."""
        entry = self._no_data_cache.get(ticker, {})
        entry['count'] = int(entry.get('count', 0)) + 1
        entry['reason'] = reason
        entry['updated_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        self._no_data_cache[ticker] = entry

    def _clear_no_data_ticker(self, ticker: str) -> None:
        """Clear persisted no-data cache after a healthy recovery."""
        self._no_data_cache.pop(ticker, None)

    def _build_no_data_cache_summary(self) -> Dict[str, Any]:
        """Create a compact summary of persisted repeated no-data tickers."""
        active_entries = []

        for ticker, entry in list(self._no_data_cache.items()):
            if not self._cache_entry_is_active(entry):
                self._no_data_cache.pop(ticker, None)
                continue

            active_entries.append(
                {
                    'ticker': ticker,
                    'count': int(entry.get('count', 0)),
                    'reason': entry.get('reason', 'unknown'),
                    'updated_at': entry.get('updated_at'),
                }
            )

        active_entries.sort(key=lambda item: (-item['count'], item['ticker']))

        return {
            'active_entry_count': len(active_entries),
            'skip_threshold': self.no_data_skip_threshold,
            'ttl_days': self.no_data_skip_ttl_days,
            'sample': active_entries[:20],
        }

    def _normalize_krx_code(self, raw_code: Any) -> Optional[str]:
        """Normalize KRX code to 6-character uppercase alphanumeric string."""
        if pd.isna(raw_code):
            return None

        # Handle numeric values that may be parsed as float (e.g., 5930.0)
        if isinstance(raw_code, float) and raw_code.is_integer():
            return f"{int(raw_code):06d}"

        raw_str = str(raw_code).strip().upper()
        if raw_str.endswith(".0") and raw_str[:-2].isdigit():
            return raw_str[:-2].zfill(6)[-6:]

        code = re.sub(r'[^0-9A-Z]', '', raw_str)
        if not code:
            return None
        return code.zfill(6)[-6:]

    def _market_value_to_suffix(self, market_value: Any) -> Optional[str]:
        """Map KRX market text to Yahoo suffix."""
        market_val = str(market_value or "").strip().upper().replace(" ", "")
        if not market_val:
            return None

        kospi_tokens = ("KOSPI", "유가증권", "STK", "MAIN")
        kosdaq_tokens = ("KOSDAQ", "코스닥", "KSQ")

        if any(token in market_val for token in kospi_tokens):
            return ".KS"
        if any(token in market_val for token in kosdaq_tokens):
            return ".KQ"
        return None

    def _detect_market_suffix(self, row: pd.Series, market_cols: List[str], code_col: str) -> Optional[str]:
        """Detect Yahoo suffix (.KS/.KQ) from market value or raw ticker text."""
        for market_col in market_cols:
            suffix = self._market_value_to_suffix(row.get(market_col, ""))
            if suffix:
                return suffix

        # fallback 1: code column already has suffix
        code_raw = str(row.get(code_col, "")).strip().upper()
        if code_raw.endswith(".KS"):
            return ".KS"
        if code_raw.endswith(".KQ"):
            return ".KQ"

        # fallback 2: check other likely ticker columns
        for col in row.index:
            col_name = str(col).lower()
            if any(token in col_name for token in ("ticker", "symbol", "종목", "코드")):
                val = str(row.get(col, "")).strip().upper()
                if val.endswith(".KS"):
                    return ".KS"
                if val.endswith(".KQ"):
                    return ".KQ"

        return None

    def _load_krx_listing_lookup(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Load code->suffix/name lookup from FinanceDataReader KRX listing."""
        if self._krx_listing_lookup is not None:
            return self._krx_listing_lookup

        try:
            krx_df = fdr.StockListing('KRX')
        except Exception as e:
            logger.warning(f"Could not load KRX listing lookup from FinanceDataReader: {e}")
            self._krx_listing_lookup = ({}, {})
            return self._krx_listing_lookup

        if krx_df is None or krx_df.empty:
            logger.warning("FinanceDataReader returned an empty KRX listing lookup.")
            self._krx_listing_lookup = ({}, {})
            return self._krx_listing_lookup

        columns = krx_df.columns.tolist()
        code_col = self._find_column(columns, ["Code", "code", "Symbol", "symbol", "종목코드"])
        market_col = self._find_column(columns, ["Market", "market", "시장", "시장구분"])
        name_col = self._find_column(columns, ["Name", "name", "종목명", "회사명"])

        if not code_col or not market_col:
            logger.warning(
                "FinanceDataReader KRX listing is missing required columns for market lookup: "
                f"code_col={code_col}, market_col={market_col}"
            )
            self._krx_listing_lookup = ({}, {})
            return self._krx_listing_lookup

        suffix_by_code = {}
        name_by_code = {}
        unresolved_market = 0

        for _, row in krx_df.iterrows():
            code = self._normalize_krx_code(row.get(code_col))
            suffix = self._market_value_to_suffix(row.get(market_col))
            if not code or not suffix:
                if code and not suffix:
                    unresolved_market += 1
                continue

            suffix_by_code[code] = suffix

            if name_col:
                name = row.get(name_col)
                if pd.notna(name):
                    stripped_name = str(name).strip()
                    if stripped_name:
                        name_by_code[code] = stripped_name

        logger.info(
            "Loaded KRX lookup from FinanceDataReader "
            f"(codes: {len(suffix_by_code)}, unresolved_market: {unresolved_market})"
        )
        self._krx_listing_lookup = (suffix_by_code, name_by_code)
        return self._krx_listing_lookup

    def _extract_name_from_row(self, row: pd.Series, name_cols: List[str]) -> Optional[str]:
        """Extract first non-empty stock name from candidate name columns."""
        for col in name_cols:
            if col not in row.index:
                continue
            val = row.get(col)
            if pd.notna(val):
                name = str(val).strip()
                if name:
                    return name
        return None

    def _safe_int_value(self, raw_value: Any, default: int = 0) -> int:
        """Convert numeric-ish values to int without crashing on NaN."""
        if pd.isna(raw_value):
            return default

        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return default

    def _is_rate_limit_error(self, error: Any) -> bool:
        """Return True when an error message looks like upstream rate limiting."""
        message = str(error).lower()
        return any(
            token in message
            for token in ("rate limit", "too many requests", "yratelimiterror", "429")
        )

    def _apply_rate_limit_cooldown(self, seconds: Optional[int] = None) -> None:
        """Back off globally for a short period after upstream rate limiting."""
        cooldown = seconds or self.rate_limit_cooldown_seconds
        self._yf_rate_limited_until = max(self._yf_rate_limited_until, time.time() + cooldown)
        logger.warning(f"Applying yfinance cooldown for {cooldown} seconds")

    def _wait_for_rate_limit_cooldown(self) -> None:
        """Sleep until the global yfinance cooldown expires."""
        remaining = self._yf_rate_limited_until - time.time()
        if remaining > 0:
            sleep_for = int(remaining) + 1
            logger.warning(f"Waiting {sleep_for} seconds for yfinance cooldown")
            time.sleep(sleep_for)

    def _normalize_downloaded_frame(self, data: Any, ticker: str) -> Optional[pd.DataFrame]:
        """Normalize yfinance output into a single-ticker daily OHLCV frame."""
        if not isinstance(data, pd.DataFrame) or data.empty:
            return None

        frame = data.copy()

        if isinstance(frame.columns, pd.MultiIndex):
            level0 = frame.columns.get_level_values(0)
            level_last = frame.columns.get_level_values(frame.columns.nlevels - 1)

            if ticker in level0:
                frame = frame[ticker].copy()
            elif ticker in level_last:
                frame = frame.xs(ticker, axis=1, level=frame.columns.nlevels - 1, drop_level=True).copy()
            elif len(set(level_last)) == 1:
                frame.columns = level0
            elif len(set(level0)) == 1:
                frame.columns = level_last
            else:
                return None

        required_columns = {"Open", "High", "Low", "Close", "Volume"}
        if not required_columns.issubset(frame.columns):
            return None

        frame = frame.dropna(how='all')
        if frame.empty:
            return None

        return frame

    def _download_single_ticker_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        max_attempts: int = 3,
    ) -> Optional[pd.DataFrame]:
        """Retry single-ticker download for missing or malformed batch members."""
        for attempt in range(1, max_attempts + 1):
            try:
                self._wait_for_rate_limit_cooldown()
                data = yf.download(
                    ticker,
                    period=self.history_period,
                    interval='1d',
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                    session=self._get_yfinance_session(),
                )
                frame = self._normalize_downloaded_frame(data, ticker)
                if frame is not None and not frame.empty:
                    return frame
            except Exception as e:
                if self._is_rate_limit_error(e):
                    self._apply_rate_limit_cooldown()
                logger.warning(
                    f"Retry {attempt}/{max_attempts} failed for {ticker}: {e}"
                )

            if attempt < max_attempts:
                time.sleep(attempt)

        return None

    def _load_krx_from_classification_csv(self) -> List[str]:
        """
        Load KRX tickers from local classification CSV file.
        Expected to contain KOSPI/KOSDAQ classification and stock code.
        """
        if not os.path.exists(self.krx_classification_file):
            logger.warning(f"KRX classification file not found: {self.krx_classification_file}")
            return []

        read_errors = []
        df = None
        for encoding in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                df = pd.read_csv(self.krx_classification_file, encoding=encoding)
                break
            except Exception as e:
                read_errors.append(f"{encoding}: {e}")

        if df is None:
            logger.error("Failed to read KRX classification CSV. " + " | ".join(read_errors))
            return []

        if df.empty:
            logger.warning("KRX classification CSV is empty.")
            return []

        columns = df.columns.tolist()
        code_col = columns[0]
        logger.info(f"Using first CSV column as stock code column: {code_col}")

        name_candidates = ["종목명", "name", "company", "회사명", "한글종목명"]
        name_col = self._find_column(columns, name_candidates)
        name_cols = []
        for col in [name_col, *[c for c in columns if c.lower() in {n.lower() for n in name_candidates}]]:
            if col and col not in name_cols:
                name_cols.append(col)
        market_candidates = [
            "시장구분", "시장", "market", "Market", "소속부", "시장구분코드", "market_type", "market_gubun"
        ]
        market_col = self._find_column(columns, market_candidates)
        market_cols = []
        for col in [market_col, *[c for c in columns if c.lower() in {m.lower() for m in market_candidates}]]:
            if col and col not in market_cols:
                market_cols.append(col)

        krx_tickers = []
        mapped_names = 0
        skipped_unknown_market = 0
        skipped_invalid_code = 0
        listing_fallback_hits = 0
        listing_suffix_by_code = None
        listing_name_by_code = None

        for _, row in df.iterrows():
            code = self._normalize_krx_code(row.get(code_col))
            if not code:
                skipped_invalid_code += 1
                continue

            suffix = self._detect_market_suffix(row, market_cols, code_col)
            if not suffix:
                if listing_suffix_by_code is None or listing_name_by_code is None:
                    listing_suffix_by_code, listing_name_by_code = self._load_krx_listing_lookup()
                suffix = listing_suffix_by_code.get(code)
                if not suffix:
                    skipped_unknown_market += 1
                    continue
                listing_fallback_hits += 1

            full_ticker = f"{code}{suffix}"
            krx_tickers.append(full_ticker)

            stock_name = self._extract_name_from_row(row, name_cols)
            if not stock_name and listing_name_by_code:
                stock_name = listing_name_by_code.get(code)
            if stock_name:
                self.krx_ticker_map[full_ticker] = stock_name
                mapped_names += 1

        # Remove duplicates while preserving order
        unique_tickers = list(dict.fromkeys(krx_tickers))
        logger.info(
            f"Loaded {len(unique_tickers)} KRX tickers from {self.krx_classification_file} "
            f"(name mapped: {mapped_names}, invalid_code_skipped: {skipped_invalid_code}, "
            f"unknown_market_skipped: {skipped_unknown_market}, "
            f"listing_fallback_hits: {listing_fallback_hits})"
        )
        return unique_tickers
        
    def get_ticker_universe(self) -> Tuple[List[str], List[str]]:
        """
        Retrieve ticker universes for both KRX and US markets.
        KRX: fetch all tickers from KOSPI/KOSDAQ
        US: fetch S&P 500/NASDAQ ticker
        Returns: (krx_tickers, us_tickers)
        """
        logger.info("Building ticker universe from public sources...")

        # KRX (Korean) stocks from local CSV file
        logger.info("Fetching KRX tickers from stock classification CSV...")
        krx_tickers = self._load_krx_from_classification_csv()

        # US stocks
        us_tickers = []
        try:
            logger.info("Fetching US tickers (NASDAQ, S&P500)")
            sp500_df = fdr.StockListing('S&P500')
            nasdaq_df = fdr.StockListing('NASDAQ')
            # Clean up for yfinance compatibility, e.g. BRK.B -> BRK-B
            sp500_df['Symbol'] = sp500_df['Symbol'].str.replace('.', '-', regex=False)
            nasdaq_df['Symbol'] = nasdaq_df['Symbol'].str.replace('.', '-', regex=False)
            us_tickers = sp500_df['Symbol'].tolist() + nasdaq_df['Symbol'].tolist()
            # Remove duplicates
            us_tickers = list(set(us_tickers))
            logger.info(f"Found {len(us_tickers)} total US tickers")
        except ImportError:
            logger.error("FinanceDataReader is not installed. Please install it using `pip install finance-datareader` to fetch US tickers.")
            us_tickers = []
        except Exception as e:
            logger.error(f"Could not fetch US tickers: {e}")
            us_tickers = []

        logger.info(f"Universe: {len(krx_tickers)} KRX tickers, {len(us_tickers)} US tickers")
        return krx_tickers, us_tickers
    
    def calculate_turtle_signals(self, data: pd.DataFrame, ticker: str) -> Dict[str, Any]:
        """
        Calculate Extended Turtle Trading signals
        
        Signal 1: 20-day breakout entry, 10-day exit
        Signal 2: 55-day breakout entry, 20-day exit
        """
        if len(data) < self.signal2_entry_period + 1:
            logger.warning(f"Insufficient data for turtle signals: {ticker}")
            return None
        
        # 수정: .copy()를 사용하여 SettingWithCopyWarning 방지
        data = data.copy()
        
        # Calculate rolling highs and lows for different periods
        data['High_20'] = data['High'].rolling(window=self.signal1_entry_period).max().shift(1)
        data['Low_20'] = data['Low'].rolling(window=self.signal1_entry_period).min().shift(1)
        data['Low_10'] = data['Low'].rolling(window=self.signal1_exit_period).min().shift(1)
        
        data['High_55'] = data['High'].rolling(window=self.signal2_entry_period).max().shift(1)
        data['Low_20_exit'] = data['Low'].rolling(window=self.signal2_exit_period).min().shift(1)
        
        # Calculate 20-day average volume for liquidity filter
        data['Volume_20_avg'] = data['Volume'].rolling(window=20).mean()
        
        # Get current values (마지막 완성된 거래일 데이터 사용)
        current_data = data.iloc[-1]
        if pd.isna(current_data['Close']):
            logger.warning(f"Latest close is NaN, skipping {ticker}")
            return None

        current_price = float(current_data['Close'])
        current_volume = self._safe_int_value(current_data['Volume'])
        current_volume_avg = float(current_data['Volume_20_avg']) if not pd.isna(current_data['Volume_20_avg']) else 0
        
        results = {
            'ticker': ticker,
            'current_price': current_price,
            'current_volume': current_volume,
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
        is_krx = ticker.endswith('.KS') or ticker.endswith('.KQ')
        
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
    
    def download_data_safe(self, tickers: List[str]) -> Dict[str, pd.DataFrame]:
        """
        안전하게 데이터를 다운로드하여 개별 DataFrame으로 반환
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=200)
        
        # 수정: interval을 '1d'로 명시하여 일별 데이터만 가져오기
        try:
            if len(tickers) == 1:
                # 단일 티커의 경우
                frame = self._download_single_ticker_data(tickers[0], start_date, end_date)
                return {tickers[0]: frame} if frame is not None else {}
            else:
                # 다중 티커의 경우
                self._wait_for_rate_limit_cooldown()
                all_data = yf.download(
                    tickers,
                    period=self.history_period,
                    interval='1d',
                    auto_adjust=True,
                    group_by='ticker',
                    progress=False,
                    threads=False,
                    session=self._get_yfinance_session(),
                )
                
                result = {}
                for ticker in tickers:
                    try:
                        single_data = None

                        if isinstance(all_data, pd.DataFrame):
                            if isinstance(all_data.columns, pd.MultiIndex):
                                if ticker in all_data.columns.get_level_values(0):
                                    single_data = self._normalize_downloaded_frame(all_data[ticker], ticker)
                                elif ticker in all_data.columns.get_level_values(all_data.columns.nlevels - 1):
                                    extracted = all_data.xs(
                                        ticker,
                                        axis=1,
                                        level=all_data.columns.nlevels - 1,
                                        drop_level=True,
                                    )
                                    single_data = self._normalize_downloaded_frame(extracted, ticker)
                            else:
                                single_data = self._normalize_downloaded_frame(all_data, ticker)

                        if single_data is None or len(single_data) < 60:
                            recovered = self._download_single_ticker_data(ticker, start_date, end_date)
                            if recovered is not None and len(recovered) >= 60:
                                result[ticker] = recovered
                            else:
                                logger.warning(f"No data available for {ticker}")
                            continue

                        result[ticker] = single_data
                    except (KeyError, IndexError, TypeError, AttributeError) as e:
                        if self._is_rate_limit_error(e):
                            self._apply_rate_limit_cooldown()
                        logger.warning(f"Malformed batch data for {ticker}: {e}")
                        recovered = self._download_single_ticker_data(ticker, start_date, end_date)
                        if recovered is not None and len(recovered) >= 60:
                            result[ticker] = recovered
                
                return result
        except Exception as e:
            if self._is_rate_limit_error(e):
                self._apply_rate_limit_cooldown()
            logger.error(f"Error downloading data for batch: {str(e)}")
            return {}
    
    def run_screening(self) -> Dict[str, Any]:
        """Run the complete Turtle Trading screening process with improved data handling"""
        start_time = time.time()
        logger.info("Starting Turtle Trading screening process")
        if self._sanitized_ca_bundle_envs:
            logger.info(
                "Sanitized invalid CA bundle environment variables: "
                + ", ".join(self._sanitized_ca_bundle_envs)
            )
        
        # Get ticker universes
        krx_tickers, us_tickers = self.get_ticker_universe()
        
        if not krx_tickers and not us_tickers:
            logger.error("No tickers to process")
            return self._create_empty_results()
        
        all_tickers = krx_tickers + us_tickers
        
        batch_size = self.batch_size
        filtered_stocks = []
        errors = []
        krx_processed = 0
        us_processed = 0
        
        logger.info(f"Processing {len(all_tickers)} tickers in batches of {batch_size}")
        
        for i in range(0, len(all_tickers), batch_size):
            batch_tickers = all_tickers[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch_tickers)} tickers")
            active_batch_tickers = []

            for ticker in batch_tickers:
                if self._should_skip_ticker_from_cache(ticker):
                    self._cache_skipped_tickers += 1
                    logger.warning(f"Skipping cached no-data ticker: {ticker}")
                else:
                    active_batch_tickers.append(ticker)
            
            # 배치 데이터 다운로드
            batch_data = self.download_data_safe(active_batch_tickers)
            batch_missing_tickers = [ticker for ticker in active_batch_tickers if ticker not in batch_data]
            
            for ticker in batch_tickers:
                try:
                    if ticker not in active_batch_tickers:
                        continue
                    if ticker not in batch_data:
                        errors.append(ticker)
                        self._record_no_data_ticker(ticker, "download_missing")
                        continue
                    
                    single_ticker_data = batch_data[ticker]
                    
                    # 데이터가 부족한 경우 건너뛰기
                    if single_ticker_data.empty or len(single_ticker_data) < 60:
                        self._record_no_data_ticker(ticker, "insufficient_history")
                        continue
                    
                    # 터틀 신호 계산
                    analysis = self.calculate_turtle_signals(single_ticker_data, ticker)
                    
                    if analysis is None:
                        self._record_no_data_ticker(ticker, "invalid_latest_row")
                        continue

                    self._clear_no_data_ticker(ticker)

                    if not self.passes_filters(analysis):
                        continue
                    
                    # 회사명 가져오기
                    stock_name = self.krx_ticker_map.get(ticker, ticker)
                    
                    # 최종 결과 포맷팅
                    result = {
                        'ticker': ticker,
                        'name': stock_name,
                        'market': 'KRX' if ticker.endswith(('.KS', '.KQ')) else 'US',
                        'current_price': round(analysis['current_price'], 2),
                        'volume_20_avg': analysis['volume_20_avg'],
                        'signals': analysis['signals'],
                        'breakout_levels': analysis['breakout_levels']
                    }
                    
                    filtered_stocks.append(result)
                    if result['market'] == 'KRX':
                        krx_processed += 1
                    else:
                        us_processed += 1
                        
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {str(e)}")
                    errors.append(ticker)
                    self._record_no_data_ticker(ticker, "processing_error")
            
            # 배치 간 잠시 대기 (API 제한 방지)
            if i + batch_size < len(all_tickers):
                pause_seconds = self.batch_failure_cooldown_seconds if batch_missing_tickers else self.batch_pause_seconds
                if batch_missing_tickers:
                    logger.warning(
                        f"Cooling down {pause_seconds}s after batch {i//batch_size + 1} "
                        f"because {len(batch_missing_tickers)} tickers returned no usable data"
                    )
                time.sleep(pause_seconds)
        
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
                'last_updated': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'total_analyzed': len(all_tickers),
                'total_signals_found': len(filtered_stocks),
                'krx_analyzed': len(krx_tickers),
                'us_analyzed': len(us_tickers),
                'krx_with_signals': krx_processed,
                'us_with_signals': us_processed,
                'processing_time_seconds': round(processing_time, 2),
                'errors_count': len(errors),
                'cached_skip_count': self._cache_skipped_tickers,
                'no_data_cache_size': len(self._no_data_cache),
                'success_rate': round((len(all_tickers) - len(errors)) / len(all_tickers) * 100, 1) if all_tickers else 0
            },
            'signal_breakdown': {
                'signal1_count': len(signal1_stocks),
                'signal2_count': len(signal2_stocks)
            },
            'no_data_cache': self._build_no_data_cache_summary(),
            'filtered_stocks': sorted(filtered_stocks, key=lambda x: x['current_price'], reverse=True)
        }
        
        logger.info(f"Screening complete: {len(filtered_stocks)} stocks with Turtle signals")
        logger.info(f"KRX signals: {krx_processed}, US signals: {us_processed}")
        logger.info(f"Signal 1 (20-day): {len(signal1_stocks)}, Signal 2 (55-day): {len(signal2_stocks)}")
        return results
    
    def _create_empty_results(self) -> Dict[str, Any]:
        """Create empty results structure"""
        return {
            'metadata': {
                'last_updated': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'total_analyzed': 0,
                'total_signals_found': 0,
                'krx_analyzed': 0,
                'us_analyzed': 0,
                'krx_with_signals': 0,
                'us_with_signals': 0,
                'processing_time_seconds': 0,
                'errors_count': 0,
                'cached_skip_count': self._cache_skipped_tickers,
                'no_data_cache_size': len(self._no_data_cache),
                'success_rate': 0
            },
            'signal_breakdown': {
                'signal1_count': 0,
                'signal2_count': 0
            },
            'no_data_cache': self._build_no_data_cache_summary(),
            'filtered_stocks': []
        }
    
    def save_results(self, results: Dict[str, Any]) -> bool:
        """Save results to JSON file"""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            # Save results
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            self._save_no_data_cache()
            
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
        krx_signals = results['metadata']['krx_with_signals']
        us_signals = results['metadata']['us_with_signals']
        print(f"Found {total_signals} stocks with signals")
        print(f"KRX: {krx_signals}, US: {us_signals}")
        print(f"Signal1: {signal1_count}, Signal2: {signal2_count}")
    else:
        logger.error("Turtle Trading screening failed")
        exit(1)

if __name__ == "__main__":
    main()
