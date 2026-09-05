"""Юнит-тесты гейта зон на `in_dev -> review` (tasks/
01M1P9QCHPHSCEA6TK13PV85SP): чистые функции разбора (`_split_zone_paths`,
`_touches_zone`, `_plan_zones_extension_paths`) и fail-closed на сбое git —
тот же класс, что `tests/test_capacity_gate.py` закрывает для соседнего
гейта ёмкости, а его собственная приёмочная планка (`tasks/
01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/`) намеренно не бьёт: там git
всегда отвечает.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class SplitZonePathsTest(unittest.TestCase):

    def test_comma_separated_paths_are_trimmed(self):
        """Ловит мутацию: `.strip()` на элементе убран/сломан — вокруг
        пути остаются пробелы (` b.py `), и он не совпадает с реальным
        путём диффа при сверке зон."""
        self.assertEqual(
            fsm_advance._split_zone_paths("a.py, b.py ,c/"),
            ["a.py", "b.py", "c/"])

    def test_none_gives_empty_list(self):
        """Ловит мутацию: `None` (поле не заполнено) трактуется как список
        из одного пустого пути, а не как «зон нет»."""
        self.assertEqual(fsm_advance._split_zone_paths(None), [])

    def test_empty_string_gives_empty_list(self):
        """Ловит мутацию: проверка `if not raw` убрана/ослаблена — пустая
        строка идёт в `"".split(",")` и даёт список из одного пустого
        пути вместо пустого списка (та же ловушка, что и `None`)."""
        self.assertEqual(fsm_advance._split_zone_paths(""), [])

    def test_blank_entries_are_dropped(self):
        """Ловит мутацию: фильтр `if p.strip()` убран — двойная запятая
        (пустой элемент между `a.py` и `b.py`) попадает в список как
        пустая строка, и пустой путь ложно матчит любой файл диффа
        (`_touches_zone` — `path.startswith("")` истинно всегда)."""
        self.assertEqual(fsm_advance._split_zone_paths("a.py,, b.py"),
                         ["a.py", "b.py"])


class TouchesZoneTest(unittest.TestCase):

    def test_exact_file_match(self):
        """Ловит мутацию: сравнение `path == z` убрано (осталось только
        `startswith`, испорченное, например, разворотом операндов) —
        путь, буквально совпадающий с зоной-файлом, обязан матчиться."""
        self.assertTrue(
            fsm_advance._touches_zone("orchestrator/store.py",
                                      ["orchestrator/store.py"]))

    def test_directory_zone_matches_file_under_it(self):
        """Ловит мутацию: `startswith` заменён на строгое равенство —
        зона-директория несёт trailing `/` (COMMON_ZONES: `"tests/"`) —
        путь под ней обязан матчиться префиксом, не только листингом
        каталога буквально."""
        self.assertTrue(
            fsm_advance._touches_zone("tests/test_x.py", ["tests/"]))

    def test_unrelated_path_does_not_match(self):
        """Ловит мутацию: сравнение ослаблено до подстроки где угодно
        (`in`), не префикса — `docs/x.py` не обязан матчить зону
        `orchestrator/`."""
        self.assertFalse(
            fsm_advance._touches_zone("docs/x.py", ["orchestrator/"]))

    def test_file_zone_matches_as_prefix_of_unrelated_file(self):
        """Ловит мутацию: намеренное поведение (тот же `startswith`, что и
        `config.PROTECTED_PATHS`/`_touches_protected_path`) заменено на
        точное сравнение путей — зона-файл без trailing `/`
        (`orchestrator/store.py`) СОВПАДАЕТ по префиксу с чужим файлом
        того же имени (`orchestrator/store.py.bak`); список зон
        намеренно не эксклюзивный, а не баг, который стоит чинить здесь."""
        self.assertTrue(
            fsm_advance._touches_zone("orchestrator/store.py.bak",
                                      ["orchestrator/store.py"]))


class PlanZonesExtensionPathsTest(unittest.TestCase):

    def test_no_section_gives_none(self):
        """Ловит мутацию: `guard.section_body` на отсутствующей секции
        возвращает не пустую строку, а весь текст (или проверка `is
        None` заменена на falsy-проверку) — исключение AC-3 открылось бы
        для PLAN, вовсе не заявлявшего расширение зон."""
        text = "# PLAN\n\n## Подход\n\nтекст\n"
        self.assertIsNone(fsm_advance._plan_zones_extension_paths(text))

    def test_section_without_paths_line_gives_none(self):
        """Ловит мутацию: раздел «## Расширение зон» сам по себе (без
        строки `Пути:`) ошибочно открывал бы исключение AC-3."""
        text = "## Расширение зон\n\nОбоснование без строки Пути.\n"
        self.assertIsNone(fsm_advance._plan_zones_extension_paths(text))

    def test_section_with_paths_line_is_parsed(self):
        """Ловит мутацию: срез `line[len("Пути:"):]` сдвинут (обрезает
        первый символ пути или оставляет сам префикс `Пути:`) — список
        путей исключения AC-3 выходит искажённым, и мандат Оператора на
        реальные пути перестаёт совпадать."""
        text = ("## Расширение зон\n\nПути: docs/a.md, docs/b.md\n\n"
               "Обоснование ниже.\n")
        self.assertEqual(
            fsm_advance._plan_zones_extension_paths(text),
            ["docs/a.md", "docs/b.md"])


class ZonesGateGitFailureTest(TmpRootTest):
    """Fail-closed на сбое git (тот же принцип ADR-0002, что
    `_capacity_gate_refuses`/лок `acceptance_tests/`): список файлов диффа
    не получен — сверка с зонами невозможна, переход отказывает, не
    пропускает молча."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.t = {"title": "Тест гейта зон", "branch": "task/t001-x",
                 "zones": "orchestrator/store.py", "zones_extension": None}

    def test_git_not_answering_diff_names_refuses(self):
        """Ловит мутацию: проверка `if files is None: ... return True`
        убрана/заменена на `return False` — `diff_names`, не ответивший
        списком файлов, молча пропустил бы переход вместо явного отказа
        (fail-open вместо fail-closed, ADR-0002)."""
        with mock.patch.object(gitcmd, "diff_names", return_value=None):
            refuses = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, self.t, "task/t001-x", "PLAN\n")
        self.assertTrue(refuses)
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.task_id,))]
        self.assertTrue(any("гейт зон" in d for d in details))


