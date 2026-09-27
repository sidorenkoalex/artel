"""AC-3 — 01M3H3T8RKTVKTJJYEAGW19BPS: в `orchestrator/fsm.py` остался
алиас публичного `cmd_ci_rerun` с пометкой срока снятия, а пять закрытых
имён команды (`_ci_rerun_refuse`, `_last_red_status_sha`,
`_last_ci_rerun_reason`, `_ci_rerun_outcome`, `_cmd_ci_rerun`) из модуля
убраны.

Алиас проверяется и на уровне модуля (тот же объект, что в новом
модуле), и на уровне исходника (есть инструкция, вводящая имя, и рядом
с ней — пометка срока снятия). Пометка ищется словарём корней
(«снят», «снима», «убра», «убер», «удал», «волн», «deprecat») в окне
вокруг инструкции: критерий требует её наличия, а не конкретной
формулировки.

Красен до реализации: `orchestrator/fsm.py` сегодня несёт все шесть
функций собственными определениями — пять закрытых имён на месте, а
`cmd_ci_rerun` не алиас, а реализация; оба метода падают.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

# Корни слов, которыми называют срок снятия временного алиаса. Набор
# широкий намеренно: AC-3 требует ПОМЕТКУ, а не заданную формулировку.
REMOVAL_STEMS = ("снят", "снима", "сним", "убра", "убер", "удал", "волн",
                 "deprecat")
#: Сколько строк вокруг инструкции алиаса считается «рядом с ним».
WINDOW_BEFORE = 12
WINDOW_AFTER = 2

_ALIAS_LINE_RE = re.compile(
    r"^\s*(?:cmd_ci_rerun\s*=|"
    r"from\s+(?:\.|orchestrator\.)ci_rerun\s+import\b.*\bcmd_ci_rerun\b)")


class FsmKeepsOnlyMarkedAliasTest(unittest.TestCase):

    def setUp(self):
        self.source = _util.current_source(_util.FSM_REL)
        self.lines = self.source.splitlines()

    def test_ac3_public_name_stays_as_alias_of_the_new_module(self):
        """`fsm.cmd_ci_rerun` — тот же объект, что
        `ci_rerun.cmd_ci_rerun`, и в `fsm.py` больше нет собственного
        определения этой функции.

        Ловит мутацию: вместо алиаса в `fsm.py` оставлена обёртка
        (`def cmd_ci_rerun(...): return ci_rerun.cmd_ci_rerun(...)`) —
        подмены существующих тестов на `fsm.cmd_ci_rerun` перестали бы
        совпадать с подменами на новый модуль; `assertIs` и проверка
        отсутствия определения покраснеют.
        """
        from orchestrator import ci_rerun, fsm

        self.assertTrue(
            hasattr(fsm, "cmd_ci_rerun"),
            "fsm.cmd_ci_rerun отсутствует — AC-3 требует сохранить алиас "
            "старого публичного имени на одну волну")
        self.assertIs(
            fsm.cmd_ci_rerun, ci_rerun.cmd_ci_rerun,
            "fsm.cmd_ci_rerun — не тот же объект, что ci_rerun.cmd_ci_rerun")
        self.assertNotIn(
            "cmd_ci_rerun", _util.functions(self.source),
            f"{_util.FSM_REL} всё ещё определяет cmd_ci_rerun собственной "
            f"функцией — это не алиас")

    def test_ac3_alias_carries_a_removal_term_note(self):
        """Рядом с инструкцией алиаса стоит пометка срока снятия.

        Ловит мутацию: алиас введён голой строкой без единого
        комментария («потом разберёмся») — временное имя тогда остаётся
        навсегда, потому что следующей волне не за что зацепиться; окно
        вокруг инструкции не найдёт ни одного корня слова о снятии.
        """
        alias_lines = [i for i, line in enumerate(self.lines)
                       if _ALIAS_LINE_RE.match(line)]
        self.assertTrue(
            alias_lines,
            f"в {_util.FSM_REL} не найдено инструкции, вводящей алиас "
            f"cmd_ci_rerun (ни присваивания, ни импорта из .ci_rerun)")

        marked = []
        for idx in alias_lines:
            window = "\n".join(
                self.lines[max(0, idx - WINDOW_BEFORE): idx + WINDOW_AFTER + 1]
            ).lower()
            marked.append(any(stem in window for stem in REMOVAL_STEMS))
        self.assertTrue(
            any(marked),
            f"у алиаса cmd_ci_rerun в {_util.FSM_REL} нет пометки срока "
            f"снятия: в {WINDOW_BEFORE} строках выше и "
            f"{WINDOW_AFTER} ниже нет ни одного из {REMOVAL_STEMS}")

    def test_ac3_private_command_names_are_gone_from_fsm(self):
        """Пяти закрытых имён команды в `fsm.py` нет — ни определением,
        ни реэкспортом в пространстве имён модуля.

        Ловит мутацию: закрытые имена перенесены копией, а в `fsm.py`
        оставлены «на всякий случай» (или подтянуты `from .ci_rerun
        import *`) — в пульте окажутся две реализации одной команды,
        расходящиеся при первой же правке; обе проверки назовут имя.
        """
        from orchestrator import fsm

        defined = _util.functions(self.source)
        for name in _util.PRIVATE_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(
                    name, defined,
                    f"{_util.FSM_REL} всё ещё определяет {name} (AC-3)")
                self.assertFalse(
                    hasattr(fsm, name),
                    f"orchestrator.fsm.{name} доступен — закрытые имена "
                    f"команды из этого модуля убраны быть должны (AC-3)")

    def test_ac3_private_names_are_not_mentioned_in_fsm_code(self):
        """В коде `fsm.py` (вне комментариев и докстрингов) не осталось
        ни одного обращения к пяти закрытым именам команды.

        Ловит мутацию: определения убраны, а вызов остался — например, в
        `fsm.py` уцелел `_cmd_ci_rerun(conn, …)` внутри другой функции:
        модуль импортируется, `hasattr` молчит, а команда падает
        `NameError` при первом же вызове ветки.
        """
        tree = ast.parse(self.source)
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in _util.PRIVATE_NAMES:
                used.add(node.id)
            if isinstance(node, ast.Attribute) and \
                    node.attr in _util.PRIVATE_NAMES:
                used.add(node.attr)
        self.assertEqual(
            set(), used,
            f"{_util.FSM_REL} обращается к закрытым именам команды "
            f"{sorted(used)}, которых в нём быть не должно (AC-3)")


if __name__ == "__main__":
    unittest.main()
