"""Юнит-тесты формата секции «## Деление» SPEC
(01M1SHJZCE0Y4DXAAWQ2W585A7, требование 1) — `scripts/guard.py::
parse_division_subsections`/`division_section_errors`.

Приёмочные тесты задачи (`tasks/01M1SHJZCE0Y4DXAAWQ2W585A7/
acceptance_tests/test_ac2_*`/`test_ac3_*`/`test_ac4_*`) уже закрывают
AC-2..AC-4/AC-13/AC-14 чёрным ящиком через `guard.check_content` — не
дублируются здесь. Этот файл проверяет `parse_division_subsections`
напрямую и граничные случаи, которые приёмочная планка не обязана
перечислять поимённо: секция без заголовка вовсе, секция с пустым
телом, необязательное поле `Рамка:` (не участвует ни в одном AC),
несколько валидных зон в одном подразделе, и что проверка не касается
артефактов иного типа, чем spec.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

SPEC_TEMPLATE = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 1
{zones_line}---

# SPEC: фикстура секции Деление

## Контекст
Фикстура.

## Требования
1. Первое требование.

## Критерии приёмки
AC-1. Первый критерий.
{division}
## Не входит
- Всё остальное.
"""

FIXTURE_ZONE = "orchestrator/foo_zone.py"


def subsection(title: str, *, zones: str, order: str, tz_text: str,
              budget: str | None = None) -> str:
    lines = [f"### {title}", "", f"Зоны: {zones}", f"Порядок: {order}"]
    if budget is not None:
        lines.append(f"Рамка: {budget}")
    lines.append("")
    lines.append(tz_text)
    return "\n".join(lines)


def spec_text(*, zones: str | None = None, subsections: list | None = None,
             division_raw: str | None = None) -> str:
    zones_line = f"zones: {zones}\n" if zones is not None else ""
    if division_raw is not None:
        body = division_raw
    elif subsections:
        body = "\n\n".join(subsections)
    else:
        body = None
    division = f"\n## Деление\n{body}\n\n" if body is not None else ""
    return SPEC_TEMPLATE.format(zones_line=zones_line, division=division)


class ParseDivisionSubsectionsTest(unittest.TestCase):
    """`guard.parse_division_subsections` — разбор секции без валидации
    обязательности (валидацию несёт `division_section_errors`)."""

    def test_no_division_header_returns_empty_list(self):
        """Ловит мутацию: отсутствие заголовка «## Деление» трактуется как
        ошибка/пустой подраздел вместо штатного AC-9 — SPEC без заявки на
        деление обязан парситься в `[]`, не поднимать исключение."""
        text = spec_text()

        self.assertEqual(guard.parse_division_subsections(text), [])

    def test_division_header_with_blank_body_returns_empty_list(self):
        """Ловит мутацию: пустое тело секции (только пробелы/пустые
        строки) молча даёт один «подраздел» без названия вместо []."""
        text = spec_text(division_raw="   \n\n   ")

        self.assertEqual(guard.parse_division_subsections(text), [])

    def test_optional_budget_field_is_parsed_when_present(self):
        """Ловит мутацию: `Рамка:` парсится как обязательное поле (падает
        на подразделе без него) либо не парсится вовсе (всегда `None`) —
        поле должно быть ИМЕННО необязательным: `$15`, когда есть, `None`,
        когда нет."""
        with_budget = subsection(
            "Часть с рамкой", zones=FIXTURE_ZONE,
            order="первая, без зависимостей", tz_text="Текст ТЗ первой.",
            budget="$15")
        without_budget = subsection(
            "Часть без рамки", zones=FIXTURE_ZONE, order="после части 1",
            tz_text="Текст ТЗ второй.")
        text = spec_text(subsections=[with_budget, without_budget])

        parsed = guard.parse_division_subsections(text)

        self.assertEqual(parsed[0]["budget"], "$15")
        self.assertIsNone(parsed[1]["budget"])

    def test_body_raw_keeps_field_lines_together_with_tz_text(self):
        """Требование 2: поля `Зоны:`/`Порядок:` подраздела остаются
        текстом внутри будущего `TZ.md` подзадачи — `body_raw` обязан
        нести их literal, не только вычлененный `tz_text`."""
        sub = subsection("Часть", zones=FIXTURE_ZONE,
                         order="первая, без зависимостей",
                         tz_text="Текст ТЗ подзадачи.")
        text = spec_text(subsections=[
            sub, subsection("Вторая", zones=FIXTURE_ZONE,
                           order="после части 1", tz_text="Текст второй.")])

        parsed = guard.parse_division_subsections(text)

        self.assertIn(f"Зоны: {FIXTURE_ZONE}", parsed[0]["body_raw"])
        self.assertIn("Текст ТЗ подзадачи.", parsed[0]["body_raw"])


