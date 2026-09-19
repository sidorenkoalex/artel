"""Юнит-тесты сборщика упоминаний путей и сверки с зонами
`scripts/guard.py` (SPEC 01M2XJKQNFTWHYAY4KBBQ1NVY7, требования 1, 2, 4,
5, 6, 8): `mentioned_paths`, `zone_items`, `unclassified_paths`,
`protected_zones`, `spec_unclassified_paths`.

Приёмочная планка задачи (`tasks/01M2XJKQNFTWHYAY4KBBQ1NVY7/
acceptance_tests/`) закрывает сквозные сценарии AC-1..AC-10; здесь —
граничные случаи регулярки и разбора, которые планка не обязана
перечислять поимённо: хвосты с номерами строк и точкой конца
предложения, шаблонные `tasks/<id>/`/`orchestrator/*.py`, URL,
пояснения в скобках внутри строки зон, вложенность защищённых путей.

Существование сверяется с временным корнем через параметр `root`, а не
с реальным деревом пульта — так набор существующих путей задаёт сам
тест.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import resilient_tmp_cleanup  # noqa: E402

EXISTING = ("orchestrator/catalog.py", "orchestrator/fsm.py",
            "scripts/guard.py", "tests/test_foo.py",
            "docs/adr/0001-sample.md", "templates/SPEC.md",
            ".github/workflows/ci.yml", "orchestrator/config.py")


def seed(root: Path, rels=EXISTING) -> None:
    for rel in rels:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# фикстура\n", encoding="utf-8")


class _SeededRootTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name)
        seed(self.root)

    def paths(self, text: str) -> set:
        return guard.mentioned_paths(text, root=self.root)


class MentionedPathsTest(_SeededRootTest):

    def test_line_number_suffix_and_sentence_dot_do_not_break_the_path(self):
        """`orchestrator/fsm.py:695-726` и `… в tests/test_foo.py.` дают
        сами пути без хвостов.

        Ловит мутацию: регулярка после расширения требует границу слова
        без учёта точки конца предложения (или включает `:` в символы
        пути) — второй путь потерялся бы либо первый вернулся бы с
        `:695`."""
        text = ("Адрес — `orchestrator/fsm.py:695-726`, тест кладётся "
                "в tests/test_foo.py.")

        self.assertEqual(self.paths(text),
                         {"orchestrator/fsm.py", "tests/test_foo.py"})

    def test_backticks_parentheses_and_quotes_are_not_part_of_the_path(self):
        """Один и тот же путь в обратных кавычках, в скобках и в
        «ёлочках» — один и тот же результат.

        Ловит мутацию: обрамляющий символ попадает в кандидата (класс
        символов пути расширен на кавычку/скобку) — кандидат перестаёт
        существовать на диске и теряется."""
        variants = ("`scripts/guard.py`", "(scripts/guard.py)",
                    "«scripts/guard.py»", "scripts/guard.py")

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(self.paths(f"Правится {variant} по месту."),
                                 {"scripts/guard.py"})

    def test_directory_candidate_needs_the_trailing_slash(self):
        """`docs/adr/` (со слэшем) — кандидат-каталог, `docs/adr` (без) —
        нет; каталог возвращается со слэшем, как записан.

        Ловит мутацию: ветка «`каталог/` с завершающим слэшем» убрана
        либо, наоборот, любое `a/b` без расширения принимается за путь
        — множество разошлось бы с ожидаемым."""
        self.assertEqual(self.paths("Смотри docs/adr/ целиком."),
                         {"docs/adr/"})
        self.assertEqual(self.paths("Смотри docs/adr целиком."), set())

    def test_template_tails_are_not_candidates(self):
        """`tasks/<id>/SPEC.md` и `orchestrator/*.py` — шаблоны, не
        упоминания каталога `tasks/`/`orchestrator/`.

        Ловит мутацию: граница кандидата-каталога снята (`_PATH_DIR_END`)
        — префикс шаблона `tasks/`/`orchestrator/` вернулся бы как
        существующий каталог и требовал бы классификации у каждого
        SPEC, упоминающего `tasks/<id>/`."""
        (self.root / "tasks").mkdir(exist_ok=True)
        text = ("Артефакты в tasks/<id>/SPEC.md, модули — "
                "`orchestrator/*.py`.")

        self.assertEqual(self.paths(text), set())

    def test_url_and_dotted_suffix_are_not_confused_with_repo_paths(self):
        """Хвост URL `example.com/scripts/guard.py` не даёт
        `scripts/guard.py`; `scripts/guard.py.bak` не даёт
        `scripts/guard.py`.

        Ловит мутацию: левая граница `(?<![A-Za-z0-9_./-])` или правая
        `(?!\\.[A-Za-z0-9_])` снята — оба ложных пути вернулись бы."""
        text = ("См. https://example.com/scripts/guard.py и копию "
                "scripts/guard.py.bak рядом.")

        self.assertEqual(self.paths(text), set())

    def test_missing_paths_are_dropped_and_root_is_config_root_by_default(self):
        """Несуществующий путь отбрасывается; без `root` существование
        сверяется с `config.ROOT` на момент вызова.

        Ловит мутацию: `config.ROOT` захвачен при импорте модуля (не
        читается в вызове) — подмена корня песочницей не действовала
        бы, и `orchestrator/nosuch.py` реального дерева всё равно
        отсутствовал бы, а `tests/test_foo.py` временного корня не
        нашёлся бы."""
        text = "Правим orchestrator/nosuch.py и tests/test_foo.py."
        self.assertEqual(self.paths(text), {"tests/test_foo.py"})

        with mock.patch.object(config, "ROOT", self.root):
            self.assertEqual(guard.mentioned_paths(text),
                             {"tests/test_foo.py"})

    def test_directory_candidate_must_be_a_directory_and_file_a_file(self):
        """`orchestrator/catalog.py/` (каталогом) и `docs/adr` файлом не
        существуют — оба отбрасываются.

        Ловит мутацию: проверка существования — общий `exists()` без
        различия каталог/файл: `Path("orchestrator/catalog.py/")`
        нормализуется в файл и «существует»."""
        self.assertEqual(self.paths("Каталог orchestrator/catalog.py/ пуст."),
                         set())


class ZoneItemsTest(unittest.TestCase):

    def test_parenthetical_note_and_trailing_dot_do_not_hide_the_zone(self):
        """«Зоны: a.py (только сборщик), tests/.» — элементы `a.py`,
        `tests/`, а не «a.py (только сборщик)» и «tests/.».

        Ловит мутацию: элементы берутся только разбиением по запятой
        (без кандидатов `PATH_MENTION`) или без `rstrip(".")` — путь с
        пояснением/точкой не покрыл бы упомянутый файл."""
        items = guard.zone_items(
            "scripts/guard.py (только сборщик), orchestrator/catalog.py,\n"
            "tests/.")

        self.assertLessEqual({"scripts/guard.py", "orchestrator/catalog.py",
                              "tests/"}, items)
        self.assertNotIn("tests/.", items)

    def test_empty_none_and_list_values(self):
        """`None`/пустая строка — пустое множество; список (если
        frontmatter отдаст его списком) — те же элементы.

        Ловит мутацию: `zone_items` падает на `None` или на списке —
        SPEC старой версии без `zones:` ронял бы approve трейсбеком."""
        self.assertEqual(guard.zone_items(None), set())
        self.assertEqual(guard.zone_items(""), set())
        self.assertEqual(guard.zone_items(["a/b.py", "tests/"]),
                         {"a/b.py", "tests/"})


class UnclassifiedPathsTest(_SeededRootTest):

    def test_directory_zone_common_zone_and_declared_text_classify(self):
        """Путь под каталогом-зоной, путь из `config.COMMON_ZONES` и
        путь, названный в объявляющем тексте, — классифицированы;
        остальной — нет, в отсортированном списке.

        Ловит мутацию: покрытие — буквальное равенство строк (без
        `zone_lock._covered_by`/`_is_common_zone`) либо объявляющий
        текст не участвует — в списке оказался бы лишний путь."""
        checked = ("Правим docs/adr/0001-sample.md, orchestrator/config.py, "
                   "scripts/guard.py и orchestrator/fsm.py.")

        result = guard.unclassified_paths(
            checked, {"docs/adr/"}, "Не входит: scripts/guard.py.",
            root=self.root)

        self.assertEqual(result, ["orchestrator/fsm.py"])

    def test_declared_directory_covers_nested_file(self):
        """Каталог, названный в объявляющем тексте («Не входит:
        docs/adr/»), покрывает вложенный файл — той же вложенностью,
        что и зона.

        Ловит мутацию: объявленные пути сверяются равенством, не
        `_covered_by` — файл под объявленным каталогом остался бы
        неклассифицированным."""
        result = guard.unclassified_paths(
            "Смотри docs/adr/0001-sample.md.", set(), "Не входит: docs/adr/.",
            root=self.root)

        self.assertEqual(result, [])

    def test_refusal_text_lists_paths_and_carries_the_hint(self):
        """Текст отказа перечисляет пути и несёт подсказку
        `UNCLASSIFIED_PATH_HINT` буквально.

        Ловит мутацию: подсказка переформулирована/потеряна — Оператор
        на отказе не узнал бы, какими разделами чинить ТЗ/SPEC."""
        text = guard.unclassified_paths_refusal(["a/b.py", "c/d.md"])

        self.assertIn("a/b.py, c/d.md", text)
        self.assertIn(guard.UNCLASSIFIED_PATH_HINT, text)
        for fragment in ("назови в Зонах", "Не входит", "Только чтение",
                         "Приложением"):
            self.assertIn(fragment, text)


class ProtectedZonesTest(unittest.TestCase):

    def test_nested_protected_file_and_exact_protected_entry(self):
        """`templates/SPEC.md` (под `templates/`) и `gates.yaml`
        (буквальная запись) — защищённые; `orchestrator/catalog.py` —
        нет. Значения — из `config.PROTECTED_PATHS`.

        Ловит мутацию: попадание сверяется равенством строк — файл под
        защищённым каталогом не распознался бы."""
        protected_dir = next(p for p in config.PROTECTED_PATHS
                             if p.endswith("/") and not p.startswith("."))
        exact = next(p for p in config.PROTECTED_PATHS if not p.endswith("/"))

        result = guard.protected_zones(
            {protected_dir + "X.md", exact, "orchestrator/catalog.py"})

        self.assertEqual(result, sorted([protected_dir + "X.md", exact]))


SPEC_TEMPLATE = """---
task: T
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
---

