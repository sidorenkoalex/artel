"""Сторож: шаг роли в песочнице не спит настоящим `time.sleep` в паузе повтора агента.

Группа: долгоживущий

Красен до реализации: умолчание песочницы `TmpRootTest` паузу повтора не подменяет — неуспешная попытка агента доходит до настоящего `time.sleep` в `orchestrator/runner.py`, сторож профиля ловит этот вызов (методы test_ac1/test_ac7); test_ac2 зелёный с рождения — явная подмена сна тестом уже видит паузы прежней длительности.

Сценарий тот же, что у `tests/test_agent_failure.py::CmdRunFailureTest`:
шаг разработчика `runner.cmd_run` с подставными попытками агента
(`runner.spawn_agent` отдаёт `FakeProc` по одному на попытку), но БЕЗ
собственной подмены сна — тест полагается на умолчание песочницы.

Настоящий сон пульта ловится профилем интерпретатора (`sys.setprofile`):
событие `c_call` настоящей функции `time.sleep`, вызванной из кода модуля
`orchestrator.runner`, — это пауза повтора `_run_attempts` (другого сна в
`runner` нет). Профиль поднимает исключение-метку ДО исполнения вызова:
красный сторож не ждёт ни `RETRY_BACKOFF_SEC`, ни
`TRANSIENT_SYSTEM_BACKOFF_SEC`. Подмена `time.sleep` на весь процесс тут
не годится — её запрещает сторож
`tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`.

Время прогона не утверждается (SPEC, требование 6): признак — факт
вызова настоящего сна, не длительность теста.

Входы — случайные при каждом запуске (число неуспешных попыток, текст
провала, класс: обычный или «транзиентный системный» с минутной паузой);
зерно печатается и входит в текст провала.
"""
import random
import sys
import threading
import time
import unittest
from unittest import mock

from orchestrator import (agent_log, catalog, config, failure_classification,
                          models, providers, runner, stack, store)
from tests.sandbox import (DeveloperBriefTmpRootTest, FakeProc,
                           capture_new_task_id, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git, patch_sleep,
                           sync_spec_from_worktree)

# Значения паузы до любой подмены песочницы — «прежняя длительность»
# (SPEC, AC-2); модуль импортируется до `setUp` любого теста.
RETRY_BACKOFF_SEC = config.RETRY_BACKOFF_SEC
TRANSIENT_SYSTEM_BACKOFF_SEC = config.TRANSIENT_SYSTEM_BACKOFF_SEC

REAL_SLEEP = time.sleep
RUNNER_MODULE = runner.__name__


class RealRetrySleep(BaseException):
    """Метка: код `orchestrator.runner` позвал настоящий `time.sleep`.

    `BaseException` — чтобы её не проглотил `except Exception` пульта."""


class RealSleepWatch:
    """Профиль интерпретатора на время сценария: настоящий `time.sleep`
    из кода `orchestrator.runner` прерывается меткой `RealRetrySleep`,
    сам сон не исполняется."""

    def __init__(self):
        self.hits = []

    def _profile(self, frame, event, arg):
        if (event == "c_call" and arg is REAL_SLEEP
                and frame.f_globals.get("__name__") == RUNNER_MODULE):
            self.hits.append(f"{frame.f_code.co_filename}:{frame.f_lineno}")
            raise RealRetrySleep(self.hits[-1])

    def __enter__(self):
        self.prev = sys.getprofile()
        self.prev_threading = threading.getprofile()
        sys.setprofile(self._profile)
        return self

    def __exit__(self, *exc):
        sys.setprofile(self.prev)
        threading.setprofile(self.prev_threading)
        return False


def transient_signatures() -> list[str]:
    """Подстроки вывода, которые провайдер по умолчанию относит к связке
    «транзиентное системное» (минутная пауза повтора)."""
    found = []
    for entry in providers.or_default().failure_signatures():
        if entry.failure_class in failure_classification.TRANSIENT_SYSTEM_CLASSES:
            found.extend(sig for sig in entry.signatures if sig)
    return found


