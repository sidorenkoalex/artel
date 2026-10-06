"""Метод AC-6 части 2 красный при каждой из двух мутаций своей строки «Ловит мутацию» (AC-3).

Группа: разовый
Зелёный с рождения: прежний метод тоже ловит обе мутации (пути `no_paths` выпадают из комментария), критерий держит свойство «не слабее прежнего» через смену метода этой задачей.

Предмет — смена существующего долгоживущего теста этой задачей
(`tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py::DraftMrHighlightTest::
test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths`), поэтому файл
разовый.

Мутация вносится на время прогона подменой публичного
`orchestrator.repo_context.protected_paths` — узла, из которого подсветка
черновика MR (`github_adapter.ensure_draft_mr`) берёт перечень проекта
задачи:
(а) перечень — `config.PROTECTED_PATHS` для любого проекта;
(б) перечень — поле `no_paths` записи артели в `targets.yaml` песочницы
метода (`targets.target(config.DEFAULT_TARGET)`), а не проекта задачи.
Метод исполняется штатным `unittest` в процессе планки. «Красный» здесь —
провал утверждения (`failures`, в том числе красный подтест), а не ошибка
обвязки (`errors`): упавшая песочница не засчитывается за пойманную мутацию.
Глобальное зерно `random` перед прогоном случайное и печатается.

Провалидировано временным стабом реализации (удалён, не закоммичен): метод
с перебором записей `subTest` и сверкой по перечню путей комментария красен
под обеими мутациями и зелен без них.
"""
import random
import unittest
from unittest import mock

from orchestrator import config, repo_context, targets
from tests import test_01m45fk56dwmnbrka1vwm12h19_draft_mr as draft_mr

METHOD = "test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths"


def pult_list_for_any_project(ctx):
    """Мутация (а): перечень пульта для любого проекта."""
    return tuple(config.PROTECTED_PATHS)


def artel_entry_list(ctx):
    """Мутация (б): перечень из записи артели, а не проекта задачи."""
    return tuple(targets.target(config.DEFAULT_TARGET)["no_paths"])


class HighlightMutationsTest(unittest.TestCase):

    def run_mutated(self, mutant) -> tuple[unittest.TestResult, str]:
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        random.seed(seed)
        result = unittest.TestResult()
        suite = unittest.TestSuite([draft_mr.DraftMrHighlightTest(METHOD)])
        with mock.patch.object(repo_context, "protected_paths", mutant):
            suite.run(result)
        return result, (f"зерно: {seed}; провалы: {len(result.failures)}; "
                        f"ошибки: {result.errors}")

    def assert_caught(self, mutant) -> None:
        result, context = self.run_mutated(mutant)
        self.assertEqual(result.testsRun, 1, context)
        self.assertEqual(result.errors, [], context)
        self.assertTrue(result.failures, f"мутация не поймана; {context}")

    def test_ac3_red_when_highlight_uses_pult_list_for_any_project(self):
        """Под мутацией «подсветка сверяет дифф с `config.PROTECTED_PATHS` для любого проекта» метод красный.

        Сценарий: `repo_context.protected_paths` на время прогона отдаёт
        `config.PROTECTED_PATHS` и для внешнего проекта `vnesh`; метод AC-6
        исполняется штатным `unittest`. В результате есть провал утверждения
        и нет ошибок обвязки.

        Ловит мутацию: при переписывании метода выпала проверка «путь
        `no_paths` назван в комментарии» и проверка отсутствия пути пульта
        ослаблена (например, сверка только с одной записью) — под мутацией
        (а) метод зелёный, провала нет.
        """
        self.assert_caught(pult_list_for_any_project)

    def test_ac3_red_when_list_comes_from_artel_entry(self):
        """Под мутацией «перечень берётся из записи артели, а не проекта задачи» метод красный.

        Сценарий: `repo_context.protected_paths` на время прогона отдаёт поле
        `no_paths` записи артели из `targets.yaml` песочницы метода; метод AC-6
        исполняется штатным `unittest`. В результате есть провал утверждения
        и нет ошибок обвязки.

        Ловит мутацию: переписанный метод перестал заводить в песочнице
        запись артели с `no_paths` из перечня пульта или перестал требовать
        подсветки путей `no_paths` проекта — под мутацией (б) метод зелёный.
        """
        self.assert_caught(artel_entry_list)


if __name__ == "__main__":
    unittest.main()
