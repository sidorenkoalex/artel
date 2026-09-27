"""AC-2: тесты, чей предмет — сама боевая карта, названы в PLAN.md
ОТДЕЛЬНЫМ списком и остаются на боевом файле.

«Отдельным списком» разбирается структурно: у пункта перечня есть
заголовок раздела, под которым он стоит (`##`-заголовок или строка-ярлык
`**...**`), и ни один раздел не смешивает вердикты «предмет карты: да» и
«предмет карты: нет».

«Остаются на боевом файле» проверяется поведением, а не глазом: SPEC
(требование 4) определяет такой тест как тот, чей исход зависит от
СОГЛАСОВАННОСТИ карты и который ДОЛЖЕН краснеть от несогласованной
правки. Планка строит карту с тремя несогласованностями сразу (ярус вне
перечня `models.TIERS`, скил, которого нет, провайдер, которого нет в
реестре `orchestrator/providers`) и требует, чтобы хотя бы один тест из
отдельного списка на ней покраснел. Три сразу — потому что разные тесты
карты сверяют её с разными реестрами.

`tests/test_analyst_role.py` в этом списке стоять не может: AC-5 требует,
чтобы он ПРОХОДИЛ на карте с чужим значением `provider:`, то есть его
исход от карты зависеть перестаёт.

Красен до реализации: PLAN.md задачи ещё не создан — отдельного списка
неоткуда взять.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class MapSubjectListTest(unittest.TestCase):
    """Структура перечня PLAN.md: отдельный список тестов карты."""

    def plan_entries(self) -> dict:
        plan = _util.plan_text()
        self.assertIsNotNone(
            plan,
            f"PLAN.md задачи не найден в артефактной ветке "
            f"{_util.artifact_branch.branch_name(_util.TASK_ID)} — отдельный "
            f"список тестов боевой карты пишет роль developer")
        return _util.plan_entries(plan)

    def test_ac2_subject_tests_live_in_a_section_of_their_own(self):
        """В перечне PLAN.md есть непустой набор пунктов с вердиктом
        «предмет карты: да», и ни один раздел перечня не смешивает их с
        пунктами «предмет карты: нет»; `tests/test_analyst_role.py` среди
        них не значится.

        Ловит мутацию: тесты карты перечислены вперемешку с остальными,
        одним общим списком, и отличаются только вердиктом в строке —
        читателю перечня (и Оператору на гейте) больше не видно, какие
        файлы СОЗНАТЕЛЬНО оставлены зависящими от боевого файла, а какие
        просто забыли перевести на фикстуру.
        """
        entries = self.plan_entries()
        subject = {rel: e for rel, e in entries.items()
                   if e.get("subject") is True}
        plain = {rel: e for rel, e in entries.items()
                 if e.get("subject") is False}

        self.assertTrue(
            subject,
            f"в перечне PLAN.md нет ни одного пункта «предмет карты: да» — "
            f"тесты, сверяющие боевую карту с каталогом моделей, с "
            f"референсом и со скилами, обязаны быть названы отдельно"
            f"\nформа пункта: {_util.PLAN_ENTRY_SHAPE}")

        shared = ({e["section"] for e in subject.values()}
                  & {e["section"] for e in plain.values()})
        self.assertEqual(
            shared, set(),
            f"разделы перечня {sorted(shared)} несут и тесты боевой карты, и "
            f"тесты, чей предмет не карта, — AC-2 требует ОТДЕЛЬНОГО списка")

        self.assertNotIn(
            _util.ANALYST_TEST, subject,
            f"{_util.ANALYST_TEST} назван тестом боевой карты, но AC-5 "
            f"требует, чтобы он ПРОХОДИЛ на карте с чужим `provider:` у "
            f"роли {_util.ANALYST} — его исход от карты зависеть не должен")


class MapSubjectTestsStillReadTheRealFileTest(unittest.TestCase):
    """Поведение тестов отдельного списка на несогласованной карте."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_ac2_a_subject_test_goes_red_on_an_inconsistent_map(self):
        """Тесты отдельного списка прогоняются на карте с тремя
        несогласованностями сразу, и хотя бы один из них краснеет.

        Ловит мутацию: разработчик перевёл на фикстуру песочницы ВСЕ
        файлы подряд, включая сверку боевой карты с каталогом моделей, а в
        PLAN.md оставил их в списке «предмет карты: да» — несогласованная
        правка `roles.yaml` (ровно тот случай, ради которого сверка и
        заведена) перестаёт кого-либо красить, и ошибка Оператора в
        защищённом файле доезжает до главной ветки молча.
        """
        entries = self.plan_entries_or_fail()
        subject = sorted(rel for rel, e in entries.items()
                         if e.get("subject") is True
                         and (_util.REPO_ROOT / rel).is_file())
        self.assertTrue(
            subject,
            "в перечне PLAN.md нет ни одного существующего файла `tests/` с "
            "вердиктом «предмет карты: да» — проверять зависимость от "
            "согласованности карты не на чем")

        text = _util.inconsistent_roles_text(_util.real_roles_text())
        code = _util.repo_copy(self.tdir, text, name="inconsistent")
        try:
            results = _util.run_pytest_many([(code, subject)], timeout=110)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover
            self.fail(f"прогон тестов боевой карты не уложился в отведённое "
                      f"время: {exc}")

        self.assertTrue(
            _util.many_failures(results),
            f"ни один тест отдельного списка не покраснел на карте, где у "
            f"agent-ролей стоят ярус вне перечня {', '.join(_util.models.TIERS)}"
            f", несуществующий скил и несуществующий провайдер — значит, "
            f"исход этих тестов от согласованности боевой карты больше не "
            f"зависит\n{_util.many_report(results)}")

    def plan_entries_or_fail(self) -> dict:
        plan = _util.plan_text()
        self.assertIsNotNone(
            plan,
            f"PLAN.md задачи не найден в артефактной ветке "
            f"{_util.artifact_branch.branch_name(_util.TASK_ID)} — отдельный "
            f"список тестов боевой карты пишет роль developer")
        return _util.plan_entries(plan)


if __name__ == "__main__":
    unittest.main()
