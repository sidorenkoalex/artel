"""Юнит-тесты запуска шага роли по абсолютному пути из резолва манифеста
и предполётной сверки модели роли с версией CLI (SPEC
01M2XJKV84SQ9VEVR0VNVKDNGJ, требования 1, 3, 4; SPEC
01M3009Y9AGGY6ZCFA7H1HJ1TD, требования 5, 9, 10 — AC-7, AC-11..AC-13).

Постоянная копия покрытия приёмочной планки задачи (`tasks/
01M2XJKV84SQ9VEVR0VNVKDNGJ/acceptance_tests/`) — та планка уходит при
уборке каталога задачи, этот файл остаётся регрессией `tests/`. Песочница
— та же, что у `tests/test_runner_role_model.py::ModelFlagJournalTest`:
настоящий путь запуска шага (`runner.cmd_run`/`auto.cmd_auto`), подменён
только процесс агента (`runner.spawn_agent`), версия CLI задаётся ответом
подпроцесса `claude --version` (подмена `subprocess.run` по базовому
имени argv[0] — `stack.installed_cli_version` зовёт CLI литералом, шаг
роли — абсолютным путём, обе формы обязаны попадать в заглушку).

Минимум версии CLI с 20.09 приходит из каталога `models.yaml`, а не из
таблицы `stack.MODEL_MIN_CLI_VERSION` (та удалена): песочница подменяет
каталог временным файлом, а модель шага задаёт ярусом роли и локальным
слоем. Модель ВНЕ каталога — теперь отказ до старта агента, а не
предупреждение «модель не в таблице совместимости» с запуском как есть
(требование 10).
"""
import io
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (auto, catalog, config, failure_classification,  # noqa: E402
                          gitcmd, runner, stack, store)
from tests.sandbox import (DeveloperBriefTmpRootTest, FakeProc,  # noqa: E402
                           capture_new_task_id, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git, is_claude_call,
                           sync_spec_from_worktree)
from tests.test_runner_role_model import _roles_yaml_text  # noqa: E402

TABLE_MODEL = "claude-fable-5-1"
UNKNOWN_MODEL = "claude-test-model-vne-kataloga"
TIER = "strong"


def _catalog_text(model: str, minimum: str) -> str:
    """Каталог из одной модели: минимум версии CLI — единственное, что
    сценариям этого файла нужно от каталога."""
    return f"""providers:
  claude:
    cli: claude
    min_cli_version: 1.0.0
    cost_from_cli: true
    models:
      {model}:
        min_cli_version: {minimum}
        status: supported
        list_price_usd_per_mtok:
          input: 5.0
          output: 25.0
          cache_write: 6.25
          cache_read: 0.50
        price_date: 2026-09-20
"""
UNSUPPORTED_OUTPUT = (
    "API Error: 400 {\"type\":\"error\",\"error\":{\"type\":"
    "\"invalid_request_error\",\"message\":\"This Claude Code version "
    "does not support this model; version 2.1.251 or newer is required\"}}\n")


def _claude_version_run(text: str, inner):
    def run(args, *rest, **kwargs):
        if is_claude_call(args):
            return subprocess.CompletedProcess(args, 0,
                                               f"{text} (Claude Code)\n", "")
        return inner(args, *rest, **kwargs)
    return run


def _write_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


