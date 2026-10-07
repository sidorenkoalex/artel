"""Свойства полной карты, проекции и брифов после удаления секций tests/.

Группа: долгоживущий
Красен до реализации: проекция пока оставляет секции tests/, а указатель не говорит об их отсутствии.
"""

import random
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import brief, config, store
from scripts import codebase_map
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git)

OMISSION_RE = re.compile(
    r"(?s)(?:нет|отсутств|без|исключ|опущ|пропущ|удал|не вход|не содерж)"
    r".{0,80}tests/|tests/.{0,80}"
    r"(?:нет|отсутств|исключ|опущ|пропущ|удал|не вход|не содерж)")


class ProjectionTest(unittest.TestCase):
    def test_ac1_tests_sections_and_their_fields_disappear(self):
        """Верхний и вложенный тестовые модули исчезают из проекции целиком.

        Ловит мутацию: фильтр удаляет только верхний уровень tests/, и
        заголовок вложенного модуля остаётся в ответе.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        names = ["tests/test_alpha.py", "tests/sub/test_beta.py"]
        rng.shuffle(names)
        for name in names:
            marker = f"маркер_{rng.randrange(2**32)}"
            source = ("# Карта\n\n" + f"## {name}\n\n"
                      f"**Назначение:** {marker}\n\n"
                      "**Публичные функции:** (нет)\n\n"
                      "**Импортирует:** —\n\n"
                      "**Импортируется:** —\n")
            projected = codebase_map.project_for_brief(source)
            self.assertNotIn(f"## {name}", projected, f"зерно: {seed}")
            self.assertNotIn(marker, projected, f"зерно: {seed}")
            self.assertEqual("# Карта\n\n", projected, f"зерно: {seed}")

    def test_ac2_other_sections_and_header_keep_previous_projection(self):
        """Шапка, порядок и три поля секций пульта и сценариев сохраняются.

        Ловит мутацию: общее удаление последнего блока захватывает
        «Импортирует» у scripts/, и ожидаемые байты проекции расходятся.
        """
        for order in (("scripts/alpha.py", "orchestrator/beta.py"),
                      ("orchestrator/beta.py", "scripts/alpha.py")):
            header = "---\nbuilt_at_sha: abc\n---\n\n# Карта\n\n"
            sections = []
            expected = []
            for name in order:
                three = (f"## {name}\n\n**Назначение:** роль {name}\n\n"
                         "**Публичные функции:**\n- `run`\n\n"
                         "**Импортирует:** `orchestrator/config.py`")
                sections.append(three + "\n\n**Импортируется:** —\n\n")
                expected.append(three + "\n\n")
            sections.insert(1, "## tests/sub/hidden.py\n\n"
                               "**Назначение:** Скрытая секция\n\n"
                               "**Публичные функции:** (нет)\n\n"
                               "**Импортирует:** —\n\n"
                               "**Импортируется:** —\n\n")
            result = codebase_map.project_for_brief(header + "".join(sections))
            self.assertEqual(header + "".join(expected), result)

    def test_ac3_projection_is_idempotent_and_does_not_access_io(self):
        """Карта трёх видов повторно проецируется без диска и git.

        Ловит мутацию: повторный проход обрезает уже короткую секцию
        scripts/ или вызывает git для определения вида секции.
        """
        source = "# Карта\n\n"
        for name in ("orchestrator/a.py", "scripts/b.py", "tests/c.py"):
            source += (f"## {name}\n\n**Назначение:** {name}\n\n"
                       "**Публичные функции:** (нет)\n\n"
                       "**Импортирует:** —\n\n**Импортируется:** —\n\n")
        with mock.patch.object(Path, "read_text", side_effect=AssertionError("диск")), \
                mock.patch("builtins.open", side_effect=AssertionError("диск")), \
                mock.patch.object(subprocess, "run", side_effect=AssertionError("git")):
            once = codebase_map.project_for_brief(source)
            twice = codebase_map.project_for_brief(once)
        self.assertEqual(once, twice)

    def test_ac4_render_keeps_full_tests_sections(self):
        """Полная карта для одного и нескольких модулей tests/ сохраняет прежние байты.

        Ловит мутацию: фильтрацию tests/ переносят в render, и в полной
        карте пропадают заголовок или блок «Импортируется».
        """
        header = ("---\nbuilt_at_sha: abc\n---\n\n# Codebase-map пульта\n\n"
                  "Автосгенерировано `scripts/codebase_map.py` — правки руками "
                  "теряются при следующем запуске.\n\n")
        for names in (("tests/a.py",), ("tests/a.py", "tests/sub/b.py")):
            modules = [codebase_map.ModuleInfo(Path(name), name, ["check"], [])
                       for name in names]
            imports = {name: [] for name in names}
            imported_by = {name: [] for name in names}
            rendered = codebase_map.render(modules, imports, imported_by, "abc")
            sections = "".join(
                f"## {name}\n\n**Назначение:** {name}\n\n"
                "**Публичные функции:**\n- `check`\n\n"
                "**Импортирует:** —\n\n**Импортируется:** —\n\n"
                for name in names)
            self.assertEqual(header + sections.rstrip("\n") + "\n", rendered)

    def test_ac5_projection_note_names_omission_and_full_map(self):
        """Указатель при проекции говорит о пропуске tests/ и полной карте.

        Ловит мутацию: текст указателя оставляют старым, поэтому роль
        видит путь к карте, но не узнаёт, что проекция лишена tests/.
        """
        projected = codebase_map.project_for_brief("# Карта\n\n")
        candidates = (projected.lower(), brief.MAP_PROJECTION_NOTE.lower())
        self.assertTrue(any(
            "docs/codebase-map.md" in message
            and "рабочего каталога" in message
            and OMISSION_RE.search(message)
            for message in candidates), "ни шапка, ни указатель не объясняют пропуск tests/")


class BriefProjectionTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        self.map_text = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
                         "---\n\n# Карта\n\n"
                         "## orchestrator/a.py\n\n**Назначение:** A\n\n"
                         "**Публичные функции:** (нет)\n\n**Импортирует:** —\n\n"
                         "**Импортируется:** —\n\n"
                         "## tests/sub/b.py\n\n**Назначение:** УДАЛЁННЫЙ-МАРКЕР\n\n"
                         "**Публичные функции:** (нет)\n\n**Импортирует:** —\n\n"
                         "**Импортируется:** —\n")
        (self.root / "docs" / "codebase-map.md").write_text(
            self.map_text, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        (config.TASKS / "T001").mkdir(parents=True)
        (config.TASKS / "T001" / "SPEC.md").write_text(
            "# Спецификация\n", encoding="utf-8")
        store.create_schema(store.db())

    def test_ac6_developer_brief_carries_projection_and_note(self):
        """Бриф разработчика несёт секцию пульта и поясняет пропуск tests/.

        Ловит мутацию: бриф получает исходную карту вместо проекции,
        и в его тексте появляется заголовок вложенного теста.
        """
        for name in ("tests/sub/b.py", "tests/b.py"):
            (self.root / "docs" / "codebase-map.md").write_text(
                self.map_text.replace("tests/sub/b.py", name), encoding="utf-8")
            with mock.patch.object(brief.gitcmd, "show", disk_backed_show), \
                    mock.patch.object(brief.gitcmd, "ls_tree_files", disk_backed_ls_tree_files), \
                    mock.patch.object(brief.gitcmd, "git", fake_git):
                result = brief.developer_brief(store.db(), "T001")
            self.assertIn("## orchestrator/a.py", result)
            self.assertNotIn(f"## {name}", result)
            self.assertNotIn("УДАЛЁННЫЙ-МАРКЕР", result)
            self.assertIn("docs/codebase-map.md", result)
            self.assertRegex(result.lower(), OMISSION_RE)

    def test_ac7_analyst_brief_carries_projection_and_note(self):
        """Бриф аналитика несёт секцию пульта и поясняет пропуск tests/.

        Ловит мутацию: компонент аналитика использует полную карту,
        поэтому в тексте остаётся поле тестового модуля.
        """
        for name in ("tests/sub/b.py", "tests/b.py"):
            (self.root / "docs" / "codebase-map.md").write_text(
                self.map_text.replace("tests/sub/b.py", name), encoding="utf-8")
            with mock.patch.object(brief.gitcmd, "show", disk_backed_show), \
                    mock.patch.object(brief.gitcmd, "ls_tree_files", disk_backed_ls_tree_files), \
                    mock.patch.object(brief.gitcmd, "git", fake_git):
                result = brief.analyst_map_component(store.db(), "T001")
            self.assertIn("## orchestrator/a.py", result)
            self.assertNotIn(f"## {name}", result)
            self.assertNotIn("УДАЛЁННЫЙ-МАРКЕР", result)
            self.assertIn("docs/codebase-map.md", result)
            self.assertRegex(result.lower(), OMISSION_RE)
