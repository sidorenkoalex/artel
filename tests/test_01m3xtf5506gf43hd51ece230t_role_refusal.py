"""Единый признак шага роли и закрытый по умолчанию отказ команд пульта.

Диспетчер `artel.main` решает «процесс — шаг роли» одним признаком
`runner.in_role_environment`: маркер `ARTEL_ROLE` либо `HOME`, равный дому
роли `config.ROLE_HOME` (с завершающей чертой или без), а прежние основания
остаются достаточными. Под ролью отказывают все команды, меняющие состояние
пульта; белый список читающих команд исполняется; команда вне обоих списков
отказывает. Отвязанный запуск и прямые вызовы функций пульта отказом не
останавливаются.

Группа: долгоживущий
Красен до реализации: диспетчер читает только ARTEL_ROLE и отказывает лишь init/observe/watch/hook-migrate/run/auto/doctor --restore/canary pool-seal, а признак без CLAUDE_CONFIG_DIR не узнаёт HOME роли — тесты AC-1, AC-2, AC-4, AC-5 падают.
"""

import contextlib
import io
import os
import random
import signal
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from orchestrator import (amend, answer, artel, auto, budget, canary, catalog,
                          ci_rerun, cleanup, config, doctor, dry_run, fsm,
                          idgen, lease, models, notes, pause, pin, pool_seal,
                          projects, prune, release, report, runner, session,
                          store, venv, version, watch, workspace, zone_lock)
from tests.sandbox import SchemaTmpRootTest, TmpRootTest

TASK = "T001"

#: Команды требования 4 (новые отказы) и часть прежних отказов: argv после
#: `artel.py` и публичная реализация, которой диспетчер передаёт команду.
REFUSED_COMMANDS = (
    (("new", "Заголовок"), catalog, "cmd_new"),
    (("advance", TASK), fsm, "cmd_advance"),
    (("workspace", TASK), workspace, "cmd_workspace"),
    (("stop", TASK), store, "db"),
    (("approve", TASK), fsm, "cmd_approve"),
    (("reject", TASK, "причина"), fsm, "cmd_reject"),
    (("answer", TASK, "/nonexistent/ANSWER.md"), answer, "cmd_answer"),
    (("zones-extend", TASK, "docs/a.md"), answer, "cmd_zones_extend"),
    (("kill", TASK, "--yes"), cleanup, "cmd_kill"),
    (("release", TASK), release, "cmd_release"),
    (("pause", TASK), pause, "cmd_pause"),
    (("pause", "--now", TASK), pause, "cmd_pause_now"),
    (("resume", TASK), pause, "cmd_resume"),
    (("budget", TASK, "40"), budget, "cmd_budget"),
    (("target-init", "demo"), projects, "cmd_target_init"),
    (("doctor", "--fix"), doctor, "cmd_doctor"),
    (("alert-ack", "1", "разобрано"), doctor, "cmd_alert_ack"),
    (("canary", "--k", "2"), canary, "cmd_canary"),
    (("prune", "--execute"), prune, "cmd_prune"),
    (("amend-tests", TASK, "--reason", "основание"), amend, "cmd_amend_tests"),
    (("ci-rerun", TASK, "--reason", "основание"), ci_rerun, "cmd_ci_rerun"),
    (("pin-update", "abc1234"), pin, "cmd_pin_update"),
    (("pin", "--to", "abc1234"), pin, "cmd_pin_to"),
    (("zone-release", TASK), zone_lock, "cmd_zone_release"),
    (("zone-reorder", TASK, "T002"), zone_lock, "cmd_zone_reorder"),
    (("venv-sync",), venv, "cmd_venv_sync"),
    # Прежние отказы — теперь и во втором варианте окружения роли.
    (("init",), catalog, "cmd_init"),
    (("doctor", "--restore"), doctor, "cmd_doctor"),
    (("canary", "pool-seal"), pool_seal, "cmd_pool_seal"),
    (("watch", "--observation"), watch, "cmd_watch"),
    (("run", TASK, "--client", "claude", "--chat", "c1"), store, "db"),
    (("auto", TASK, "--client", "claude", "--chat", "c1"), store, "db"),
)