class DivisionSectionErrorsTest(unittest.TestCase):
    """`guard.division_section_errors` — обязательность применяется
    независимо от `schema_version` (AC-9: секция необязательна для всех
    версий, версия-гейтинг здесь не нужен)."""

    def test_non_spec_type_is_never_checked(self):
        """Ловит мутацию: проверка `meta.get("type") != "spec"` выпадает
        или инвертируется — секция «## Деление» текстом в PLAN.md (где
        она не имеет смысла) не должна порождать ошибок формата."""
        single = subsection("Одна часть", zones=FIXTURE_ZONE,
                            order="первая, без зависимостей",
                            tz_text="Текст ТЗ.")
        text = spec_text(subsections=[single])

        errors = guard.division_section_errors(
            "PLAN.md", text, {"type": "plan"})

        self.assertEqual(errors, [])

    def test_multiple_valid_zones_in_one_subsection_do_not_error(self):
        """Мутация «сверка смотрит только на первую зону подраздела» не
        поймалась бы одной зоной на подраздел — здесь их две, обе
        валидные (одна через зоны родителя, одна через COMMON_ZONES)."""
        common_zone = config.COMMON_ZONES[0]
        first = subsection(
            "Первая часть", zones=f"{FIXTURE_ZONE}, {common_zone}",
            order="первая, без зависимостей",
            tz_text="Текст ТЗ первой части.")
        second = subsection("Вторая часть", zones=FIXTURE_ZONE,
                           order="после части 1",
                           tz_text="Текст ТЗ второй части.")
        text = spec_text(zones=FIXTURE_ZONE, subsections=[first, second])

        errors = guard.division_section_errors(
            "SPEC.md", text, {"type": "spec", "zones": FIXTURE_ZONE})

        self.assertEqual(errors, [])

    def test_zone_nested_under_a_common_directory_zone_does_not_error(self):
        """Ловит мутацию R1-F1 (REVIEW.md итерация 1): сверка зоны
        подраздела с общими зонами — буквальное членство в множестве, а
        не покрытие с учётом вложенности каталог/файл. `tests/` входит в
        `config.COMMON_ZONES` как каталог — конкретный файл внутри него
        (`tests/test_something_new.py`) обязан считаться покрытым, а не
        отказываться из-за того, что сам путь не встречается в
        `COMMON_ZONES` буквально."""
        nested_zone = "tests/test_something_new.py"
        self.assertIn("tests/", config.COMMON_ZONES)
        first = subsection("Часть с вложенной общей зоной",
                           zones=nested_zone,
                           order="первая, без зависимостей",
                           tz_text="Текст ТЗ первой части.")
        second = subsection("Вторая часть", zones=FIXTURE_ZONE,
                           order="после части 1",
                           tz_text="Текст ТЗ второй части.")
        text = spec_text(zones=FIXTURE_ZONE, subsections=[first, second])

        errors = guard.division_section_errors(
            "SPEC.md", text, {"type": "spec", "zones": FIXTURE_ZONE})

        self.assertEqual(errors, [])

    def test_zone_nested_under_a_parent_directory_zone_does_not_error(self):
        """Ловит мутацию R1-F1 (REVIEW.md итерация 1): та же вложенность,
        но со стороны зоны РОДИТЕЛЯ — родитель называет зоной целый
        каталог (`orchestrator/`), подраздел — конкретный файл внутри него
        (`orchestrator/catalog.py`); плоское членство отказало бы, хотя
        файл целиком лежит внутри зоны родителя."""
        parent_dir_zone = "orchestrator/"
        first = subsection("Часть внутри каталога родителя",
                           zones="orchestrator/catalog.py",
                           order="первая, без зависимостей",
                           tz_text="Текст ТЗ первой части.")
        second = subsection("Вторая часть", zones="orchestrator/fsm.py",
                           order="после части 1",
                           tz_text="Текст ТЗ второй части.")
        text = spec_text(zones=parent_dir_zone, subsections=[first, second])

        errors = guard.division_section_errors(
            "SPEC.md", text, {"type": "spec", "zones": parent_dir_zone})

        self.assertEqual(errors, [])

    def test_zone_wider_than_parent_directory_still_errors(self):
        """Каталожная вложенность не должна стать лазейкой в обратную
        сторону: подраздел, называющий зоной каталог ШИРЕ узкой зоны
        родителя (родитель — конкретный файл, подраздел — весь каталог),
        по-прежнему режет зону родителя поперёк и обязан отказать."""
        single = subsection("Часть шире родителя", zones="orchestrator/",
                            order="первая, без зависимостей",
                            tz_text="Текст ТЗ.")
        text = spec_text(zones="orchestrator/catalog.py",
                         subsections=[single])

        errors = guard.division_section_errors(
            "SPEC.md", text, {"type": "spec", "zones": "orchestrator/catalog.py"})

        self.assertTrue(
            any("orchestrator/" in e for e in errors),
            f"не отказал зоне шире зоны родителя: {errors}")

    def test_header_present_with_prose_but_no_subsections_errors(self):
        """Ловит мутацию R1-F3 (REVIEW.md итерация 1): заголовок «##
        Деление» есть, тело непустое, но ни одного `### <название>` нет —
        функция обязана явно отказать (намерение аналитика на деление не
        должно тихо проходить тем же путём, что и полное отсутствие
        секции)."""
        text = spec_text(division_raw="Текст без единого ### подраздела.")

        errors = guard.division_section_errors(
            "SPEC.md", text, {"type": "spec"})

        self.assertTrue(
            any("подраздела" in e for e in errors),
            f"молча пропустил секцию без подразделов: {errors}")

    def test_check_content_wires_division_errors_for_spec(self):
        """Мутация: вызов `division_section_errors` выпал из
        `_content_errors` — нарушение секции «## Деление» прошло бы
        `check_content` без единой ошибки."""
        single = subsection("Одна часть", zones=FIXTURE_ZONE,
                            order="первая, без зависимостей",
                            tz_text="Текст ТЗ.")
        text = spec_text(zones=FIXTURE_ZONE, subsections=[single])

        errors = guard.check_content("SPEC.md", text)

        self.assertTrue(
            any("Деление" in e for e in errors),
            f"check_content не назвал секцию 'Деление' в ошибках: {errors}")


if __name__ == "__main__":
    unittest.main()