class _StepSandbox(DeveloperBriefTmpRootTest):
    """Один шаг роли `developer` во временном каталоге с управляемыми
    `roles.yaml`, таблицей совместимости и ответом `claude --version`."""

    ROLE = "developer"

    def setUp(self):
        super().setUp()
        self.patch(gitcmd, "git", fake_git)
        self.patch(gitcmd, "show", disk_backed_show)
        self.patch(gitcmd, "ls_tree_files", disk_backed_ls_tree_files)
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Модель и путь")
        sync_spec_from_worktree(self.TASK)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()
        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")

        self.pauses = []
        self.patch(runner.time, "sleep", self.pauses.append)
        self.patch(auto.time, "sleep", self.pauses.append)
        self.patch(runner.keychain, "token", lambda slot: "tok-test")
        preflight = mock.patch("orchestrator.doctor.preflight_checks",
                               lambda role, target: [])
        preflight.start()
        self.addCleanup(preflight.stop)
        self.set_catalog(TABLE_MODEL, "2.1.251")
        self.exit_message = None
        self.spawn = None

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    # Имя файла каталога под тестом — РОВНО `models.yaml`, отличается
    # только каталог: наследники этой песочницы (планка приёмки
    # 01M3009Y9AGGY6ZCFA7H1HJ1TD) уводят пути слоёв в свой временный
    # корень, отыскивая их обходом `vars(config)` по имени файла. Имя
    # вида `models-under-test.yaml` такому обходу невидимо, и наследник
    # молча оставался бы на каталоге ЭТОГО файла — сценарий проверял бы
    # не то, что написано в нём (модель `experimental` стартовала бы как
    # `supported`).
    CATALOG_DIR = "catalog-under-test"

    def set_catalog(self, model: str, minimum: str) -> None:
        """Каталог моделей под тестом — временный файл вместо боевого."""
        path = self.root / self.CATALOG_DIR / "models.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_catalog_text(model, minimum), encoding="utf-8")
        self.patch(config, "MODELS", path)

    def set_model(self, model) -> None:
        """Модель шага: ярус у роли (`roles.yaml`) плюс модель яруса в
        локальном слое — цепочка целиком, как её видит `run`."""
        path = self.root / "roles-under-test.yaml"
        path.write_text(_roles_yaml_text(self.ROLE, TIER), encoding="utf-8")
        self.patch(config, "ROLES", path)
        config.MODELS_LOCAL.write_text(f"tiers:\n  {TIER}: {model}\n",
                                       encoding="utf-8")

    def set_no_tier(self) -> None:
        """Роль без `model_tier` — сценарий требования 5."""
        path = self.root / "roles-under-test.yaml"
        path.write_text(_roles_yaml_text(self.ROLE, None), encoding="utf-8")
        self.patch(config, "ROLES", path)

    def set_cli_version(self, text: str) -> None:
        self.patch(subprocess, "run", _claude_version_run(text, subprocess.run))

    def run_step(self, *attempts) -> str:
        """`attempts` — пары `(rc, строки вывода)` по одной на попытку;
        без аргументов — одна успешная. `sys.exit` отказа перехватывается
        в `self.exit_message` — как его увидел бы `auto`."""
        if not attempts:
            attempts = ((0, ["готово\n"]),)
        procs = [FakeProc(lines, rc) for rc, lines in attempts]
        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=procs) as spawn:
            with redirect_stdout(buf):
                try:
                    runner.cmd_run(self.TASK)
                except SystemExit as exc:
                    self.exit_message = str(exc)
        self.spawn = spawn
        return buf.getvalue()

    def run_auto(self) -> str:
        def fresh_proc(*args, **kwargs):
            return FakeProc(["готово\n"], 0)

        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=fresh_proc) as spawn:
            with redirect_stdout(buf):
                try:
                    auto.cmd_auto(self.TASK)
                except SystemExit as exc:
                    self.exit_message = str(exc)
        self.spawn = spawn
        return buf.getvalue()

    def argv(self) -> list:
        return list(self.spawn.call_args.args[0])

    def journal_rows(self) -> list:
        return store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()

    def entries_containing(self, needle: str) -> list:
        return [f"{r['action']}: {r['detail']}" for r in self.journal_rows()
                if needle in f"{r['action']}: {r['detail']}"]

    def actions(self) -> list:
        return [r["action"] for r in self.journal_rows()]

    def state(self) -> str:
        return store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (self.TASK,)).fetchone()["state"]