#: Белый список требования 5 с публичной реализацией (кроме `observe show`
#: и `hook-migrate inspect` — у них свои сценарии ниже).
ALLOWED_COMMANDS = (
    (("status",), catalog, "cmd_status"),
    (("show", TASK), catalog, "cmd_show"),
    (("log", TASK), catalog, "cmd_log"),
    (("version",), version, "cmd_version"),
    (("models",), models, "cmd_models"),
    (("report",), report, "cmd_report"),
    (("doctor",), doctor, "cmd_doctor"),
    (("watch",), watch, "cmd_watch"),
    (("acceptance-dry-run", TASK), dry_run, "cmd_acceptance_dry_run"),
    (("prune",), prune, "cmd_prune"),
)

#: Формы с флагом, которые обязаны отказывать, хотя голая форма разрешена.
FLAG_FORMS = (
    (("doctor", "--fix"), doctor, "cmd_doctor"),
    (("doctor", "--restore"), doctor, "cmd_doctor"),
    (("prune", "--execute"), prune, "cmd_prune"),
    (("watch", "--observation"), watch, "cmd_watch"),
)


class ImplementationReached(Exception):
    """Диспетчер дошёл до подменённой реализации команды."""


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


def dispatch(argv) -> None:
    with mock.patch.object(sys, "argv", ["artel.py", *argv]):
        artel.main()


class RoleDispatchTest(TmpRootTest):
    """Песочница с путями `config` во временном каталоге (`config.ROOT` — не
    worktree, поэтому отказ «пульт только из главной копии» не мешает)."""

    def setUp(self):
        super().setUp()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)

    def operator_home(self) -> str:
        return f"/tmp/operator_{self.rng.randrange(1 << 30):x}"

    def role_name(self) -> str:
        return f"role_{self.rng.randrange(1 << 30):x}"

    def marker_env(self, role: str) -> dict:
        return {"HOME": self.operator_home(), config.ARTEL_ROLE_ENV: role,
                "PATH": os.environ.get("PATH", "")}

    def home_env(self) -> dict:
        return {"HOME": str(config.ROLE_HOME), "PATH": os.environ.get("PATH", "")}

    def operator_env(self) -> dict:
        return {"HOME": self.operator_home(), "PATH": os.environ.get("PATH", "")}

    def role_variants(self):
        """(название, окружение, обязательная подстрока текста отказа)."""
        role = self.role_name()
        return (("маркер", self.marker_env(role), role),
                ("HOME роли", self.home_env(), "окружение роли"))

    def assert_refused(self, argv, module, attr, env, expected):
        spy = mock.Mock(side_effect=ImplementationReached(" ".join(argv)))
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(module, attr, spy):
            try:
                with self.assertRaises(SystemExit) as refused:
                    dispatch(argv)
            except ImplementationReached:
                self.fail(f"зерно: {self.seed}; {' '.join(argv)}: под ролью "
                          f"исполнена реализация {module.__name__}.{attr}")
        spy.assert_not_called()
        self.assertIn(expected, str(refused.exception.code),
                      f"зерно: {self.seed}; {' '.join(argv)}: текст отказа")

    def assert_executed(self, argv, module, attr, env):
        spy = mock.Mock(return_value=None)
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(module, attr, spy):
            try:
                dispatch(argv)
            except SystemExit as exc:
                self.fail(f"зерно: {self.seed}; {' '.join(argv)}: под ролью "
                          f"отказ вместо исполнения: {exc.code}")
        self.assertEqual(1, spy.call_count,
                         f"зерно: {self.seed}; {' '.join(argv)}: реализация "
                         f"{module.__name__}.{attr} не вызвана")


