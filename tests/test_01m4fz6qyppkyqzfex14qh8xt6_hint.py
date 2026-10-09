"""Подсказка запуска и строка перезапуска `pin-update` — одна форма с `--observation`.

Группа: долгоживущий
Красен до реализации: `launch_hint` и `cycle_command` печатают `--client <клиент> --chat <чат>`, а не `--observation <ID>`; без наблюдения подсказка подставляет заглушки пары.

Подсказка (`cycle_hint.launch_hint`) только читает БД — проверяется
модульно на песочнице БД без git. Строка перезапуска `pin-update` —
`doctor.stale_cycle_lines` над `doctor.stale_cycles`: ровно эти строки
`pin-update` печатает и пишет в журнал. Живой «цикл» — сам процесс теста:
lease задачи взят `lease.acquire` (pid и хост этого процесса), момент
пина — в будущем, так что процесс стартовал раньше него. Наблюдаемость
цикла — строка `observed_runs` с его задачей и pid.

Наблюдения заводятся с непустой случайной парой клиент/чат: форма
подсказки не должна её печатать. Зерно печатается и входит в текст
провала.
"""
import os
import random
from datetime import datetime, timedelta, timezone

from orchestrator import config, cycle_hint, doctor, lease, session, store
from tests.sandbox import TaskSeededTmpRootTest


