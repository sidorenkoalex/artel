"""`artel.py observe add|remove <obs>` с лишним позиционным аргументом
отказывает целиком и не меняет список задач наблюдения.

Группа: долгоживущий

Красен до реализации: `_cmd_observe` молча игнорирует лишний позиционный аргумент — `observe add <obs> --tasks A B` добавляет A и возвращает 0, `observe remove` так же убирает A; методы AC-6 и AC-7 красные.

Сценарий — публичный CLI `artel.main` с подменённым `sys.argv`, как у
Оператора в терминале; песочница `TaskSeededTmpRootTest` (БД во временном
каталоге, задача `self.TASK`), сессия Оператора (`ARTEL_ROLE_ENV` пуст).
Наблюдение регистрируется `observe register`, список задач читается
`observe show <obs> --json`. «Подсказка формы через запятую» — текст
отказа несёт форму `A,B` либо слово «запятая» в любой форме; точная
формулировка не навязывается. Номера задач и то, заведена ли лишняя
задача `B` в БД (для `add`), — из `random`, зерно печатается и входит в
текст провала.
"""
import contextlib
import io
import json
import os
import random
import sys
import unittest
from unittest import mock

from orchestrator import artel, config, store
from tests.sandbox import TaskSeededTmpRootTest


class ObserveExtraArgsSandbox(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        operator_env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        operator_env.start()
        self.addCleanup(operator_env.stop)
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.chat = f"chat-{self.rng.randrange(1 << 20)}"
        numbers = self.rng.sample(range(100, 1000), 2)
        self.task_a, self.task_b = (f"T{n}" for n in numbers)

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def add_task(self, task_id: str) -> None:
        store.insert_task(store.db(), task_id, f"Задача {task_id}", "in_dev",
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def cli(self, *argv: str) -> tuple[str, bool]:
        """(вывод вместе с текстом отказа, был ли ненулевой код возврата)."""
        buf = io.StringIO()
        failed = False
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                code = artel.main()
            except SystemExit as exc:
                code = exc.code
            if code not in (None, 0):
                failed = True
                buf.write(f"\n{code}")
        return buf.getvalue(), failed

    def register(self, tasks: str) -> str:
        out, failed = self.cli("observe", "register", "--client", "claude",
                               "--chat", self.chat, "--tasks", tasks)
        self.assertFalse(failed, self.note(f"предпосылка: register отказал:\n{out}"))
        return json.loads(out)["id"]

    def tasks_of(self, observation_id: str) -> list:
        out, failed = self.cli("observe", "show", observation_id, "--json")
        self.assertFalse(failed, self.note(f"show отказал:\n{out}"))
        return sorted(json.loads(out)["tasks"])

    def assert_named_refusal(self, out: str, failed: bool, action: str) -> None:
        self.assertTrue(failed, self.note(
            f"observe {action} с лишним аргументом {self.task_b} завершился "
            f"нулевым кодом:\n{out}"))
        self.assertIn(self.task_b, out, self.note(
            f"отказ observe {action} не называет лишний аргумент:\n{out}"))
        hint = f"{self.task_a},{self.task_b}" in out or "запят" in out.lower()
        self.assertTrue(hint, self.note(
            f"отказ observe {action} не подсказывает перечисление через "
            f"запятую:\n{out}"))


class ObserveAddExtraArgTest(ObserveExtraArgsSandbox):

    def test_ac6_add_with_extra_positional_refuses_without_adding(self):
        """`observe add <obs> --tasks A B` — ненулевой код, отказ называет `B` и подсказывает запятую, `A` не добавлена.

        Сценарий: наблюдение зарегистрировано на задачу `self.TASK`; задача
        `A` заведена, `B` заведена или нет (случайно). `observe add <obs>
        --tasks A B` завершается ненулевым кодом; текст отказа называет
        `B` и подсказывает форму через запятую; список задач наблюдения
        после вызова тот же, что до него.

        Ловит мутацию: лишние позиционные аргументы не проверяются (как на
        пине) — `A` добавлена, код 0; проверка стоит после
        `store.add_observation_tasks` — отказ есть, но `A` уже добавлена;
        отказ без имени лишнего аргумента.
        """
        self.add_task(self.task_a)
        b_exists = self.rng.random() < 0.5
        if b_exists:
            self.add_task(self.task_b)
        observation_id = self.register(self.TASK)
        before = self.tasks_of(observation_id)

        out, failed = self.cli("observe", "add", observation_id,
                               "--tasks", self.task_a, self.task_b)

        self.assert_named_refusal(out, failed, f"add (B в БД: {b_exists})")
        self.assertEqual(self.tasks_of(observation_id), before, self.note(
            f"список задач наблюдения изменён отказным add:\n{out}"))


class ObserveRemoveExtraArgTest(ObserveExtraArgsSandbox):

    def test_ac7_remove_with_extra_positional_refuses_without_removing(self):
        """`observe remove <obs> --tasks A B` (обе — задачи наблюдения) — ненулевой код с той же причиной, `A` не убрана.

        Сценарий: задачи `A` и `B` заведены, наблюдение зарегистрировано на
        `self.TASK`, `A` и `B`. `observe remove <obs> --tasks A B`
        завершается ненулевым кодом; текст отказа называет `B` и
        подсказывает форму через запятую; список задач наблюдения не
        изменён.

        Ловит мутацию: проверка лишних аргументов добавлена только в ветку
        `add` — `remove` по-прежнему убирает `A` с кодом 0; проверка стоит
        после `store.remove_observation_tasks`.
        """
        self.add_task(self.task_a)
        self.add_task(self.task_b)
        observation_id = self.register(
            ",".join((self.TASK, self.task_a, self.task_b)))
        before = self.tasks_of(observation_id)
        self.assertIn(self.task_a, before, self.note("предпосылка: A не в наблюдении"))

        out, failed = self.cli("observe", "remove", observation_id,
                               "--tasks", self.task_a, self.task_b)

        self.assert_named_refusal(out, failed, "remove")
        self.assertEqual(self.tasks_of(observation_id), before, self.note(
            f"список задач наблюдения изменён отказным remove:\n{out}"))


if __name__ == "__main__":
    unittest.main()