class SinglePredicateDispatchTest(RoleDispatchTest):
    def test_ac1_dispatcher_decides_by_in_role_environment(self):
        """Диспетчер спрашивает признак роли у `runner.in_role_environment`.

        Сценарий: `kill` из окружения с HOME дома роли без маркера — признак
        вызван, отказ говорит «окружение роли»; с маркером — отказ называет
        роль; подменённый признак «истина» при чужом HOME даёт отказ, а
        «ложь» при выставленном маркере отказа не даёт — решение принимает
        только он.

        Ловит мутацию: `artel._refuse_if_role_restricted` снова читает
        только `ARTEL_ROLE` — окружение с HOME роли без маркера доходит до
        `cleanup.cmd_kill`, а подмена признака на «истину» отказа не даёт.
        """
        argv, module, attr = (("kill", TASK), cleanup, "cmd_kill")
        with mock.patch.object(runner, "in_role_environment",
                               wraps=runner.in_role_environment) as predicate:
            self.assert_refused(argv, module, attr, self.home_env(), "окружение роли")
        predicate.assert_called()

        role = self.role_name()
        self.assert_refused(argv, module, attr, self.marker_env(role), role)

        with mock.patch.object(runner, "in_role_environment", return_value=True):
            self.assert_refused(argv, module, attr, self.operator_env(),
                                "окружение роли")
        with mock.patch.object(runner, "in_role_environment", return_value=False):
            self.assert_executed(argv, module, attr, self.marker_env(self.role_name()))


class HomePredicateTest(TmpRootTest):
    def test_ac2_role_home_alone_is_a_role_step(self):
        """HOME дома роли без маркера и без `CLAUDE_CONFIG_DIR` — шаг роли.

        Сценарий: на нескольких случайных домах роли (и на доме песочницы)
        окружение `{"HOME": дом}` и `{"HOME": дом + "/"}` распознаются ролью,
        HOME Оператора — нет; собранное окружение шага Codex со снятым
        `ARTEL_ROLE` распознаётся по HOME.

        Ловит мутацию: резервная ветка признака снова требует
        `CLAUDE_CONFIG_DIR` (или сравнивает HOME строкой без снятия
        завершающей черты) — окружение Codex со снятым маркером и HOME с
        чертой дают ложь.
        """
        seed = new_seed()
        rng = random.Random(seed)
        homes = [config.ROLE_HOME] + [
            Path(f"/tmp/artel_{rng.randrange(1 << 30):x}") / ".artel" / "home"
            for _ in range(4)]
        for home in homes:
            with mock.patch.object(config, "ROLE_HOME", home), \
                    mock.patch.object(config, "ROLE_CONFIG_DIR", home / ".claude"):
                for value in (str(home), str(home) + "/"):
                    self.assertTrue(runner.in_role_environment({"HOME": value}),
                                    f"зерно: {seed}; HOME={value}")
                operator = f"/tmp/operator_{rng.randrange(1 << 30):x}"
                self.assertFalse(runner.in_role_environment({"HOME": operator}),
                                 f"зерно: {seed}; HOME={operator}")

        ambient = {"HOME": f"/tmp/operator_{rng.randrange(1 << 30):x}",
                   "PATH": os.environ.get("PATH", "")}
        with mock.patch.dict(os.environ, ambient, clear=True), \
                mock.patch.object(runner, "declared_tool_path", return_value="/tmp/codex"), \
                mock.patch.object(runner, "git_identity", return_value={}), \
                mock.patch.object(runner.providers, "for_role",
                                  return_value=runner.providers.get("codex")):
            env = dict(runner.role_env("developer"))
        env.pop(config.ARTEL_ROLE_ENV, None)
        env.pop("CLAUDE_CONFIG_DIR", None)
        self.assertTrue(runner.in_role_environment(env),
                        f"зерно: {seed}; окружение Codex без маркера")

    def test_ac3_prior_grounds_remain_sufficient(self):
        """Прежние основания признака по-прежнему достаточны.

        Сценарий: непустой случайный `ARTEL_ROLE` при чужом HOME — роль;
        пара HOME+`CLAUDE_CONFIG_DIR` дома роли — роль; `ARTEL_ROLE` пуст, а
        HOME чужой — не роль.

        Ловит мутацию: правило HOME вытеснило прежние ветки либо маркер
        проверяется присутствием ключа, а не непустотой — случайный маркер
        при чужом HOME даёт ложь или пустой маркер даёт истину.
        """
        seed = new_seed()
        rng = random.Random(seed)
        for _ in range(5):
            env = {"HOME": f"/tmp/operator_{rng.randrange(1 << 30):x}",
                   config.ARTEL_ROLE_ENV: f"role_{rng.randrange(1 << 30):x}"}
            self.assertTrue(runner.in_role_environment(env), f"зерно: {seed}; {env}")
        legacy = {"HOME": str(config.ROLE_HOME),
                  "CLAUDE_CONFIG_DIR": str(config.ROLE_CONFIG_DIR)}
        self.assertTrue(runner.in_role_environment(legacy), f"зерно: {seed}; пара")
        self.assertFalse(runner.in_role_environment(
            {"HOME": "/tmp/operator", config.ARTEL_ROLE_ENV: ""}),
            f"зерно: {seed}; пустой маркер при чужом HOME")


