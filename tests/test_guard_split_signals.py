"""Юнит-тесты сигналов «подозрения на большой объём» и проверки секции
«Оценка объёма и деление» (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требования
1, 3; ANSWER-1).

Приёмочные тесты задачи (`tasks/01M1KS8K9RXWHX2PW3ZKB0P903/
acceptance_tests/test_ac1_split_signal_constants.py` и соседние
`test_ac2_*`/`test_ac3_*`/`test_ac5_*`/`test_ac6_*`/`test_ac7_*`) уже
закрывают AC-1..AC-7 чёрным ящиком через `guard.check_content` — они
зафиксированы `tests_writing` и не дублируются здесь. Этот файл
проверяет напрямую `guard.split_signal_names`/`guard.
split_assessment_errors` и граничные случаи, которые приёмочная планка
не обязана перечислять поимённо: сигналы «число затрагиваемых
модулей/файлов», «число критериев приёмки», «бюджет», «прогноз диффа»
по отдельности, и правило «прогноз диффа не дан — сигнал, только если
сработал другой» (ANSWER-1, редактура Оператора 04.09).
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

SPEC_BASE = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 3
budget_usd: {budget}
{extra_meta}---

# SPEC: фикстура сигналов объёма

## Контекст
Фикстура.

## Требования
1. Первое требование.
{zones}
## Критерии приёмки
{ac_items}

## Не входит
- Всё остальное.
{volume_section}"""


def _ac_items(n: int) -> str:
    return "\n".join(f"AC-{i}. критерий {i}." for i in range(1, n + 1))


def spec_text(*, budget=15, ac_count=2, zone_paths=None,
             volume_section: str | None = None,
             extra_meta: str = "") -> str:
    zones = ""
    if zone_paths is not None:
        body = "\n".join(f"- `{p}`" for p in zone_paths)
        zones = f"\n## Зоны\n{body}\n"
    volume = ""
    if volume_section is not None:
        volume = f"\n## Оценка объёма и деление\n{volume_section}\n"
    return SPEC_BASE.format(budget=budget, extra_meta=extra_meta,
                            zones=zones, ac_items=_ac_items(ac_count),
                            volume_section=volume)


def _meta(text: str) -> dict:
    from orchestrator import yamlmini
    return yamlmini.frontmatter(text)


class ZoneFilesSignalTest(unittest.TestCase):
    """«Число затрагиваемых модулей/файлов» — порог `config.
    SPLIT_SIGNAL_ZONE_FILES` по числу путей, упомянутых в тексте SPEC.

    Ловит мутацию: граница сдвинута на единицу (`>` вместо `>=` или
    наоборот) — оба теста вместе фиксируют ровно порог: `threshold - 1`
    не срабатывает, `threshold` уже срабатывает."""

    def test_below_threshold_does_not_fire(self):
        paths = [f"orchestrator/m{i}.py"
                for i in range(config.SPLIT_SIGNAL_ZONE_FILES - 1)]
        text = spec_text(zone_paths=paths)

        names = guard.split_signal_names(text, _meta(text))

        self.assertNotIn("число затрагиваемых модулей/файлов", names)

    def test_at_threshold_fires(self):
        paths = [f"orchestrator/m{i}.py"
                for i in range(config.SPLIT_SIGNAL_ZONE_FILES)]
        text = spec_text(zone_paths=paths)

        names = guard.split_signal_names(text, _meta(text))

        self.assertIn("число затрагиваемых модулей/файлов", names)


class AcCountSignalTest(unittest.TestCase):
    """«Число критериев приёмки» — порог `config.SPLIT_SIGNAL_AC_COUNT`.

    Ловит мутацию: граница сдвинута на единицу — `threshold - 1` не
    срабатывает, `threshold` уже срабатывает, оба теста вместе фиксируют
    ровно порог `>=`, не `>`."""

    def test_below_threshold_does_not_fire(self):
        text = spec_text(ac_count=config.SPLIT_SIGNAL_AC_COUNT - 1)

        names = guard.split_signal_names(text, _meta(text))

        self.assertNotIn("число критериев приёмки", names)

    def test_at_threshold_fires(self):
        text = spec_text(ac_count=config.SPLIT_SIGNAL_AC_COUNT)

        names = guard.split_signal_names(text, _meta(text))

        self.assertIn("число критериев приёмки", names)