class StepCommandArgv0Test(_StepSandbox):
    """Требование 1 (AC-1/AC-3): argv[0] шага — абсолютный путь из резолва
    манифеста, не литерал, ищущийся по PATH роли в момент запуска."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        self.set_cli_version("9.9.9")

    def test_argv0_is_the_absolute_path_from_the_manifest_resolve(self):
        """Ловит мутацию: `role_cmd()` снова начинается литералом `claude`
        (или путём не из `shutil.which`) — argv[0] расходится с резолвом
        манифеста либо перестаёт быть абсолютным."""
        self.run_step()

        argv0 = self.argv()[0]
        self.assertEqual(argv0, shutil.which("claude"))
        self.assertTrue(Path(argv0).is_absolute(), argv0)
        self.assertEqual(self.argv()[1:3], ["-p", "--permission-mode"])
        self.assertEqual(self.argv()[-2:], ["--model", TABLE_MODEL])

    def test_declared_binary_wins_over_a_namesake_in_another_tools_dir(self):
        """Сценарий затенения (инцидент 06.09): каталог `gh` с одноимённым
        `claude` стоит в PATH роли РАНЬШЕ каталога резолва.

        Ловит мутацию: argv[0] собирается именем или поиском по PATH роли
        — запускается тёзка из каталога `gh`, а не бинарник резолва."""
        resolved_dir = self.root / "resolved-bin"
        other_dir = self.root / "gh-bin"
        resolved_dir.mkdir()
        other_dir.mkdir()
        _write_executable(resolved_dir / "claude")
        _write_executable(other_dir / "gh")
        namesake = _write_executable(other_dir / "claude")
        path = os.pathsep.join([str(resolved_dir), str(other_dir),
                                os.environ.get("PATH", "")])

        with mock.patch.dict(os.environ, {"PATH": path}):
            role_path = runner.role_env(self.ROLE, self.TASK)["PATH"]
            self.run_step()
            argv0 = self.argv()[0]

        dirs = role_path.split(os.pathsep)
        self.assertLess(dirs.index(str(other_dir)), dirs.index(str(resolved_dir)))
        self.assertEqual(argv0, str(resolved_dir / "claude"))
        self.assertNotEqual(argv0, str(namesake))


class ModelBelowCliMinimumTest(_StepSandbox):
    """Требование 3 (AC-6/AC-7): модель из таблицы, CLI ниже минимума."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        self.set_cli_version("2.1.250")

    def test_step_refuses_before_the_agent_without_retries_or_escalation(self):
        """Ловит мутацию: сверка стоит после старта агента либо оформлена
        провалом попытки — агент стартует, шаг крутит попытки с паузами и
        уводит задачу в `escalated`; либо запись журнала не называет
        модель и обе версии."""
        self.run_step()

        self.spawn.assert_not_called()
        named = self.entries_containing(stack.MODEL_UNSUPPORTED_PREFIX)
        self.assertEqual(len(named), 1, self.journal_rows())
        self.assertIn(f"{stack.MODEL_UNSUPPORTED_PREFIX}: {TABLE_MODEL}", named[0])
        self.assertIn("требует claude ≥ 2.1.251", named[0])
        self.assertIn("установлен 2.1.250", named[0])
        self.assertIn(runner.MODEL_UNSUPPORTED_REFUSAL_ACTION, self.actions())
        self.assertNotIn("agent run retry", self.actions())
        self.assertNotIn("agent run started", self.actions())
        self.assertEqual(self.pauses, [])
        self.assertEqual(self.state(), "in_dev")
        self.assertIn(stack.CLI_UPGRADE_HINT, self.exit_message)

    def test_auto_stops_on_the_refusal_and_prints_the_upgrade_hint(self):
        """Ловит мутацию: отказ оформлен `return`, а не `sys.exit` — `auto`
        не замечает его и крутит шаги до потолка; либо подсказка потеряна."""
        out = self.run_auto()

        self.spawn.assert_not_called()
        self.assertIn(stack.CLI_UPGRADE_HINT, out)
        self.assertEqual(len(self.entries_containing(stack.MODEL_UNSUPPORTED_PREFIX)), 1)
        self.assertNotIn(f"лимит {config.AUTO_MAX_STEPS} шагов исчерпан", out)

    def test_minimum_comes_from_the_catalog_not_from_a_literal(self):
        """Ловит мутацию: число `2.1.251` повторено по месту сравнения —
        подмена записи каталога вердикт не меняет."""
        self.set_catalog(TABLE_MODEL, "2.1.0")

        self.run_step()

        self.assertEqual(self.spawn.call_count, 1)
        self.assertEqual(self.entries_containing(stack.MODEL_UNSUPPORTED_PREFIX), [])


