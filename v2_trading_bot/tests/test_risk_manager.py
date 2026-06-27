from src.config import AppConfig
from src.risk.risk_manager import RiskManager
from src.models import Side


def test_mes_bracket_prices_long():
    cfg = AppConfig()
    risk = RiskManager(cfg)
    stop, target = risk.build_bracket_prices(Side.LONG, 6000.00)
    assert stop == 5996.00
    assert target == 6006.00


def test_mes_bracket_prices_short():
    cfg = AppConfig()
    risk = RiskManager(cfg)
    stop, target = risk.build_bracket_prices(Side.SHORT, 6000.00)
    assert stop == 6004.00
    assert target == 5994.00
