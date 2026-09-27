"""AC-6 (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): тестовый метод, у
которого первый исполняемый оператор тела — `if <условие>:` с
единственным `return` без значения в теле ветки, даёт находку с именем
файла и квалифицированным именем метода; тот же ранний `return`, уже
стоявший на том же имени в базе сравнения, находки не даёт.

Красен до реализации: ранний `return` под условием узел сегодня не
распознаёт вовсе (`_file_findings` знает только удаление файла,
исчезнувший метод и маркеры пропуска `guard.test_skip_markers`) — ветка
с таким методом проходит рубеж молча, и первый сценарий падает на
`outcome.refused is False`.

Второй сценарий (`test_ac6_early_return_already_in_base_gives_no_
finding`) зелен с рождения и обязан таким остаться: сегодня находки нет,
потому что распознавания нет вовсе, после реализации её нет уже осознанно
— по правилу появления требования 6. Он краснеет ровно на мутации «ранний
`return` ищется только в head, без сверки с тем же именем в базе»: тогда
любая правка файла, где ранний выход стоял годами, начинает отказывать
переходу на ровном месте.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (EARLY_RETURN, EARLY_RETURN_BASE_CLASS,  # noqa: E402
                      EARLY_RETURN_BASE_PATH, EARLY_RETURN_CLASS,
                      EARLY_RETURN_IN_BASE_PLUS_NEW_METHOD,
                      EARLY_RETURN_METHOD, EARLY_RETURN_PATH,
                      REFUSAL_ACTION, GateSandbox)


class EarlyReturnUnderConditionTest(GateSandbox):

    def test_ac6_early_return_under_condition_is_a_finding(self):
        """Новый метод начинается с `if not HAS_ZSH: return` — ровно тем
        обходом, которым 27.09 заплатили за перекос рубежа: узел обязан
        дать находку, а её текст — назвать файл и квалифицированное имя
        метода (класс и метод).

        Ловит мутацию: распознавание раннего выхода не добавлено вовсе
        либо привязано к тексту (поиск строки `return` регуляркой) и
        потому не срабатывает на отступе внутри `if` — обход рубежа,
        который SPEC называет известным и открытым, остаётся открытым, и
        послабление требования 2 становится чистым ослаблением: честному
        пропуску с причиной по-прежнему есть бесплатная альтернатива, не
        видимая ревьюверу.
        """
        self.apply(EARLY_RETURN_PATH, EARLY_RETURN)

        outcome = self.run_gate()

        self.assertTrue(
            outcome.refused,
            f"ранний return под условием — находка (AC-6); журнал: "
            f"{outcome.journal}; stdout: {outcome.printed}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn(EARLY_RETURN_PATH, outcome.detail,
                      f"текст находки обязан назвать файл (AC-6); "
                      f"detail: {outcome.detail}")
        self.assertIn(EARLY_RETURN_CLASS, outcome.detail,
                      f"текст находки обязан назвать имя метода "
                      f"КВАЛИФИЦИРОВАННО — вместе с классом (AC-6); "
                      f"detail: {outcome.detail}")
        self.assertIn(EARLY_RETURN_METHOD, outcome.detail,
                      f"detail: {outcome.detail}")

    def test_ac6_early_return_already_in_base_gives_no_finding(self):
        """Файл `tests/test_early_return_base.py` попал в дифф (на ветке
        к нему добавлен обычный метод), но ранний `return` на
        `test_early_return_from_base` стоял ещё в базе сравнения: находки
        по нему нет и переход не отказывает.

        Ловит мутацию: ранний `return` собран по одному только head («в
        методе есть ранний выход») без сверки с тем же именем в базе —
        правка соседнего метода такого файла начинает отказывать переходу
        за чужой давний код, и правило появления требования 6, общее с
        маркерами пропуска, не соблюдено.
        """
        self.apply(EARLY_RETURN_BASE_PATH, EARLY_RETURN_IN_BASE_PLUS_NEW_METHOD)

        outcome = self.run_gate()

        self.assertFalse(
            outcome.refused,
            f"ранний return из базы сравнения находки не даёт (AC-6, "
            f"вторая фраза); журнал: {outcome.journal}; "
            f"stdout: {outcome.printed}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertNotIn(EARLY_RETURN_BASE_CLASS, outcome.detail,
                         f"detail: {outcome.detail}")


if __name__ == "__main__":
    unittest.main()
