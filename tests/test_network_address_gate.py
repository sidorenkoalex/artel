"""Юнит-тесты рубежа сетевых адресов `tests/` на `in_dev -> verifying`
(SPEC 01M4JN2EDQP8Q3WVYK0TS95ZVC, требование 3) — свойства, которых не
держат долгоживущий файл задачи (само правило адресов) и её планка
(отказ и пропуск на настоящем git): fail-closed на сбое git, отбор записей
диффа (удаление, переименование, файлы вне `tests/**/*.py`), пропуск
канарейки и чужого проекта, класс отказа «чинит роль».

Адреса собраны по частям (`SEP`): файл сам лежит в `tests/` и обязан
проходить инвариант 35 и этот же рубеж.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_advance, gitcmd, store  # noqa: E402
from orchestrator.advance_gates import refusal_classes, tests_writing  # noqa: E402
from tests.sandbox import TaskIdSchemaConnTmpRootTest  # noqa: E402

SEP = ":" + "//"
DNS_TEXT = f"URL = 'https{SEP}mirror.example.test/repo.git'\n"
CLEAN_TEXT = f"URL = 'http{SEP}127.0.0.1:8080/repo.git'\n"


def _task_row(is_canary=False):
    return {"branch": "task/t001-x", "is_canary": is_canary}


def _show_from(texts: dict):
    def show(branch, rel, *, repo=None):
        if rel in texts:
            return texts[rel], ""
        return None, "нет такого пути"
    return show


class NetworkAddressGateTest(TaskIdSchemaConnTmpRootTest):

    def gate(self, entries, texts, t=None):
        with mock.patch.object(gitcmd, "diff_base", return_value="base"), \
             mock.patch.object(gitcmd, "diff_name_status",
                               return_value=entries), \
             mock.patch.object(gitcmd, "show", _show_from(texts)):
            return tests_writing._network_address_gate(
                self.conn, self.task_id, t or _task_row())

    def test_git_not_answering_diff_base_refuses(self):
        """Неответ git на базу сравнения — отказ класса «чинит Оператор».

        Ловит мутацию: `base is None` трактуется как «диффа нет» — рубеж
        молча пропускает ветку, которую не смог прочитать (fail-open).
        """
        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            refusal = tests_writing._network_address_gate(
                self.conn, self.task_id, _task_row())
        self.assertIsNotNone(refusal)
        self.assertEqual(tests_writing.NETWORK_ADDRESS_GIT_ACTION,
                         refusal.action)
        self.assertEqual(refusal_classes.OPERATOR_FIXES,
                         refusal_classes.refusal_class(refusal.action))

    def test_git_not_answering_diff_or_show_refuses(self):
        """Неответ git на список диффа или на чтение файла — тот же отказ.

        Ловит мутацию: сбой `diff_name_status` или `show` пропускается
        (`continue`/пустой список) — файл с адресом уходит в CI непрочитанным.
        """
        with mock.patch.object(gitcmd, "diff_base", return_value="base"), \
             mock.patch.object(gitcmd, "diff_name_status", return_value=None):
            refusal = tests_writing._network_address_gate(
                self.conn, self.task_id, _task_row())
        self.assertEqual(tests_writing.NETWORK_ADDRESS_GIT_ACTION,
                         refusal.action)
        refusal = self.gate([("M", "tests/test_x.py", None)], {})
        self.assertEqual(tests_writing.NETWORK_ADDRESS_GIT_ACTION,
                         refusal.action)
        self.assertIn("tests/test_x.py", refusal.detail)

    def test_violation_is_role_class_and_journaled(self):
        """Адрес в изменённом файле — отказ класса «чинит роль» через каркас.

        Ловит мутацию: отказ рубежа получает действие вне перечня
        `refusal_classes` — цикл `auto` останавливается на Операторе
        вместо возврата шага разработчику.
        """
        with mock.patch.object(gitcmd, "diff_base", return_value="base"), \
             mock.patch.object(gitcmd, "diff_name_status",
                               return_value=[("M", "tests/test_x.py", None)]), \
             mock.patch.object(gitcmd, "show",
                               _show_from({"tests/test_x.py": DNS_TEXT})):
            refused = fsm_advance._run_gates(
                self.conn, self.task_id,
                [lambda: fsm_advance._network_address_gate(
                    self.conn, self.task_id, _task_row())])
        self.assertTrue(refused)
        row = self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=?",
            (self.task_id,)).fetchone()
        self.assertEqual(refusal_classes.ROLE_FIXES,
                         refusal_classes.refusal_class(row["action"]))
        self.assertIn("tests/test_x.py:1", row["detail"])

    def test_entry_selection(self):
        """Удалённые файлы и пути вне `tests/**/*.py` не читаются; у
        переименования читается новый путь.

        Ловит мутацию: рубеж читает старый путь переименования (адрес в
        переименованном файле проходит) или зовёт `show` на удалённый
        файл (ложный отказ «git не ответил» на законное удаление).
        """
        entries = [("D", "tests/test_gone.py", None),
                   ("M", "tests/fixture.txt", None),
                   ("R100", "tests/test_old.py", "tests/sub/test_new.py")]
        refusal = self.gate(entries, {"tests/sub/test_new.py": DNS_TEXT})
        self.assertIsNotNone(refusal)
        self.assertIn("tests/sub/test_new.py:1", refusal.detail)
        self.assertNotIn("test_gone", refusal.detail)
        clean = self.gate(entries, {"tests/sub/test_new.py": CLEAN_TEXT})
        self.assertIsNone(clean)

    def test_canary_and_foreign_project_skip(self):
        """Канарейка и чужой проект — рубеж не читает git вовсе.

        Ловит мутацию: условие `is_canary` или `is_artel` убрано — рубеж
        зовёт `diff_base` у задачи, к которой инвариант 35 не относится.
        """
        def boom(*args, **kwargs):
            raise AssertionError("рубеж адресов не обязан звать diff_base")

        with mock.patch.object(gitcmd, "diff_base", boom):
            self.assertIsNone(tests_writing._network_address_gate(
                self.conn, self.task_id, _task_row(is_canary=True)))
            store.insert_task(self.conn, self.task_id, "Задача", "in_dev",
                              "task/t001-x", "sled", 25.0)
            self.assertNotEqual(config.DEFAULT_TARGET, "sled")
            self.assertIsNone(tests_writing._network_address_gate(
                self.conn, self.task_id, _task_row()))


if __name__ == "__main__":
    unittest.main()
