"""AC-4: второе место сборки `-c` и команда шага первого провайдера.

Зелёный с рождения: держит существующее поведение — ни
`CodexProvider.login_status_command()`, ни `ClaudeProvider.command()`
новой пары не несут, и до правок задачи это уже так. Метод краснеет
ровно тогда, когда правка задачи занесёт глубину рассуждения в одно из
этих двух мест.

Полный argv ни одной из двух команд планка не фиксирует снимком:
утверждать сегодняшний состав флагов публичной команды запрещено
(ADR-0018, решение Оператора 27.09 — планка
01M3FQ2Z2PY0E9T5F5WQ207NP5 покраснела от законно добавленного флага).
«Байт-в-байт прежним» проверяется в том измерении, которое эта задача
вообще способна изменить: новой пары там нет ни под каким видом.
"""
import unittest

import _util


class Ac4UntouchedCommandsTest(unittest.TestCase):
    """`login_status_command()` провайдера `codex` и `command()`
    провайдера `claude`."""

    def setUp(self):
        self.pair = (_util.REASONING_KEY, _util.REASONING_VALUE)
        _util.stub_tool_path(self)
        self.login_argv = _util.providers.get(
            "codex").login_status_command()
        self.claude_argv = _util.providers.get("claude").command(
            "claude-opus-5")

    def test_ac4_neither_login_status_nor_the_claude_step_gains_the_pair(self):
        """Проверка подписочного входа и команда шага первого провайдера
        остаются прежними: глубина рассуждения не попадает ни в argv
        `codex login status`, ни в argv шага `claude`.

        Ловит мутацию: пару добавили в `AUTH_OVERRIDES` вместо
        отдельного члена `CONFIG_OVERRIDES` («набор один, так короче») —
        `-c`-пара уезжает и в проверку входа, и в документированную
        команду ручного входа Оператора (`docs/stack.md`), которой
        глубина рассуждения не нужна вовсе: наблюдаемо, что argv
        `login_status_command()` получает лишний `-c`-флаг.
        """
        self.assertNotIn(self.pair, _util.codex_provider.AUTH_OVERRIDES)

        login_pairs = [tuple(value.split("=", 1))
                       for value in _util.dash_c_values(self.login_argv)]
        self.assertEqual(login_pairs,
                         [tuple(item) for item
                          in _util.codex_provider.AUTH_OVERRIDES],
                         self.login_argv)
        for name, argv in (("codex login status", self.login_argv),
                           ("claude step", self.claude_argv)):
            with self.subTest(command=name):
                self.assertEqual(
                    [item for item in argv
                     if _util.REASONING_KEY in item], [], argv)


if __name__ == "__main__":
    unittest.main()
