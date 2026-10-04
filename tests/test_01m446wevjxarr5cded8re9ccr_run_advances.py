"""`artel.py run <id>` после успешного шага роли один раз продвигает задачу.

После шага роли с rc=0 в агентском состоянии команда `run` один раз
выполняет `advance` и печатает его исход; отказ этого `advance` нового шага
роли не запускает; шаг с rc≠0 `advance` не получает. Шаг роли, запущенный
циклом `auto`, сам `advance` не выполняет — продвигает только цикл.

Группа: долгоживущий
Красен до реализации: `run` после успешного шага только печатает «дальше: artel.py advance <id>» и `advance` не вызывает — AC-10 и AC-11 (отказ advance) падают; AC-11 (rc≠0) и AC-12 держатся уже сегодня и в связке с ними сторожат, что продвижение не задвоилось.

Публичная поверхность: команда — `artel.main()` с argv `run <id> --attach`
(форма, которой отвязанный `run` исполняется в своём процессе); шаг роли —
настоящий `runner.cmd_run` с подменённым `runner.spawn_agent` (агент — поток
событий `FakeProc`, документ роли пишется в каталог документов задачи);
`advance` — подменённый `fsm.cmd_advance`, считающий вызовы: если агент
шага сдал PLAN.md `status: ready`, он, как настоящий, переводит задачу
`in_dev -> verifying` и печатает переход, в сценарии отказа — журналирует
отказ «переход отклонён: …» и печатает его. Цикл — `auto.cmd_auto(<id>)`.
Числа (лимит шагов цикла, хвосты текстов) случайны; зерно печатается и
входит в текст провала.

Исход «состояние не меняется» при rc≠0 читается как «`advance` состояние не
двигает»: задача остаётся там, где её оставил сам неуспешный шаг (штатная
эскалация после исчерпанных попыток), и не уходит в состояние, в которое
увёл бы её `advance`.
"""
import contextlib
import io
import os
import random
import shutil
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, auto, config, fsm, keychain, runner, store
from tests.sandbox import (FakeProc, LightTransitionSandbox, TimeWithSleep,
                           event, seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

#: Корень репозитория — источник `templates/`/`skills/` для брифа шага.
REPO_ROOT = Path(__file__).resolve().parent.parent
STUB_BIN = "/artel-test-stub-bin"
FORWARD = "verifying"


def plan_text(task_id: str, status: str) -> str:
    return (f"---\ntask: {task_id}\ntype: plan\nauthor_role: developer\n"
            f"status: {status}\nschema_version: 1\n---\n\n# PLAN: шаг\n\n"
            f"## Подход\n\n## Шаги\n\n## Покрытие требований\n\n"
            f"## Влияние на систему\n")


class CountingAdvance:
    """Подмена `fsm.cmd_advance`: считает вызовы; `refusal` — отказывать
    этим действием, иначе переход `in_dev -> verifying`, если агент шага
    сдал PLAN.md `status: ready` (`ready()`)."""

    def __init__(self, ready):
        self.ready = ready
        self.calls = 0
        self.refusal: str | None = None
        self.marker = ""

    def __call__(self, task_id, *args, **kwargs) -> bool:
        self.calls += 1
        conn = store.db()
        task_id = store.resolve_task_id(conn, task_id)
        if self.refusal is not None:
            store.journal(conn, task_id, "fsm", self.refusal, self.marker)
            print(f"[{task_id}] {self.refusal}: {self.marker}")
            return False
        state = store.get_task(conn, task_id)["state"]
        if state == "in_dev" and self.ready():
            store.set_state(conn, task_id, FORWARD, "fsm", expected_state=state,
                            detail=self.marker)
            print(f"[{task_id}] -> {FORWARD}  ({self.marker})")
            return False
        print(f"[{task_id}] PLAN.md не ready — нечего продвигать ({self.marker})")
        return False


class RunAdvancesSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов с настоящим шагом роли: CLI агента
    подменён (`runner.spawn_agent`), `which`/`--version` CLI отвечают
    заглушкой, предполёт окружения пуст, слот keychain отдаёт токен, паузы
    между попытками мгновенны."""

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        previous_signal = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous_signal)
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills",
                        dirs_exist_ok=True)
        seed_developer_brief_fixtures(self.root)
        operator_home = self.root / "operator-home"
        operator_home.mkdir()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "HOME": str(operator_home)})
        env.start()
        self.addCleanup(env.stop)
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
            os.environ.pop(name, None)

        previous_which = shutil.which
        previous_run = subprocess.run

        def which(name, *args, **kwargs):
            if name in ("claude", "codex", "gh"):
                return f"{STUB_BIN}/{name}"
            return previous_which(name, *args, **kwargs)

        def run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and cmd:
                argv = [str(part) for part in cmd]
                if Path(argv[0]).name == "claude" and "--version" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "2.1.300 (Claude Code)\n", "")
            return previous_run(cmd, *args, **kwargs)

        self.plan_ready = False
        self.advance = CountingAdvance(lambda: self.plan_ready)
        self.advance.marker = f"исход advance {self.rng.randrange(1 << 40):x}"
        self.spawns = 0
        self.rc = 0
        for target, attr, value in ((shutil, "which", which),
                                    (subprocess, "run", run),
                                    (runner, "time", TimeWithSleep(lambda _: None)),
                                    (keychain, "token", lambda slot: "tok-test"),
                                    (runner, "spawn_agent", self.spawn),
                                    (fsm, "cmd_advance", self.advance)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        preflight = mock.patch("orchestrator.doctor.preflight_checks",
                               lambda role, target, **step: [])
        preflight.start()
        self.addCleanup(preflight.stop)
        self.use_catalog_fixture()
        self.plan_status = "ready"

        conn = store.db()
        store.update_task(conn, self.TASK, state="in_dev", paused=0)
        sync_spec_from_worktree(self.TASK)
        self.docs_dir(self.TASK).mkdir(parents=True, exist_ok=True)

    def note(self, extra: str = "") -> str:
        return f"зерно: {self.seed}; {extra}"

    def docs_dir(self, task_id: str) -> Path:
        return config.PROJECTS / config.DEFAULT_TARGET / "tasks" / task_id

    def spawn(self, cmd, *args, **kwargs):
        """Агент шага: пишет PLAN.md в каталог документов задачи и
        завершается с кодом `self.rc`."""
        self.spawns += 1
        docs = self.docs_dir(self.TASK)
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(plan_text(self.TASK, self.plan_status),
                                      encoding="utf-8")
        self.plan_ready = self.plan_status == "ready"
        if self.rc == 0:
            return FakeProc([event(type="result", subtype="success",
                                   is_error=False, result="готово",
                                   total_cost_usd=0.01)])
        return FakeProc([event(type="result", subtype="error_during_execution",
                               is_error=True, result="упал",
                               total_cost_usd=0.01)], returncode=self.rc)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def run_command(self) -> str:
        """`artel.py run <id> --attach`: печать команды (вместе с отказом,
        если команда завершилась `SystemExit`)."""
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "run", self.TASK, "--attach"]), \
                contextlib.redirect_stdout(buf):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\nSystemExit: {exc.code}\n")
        return buf.getvalue()

    def agent_finished(self) -> bool:
        return any(row["actor"] == "developer"
                   and row["action"] == "agent run finished"
                   for row in store.task_steps(store.db(), self.TASK))


class RunAdvancesAfterSuccessfulStepTest(RunAdvancesSandbox):

    def test_ac10_run_advances_once_after_a_successful_step(self):
        """Успешный шаг developer с готовым PLAN.md — `run` один раз продвигает задачу.

        Сценарий: задача в `in_dev`; агент шага пишет PLAN.md `status: ready`
        в каталог документов и завершается rc=0. После команды `run` шаг
        завершён («agent run finished»), `advance` вызван ровно один раз,
        задача в `verifying`, а напечатанный исход `advance` (строка
        перехода со случайной меткой) — в выводе `run`.

        Ловит мутацию: `run` по-прежнему заканчивается подсказкой «дальше:
        artel.py advance» без вызова — задача остаётся в `in_dev`, вызовов
        `advance` ноль; либо `advance` зовётся дважды (в `runner` и в
        диспетчере) — вызовов два.
        """
        out = self.run_command()
        self.assertTrue(self.agent_finished(), self.note(f"шаг не завершён\n{out}"))
        self.assertEqual(self.spawns, 1, self.note(out))
        self.assertEqual(self.advance.calls, 1, self.note(
            f"вызовов advance после шага: {self.advance.calls}\n{out}"))
        self.assertEqual(self.state(), FORWARD, self.note(out))
        self.assertIn(self.advance.marker, out, self.note(
            "исход advance не напечатан в выводе run"))


class RunAdvanceRefusalAndFailedStepTest(RunAdvancesSandbox):

    def test_ac11_refused_advance_is_printed_and_no_new_step_runs(self):
        """`advance` после успешного шага отказал — исход напечатан, нового шага нет.

        Сценарий: задача в `in_dev`; шаг developer завершается rc=0;
        `advance` отказывает действием «переход отклонён: …» со случайным
        хвостом. После `run` агент запускался ровно один раз, `advance` — ровно
        один, задача в `in_dev`, текст отказа (с меткой) — в выводе `run`.

        Ловит мутацию: `run` не зовёт `advance` (отказа в выводе нет) либо
        на отказе `advance` повторяет шаг роли (как цикл на классе «чинит
        роль») — агент запущен дважды.
        """
        self.advance.refusal = (f"переход отклонён: гейт сценария "
                                f"{self.rng.randrange(1 << 30):x}")
        out = self.run_command()
        self.assertTrue(self.agent_finished(), self.note(f"шаг не завершён\n{out}"))
        self.assertEqual(self.advance.calls, 1, self.note(
            f"вызовов advance после шага: {self.advance.calls}\n{out}"))
        self.assertEqual(self.spawns, 1, self.note(
            f"после отказа advance запущен новый шаг роли\n{out}"))
        self.assertEqual(self.state(), "in_dev", self.note(out))
        self.assertIn(self.advance.refusal, out, self.note(
            "отказ advance не напечатан в выводе run"))
        self.assertIn(self.advance.marker, out, self.note(
            "подробность отказа advance не напечатана в выводе run"))

    def test_ac11_failed_step_gets_no_advance(self):
        """Шаг с rc≠0 — `advance` не выполняется, состояние им не двигается.

        Сценарий: задача в `in_dev`; агент шага пишет готовый PLAN.md, но
        завершается со случайным ненулевым кодом на каждой попытке. После
        `run` записи «agent run finished» нет, `advance` не вызывался ни
        разу, задача не в `verifying` (куда увёл бы её `advance` по готовому
        PLAN.md).

        Ловит мутацию: `advance` после шага зовётся без проверки исхода шага
        (по факту возврата `cmd_run`) — готовый PLAN.md упавшего шага уводит
        задачу в `verifying`, вызовов `advance` один.
        """
        self.rc = self.rng.randrange(1, 126)
        out = self.run_command()
        self.assertFalse(self.agent_finished(), self.note(
            f"шаг с rc={self.rc} записан успешным\n{out}"))
        self.assertGreaterEqual(self.spawns, 1, self.note(out))
        self.assertEqual(self.advance.calls, 0, self.note(
            f"rc={self.rc}: после неуспешного шага вызван advance\n{out}"))
        self.assertNotEqual(self.state(), FORWARD, self.note(out))


class AutoStepDoesNotAdvanceItselfTest(RunAdvancesSandbox):

    def test_ac12_role_step_inside_auto_does_not_advance(self):
        """Шаг роли внутри цикла `auto` сам `advance` не делает — один `advance` на итерацию.

        Сценарий: задача в `in_dev`, лимит шагов цикла — случайное число от 1
        до 3, порог холостых шагов выше; агент каждого шага пишет PLAN.md
        `status: draft` и завершается rc=0, `advance` ничего не продвигает и
        не отказывает. Цикл делает столько шагов developer, каков лимит, и
        `advance` вызывается ровно столько же раз — по одному
        предварительному на итерацию.

        Ловит мутацию: продвижение после шага встроено в `runner.cmd_run`
        безусловно — шаг роли внутри цикла зовёт свой `advance`, вызовов
        вдвое больше, чем шагов.
        """
        self.plan_status = "draft"
        limit = self.rng.randint(1, 3)
        with mock.patch.object(config, "AUTO_MAX_STEPS", limit), \
                mock.patch.object(config, "AUTO_STALL_STEPS_LIMIT", limit + 5):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                auto.cmd_auto(self.TASK)
        out = buf.getvalue()
        finished = sum(1 for row in store.task_steps(store.db(), self.TASK)
                       if row["actor"] == "developer"
                       and row["action"] == "agent run finished")
        self.assertEqual(finished, limit, self.note(
            f"лимит {limit}: шагов developer {finished}\n{out}"))
        self.assertEqual(self.advance.calls, finished, self.note(
            f"лимит {limit}: шагов {finished}, вызовов advance "
            f"{self.advance.calls}\n{out}"))


if __name__ == "__main__":
    unittest.main()