class BudgetSignalTest(unittest.TestCase):
    """«Бюджет» — порог `config.SPLIT_SIGNAL_BUDGET_USD`, `budget_usd`
    frontmatter.

    Ловит мутацию: граница сдвинута на единицу — `threshold - 1` не
    срабатывает, `threshold` уже срабатывает, оба теста вместе фиксируют
    ровно порог `>=`, не `>`."""

    def test_below_threshold_does_not_fire(self):
        text = spec_text(budget=config.SPLIT_SIGNAL_BUDGET_USD - 1)

        names = guard.split_signal_names(text, _meta(text))

        self.assertNotIn("бюджет", names)

    def test_at_threshold_fires(self):
        text = spec_text(budget=config.SPLIT_SIGNAL_BUDGET_USD)

        names = guard.split_signal_names(text, _meta(text))

        self.assertIn("бюджет", names)


class DiffForecastSignalTest(unittest.TestCase):
    """«Прогноз диффа» — `diff_forecast_kib` (frontmatter либо строка
    секции) выше половины `REVIEW_SNAPSHOT_DIFF_MAX_BYTES` (ANSWER-1)."""

    def _threshold_kib(self) -> float:
        return ((config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES / 1024)
               * config.SPLIT_SIGNAL_DIFF_FORECAST_RATIO)

    def test_frontmatter_field_below_threshold_does_not_fire(self):
        """Ловит мутацию: граница `> threshold` подменена на `>=
        threshold` (или сравнение вовсе выпало) — значение ровно под
        порогом ложно срабатывало бы."""
        text = spec_text(extra_meta=f"diff_forecast_kib: "
                                    f"{int(self._threshold_kib() - 1)}\n")

        names = guard.split_signal_names(text, _meta(text))

        self.assertNotIn("прогноз диффа", names)

    def test_frontmatter_field_above_threshold_fires(self):
        """Ловит мутацию: чтение `diff_forecast_kib` из frontmatter
        выпало (например читается только строка секции) — значение выше
        порога перестало бы срабатывать."""
        text = spec_text(extra_meta=f"diff_forecast_kib: "
                                    f"{int(self._threshold_kib() + 1)}\n")

        names = guard.split_signal_names(text, _meta(text))

        self.assertIn("прогноз диффа", names)

    def test_section_line_above_threshold_fires_without_frontmatter_field(self):
        """Ловит мутацию: запасное чтение строки «Прогноз диффа: N КиБ»
        секции (`DIFF_FORECAST_LINE`) выпало — без frontmatter-поля
        сигнал перестал бы срабатывать вовсе."""
        kib = int(self._threshold_kib() + 1)
        text = spec_text(volume_section=f"Прогноз диффа: {kib} КиБ.")

        names = guard.split_signal_names(text, _meta(text))

        self.assertIn("прогноз диффа", names)

    def test_missing_forecast_alone_is_not_a_signal(self):
        """«Чистый» SPEC без единого сигнала и без прогноза — прогноз не
        считается сигналом сам по себе (AC-6): вписывать его просто по
        факту отсутствия поля не нужно, если больше ничего не сработало.

        Ловит мутацию: условие «сигнал, только если сработал другой»
        (`elif forecast is None and names`) заменено на безусловное — уже
        сам факт отсутствия прогноза красил бы «чистый» SPEC."""
        text = spec_text()

        names = guard.split_signal_names(text, _meta(text))

        self.assertEqual(names, [])

    def test_missing_forecast_is_a_signal_when_another_signal_fired(self):
        """Отсутствие прогноза становится сигналом, ТОЛЬКО когда уже
        сработал другой (ANSWER-1, редактура Оператора 04.09).

        Ловит мутацию: ветка «прогноз не дан» удалена целиком — сигнал
        «прогноз диффа не дан» никогда бы не появлялся в списке, даже
        когда бюджет уже сработал."""
        text = spec_text(budget=config.SPLIT_SIGNAL_BUDGET_USD)

        names = guard.split_signal_names(text, _meta(text))

        self.assertIn("бюджет", names)
        self.assertIn("прогноз диффа не дан", names)


