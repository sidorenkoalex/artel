"""AC-5 (tasks/T085/SPEC.md): комментарии у `PROGRAM_STOP_LOSS_USD` и
`PROGRAM_ALERT_RATIOS` в `orchestrator/config.py` описывают пороги как
отчётную веху (ADR-0010): не как условие, способное заблокировать
переход или гейт.

Читает исходник `orchestrator/config.py` и берёт контиguous-блок
комментариев (строки, начинающиеся с `#`), непосредственно
предшествующий строке присвоения каждого имени — если он пуст (сегодня
`PROGRAM_ALERT_RATIOS` идёт вплотную за `PROGRAM_STOP_LOSS_USD` и делит
с ним один общий блок выше), падает на блок соседней из этих двух
констант: комментарий может остаться общим на обе, лишь бы обе были
им описаны.

Красен до реализации: сегодняшний блок (строки 109-113) не упоминает
ADR-0010 и не называет пороги «отчётной вехой» словами — только «повод
для внеочередного пересмотра программы» без ссылки на решение.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

CONFIG_PATH = REPO_ROOT / "orchestrator" / "config.py"
NAMES = ("PROGRAM_STOP_LOSS_USD", "PROGRAM_ALERT_RATIOS")


def _comment_block_above(lines: list[str], idx: int) -> list[str]:
    """Строки-комментарии непосредственно НАД `lines[idx]` (не включая
    её), собранные снизу вверх, пока строка начинается с `#`."""
    block = []
    j = idx - 1
    while j >= 0 and lines[j].strip().startswith("#"):
        block.insert(0, lines[j])
        j -= 1
    return block


def _line_index(lines: list[str], name: str) -> int:
    for i, line in enumerate(lines):
        if line.startswith(f"{name} ="):
            return i
    raise AssertionError(f"{name} не найдено в orchestrator/config.py")


def _described_comment_text(name: str, other: str) -> str:
    lines = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    idx = _line_index(lines, name)
    block = _comment_block_above(lines, idx)
    if not block:
        other_idx = _line_index(lines, other)
        if idx > 0 and lines[idx - 1].startswith(f"{other} ="):
            block = _comment_block_above(lines, other_idx)
    return "\n".join(block)


class ConfigCommentsDescribeMilestoneTest(unittest.TestCase):

    def test_ac5_stop_loss_comment_names_adr_0010_and_milestone(self):
        text = _described_comment_text("PROGRAM_STOP_LOSS_USD",
                                       "PROGRAM_ALERT_RATIOS")
        self.assertRegex(
            text, r"ADR-0010",
            f"AC-5: комментарий у PROGRAM_STOP_LOSS_USD обязан ссылаться "
            f"на ADR-0010; сейчас: {text!r}")
        self.assertRegex(
            text, r"веха",
            f"AC-5: комментарий обязан описывать порог как отчётную "
            f"веху; сейчас: {text!r}")

    def test_ac5_alert_ratios_comment_names_adr_0010_and_milestone(self):
        text = _described_comment_text("PROGRAM_ALERT_RATIOS",
                                       "PROGRAM_STOP_LOSS_USD")
        self.assertRegex(
            text, r"ADR-0010",
            f"AC-5: комментарий у PROGRAM_ALERT_RATIOS обязан ссылаться "
            f"на ADR-0010; сейчас: {text!r}")
        self.assertRegex(
            text, r"веха",
            f"AC-5: комментарий обязан описывать пороги как отчётную "
            f"веху; сейчас: {text!r}")


if __name__ == "__main__":
    unittest.main()
