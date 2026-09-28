"""AC-1: глубина рассуждения в команде шага провайдера `codex`.

Красен до реализации: пары `model_reasoning_effort=high` нет ни в
`CONFIG_OVERRIDES`, ни среди `-c`-значений argv команды шага, и
константы со значением `high` в модуле `orchestrator/providers/codex.py`
тоже нет — обе проверки падают на отсутствии кода задачи.
"""
import unittest

import _util


class Ac1StepCommandTest(unittest.TestCase):
    """Argv команды шага (`CodexProvider.command()`) и именованная
    константа значения глубины рассуждения."""

    def setUp(self):
        self.argv = _util.step_argv(self)

    def test_ac1_reasoning_effort_pair_stands_among_c_flags_before_exec(self):
        """Пара глубины рассуждения едет команде шага флагом `-c` и
        стоит до подкоманды `exec`; значение задано именованной
        константой модуля, а не только литералом в argv.

        Ловит мутацию: пара дописана в общий список флагов ПОСЛЕ
        подкоманды (`exec --json … -c model_reasoning_effort=high`) —
        0.155.1 разбирает глобальные `-c` только до подкоманды, и шаг
        либо падает разбором аргументов, либо молча уходит на дефолт
        вендора (`low` у `gpt-6-astra`). Наблюдаемо: индекс значения в
        argv становится больше индекса `exec`.
        """
        self.assertIn("exec", self.argv, self.argv)
        at = self.argv.index("exec")
        pair = f"{_util.REASONING_KEY}={_util.REASONING_VALUE}"

        self.assertIn(pair, _util.dash_c_values(self.argv), self.argv)

        position = self.argv.index(pair)
        self.assertEqual(self.argv[position - 1], "-c", self.argv)
        self.assertLess(position, at, self.argv)
        self.assertTrue(
            _util.named_string_constants(_util.codex_provider,
                                         _util.REASONING_VALUE),
            "в orchestrator/providers/codex.py нет именованной константы "
            f"со значением {_util.REASONING_VALUE!r}")


if __name__ == "__main__":
    unittest.main()
