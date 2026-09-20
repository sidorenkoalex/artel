"""AC-10/AC-11 (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF): полный прогон перед push
запускается ровно для приложений, трогающих `tests/` или `.github/` —
красный прогон отказывает мержу именованной причиной; приложение к
прочим защищённым путям прогона не требует и мержу не мешает.

Красен до реализации: приложения на мерже не применяются и полный прогон не запускается ни для одного приложения — `acceptance.run_full_suite` не звана ни разу, задача с приложением к `tests/` доезжает до `done`, и отказа «приложения ломают тесты» в журнале нет. `test_ac11_*` до реализации красен на проверке коммита приложений (сам факт «прогон не звался» выполняется и без кода — поэтому один этот факт критерием не считается).

`acceptance.run_full_suite` подменена (SPEC называет её дословно в
требовании 5) — настоящий полный набор внутри приёмочного теста гонять
незачем; подмена запоминает и корень прогона, и содержимое защищённых
файлов в нём на момент вызова, так что «прогон видит уже применённое
приложение» проверяется, а не предполагается.

Провалидировано стабом (решение Оператора 03.09): временное применение
приложений с прогоном `acceptance.run_full_suite(scratch)` ровно для
путей под `tests/`/`.github/` и отказом «приложения ломают тесты:
<хвост>» на красном исходе зеленит все три теста файла; стаб удалён,
репозиторий не тронут.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _parse  # noqa: E402
import _sandbox  # noqa: E402

from orchestrator import config  # noqa: E402

# Хвост красного прогона — короткий НАМЕРЕННО: любой принятый в кодовой
# базе срез хвоста (`[:300]`, `[:500]`, `[-2000:]`) сохраняет его целиком,
# и сверка не зависит от того, какой срез выберет реализация.
RED_TAIL = "1 failed (подменённый прогон)"
TESTS_MARKER = "правка Оператора в защищённом тесте"
GITHUB_MARKER = "правка Оператора в workflow"
SKILLS_MARKER = "правка Оператора вне tests и .github"


class RedFullSuiteRefusesTheMergeTest(_sandbox.MergeAppendixSandbox):

    def test_ac10_red_full_suite_refuses_and_publishes_nothing(self):
        """Приложение к защищённому пути под `tests/`: полный прогон
        запущен в дереве, где приложение уже применено, его красный исход
        отказывает мержу именованной причиной «приложения ломают тесты:
        <хвост>», задача остаётся на `merge_gate`, main origin не
        продвинут, приложения не опубликованы, scratch убран.

        Ловит мутацию: исход `run_full_suite` не проверяется (вызвали и
        поехали дальше) — main origin продвинулся бы с приложением,
        ломающим тесты, и проверка sha ниже покраснеет. Вторая мутация:
        прогон запускается ДО `git apply` — снимок текста файла на
        момент вызова не будет содержать маркер приложения.
        """
        self.full_suite_result = (False, RED_TAIL)
        self.commit_plan([_parse.appendix_section(
            [self.applicable_diff_block(_parse.PROTECTED_TESTS_FILE,
                                        TESTS_MARKER)],
            suffix=f": правка {_parse.PROTECTED_TESTS_FILE}")])
        before_main = self.origin_main_sha()

        outcome, exit_text = self.approve_catching_exit()

        self.assertEqual(
            len(self.full_suite_calls), 1,
            f"полный прогон обязан быть запущен ровно один раз для "
            f"приложения к {_parse.PROTECTED_TESTS_FILE}; исход тела "
            f"гейта: {outcome!r}, отказ: {exit_text!r}")
        seen = self.full_suite_calls[0]["texts"][_parse.PROTECTED_TESTS_FILE]
        self.assertIn(
            TESTS_MARKER, seen,
            "полный прогон обязан идти в дереве, где приложение УЖЕ "
            "применено")
        blob = f"{self.journal_blob()}\n{exit_text}"
        self.assertIn(
            _sandbox.BROKEN_TESTS_REFUSAL, blob,
            f"нет именованного отказа «{_sandbox.BROKEN_TESTS_REFUSAL}»:\n"
            f"{blob}")
        self.assertIn(RED_TAIL, blob,
                      f"в отказе нет хвоста прогона:\n{blob}")
        self.assertEqual(self.state(), "merge_gate")
        self.assertEqual(self.origin_main_sha(), before_main,
                         "main origin не имеет права продвинуться")
        self.assertEqual(
            [s for s in self.origin_main_subjects()
             if _sandbox.APPLIED_COMMIT_MARK in s], [],
            "приложения не имеют права публиковаться при красном прогоне")
        self.assertEqual(self.worktree_paths(config.ROOT),
                         [str(config.ROOT)],
                         "scratch-worktree обязан быть дерегистрирован")

    def test_ac10_appendix_to_github_also_triggers_the_full_suite(self):
        """Второй путь требования 5: приложение к защищённому пути под
        `.github/` тоже запускает полный прогон — зелёный исход мержу не
        мешает.

        Ловит мутацию: условие запуска сведено к одному `tests/` (или,
        наоборот, к одному `.github/`) — прогон не состоится вовсе, и
        правка CI уехала бы в main без проверки.
        """
        self.commit_plan([_parse.appendix_section(
            [self.applicable_diff_block(_parse.PROTECTED_GITHUB_FILE,
                                        GITHUB_MARKER)],
            suffix=f": правка {_parse.PROTECTED_GITHUB_FILE}")])

        outcome = self.approve()

        self.assertEqual(
            len(self.full_suite_calls), 1,
            f"полный прогон обязан быть запущен для приложения к "
            f"{_parse.PROTECTED_GITHUB_FILE}; исход: {outcome!r}")
        self.assertEqual(outcome, ("done",))


class AppendixOutsideTestsSkipsTheFullSuiteTest(_sandbox.MergeAppendixSandbox):

    def test_ac11_appendix_outside_tests_and_github_runs_no_full_suite(self):
        """Приложение только к защищённому пути вне `tests/` и `.github/`:
        полный прогон не запускается ни разу, мерж идёт дальше — задача
        `done`, коммит приложений в main origin есть.

        Ловит мутацию: полный прогон запускается для ЛЮБОГО приложения
        (условие требования 5 потеряно) — каждый мерж с приложением к
        `skills/` платил бы полным набором тестов там, где SPEC прямо
        отдаёт проверку CI main; `assertEqual(calls, [])` это поймает.
        """
        self.commit_plan([_parse.appendix_section(
            [self.applicable_diff_block(_parse.PROTECTED_FILE,
                                        SKILLS_MARKER)],
            suffix=f": правка {_parse.PROTECTED_FILE}")])

        outcome = self.approve()

        self.assertEqual(
            self.full_suite_calls, [],
            f"полный прогон запущен для приложения вне tests/ и .github/ "
            f"({_parse.PROTECTED_FILE})")
        self.assertEqual(outcome, ("done",))
        self.assertEqual(self.state(), "done")
        self.assertTrue(
            [s for s in self.origin_main_subjects()
             if _sandbox.APPLIED_COMMIT_MARK in s],
            f"мерж обязан идти дальше и опубликовать приложение: "
            f"{self.origin_main_subjects()}")


if __name__ == "__main__":
    unittest.main()