class InvariantMechanismSignalUnitTest(unittest.TestCase):
    """`_zone_paths`/пересечение с `docs/invariants.md` напрямую — без
    оценки смысла, только буквальная подстрока (ANSWER-1)."""

    def test_no_zones_section_never_fires(self):
        """Ловит мутацию: сигнал срабатывает безусловно (например
        `if zone_paths:` заменено на константу `True`) — SPEC без единого
        пути формата `orchestrator/<имя>.py`/`scripts/<имя>.py` не должен
        красить сигнал сравнением с пустым множеством путей."""
        text = spec_text(zone_paths=None)

        names = guard.split_signal_names(text, _meta(text))

        self.assertNotIn("затронут инвариантный механизм", names)

    def test_zone_path_present_in_invariants_doc_fires(self):
        """Ловит мутацию: сравнение подстроки с `docs/invariants.md`
        выпало или инвертировано (`not in` вместо `in`) — путь, реально
        встречающийся в документе, перестал бы зажигать сигнал."""
        text = spec_text(zone_paths=["scripts/fixture_only_module.py"])
        fake_invariants = "`scripts/fixture_only_module.py` несёт механику\n"

        with mock.patch.object(
                guard, "_invariants_doc_text", return_value=fake_invariants):
            names = guard.split_signal_names(text, _meta(text))

        self.assertIn("затронут инвариантный механизм", names)


class RequiresSplitAssessmentTest(unittest.TestCase):
    """Версия-гейтинг (тот же приём, что `requires_ac_markup`/`requires_
    registry`): SPEC ниже версии 3 не подпадает под новую проверку —
    старый беклог (`schema_version: 1`, высокий `budget_usd`, ни одной
    секции «Оценка объёма и деление») не должен внезапно упереться в
    guard задним числом (регресс, пойманный `tests/test_spec_budget.py`
    при первой реализации без версии-гейтинга — SPEC фикстуры теста несёт
    `schema_version: 1` и `budget_usd` выше нового порога)."""

    def test_version_3_requires_the_check(self):
        """Ловит мутацию: граница `>= 3` сдвинута вверх (например `> 3`)
        — версия 3, текущий дефолт `templates/SPEC.md`, перестала бы
        требовать проверку."""
        self.assertTrue(guard.requires_split_assessment({"schema_version": 3}))

    def test_version_below_3_does_not_require_the_check(self):
        """Ловит мутацию: версия-гейтинг выпал целиком (функция всегда
        возвращает `True`) — старый беклог версии 1 упёрся бы в новую
        проверку задним числом, регресс, уже пойманный `test_spec_budget.py`
        при первой реализации."""
        self.assertFalse(guard.requires_split_assessment({"schema_version": 1}))

    def test_missing_field_does_not_require_the_check(self):
        """Ловит мутацию: отсутствие поля дефолтится не в версию 1, а в
        версию >= 3 (например `meta.get("schema_version", 3)`) — SPEC без
        поля `schema_version` вовсе ошибочно попал бы под новую проверку."""
        self.assertFalse(guard.requires_split_assessment({}))

    def test_old_spec_with_high_budget_and_no_section_is_not_rejected(self):
        """Ловит мутацию: версия-гейтинг не проведён до конца в
        `split_assessment_errors`/`check_content` (проверяется
        `requires_split_assessment`, но результат не используется) —
        сквозной путь через `check_content`, не только сам предикат."""
        text = spec_text(budget=500, volume_section=None,
                         extra_meta="").replace("schema_version: 3",
                                                "schema_version: 1")

        self.assertEqual(guard.check_content("SPEC.md", text), [])