# SPEC: фикстура

## Контекст

{context}

## Требования

1. {requirement}

## Критерии приёмки

AC-1. {ac}

## Не входит

{not_included}

## Материалы

{materials}
"""


def spec(zones="orchestrator/catalog.py", context="Ничего.",
         requirement="Ничего.", ac="Ничего.", not_included="Ничего.",
         materials="Нет."):
    return SPEC_TEMPLATE.format(zones=zones, context=context,
                                requirement=requirement, ac=ac,
                                not_included=not_included,
                                materials=materials)


class SpecUnclassifiedPathsTest(_SeededRootTest):

    def check(self, text: str) -> list:
        meta = guard.yamlmini.frontmatter(text) or {}
        return guard.spec_unclassified_paths(text, meta, root=self.root)

    def test_each_checked_section_is_scanned(self):
        """Путь в «## Контекст», «## Требования» и «## Критерии приёмки»
        — каждый по отдельности попадает в отказ.

        Ловит мутацию: из `SPEC_PATH_CHECKED_SECTIONS` выпал раздел —
        путь из него прошёл бы гейт мимо зон (ровно инцидент 06.09 с
        `answer.py` в «Контексте»)."""
        cases = {"context": "Сломан orchestrator/fsm.py.",
                 "requirement": "Починить orchestrator/fsm.py.",
                 "ac": "Проверить orchestrator/fsm.py."}
        for field, value in cases.items():
            with self.subTest(section=field):
                self.assertEqual(self.check(spec(**{field: value})),
                                 ["orchestrator/fsm.py"])

    def test_zones_directory_not_included_and_materials_classify(self):
        """Каталог в `zones:` покрывает вложенный файл; путь, названный в
        «## Не входит» или «## Материалы», классифицирован.

        Ловит мутацию: `SPEC_PATH_DECLARING_SECTIONS` неполон или
        `zones:` сверяется без вложенности — честный SPEC получил бы
        отказ."""
        self.assertEqual(self.check(spec(
            zones="docs/adr/", requirement="Правим docs/adr/0001-sample.md.")),
            [])
        self.assertEqual(self.check(spec(
            requirement="Учесть orchestrator/fsm.py.",
            not_included="Правка orchestrator/fsm.py.")), [])
        self.assertEqual(self.check(spec(
            requirement="Учесть orchestrator/fsm.py.",
            materials="Адрес: orchestrator/fsm.py.")), [])

    def test_missing_zones_field_and_missing_path_do_not_refuse_by_themselves(self):
        """SPEC без `zones:` и без путей в проверяемых разделах — пустой
        список; несуществующий путь (`orchestrator/nosuch.py`) не
        отказывает.

        Ловит мутацию: отсутствие `zones:` трактуется как отказ само по
        себе, либо фильтр существования снят — оба варианта дали бы
        непустой список."""
        no_zones = spec().replace("zones: orchestrator/catalog.py\n", "")
        self.assertEqual(self.check(no_zones), [])
        self.assertEqual(self.check(spec(
            requirement="Создать orchestrator/nosuch.py.")), [])

    def test_check_content_does_not_call_the_spec_path_check(self):
        """`guard.check_content` на SPEC с неклассифицированным путём не
        называет этот путь ни в одной ошибке — проверка живёт вне
        общего ядра (требование 7).

        Ловит мутацию: `spec_unclassified_paths` подключена к
        `_content_errors` — исторические SPEC покраснели бы в CI."""
        with mock.patch.object(config, "ROOT", self.root):
            errors = guard.check_content(
                "tasks/T/SPEC.md", spec(requirement="Починить orchestrator/fsm.py."))

        self.assertEqual([e for e in errors if "orchestrator/fsm.py" in e], [])


if __name__ == "__main__":
    unittest.main()
