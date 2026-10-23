"""Правка докстринга `orchestrator/artel.py` относительно базы ветки задачи.

Группа: разовый

Сравнивается текст модуля в базе диффа задачи (`DIFF_BASE` помощника
пульта, `git show <база>:orchestrator/artel.py`) с текстом модуля рабочей
копии кода. Свойства реестра и шапки, обязанные держаться после мержа, —
в долгоживущем `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`.

Красен до реализации: в блоке «Команды:» ещё нет строк семи команд (AC-1), шапка говорит «Артель, Фаза 0» и «Все гейты Фазы 0 — ручные» (AC-2); AC-6 зелен и до реализации — ветка ещё не меняет ни кода `artel.py`, ни существующих файлов tests/.
"""

import ast
import collections
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

ARTEL = "orchestrator/artel.py"

NEW_COMMANDS = (
    "workspace <id>",
    "report",
    "acceptance-dry-run <id>",
    "plank-run <id> [<файл>]",
    "suite-run <id> [--wait <минуты> | --failed]",
    "preflight <id>",
    "guard <id> [<файл>]",
)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", CODE_ROOT, *args], capture_output=True,
                          text=True, encoding="utf-8")


def base_source() -> str:
    res = git("show", f"{DIFF_BASE}:{ARTEL}")
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{ARTEL}: {res.stderr}")
    return res.stdout


def head_source() -> str:
    return (Path(CODE_ROOT) / ARTEL).read_text(encoding="utf-8")


def docstring(source: str) -> str:
    return ast.get_docstring(ast.parse(source), clean=False)


def commands_block(doc: str) -> list[str]:
    lines = doc.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "Команды:")
    block = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        block.append(line)
    return block


def split_at_states(doc: str) -> tuple[str, str]:
    idx = doc.find("Состояния:")
    if idx == -1:
        raise AssertionError("в докстринге нет строки «Состояния:»")
    return doc[:idx], doc[idx:]


class CommandsBlockTest(unittest.TestCase):

    def test_ac1_seven_commands_added_existing_lines_kept(self):
        """Блок «Команды:» несёт семь новых команд в оформлении соседей; прежние строки целы.

        Каждая форма стоит в строке блока с отступом, слева от неё — отступ
        начала строки или «| », справа — « |» либо конец строки; каждая
        строка блока базы присутствует в блоке рабочей копии без изменений
        (с учётом повторов).
        Ловит мутацию: команду дописали в конец существующей строки
        (`[--interval SEC] [--until <state>] | report`) — прежняя строка
        изменилась; либо форму записали иначе (`plank-run <id> [файл]`)."""
        base_block = commands_block(docstring(base_source()))
        head_block = commands_block(docstring(head_source()))
        for form in NEW_COMMANDS:
            pattern = re.compile(r"(?:^ {2,}|\| )" + re.escape(form)
                                 + r"(?: \||$)")
            with self.subTest(form=form):
                self.assertTrue(
                    any(pattern.search(line) for line in head_block),
                    f"в блоке «Команды:» нет строки с «{form}» в оформлении "
                    f"соседних строк")
        lost = collections.Counter(base_block) - collections.Counter(head_block)
        self.assertEqual(list(lost.elements()), [],
                         "строки блока «Команды:» базы изменены или удалены")


class HeaderTest(unittest.TestCase):

    def test_ac2_header_states_gates_and_rest_unchanged(self):
        """Шапка без «Фаза 0» утверждает ручные и автогейт; всё после «Состояния:» прежнее.

        Первая строка и текст до `Состояния:` — без «Фаза 0»/«Фазы 0»,
        называют `spec_gate`, `merge_gate`, ручной характер
        (approve/reject из CLI), `acceptance` автогейтом по `gates.yaml`
        (`orchestrator/fsm_autogate.py`) и ожидание Оператора. Текст от
        `Состояния:` до конца совпадает с базой, если убрать из него строки,
        добавленные в блок «Команды:».
        Ловит мутацию: «Фаза 0» осталась в первой строке; шапка не
        называет `fsm_autogate.py` или Оператора; при правке задета схема
        состояний или абзац «Фаза 0: гейт плана …»."""
        base_doc = docstring(base_source())
        head_doc = docstring(head_source())
        first = head_doc.lstrip("\n").splitlines()[0]
        self.assertNotIn("Фаза 0", first, f"первая строка: {first!r}")
        head_header, head_tail = split_at_states(head_doc)
        for banned in ("Фаза 0", "Фазы 0"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, head_header)
        flat = " ".join(head_header.split())
        for needle in ("spec_gate", "merge_gate", "ручн", "approve/reject",
                       "acceptance", "автогейт", "gates.yaml",
                       "orchestrator/fsm_autogate.py", "Оператор"):
            with self.subTest(needle=needle):
                self.assertIn(needle, flat, f"шапка без {needle!r}")
        _, base_tail = split_at_states(base_doc)
        added = (collections.Counter(commands_block(head_doc))
                 - collections.Counter(commands_block(base_doc)))
        kept = []
        for line in head_tail.splitlines():
            if added[line] > 0:
                added[line] -= 1
                continue
            kept.append(line)
        self.assertEqual(kept, base_tail.splitlines(),
                         "схема состояний или абзацы после неё изменены")


class DiffScopeTest(unittest.TestCase):

    def test_ac6_artel_code_unchanged_and_existing_tests_untouched(self):
        """Вне докстринга `artel.py` не изменён; существующие файлы tests/ не тронуты.

        Деревья разбора модуля базы и рабочей копии без докстринга модуля
        совпадают (`table`, `main()`, разборщики аргументов — внутри них);
        каждый путь задачи под `tests/` в базе отсутствовал.
        Ловит мутацию: разработчик заодно поправил строку `table` или
        `_cmd_pin_update`, либо дописал свой тест в существующий файл
        tests/."""
        def without_docstring(source: str) -> str:
            tree = ast.parse(source)
            body = tree.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                tree.body = body[1:]
            return ast.dump(tree)

        self.assertEqual(without_docstring(head_source()),
                         without_docstring(base_source()),
                         f"{ARTEL}: изменён код вне докстринга модуля")
        touched = [p for p in changed_paths() if p.startswith("tests/")
                   and git("cat-file", "-e", f"{DIFF_BASE}:{p}").returncode == 0]
        self.assertEqual(touched, [], "изменены существующие файлы tests/")


if __name__ == "__main__":
    unittest.main()
