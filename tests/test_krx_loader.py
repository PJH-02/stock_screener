import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from run_screener import TurtleTradingScreener


class KRXLoaderTests(unittest.TestCase):
    def test_normalize_krx_code_preserves_alphanumeric_codes(self):
        screener = TurtleTradingScreener()

        self.assertEqual(screener._normalize_krx_code("0001A0"), "0001A0")
        self.assertEqual(screener._normalize_krx_code("5930"), "005930")
        self.assertEqual(screener._normalize_krx_code(5930.0), "005930")

    def test_load_krx_from_classification_csv_uses_listing_fallback_without_market_column(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "stock_classification.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["종목코드", "종목명", "대분류"])
                writer.writerow(["005930", "삼성전자", "제조"])
                writer.writerow(["000250", "삼천당제약", "제조"])
                writer.writerow(["0001A0", "덕양에너젠", "유틸리티"])

            listing_df = pd.DataFrame(
                [
                    {"Code": "005930", "Market": "KOSPI", "Name": "삼성전자"},
                    {"Code": "000250", "Market": "KOSDAQ", "Name": "삼천당제약"},
                    {"Code": "0001A0", "Market": "KOSDAQ", "Name": "덕양에너젠"},
                ]
            )

            screener = TurtleTradingScreener(krx_classification_file=str(csv_path))
            with patch("run_screener.fdr.StockListing", return_value=listing_df) as mock_stock_listing:
                tickers = screener._load_krx_from_classification_csv()

            self.assertEqual(tickers, ["005930.KS", "000250.KQ", "0001A0.KQ"])
            self.assertEqual(screener.krx_ticker_map["005930.KS"], "삼성전자")
            self.assertEqual(screener.krx_ticker_map["000250.KQ"], "삼천당제약")
            self.assertEqual(screener.krx_ticker_map["0001A0.KQ"], "덕양에너젠")
            mock_stock_listing.assert_called_once_with("KRX")

    def test_calculate_turtle_signals_tolerates_nan_latest_volume(self):
        screener = TurtleTradingScreener()
        data = pd.DataFrame(
            {
                "High": [100 + i for i in range(60)],
                "Low": [90 + i for i in range(60)],
                "Close": [95 + i for i in range(60)],
                "Volume": [100000 + i for i in range(59)] + [float("nan")],
            },
            index=pd.date_range("2025-01-01", periods=60, freq="D"),
        )

        result = screener.calculate_turtle_signals(data, "000300.KS")

        self.assertIsNotNone(result)
        self.assertEqual(result["current_volume"], 0)

    def test_normalize_downloaded_frame_flattens_single_ticker_multiindex(self):
        screener = TurtleTradingScreener()
        dates = pd.date_range("2025-01-01", periods=3, freq="D")
        columns = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Volume"], ["000300.KS"]],
            names=["Price", "Ticker"],
        )
        data = pd.DataFrame(
            [
                [10, 11, 9, 10, 1000],
                [11, 12, 10, 11, 1100],
                [float("nan"), float("nan"), float("nan"), float("nan"), float("nan")],
            ],
            index=dates,
            columns=columns,
        )

        normalized = screener._normalize_downloaded_frame(data, "000300.KS")

        self.assertIsNotNone(normalized)
        self.assertEqual(list(normalized.columns), ["Open", "High", "Low", "Close", "Volume"])
        self.assertEqual(len(normalized), 2)

    def test_download_data_safe_recovers_missing_batch_member_with_single_ticker_retry(self):
        screener = TurtleTradingScreener()
        dates = pd.date_range("2025-01-01", periods=65, freq="D")

        good_batch = pd.DataFrame(
            {
                ("000020.KS", "Open"): range(65),
                ("000020.KS", "High"): range(1, 66),
                ("000020.KS", "Low"): range(65),
                ("000020.KS", "Close"): range(1, 66),
                ("000020.KS", "Volume"): [100000] * 65,
            },
            index=dates,
        )
        recovered_single = pd.DataFrame(
            {
                "Open": range(65),
                "High": range(1, 66),
                "Low": range(65),
                "Close": range(1, 66),
                "Volume": [120000] * 65,
            },
            index=dates,
        )

        download_calls = []

        def fake_download(tickers, **kwargs):
            download_calls.append(tickers)
            if isinstance(tickers, list):
                return good_batch
            if tickers == "000300.KS":
                return recovered_single
            return pd.DataFrame()

        with patch("run_screener.yf.download", side_effect=fake_download):
            result = screener.download_data_safe(["000020.KS", "000300.KS"])

        self.assertEqual(set(result.keys()), {"000020.KS", "000300.KS"})
        self.assertEqual(len(result["000020.KS"]), 65)
        self.assertEqual(len(result["000300.KS"]), 65)
        self.assertIn(["000020.KS", "000300.KS"], download_calls)
        self.assertIn("000300.KS", download_calls)

    def test_download_single_ticker_applies_rate_limit_cooldown_before_retry(self):
        screener = TurtleTradingScreener()
        dates = pd.date_range("2025-01-01", periods=65, freq="D")
        recovered_single = pd.DataFrame(
            {
                "Open": range(65),
                "High": range(1, 66),
                "Low": range(65),
                "Close": range(1, 66),
                "Volume": [120000] * 65,
            },
            index=dates,
        )

        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("run_screener.yf.download", side_effect=[Exception("Too Many Requests"), recovered_single]):
            with patch("run_screener.time.sleep", side_effect=fake_sleep):
                result = screener._download_single_ticker_data("000300.KS", dates[0].to_pydatetime(), dates[-1].to_pydatetime())

        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(sleep_calls), 2)
        self.assertTrue(any(seconds >= screener.rate_limit_cooldown_seconds for seconds in sleep_calls))

    def test_should_skip_ticker_from_cache_after_repeated_no_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "no_data_cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "tickers": {
                            "000300.KS": {
                                "count": 3,
                                "reason": "download_missing",
                                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            screener = TurtleTradingScreener(no_data_cache_file=str(cache_path))

            self.assertTrue(screener._should_skip_ticker_from_cache("000300.KS"))

    def test_recorded_no_data_cache_clears_after_successful_recovery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "no_data_cache.json"
            screener = TurtleTradingScreener(no_data_cache_file=str(cache_path))
            screener._record_no_data_ticker("000300.KS", "download_missing")
            self.assertIn("000300.KS", screener._no_data_cache)

            screener._clear_no_data_ticker("000300.KS")

            self.assertNotIn("000300.KS", screener._no_data_cache)

    def test_build_no_data_cache_summary_returns_ranked_sample(self):
        screener = TurtleTradingScreener()
        screener._no_data_cache = {
            "000300.KS": {"count": 4, "reason": "download_missing", "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")},
            "000020.KS": {"count": 2, "reason": "insufficient_history", "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")},
        }

        summary = screener._build_no_data_cache_summary()

        self.assertEqual(summary["active_entry_count"], 2)
        self.assertEqual(summary["sample"][0]["ticker"], "000300.KS")
        self.assertEqual(summary["sample"][0]["count"], 4)

    def test_invalid_windows_ca_bundle_env_is_replaced_with_certifi_bundle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "no_data_cache.json"
            cert_path = Path(temp_dir) / "cacert.pem"
            cert_path.write_text("dummy cert", encoding="utf-8")

            with patch.dict(
                "os.environ",
                {"CURL_CA_BUNDLE": r"C:\Users\박제형\Desktop\stock_screener\.venv\lib\site-packages\certifi\cacert.pem"},
                clear=False,
            ):
                with patch("run_screener.certifi.where", return_value=str(cert_path)):
                    screener = TurtleTradingScreener(no_data_cache_file=str(cache_path))
                    self.assertEqual(__import__("os").environ["CURL_CA_BUNDLE"], str(cert_path))

            self.assertEqual(screener.no_data_cache_file, str(cache_path))

    def test_download_single_ticker_uses_period_and_certifi_session(self):
        screener = TurtleTradingScreener(no_data_cache_file=".cache/test-no-data-cache.json")
        dates = pd.date_range("2025-01-01", periods=65, freq="D")
        recovered_single = pd.DataFrame(
            {
                "Open": range(65),
                "High": range(1, 66),
                "Low": range(65),
                "Close": range(1, 66),
                "Volume": [120000] * 65,
            },
            index=dates,
        )
        fake_session = object()

        with patch.object(screener, "_get_yfinance_session", return_value=fake_session):
            with patch("run_screener.yf.download", return_value=recovered_single) as mock_download:
                result = screener._download_single_ticker_data("000300.KS", dates[0].to_pydatetime(), dates[-1].to_pydatetime())

        self.assertIsNotNone(result)
        kwargs = mock_download.call_args.kwargs
        self.assertEqual(kwargs["period"], screener.history_period)
        self.assertEqual(kwargs["session"], fake_session)
        self.assertNotIn("start", kwargs)
        self.assertNotIn("end", kwargs)

    def test_run_screening_logs_sanitized_ca_bundle_envs(self):
        screener = TurtleTradingScreener(no_data_cache_file=".cache/test-no-data-cache.json")
        screener._sanitized_ca_bundle_envs = ["CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE"]

        with patch.object(screener, "get_ticker_universe", return_value=([], [])):
            with patch("run_screener.logger.info") as mock_info:
                screener.run_screening()

        mock_info.assert_any_call(
            "Sanitized invalid CA bundle environment variables: CURL_CA_BUNDLE, REQUESTS_CA_BUNDLE"
        )


if __name__ == "__main__":
    unittest.main()
