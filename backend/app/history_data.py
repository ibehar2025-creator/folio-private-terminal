"""No-key historical prices for private use, isolated from the quote provider."""

import math
import re
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from .market import ProviderUnavailable, wait_for_provider_slot
from .models import now


class YahooHistoryProvider:
    name = "yahoo"
    # Known US share classes; never rewrite every dot (it can denote an exchange).
    aliases = {"BRK.A": "BRK-A", "BRK.B": "BRK-B", "BF.A": "BF-A", "BF.B": "BF-B"}

    def get_history(self, symbol):
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,39}", symbol):
            raise ProviderUnavailable(
                "This ticker format is not supported by Yahoo history"
            )
        ticker = self.aliases.get(symbol, symbol)
        wait_for_provider_slot(self.name, 30)
        try:
            response = httpx.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/"
                + quote(ticker, safe=""),
                params={"range": "10y", "interval": "1d", "includePrePost": "false"},
                headers={"User-Agent": "FolioPrivateTerminal/1.0"},
                timeout=20,
            )
            if response.status_code == 429:
                raise ProviderUnavailable(
                    "Yahoo history is temporarily rate-limited. Retry later; cached history remains available."
                )
            if response.status_code in {401, 403}:
                raise ProviderUnavailable(
                    "Yahoo's public history feed is currently restricting access. No Finnhub key change is needed; retry later or select another history provider."
                )
            if response.status_code == 404:
                raise ProviderUnavailable(
                    "Yahoo has no historical series for this ticker"
                )
            response.raise_for_status()
            return self.normalize(response.json(), ticker)
        except httpx.HTTPError:
            raise ProviderUnavailable(
                "Yahoo historical prices are temporarily unavailable; cached history remains available."
            ) from None
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            raise ProviderUnavailable(
                "Yahoo returned an invalid historical-price series; the last good data is preserved."
            ) from None

    @staticmethod
    def normalize(payload, ticker):
        chart = payload["chart"]
        if chart.get("error") or not chart.get("result"):
            raise ProviderUnavailable("Yahoo has no historical series for this ticker")
        result = chart["result"][0]
        meta = result["meta"]
        if meta.get("symbol", "").upper() != ticker.upper():
            raise ValueError("Mismatched symbol")
        if meta.get("currency") != "USD":
            raise ProviderUnavailable(
                "This historical series is not in USD; FX conversion is not configured."
            )
        try:
            exchange_zone = ZoneInfo(meta["exchangeTimezoneName"])
        except (ZoneInfoNotFoundError, TypeError, KeyError):
            raise ValueError("Missing exchange timezone") from None
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        if len(stamps) != len(closes) or len(stamps) > 10000:
            raise ValueError("Mismatched or oversized series")
        observed = now()
        today = observed.astimezone(exchange_zone).date()
        regular_end = meta.get("currentTradingPeriod", {}).get("regular", {}).get("end")
        points = {}
        for stamp, close in zip(stamps, closes):
            if close is None:
                continue  # Missing observations stay absent, never interpolated.
            value = float(close)
            if isinstance(close, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid close")
            day = (
                datetime.fromtimestamp(stamp, timezone.utc)
                .astimezone(exchange_zone)
                .date()
            )
            if day > today or (
                day == today and (not regular_end or observed.timestamp() < regular_end)
            ):
                continue  # Do not cache an unfinished current session as its closing price.
            key = day.isoformat()
            if key in points and points[key] != value:
                raise ValueError("Conflicting daily observations")
            points[key] = value
        if not points:
            raise ProviderUnavailable(
                "Yahoo has no completed daily prices for this ticker yet"
            )
        return {
            "items": [{"date": day, "close": points[day]} for day in sorted(points)],
            "currency": "USD",
            "interval": "1d",
            "adjusted": False,  # The app reserves this flag for dividend-adjusted returns.
            "split_adjusted": True,
            "dividend_adjusted": False,
            "label": "Yahoo Finance · daily closing prices",
            "methodology": "Daily Close prices with provider split adjustments; dividends excluded. Up to 10 years where available. The current trading session is excluded until its regular close.",
            "source_url": "https://finance.yahoo.com/quote/"
            + quote(ticker, safe="")
            + "/history/",
        }
