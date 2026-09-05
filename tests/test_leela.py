import chess

from src.engine.leela import IntuitionEngine


def test_unstarted_engine_reports_no_reading_rather_than_zero():
    """Leela is optional and the coach runs without it. A 0.0 here would be
    rendered downstream as "the position is balanced" - a confident claim from
    an engine that never started."""
    engine = IntuitionEngine(engine_path="lc0", weights_path=None)

    vibe = engine.get_vibe(chess.Board())

    assert vibe["vibe_score"] is None
    assert vibe["top_choice"] is None