class RefusedCommandsTest(RoleDispatchTest):
    def test_ac4_every_state_changing_command_refuses_before_implementation(self):
        """Каждая команда списка требования 4 под ролью отказывает до реализации.

        Сценарий: для каждой команды (в случайном порядке) и для обоих
        вариантов окружения роли — с маркером и с HOME дома роли без
        маркера — `artel.main()` завершается отказом, подменённая
        реализация не вызвана, текст отказа называет роль либо «окружение
        роли».

        Ловит мутацию: пропущена одна команда списка (например `budget` или
        `zone-reorder`) — её подменённая реализация вызывается под ролью.
        """
        cases = list(REFUSED_COMMANDS)
        self.rng.shuffle(cases)
        for argv, module, attr in cases:
            for name, env, expected in self.role_variants():
                with self.subTest(command=" ".join(argv), variant=name):
                    self.assert_refused(argv, module, attr, env, expected)


class AllowedCommandsTest(RoleDispatchTest):
    def test_ac5_allow_list_runs_under_role(self):
        """Белый список требования 5 под ролью исполняется.

        Сценарий: `status`, `show`, `log`, `version`, `models`, `report`,
        голый `doctor`, `watch` без `--observation`, `acceptance-dry-run`,
        `prune` без `--execute` доходят до своей реализации; `observe show`
        печатает наблюдение; `hook-migrate inspect` печатает статус — в
        обоих вариантах окружения роли.

        Ловит мутацию: закрытость по умолчанию задела читающую команду
        (например `report` или голый `doctor` не внесены в белый список) —
        под ролью вместо исполнения отказ.
        """
        cases = list(ALLOWED_COMMANDS)
        self.rng.shuffle(cases)
        for argv, module, attr in cases:
            for name, env, _expected in self.role_variants():
                with self.subTest(command=" ".join(argv), variant=name):
                    self.assert_executed(argv, module, attr, env)

        observation = {"id": "obs1", "target": config.DEFAULT_TARGET,
                       "client": "claude", "chat": "c1", "state": "stopped",
                       "last_seen_at": None, "session_id": "s"}
        with tempfile.TemporaryDirectory() as tmp:
            absent_config = str(Path(tmp) / "settings.json")
            for name, env, _expected in self.role_variants():
                with self.subTest(command="observe show", variant=name), \
                        mock.patch.dict(os.environ, env, clear=True), \
                        mock.patch.object(store, "db", return_value=mock.Mock()), \
                        mock.patch.object(store, "observation", return_value=observation), \
                        mock.patch.object(store, "observation_tasks", return_value=[TASK]), \
                        mock.patch.object(store, "observed_runs", return_value=[]) as runs:
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        dispatch(("observe", "show", "obs1"))
                    runs.assert_called_once()
                    self.assertIn("obs1", out.getvalue())
                with self.subTest(command="hook-migrate inspect", variant=name), \
                        mock.patch.dict(os.environ, env, clear=True):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        dispatch(("hook-migrate", "inspect", "--client", "claude",
                                  "--config", absent_config))
                    self.assertIn("absent", out.getvalue())

    def test_ac5_flag_forms_refuse(self):
        """Формы с флагом отказывают, хотя голая форма разрешена.

        Сценарий: `doctor --fix`, `doctor --restore`, `prune --execute`,
        `watch --observation` в обоих вариантах окружения роли — отказ,
        реализация не вызвана.

        Ловит мутацию: отказ решается по имени команды без учёта флага —
        `doctor`/`prune` в белом списке пропускают и `--fix`/`--execute`.
        """
        for argv, module, attr in FLAG_FORMS:
            for name, env, expected in self.role_variants():
                with self.subTest(command=" ".join(argv), variant=name):
                    self.assert_refused(argv, module, attr, env, expected)

    def test_ac5_command_outside_both_lists_refuses(self):
        """Команда вне белого списка и списка отказа под ролью отказывает.

        Сценарий: `note` и `doc-commit` (есть в таблице диспетчера, нет ни в
        одном списке) отказывают в диспетчере, не доходя до `notes`; имя
        команды-заглушки, которого нет ни в одном списке, под ролью получает
        отказ роли до разбора таблицы — список закрыт по умолчанию.

        Ловит мутацию: отказ задан перечнем запрещённых команд, а не
        закрытостью по умолчанию — команда без записи в списке (заглушка)
        исполняется либо получает «Неизвестная команда» вместо отказа роли.
        """
        for argv, attr in ((("note", "--flush"), "cmd_note"),
                           (("doc-commit", "--flush"), "cmd_doc_commit")):
            for name, env, expected in self.role_variants():
                with self.subTest(command=argv[0], variant=name):
                    self.assert_refused(argv, notes, attr, env, expected)

        stub = f"stub-{self.rng.randrange(1 << 30):x}"
        for name, env, expected in self.role_variants():
            with self.subTest(command=stub, variant=name), \
                    mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(SystemExit) as refused:
                    dispatch((stub,))
                self.assertIn(expected, str(refused.exception.code),
                              f"зерно: {self.seed}; заглушка {stub}")