class ZonesGateNoDeclaredZoneSkipsTest(TmpRootTest):
    """Задача без заявленной зоны вовсе (`zones`/`zones_extension` оба
    пусты — SPEC старой версии до `guard.requires_zones`, либо тестовая
    фикстура, заведённая мимо гейта SPEC) — гейт не звонится (AC-7,
    `PLAN.md`, «Риски»): опт-ин механики, не ретроактивный запрет.

    Ловит мутацию: гейт считает пустой `zones` как «зона пуста, всё вне
    зоны» вместо «зона не декларировалась вовсе» — любой существующий
    тест, заводящий задачу в обход гейта SPEC (без `zones`), начал бы
    отказывать на первом же файле вне `COMMON_ZONES`."""

    def test_no_zones_and_no_extension_skips_the_gate(self):
        store.create_schema(store.db())
        conn = store.db()
        task_id = "T001"
        store.insert_task(conn, task_id, "Тест", "in_dev", "task/t001-x",
                          config.DEFAULT_TARGET, 10.0)
        t = {"title": "Тест", "branch": "task/t001-x", "zones": None,
            "zones_extension": None}

        def boom(*args, **kwargs):
            raise AssertionError("гейт зон не обязан звать diff_names без "
                                 "заявленной зоны")

        with mock.patch.object(gitcmd, "diff_names", boom):
            refuses = fsm_advance._zones_gate_refuses(
                conn, task_id, t, "task/t001-x", "PLAN\n")
        self.assertFalse(refuses)


class ZonesGateExternalTargetSkipsTest(TmpRootTest):
    """Внешний (не self) target — гейт не проверяется вовсе (тот же довод,
    что `_capacity_gate_refuses`: diff в `config.ROOT` не видит код
    внешнего target)."""

    def test_external_target_never_calls_diff_names(self):
        store.create_schema(store.db())
        conn = store.db()
        task_id = "T001"
        store.insert_task(conn, task_id, "Тест", "in_dev", "task/t001-x",
                          "some-external-target", 10.0)
        self.assertNotEqual(store.task_target(conn, task_id),
                            config.DEFAULT_TARGET)
        t = {"title": "Тест", "branch": "task/t001-x", "zones": None,
            "zones_extension": None}

        def boom(*args, **kwargs):
            raise AssertionError("гейт зон не обязан звать diff_names "
                                 "для внешнего target")

        with mock.patch.object(gitcmd, "diff_names", boom):
            refuses = fsm_advance._zones_gate_refuses(
                conn, task_id, t, "task/t001-x", "PLAN\n")
        self.assertFalse(refuses)


if __name__ == "__main__":
    unittest.main()
