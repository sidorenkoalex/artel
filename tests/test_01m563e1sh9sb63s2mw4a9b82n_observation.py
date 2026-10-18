"""Одно наблюдение на задачи разных проектов: `observe`, `watch`,
`observe events`, `run`/`auto` с наблюдением и без.

Группа: долгоживущий
Красен до реализации: `observe register|add` отказывает задаче другого проекта, фильтр алертов дозора не знает проектов задач набора и проекта артели, `run --observation` сверяет проект наблюдения с проектом задачи, отказ без флага не называет `--observation <ID>`; тесты AC-5 и первая часть AC-6 зелены и до правки — они держат прежнее поведение однопроектного наблюдения.

Связка, которую держат тесты: команда CLI (`artel.main`) — таблицы
наблюдений и журнала в БД песочницы — вывод дозора/событий. Внешний
проект, третий проект и маркеры событий выбираются случайно при каждом
запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import json
import os
import random
import sys
from unittest import mock

from orchestrator import artel, config, session, store, watch
from tests.sandbox import TaskSeededTmpRootTest, capture, patch_sleep

PROJECT_NAMES = ("sled", "zubr", "kedr", "luna", "brod", "volna", "sosna")


class _MixedObservationBase(TaskSeededTmpRootTest):
    """Песочница: задача артели `self.TASK` (T001) и задача внешнего
    проекта `self.EXT` (T002, id сортируется после T001)."""

    EXT = "T002"

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        self.ext_project, self.third_project = rng.sample(PROJECT_NAMES, 2)
        self.mark = f"m{rng.randrange(1 << 30)}"
        self.conn = store.db()
        self.add_task(self.EXT, self.ext_project)

    def add_task(self, task_id: str, target: str) -> None:
        store.insert_task(self.conn, task_id, f"Задача {task_id}", "in_dev",
                          f"task/{task_id.lower()}", target, 25.0)

    def msg(self, *parts) -> str:
        return f"зерно {self.seed}: " + " ".join(str(p) for p in parts)

    def cli(self, *argv) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            return capture(artel.main)

    def refused(self, *argv) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            with self.assertRaises(SystemExit, msg=self.msg(argv)) as ctx:
                capture(artel.main)
        return str(ctx.exception.code)

    def register(self, tasks: str, project: str | None = None) -> str:
        argv = ["observe", "register", "--tasks", tasks]
        if project is not None:
            argv += ["--project", project]
        return json.loads(self.cli(*argv))["id"]

    def show(self, observation_id: str) -> dict:
        return json.loads(self.cli("observe", "show", observation_id, "--json"))

    def observation_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    def alert(self, target: str, label: str) -> str:
        message = f"{self.mark}-{label}"
        store.insert_alert(self.conn, target, "incident", "test", message)
        return message

    def step(self, task_id: str, label: str) -> str:
        detail = f"{self.mark}-{label}"
        store.journal(self.conn, task_id, "fsm", "state -> review", detail)
        return detail

    def watch_output(self, observation_id: str) -> str:
        """Одна итерация `watch --observation`: пауза цикла обрывает его."""
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation",
                                             observation_id]), \
                patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))), \
                contextlib.redirect_stdout(out):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                artel.main()
        return out.getvalue()

    def events_output(self, observation_id: str) -> str:
        return self.cli("observe", "events", observation_id)


class ObserveRegisterAddTest(_MixedObservationBase):

    def test_ac1_register_accepts_tasks_of_two_projects(self):
        """Регистрация задачи артели вместе с задачей внешнего проекта.

        Сценарий: `observe register --tasks T001,T002`, где T002 — задача
        случайного внешнего проекта; `observe show` видит обе задачи.
        Ловит мутацию: проверка «задача принадлежит другому проекту» в
        разборе `--tasks` оставлена — register выходит с отказом, и
        наблюдение не создаётся.
        """
        observation_id = self.register(f"{self.TASK},{self.EXT}")
        self.assertCountEqual(self.show(observation_id)["tasks"],
                              [self.TASK, self.EXT], self.msg())

    def test_ac1_unknown_task_refused_without_side_effects(self):
        """Несуществующая задача в `--tasks` — отказ без изменения состояния.

        Сценарий: register смешанного набора с лишним T999 — отказ, число
        наблюдений прежнее; add T999 к смешанному наблюдению — отказ,
        набор прежний.
        Ловит мутацию: вместе с проверкой проекта снята проверка
        существования задачи — register создаёт наблюдение с T999, либо
        add дописывает T999 в набор.
        """
        before = self.observation_count()
        self.refused("observe", "register", "--tasks",
                     f"{self.TASK},{self.EXT},T999")
        self.assertEqual(self.observation_count(), before, self.msg())
        observation_id = self.register(f"{self.TASK},{self.EXT}")
        self.refused("observe", "add", observation_id, "--tasks", "T999")
        self.assertCountEqual(self.show(observation_id)["tasks"],
                              [self.TASK, self.EXT], self.msg())

    def test_ac2_add_and_remove_across_projects(self):
        """Задача внешнего проекта — в наблюдение артели, задача артели —
        в наблюдение внешнего проекта; remove убирает каждую.

        Ловит мутацию: `observe add|remove` по-прежнему сверяет проект
        задачи с проектом наблюдения — add выходит с отказом, задача в
        набор не попадает.
        """
        cases = ((self.TASK, self.EXT), (self.EXT, self.TASK))
        for owner, guest in cases:
            with self.subTest(owner=owner, guest=guest, seed=self.seed):
                observation_id = self.register(owner)
                self.cli("observe", "add", observation_id, "--tasks", guest)
                self.assertCountEqual(self.show(observation_id)["tasks"],
                                      [owner, guest], self.msg(owner, guest))
                self.cli("observe", "remove", observation_id, "--tasks", guest)
                self.assertEqual(self.show(observation_id)["tasks"], [owner],
                                 self.msg(owner, guest))

    def test_ac3_default_project_is_first_listed_task(self):
        """Без `--project` проект наблюдения — проект первой задачи в
        `--tasks`, а не задачи с наименьшим id.

        Сценарий: `--tasks T002,T001` (внешняя первой, её id сортируется
        после T001) — проект наблюдения внешний.
        Ловит мутацию: проект берётся у первой задачи отсортированного
        набора — наблюдение получает проект артели.
        """
        observation_id = self.register(f"{self.EXT},{self.TASK}")
        self.assertEqual(self.show(observation_id)["project"], self.ext_project,
                         self.msg())

    def test_ac3_explicit_project_any_order(self):
        """`--project P`, где хотя бы одна задача набора из P, — проект P
        при любом порядке `--tasks`.

        Ловит мутацию: `--project` сверяется с проектом первой задачи
        (отказ при другом порядке) или игнорируется (проект первой задачи
        вместо P).
        """
        orders = (f"{self.TASK},{self.EXT}", f"{self.EXT},{self.TASK}")
        for project in (config.DEFAULT_TARGET, self.ext_project):
            for tasks in orders:
                with self.subTest(project=project, tasks=tasks, seed=self.seed):
                    observation_id = self.register(tasks, project)
                    self.assertEqual(self.show(observation_id)["project"], project,
                                     self.msg(project, tasks))

    def test_ac3_project_without_tasks_refused(self):
        """`--project Q`, где ни одна задача набора не из Q, — отказ, и
        наблюдение не создаётся.

        Ловит мутацию: проверка «хотя бы одна задача из P» снята вместе со
        сверкой с первой задачей — наблюдение создаётся с чужим проектом Q.
        """
        before = self.observation_count()
        for tasks in (f"{self.TASK},{self.EXT}", f"{self.EXT},{self.TASK}"):
            with self.subTest(tasks=tasks, seed=self.seed):
                self.refused("observe", "register", "--tasks", tasks,
                             "--project", self.third_project)
                self.assertEqual(self.observation_count(), before, self.msg(tasks))


class WatchMixedObservationTest(_MixedObservationBase):

    def test_ac4_watch_shows_steps_and_alerts_of_both_projects(self):
        """Дозор смешанного наблюдения выводит события шагов обеих задач,
        алерты id внешней задачи, её проекта и проекта артели; алерт
        третьего проекта — нет.

        Сценарий проверяется при обоих порядках `--tasks` (проект
        наблюдения — артель либо внешний).
        Ловит мутацию: фильтр алертов дозора пропускает только id задач
        набора и проект наблюдения — алерт проекта внешней задачи (при
        наблюдении артели) или алерт артели (при наблюдении внешнего
        проекта) пропадает из вывода; либо фильтр снят — алерт третьего
        проекта выводится.
        """
        for tasks in (f"{self.TASK},{self.EXT}", f"{self.EXT},{self.TASK}"):
            with self.subTest(tasks=tasks, seed=self.seed):
                observation_id = self.register(tasks)
                tag = tasks.replace(",", "-")
                shown = [self.step(self.TASK, f"{tag}-step-artel"),
                         self.step(self.EXT, f"{tag}-step-ext"),
                         self.alert(self.EXT, f"{tag}-alert-task"),
                         self.alert(self.ext_project, f"{tag}-alert-project"),
                         self.alert(config.DEFAULT_TARGET, f"{tag}-alert-artel")]
                hidden = self.alert(self.third_project, f"{tag}-alert-third")
                out = self.watch_output(observation_id)
                for text in shown:
                    self.assertIn(text, out, self.msg(text, out))
                self.assertNotIn(hidden, out, self.msg(out))

    def test_ac4_observation_project_alerts_survive_removal(self):
        """Наблюдение проекта P после `observe remove` задачи P держит
        только задачу артели и всё равно выводит алерт с `target` = P.

        Ловит мутацию: из фильтра алертов выпала ветка «проект
        наблюдения» (остались проекты задач набора и артель) — алерт P
        после удаления последней задачи P пропадает.
        """
        observation_id = self.register(f"{self.TASK},{self.EXT}", self.ext_project)
        self.cli("observe", "remove", observation_id, "--tasks", self.EXT)
        self.assertEqual(self.show(observation_id)["tasks"], [self.TASK], self.msg())
        message = self.alert(self.ext_project, "alert-project")
        self.assertIn(message, self.watch_output(observation_id), self.msg())

    def test_ac10_observe_events_filters_alerts_like_watch(self):
        """`observe events` смешанного наблюдения выводит алерт проекта
        внешней задачи и алерт артели, но не алерт третьего проекта.

        Сценарий проверяется при обоих порядках `--tasks`.
        Ловит мутацию: правка фильтра сделана только в цикле `watch`, а
        `observe events` читает алерты прежним правилом — алерт проекта
        внешней задачи или артели пропадает из вывода `events`.
        """
        for tasks in (f"{self.TASK},{self.EXT}", f"{self.EXT},{self.TASK}"):
            with self.subTest(tasks=tasks, seed=self.seed):
                observation_id = self.register(tasks)
                tag = tasks.replace(",", "-")
                shown = [self.alert(self.ext_project, f"{tag}-alert-project"),
                         self.alert(config.DEFAULT_TARGET, f"{tag}-alert-artel")]
                hidden = self.alert(self.third_project, f"{tag}-alert-third")
                out = self.events_output(observation_id)
                for text in shown:
                    self.assertIn(text, out, self.msg(text, out))
                self.assertNotIn(hidden, out, self.msg(out))


class WatchSingleProjectTest(_MixedObservationBase):

    def test_ac5_artel_only_observation_unchanged(self):
        """Наблюдение только задач артели: проект и набор у register/add,
        события шагов и алерты дозора — прежние.

        Сценарий: register T001,T003 и add T004 (все артели); дозор
        выводит шаг задачи набора, алерт с id задачи и алерт артели, не
        выводит шаг внешней задачи вне набора и алерт третьего проекта.
        Ловит мутацию: новая выборка алертов теряет ветку «id задачи
        набора» или начинает пропускать любой проект; либо проект
        наблюдения по умолчанию перестаёт быть проектом задач.
        """
        self.add_task("T003", config.DEFAULT_TARGET)
        self.add_task("T004", config.DEFAULT_TARGET)
        observation_id = self.register(f"{self.TASK},T003")
        self.cli("observe", "add", observation_id, "--tasks", "T004")
        shown_obs = self.show(observation_id)
        self.assertEqual(shown_obs["project"], config.DEFAULT_TARGET, self.msg())
        self.assertCountEqual(shown_obs["tasks"], [self.TASK, "T003", "T004"],
                              self.msg())
        shown = [self.step(self.TASK, "step-artel"),
                 self.alert(self.TASK, "alert-task"),
                 self.alert(config.DEFAULT_TARGET, "alert-artel")]
        hidden = [self.step(self.EXT, "step-outside"),
                  self.alert(self.third_project, "alert-third")]
        out = self.watch_output(observation_id)
        for text in shown:
            self.assertIn(text, out, self.msg(text, out))
        for text in hidden:
            self.assertNotIn(text, out, self.msg(text, out))

    def test_ac6_external_only_observation_keeps_own_events(self):
        """Наблюдение только задач внешнего проекта: прежние события шагов
        и алерты своего проекта и своей задачи; алерт третьего проекта —
        нет.

        Ловит мутацию: фильтр алертов перестаёт сравнивать с проектом
        наблюдения или с id задачи — алерт своего проекта/задачи
        пропадает; либо фильтр пропускает любой `target` — выводится
        алерт третьего проекта.
        """
        self.add_task("T005", self.ext_project)
        observation_id = self.register(f"{self.EXT},T005")
        self.assertEqual(self.show(observation_id)["project"], self.ext_project,
                         self.msg())
        shown = [self.step(self.EXT, "step-ext"),
                 self.step("T005", "step-ext2"),
                 self.alert(self.EXT, "alert-task"),
                 self.alert(self.ext_project, "alert-project")]
        hidden = [self.step(self.TASK, "step-outside"),
                  self.alert(self.third_project, "alert-third")]
        out = self.watch_output(observation_id)
        for text in shown:
            self.assertIn(text, out, self.msg(text, out))
        for text in hidden:
            self.assertNotIn(text, out, self.msg(text, out))

    def test_ac6_external_only_observation_shows_artel_alerts(self):
        """Наблюдение только задач внешнего проекта выводит алерт проекта
        артели (алерт уровня пульта).

        Ловит мутацию: в фильтре алертов нет ветки `config.DEFAULT_TARGET`
        — алерт стоп-крана волны, заведённый на артель, наблюдению
        внешнего проекта не виден.
        """
        self.add_task("T005", self.ext_project)
        observation_id = self.register(f"{self.EXT},T005")
        message = self.alert(config.DEFAULT_TARGET, "alert-artel")
        self.assertIn(message, self.watch_output(observation_id), self.msg())


class LaunchWithObservationTest(_MixedObservationBase):

    def launch(self, command: str, task_id: str, *extra) -> tuple:
        """`run|auto` отвязанно: (SystemExit или None, мок Popen)."""
        with mock.patch.object(sys, "argv", ["artel.py", command, task_id, *extra]), \
                mock.patch.object(artel.subprocess, "Popen",
                                  return_value=mock.Mock(pid=40000)) as popen:
            try:
                capture(artel.main)
            except SystemExit as exc:
                return exc, popen
        return None, popen

    def fresh(self, target: str, tasks: list, session_id: str | None = None) -> str:
        observation_id = store.register_observation(
            self.conn, target, "", "", session_id or session.resolve_session_id(None),
            tasks)
        store.touch_observation(self.conn, observation_id)
        return observation_id

    def test_ac7_launch_accepts_task_of_other_project(self):
        """`run|auto <id> --observation <ID>` идёт, когда проект задачи не
        совпадает с проектом наблюдения (в обе стороны).

        Ловит мутацию: в `_launch_observation` оставлена сверка проекта
        наблюдения с проектом задачи — запуск выходит с отказом «другой
        сессии или проекту», Popen не вызван.
        """
        cases = ((self.EXT, config.DEFAULT_TARGET),
                 (self.TASK, self.ext_project))
        for task_id, project in cases:
            observation_id = self.fresh(project, [self.TASK, self.EXT])
            for command in ("run", "auto"):
                with self.subTest(task=task_id, command=command, seed=self.seed):
                    refusal, popen = self.launch(command, task_id,
                                                 "--observation", observation_id)
                    self.assertIsNone(refusal, self.msg(refusal))
                    popen.assert_called_once()

    def test_ac7_other_refusals_kept(self):
        """Наблюдение другой сессии, неактивное и задача вне набора —
        по-прежнему отказ до запуска; отказ чужой сессии называет
        «другой сессии».

        Ловит мутацию: вместе со сверкой проекта снята сверка сессии,
        активности или членства — Popen вызван для чужого, прекращённого
        наблюдения либо для задачи вне набора.
        """
        foreign = self.fresh(config.DEFAULT_TARGET, [self.TASK, self.EXT],
                             session_id="other-session")
        stopped = self.fresh(config.DEFAULT_TARGET, [self.TASK, self.EXT])
        store.stop_observation(self.conn, stopped)
        without = self.fresh(config.DEFAULT_TARGET, [self.TASK])
        cases = ((foreign, "другой сессии"), (stopped, None), (without, None))
        for command in ("run", "auto"):
            for observation_id, phrase in cases:
                with self.subTest(command=command, observation=observation_id,
                                  seed=self.seed):
                    refusal, popen = self.launch(command, self.EXT,
                                                 "--observation", observation_id)
                    self.assertIsNotNone(refusal, self.msg(observation_id))
                    popen.assert_not_called()
                    if phrase:
                        self.assertIn(phrase, str(refusal.code), self.msg())

    def test_ac11_refusal_without_flag_names_observation(self):
        """Задача внешнего проекта стоит в активном наблюдении артели
        текущей сессии, наблюдения её проекта нет: отказ `run|auto` без
        флага называет `--observation <ID>` и не советует `observe add`.

        Задача вне всех наблюдений получает прежний совет
        `observe register --tasks <id>` и `observe add <ID> --tasks <id>`.
        Ловит мутацию: отказ без флага не ищет задачу в наблюдениях
        сессии вне её проекта — по-прежнему советует `observe add`; либо
        новый совет выдаётся и задаче вне всех наблюдений.
        """
        observation_id = self.fresh(config.DEFAULT_TARGET, [self.TASK, self.EXT])
        self.add_task("T006", self.ext_project)
        for command in ("run", "auto"):
            with self.subTest(command=command, task=self.EXT, seed=self.seed):
                refusal, popen = self.launch(command, self.EXT)
                self.assertIsNotNone(refusal, self.msg())
                popen.assert_not_called()
                text = str(refusal.code)
                self.assertIn(f"--observation {observation_id}", text, self.msg(text))
                self.assertNotIn("observe add", text, self.msg(text))
            with self.subTest(command=command, task="T006", seed=self.seed):
                refusal, popen = self.launch(command, "T006")
                self.assertIsNotNone(refusal, self.msg())
                popen.assert_not_called()
                text = str(refusal.code)
                self.assertIn("observe register --tasks T006", text, self.msg(text))
                self.assertIn("observe add <ID> --tasks T006", text, self.msg(text))
