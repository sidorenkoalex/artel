"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-1 (`orchestrator/
config.py` несёт `ROLE_BUDGET_CAP = 100.0` с комментарием-ссылкой на
ADR-0014; `DEFAULT_BUDGET_USD` остаётся 50).

Красен до реализации: `grep -n "ROLE_BUDGET_CAP" orchestrator/config.py`
сегодня пусто — константы нет вовсе, `getattr` ниже вернёт значение по
умолчанию `_MISSING`, и оба ассерта на неё упадут прежде, чем дойдут до
проверки значения.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

CONFIG_PATH = REPO_ROOT / "orchestrator" / "config.py"
_MISSING = object()


def _comment_block_above(lines: list, idx: int) -> list:
    """Строки-комментарии непосредственно НАД `lines[idx]` (не включая
    её), собранные снизу вверх, пока строка начинается с `#` (тот же
    приём, что tasks/T085/acceptance_tests/
    test_ac5_config_comments_describe_reporting_milestone.py)."""
    block = []
    j = idx - 1
    while j >= 0 and lines[j].strip().startswith("#"):
        block.insert(0, lines[j])
        j -= 1
    return block


class RoleBudgetCapValueTest(unittest.TestCase):
    """Значения обеих констант — ровно те, что называет AC-1.

    Ловит мутацию: `ROLE_BUDGET_CAP` заведена с другим числом (например,
    по опечатке `10.0` вместо `100.0`), либо правка `ROLE_BUDGET_CAP`
    попутно сдвигает и `DEFAULT_BUDGET_USD` — обе половины AC-1 (новая
    константа и неизменность старой) проверяются отдельными assert'ами,
    так что регрессия любой стороны отличима по имени упавшего assert'а.
    """

    def test_ac1_role_budget_cap_is_100(self):
        actual = getattr(config, "ROLE_BUDGET_CAP", _MISSING)
        self.assertNotEqual(
            actual, _MISSING,
            "orchestrator/config.py не содержит константу ROLE_BUDGET_CAP")
        self.assertEqual(actual, 100.0)

    def test_ac1_default_budget_usd_stays_50(self):
        self.assertEqual(config.DEFAULT_BUDGET_USD, 50)


class RoleBudgetCapCommentTest(unittest.TestCase):
    """Комментарий над `ROLE_BUDGET_CAP` ссылается на ADR-0014 (AC-1,
    «с комментарием-ссылкой на ADR-0014»).

    Ловит мутацию: константа заведена без единого слова комментария,
    либо с комментарием, не называющим ADR-0014 (например, только
    «потолок ролей» без ссылки на решение) — тест не может отличить
    «забыли сослаться» от «сослались на другой ADR», обе одинаково не
    выполняют это условие AC-1.
    """

    def test_ac1_comment_references_adr_0014(self):
        lines = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
        idx = next((i for i, line in enumerate(lines)
                   if line.startswith("ROLE_BUDGET_CAP =")), None)
        self.assertIsNotNone(
            idx, "ROLE_BUDGET_CAP = ... не найдено в orchestrator/config.py")

        # Ссылка на ADR-0014 может стоять как в блоке комментариев над
        # строкой присвоения, так и хвостовым комментарием на самой этой
        # строке (`ROLE_BUDGET_CAP = 100.0  # ADR-0014 ...`) — оба места
        # равноправны для условия «с комментарием-ссылкой».
        block = _comment_block_above(lines, idx)
        text = "\n".join(block) + "\n" + lines[idx]

        self.assertRegex(
            text, r"ADR-0014",
            f"AC-1: комментарий у ROLE_BUDGET_CAP обязан ссылаться на "
            f"ADR-0014; сейчас: {text!r}")


if __name__ == "__main__":
    unittest.main()
