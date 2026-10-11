"""Факты ветки задачи: константы наблюдения добавлены в `orchestrator/config.py` (флаг `True`, предел 600), `tests/sandbox.py` получил только выключение флага рядом с подменой `config.ROLES`/`config.MODELS_LOCAL` с комментарием, защищённые тестовые файлы и `orchestrator/providers/*` не тронуты (AC-9 — по исходнику, AC-11, AC-12 — провайдеры).

Группа: разовый

Красен до реализации: ветка ещё не добавила ни флага наблюдения и предела в `orchestrator/config.py`, ни строки выключения флага в `tests/sandbox.py` — `test_ac9_*` и `test_ac11_sandbox_*` не находят добавленных строк; `test_ac11_protected_tests_untouched` и `test_ac12_providers_untouched` держат неизменность и зелёны с рождения.

Дифф задачи — `branch_diff()`/`changed_paths()` помощника пульта `_pult.py`
(база — точка расхождения ветки с `origin`, тем же правилом, что гейт
зон); текст `tests/sandbox.py` головы — из рабочей копии кода
(`CODE_ROOT`). Остальные критерии — в долгоживущих файлах задачи
`tests/test_<id задачи>_two_sided_observation.py` и
`tests/test_<id задачи>_test_author_report.py`.

Валидация стабом: на временной правке рабочей копии (флаг `= True` и
предел `= 600` в `config.py`, строка `config.<флаг> = False` с
комментарием после подмены `config.MODELS_LOCAL` в `tests/sandbox.py`,
закоммиченной во временную ветку) разбор диффа находит обе константы и
одну строку выключения; правка удалена.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, branch_diff, changed_paths  # noqa: E402

CONFIG = "orchestrator/config.py"
SANDBOX = "tests/sandbox.py"
NEAR = 12
PROTECTED = ("tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py",
             "tests/test_fsm_advance_gate_smoke.py")


def file_diff(path: str) -> list:
    """Строки диффа задачи по `path` (без заголовков файла)."""
    lines, inside = [], False
    for line in branch_diff().splitlines():
        if line.startswith("diff --git "):
            inside = line.endswith(f" b/{path}")
            continue
        if inside and not line.startswith(("+++", "---", "index ", "new file",
                                           "deleted file", "similarity",
                                           "rename ", "old mode", "new mode")):
            lines.append(line)
    return lines


def value(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return value(node.left) * value(node.right)
    raise ValueError(ast.dump(node))


def added_assignments(path: str) -> dict:
    """{имя: значение} однострочных присваиваний верхнего уровня, которые
    дифф задачи добавил в `path`."""
    found = {}
    for line in file_diff(path):
        if not line.startswith("+") or line.startswith("+ "):
            continue
        try:
            tree = ast.parse(line[1:])
        except SyntaxError:
            continue
        for node in tree.body:
            target = node.target if isinstance(node, ast.AnnAssign) else (
                node.targets[0] if isinstance(node, ast.Assign) else None)
            if isinstance(target, ast.Name) and node.value is not None:
                try:
                    found[target.id] = value(node.value)
                except ValueError:
                    continue
    return found


def disables_config_flag(statement: str) -> bool:
    """Строка выключает атрибут `config`: `config.X = False`,
    `setattr(config, "X", False)` или `mock.patch.object(config, "X",
    False)` (в том числе с `.start()`)."""
    return bool(re.fullmatch(
        r"config\.[A-Z][A-Z0-9_]*\s*=\s*False"
        r"|setattr\(\s*config\s*,\s*['\"][A-Z][A-Z0-9_]*['\"]\s*,\s*False\s*\)"
        r"|(?:\w+\s*=\s*)?(?:mock\.)?patch\.object\(\s*config\s*,\s*"
        r"['\"][A-Z][A-Z0-9_]*['\"]\s*,\s*False\s*\)(?:\.start\(\))?",
        statement.strip()))


class BranchFactsTest(unittest.TestCase):

    def test_ac9_config_source_adds_enabled_flag_and_600_second_limit(self):
        """Ветка добавляет в `orchestrator/config.py` флаг со значением `True` и константу со значением 600.

        Сценарий: однострочные присваивания верхнего уровня, добавленные
        диффом задачи в `orchestrator/config.py`, разбираются `ast`; среди
        них есть `ИМЯ = True` и `ИМЯ = 600` (в том числе `10 * 60`).

        Ловит мутацию: флаг заведён со значением `False` (наблюдение в бою
        выключено); предел — не 600 (например, 300 или 900).
        """
        added = added_assignments(CONFIG)
        context = f"добавленные присваивания config: {added}"
        self.assertIn(True, [v for v in added.values() if isinstance(v, bool)],
                      context)
        self.assertIn(600, [v for v in added.values()
                            if isinstance(v, (int, float))
                            and not isinstance(v, bool)], context)

    def test_ac11_sandbox_change_is_only_flag_disable_with_comment_near_roles(self):
        """`tests/sandbox.py` меняется только выставлением флага выключенным рядом с подменой `config.ROLES`/`config.MODELS_LOCAL`, с комментарием о причине.

        Сценарий: дифф задачи по `tests/sandbox.py` не удаляет ни одной
        строки; добавленные строки — комментарии, пустые строки и ровно
        одна строка, выключающая атрибут `config`; среди добавленных есть
        комментарий; в тексте головы эта строка стоит не дальше 12 строк от
        присваивания `config.ROLES`/`config.MODELS_LOCAL`.

        Ловит мутацию: заодно правится другая строка песочницы (удалена,
        изменена или добавлен иной код); флаг выключен без комментария о
        причине; выключение вынесено далеко от подмены карты (в `setUp`
        класса).
        """
        diff = file_diff(SANDBOX)
        removed = [l for l in diff if l.startswith("-")]
        added = [l[1:] for l in diff if l.startswith("+")]
        code = [l for l in added if l.strip() and not l.strip().startswith("#")]
        comments = [l for l in added if l.strip().startswith("#")]
        context = f"дифф tests/sandbox.py:\n" + "\n".join(diff)
        self.assertEqual(removed, [], context)
        self.assertEqual(len(code), 1, context)
        self.assertTrue(disables_config_flag(code[0]), context)
        self.assertTrue(comments, context)
        head = (Path(CODE_ROOT) / SANDBOX).read_text(encoding="utf-8").splitlines()
        flag_at = [i for i, l in enumerate(head) if l == code[0]]
        anchors = [i for i, l in enumerate(head)
                   if re.match(r"config\.(ROLES|MODELS_LOCAL)\s*=", l)]
        self.assertTrue(flag_at and anchors, context)
        self.assertLessEqual(min(abs(f - a) for f in flag_at for a in anchors),
                             NEAR, context)

    def test_ac11_protected_tests_untouched(self):
        """Файлы `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py` и `tests/test_fsm_advance_gate_smoke.py` веткой не изменены.

        Зелёный с рождения: держит неизменность двух файлов на всём пути
        задачи — правка любого из них попадает в `changed_paths()`.
        """
        changed = changed_paths()
        for path in PROTECTED:
            self.assertNotIn(path, changed)

    def test_ac12_providers_untouched(self):
        """Ветка не меняет `orchestrator/providers/*`.

        Зелёный с рождения: держит неизменность провайдеров (обрезка
        аргумента лога не снимается ради полного пути Write).
        """
        touched = [p for p in changed_paths()
                   if p.startswith("orchestrator/providers/")]
        self.assertEqual(touched, [])


if __name__ == "__main__":
    unittest.main()
