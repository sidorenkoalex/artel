"""Мутация «фоновый `suite-run` обрывает прогон не по пределу профиля N» —
целевой тест краснеет, в том числе когда отчёт по-прежнему называет N.

Группа: разовый
Красен до реализации: сегодня обрыв идёт по реальным часам, и строка отчёта берёт N из профиля (suite_run.py:593) — обрыв `proc.wait` по пределу N + k или N − k (и по 60 с config, если отчёт успевает к --wait 1) даёт тот же отчёт с N, целевой тест зелёный, мутация выживает.

Каждая мутация вносится во временную копию рабочей копии кода
(`_mutant.py`), и в ней вложенным pytest прогоняется целевой тест
`SuiteRunProfileLimitTest::test_ac5_…`. Мутация считается пойманной, если
он красен; при этом немутированный целевой тест в такой же копии обязан
быть зелёным — иначе краснота мутанта ничего не доказывает.
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mutant  # noqa: E402

WAIT = "code = proc.wait(timeout=limit[0])"
OTHER_LIMITS = {
    "больше N": ["limit[0] + 1", "limit[0] + 2", "limit[0] + 5",
                 "limit[0] * 2"],
    "меньше N": ["limit[0] - 1", "limit[0] - 2", "limit[0] / 2",
                 "limit[0] * 0.75"],
}


class WaitLimitMutationTest(unittest.TestCase):

    def assert_caught(self, what: str, *edits: tuple) -> None:
        baseline = _mutant.instrumented_run()
        self.assertTrue(baseline.green, baseline.context(
            "немутированный целевой тест не зелёный"))
        run = _mutant.mutated_run(*edits)
        self.assertFalse(run.green, run.context(
            f"мутация «{what}» выжила — целевой тест зелёный"))

    def test_ac6_config_limit_in_wait_turns_target_red(self):
        """Предел config в `proc.wait` вместо `limit[0]` — целевой тест красен.

        Сценарий: в `_run_full_suite_to_log` копии
        `proc.wait(timeout=limit[0])` заменён на
        `proc.wait(timeout=config.FULL_SUITE_TIMEOUT_SEC)`; строка отчёта
        по-прежнему называет N из профиля. Целевой тест в такой копии красен.

        Ловит мутацию: подмена часов в тесте не сверяет предел, переданный в
        `proc.wait`, с N (подменённые часы «прыгают» за любой таймаут) — обрыв
        по 60 с config выглядит как обрыв по N, целевой тест зелёный, метод
        красен.
        """
        self.assert_caught(
            "proc.wait берёт config.FULL_SUITE_TIMEOUT_SEC",
            (_mutant.ACCEPTANCE_REL, WAIT,
             "code = proc.wait(timeout=config.FULL_SUITE_TIMEOUT_SEC)"))

    def test_ac6_any_other_limit_in_wait_turns_target_red(self):
        """Предел `proc.wait`, больший и меньший N, — целевой тест красен.

        Сценарий: для каждой стороны («больше N», «меньше N») случайно (зерно
        печатается) выбирается выражение предела — `limit[0] ± k`,
        `limit[0] * 2`, `limit[0] / 2` и т.п. — и подставляется в
        `proc.wait(timeout=…)` копии; отчёт по-прежнему называет N. Целевой
        тест в каждой такой копии красен.

        Ловит мутацию: подмена времени чувствительна только к пределу больше
        N (например, «прыгающие» часы обрывают на любом пределе ≤ скачка) —
        обрыв по `limit[0] - 1` даёт тот же отчёт с N, целевой тест зелёный,
        подтест «меньше N» красен.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for side, choices in OTHER_LIMITS.items():
            expr = rng.choice(choices)
            with self.subTest(side=side, expr=expr, seed=seed):
                self.assert_caught(
                    f"proc.wait(timeout={expr}) ({side}; зерно {seed})",
                    (_mutant.ACCEPTANCE_REL, WAIT,
                     f"code = proc.wait(timeout={expr})"))

    def test_ac6_suite_run_taking_config_limit_turns_target_red(self):
        """Фоновый `suite-run` берёт предел config, а не профиля, — тест красен.

        Сценарий: в `_run` копии `orchestrator/suite_run.py` предел профиля
        `project_profile.full_suite_limit(target)` заменён на
        `(config.FULL_SUITE_TIMEOUT_SEC, "config")` — и обрыв, и строка
        отчёта идут от значения config копии. Целевой тест красен.

        Ловит мутацию: из целевого метода убрано или ослаблено утверждение
        об отсутствии значения config в строке «не уложился» вместе с
        N-чувствительностью подмены — обрыв по config с отчётом о config
        проходит, целевой тест зелёный, метод красен.
        """
        self.assert_caught(
            "suite-run берёт config.FULL_SUITE_TIMEOUT_SEC",
            (_mutant.SUITE_RUN_REL,
             "limit = project_profile.full_suite_limit(target)",
             "limit = (config.FULL_SUITE_TIMEOUT_SEC, \"config\")"))


if __name__ == "__main__":
    unittest.main()