class SplitAssessmentErrorsTest(unittest.TestCase):
    """`split_assessment_errors` — только для `type: spec` версии ≥ 3,
    вызывается из `check_content` (проверка проводки, не самих сигналов)."""

    def test_non_spec_artifact_is_never_checked(self):
        """Ловит мутацию: проверка `type` выпала (например
        `meta.get("type")` не сравнивается с `"spec"`) — PLAN/REVIEW с тем
        же набором сигналов ошибочно попали бы под отказ."""
        errors = guard.split_assessment_errors(
            "label", "любой текст", {"type": "plan", "schema_version": 3})

        self.assertEqual(errors, [])

    def test_check_content_wires_the_new_check_for_spec(self):
        """Ловит мутацию: вызов `split_assessment_errors` выпал из
        `check_content` (проводка не собрана) — SPEC с сработавшим
        сигналом и пустой секцией проходил бы `check_content` молча."""
        text = spec_text(budget=config.SPLIT_SIGNAL_BUDGET_USD,
                         volume_section=None)

        errors = guard.check_content("SPEC.md", text)

        self.assertTrue(
            any("Оценка объёма и деление" in e for e in errors), errors)

    def test_check_content_does_not_reject_a_clean_spec(self):
        """Ловит мутацию: сигнал срабатывает без причины (ложное
        `if True` вместо реальной проверки условий) — обычный SPEC без
        единого сигнала ошибочно красился бы отказом."""
        text = spec_text()

        self.assertEqual(guard.check_content("SPEC.md", text), [])


class ClosedTaskExceptionTest(unittest.TestCase):
    """SPEC задачи, у которой уже есть `docs/retro/<id>.md` (задача
    закрыта ДО появления этой проверки), не подпадает под `split_
    assessment_errors` (ANSWER-3, вариант b): новые правила guard
    действуют на живые задачи, история не переписывается —
    `docs/retention.md` объявляет SPEC смерженных задач вечными."""

    def test_closed_task_with_fired_signal_is_not_rejected(self):
        """Ловит мутацию: исключение `_closed_before_split_assessment` не
        подключено в `split_assessment_errors` (проверка написана, но не
        вызывается) — закрытая задача из ANSWER-3 продолжала бы краситься
        отказом."""
        text = spec_text(budget=config.SPLIT_SIGNAL_BUDGET_USD,
                         volume_section=None)
        with tempfile.TemporaryDirectory() as tmp:
            retro_dir = Path(tmp)
            (retro_dir / "T900.md").write_text("RETRO\n", encoding="utf-8")
            with mock.patch.object(guard, "RETRO_DIR", retro_dir):
                errors = guard.check_content("tasks/T900/SPEC.md", text)

        self.assertEqual(errors, [])

    def test_live_task_with_fired_signal_is_still_rejected(self):
        """Тот же SPEC, но без `docs/retro/T900.md` — задача живая,
        проверка действует как обычно (исключение не превращается в
        общее ослабление).

        Ловит мутацию: `_closed_before_split_assessment` возвращает
        `True` безусловно (например по одному наличию сегмента
        `tasks/<id>/` в пути, без проверки файла retro) — живые задачи
        освободились бы от проверки так же, как закрытые."""
        text = spec_text(budget=config.SPLIT_SIGNAL_BUDGET_USD,
                         volume_section=None)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(guard, "RETRO_DIR", Path(tmp)):
                errors = guard.check_content("tasks/T900/SPEC.md", text)

        self.assertTrue(
            any("Оценка объёма и деление" in e for e in errors), errors)

    def test_label_without_task_segment_is_never_closed(self):
        """Ловит мутацию: регэксп `TASK_ID_FROM_PATH` не находит
        совпадение и код по ошибке трактует «нет совпадения» как «задача
        закрыта» (например `return True` в ветке `if not match`) — метка
        вроде голого `SPEC.md`, не несущая пути `tasks/<id>/`, ошибочно
        считалась бы закрытой задачей."""
        self.assertFalse(guard._closed_before_split_assessment("SPEC.md"))


if __name__ == "__main__":
    unittest.main()
