"""Команда шага роли на Codex открывает на запись каталог `suite-run` и
ничего сверх нужного; шаг роли на Claude прежний.

Группа: долгоживущий

Красен до реализации: `providers/codex.py::command` несёт единственный `--add-dir` — каталог документов задачи, каталога `config.LOGS / "suite-run"` в argv шага Codex нет (AC-1); AC-2, AC-3 и AC-7 держат прежние свойства (запрещённых корней среди `--add-dir` нет, `--sandbox workspace-write` и каталог документов на месте, шаг Claude без новых корней и переменных) и зелены с рождения.

Публичная поверхность, которую читает файл (стенд — тот же, что у
долгоживущего сторожа каталога документов в команде шага):

- шаг роли — `runner.cmd_run(<id>)` с подменённым `runner.spawn_agent`:
  argv запуска агента — первый позиционный аргумент, окружение —
  именованный `env=`; первый вызов и есть команда шага;
- каталог документов задачи — `config.PROJECTS / <проект> / "tasks" /
  <id>`, проект задачи артели — `config.DEFAULT_TARGET`;
- каталог `suite-run` — `config.LOGS / "suite-run"`, он же родитель файла
  замка `suite_lock.path()`; кэш итогов полного прогона —
  `acceptance.suite_results_dir()`; БД пульта — `config.DB`.

Значения `--add-dir` читаются в раздельной форме (`--add-dir <путь>`) и
слитной (`--add-dir=<путь>`) и сравниваются после `os.path.realpath`:
временный каталог macOS живёт под символической ссылкой `/var` ->
`/private/var`. Каталог, ОБЪЕМЛЮЩИЙ запрещённый путь (например, `.artel/`
над БД), открыл бы его на запись так же, как сам путь, — поэтому AC-2
отклоняет и предков запрещённых путей.

Роль шага (developer в `in_dev` либо test_author в `tests_writing`)
выбирается случайно; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, keychain, models, runner, store
from orchestrator import suite_lock
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_TIER, FakeProc,
                           LightTransitionSandbox, TimeWithSleep, event,
                           seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

#: Корень репозитория — источник `templates`/`skills` для брифа шага.
REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE, CODEX = "claude", "codex"
#: Каталог-заглушка объявленных CLI: `runner.declared_tool_path` отдаёт
#: argv[0] абсолютным путём из резолва `shutil.which`.
STUB_BIN = "/artel-test-stub-bin"
ADD_DIR = "--add-dir"
SANDBOX_FLAG = "--sandbox"
SANDBOX_VALUE = "workspace-write"
EXEC = "exec"
#: Роль шага и состояние, в котором `run` её запускает.
STEP_ROLES = (("developer", "in_dev"), ("test_author", "tests_writing"))


def real(path) -> str:
    return os.path.realpath(str(path))


def add_dir_values(argv: list, start: int = 0) -> list:
    """Значения каждого `--add-dir` в `argv[start:]` — в раздельной форме
    и слитной."""
    found = []
    for i in range(start, len(argv)):
        token = str(argv[i])
        if token == ADD_DIR and i + 1 < len(argv):
            found.append(str(argv[i + 1]))
        elif token.startswith(ADD_DIR + "="):
            found.append(token[len(ADD_DIR) + 1:])
    return found


def is_within(path: str, ancestor: str) -> bool:
    """`path` совпадает с `ancestor` или лежит под ним (оба — realpath)."""
    return path == ancestor or path.startswith(ancestor.rstrip(os.sep) + os.sep)


class StepSuiteDirsSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов с брифом шага: CLI агента подменён
    (`runner.spawn_agent`), `which`/`--version` обоих CLI отвечают
    заглушкой, предполёт окружения пуст, слот keychain отдаёт токен."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills",
                        dirs_exist_ok=True)
        seed_developer_brief_fixtures(self.root)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
            os.environ.pop(name, None)

        previous_which = shutil.which
        previous_run = subprocess.run

        def which(name, *args, **kwargs):
            if name in (CLAUDE, CODEX, "gh"):
                return f"{STUB_BIN}/{name}"
            return previous_which(name, *args, **kwargs)

        def run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and cmd:
                argv = [str(part) for part in cmd]
                tool = Path(argv[0]).name
                if tool == CODEX and "--version" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "codex-cli 0.155.1\n", "")
                if tool == CLAUDE and "--version" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "2.1.300 (Claude Code)\n", "")
            return previous_run(cmd, *args, **kwargs)

        for target, attr, value in ((shutil, "which", which),
                                    (subprocess, "run", run),
                                    (runner, "time", TimeWithSleep(lambda _: None)),
                                    (keychain, "token", lambda slot: "tok-test")):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        preflight = mock.patch("orchestrator.doctor.preflight_checks",
                               lambda role, target, **step: [])
        preflight.start()
        self.addCleanup(preflight.stop)
        self.use_catalog_fixture()

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}. {extra}"

    def use_provider(self, role: str, provider: str) -> None:
        """Карта исполнителей сценария: роль шага — на `provider`. Codex
        получает свой ярус с моделью раздела `codex` каталога-фикстуры."""
        if provider == CLAUDE:
            self.use_role_map()
            return
        tier = next(t for t in models.TIERS if t != FIXTURE_TIER)
        self.use_role_map(roles={role: {"provider": CODEX, "model_tier": tier}},
                          tiers={tier: FIXTURE_CODEX_MODEL},
                          allow_experimental=(FIXTURE_CODEX_MODEL,))

    def docs_dir(self) -> Path:
        return config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.TASK

    def suite_dir(self) -> Path:
        return config.LOGS / "suite-run"

    def launched(self, provider: str) -> dict:
        """Шаг случайной роли на `provider`: argv и окружение первого
        запуска агента; агент обязан быть запущен CLI этого провайдера."""
        role, state = self.rnd.choice(STEP_ROLES)
        self.use_provider(role, provider)
        conn = store.db()
        store.update_task(conn, self.TASK, state=state, paused=0)
        sync_spec_from_worktree(self.TASK)
        self.docs_dir().mkdir(parents=True, exist_ok=True)
        calls = []

        def spawn(cmd, *args, **kwargs):
            calls.append((list(cmd), kwargs.get("env")))
            return FakeProc([event(type="result", subtype="success",
                                   is_error=False, result="готово",
                                   total_cost_usd=0.1)])

        refusal, buf = None, io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(buf):
            try:
                runner.cmd_run(self.TASK)
            except SystemExit as exc:
                refusal = str(exc.code)
        why = f"роль {role}, провайдер {provider}"
        self.assertTrue(calls, self.note(
            f"{why}: агент не запущен: {refusal}\n{buf.getvalue()}"))
        argv, env = calls[0]
        argv = [str(token) for token in argv]
        self.assertEqual(Path(argv[0]).name, provider,
                         self.note(f"{why}: argv {argv}"))
        return {"argv": argv, "env": env or {}, "why": why, "role": role}

    def codex_step(self) -> dict:
        """Шаг роли на Codex; значения `--add-dir` после подкоманды `exec`."""
        step = self.launched(CODEX)
        argv = step["argv"]
        self.assertIn(EXEC, argv, self.note(f"нет подкоманды exec: {argv}"))
        step["opened"] = [real(v) for v in
                          add_dir_values(argv, argv.index(EXEC) + 1)]
        return step


class CodexStepOpensSuiteDirTest(StepSuiteDirsSandbox):

    def test_ac1_codex_step_adds_suite_run_dir(self):
        """Шаг роли на Codex открывает каталог `suite-run` отдельным `--add-dir`.

        Сценарий: карта исполнителей держит роль шага (случайно developer
        либо test_author) на codex; `run` задачи песочницы. В argv первого
        запуска агента после `exec` среди значений `--add-dir` есть каталог
        `config.LOGS / "suite-run"` — он же родитель файла замка
        `suite_lock.path()`; каталог документов задачи остаётся отдельной
        парой.

        Ловит мутацию: каталог замка не выдан — в argv шага Codex только
        `--add-dir <каталог документов>`, и `suite-run` из шага падает
        PermissionError на `lock.json`; выдан не тот каталог (файл замка
        вместо его каталога, `config.LOGS / "suite-run" / <id>`) либо оба
        каталога склеены в одно значение флага."""
        step = self.codex_step()
        opened = step["opened"]
        suite_dir = real(self.suite_dir())
        self.assertEqual(real(suite_lock.path().parent), suite_dir,
                         self.note("файл замка вне каталога suite-run"))
        self.assertIn(suite_dir, opened, self.note(
            f"{step['why']}: нет «{ADD_DIR} {suite_dir}»: {step['argv']}"))
        self.assertIn(real(self.docs_dir()), opened, self.note(
            f"{step['why']}: нет пары каталога документов: {step['argv']}"))


class CodexStepOpensNothingElseTest(StepSuiteDirsSandbox):

    def test_ac2_codex_step_opens_no_pult_root_artel_logs_results_or_db(self):
        """Среди `--add-dir` шага Codex нет корней пульта, логов, итогов и БД.

        Сценарий: шаг роли (случайно developer либо test_author) на codex;
        ни одно значение `--add-dir` argv не равно и не объемлет корень
        пульта (`config.ROOT`), каталог `.artel/` целиком, каталог логов
        `config.LOGS`, кэш итогов `acceptance.suite_results_dir()`, файл БД
        `config.DB` или его каталог.

        Ловит мутацию: выдан каталог логов пульта `config.LOGS` вместо
        выделенного `config.LOGS / "suite-run"` (роль могла бы подменить
        итог полного прогона в `fullsuite-results` или чужие логи); выдан
        `.artel/` целиком или каталог БД ради записи журнала; выдан корень
        пульта."""
        step = self.codex_step()
        forbidden = {
            "корень пульта": real(config.ROOT),
            "каталог .artel/": real(config.ROOT / ".artel"),
            "каталог логов config.LOGS": real(config.LOGS),
            "кэш итогов полного прогона": real(acceptance.suite_results_dir()),
            "БД пульта": real(config.DB),
            "каталог БД пульта": real(Path(config.DB).parent),
        }
        for value in step["opened"]:
            for name, path in forbidden.items():
                with self.subTest(value=value, forbidden=name):
                    self.assertFalse(is_within(path, value), self.note(
                        f"{step['why']}: «{ADD_DIR} {value}» открывает "
                        f"{name} ({path}): {step['argv']}"))


class CodexStepKeepsSandboxTest(StepSuiteDirsSandbox):

    def test_ac3_codex_step_keeps_workspace_write_and_docs_dir(self):
        """Шаг Codex по-прежнему под `--sandbox workspace-write` с каталогом документов.

        Сценарий: шаг роли (случайно developer либо test_author) на codex;
        в argv после `exec` стоит `--sandbox workspace-write` (раздельно
        или слитно) и `--add-dir <каталог документов задачи>`.

        Ловит мутацию: ради записи в `.artel/logs` песочница ослаблена до
        `danger-full-access` (или флаг `--sandbox` снят); пара каталога
        документов заменена парой `suite-run` вместо добавления к ней."""
        step = self.codex_step()
        argv = step["argv"]
        tail = argv[argv.index(EXEC) + 1:]
        pairs = list(zip(tail, tail[1:]))
        self.assertTrue((SANDBOX_FLAG, SANDBOX_VALUE) in pairs
                        or f"{SANDBOX_FLAG}={SANDBOX_VALUE}" in tail,
                        self.note(f"{step['why']}: нет «{SANDBOX_FLAG} "
                                  f"{SANDBOX_VALUE}»: {argv}"))
        self.assertIn(real(self.docs_dir()), step["opened"], self.note(
            f"{step['why']}: нет «{ADD_DIR} <каталог документов>»: {argv}"))


class ClaudeStepUnchangedTest(StepSuiteDirsSandbox):

    def test_ac7_claude_step_has_no_new_add_dir_or_env(self):
        """Шаг роли на Claude: единственный `--add-dir` — каталог документов, окружение без `suite-run`.

        Сценарий: шаг роли (случайно developer либо test_author) на
        claude; значения `--add-dir` argv — ровно каталог документов
        задачи; ни имя, ни значение переменной окружения процесса роли не
        называет каталог `suite-run` или каталог логов `config.LOGS`.

        Ловит мутацию: каталог `suite-run` добавлен в argv шага общей
        сборкой для всех провайдеров, а не только Codex — у Claude
        появляется второй `--add-dir`; каталог передан ролям переменной
        окружения с путём к нему."""
        step = self.launched(CLAUDE)
        opened = [real(v) for v in add_dir_values(step["argv"])]
        self.assertEqual(opened, [real(self.docs_dir())], self.note(
            f"{step['why']}: --add-dir шага Claude: {step['argv']}"))
        marks = {str(self.suite_dir()), real(self.suite_dir()),
                 str(config.LOGS), real(config.LOGS)}
        for name, value in step["env"].items():
            for mark in marks:
                with self.subTest(env=name, mark=mark):
                    self.assertNotIn(mark, str(value), self.note(
                        f"{step['why']}: переменная {name}={value}"))


if __name__ == "__main__":
    unittest.main()
