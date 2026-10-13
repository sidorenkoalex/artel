"""Команда `knowledge` и подсказка миссии: свойства сверх долгоживущих
файлов задачи 01M4S0K2MJRMVMQWKATAME3RHR — имена распаковки и обработчиков
`try` в проверке свежести, счёт записей обращения, синтаксис команды,
сбой записи отказа подсказки.
"""
import ast
import contextlib
import io
import sqlite3
import unittest
from unittest import mock

from orchestrator import budget, config, knowledge_cards as kc, role_prompt
from orchestrator import store
from tests.sandbox import TmpRootTest


class DefinedNamesTest(unittest.TestCase):

    def test_unpacking_and_try_handler_names_found(self):
        """Цели распаковки (`A, (B, *C) = …`), `def` в обработчике `except` и
        присваивание в `finally` верхнего уровня — найденные символы.

        Ловит мутацию: тела обработчиков `except` и `finally` не обходятся
        (или распаковка не разбирается) — `handler_fn`, `FINAL`, `C` не в
        перечне, свежая карточка получила бы пометку «возможно устарела».
        """
        tree = ast.parse("A, (B, *C) = 1, (2, 3)\n"
                         "try:\n    pass\n"
                         "except ImportError:\n    def handler_fn():\n"
                         "        pass\n"
                         "finally:\n    FINAL = 1\n")
        names = set(kc._defined_names(tree.body, ""))
        self.assertTrue({"A", "B", "C", "handler_fn", "FINAL"} <= names, names)


class AccessTallyTest(unittest.TestCase):

    def test_exhausted_record_and_other_actions_not_counted(self):
        """Записи обращения, запись «предел исчерпан» и запись отказа
        подсказки того же автора.

        Наблюдение: к пределу идут только записи обращения; запись «предел
        исчерпан» — признак, не счёт.

        Ловит мутацию: счёт берёт все записи `ACCESS_ACTION` без проверки
        префикса — запись «предел исчерпан» съедает место в пределе.
        """
        rows = [{"action": kc.ACCESS_ACTION, "detail": "обращение 1"},
                {"action": kc.ACCESS_ACTION, "detail": kc.exhausted_detail()},
                {"action": kc.HINT_REFUSAL_ACTION, "detail": "коды"},
                {"action": kc.ACCESS_ACTION, "detail": None}]
        self.assertEqual(kc.access_tally(rows), (2, True))


class CommandSyntaxTest(TmpRootTest):

    def test_wrong_arity_refused_without_journal(self):
        """`knowledge` с одним аргументом и с тремя.

        Наблюдение: отказ `SystemExit` с текстом о синтаксисе, журнал задачи
        пуст.

        Ловит мутацию: проверка числа аргументов убрана — распаковка падает
        `ValueError` вместо отказа с синтаксисом команды.
        """
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T701", "Задача", "in_dev",
                          "task/t701-zadacha", config.DEFAULT_TARGET, 25.0)
        for rest in (["T701"], ["T701", "a.py", "b.py"]):
            with self.subTest(rest=rest):
                with self.assertRaises(SystemExit) as caught:
                    kc.cmd_knowledge(rest)
                self.assertIn("синтаксис", str(caught.exception.code))
        self.assertEqual(store.task_steps(store.db(), "T701"), [])


class HintJournalFailureTest(unittest.TestCase):

    def test_journal_error_keeps_hint_line(self):
        """Отказ чтения вида, а запись журнала шага отказывает
        `sqlite3.OperationalError`.

        Наблюдение: строка-подсказка возвращена, в stderr одна строка,
        исключение наружу не вышло.

        Ловит мутацию: перехват `sqlite3.Error` вокруг
        `budget.journal_warning_once` убран — сборка миссии падает и шаг
        роли не стартует.
        """
        err = io.StringIO()
        with mock.patch.object(kc, "hint_line",
                               return_value=("строка", [("system",
                                                         kc.FIELD_FORM)])), \
                mock.patch.object(budget, "journal_warning_once",
                                  side_effect=sqlite3.OperationalError("ro")), \
                contextlib.redirect_stderr(err):
            line = role_prompt.knowledge_hint_note(object(), "T801",
                                                   {"target": "artel"})
        self.assertEqual(line, "строка")
        self.assertEqual(len([s for s in err.getvalue().splitlines()
                              if s.strip()]), 1)


if __name__ == "__main__":
    unittest.main()
