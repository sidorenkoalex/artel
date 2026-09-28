"""Приёмочный тест 01M3KHQS7EQTHDT1RGCNH4KGTW — AC-1 (SPEC.md).

Предмет — сама настройка `orchestrator/config.py` и комментарий над ней.
Значение берётся импортом модуля, комментарий — текстом файла, в котором
этот модуль лежит (`config.__file__`, не путь-литерал: так тест читает
ровно тот `config.py`, чьё значение он же и проверил). Комментарием
настройки считается непрерывный блок строк `#` НЕПОСРЕДСТВЕННО над
присваиванием — тот же блок, который читает глазами Оператор.

Красен до реализации: `orchestrator/config.py:756` несёт
`AUTO_WAIT_ZONE_DEFAULT = False`, а комментарий над ним — прежнюю
оговорку «пока Оператор явно не включит настройку», без даты 28.09.2026
и без прецедента 01M3KE8ZJXFARS6KC441PCDCQV.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

SETTING = "AUTO_WAIT_ZONE_DEFAULT"
DECISION_DATE = "28.09.2026"
PRECEDENT_TASK = "01M3KE8ZJXFARS6KC441PCDCQV"
OBSOLETE_CLAUSE = "пока Оператор явно не включит настройку"


def _setting_comment() -> str:
    """Непрерывный блок строк-комментариев прямо над присваиванием
    настройки в файле импортированного `orchestrator.config`. Пустая
    строка — присваивания нет либо комментария над ним нет."""
    source = Path(config.__file__).read_text(encoding="utf-8")
    lines = source.splitlines()
    assignment = re.compile(rf"^{SETTING}\s*=")
    index = next((i for i, line in enumerate(lines) if assignment.match(line)),
                 None)
    if index is None:
        return ""
    block = []
    for line in reversed(lines[:index]):
        if not line.lstrip().startswith("#"):
            break
        block.append(line)
    return "\n".join(reversed(block))


class Ac1ConfigDefaultAndCommentTest(unittest.TestCase):

    def test_ac1_default_is_true_and_comment_names_decision_and_basis(self):
        """`config.AUTO_WAIT_ZONE_DEFAULT` равна `True`, а комментарий
        настройки называет дату 28.09.2026, решение Оператора и основание
        — остановку задачи на занятой зоне без надзора с прецедентом
        волны 28.09 (01M3KE8ZJXFARS6KC441PCDCQV); прежней оговорки «пока
        Оператор явно не включит настройку» в нём больше нет.

        Ловит мутацию: значение поднято до `True`, а комментарий оставлен
        прежним (самая дешёвая правка — одна строка) — Оператор, читающий
        `config.py`, видел бы над включённой настройкой оговорку о том,
        что она ждёт его включения, без даты решения и без прецедента,
        которым оно обосновано.
        """
        self.assertIs(
            config.AUTO_WAIT_ZONE_DEFAULT, True,
            f"config.{SETTING} = {config.AUTO_WAIT_ZONE_DEFAULT!r}")

        comment = _setting_comment()
        self.assertTrue(
            comment, f"над присваиванием {SETTING} в {config.__file__} нет "
                     f"блока комментария")
        self.assertIn(DECISION_DATE, comment,
                      f"комментарий настройки не называет дату решения "
                      f"Оператора:\n{comment}")
        self.assertRegex(comment, r"[Оо]ператор",
                         f"комментарий настройки не называет решение "
                         f"Оператора:\n{comment}")
        self.assertIn(PRECEDENT_TASK, comment,
                      f"комментарий настройки не называет прецедент волны "
                      f"28.09:\n{comment}")
        self.assertRegex(comment, r"останов",
                         f"комментарий настройки не называет основание — "
                         f"остановку задачи на занятой зоне:\n{comment}")
        self.assertNotIn(OBSOLETE_CLAUSE, comment,
                         f"комментарий настройки несёт прежнюю оговорку "
                         f"{OBSOLETE_CLAUSE!r}:\n{comment}")


if __name__ == "__main__":
    unittest.main()
