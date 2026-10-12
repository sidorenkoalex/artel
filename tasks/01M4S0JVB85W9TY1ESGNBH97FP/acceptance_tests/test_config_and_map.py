"""Факты ветки задачи: константы `config` карточек знаний, запись
`knowledge/` в `config.PROTECTED_PATHS` и свежая карта кода.

Константы — крутилки Оператора (лимиты класса ADR-0002): их значения на
мерже задачи — факт этой задачи, после мержа Оператор вправе их менять,
поэтому проверка значений — разовая. Перечень защищённых путей сверяется
с базой диффа задачи (`DIFF_BASE` помощника пульта): первые 12 записей и
их порядок — как в main, длина 19, последняя — `knowledge/`.

Группа: разовый
Красен до реализации: констант config.KNOWLEDGE_CARD_* и записи `knowledge/` в PROTECTED_PATHS ещё нет, раздела orchestrator/knowledge_cards.py в docs/codebase-map.md нет — все тесты файла красны.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import config  # noqa: E402
from scripts import ci_protected_paths, codebase_map  # noqa: E402

CONFIG_REL = "orchestrator/config.py"
MAP_REL = "docs/codebase-map.md"

EXPECTED = {
    "KNOWLEDGE_CARD_MAX_CHARS": 1200,
    "KNOWLEDGE_CARD_MAX_PER_FILE": 80,
    "KNOWLEDGE_CARD_QUERY_MAX_CHARS": 200,
    "KNOWLEDGE_CARD_SYSTEM_REL": "knowledge/system.yaml",
    "KNOWLEDGE_CARD_OUTPUT_MAX": 12,
    "KNOWLEDGE_CARD_HINT_MAX_KEYS": 40,
    "KNOWLEDGE_CARD_JOURNAL_MAX_PER_TASK": 200,
    "KNOWLEDGE_CARD_STALE_FILE_MAX_BYTES": 2 * 1024 * 1024,
}


def branch_source(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def base_source(rel: str) -> str:
    res = subprocess.run(["git", "show", f"{DIFF_BASE}:{rel}"], cwd=CODE_ROOT,
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"{rel} базы {DIFF_BASE} не прочитан: {res.stderr}")
    return res.stdout


class ConfigConstantsTest(unittest.TestCase):

    def test_ac5_knowledge_card_constants_values(self):
        """В `config` восемь констант карточек знаний с ровно
        предложенными значениями.

        Ловит мутацию: константа части Б не заведена или предел записан в
        килобайтах/иной величиной (`2 * 1000 * 1000`) — значение расходится.
        """
        for name, value in EXPECTED.items():
            with self.subTest(name=name):
                self.assertTrue(hasattr(config, name), f"нет config.{name}")
                self.assertEqual(getattr(config, name), value)
                self.assertEqual(type(getattr(config, name)), type(value))

    def test_ac5_constants_form_one_block_with_adr_0002_comment(self):
        """Восемь присваиваний стоят одним блоком (между ними нет других
        присваиваний верхнего уровня), а комментарий над блоком или в нём
        называет лимиты класса ADR-0002, которые меняет Оператор.

        Ловит мутацию: константы части Б разнесены по файлу либо блок без
        комментария о классе ADR-0002 — тест красен на разрыве блока или на
        отсутствии комментария.
        """
        source = branch_source(CONFIG_REL)
        lines = source.splitlines()
        assign = re.compile(r"^([A-Z][A-Z0-9_]*)\s*(?::[^=]*)?=")
        rows = {}
        for number, line in enumerate(lines, 1):
            m = assign.match(line)
            if m:
                rows.setdefault(m.group(1), number)
        for name in EXPECTED:
            self.assertTrue(name in rows, f"нет присваивания {name}")
        first = min(rows[n] for n in EXPECTED)
        last = max(rows[n] for n in EXPECTED)
        intruders = [n for n, row in rows.items()
                     if first < row < last and n not in EXPECTED]
        self.assertEqual(intruders, [], "блок констант разорван")
        head = first - 1
        while head > 0 and lines[head - 1].lstrip().startswith("#"):
            head -= 1
        comments = "\n".join(line for line in lines[head:last]
                             if line.lstrip().startswith("#"))
        self.assertIn("ADR-0002", comments, "нет комментария о классе ADR-0002")
        self.assertRegex(comments, re.compile(r"Оператор", re.IGNORECASE))


class ProtectedPathsTest(unittest.TestCase):

    def test_ac13_protected_paths_grow_by_knowledge_last(self):
        """`config.PROTECTED_PATHS` — 19 записей, последняя `knowledge/`,
        первые 12 и их порядок — как в базе ветки;
        `is_protected_path("knowledge/system.yaml")` истинно.

        Ловит мутацию: запись вставлена не в конец (сдвинула прежние) либо
        прежняя запись снята ради новой — срез `[:12]` или длина расходятся
        с базой.
        """
        base, reason = ci_protected_paths.protected_paths_from_source(
            base_source(CONFIG_REL))
        self.assertIsNotNone(base, reason)
        current = list(config.PROTECTED_PATHS)
        self.assertEqual(len(current), 19)
        self.assertEqual(current[-1], "knowledge/")
        self.assertEqual(current[:12], list(base)[:12])
        self.assertTrue(config.is_protected_path("knowledge/system.yaml"))

    def test_ac13_entry_is_in_assignment_literal(self):
        """`protected_paths_from_source` на тексте `orchestrator/config.py`
        ветки отдаёт 19 путей с `knowledge/` последним — запись стоит в
        литерале присваивания, а не добавлена после него.

        Ловит мутацию: `PROTECTED_PATHS += ("knowledge/",)` отдельной
        строкой — импорт видит 19 записей, а разбор литерала джобом CI —
        18.
        """
        paths, reason = ci_protected_paths.protected_paths_from_source(
            branch_source(CONFIG_REL))
        self.assertIsNotNone(paths, reason)
        self.assertEqual(len(paths), 19)
        self.assertEqual(paths[-1], "knowledge/")


class CodebaseMapTest(unittest.TestCase):

    def test_ac15_codebase_map_fresh_and_names_module(self):
        """`docs/codebase-map.md` ветки совпадает с регенерацией
        `scripts/codebase_map.py` (без строки `built_at_sha`) и содержит
        раздел `orchestrator/knowledge_cards.py`.

        Ловит мутацию: карта не регенерирована после правки `config.py`/
        `notes.py`/`targets.py` или нового модуля — раздела нет либо
        перечень функций/импортов устарел.
        """
        root = Path(CODE_ROOT)
        modules, resolved, imported_by = codebase_map.build_modules(root)
        fresh = codebase_map.render(modules, resolved, imported_by, "x")
        on_disk = (root / MAP_REL).read_text(encoding="utf-8")

        def body(text: str) -> list:
            return [line for line in text.splitlines()
                    if not line.startswith("built_at_sha:")]

        self.assertIn("## orchestrator/knowledge_cards.py", on_disk.splitlines())
        self.assertEqual(body(on_disk), body(fresh), "карта не свежая")


if __name__ == "__main__":
    unittest.main()
