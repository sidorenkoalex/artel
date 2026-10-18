"""Алерт уровня пульта (`target` NULL) в дозоре наблюдения и в
`observe events`.

Группа: долгоживущий
Красен до реализации: фильтр алертов дозора наблюдения не пропускает `target` NULL — алерт не выводится ни одним наблюдением, ни `observe events`, поэтому и поля проекта `-` в его строке нет.

Связка: команда CLI (`artel.main`: `observe register`, `watch
--observation`, `observe events`) — таблицы наблюдений и алертов в БД
песочницы — вывод дозора. Внешний проект, маркер сообщения, источник и
число циклов дозора выбираются случайно при каждом запуске; зерно
печатается и входит в текст провала.
"""
import contextlib
import io
import json
import os
import random
import sys
from unittest import mock

from orchestrator import artel, config, store, watch
from tests.sandbox import TaskSeededTmpRootTest, capture, patch_sleep

PROJECT_NAMES = ("sled", "zubr", "kedr", "luna", "brod", "volna", "sosna")


class _NullAlertBase(TaskSeededTmpRootTest):
    """Задача артели `self.TASK` (T001) и задача внешнего проекта T002;
    наблюдение артели — на T001, наблюдение внешнего проекта — на T002."""

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
        self.rng = random.Random(self.seed)
        self.project = self.rng.choice(PROJECT_NAMES)
        self.mark = f"m{self.rng.randrange(1 << 30)}"
        self.source = f"src{self.rng.randrange(1 << 20)}"
        self.conn = store.db()
        store.insert_task(self.conn, self.EXT, "Внешняя", "in_dev", "task/t002",
                          self.project, 25.0)
        self.obs_artel = self.register(self.TASK)
        self.obs_ext = self.register(self.EXT)

    def msg(self, *parts) -> str:
        return f"зерно {self.seed}: " + " ".join(str(p) for p in parts)

    def cli(self, *argv) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            return capture(artel.main)

    def register(self, tasks: str) -> str:
        return json.loads(self.cli("observe", "register", "--tasks", tasks))["id"]

    def null_alert(self, label: str) -> str:
        message = f"{self.mark}-{label}"
        store.insert_alert(self.conn, None, "incident", self.source, message)
        return message

    def watch_output(self, observation_id: str, cycles: int) -> str:
        """`cycles` итераций `watch --observation`: пауза после последней
        обрывает цикл."""
        sleep = mock.Mock(side_effect=[None] * (cycles - 1)
                          + [RuntimeError("watch ended")])
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation",
                                             observation_id]), \
                patch_sleep(watch, sleep), contextlib.redirect_stdout(out):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                artel.main()
        return out.getvalue()

    def lines_with(self, out: str, message: str) -> list:
        return [line for line in out.splitlines() if message in line]


class NullAlertDeliveryTest(_NullAlertBase):

    def test_ac5_null_alert_once_per_observation(self):
        """Алерт с `target` NULL выводится дозором каждого из двух
        наблюдений ровно один раз — и при нескольких циклах одного
        запуска, и при повторном запуске дозора.

        Сценарий: алерт заводится после регистрации обоих наблюдений;
        дозор наблюдения артели (несколько циклов), затем дозор
        наблюдения внешнего проекта (несколько циклов), затем повторно
        оба. Порядок наблюдений случаен.
        Ловит мутацию: NULL не пропускается фильтром (алерт не выводится
        никому); доставка отмечается общей позицией, а не позицией
        наблюдения (второе наблюдение алерт не получает); позиция
        наблюдения не продвигается за выведенный алерт (повтор в
        следующем цикле или запуске); NULL пропускается только
        наблюдению артели.
        """
        message = self.null_alert("pult")
        order = [self.obs_artel, self.obs_ext]
        self.rng.shuffle(order)
        for observation_id in order:
            cycles = self.rng.randrange(2, 5)
            with self.subTest(observation=observation_id, run="first", seed=self.seed):
                out = self.watch_output(observation_id, cycles)
                self.assertEqual(len(self.lines_with(out, message)), 1,
                                 self.msg(observation_id, cycles, out))
        for observation_id in order:
            with self.subTest(observation=observation_id, run="again", seed=self.seed):
                out = self.watch_output(observation_id, 2)
                self.assertEqual(self.lines_with(out, message), [],
                                 self.msg(observation_id, out))

    def test_ac6_null_alert_project_field_is_dash(self):
        """Строка дозора у алерта с `target` NULL несёт `-` в поле проекта.

        Строка дозора — `ts  <поле проекта>  <источник>  alert:<вид>  |
        <сообщение>`; поле проекта стоит сразу за меткой времени.
        Ловит мутацию: поле печатается как `None` или пустым, либо `-`
        ставится не в поле проекта (например, в источник).
        """
        message = self.null_alert("dash")
        for observation_id in (self.obs_artel, self.obs_ext):
            with self.subTest(observation=observation_id, seed=self.seed):
                lines = self.lines_with(self.watch_output(observation_id, 1), message)
                self.assertEqual(len(lines), 1, self.msg(observation_id, lines))
                fields = lines[0].split("  ")
                self.assertEqual(fields[1:4],
                                 ["-", self.source, "alert:incident"],
                                 self.msg(lines[0]))

    def test_ac7_observe_events_prints_null_alert_with_dash(self):
        """`observe <наблюдение> events` с окном, включающим алерт с
        `target` NULL, выводит его с `-` в поле проекта.

        Сценарий: окно задаётся `--from 0,0` и прежней позицией
        разбора (без `--from`), у наблюдения каждого проекта.
        Ловит мутацию: правка фильтра сделана только в цикле дозора, а
        `observe events` читает алерты прежним правилом — алерт с NULL
        не выводится; либо поле проекта печатается `None`.
        """
        message = self.null_alert("events")
        for observation_id in (self.obs_artel, self.obs_ext):
            for extra in (["--from", "0,0"], []):
                with self.subTest(observation=observation_id, extra=extra,
                                  seed=self.seed):
                    out = self.cli("observe", "events", observation_id, *extra)
                    lines = self.lines_with(out, message)
                    self.assertEqual(len(lines), 1, self.msg(observation_id, out))
                    self.assertEqual(lines[0].split("  ")[1:4],
                                     ["-", self.source, "alert:incident"],
                                     self.msg(lines[0]))