class ModelOutsideCatalogTest(_StepSandbox):
    """Требование 10 (AC-13): модели в каталоге нет — отказ до старта
    агента, а не предупреждение с запуском как есть (поведение до
    20.09)."""

    def setUp(self):
        super().setUp()
        self.set_model(UNKNOWN_MODEL)

    def test_unknown_model_refuses_before_the_agent_without_probing_cli(self):
        """Ловит мутацию: модель вне каталога запускается «как есть»
        (прежнее `warn` «модель не в таблице совместимости») — шаг уходил
        бы в CLI без минимума версии и без тарифа; либо ради заведомого
        отказа всё равно заводится `claude --version`."""
        calls = []

        def spy_run(args, *rest, **kwargs):
            if is_claude_call(args):
                calls.append(list(args))
                return subprocess.CompletedProcess(args, 0, "1.0.0\n", "")
            return spy_run.inner(args, *rest, **kwargs)
        spy_run.inner = subprocess.run
        self.patch(subprocess, "run", spy_run)

        self.run_step()

        self.spawn.assert_not_called()
        named = self.entries_containing(UNKNOWN_MODEL)
        self.assertTrue(named, self.journal_rows())
        self.assertIn(runner.MODEL_UNRESOLVED_REFUSAL_ACTION, self.actions())
        self.assertEqual(self.state(), "in_dev")
        self.assertIn(UNKNOWN_MODEL, self.exit_message)
        self.assertEqual(calls, [],
                         "`claude --version` ради заведомого отказа не нужен")


class RoleWithoutTierTest(_StepSandbox):
    """Требование 5 (AC-7): agent-роль без `model_tier` — отказ до старта
    агента."""

    def setUp(self):
        super().setUp()
        self.set_no_tier()

    def test_step_refuses_before_the_agent_and_names_the_field(self):
        """Ловит мутацию: роль без яруса идёт на дефолт CLI либо на
        «первый попавшийся» ярус — агент стартовал бы без явной модели,
        ровно то поведение, которое требование 5 снимает."""
        self.run_step()

        self.spawn.assert_not_called()
        self.assertIn(runner.MODEL_UNRESOLVED_REFUSAL_ACTION, self.actions())
        self.assertIn("model_tier", self.exit_message)
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.pauses, [])

    def test_auto_stops_on_the_refusal(self):
        """Ловит мутацию: отказ оформлен `return`, а не `sys.exit` —
        `auto` не замечает его и крутит шаги до потолка."""
        out = self.run_auto()

        self.spawn.assert_not_called()
        self.assertIn("model_tier", out)
        self.assertNotIn(f"лимит {config.AUTO_MAX_STEPS} шагов исчерпан", out)


class TierWithoutModelTest(_StepSandbox):
    """Требование 8 (AC-11): ярус роли не назван в `tiers:` локального
    слоя."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        config.MODELS_LOCAL.write_text(f"tiers:\n  cheap: {TABLE_MODEL}\n",
                                       encoding="utf-8")

    def test_step_refuses_before_the_agent(self):
        """Ловит мутацию: ярус без модели резолвится «первой попавшейся»
        моделью каталога — пульт молча ушёл бы не на ту модель."""
        self.run_step()

        self.spawn.assert_not_called()
        self.assertIn(runner.MODEL_UNRESOLVED_REFUSAL_ACTION, self.actions())
        self.assertIn(TIER, self.exit_message)


class BrokenLocalLayerTest(_StepSandbox):
    """Требование 8 (AC-11, AC-12): локальный слой есть, но не
    разбирается — отказ до старта агента, а не деградация к `None`."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        # Переопределение без цен: слой читается, схема — нет. Именно
        # этот класс ошибки `_resolved_role_model` гасит до `None`
        # (штатно — потому что отказ уже случился раньше), и проверяется
        # здесь, что раньше он ДЕЙСТВИТЕЛЬНО случается.
        config.MODELS_LOCAL.write_text(
            f"tiers:\n  {TIER}: {TABLE_MODEL}\n"
            f"overrides:\n  {TABLE_MODEL}:\n    source: без цен\n",
            encoding="utf-8")

    def test_unparsed_local_layer_refuses_before_the_agent(self):
        """Ловит мутацию: ошибка СХЕМЫ локального слоя ловится только
        деградацией к `None` в `_resolved_role_model`, а предполёт её не
        видит — шаг уходил бы в CLI без `--model` (дефолт CLI) при
        сломанном слое, то есть fail-closed цепочки держался бы лишь на
        тех ошибках, что отдаёт `resolve_role`."""
        self.run_step()

        self.spawn.assert_not_called()
        self.assertIn(runner.MODEL_UNRESOLVED_REFUSAL_ACTION, self.actions())
        self.assertIn(str(config.MODELS_LOCAL), self.exit_message)
        self.assertEqual(self.state(), "in_dev")

    def test_resolved_role_model_degrades_to_none_without_raising(self):
        """Ловит мутацию: деградация `_resolved_role_model` заменена на
        проброс исключения — сборка argv/журнала попытки падала бы
        трейсбеком вместо отказа, оформленного предполётом."""
        self.assertIsNone(runner._resolved_role_model(self.ROLE))


