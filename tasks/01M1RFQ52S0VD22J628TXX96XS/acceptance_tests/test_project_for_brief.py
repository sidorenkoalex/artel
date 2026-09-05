"""Приёмочные тесты 01M1RFQ52S0VD22J628TXX96XS — AC-1..AC-8: чистая
функция `scripts.codebase_map.project_for_brief`.

Источник — только tasks/01M1RFQ52S0VD22J628TXX96XS/SPEC.md, раздел
«Критерии приёмки». Фикстуры карты (`_fixtures.small_map`) строятся
РЕАЛЬНЫМ рендерером `codebase_map.render` на синтетических `ModuleInfo`
трёх видов секций — см. `_fixtures.py`.

Красен до реализации: `scripts/codebase_map.py` ещё не содержит
`project_for_brief` — `from scripts import codebase_map` проходит (модуль
существует), но `codebase_map.project_for_brief` падает AttributeError
в каждом тесте этого файла, пока функция не написана (задача этой
эскалации SPEC, требование 1).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import codebase_map  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures  # noqa: E402

REAL_MAP_PATH = (Path(__file__).resolve().parents[3] / "docs"
                 / "codebase-map.md")


class ProjectForBriefPurityTest(unittest.TestCase):
    """AC-1: функция не читает диск и не обращается к git."""

    def test_ac1_does_not_touch_disk_or_subprocess(self):
        """Прогоняет `project_for_brief` на фикстуре с патчем `Path.
        read_text`/`Path.write_text`/`subprocess.run`, каждый из которых
        роняет тест при вызове — функция обязана дойти до конца, ни разу
        их не потревожив.

        Ловит мутацию: реализация внутри `project_for_brief` вызывает
        `Path(...).read_text(...)` (например, «на всякий случай»
        перечитывает файл карты вместо работы с переданным аргументом)
        или зовёт `subprocess.run`/`git` — тест краснеет на `AssertionError`
        из побочного вызова вместо того, чтобы молча пройти.
        """
        fixture = _fixtures.small_map()

        def boom(*a, **kw):
            raise AssertionError(
                "project_for_brief не должна читать/писать диск или "
                "звать subprocess — она чистая функция строка-в-строку")

        with mock.patch.object(Path, "read_text", side_effect=boom), \
                mock.patch.object(Path, "write_text", side_effect=boom), \
                mock.patch("subprocess.run", side_effect=boom):
            result = codebase_map.project_for_brief(fixture)

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class OrchestratorScriptsSectionsTest(unittest.TestCase):
    """AC-2: секции `orchestrator/*` и `scripts/*` сохраняют «Назначение»,
    «Публичные функции», «Импортирует», теряют «Импортируется»."""

    def setUp(self):
        self.fixture = _fixtures.small_map()
        self.projected = codebase_map.project_for_brief(self.fixture)

    def test_ac2_orchestrator_section_keeps_three_blocks_drops_importers(self):
        """На секции `orchestrator/foo.py` (Импортируется непусто в
        исходнике — `tests/test_baz.py`) блоки «Назначение»/«Публичные
        функции»/«Импортирует» остаются буквально, блок «Импортируется»
        отсутствует целиком.

        Ловит мутацию: удаление применено к неверному блоку (например,
        по ошибке вырезан «Импортирует» вместо «Импортируется») либо
        правило вовсе не применено к секциям `orchestrator/*` — тест
        покраснеет либо на пропавшем «Импортирует: `scripts/bar.py`»,
        либо на всё ещё присутствующем «Импортируется».
        """
        block = _fixtures.section_block(self.projected, "orchestrator/foo.py")

        self.assertIn("**Назначение:** Оркестрирует нечто важное.", block)
        self.assertIn("**Публичные функции:**", block)
        self.assertIn("`do_thing`", block)
        self.assertIn("`run_it`", block)
        self.assertIn("**Импортирует:** `scripts/bar.py`", block)
        self.assertNotIn("Импортируется", block)

    def test_ac2_scripts_section_keeps_three_blocks_drops_importers(self):
        """Тот же контроль на секции `scripts/bar.py` (в исходнике —
        двое «Импортируется»: `orchestrator/foo.py`, `tests/test_baz.py`).

        Ловит мутацию: правило проекции применено только к `orchestrator/
        *`, а `scripts/*` по ошибке не тронут — блок «Импортируется»
        остался бы виден.
        """
        block = _fixtures.section_block(self.projected, "scripts/bar.py")

        self.assertIn("**Назначение:** Скрипт вспомогательный.", block)
        self.assertIn("**Публичные функции:**", block)
        self.assertIn("`run_bar`", block)
        self.assertIn("**Импортирует:** —", block)
        self.assertNotIn("Импортируется", block)


class TestsSectionsTest(unittest.TestCase):
    """AC-3: секции `tests/*` — только заголовок и «Назначение»."""

    def setUp(self):
        self.fixture = _fixtures.small_map()
        self.projected = codebase_map.project_for_brief(self.fixture)

    def test_ac3_tests_section_keeps_only_heading_and_purpose(self):
        """Секция `tests/test_baz.py` (в исходнике — непустые «Публичные
        функции» и «Импортирует», «Импортируется» — «—») после проекции
        несёт заголовок и «Назначение» одной строкой, «Публичные
        функции»/«Импортирует»/«Импортируется» отсутствуют.

        Ловит мутацию: для `tests/*` сохранён (не удалён) блок
        «Публичные функции» или «Импортирует» — правило AC-3 сильнее
        AC-2 (у тестов удаляются ВСЕ три блока, не только
        «Импортируется») и мутация «применили правило orchestrator/
        scripts и к tests/*» тест обязан поймать.
        """
        block = _fixtures.section_block(self.projected, "tests/test_baz.py")

        self.assertIn("## tests/test_baz.py", block)
        self.assertIn("**Назначение:** Тестирует нечто важное.", block)
        self.assertNotIn("Публичные функции", block)
        self.assertNotIn("Импортир", block,
                         "ни «Импортирует», ни «Импортируется» не должны "
                         "остаться в секции tests/*")


class HeaderPreservedTest(unittest.TestCase):
    """AC-4: шапка карты не меняется проекцией."""

    def test_ac4_frontmatter_title_and_autogen_line_are_byte_identical(self):
        """Сравнивает текст ДО первого `## <путь>` в исходнике и в
        результате `project_for_brief` — обязаны совпасть побайтово.

        Ловит мутацию: реализация ошибочно трогает шапку (например,
        нормализует перевод строки, меняет заголовок «# Codebase-map
        пульта» или строку про автогенерацию) — сравнение целой шапки
        строкой, а не отдельных полей, ловит любую такую правку, а не
        только конкретно `built_at_sha`.
        """
        fixture = _fixtures.small_map()
        projected = codebase_map.project_for_brief(fixture)

        self.assertEqual(_fixtures.header_block(fixture),
                         _fixtures.header_block(projected))


class SectionOrderPreservedTest(unittest.TestCase):
    """AC-5: порядок и заголовки секций не меняются."""

    def test_ac5_section_headers_are_identical_and_in_the_same_order(self):
        """Список заголовков `## <путь>` исходника и проекции обязан
        совпасть поэлементно — ни одна секция не добавлена, не удалена,
        не переставлена.

        Ловит мутацию: реализация фильтрует секции (например, по
        ошибке отбрасывает секцию `tests/*` целиком вместо урезания её
        блоков) или переупорядочивает их (например, группирует все
        `tests/*` в конец) — список заголовков разойдётся с исходным.
        """
        fixture = _fixtures.small_map()
        projected = codebase_map.project_for_brief(fixture)

        self.assertEqual(_fixtures.section_headers(fixture),
                         _fixtures.section_headers(projected))


class IdempotenceTest(unittest.TestCase):
    """AC-7: `project_for_brief(project_for_brief(x)) == project_for_brief(x)`."""

    def test_ac7_projecting_the_projection_is_a_no_op(self):
        """Повторное применение проекции к уже спроецированному тексту
        не меняет его.

        Ловит мутацию: правило для `orchestrator/scripts` ищет блок
        «Импортируется» по позиции (например, «третий блок секции»)
        вместо метки — на уже урезанной секции (три блока вместо
        четырёх) такое правило срезало бы ЛИШНИЙ блок («Импортирует»)
        на втором проходе, и повтор перестал бы быть no-op.
        """
        fixture = _fixtures.small_map()
        once = codebase_map.project_for_brief(fixture)
        twice = codebase_map.project_for_brief(once)

        self.assertEqual(once, twice)


class RealMapSizeTest(unittest.TestCase):
    """AC-8: на тексте текущего docs/codebase-map.md проекция — не
    больше 50% байт исходника."""

    def test_ac8_projection_of_the_real_map_is_at_most_half_its_bytes(self):
        """Читает настоящий `docs/codebase-map.md` дерева (тот же файл,
        которым уже пользуется CI-джоба `codebase-map`), применяет
        `project_for_brief` и сравнивает размер в байтах UTF-8.

        Ловит мутацию: правило «Импортируется» удаляется только у
        `orchestrator/*`, но не у `scripts/*» (SPEC, «Контекст»: 43%
        байт полной карты — секции `tests/*`, 32%+27% — блоки
        «Импортируется»/«Импортирует» — пропуск любой из веток проекции
        не даёт заявленных 46%/50% на реальном файле).
        """
        if not REAL_MAP_PATH.is_file():
            self.skipTest(f"{REAL_MAP_PATH} отсутствует в рабочем дереве")
        real_text = REAL_MAP_PATH.read_text(encoding="utf-8")

        projected = codebase_map.project_for_brief(real_text)

        original_size = len(real_text.encode("utf-8"))
        projected_size = len(projected.encode("utf-8"))
        self.assertLessEqual(
            projected_size, original_size * 0.5,
            f"проекция {projected_size} байт — больше половины исходных "
            f"{original_size} байт docs/codebase-map.md")


if __name__ == "__main__":
    unittest.main()
