"""AC-8: инструмент манифеста объявляет сам провайдер (`cli_tool()`) —
для `claude` то же имя, тот же минимум версии, по-прежнему обязательный.

Красен до реализации: метода `cli_tool()` нет ни у кого — реестр
провайдеров ещё не существует, а `stack.REQUIRED_TOOLS` несёт запись
`claude` литералом.
"""
import inspect
import unittest

from orchestrator import stack
from _providers import CLAUDE, cli_tool_parts, provider


class ProviderCliToolTest(unittest.TestCase):
    """Манифест стека и провайдер называют один и тот же инструмент."""

    def test_ac8_cli_tool_matches_the_manifest_entry_for_claude(self):
        """`cli_tool()` провайдера `claude` называет тот же инструмент и
        тот же минимум версии, что запись манифеста, и инструмент
        остаётся обязательным (он в `REQUIRED_TOOLS` и в объявленных
        инструментах PATH роли).

        Ловит мутацию: провайдер объявил свой минимум версии мимо
        манифеста (или назвал инструмент другим именем) — два источника
        истины о том, что нужно исполнителю роли, разошлись ровно там,
        где задача их сводила; либо запись перестала быть обязательной
        (уехала в необязательный список) и отсутствие CLI больше не
        красит `doctor`.
        """
        name, minimum = cli_tool_parts(provider().cli_tool())

        self.assertEqual(name, CLAUDE)
        self.assertIn(CLAUDE, stack.REQUIRED_TOOLS)
        self.assertIn(CLAUDE, stack.DECLARED_TOOLS)
        requirement = stack.REQUIRED_TOOLS[CLAUDE]
        self.assertEqual(minimum, requirement.minimum)
        self.assertEqual(requirement.command[0], CLAUDE)
        self.assertIn("--version", requirement.command)

    def test_ac8_manifest_takes_the_tool_from_the_provider(self):
        """Запись `claude` в `stack.REQUIRED_TOOLS` собрана обращением к
        провайдеру, а не повторена литералом рядом.

        Ловит мутацию: `cli_tool()` у провайдера появился, но манифест
        по-прежнему несёт свою копию имени и версии — следующий
        провайдер снова правит `stack.py` руками, и расхождение двух
        копий никто не заметит до отказа шага.
        """
        source = inspect.getsource(stack)

        self.assertTrue(
            "cli_tool" in source or "providers" in source,
            "orchestrator/stack.py не обращается к провайдеру за "
            "инструментом манифеста — запись осталась литералом")


if __name__ == "__main__":
    unittest.main()