class LaunchFormTest(TaskSeededTmpRootTest):

    OTHER = "T002"

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        store.insert_task(store.db(), self.OTHER, "Другая", "in_dev", "task/t002",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def msg(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def observe(self, tasks: list) -> tuple:
        client = self.rnd.choice(["codex", "claude"])
        chat = f"chat-{self.rnd.randrange(1 << 30)}"
        conn = store.db()
        observation_id = store.register_observation(
            conn, config.DEFAULT_TARGET, client, chat,
            session.resolve_session_id(None), tasks)
        store.touch_observation(conn, observation_id)
        return observation_id, client, chat

    def assert_no_pair(self, text: str, where: str) -> None:
        for flag in ("--client", "--chat"):
            self.assertNotIn(flag, text, self.msg(f"{where}: есть {flag}:\n{text}"))

    def test_ac9_launch_hint_uses_observation_id_and_observe_add(self):
        """Подсказка: `--observation <ID>` при наблюдении, голая строка без него.

        Четыре состояния БД: нет наблюдения; задача включена в наблюдение;
        задача выключена в нём (`disable_task_observation`); задачи нет в
        наборе (наблюдение только на другую задачу). Первая строка — ровно
        `artel.py <cmd> <id> --observation <ID>` либо `artel.py <cmd> <id>`;
        `--client`/`--chat` нет ни в одной строке подсказки; при
        выключенной или отсутствующей задаче есть `observe add <ID> --tasks <id>`.

        Ловит мутацию: подсказка по-прежнему печатает пару клиент/чат
        выбранного наблюдения (или заглушку `codex|claude` без него)
        вместо `--observation <ID>`; либо теряет шаг `observe add` для
        задачи вне набора.
        """
        cases = ("нет наблюдения", "включена", "выключена", "нет в наборе")
        for case in cases:
            with self.subTest(case=case, seed=self.seed):
                conn = store.db()
                for row in conn.execute("SELECT id FROM observations WHERE state='active'"):
                    store.stop_observation(conn, row[0])
                observation_id = None
                if case in ("включена", "выключена"):
                    observation_id, _, _ = self.observe([self.TASK])
                    if case == "выключена":
                        store.disable_task_observation(conn, self.TASK)
                elif case == "нет в наборе":
                    observation_id, _, _ = self.observe([self.OTHER])
                for cmd in ("run", "auto"):
                    hint = cycle_hint.launch_hint(store.db(), self.TASK, cmd)
                    text = "\n".join(hint)
                    expected = (f"artel.py {cmd} {self.TASK}" if observation_id is None
                                else f"artel.py {cmd} {self.TASK} --observation {observation_id}")
                    self.assertEqual(hint[0], expected, self.msg(f"{case}/{cmd}:\n{text}"))
                    self.assert_no_pair(text, f"{case}/{cmd}")
                    first = cycle_hint.launch_text(store.db(), self.TASK, cmd).splitlines()[0]
                    self.assertEqual(first, expected, self.msg(f"launch_text {case}/{cmd}"))
                    if case in ("выключена", "нет в наборе"):
                        self.assertIn(f"observe add {observation_id} --tasks {self.TASK}",
                                      text, self.msg(f"{case}/{cmd}: нет observe add:\n{text}"))

    def test_ac9_cycle_command_has_observation_form(self):
        """`cycle_command` с ID наблюдения и без него — одна форма с подсказкой.

        Ловит мутацию: `cycle_command` по-прежнему ждёт пару клиент/чат и
        печатает `--client`/`--chat` (или игнорирует ID наблюдения) —
        строка расходится с `artel.py <cmd> <id> --observation <ID>`.
        """
        for _ in range(5):
            cmd = self.rnd.choice(["run", "auto"])
            task_id = f"T{self.rnd.randrange(1, 1000):03d}"
            observation_id = f"{self.rnd.randrange(1 << 64):016x}"
            with self.subTest(cmd=cmd, task=task_id, seed=self.seed):
                self.assertEqual(cycle_hint.cycle_command(cmd, task_id, observation_id),
                                 f"artel.py {cmd} {task_id} --observation {observation_id}",
                                 self.msg("форма с наблюдением"))
                self.assertEqual(cycle_hint.cycle_command(cmd, task_id),
                                 f"artel.py {cmd} {task_id}", self.msg("форма без наблюдения"))

    def test_ac9_pin_update_restart_line_names_observation(self):
        """Строки перезапуска `pin-update`: наблюдаемый цикл — с ID, другой — голый.

        Две задачи с lease этого процесса; у первой строка `observed_runs`
        с её задачей и pid этого процесса, у второй — нет. В строке первой
        — `auto <id> --observation <ID>`, строка второй кончается на
        `auto <id>`; `--client`/`--chat` нет ни в одной строке.

        Ловит мутацию: строка перезапуска всё ещё берёт клиент/чат
        наблюдения (`--client … --chat …`) вместо его ID; либо наблюдаемый
        цикл получает голый `auto <id>`, неотличимый от ненаблюдаемого.
        """
        conn = store.db()
        observation_id, _, _ = self.observe([self.TASK])
        holder = f"session-{self.rnd.randrange(1 << 20)}"
        for task_id in (self.TASK, self.OTHER):
            refusal, _ = lease.acquire(conn, task_id, holder)
            self.assertIsNone(refusal, self.msg(f"lease {task_id} не взят"))
        store.record_observed_run(conn, observation_id, self.TASK, os.getpid(),
                                  str(config.LOGS / "run.log"))
        cycles = doctor.stale_cycles(conn, datetime.now(timezone.utc) + timedelta(days=1))
        lines = doctor.stale_cycle_lines(cycles)
        text = "\n".join(lines)
        observed = [line for line in lines if f"artel.py auto {self.TASK}" in line]
        plain = [line for line in lines if f"artel.py auto {self.OTHER}" in line]
        self.assertEqual(len(observed), 1, self.msg(f"нет строки {self.TASK}:\n{text}"))
        self.assertEqual(len(plain), 1, self.msg(f"нет строки {self.OTHER}:\n{text}"))
        self.assertTrue(observed[0].endswith(
            f"artel.py auto {self.TASK} --observation {observation_id}"),
            self.msg(f"наблюдаемый цикл:\n{text}"))
        self.assertTrue(plain[0].endswith(f"artel.py auto {self.OTHER}"),
                        self.msg(f"ненаблюдаемый цикл:\n{text}"))
        self.assert_no_pair(text, "pin-update")
