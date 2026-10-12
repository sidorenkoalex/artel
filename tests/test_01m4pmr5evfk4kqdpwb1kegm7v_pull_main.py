"""Команда Оператора `pull-main`: подтяжка main в ветку задачи на `verifying`.

Команда исполняется через публичный вход диспетчера `artel.main()` с
подменённым `sys.argv` — так тест не зависит от имени функции внутри
`orchestrator/pull_main.py`. Окружение процесса на время вызова — окружение
Оператора (временный HOME, без маркера роли), сессия — `ARTEL_SESSION_ID`.

Связка, которую держит файл: команда — lease — БД задачи — узел подтяжки
`pull.evaluate`. Песочница — `tests.sandbox.LightTransitionSandbox`
(поддельный git, рабочая копия во временном каталоге, артефакты задачи с
диска). Git-ответы сценария даёт хук `in_repo_handlers`: число отставших
коммитов (`rev-list --count`), документный дифф main (`merge-base` и
`diff --name-only`), исход `git merge`, посторонний файл в индексе. Прогон
планки (`acceptance.run`) и отправка головы
(`github_adapter.ensure_head_in_origin`) подменены — их вызовы и есть
наблюдаемое свойство.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/pull_main.py и команды pull-main в таблице artel.py ещё нет — импорт модуля падает, диспетчер отвечает «Неизвестная команда», verifying нет в pull.PULL_CONFLICT_MARKED_STATES.
"""
import contextlib
import importlib
import io
import os
import random
import shutil
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, artel, config, github_adapter, pull,
                          store, workspace)
from scripts import ci_push_class
from tests.sandbox import LightTransitionSandbox, _alive_foreign_pid

#: Метка `updated_at` задачи до команды — заведомо в прошлом.
OLD_STAMP = "2020-01-01 00:00:00Z"

#: Состояния, отличные от `verifying`, на которых команда обязана отказать.
NON_VERIFYING_STATES = ("spec_gate", "tests_writing", "in_dev", "review",
                        "acceptance", "merge_gate", "done")

#: Файл, конфликтующий при `git merge` в сценарии конфликта.
CONFLICT_FILE = "orchestrator/conflicting_module.py"


def pull_main_module():
    """Модуль команды; импорт — в тесте, чтобы отсутствие модуля роняло
    каждый тест по отдельности, а не сбор файла."""
    return importlib.import_module("orchestrator.pull_main")


