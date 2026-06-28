"""Currency business logic as a dependency-injectable service.

This module extracts the logic previously in ``avalone_finance.core.currency``
into a class so callers can provide a custom glossary service while keeping the
old module-level API working through the facade in ``currency.py``.
"""

from __future__ import annotations

from typing import Any

import httpx

# --- Список валют. code -> {name, symbol}. Порядок = порядок показа. ---
# fiat: широкий набор ходовых; крипта помечается флагом crypto.
FIAT: dict[str, dict] = {
    "KRW": {"name": "South Korean Won", "symbol": "₩"},
    "USD": {"name": "US Dollar", "symbol": "$"},
    "EUR": {"name": "Euro", "symbol": "€"},
    "RUB": {"name": "Russian Ruble", "symbol": "₽"},
    "JPY": {"name": "Japanese Yen", "symbol": "¥"},
    "CNY": {"name": "Chinese Yuan", "symbol": "¥"},
    "GBP": {"name": "British Pound", "symbol": "£"},
    "CHF": {"name": "Swiss Franc", "symbol": "Fr"},
    "AUD": {"name": "Australian Dollar", "symbol": "A$"},
    "CAD": {"name": "Canadian Dollar", "symbol": "C$"},
    "HKD": {"name": "Hong Kong Dollar", "symbol": "HK$"},
    "SGD": {"name": "Singapore Dollar", "symbol": "S$"},
    "INR": {"name": "Indian Rupee", "symbol": "₹"},
    "THB": {"name": "Thai Baht", "symbol": "฿"},
    "VND": {"name": "Vietnamese Dong", "symbol": "₫"},
    "IDR": {"name": "Indonesian Rupiah", "symbol": "Rp"},
    "PHP": {"name": "Philippine Peso", "symbol": "₱"},
    "MYR": {"name": "Malaysian Ringgit", "symbol": "RM"},
    "TRY": {"name": "Turkish Lira", "symbol": "₺"},
    "BRL": {"name": "Brazilian Real", "symbol": "R$"},
    "MXN": {"name": "Mexican Peso", "symbol": "$"},
    "ZAR": {"name": "South African Rand", "symbol": "R"},
    "AED": {"name": "UAE Dirham", "symbol": "د.إ"},
    "SAR": {"name": "Saudi Riyal", "symbol": "﷼"},
    "PLN": {"name": "Polish Zloty", "symbol": "zł"},
    "SEK": {"name": "Swedish Krona", "symbol": "kr"},
    "NOK": {"name": "Norwegian Krone", "symbol": "kr"},
    "DKK": {"name": "Danish Krone", "symbol": "kr"},
    "CZK": {"name": "Czech Koruna", "symbol": "Kč"},
    "UAH": {"name": "Ukrainian Hryvnia", "symbol": "₴"},
    "KZT": {"name": "Kazakhstani Tenge", "symbol": "₸"},
    "NZD": {"name": "New Zealand Dollar", "symbol": "NZ$"},
    "ILS": {"name": "Israeli Shekel", "symbol": "₪"},
    "EGP": {"name": "Egyptian Pound", "symbol": "E£"},
    "TWD": {"name": "Taiwan Dollar", "symbol": "NT$"},
}

# крипта: code -> {name, symbol, cg_id (coingecko id)}
CRYPTO: dict[str, dict] = {
    "BTC":  {"name": "Bitcoin", "symbol": "₿", "cg_id": "bitcoin"},
    "ETH":  {"name": "Ethereum", "symbol": "Ξ", "cg_id": "ethereum"},
    "USDT": {"name": "Tether", "symbol": "₮", "cg_id": "tether"},
    "USDC": {"name": "USD Coin", "symbol": "$", "cg_id": "usd-coin"},
    "BNB":  {"name": "BNB", "symbol": "BNB", "cg_id": "binancecoin"},
    "XRP":  {"name": "XRP", "symbol": "XRP", "cg_id": "ripple"},
    "SOL":  {"name": "Solana", "symbol": "SOL", "cg_id": "solana"},
    "TRX":  {"name": "TRON", "symbol": "TRX", "cg_id": "tron"},
    "TON":  {"name": "Toncoin", "symbol": "TON", "cg_id": "the-open-network"},
    "DOGE": {"name": "Dogecoin", "symbol": "Ð", "cg_id": "dogecoin"},
    "ADA":  {"name": "Cardano", "symbol": "ADA", "cg_id": "cardano"},
}

ALL: dict[str, dict] = {**FIAT, **CRYPTO}