class RetryPauseScenario(DeveloperBriefTmpRootTest):
    """Шаг разработчика с подставными попытками агента в умолчании
    песочницы — без собственной подмены сна."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

        # Песочница без настоящего git: ветки — `fake_git`, артефакты —
        # диск `config.TASKS` (как в `CmdRunFailureTest`).
        for name, fake in (("git", fake_git), ("show", disk_backed_show),
                           ("ls_tree_files", disk_backed_ls_tree_files)):
            patcher = mock.patch.object(runner.gitcmd, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.capture(catalog.cmd_init)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch("orchestrator.doctor.preflight_checks",
                                lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        cli_patcher = mock.patch.object(
            stack, "installed_cli_version",
            lambda tool=None: max(m.min_cli_version for m in
                                  models.load_catalog().models.values()))
        cli_patcher.start()
        self.addCleanup(cli_patcher.stop)
        fp_patcher = mock.patch.object(
            agent_log, "environment_fingerprint",
            lambda: "окружение пульта подменено тестом")
        fp_patcher.start()
        self.addCleanup(fp_patcher.stop)

    def new_task_in_dev(self) -> str:
        _, task = capture_new_task_id(catalog.cmd_new, "Пауза повтора агента")
        sync_spec_from_worktree(task)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (task,))
        conn.commit()
        return task

    def run_step(self, task: str, attempts: list) -> list[str]:
        """Шаг `run` задачи `task`; attempts — (rc, строки вывода) по одной
        паре на попытку. Возвращает места настоящего сна `runner`."""
        procs = [FakeProc(lines, rc) for rc, lines in attempts]

        with mock.patch.object(runner, "spawn_agent", side_effect=procs), \
                RealSleepWatch() as watch:
            try:
                self.capture(runner.cmd_run, task)
            except RealRetrySleep:
                pass
        return watch.hits

    def retry_journal(self, task: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (task, "agent run retry"))]

    def failing_lines(self, transient: bool) -> list[str]:
        if transient:
            return [f"{self.rng.choice(transient_signatures())}\n"]
        return [f"упал на шаге {self.rng.randrange(1000)}\n"]


class SandboxRetryPauseTest(RetryPauseScenario):
    """Умолчание песочницы снимает паузу повтора; явная подмена её видит."""

    def test_ac1_failed_attempt_never_reaches_real_retry_sleep(self):
        """Неуспешные попытки в умолчании песочницы не доходят до настоящего сна.

        Сценарий: две задачи — обычный провал (случайный текст) и провал
        «транзиентного системного» класса (случайная сигнатура провайдера,
        минутная пауза); все попытки каждой падают. Журнал несёт записи
        «agent run retry» (пауза повтора действительно наступала), а
        профиль не видел ни одного вызова настоящего `time.sleep` из
        `orchestrator.runner`.

        Ловит мутацию: подмена паузы повтора в `TmpRootTest.setUp` снята
        (или наложена только на одну ветку бэкоффа) — профиль видит
        настоящий `time.sleep` из `runner`, список мест сна непуст.
        """
        for transient in (False, True):
            with self.subTest(transient=transient, seed=self.seed):
                task = self.new_task_in_dev()
                attempts = [(1, self.failing_lines(transient))
                            for _ in range(config.AGENT_ATTEMPTS)]

                hits = self.run_step(task, attempts)

                self.assertEqual(hits, [],
                                 f"зерно {self.seed}: настоящий time.sleep "
                                 f"пульта на паузе повтора: {hits}")
                self.assertTrue(self.retry_journal(task),
                                f"зерно {self.seed}: пауза повтора не "
                                f"наступила — сценарий не проверяет её")

    def test_ac7_sandbox_step_does_not_sleep_on_retry(self):
        """Шаг роли, исчерпавший все попытки, не вызывает настоящий сон пульта.

        Сценарий: все `AGENT_ATTEMPTS` попыток разработчика падают обычным
        провалом со случайным текстом; между ними пульт журналирует
        `AGENT_RETRIES` записей «agent run retry», но профиль не видит
        настоящего `time.sleep` из `orchestrator.runner`.

        Ловит мутацию: в `tests/sandbox.py` снята подмена паузы повтора
        (умолчание песочницы снова оставляет `runner` с модулем `time`) —
        первая же пауза повтора зовёт настоящий `time.sleep`, профиль
        прерывает её меткой, тест красный.
        """
        task = self.new_task_in_dev()
        attempts = [(1, self.failing_lines(False))] * config.AGENT_ATTEMPTS

        hits = self.run_step(task, attempts)

        self.assertEqual(hits, [], f"зерно {self.seed}: настоящий time.sleep "
                                   f"пульта на паузе повтора: {hits}")
        self.assertEqual(len(self.retry_journal(task)), config.AGENT_RETRIES,
                         f"зерно {self.seed}: число пауз повтора")

    def test_ac2_explicit_opt_out_sees_original_pause_values(self):
        """Тест, явно подменивший сон `runner` сам, получает паузы прежней длительности.

        Сценарий: поверх умолчания песочницы тест ставит свою подмену сна
        `patch_sleep(runner, pauses.append)` — тот же явный отказ, что у
        `tests/test_agent_failure.py::CmdRunFailureTest`; все попытки
        падают (класс — случайно обычный или «транзиентный системный»).
        Записанные паузы — ровно `база * 2 ** (attempt - 1)` для попыток
        1..AGENT_RETRIES, где база — значение `RETRY_BACKOFF_SEC` либо
        `TRANSIENT_SYSTEM_BACKOFF_SEC` до любой подмены песочницы.

        Ловит мутацию: песочница снимает паузу обнулением
        `config.RETRY_BACKOFF_SEC`/`TRANSIENT_SYSTEM_BACKOFF_SEC` вместо
        подмены сна — явная подмена теста получает нули вместо прежних
        значений, список пауз расходится.
        """
        pauses = []
        patcher = patch_sleep(runner, pauses.append)
        patcher.start()
        self.addCleanup(patcher.stop)
        transient = self.rng.choice((False, True))
        base = TRANSIENT_SYSTEM_BACKOFF_SEC if transient else RETRY_BACKOFF_SEC
        task = self.new_task_in_dev()
        attempts = [(1, self.failing_lines(transient))] * config.AGENT_ATTEMPTS

        hits = self.run_step(task, attempts)

        self.assertEqual(hits, [], f"зерно {self.seed}: явная подмена теста "
                                   f"не перехватила сон: {hits}")
        self.assertEqual(pauses,
                         [base * 2 ** (n - 1)
                          for n in range(1, config.AGENT_ATTEMPTS)],
                         f"зерно {self.seed}: transient={transient}")


if __name__ == "__main__":
    unittest.main()
