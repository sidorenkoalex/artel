"""Отсоединённый `run`/`auto` и `observe register` без пары клиент/чат.

Группа: долгоживущий
Красен до реализации: разбор `run`/`auto` отказывает без `--client`/`--chat` и не знает флага `--observation`, `observe register` требует пару, выбор наблюдения идёт по паре.

Связка, которую держит файл: команда CLI (`artel.main` с `sys.argv`) —
БД пульта (`observations`, `observed_runs`, `steps`, `tasks`, `leases`) —
порождение дочернего процесса (`subprocess.Popen`, подменён: настоящий
цикл в тесте не идёт). Свежесть связи задаётся записью `last_seen_at`
наблюдения от `config.OBSERVATION_STALE_SECONDS`, а не ожиданием по
реальному времени. Наблюдения заводятся публичной командой `observe
register` (с парой — как прежние наблюдения, без пары — как новые).

Свойство проверяется на случайных входах (чат, клиент, pid, сдвиги
свежести); зерно печатается и входит в текст провала.
"""
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import artel, config, lease, store
from tests.sandbox import TaskSeededTmpRootTest, capture


class DetachedLaunchWithoutPairTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)

    # --- помощники сценария ---

    def msg(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def cli(self, *argv) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            return capture(artel.main)

    def register(self, *pair, tasks=None) -> str:
        out = self.cli("observe", "register", *pair, "--tasks", tasks or self.TASK)
        return json.loads(out)["id"]

    def set_seen(self, observation_id: str, age_seconds: float,
                 at: datetime | None = None) -> None:
        moment = (at or datetime.now(timezone.utc)) - timedelta(seconds=age_seconds)
        conn = store.db()
        with conn:
            conn.execute("UPDATE observations SET last_seen_at=? WHERE id=?",
                         (moment.isoformat(), observation_id))

    def set_created(self, observation_id: str, ago_seconds: float) -> None:
        moment = datetime.now(timezone.utc) - timedelta(seconds=ago_seconds)
        conn = store.db()
        with conn:
            conn.execute("UPDATE observations SET created_at=? WHERE id=?",
                         (moment.strftime("%Y-%m-%d %H:%M:%SZ"), observation_id))

    def fresh_age(self) -> float:
        return self.rnd.uniform(0, config.OBSERVATION_STALE_SECONDS * 0.4)

    def stale_age(self) -> float:
        return config.OBSERVATION_STALE_SECONDS + self.rnd.uniform(5, 600)

    def runs(self, observation_id: str) -> list:
        return [tuple(r) for r in store.observed_runs(store.db(), observation_id)]

    def launch(self, *argv):
        """Запуск с подменённым Popen: (popen-мок, pid)."""
        pid = self.rnd.randrange(10_000, 4_000_000)
        with mock.patch.object(artel.subprocess, "Popen",
                               return_value=mock.Mock(pid=pid)) as popen:
            self.cli(*argv)
        return popen, pid

    def refused(self, *argv) -> str:
        """Запуск, обязанный отказать до Popen: текст отказа."""
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit, msg=self.msg(f"нет отказа: {argv}")) as ctx:
                self.cli(*argv)
            popen.assert_not_called()
        return str(ctx.exception.code)

    # --- критерии ---

    def test_ac1_launch_without_pair_spawns_attach_child_and_records_run(self):
        """Одно свежее наблюдение без пары: `run`/`auto <id>` порождают ребёнка.

        Наблюдение заведено `observe register --tasks <id>` без пары, связь
        свежая. И `run`, и `auto` без `--client`/`--chat`/`--attach` зовут
        Popen ровно раз с командой, задачей и `--attach`, а `observed_runs`
        наблюдения получает строку с этой задачей и pid ребёнка.

        Ловит мутацию: разбор `run`/`auto` по-прежнему требует пару
        `--client`/`--chat` — вызов без пары отказывает, Popen не зовётся и
        строки в `observed_runs` нет; либо запуск не пишет `observed_runs`.
        """
        observation_id = self.register()
        self.set_seen(observation_id, self.fresh_age())
        for command in ("run", "auto"):
            with self.subTest(command=command, seed=self.seed):
                popen, pid = self.launch(command, self.TASK)
                self.assertEqual(popen.call_count, 1, self.msg("Popen не вызван"))
                child = [str(a) for a in popen.call_args[0][0]]
                for part in (command, self.TASK, "--attach"):
                    self.assertIn(part, child, self.msg(f"в команде ребёнка нет {part}: {child}"))
                self.assertIn(self.TASK, [r[0] for r in self.runs(observation_id)
                                          if r[1] == pid],
                              self.msg(f"observed_runs не записан: {self.runs(observation_id)}"))

    def test_ac2_stale_link_refuses_and_names_observation_and_watch(self):
        """Связь единственного наблюдения старше порога: отказ с ID и `watch`.

        Ловит мутацию: выбор наблюдения без пары пропускает гейт свежести
        (Popen вызван), либо отказ не называет ID наблюдения и команду
        `watch --observation <ID>` для перезапуска дозора.
        """
        observation_id = self.register()
        self.set_seen(observation_id, self.stale_age())
        for command in ("run", "auto"):
            with self.subTest(command=command, seed=self.seed):
                text = self.refused(command, self.TASK)
                self.assertIn(observation_id, text, self.msg(f"нет ID в отказе: {text}"))
                self.assertIn(f"watch --observation {observation_id}", text,
                              self.msg(f"нет команды watch в отказе: {text}"))
                self.assertEqual(self.runs(observation_id), [], self.msg("запуск записан"))

    def test_ac3_pair_is_audit_metadata_and_malformed_pair_refused(self):
        """Пара не выбирает наблюдение и попадает в журнал; кривая пара — отказ.

        Наблюдение заведено с парой. `auto` без пары, с совпадающей парой
        и с парой, не совпадающей ни с одним наблюдением, — все три
        запускают цикл в него; после запуска с чужой парой в журнале шагов
        задачи есть запись с её клиентом и чатом. Неполная или неверная по
        форме пара отказывает без Popen и у `run`, и у `auto`.

        Ловит мутацию: выбор наблюдения по-прежнему фильтрует по паре —
        запуск с чужой парой отказывает; либо пара запуска не пишется в
        журнал задачи; либо проверка формы пары снята — `--client` без
        `--chat` или клиент вне `codex|claude` порождает ребёнка.
        """
        own_client = self.rnd.choice(["codex", "claude"])
        own_chat = f"chat-{self.rnd.randrange(1 << 30)}"
        observation_id = self.register("--client", own_client, "--chat", own_chat)
        self.set_seen(observation_id, self.fresh_age())
        other_client = "claude" if own_client == "codex" else "codex"
        other_chat = f"foreign-{self.rnd.randrange(1 << 30)}"
        calls = ([], ["--client", own_client, "--chat", own_chat],
                 ["--client", other_client, "--chat", other_chat])
        for pair in calls:
            with self.subTest(pair=pair, seed=self.seed):
                popen, pid = self.launch("auto", self.TASK, *pair)
                self.assertEqual(popen.call_count, 1, self.msg(f"Popen не вызван: {pair}"))
                self.assertIn(pid, [r[1] for r in self.runs(observation_id)],
                              self.msg(f"запуск {pair} не в наблюдение {observation_id}"))
        rows = store.db().execute("SELECT * FROM steps WHERE task_id=?",
                                  (self.TASK,)).fetchall()
        texts = [" ".join(str(v) for v in tuple(r)) for r in rows]
        self.assertTrue(any(other_client in t and other_chat in t for t in texts),
                        self.msg(f"в журнале задачи нет записи с {other_client}/"
                                 f"{other_chat}: {texts}"))
        malformed = (["--client", other_client],
                     ["--chat", other_chat],
                     ["--client", other_client, "--chat", ""],
                     ["--client", "unknown", "--chat", other_chat])
        before = self.runs(observation_id)
        for command in ("run", "auto"):
            for pair in malformed:
                with self.subTest(command=command, pair=pair, seed=self.seed):
                    self.refused(command, self.TASK, *pair)
        self.assertEqual(self.runs(observation_id), before, self.msg("кривая пара записала запуск"))

    def test_ac4_freshest_then_latest_created_observation_is_chosen(self):
        """Два свежих наблюдения: выбор по `last_seen_at`, при равенстве — позднее созданное.

        Случай «свежее»: свежее то наблюдение, что создано РАНЬШЕ, — запуск
        записан только у него. Случай «равно»: одинаковый `last_seen_at` —
        запуск записан только у созданного позже. Между случаями пара
        прекращается `observe stop`.

        Ловит мутацию: порядок выбора по созданию (rowid/`created_at`) вместо
        `last_seen_at` — в первом случае запуск уходит в позднее созданное;
        либо при равной свежести берётся первое созданное; либо запуск
        пишется в оба наблюдения.
        """
        for case in ("свежее", "равно"):
            with self.subTest(case=case, seed=self.seed):
                earlier = self.register()
                later = self.register()
                self.set_created(earlier, 120)
                self.set_created(later, 30)
                if case == "свежее":
                    young = self.rnd.uniform(0, config.OBSERVATION_STALE_SECONDS * 0.2)
                    self.set_seen(earlier, young)
                    self.set_seen(later, young + self.rnd.uniform(
                        1, config.OBSERVATION_STALE_SECONDS * 0.5))
                    winner, loser = earlier, later
                else:
                    at = datetime.now(timezone.utc)
                    age = self.fresh_age()
                    self.set_seen(earlier, age, at)
                    self.set_seen(later, age, at)
                    winner, loser = later, earlier
                command = self.rnd.choice(["run", "auto"])
                _, pid = self.launch(command, self.TASK)
                self.assertEqual([r[1] for r in self.runs(winner)], [pid],
                                 self.msg(f"{case}: запуск не в {winner}"))
                self.assertEqual(self.runs(loser), [],
                                 self.msg(f"{case}: запуск записан и в {loser}"))
                self.cli("observe", "stop", earlier)
                self.cli("observe", "stop", later)

    def test_ac5_named_observation_wins_over_fresher_one(self):
        """`--observation <ID>` ведёт запуск в названное, хоть другое свежее.

        Ловит мутацию: флаг `--observation` разобран, но выбор всё равно
        берёт самое свежее наблюдение — запуск записан не в названное.
        """
        named, other = self.register(), self.register()
        if self.rnd.random() < 0.5:
            named, other = other, named
        older = self.rnd.uniform(config.OBSERVATION_STALE_SECONDS * 0.5,
                                 config.OBSERVATION_STALE_SECONDS * 0.9)
        self.set_seen(named, older)
        self.set_seen(other, self.rnd.uniform(0, config.OBSERVATION_STALE_SECONDS * 0.3))
        for command in ("run", "auto"):
            with self.subTest(command=command, seed=self.seed):
                _, pid = self.launch(command, self.TASK, "--observation", named)
                self.assertIn(pid, [r[1] for r in self.runs(named)],
                              self.msg(f"запуск не в названное {named}"))
        self.assertEqual(self.runs(other), [], self.msg("запуск записан в неназванное"))

    def test_ac6_named_stale_observation_refused_despite_fresh_other(self):
        """Названное наблюдение со старой связью — отказ, хоть есть свежее.

        Ловит мутацию: при устаревшем названном наблюдении запуск
        откатывается на другое свежее (Popen вызван), либо отказ не
        называет ID названного наблюдения.
        """
        named, other = self.register(), self.register()
        self.set_seen(named, self.stale_age())
        self.set_seen(other, self.fresh_age())
        for command in ("run", "auto"):
            with self.subTest(command=command, seed=self.seed):
                text = self.refused(command, self.TASK, "--observation", named)
                self.assertIn(named, text, self.msg(f"нет ID в отказе: {text}"))
        self.assertEqual(self.runs(named) + self.runs(other), [],
                         self.msg("отказавший запуск записан"))

    def test_ac7_register_without_pair_stores_empty_strings(self):
        """`observe register --tasks <id>` без пары — пустые клиент и чат.

        Ловит мутацию: `observe register` по-прежнему требует пару и
        отказывает; либо отсутствие пары пишется не пустой строкой
        (заглушка/NULL), и `observe show` отдаёт иное значение.
        """
        observation_id = self.register()
        row = store.db().execute("SELECT client, chat FROM observations WHERE id=?",
                                 (observation_id,)).fetchone()
        self.assertEqual((row["client"], row["chat"]), ("", ""),
                         self.msg(f"в БД не пустая пара: {tuple(row)}"))
        shown = json.loads(self.cli("observe", "show", observation_id, "--json"))
        self.assertEqual(shown["id"], observation_id, self.msg("show: чужой id"))
        self.assertEqual((shown["client"], shown["chat"]), ("", ""),
                         self.msg(f"show: не пустая пара: {shown}"))

    def test_ac8_observation_with_pair_is_shown_and_chosen_without_pair(self):
        """Наблюдение с парой читается с ней и выбирается запуском без пары.

        Рядом — наблюдение без пары с менее свежей связью: запуск без пары
        уходит в наблюдение с парой (оно свежее).

        Ловит мутацию: выбор без пары отбрасывает наблюдения с непустой
        парой (берёт только пустую) — запуск уходит в менее свежее
        наблюдение без пары; либо `observe show` теряет пару.
        """
        client = self.rnd.choice(["codex", "claude"])
        chat = f"chat-{self.rnd.randrange(1 << 30)}"
        paired = self.register("--client", client, "--chat", chat)
        bare = self.register()
        shown = json.loads(self.cli("observe", "show", paired, "--json"))
        self.assertEqual((shown["client"], shown["chat"]), (client, chat),
                         self.msg(f"show потерял пару: {shown}"))
        young = self.rnd.uniform(0, config.OBSERVATION_STALE_SECONDS * 0.2)
        self.set_seen(paired, young)
        self.set_seen(bare, young + self.rnd.uniform(1, config.OBSERVATION_STALE_SECONDS * 0.5))
        _, pid = self.launch(self.rnd.choice(["run", "auto"]), self.TASK)
        self.assertEqual([r[1] for r in self.runs(paired)], [pid],
                         self.msg("запуск не в наблюдение с парой"))
        self.assertEqual(self.runs(bare), [], self.msg("запуск в менее свежее"))

    def test_ac10_refused_launch_keeps_task_state_and_leases(self):
        """Отказы (нет наблюдения, старая связь, названное не найдено) ничего не меняют.

        У другой задачи заранее взят lease — таблица `leases` не пуста.
        После каждого отказа `tasks.state` задачи и вся таблица `leases`
        совпадают со снимком до вызова.

        Ловит мутацию: lease задачи берётся (или состояние задачи
        меняется) до проверки наблюдения — отказ оставляет строку
        `leases` либо иной `tasks.state`.
        """
        other = "T002"
        conn = store.db()
        store.insert_task(conn, other, "Другая", "in_dev", "task/t002",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        refusal, _ = lease.acquire(conn, other, f"session-{self.rnd.randrange(1 << 20)}")
        self.assertIsNone(refusal, self.msg("lease другой задачи не взят"))

        def snapshot():
            db = store.db()
            return (db.execute("SELECT state FROM tasks WHERE id=?",
                               (self.TASK,)).fetchone()[0],
                    [tuple(r) for r in db.execute(
                        "SELECT * FROM leases ORDER BY task_id")])

        def no_observation():
            return []

        def stale():
            observation_id = self.register()
            self.set_seen(observation_id, self.stale_age())
            return []

        def missing():
            observation_id = self.register()
            self.set_seen(observation_id, self.fresh_age())
            return ["--observation", f"absent{self.rnd.randrange(1 << 40):x}"]

        for name, prepare in (("нет наблюдения", no_observation),
                              ("старая связь", stale),
                              ("названное не найдено", missing)):
            extra = prepare()
            for command in ("run", "auto"):
                with self.subTest(case=name, command=command, seed=self.seed):
                    before = snapshot()
                    self.refused(command, self.TASK, *extra)
                    self.assertEqual(snapshot(), before,
                                     self.msg(f"{name}: состояние или leases изменены"))
            for row in store.db().execute("SELECT id FROM observations WHERE state='active'"):
                self.cli("observe", "stop", row[0])
