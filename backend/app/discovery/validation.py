import re


def valid_symbol(symbol: str, market: str) -> bool:
    if market == "CN_A":
        return re.fullmatch(r"[0-9]{6}", symbol) is not None
    return re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol) is not None
