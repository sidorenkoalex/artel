"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-2 (с включённым
режимом артефактной ветки и `status: draft` артефакта типа spec/plan/
review/test_report нарушения содержания не считаются ошибками — только
предупреждение).

Красен до реализации: `guard.py` сегодня не умеет флаг
`--artifact-branch` вовсе (`main()` трактует любой аргумент, кроме
буквально `--all`, как путь к файлу) — прогон `--all --artifact-branch`
сегодня возвращает ДВЕ ошибки «файл не найден» (для `--all` и для
`--artifact-branch`, оба приняты за пути) и код 1 независимо от
содержимого фикстур; тесты ниже ожидают код 0 и сводку «черновиков 1» —
это красная строка ПО ПРИЧИНЕ отсутствия режима, не по опечатке в
фикстуре (проверено `python3 scripts/guard.py --all --artifact-branch`
в пустом дереве: `--all: файл не найден`, `--artifact-branch: файл не
найден`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FILE_NAME_BY_TYPE, generic_broken_text, parse_summary,  # noqa: E402
                      run_main, spec_zones_text)


class DraftArtifactDoesNotFailTheRunTest(unittest.TestCase):
    """Черновик (status: draft) с разбитым содержимым (ни одной секции) —
    с флагом `--artifact-branch` прогон не падает, а нарушение всё равно
    попадает в сводку как посчитанное (не тихо проглочено)."""

    def test_ac2_draft_of_each_type_is_a_warning_not_an_error(self):
        """Для каждого из четырёх типов requirement 2 (`spec`, `plan`,
        `review`, `test_report`) черновик без единой секции: с флагом —
        exit-код 0, файл учтён как черновик, а не как сданный, и
        нарушение всё же вошло в счётчик K.

        Ловит мутацию: разработчик реализует понижение нарушений до
        предупреждения только для ОДНОГО типа (например только `spec`,
        по образцу уже существующей zone-проверки) вместо всех четырёх,
        перечисленных требованием 2, — subTest на `plan`/`review`/
        `test_report` покраснеет отказом (exit 1) там, где остальные уже
        зелёные.
        """
        for atype, name in FILE_NAME_BY_TYPE.items():
            with self.subTest(тип=atype):
                text = generic_broken_text(atype, "draft")

                code, out = run_main({f"tasks/T1/{name}": text},
                                     artifact_branch=True)

                self.assertEqual(code, 0, out)
                summary = parse_summary(out)
                self.assertIsNotNone(summary, out)
                sdano, chernovikov, narusheniy = summary
                self.assertEqual(sdano, 0, out)
                self.assertEqual(chernovikov, 1, out)
                self.assertGreaterEqual(narusheniy, 1, out)


class DraftFrontmatterViolationStillFailsTheRunTest(unittest.TestCase):
    """Требование 2, вторая часть: «нарушения frontmatter ... остаются
    ошибками» — даже для черновика с включённым режимом."""

    def test_ac2_too_new_schema_version_on_a_draft_still_fails(self):
        """Черновик SPEC с `schema_version`, которую этот guard не
        поддерживает, — с флагом `--artifact-branch` всё равно exit-код 1
        и сообщение по-прежнему называет версию.

        Ловит мутацию: разработчик реализует понижение ЛЮБОГО нарушения
        черновика до предупреждения без разбора на «frontmatter» и
        «содержание» (например просто `if status == "draft": errors = []`
        без исключения `schema_errors`) — тогда этот сценарий тоже дал бы
        exit 0, хотя требование 2 явно исключает frontmatter-нарушения
        из понижения.
        """
        text = spec_zones_text(status="draft").replace(
            "schema_version: 4", "schema_version: 999")

        code, out = run_main({"tasks/T1/SPEC.md": text}, artifact_branch=True)

        self.assertEqual(code, 1, out)
        self.assertIn("999", out)


if __name__ == "__main__":
    unittest.main()
