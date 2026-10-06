"""Метод AC-6 части 2 перебирает все записи `config.PROTECTED_PATHS` подтестами и зелен при любом исходе генератора `random` (AC-1, AC-2).

Группа: разовый
Красен до реализации: метод выбирает путь пульта `self.rng.choice(config.PROTECTED_PATHS)` и не заводит ни одного подтеста — счёт подтестов 0 вместо 2 × len(PROTECTED_PATHS), а при выборе `targets.yaml` проверка подстрокой находит его в тексте «no_paths проекта vnesh в targets.yaml» и метод красный.

Предмет — смена существующего долгоживущего теста этой задачей
(`tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py::DraftMrHighlightTest::
test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths`), поэтому файл
разовый: после мержа факт «метод переписан» проверять не на чем.

Метод исполняется здесь же, в процессе планки, штатным `unittest`
(`TestSuite.run` с собственным `TestResult`), на исправном коде
`orchestrator/github_adapter.py`. Результат считает каждый `addSubTest`
(и зелёный, и красный). Прогон метода дорог (по черновику MR на подтест),
поэтому он делается один раз на класс и делится между AC-1 и AC-2.

«Любое зерно» разыгрывается враждебным генератором: на время прогона
`random.Random.choice` подменён обёрткой — выбор из самого перечня
`config.PROTECTED_PATHS` отдаёт `targets.yaml` (ровно тот исход, на котором
прежний метод ложно красный), любой другой выбор идёт настоящим методом;
глобальное зерно `random` перед прогоном задаётся случайным и печатается.

Провалидировано временным стабом реализации (удалён, не закоммичен): метод,
перебирающий записи `subTest` в двух сценариях и сверяющий путь пульта с
перечнем путей комментария, — оба теста зелёные.
"""
import random
import unittest
from unittest import mock

from orchestrator import config
from tests import test_01m45fk56dwmnbrka1vwm12h19_draft_mr as draft_mr

METHOD = "test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths"
# Сценарии метода, где путь пульта прежде выбирался случайно (SPEC,
# требование 1): дифф с путями `no_paths` проекта и дифф только с путём пульта.
SCENARIOS = 2
TRAP = "targets.yaml"


class CountingResult(unittest.TestResult):
    """Результат прогона, считающий подтесты: (описание, ошибка или None)."""

    def __init__(self):
        super().__init__()
        self.subtests: list = []

    def addSubTest(self, test, subtest, err):
        self.subtests.append((str(subtest), err))
        super().addSubTest(test, subtest, err)


def run_method(seed: int) -> CountingResult:
    """Один прогон метода AC-6 с враждебным `Random.choice`."""
    real_choice = random.Random.choice

    def hostile_choice(self, seq):
        if tuple(seq) == tuple(config.PROTECTED_PATHS):
            return TRAP
        return real_choice(self, seq)

    random.seed(seed)
    result = CountingResult()
    suite = unittest.TestSuite([draft_mr.DraftMrHighlightTest(METHOD)])
    with mock.patch.object(random.Random, "choice", hostile_choice):
        suite.run(result)
    return result


def describe(result: CountingResult, seed: int) -> str:
    red = [(d, e) for d, e in result.subtests if e is not None]
    return (f"зерно: {seed}; подтестов {len(result.subtests)}, красных "
            f"{len(red)}; провалы: {result.failures}; ошибки: {result.errors}; "
            f"красные подтесты: {red[:3]}")


class HighlightSubtestsTest(unittest.TestCase):

    seed = 0
    result = None

    @classmethod
    def setUpClass(cls):
        cls.seed = random.randrange(1 << 30)
        print(f"зерно: {cls.seed}")
        cls.result = run_method(cls.seed)

    def test_ac1_one_subtest_per_protected_path_in_each_scenario(self):
        """Метод заводит ровно по подтесту на запись `config.PROTECTED_PATHS` в каждом из двух сценариев.

        Сценарий: метод AC-6 исполняется штатным `unittest`; результат
        считает вызовы `addSubTest`. Их число обязано равняться
        `len(config.PROTECTED_PATHS) × 2` (дифф с путями `no_paths` и дифф
        только с путём пульта), перечень читается в момент проверки.

        Ловит мутацию: путь пульта по-прежнему выбирается
        `self.rng.choice(config.PROTECTED_PATHS)` (подтестов 0), либо перебор
        оставлен только в одном из двух сценариев (подтестов вдвое меньше),
        либо перебирается срез перечня — счёт расходится с 2 × len.
        """
        self.assertIn(TRAP, config.PROTECTED_PATHS,
                      f"предпосылка: {TRAP} в config.PROTECTED_PATHS")
        self.assertEqual(len(self.result.subtests),
                         len(config.PROTECTED_PATHS) * SCENARIOS,
                         describe(self.result, self.seed))

    def test_ac2_green_even_when_generator_yields_targets_yaml(self):
        """Метод зелёный на исправном коде, даже когда генератор отдаёт `targets.yaml` из перечня пульта.

        Сценарий: `random.Random.choice` враждебен — любой выбор из
        `config.PROTECTED_PATHS` отдаёт `targets.yaml`, слово которого всегда
        есть в тексте комментария «no_paths проекта vnesh в targets.yaml».
        Метод AC-6 исполняется на исправном `github_adapter`: в результате нет
        ни провалов, ни ошибок, ни красных подтестов, подтесты были.

        Ловит мутацию: отсутствие пути пульта по-прежнему сверяется
        подстрокой всего текста комментариев (`assertNotIn(artel_path,
        text)`) — подтест записи `targets.yaml` красный; путь пульта
        по-прежнему выбирается случайно — враждебный выбор даёт тот же
        `targets.yaml` и тот же провал.
        """
        context = describe(self.result, self.seed)
        self.assertEqual(self.result.failures, [], context)
        self.assertEqual(self.result.errors, [], context)
        self.assertTrue(self.result.subtests, context)
        self.assertEqual([d for d, e in self.result.subtests if e is not None],
                         [], context)
        self.assertEqual(self.result.testsRun, 1, context)


if __name__ == "__main__":
    unittest.main()
