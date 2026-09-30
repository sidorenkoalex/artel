"""Границы сводки отказа автогейта приёмки канарейки."""

from orchestrator import canary


def test_refusal_survives_journal_excerpt_limit():
    """Ловит мутацию: поздние переходы вытесняют отказ автогейта из выдержки."""
    steps = [{"ts": "t0", "actor": "fsm",
              "action": "автогейт acceptance не пройден", "detail": "причина"}]
    steps += [{"ts": f"t{index}", "actor": "fsm",
               "action": f"state -> step{index}", "detail": ""}
              for index in range(1, 21)]

    excerpt = canary._journal_excerpt_lines(steps)

    assert len(excerpt) == 18
    assert "автогейт acceptance не пройден" in excerpt[0]
    assert "state -> step20" in excerpt[-1]


def test_summary_binds_refusal_reason_to_500_characters():
    """Ловит мутацию: причина отказа длиннее 500 символов выходит в строку итога."""
    reason = "  первая  строка\n" + "я" * 600

    note = canary._acceptance_summary("manual", reason, True)

    assert note.startswith("  приёмка вручную: первая строка ")
    assert "\n" not in note
    assert len(note.split("приёмка вручную: ", 1)[1]) == 500