class DetachedLaunchTest(RoleDispatchTest):
    def test_ac6_detached_launch_spawns_attach_child(self):
        """Отвязанный `run`/`auto` из окружения Оператора порождает ребёнка с `--attach`.

        Сценарий: родитель без признака роли зовёт `run`/`auto` с клиентом и
        чатом; наблюдение живое, lease свободен; подменённый
        `subprocess.Popen` получает argv с командой, задачей и `--attach`,
        отказа нет.

        Ловит мутацию: отказ поставлен в общий путь отвязанного запуска
        (проверка признака роли или безусловный отказ перед `Popen`) —
        `Popen` не вызван, родитель Оператора получает отказ.
        """
        observer = {"id": "obs1",
                    "last_seen_at": datetime.now(timezone.utc).isoformat()}
        for cmd in ("run", "auto"):
            popen = mock.Mock(return_value=mock.Mock(pid=4242))
            with self.subTest(command=cmd), \
                    mock.patch.dict(os.environ, self.operator_env(), clear=True), \
                    mock.patch.object(store, "db", return_value=mock.Mock()), \
                    mock.patch.object(store, "resolve_task_id",
                                      side_effect=lambda conn, task: task), \
                    mock.patch.object(store, "get_task",
                                      return_value={"target": config.DEFAULT_TARGET}), \
                    mock.patch.object(session, "resolve_session_id", return_value="s"), \
                    mock.patch.object(store, "matching_observation", return_value=observer), \
                    mock.patch.object(lease, "is_live", return_value=False), \
                    mock.patch.object(store, "record_observed_run"), \
                    mock.patch.object(artel.subprocess, "Popen", popen):
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        dispatch((cmd, TASK, "--client", "claude", "--chat", "c1"))
                    except SystemExit as exc:
                        self.fail(f"зерно: {self.seed}; {cmd}: отказ отвязанному "
                                  f"запуску Оператора: {exc.code}")
                popen.assert_called_once()
                child_argv = popen.call_args.args[0]
                self.assertIn(cmd, child_argv)
                self.assertIn(TASK, child_argv)
                self.assertIn("--attach", child_argv)

    def test_ac6_attach_forms_run_under_role(self):
        """`run --attach` и `auto --attach` под ролью исполняются, как и до задачи.

        Сценарий: в обоих вариантах окружения роли `run <id> --attach`
        доходит до `runner.cmd_run`, `auto <id> --attach` — до
        `auto.cmd_auto`.

        Ловит мутацию: исключение `--attach` из закрытости по умолчанию
        потеряно (run/auto отказывают безусловно) — ребёнок отвязанного
        запуска, унаследовавший окружение, получил бы отказ.
        """
        for argv, module, attr in ((("run", TASK, "--attach"), runner, "cmd_run"),
                                   (("auto", TASK, "--attach"), auto, "cmd_auto")):
            for name, env, _expected in self.role_variants():
                with self.subTest(command=" ".join(argv), variant=name):
                    self.assert_executed(argv, module, attr, env)