class PullMainSandbox(LightTransitionSandbox):
    """Задача в `verifying` с планкой на диске, main ушёл вперёд на
    случайное число коммитов; отправка головы и прогон планки подменены."""

    TASK_TITLE = "Подтяжка main командой pull-main"

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.session = f"operator-{self.rng.randrange(1 << 30):x}"

        # Параметры сценария git: меняются тестом до вызова команды.
        self.behind = self.rng.randint(1, 9)
        self.doc_only_main = False
        self.doc_files = [f"docs/note-{self.rng.randrange(1 << 20):x}.md",
                          f"docs/backlog-{self.rng.randrange(1 << 20):x}.md"]
        self.merge_conflict = False
        self.staged_stray = None
        self.git_calls: list = []
        self.in_repo_handlers.append(self._scenario_git)

        self.write_acceptance_plank()
        self.set_state("verifying")
        conn = store.db()
        conn.execute("UPDATE tasks SET updated_at=? WHERE id=?",
                     (OLD_STAMP, self.TASK))
        conn.commit()

        self.push = mock.Mock(return_value=(True, ""))
        self.plank_run = mock.Mock(return_value=(True, "1 passed"))
        self.update_task = mock.Mock(wraps=store.update_task)
        for module, name, value in (
                (github_adapter, "ensure_head_in_origin", self.push),
                (acceptance, "run", self.plank_run),
                (store, "update_task", self.update_task)):
            patcher = mock.patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ git сценария

    @staticmethod
    def _done(repo, args, code: int = 0, out: str = "", err: str = ""):
        """Ответ заглушки на команду `args` в репозитории `repo`."""
        return subprocess.CompletedProcess((str(repo), *args), code, out, err)

    def _scenario_git(self, repo, *args):
        self.git_calls.append(args)
        if args[:2] == ("rev-list", "--count"):
            if self.behind is None:
                return self._done(repo, args, 128, "", "fatal: bad revision")
            return self._done(repo, args, 0, f"{self.behind}\n")
        if args[:1] == ("merge-base",) and self.doc_only_main:
            return self._done(repo, args, 0, "1234abcd" * 5 + "\n")
        if (args[:2] == ("diff", "--name-only") and self.doc_only_main
                and "--diff-filter=U" not in args):
            side = "" if args[-1] == self.branch else "\n".join(self.doc_files)
            return self._done(repo, args, 0, side + "\n")
        if args[:3] == ("diff", "--cached", "--name-only") and self.staged_stray:
            return self._done(repo, args, 0, self.staged_stray + "\n")
        if args[:1] == ("merge",) and "--abort" in args:
            return self._done(repo, args)
        if args[:1] == ("merge",):
            if self.merge_conflict:
                return self._done(repo, args, 1, "",
                                  f"CONFLICT (content): Merge conflict in "
                                  f"{CONFLICT_FILE}")
            return self._done(repo, args)
        if args[:3] == ("diff", "--name-only", "--diff-filter=U"):
            out = CONFLICT_FILE + "\n" if self.merge_conflict else ""
            return self._done(repo, args, 0, out)
        if args[:1] == ("push",):
            return self._done(repo, args)
        return None

    # --------------------------------------------------------------- вызов

    def operator_env(self) -> dict:
        return {"HOME": str(self.root / "operator-home"),
                "PATH": os.environ.get("PATH", ""),
                "ARTEL_SESSION_ID": self.session}

    def dispatch(self, argv, env: dict | None = None) -> str:
        """Всё, что сказал диспетчер: stdout, stderr и текст `SystemExit`."""
        out = io.StringIO()
        with mock.patch.dict(os.environ, env or self.operator_env(), clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                out.write(f"\n{exc.code}")
        return out.getvalue()

    def run_pull_main(self, task_ref: str | None = None) -> str:
        return self.dispatch(("pull-main", task_ref or self.TASK))

    # ---------------------------------------------------------- наблюдения

    def reset_observations(self) -> None:
        self.git_calls.clear()
        self.push.reset_mock()
        self.plank_run.reset_mock()
        self.update_task.reset_mock()

    def set_task_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def merges(self) -> list:
        return [a for a in self.git_calls
                if a[:1] == ("merge",) and "--abort" not in a]

    def behind_queries(self) -> list:
        return [a for a in self.git_calls if a[:2] == ("rev-list", "--count")]

    def git_pushes(self) -> list:
        return [a for a in self.git_calls if a[:1] == ("push",)]

    def ceiling_resets(self) -> list:
        return [c for c in self.update_task.call_args_list
                if "updated_at" in c.kwargs]

    def journal(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def actions(self) -> list:
        return [row["action"] for row in self.journal()]

    def task(self):
        return store.get_task(store.db(), self.TASK)

    def assert_untouched(self, text: str, expected_state: str) -> None:
        """Ни подтяжки, ни отправки, ни сброса потолка; состояние прежнее."""
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(self.task()["state"], expected_state, tag)
        self.assertEqual(self.merges(), [], tag)
        self.assertEqual(self.behind_queries(), [], tag)
        self.plank_run.assert_not_called()
        self.push.assert_not_called()
        self.assertEqual(self.git_pushes(), [], tag)
        self.assertEqual(self.ceiling_resets(), [], tag)
        self.assertEqual(self.task()["updated_at"], OLD_STAMP, tag)
        self.assertNotIn(pull_main_module().PULL_MAIN_ACTION, self.actions(), tag)


class CommandDispatchTest(PullMainSandbox):

    def test_ac1_command_is_dispatched_by_full_id_and_prefix(self):
        """`pull-main` есть в справке и в таблице диспетчера, id — полный и префикс.

        Сценарий: справка `artel.py` без аргументов называет `pull-main`;
        модуль команды — `orchestrator/pull_main.py`; ветка задачи свежа
        (`rev-list --count` = 0), команда вызвана с полным id и со случайным
        префиксом id — в обоих случаях она доходит до задачи и отвечает
        «main уже в ветке», а не «Неизвестная команда».

        Ловит мутацию: строка `pull-main` есть в справке, но не в таблице
        команд (или наоборот), либо префикс не разрешается в полный id через
        `store.resolve_task_id` — вывод «Неизвестная команда» или отказ «задача
        не найдена» вместо ответа о свежести ветки.
        """
        module = pull_main_module()
        source = Path(module.__file__)
        self.assertEqual((source.parent.name, source.name),
                         ("orchestrator", "pull_main.py"))
        self.assertIn("pull-main", self.dispatch(()),
                      f"зерно: {self.seed}; справка")

        self.behind = 0
        prefix = self.TASK[:self.rng.randint(6, len(self.TASK) - 1)]
        for ref in (self.TASK, prefix):
            with self.subTest(ref=ref):
                text = self.run_pull_main(ref)
                tag = f"зерно: {self.seed}; id {ref!r}; вывод: {text!r}"
                self.assertNotIn("Неизвестная команда", text, tag)
                self.assertIn(module.PULL_MAIN_ALREADY_FRESH, text, tag)


class StateRefusalTest(PullMainSandbox):

    def test_ac2_command_refuses_outside_verifying(self):
        """Вне `verifying` (и в `escalated` после потолка) — отказ без подтяжки.

        Сценарий: задача, у которой main ушёл вперёд, поочерёдно стоит в
        `escalated` (эскалирована из `verifying`) и в случайных других
        состояниях; на каждый вызов команда отвечает непустым отказом, а
        состояние, `updated_at`, журнал подтяжки, git-слияние, сверка
        отставания, прогон планки и отправка головы остаются нетронутыми.

        Ловит мутацию: команда работает вне verifying — проверка состояния
        снята или сравнивает не с `verifying` (например, пропускает любое
        состояние, кроме `done`): в `escalated`/`in_dev` идёт `git merge` и
        запись «main подтянут в ветку (pull-main)».
        """
        states = ["escalated", *self.rng.sample(NON_VERIFYING_STATES, 3)]
        for state in states:
            with self.subTest(state=state):
                self.reset_observations()
                self.set_task_state(state)
                if state == "escalated":
                    conn = store.db()
                    conn.execute("UPDATE tasks SET escalated_from='verifying' "
                                 "WHERE id=?", (self.TASK,))
                    conn.commit()
                text = self.run_pull_main()
                self.assertTrue(text.strip(), f"зерно: {self.seed}; {state}: "
                                              f"отказ без текста")
                self.assertNotIn(pull_main_module().PULL_MAIN_ALREADY_FRESH,
                                 text, f"зерно: {self.seed}; {state}")
                self.assert_untouched(text, state)

    def test_ac2_state_is_read_after_lease_from_fresh_row(self):
        """Состояние сверяется после захвата lease по свежему чтению из БД.

        Сценарий: на момент вызова задача в `verifying`; в момент захвата
        lease (запись строки lease в БД) параллельная сторона переводит
        задачу в другое случайное состояние. Команда обязана увидеть новое
        состояние и отказать: подтяжки, сверки отставания, отправки головы и
        сброса потолка нет, состояние — то, что записала параллельная
        сторона.

        Ловит мутацию: состояние проверено до lease — команда читает задачу
        до `lease.run_locked` (или сверяет строку, прочитанную до захвата),
        видит `verifying` и подтягивает main в ветку задачи, которая уже
        ушла из `verifying`.
        """
        moved_to = self.rng.choice(NON_VERIFYING_STATES)
        original_insert = store.insert_lease

        def insert_and_move(conn, task_id, *args, **kwargs):
            original_insert(conn, task_id, *args, **kwargs)
            conn.execute("UPDATE tasks SET state=? WHERE id=?",
                         (moved_to, task_id))
            conn.commit()

        with mock.patch.object(store, "insert_lease", insert_and_move):
            text = self.run_pull_main()
        self.assertTrue(text.strip(), f"зерно: {self.seed}; отказ без текста")
        self.assert_untouched(text, moved_to)


class LeaseRefusalTest(PullMainSandbox):

    def test_ac3_live_lease_of_another_process_refuses(self):
        """Живой lease любого процесса, кроме вызывающего, — отказ.

        Сценарий: задача в `verifying`, main ушёл вперёд; lease держит
        (а) другая сессия на другом host со свежим heartbeat, (а') другая
        сессия на этом host под живым чужим pid, (б) СВОЯ сессия на этом
        host под живым pid, отличным от pid теста (отвязанный `auto`). В
        каждом случае команда отказывает: строка lease прежняя, состояние
        `verifying`, подтяжки, отправки головы и сброса потолка нет.

        Ловит мутацию: команда работает при занятом lease — передаёт
        `same_host_ok=True` в `lease.run_locked` (случаи (а') и (б) проходят
        к `git merge`) либо исполняется вовсе без lease (проходят все три).
        """
        alive_pid = _alive_foreign_pid(self)
        here = socket.gethostname()
        holders = [
            ("другая сессия, другой host",
             f"foreign-{self.rng.randrange(1 << 30):x}",
             self.rng.randrange(2, 1 << 15), f"far-host-{self.rng.randrange(1 << 20):x}"),
            ("другая сессия, этот host, живой pid",
             f"foreign-{self.rng.randrange(1 << 30):x}", alive_pid, here),
            ("своя сессия, этот host, другой живой pid",
             self.session, alive_pid, here),
        ]
        self.rng.shuffle(holders)
        conn = store.db()
        for label, session, pid, host in holders:
            with self.subTest(holder=label):
                self.reset_observations()
                conn.execute("DELETE FROM leases WHERE task_id=?", (self.TASK,))
                conn.commit()
                store.insert_lease(conn, self.TASK, session, pid, host,
                                   store.now())
                text = self.run_pull_main()
                tag = f"зерно: {self.seed}; {label}; вывод: {text!r}"
                self.assertTrue(text.strip(), tag)
                row = store.lease_row(store.db(), self.TASK)
                self.assertIsNotNone(row, tag)
                self.assertEqual((row["session_id"], row["pid"], row["hostname"]),
                                 (session, pid, host), tag)
                self.assert_untouched(text, "verifying")


class PulledOutcomeTest(PullMainSandbox):

    def test_ac5_doc_only_main_advance_is_still_pulled(self):
        """Документный дифф main не отменяет подтяжку командой.

        Сценарий: main после базы ветки несёт только документные файлы
        (`ci_push_class.is_doc_path`), ветка их не трогала — ровно случай,
        в котором автоматическая подтяжка пропускается. Команда всё равно
        сливает main в ветку (`git merge` состоялся), гоняет планку и пишет
        запись «main подтянут в ветку (pull-main)».

        Ловит мутацию: подтяжка пропущена по документному диффу — путь
        команды не отключает `_doc_only_main_advance` в `pull.evaluate`,
        исход `Fresh()`, `git merge` не вызывается, команда отвечает «main
        уже в ветке».
        """
        self.doc_only_main = True
        for rel in self.doc_files:
            self.assertTrue(ci_push_class.is_doc_path(rel), rel)
        text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(len(self.merges()), 1, tag)
        self.plank_run.assert_called()
        self.assertIn(pull_main_module().PULL_MAIN_ACTION, self.actions(), tag)
        self.assertNotIn(pull_main_module().PULL_MAIN_ALREADY_FRESH, text, tag)
        self.assertEqual(self.task()["state"], "verifying", tag)

    def test_ac7_pulled_head_is_pushed_except_canary(self):
        """После подтяжки голова уходит в origin; у канарейки — нет.

        Сценарий: в случайном порядке — обычная задача и та же задача с
        признаком `is_canary`. У обычной `ensure_head_in_origin` вызван
        ровно раз с веткой задачи; у канарейки не вызван, и `git push` нет.

        Ловит мутацию: голова не отправлена в origin после подтяжки —
        команда не зовёт `github_adapter.ensure_head_in_origin` на исходе
        «подтянуто» (или зовёт его и у канарейки, вопреки `is_canary`).
        """
        cases = [False, True]
        self.rng.shuffle(cases)
        conn = store.db()
        for canary in cases:
            with self.subTest(canary=canary):
                self.reset_observations()
                conn.execute("UPDATE tasks SET is_canary=? WHERE id=?",
                             (int(canary), self.TASK))
                conn.commit()
                text = self.run_pull_main()
                tag = f"зерно: {self.seed}; канарейка={canary}; вывод: {text!r}"
                self.assertEqual(len(self.merges()), 1, tag)
                if canary:
                    self.push.assert_not_called()
                    self.assertEqual(self.git_pushes(), [], tag)
                else:
                    self.assertEqual(self.push.call_count, 1, tag)
                    args = self.push.call_args
                    self.assertIn(self.branch,
                                  [*args.args, *args.kwargs.values()], tag)

    def test_ac8_success_keeps_task_in_verifying_and_journals_pull(self):
        """Исход «подтянуто»: задача остаётся в `verifying`, журнал несёт подтяжку.

        Сценарий: main ушёл вперёд на случайное число коммитов, слияние
        чистое, планка зелёная, отправка головы удалась. После команды
        задача в `verifying`, в журнале ровно одна запись с действием
        `pull_main.PULL_MAIN_ACTION`, его текст — «main подтянут в ветку
        (pull-main)».

        Ловит мутацию: команда меняет состояние задачи при успехе — после
        подтяжки зовёт `store.set_state` (в `review`/`in_dev`) или
        `fsm.cmd_advance`, и задача уходит из `verifying`.
        """
        module = pull_main_module()
        self.assertEqual(module.PULL_MAIN_ACTION, "main подтянут в ветку (pull-main)")
        text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(len(self.merges()), 1, tag)
        self.assertEqual(self.task()["state"], "verifying", tag)
        self.assertEqual(self.actions().count(module.PULL_MAIN_ACTION), 1, tag)

    def test_ac8_success_restarts_verifying_ceiling(self):
        """Успешная подтяжка сдвигает `updated_at` на момент команды.

        Сценарий: `updated_at` задачи — далёкое прошлое; в случайном
        порядке обычная задача (отправка головы удалась) и канарейка (без
        отправки). После команды `store.update_task` вызван с `updated_at`,
        и `updated_at` задачи не раньше момента вызова;
        `config.VERIFYING_CEILING_SEC` не изменился.

        Ловит мутацию: потолок не сброшен после подтяжки — команда не зовёт
        `store.update_task(conn, id, updated_at=store.now())` (или зовёт его
        только у не-канарейки), и опрос `verifying` эскалирует задачу по
        старому отсчёту сразу после подтяжки.
        """
        ceiling = config.VERIFYING_CEILING_SEC
        cases = [False, True]
        self.rng.shuffle(cases)
        conn = store.db()
        for canary in cases:
            with self.subTest(canary=canary):
                self.reset_observations()
                conn.execute("UPDATE tasks SET is_canary=?, updated_at=? "
                             "WHERE id=?", (int(canary), OLD_STAMP, self.TASK))
                conn.commit()
                before = store.now()
                text = self.run_pull_main()
                tag = f"зерно: {self.seed}; канарейка={canary}; вывод: {text!r}"
                resets = self.ceiling_resets()
                self.assertTrue(resets, tag)
                self.assertIn(self.TASK, [*resets[-1].args, *resets[-1].kwargs.values()],
                              tag)
                self.assertGreaterEqual(self.task()["updated_at"], before, tag)
                self.assertEqual(self.task()["state"], "verifying", tag)
        self.assertEqual(config.VERIFYING_CEILING_SEC, ceiling)

    def test_ac9_failed_push_keeps_ceiling_and_says_who_retries(self):
        """Отправка головы не удалась — потолок не сброшен, вывод называет повтор.

        Сценарий: подтяжка состоялась, `ensure_head_in_origin` вернул
        `(False, причина)`. `store.update_task` с `updated_at` не вызван,
        `updated_at` прежний, задача в `verifying`; вывод команды содержит
        `PULL_MAIN_PUSH_FAILED` и `PULL_MAIN_PUSH_RETRY`.

        Ловит мутацию: потолок сбрасывается независимо от итога отправки
        (первый элемент ответа `ensure_head_in_origin` не проверяется) —
        `update_task(updated_at=…)` вызван, `updated_at` сдвинут, хотя CI по
        голове, которой нет в origin, не придёт.
        """
        module = pull_main_module()
        self.assertEqual(module.PULL_MAIN_PUSH_FAILED,
                         "отправка головы в origin не удалась")
        self.assertEqual(module.PULL_MAIN_PUSH_RETRY,
                         "опрос verifying отправит голову сам")
        self.push.return_value = (
            False, f"push отклонён: {self.rng.randrange(1 << 20):x}")
        text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(len(self.merges()), 1, tag)
        self.push.assert_called_once()
        self.assertEqual(self.ceiling_resets(), [], tag)
        self.assertEqual(self.task()["updated_at"], OLD_STAMP, tag)
        self.assertEqual(self.task()["state"], "verifying", tag)
        self.assertIn(module.PULL_MAIN_PUSH_FAILED, text, tag)
        self.assertIn(module.PULL_MAIN_PUSH_RETRY, text, tag)

    def test_ac10_already_fresh_is_named_answer_without_effects(self):
        """main уже в ветке — именованный ответ без подтяжки и побочных действий.

        Сценарий: `rev-list --count` отвечает 0. Вывод содержит
        `PULL_MAIN_ALREADY_FRESH` («main уже в ветке»); записи
        `PULL_MAIN_ACTION` нет, `git merge` и отправки нет, `updated_at` не
        сдвинут, задача в `verifying`.

        Ловит мутацию: исход `"fresh"` обрабатывается как «подтянуто» —
        команда пишет запись подтяжки, отправляет голову и сбрасывает
        потолок, хотя в ветке ничего не изменилось.
        """
        module = pull_main_module()
        self.assertEqual(module.PULL_MAIN_ALREADY_FRESH, "main уже в ветке")
        self.behind = 0
        text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertIn(module.PULL_MAIN_ALREADY_FRESH, text, tag)
        self.assertEqual(self.merges(), [], tag)
        self.push.assert_not_called()
        self.assertEqual(self.git_pushes(), [], tag)
        self.assertEqual(self.ceiling_resets(), [], tag)
        self.assertEqual(self.task()["updated_at"], OLD_STAMP, tag)
        self.assertNotIn(module.PULL_MAIN_ACTION, self.actions(), tag)
        self.assertEqual(self.task()["state"], "verifying", tag)


class EscalationOutcomeTest(PullMainSandbox):

    def test_ac11_conflict_red_plank_and_missing_worktree_escalate(self):
        """Конфликт, красная планка и несозданная рабочая копия эскалируют задачу.

        Сценарий: три случая в случайном порядке, перед каждым задача снова
        в `verifying` — `git merge` с конфликтом содержимого; чистое слияние
        и красная планка; `workspace.ensure` вернул ошибку. Каждый раз
        задача в `escalated`, отправки головы нет, `store.update_task` с
        `updated_at` не вызван.

        Ловит мутацию: команда отправляет голову и сбрасывает потолок на
        любом исходе, кроме «main уже в ветке» (исход `"escalated"`
        обработан как «подтянуто») — `ensure_head_in_origin` вызван после
        эскалации.
        """
        cases = ["конфликт", "красная планка", "нет рабочей копии"]
        self.rng.shuffle(cases)
        for case in cases:
            with self.subTest(case=case):
                self.reset_observations()
                self.set_task_state("verifying")
                self.merge_conflict = case == "конфликт"
                self.plank_run.return_value = (
                    (False, "1 failed") if case == "красная планка"
                    else (True, "1 passed"))
                ensure = (lambda task_id, branch: (self.wt_path, "worktree add упал")
                          if case == "нет рабочей копии"
                          else (self.wt_path, None))
                with mock.patch.object(workspace, "ensure", ensure):
                    text = self.run_pull_main()
                tag = f"зерно: {self.seed}; {case}; вывод: {text!r}"
                self.assertEqual(self.task()["state"], "escalated", tag)
                self.push.assert_not_called()
                self.assertEqual(self.git_pushes(), [], tag)
                self.assertEqual(self.ceiling_resets(), [], tag)

    def test_ac12_conflict_from_verifying_is_marked_for_role_step(self):
        """Конфликт подтяжки из `verifying` метится признаком «нужен шаг роли».

        Сценарий: `verifying` входит в `pull.PULL_CONFLICT_MARKED_STATES`;
        команда на задаче в `verifying` ловит неразрешённый конфликт
        содержимого — задача в `escalated`, в журнале есть запись с
        действием `pull.PULL_CONFLICT_ROLE_STEP_MARKER`.

        Ловит мутацию: `verifying` вне набора `PULL_CONFLICT_MARKED_STATES`
        — эскалация из `verifying` уходит без метки, и `auto` после возврата
        повторяет ту же подтяжку вместо шага разработчика.
        """
        self.assertIn("verifying", pull.PULL_CONFLICT_MARKED_STATES)
        self.merge_conflict = True
        text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(self.task()["state"], "escalated", tag)
        self.assertIn(pull.PULL_CONFLICT_ROLE_STEP_MARKER, self.actions(), tag)

    def test_ac13_refusal_before_merge_is_named_refusal(self):
        """Отказ узла до слияния (посторонний файл) — именованный отказ команды.

        Сценарий: в индексе рабочей копии — файл вне зон задачи, чекпоинт
        перед подтяжкой отказывает, `git merge` не начинается. Команда
        отвечает непустым отказом; задача в `verifying`, отправки головы,
        записи `PULL_MAIN_ACTION` и сброса потолка нет.

        Ловит мутацию: исход `"refused"` до слияния обработан как
        «подтянуто» или как эскалация — команда пишет запись подтяжки и
        отправляет голову либо переводит задачу в `escalated`.
        """
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?",
                     ("orchestrator/allowed_zone.py", self.TASK))
        conn.commit()
        self.staged_stray = f"docs/stray-{self.rng.randrange(1 << 20):x}.md"
        text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertTrue(text.strip(), tag)
        self.assertEqual(self.merges(), [], tag)
        self.assertEqual(self.task()["state"], "verifying", tag)
        self.push.assert_not_called()
        self.assertEqual(self.ceiling_resets(), [], tag)
        self.assertNotIn(pull_main_module().PULL_MAIN_ACTION, self.actions(), tag)

    def test_ac13_refusal_after_merge_escalates_unverified_head(self):
        """Отказ узла после слияния (планки нет) — эскалация с названной причиной.

        Сценарий: SPEC задачи требует AC-разметку, а планки в источнике нет;
        слияние уже состоялось. Задача в `escalated`, журнал называет
        причину «голова после подтяжки не проверена планкой»; отправки
        головы и сброса потолка нет.

        Ловит мутацию: отказ после слияния обработан как отказ до слияния —
        задача остаётся в `verifying` с непроверенной планкой головой, и
        опрос CI уводит её дальше.
        """
        shutil.rmtree(self.tdir / "acceptance_tests")
        text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(len(self.merges()), 1, tag)
        self.assertEqual(self.task()["state"], "escalated", tag)
        journal_text = "\n".join(f"{row['action']} {row['detail'] or ''}"
                                 for row in self.journal())
        self.assertIn("голова после подтяжки не проверена планкой",
                      journal_text, tag)
        self.push.assert_not_called()
        self.assertEqual(self.ceiling_resets(), [], tag)


class RoleRefusalTest(PullMainSandbox):

    def test_ac14_role_process_is_refused_before_execution(self):
        """Процессу роли команда недоступна: отказ до исполнения.

        Сценарий: команда вызвана из окружения роли — с маркером роли
        (случайное имя) и с HOME дома роли без маркера. В обоих случаях
        диспетчер завершает вызов отказом о роли, а команда не исполняется:
        ни сверки отставания, ни `git merge`, ни записи подтяжки.

        Ловит мутацию: `pull-main` внесена в белый список команд роли
        (`artel._ROLE_ALLOWED_COMMANDS`) — под ролью команда подтягивает
        main в ветку задачи.
        """
        role = f"role_{self.rng.randrange(1 << 30):x}"
        variants = (
            ("маркер", {**self.operator_env(), config.ARTEL_ROLE_ENV: role}, role),
            ("HOME роли", {**self.operator_env(), "HOME": str(config.ROLE_HOME)},
             "окружение роли"),
        )
        for name, env, expected in variants:
            with self.subTest(variant=name):
                self.reset_observations()
                text = self.dispatch(("pull-main", self.TASK), env=env)
                tag = f"зерно: {self.seed}; {name}; вывод: {text!r}"
                self.assertIn(expected, text, tag)
                self.assertIn("pull-main", text, tag)
                self.assert_untouched(text, "verifying")


if __name__ == "__main__":
    unittest.main()
