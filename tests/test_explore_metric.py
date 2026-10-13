"""Разбор искомой строки команды оболочки метрикой разведки
(`explore_metric.search_string`, SPEC 01M4RZAYH3SWJW4WFBW4QW15FP,
требование 6) — свойства, которых не касаются долгоживущие файлы задачи:
`-e`/`--regexp`, `git grep`, начало команды после `$(` и разделители
внутри кавычек."""
import unittest

from orchestrator import explore_metric


class SearchStringTest(unittest.TestCase):

    def test_regexp_flag_value_is_the_pattern(self):
        """`-e`/`--regexp`/`--regexp=` дают шаблон, даже если он сам
        начинается с `-` и перед ним стоит флаг со значением.

        Ловит мутацию: значение `-e`/`--regexp` не берётся шаблоном —
        `-needle` пропустится как флаг, и шаблоном станет путь
        `orchestrator/`.
        """
        for command in ("grep -rn -A 2 -e -needle orchestrator/",
                        "rg --regexp -needle orchestrator/",
                        "grep --regexp=-needle orchestrator/"):
            with self.subTest(command=command):
                self.assertEqual("-needle", explore_metric.search_string(command))

    def test_git_grep_and_command_substitution_start(self):
        """`git grep` — команда поиска; `grep` после `$(` — начало команды;
        `grep` в аргументе другой команды — нет.

        Ловит мутацию: `$(` не признан началом команды — у второй строки
        шаблона не будет (`None`); любое слово `grep` в строке сочтено
        командой — у третьей строки появится шаблон `x`.
        """
        self.assertEqual("needle", explore_metric.search_string(
            "git grep -n needle -- orchestrator"))
        self.assertEqual("needle", explore_metric.search_string(
            "echo $(grep -l needle tests/*.py)"))
        self.assertIsNone(explore_metric.search_string("echo grep x"))

    def test_separators_inside_quotes_do_not_start_a_command(self):
        """`|` и `;` внутри кавычек — часть шаблона, не разделитель.

        Ловит мутацию: разделители ищутся и внутри кавычек — шаблон
        `a|b` оборвётся на `a`, а `"x; grep y"` даст `y` второй командой.
        """
        self.assertEqual("a|b", explore_metric.search_string(
            "grep -E 'a|b' orchestrator/"))
        self.assertEqual("x; grep y", explore_metric.search_string(
            'grep "x; grep y" a.py'))


if __name__ == "__main__":
    unittest.main()
