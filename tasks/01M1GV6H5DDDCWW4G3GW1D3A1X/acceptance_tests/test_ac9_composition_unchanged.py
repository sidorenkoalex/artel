"""AC-9 (tasks/01M1GV6H5DDDCWW4G3GW1D3A1X/SPEC.md): состав компонентов,
включаемых в бриф каждой роли и в ревью-пакет, не меняется этой задачей
— меняется только наличие граничных маркеров вокруг недоверенного
содержимого.

Зелёный с рождения по числу журналируемых компонентов: то же число
компонентов, что `tests/test_brief.py::DeveloperBriefTest.
test_assembles_three_components_and_journals_their_hashes`/
`AnalystMapComponentTest.test_adds_only_the_map_and_journals_one_hash`
уже проверяют сегодня, ДО этой задачи — обвязка маркерами не должна
превратиться в «ещё один компонент» (например если маркер по ошибке
журналируется как отдельная запись) и не должна потерять существующий.
Тело компонентов (сами тексты SPEC/карты/конвенций) обязано остаться
читаемым в выдаче целиком — маркеры дописываются СНАРУЖИ содержимого,
не заменяют и не обрезают его.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BriefSandbox, CONVENTIONS_SMALL, FakeGitDiff,  # noqa: E402
                      MAP_FRESH, PLAN_MD, SPEC_MD, SPEC_SMALL, TASK,
                      build_review_package, standard_files)


class Ac9DeveloperBriefCompositionTest(BriefSandbox):

    def test_ac9_developer_brief_still_journals_exactly_three_components(self):
        """Ловит мутацию: обвязка маркерами журналирует себя как
        отдельный «компонент» (например маркер сам получает запись
        `бриф: компонент`) — число записей журнала стало бы 4 вместо 3
        без изменения фактического состава брифа."""
        text = self.build_developer_brief()

        for marker in (SPEC_SMALL.strip(), MAP_FRESH.strip(),
                      CONVENTIONS_SMALL.strip()):
            self.assertIn(marker, text,
                         f"состав брифа не должен потерять компонент: "
                         f"{marker!r} (тело обязано остаться читаемым, "
                         f"не только под маркерами)")

        details = self.journal_details("developer")
        self.assertEqual(
            len(details), 3,
            "обвязка маркерами не должна менять число журналируемых "
            "компонентов брифа разработчика (SPEC, карта, конвенции)")


class Ac9AnalystBriefCompositionTest(BriefSandbox):

    def test_ac9_analyst_brief_still_journals_exactly_one_component(self):
        """Ловит мутацию: обвязка добавляет карте лишний журналируемый
        «компонент» (например открывающий и закрывающий маркер
        журналируются раздельно) — число записей стало бы 2 вместо 1."""
        text = self.build_analyst_brief()

        self.assertIn(MAP_FRESH.strip(), text)
        self.assertNotIn(SPEC_SMALL.strip(), text, "SPEC — не вход analyst")

        details = self.journal_details("analyst")
        self.assertEqual(len(details), 1)


class Ac9ReviewPackageCompositionTest(unittest.TestCase):

    def test_ac9_review_package_still_carries_spec_plan_stat_and_diff(self):
        """Ловит мутацию: обвязка маркерами случайно роняет один из
        существующих разделов пакета (например форму вердикта или
        стат-список) — состав секций должен остаться тем же, что и до
        этой задачи, только с добавленными маркерами вокруг тела."""
        git = FakeGitDiff(files=standard_files())

        package = build_review_package(git)
        text = package["text"]

        self.assertIn("### Задача", text)
        self.assertIn(f"tasks/{TASK}/SPEC.md", text)
        self.assertIn(f"tasks/{TASK}/PLAN.md", text)
        self.assertIn("templates/REVIEW.md", text)
        self.assertIn("### Изменённые файлы", text)
        self.assertIn("### Diff", text)
        self.assertIn(SPEC_MD.format(task=TASK).strip().splitlines()[-1], text)
        self.assertIn(PLAN_MD.format(task=TASK).strip().splitlines()[-1], text)


if __name__ == "__main__":
    unittest.main()