class CurrencyService:
    """Business logic for fiat/crypto currencies and live-rate conversion."""

    FIAT = FIAT
    CRYPTO = CRYPTO
    ALL = ALL

    def __init__(self, glossary_service: Any | None = None) -> None:
        self._glossary = glossary_service

    def _glossary_module(self):
        if self._glossary is not None:
            return self._glossary
        from avalone_finance.core import glossary
        return glossary

    def is_crypto(self, code: str) -> bool:
        return code.upper() in self.CRYPTO

    def known(self, code: str | None) -> bool:
        return bool(code) and code.upper() in self.ALL

    def seed_glossary(self) -> int:
        """Засеять названия валют в единый глоссарий (kind='currency', ключи
        cur_<code>). Сейчас в EN из таблиц FIAT/CRYPTO; ru/ko можно дополнить в
        глоссарии позже (источник истины — глоссарий). Вызывается на старте."""
        glossary = self._glossary_module()
        rows = []
        for c, v in {**self.FIAT, **self.CRYPTO}.items():
            kind_word = "cryptocurrency" if c in self.CRYPTO else "fiat currency"
            desc = (f"Full display name of the {kind_word} with ISO/ticker code "
                    f"'{c}' (symbol {v['symbol']}). Shown in a currency picker next to "
                    f"a money amount. Translate as the official localized name of this "
                    f"currency, not literally.")
            rows.append({"key": f"cur_{c.lower()}", "en": v["name"],
                         "kind": "currency", "desc": desc})
        return glossary.upsert_many(rows)

    def name(self, code: str, lang: str = "en") -> str:
        """Локализованное название валюты из глоссария; фолбэк — EN из таблицы."""
        glossary = self._glossary_module()
        key = f"cur_{code.lower()}"
        g = glossary.get(key, lang)
        if g != key:
            return g
        return self.ALL.get(code.upper(), {}).get("name", code)

    def options(self, lang: str = "en") -> dict[str, list[dict]]:
        """Списки для дроплиста: {fiat:[{code,name,symbol}...], crypto:[...]}.
        name — локализованное имя из глоссария (источник истины)."""
        fiat = [{"code": c, "name": self.name(c, lang), "symbol": v["symbol"]}
                for c, v in self.FIAT.items()]
        crypto = [{"code": c, "name": self.name(c, lang), "symbol": v["symbol"]}
                  for c, v in self.CRYPTO.items()]
        return {"fiat": fiat, "crypto": crypto}

    async def _fiat_usd_rates(self) -> dict[str, float] | None:
        """USD-базисные курсы для фиата: {code: units_per_USD}. Без ключа, без кэша."""
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get("https://open.er-api.com/v6/latest/USD")
            d = r.json()
            if d.get("result") == "success":
                return d.get("rates") or None
        except Exception:
            return None
        return None

    async def _crypto_usd_price(self, codes: list[str]) -> dict[str, float] | None:
        """USD-цена за 1 монету для крипто-кодов: {code: usd_per_coin}."""
        ids = {self.CRYPTO[c]["cg_id"]: c for c in codes if c in self.CRYPTO}
        if not ids:
            return {}
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get("https://api.coingecko.com/api/v3/simple/price",
                                params={"ids": ",".join(ids), "vs_currencies": "usd"})
            d = r.json()
            out = {}
            for cg_id, code in ids.items():
                v = (d.get(cg_id) or {}).get("usd")
                if v:
                    out[code] = float(v)
            return out
        except Exception:
            return None

    async def usd_value(self, code: str) -> float | None:
        """Сколько USD стоит 1 единица валюты `code` (фиат или крипта). None если нет данных."""
        code = code.upper()
        if code == "USD":
            return 1.0
        if code in self.CRYPTO:
            prices = await self._crypto_usd_price([code])
            return prices.get(code) if prices else None
        rates = await self._fiat_usd_rates()
        if not rates or code not in rates or not rates[code]:
            return None
        return 1.0 / rates[code]   # units_per_USD -> USD per unit

    async def convert(self, amount: float, frm: str, to: str) -> float | None:
        """Перевести сумму из валюты frm в to по живому курсу. None если нет данных.
        Кросс-курс через USD (общий базис для фиата и крипты)."""
        frm, to = frm.upper(), to.upper()
        if frm == to:
            return amount
        uf = await self.usd_value(frm)
        ut = await self.usd_value(to)
        if uf is None or ut is None or ut == 0:
            return None
        return amount * uf / ut
