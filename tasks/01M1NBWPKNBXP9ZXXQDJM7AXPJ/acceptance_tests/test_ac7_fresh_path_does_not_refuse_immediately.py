"""AC-7 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): Юнит-тест: путь
«fresh» после push головы ветки в origin ждёт CI циклом ожидания, не
отказывает немедленно по «нет ни одной проверки».

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-7.

Красен до реализации: см. докстринг test_ac5 — на пути "fresh" сегодня
`ci.branch_status` зовётся ровно один раз, любой не-красный,
не-зелёный ответ (включая «нет ни одной проверки») немедленно
`sys.exit`'ит. Проверено прогоном на немодифицированном коде при
подготовке файла: второй вызов `ci.branch_status` не происходит,
`SystemExit` поднимается на первом же ответе.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import NOCHECKS, MergeGateFreshCiWaitSandbox  # noqa: E402


class _StopAfterSecondPoll(Exception):
    """Сентинел этого теста: второй опрос `ci.branch_status` состоялся —
    гейт не отказал по первому же ответу «нет ни одной проверки»."""


class Ac7DoesNotRefuseOnFirstNoChecksResponseTest(MergeGateFreshCiWaitSandbox):

    def test_ac7_first_no_checks_response_does_not_refuse_immediately(self):
        """Первый смоделированный ответ CI — «нет ни одной проверки»
        (голова только что впервые опубликована, checks ещё не успели
        завестись). Гейт обязан продолжить опрос циклом ожидания (как
        путь «pulled»), а не отказать немедленно: второй опрос CI —
        прямое наблюдаемое доказательство, что цикл продолжился, а не
        оборвался на первом ответе.

        Ловит мутацию: сегодняшний код на первом же не-красном,
        не-зелёном ответе `sys.exit`'ит («merge отклонён: <note>») —
        второго вызова `ci.branch_status` не будет никогда, тест
        поймает `SystemExit` вместо ожидаемого сентинела и провалится.
        """
        calls = {"n": 0}

        def branch_status(branch):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise _StopAfterSecondPoll()
            return NOCHECKS

        self.patch_branch_status(branch_status)

        with self.assertRaises(_StopAfterSecondPoll):
            self.run_cycle()

        self.assertEqual(calls["n"], 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
