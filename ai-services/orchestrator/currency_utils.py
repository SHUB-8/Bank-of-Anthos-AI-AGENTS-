import re

# Expanded currency normalization mapping
CURRENCY_MAP = {
    "dollar": "USD", "dollars": "USD", "usd": "USD", "us dollar": "USD", "bucks": "USD", "greenback": "USD", "american dollar": "USD", "u.s. dollar": "USD",
    "euro": "EUR", "euros": "EUR", "eur": "EUR", "european euro": "EUR", "eu currency": "EUR", "european currency": "EUR", "euors": "EUR",
    "pound": "GBP", "pounds": "GBP", "quid": "GBP", "sterling": "GBP", "gbp": "GBP", "british pound": "GBP", "uk pound": "GBP", "english pound": "GBP",
    "rupee": "INR", "rupees": "INR", "inr": "INR", "indian rupee": "INR", "rs": "INR", "₹": "INR", "indian currency": "INR", "rupiya": "INR", "rupay": "INR", "ruppe": "INR", "rupi": "INR",
    "yen": "JPY", "jpy": "JPY", "japanese yen": "JPY", "jp yen": "JPY", "japan currency": "JPY", "円": "JPY",
    "yuan": "CNY", "cny": "CNY", "rmb": "CNY", "renminbi": "CNY", "chinese yuan": "CNY", "china currency": "CNY",
    "franc": "CHF", "chf": "CHF", "swiss franc": "CHF", "swiss money": "CHF", "switzerland currency": "CHF",
    "canadian dollar": "CAD", "cad": "CAD", "canada dollar": "CAD", "canadian bucks": "CAD", "canadian currency": "CAD",
    "australian dollar": "AUD", "aud": "AUD", "aussie dollar": "AUD", "australia dollar": "AUD", "australian bucks": "AUD",
    "singapore dollar": "SGD", "sgd": "SGD", "singapore bucks": "SGD", "singapore currency": "SGD",
    "rand": "ZAR", "zar": "ZAR", "south african rand": "ZAR", "sa rand": "ZAR", "south africa currency": "ZAR",
    "peso": "MXN", "mxn": "MXN", "mexican peso": "MXN", "mexico currency": "MXN",
    "real": "BRL", "brl": "BRL", "brazilian real": "BRL", "brazil currency": "BRL",
    "lira": "TRY", "try": "TRY", "turkish lira": "TRY", "turkey currency": "TRY",
    "ruble": "RUB", "rub": "RUB", "russian ruble": "RUB", "russia currency": "RUB",
    "won": "KRW", "krw": "KRW", "korean won": "KRW", "south korean won": "KRW", "korea currency": "KRW",
    "dirham": "AED", "aed": "AED", "uae dirham": "AED", "emirati dirham": "AED", "dubai currency": "AED",
    "shekel": "ILS", "ils": "ILS", "israeli shekel": "ILS", "israel currency": "ILS",
    "krona": "SEK", "sek": "SEK", "swedish krona": "SEK", "sweden currency": "SEK",
    "dinar": "KWD", "kwd": "KWD", "kuwaiti dinar": "KWD", "kuwait currency": "KWD",
}

def normalize_currency(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    if text in CURRENCY_MAP:
        return CURRENCY_MAP[text]
    for key in CURRENCY_MAP:
        if key in text:
            return CURRENCY_MAP[key]
    if text in ["rupee", "rupees", "rs", "rupiya", "rupay", "ruppe", "rupi", "indian currency", "inr"]:
        return "INR"
    return "USD"

def convert_amount(amount, from_currency, to_currency, rates):
    """
    Convert amount from one currency to another using rates dict.
    rates: dict of currency_code -> rate (relative to USD)
    """
    from_rate = rates.get(from_currency.upper())
    to_rate = rates.get(to_currency.upper())
    if from_rate is None or to_rate is None:
        raise ValueError(f"Missing rate for {from_currency} or {to_currency}")
    # Convert to USD, then to target
    usd_amount = float(amount) / from_rate if from_currency.upper() != "USD" else float(amount)
    target_amount = usd_amount * to_rate if to_currency.upper() != "USD" else usd_amount
    return target_amount
