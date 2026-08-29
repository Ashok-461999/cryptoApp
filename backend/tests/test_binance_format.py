from app.services.binance_trading_client import BinanceTradingClient


def test_format_price_no_scientific_notation():
    c = BinanceTradingClient()
    assert c._format_for_api(0.00001234, 0.00000001) == "0.00001234"
    assert "e" not in c._format_for_api(7.48, 0.01).lower()


def test_format_price_rejects_zero():
    c = BinanceTradingClient()
    try:
        c._format_for_api(0.0, 0.01)
        assert False, "expected error"
    except Exception as exc:
        assert "Invalid API value" in str(exc)