class ExplicitModelFlagTest(_StepSandbox):
    """AC-12: агент роли не стартует без явного `--model`."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        self.set_cli_version("9.9.9")

    def test_agent_starts_only_with_an_explicit_model_flag(self):
        """Ловит мутацию: `--model` перестал попадать в argv (модель
        «по умолчанию CLI») — инвариант требования 9 нарушен молча, и
        шаг пошёл бы на модель, о которой пульт ничего не знает."""
        self.run_step()

        argv = self.argv()
        self.assertEqual(argv.count("--model"), 1, argv)
        self.assertEqual(argv[-2:], ["--model", TABLE_MODEL])

    def test_no_step_of_this_file_ever_spawns_without_the_flag(self):
        """Ловит мутацию: отказы неразрешимой цепочки заменены на запуск
        без `--model` — проверка «агент не стартовал» в соседних классах
        могла бы стать зелёной по другой причине, эта фиксирует связку:
        либо флаг есть, либо агента нет."""
        self.set_model(UNKNOWN_MODEL)

        self.run_step()

        self.spawn.assert_not_called()


class ModelUnsupportedAttemptTest(_StepSandbox):
    """Требование 4 (AC-9): CLI отверг модель уже в попытке агента."""

    def setUp(self):
        super().setUp()
        self.set_model(TABLE_MODEL)
        self.set_cli_version("9.9.9")

    def test_attempt_is_not_repeated_and_the_step_refuses_by_name(self):
        """Ловит мутацию: класс заведён, но `_run_attempts` о нём не знает
        — шаг доигрывает `config.AGENT_ATTEMPTS` попыток с паузами и уводит
        задачу в `escalated`; либо отказ оформлен безымянной эскалацией."""
        attempts = ((1, [UNSUPPORTED_OUTPUT]),) * config.AGENT_ATTEMPTS

        self.run_step(*attempts)

        self.assertEqual(self.spawn.call_count, 1)
        self.assertEqual(self.pauses, [])
        self.assertNotIn("agent run retry", self.actions())
        self.assertEqual(self.state(), "in_dev")
        named = self.entries_containing(stack.MODEL_UNSUPPORTED_PREFIX)
        self.assertTrue(named, self.journal_rows())
        self.assertIn(runner.MODEL_UNSUPPORTED_REFUSAL_ACTION, self.actions())
        self.assertIn("требует claude ≥ 2.1.251", named[-1])
        self.assertIn("установлен 9.9.9", named[-1])
        self.assertIn(stack.CLI_UPGRADE_HINT, self.exit_message)
        classified = [r["detail"] for r in self.journal_rows()
                      if r["action"] == "agent failure classified"]
        self.assertEqual(len(classified), 1)
        self.assertIn(failure_classification.CLASS_LABELS[
            failure_classification.MODEL_UNSUPPORTED_CLASS], classified[0])

    def test_other_api_errors_still_retry_as_system_candidates(self):
        """Контроль (инвариант 3 не тронут): прочий «API Error:» остаётся
        «системным кандидатом» — попытки идут до лимита с бэкоффом связки,
        задача уходит в `escalated`.

        Ловит мутацию: новая проверка написана по подстроке «API Error»/
        «model» и забирает себе весь класс 1 — транзиентные отказы
        перестают ретраиться."""
        attempts = ((1, ["API Error: 500 Internal Server Error\n"]),) * config.AGENT_ATTEMPTS

        self.run_step(*attempts)

        self.assertEqual(self.spawn.call_count, config.AGENT_ATTEMPTS)
        self.assertEqual(len(self.pauses), config.AGENT_ATTEMPTS - 1)
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.entries_containing(stack.MODEL_UNSUPPORTED_PREFIX), [])


if __name__ == "__main__":
    unittest.main()