class DirectCallsTest(RoleDispatchTest):
    def setUp(self):
        super().setUp()
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)

    def test_ac7_direct_calls_are_not_refused(self):
        """Прямые вызовы функций пульта под окружением роли не получают отказа.

        Сценарий: в обоих вариантах окружения роли `fsm.cmd_approve` и
        `auto.cmd_auto` доходят до взятия lease, `catalog.cmd_new` — до
        выдачи id задачи (подменены и останавливают вызов сигналом
        «дошли»), отказа пульта нет.

        Ловит мутацию: отказ перенесён внутрь функций `fsm`/`auto`/`catalog`
        — прямой вызов (ведение канарейки, цикл `auto`) завершается отказом
        роли раньше, чем доходит до lease или id.
        """
        calls = (("fsm.cmd_approve", lambda: fsm.cmd_approve(TASK)),
                 ("auto.cmd_auto", lambda: auto.cmd_auto(TASK)),
                 ("catalog.cmd_new", lambda: catalog.cmd_new("Заголовок")))
        reached = ImplementationReached("дошли")
        for label, call in calls:
            for name, env, _expected in self.role_variants():
                with self.subTest(call=label, variant=name), \
                        mock.patch.dict(os.environ, env, clear=True), \
                        mock.patch.object(store, "db", return_value=mock.Mock()), \
                        mock.patch.object(store, "resolve_task_id",
                                          side_effect=lambda conn, task: task), \
                        mock.patch.object(store, "journal"), \
                        mock.patch.object(lease, "run_locked", side_effect=reached), \
                        mock.patch.object(idgen, "new_task_id", side_effect=reached):
                    try:
                        call()
                    except ImplementationReached:
                        continue
                    except SystemExit as exc:
                        self.fail(f"зерно: {self.seed}; {label}: отказ при прямом "
                                  f"вызове под ролью: {exc.code}")
                    self.fail(f"зерно: {self.seed}; {label}: не дошёл до lease/id")


class InternalRefusalsTest(SchemaTmpRootTest):
    def test_ac7_internal_refusals_still_fire(self):
        """Внутренние отказы `answer`, `notes`, `pool_seal` под ролью срабатывают.

        Сценарий: шаг роли с маркером зовёт `answer.cmd_answer` в `in_dev`,
        `notes.cmd_note(["--flush"])` и `pool_seal.restore_pool_if_missing`
        напрямую, минуя диспетчер — каждый отказывает текстом о роли.

        Ловит мутацию: внутренний рубеж снят как «дублирующий» отказ
        диспетчера — `notes.cmd_note` под ролью завершается успешно.
        """
        seed = new_seed()
        role = f"role_{random.Random(seed).randrange(1 << 30):x}"
        with tempfile.TemporaryDirectory() as fake_home:
            env = {"HOME": fake_home, config.ARTEL_ROLE_ENV: role}
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(Path, "home", return_value=Path(fake_home)):
                with mock.patch.object(store, "db", return_value=object()), \
                        mock.patch.object(store, "resolve_task_id",
                                          side_effect=lambda conn, task: task), \
                        mock.patch.object(answer.lease, "run_locked",
                                          side_effect=lambda conn, task, sid, fn: fn(sid)), \
                        mock.patch.object(store, "get_task",
                                          return_value={"state": "in_dev",
                                                        "branch": "task/test"}):
                    with self.assertRaises(SystemExit) as refused_answer:
                        answer.cmd_answer(TASK, "/tmp/no-answer")
                    self.assertIn("роли", str(refused_answer.exception),
                                  f"зерно: {seed}; answer")

                with self.assertRaises(SystemExit) as refused_note:
                    notes.cmd_note(["--flush"])
                self.assertIn("роли", str(refused_note.exception), f"зерно: {seed}; note")

                refusal = pool_seal.restore_pool_if_missing(None)
                self.assertIsInstance(refusal, str, f"зерно: {seed}; pool_seal")
                self.assertIn("роли", refusal, f"зерно: {seed}; pool_seal")


if __name__ == "__main__":
    unittest.main()
