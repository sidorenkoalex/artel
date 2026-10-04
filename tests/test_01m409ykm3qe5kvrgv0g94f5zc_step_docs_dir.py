"""Команда шага роли открывает каталог документов задачи на запись, а
рабочим каталогом шага остаётся рабочая копия кода задачи — у обоих
провайдеров (claude и codex).

Группа: долгоживущий

Красен до реализации: ни `providers/claude.py::command`, ни `providers/codex.py::command` не несут флага `--add-dir`, и `runner` его не добавляет — argv шага без `--add-dir <каталог документов>` (AC-4, AC-5); AC-6 (cwd — рабочая копия кода) держится уже сегодня и в связке с ними зеленеет вместе с флагом.

Публичная поверхность, которую читает файл:

- шаг роли — `runner.cmd_run(<id>)` с подменённым `runner.spawn_agent`:
  argv запуска агента — первый позиционный аргумент, рабочий каталог —
  именованный `cwd=`; первый вызов и есть команда шага;
- каталог документов задачи — `config.PROJECTS / <проект> / "tasks" /
  <id>` (то есть `.artel/projects/<проект>` и в нём каталог задачи по её
  номеру), проект задачи артели — `config.DEFAULT_TARGET`;
- рабочая копия кода задачи — то, что отдаёт `workspace.ensure`
  (песочница `LightTransitionSandbox` подменяет его на `self.wt_path`).

«`exec --add-dir <каталог>`» критерия AC-5 читается как «флаг `--add-dir`
подкоманды `exec`»: пара `--add-dir <каталог>` стоит ПОСЛЕ `exec`, а все
глобальные флаги (`--disable`, `-c`) — ДО неё; место пары среди прочих
флагов подкоманды тест не навязывает. Форма `--add-dir=<каталог>` тоже
принимается. Пути сравниваются после `os.path.realpath`: временный каталог
macOS живёт под символической ссылкой `/var` -> `/private/var`.

Роль шага (developer в `in_dev` либо test_author в `tests_writing`) и
порядок провайдеров выбираются случайно; зерно печатается и входит в
текст провала.
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

from orchestrator import config, keychain, models, runner, store
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_TIER, FakeProc,
                           LightTransitionSandbox, TimeWithSleep, event,
                           seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

#: Корень репозитория — источник `templates/`/`skills/` для брифа шага.
REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE, CODEX = "claude", "codex"
#: Каталог-заглушка объявленных CLI: `runner.declared_tool_path` отдаёт
#: argv[0] абсолютным путём из резолва `shutil.which`.
STUB_BIN = "/artel-test-stub-bin"
#: Флаг каталога, открытого на запись дополнительно к рабочему.
ADD_DIR = "--add-dir"
#: Подкоманда шага Codex и его глобальные флаги (справка 0.155.1: только
#: до подкоманды).
EXEC = "exec"
GLOBAL_FLAGS = ("--disable", "-c")
#: Роль шага и состояние, в котором `run` её запускает.
STEP_ROLES = (("developer", "in_dev"), ("test_author", "tests_writing"))


def real(path) -> str:
    return os.path.realpath(str(path))


def add_dir_values(argv: list, start: int = 0) -> list:
    """(индекс, значение) каждого `--add-dir` в `argv[start:]` — в
    раздельной форме (`--add-dir <путь>`) и слитной (`--add-dir=<путь>`)."""
    found = []
    for i in range(start, len(argv)):
        token = str(argv[i])
        if token == ADD_DIR and i + 1 < len(argv):
            found.append((i, str(argv[i + 1])))
        elif token.startswith(ADD_DIR + "="):
            found.append((i, token[len(ADD_DIR) + 1:]))
    return found


class StepDocsDirSandbox(LightTransitionSandbox):
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

    def docs_dir(self, task_id: str) -> Path:
        return config.PROJECTS / config.DEFAULT_TARGET / "tasks" / task_id

    def run_step(self, role: str, state: str) -> dict:
        """Шаг `role` задачи песочницы: argv и `cwd` первого запуска агента
        (`None` — агент не запускался), отказ шага и печать."""
        conn = store.db()
        store.update_task(conn, self.TASK, state=state, paused=0)
        sync_spec_from_worktree(self.TASK)
        # Каталог документов заведён заранее: предмет файла — команда шага,
        # а не выкладка документов (её сторожат другие тесты задачи).
        self.docs_dir(self.TASK).mkdir(parents=True, exist_ok=True)
        calls = []

        def spawn(cmd, *args, **kwargs):
            calls.append((list(cmd), kwargs.get("cwd")))
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
        argv, cwd = calls[0] if calls else (None, None)
        return {"argv": argv, "cwd": cwd, "refusal": refusal,
                "output": buf.getvalue()}

    def launched(self, provider: str) -> dict:
        """Шаг случайной роли на `provider`; агент обязан быть запущен CLI
        этого провайдера."""
        role, state = self.rnd.choice(STEP_ROLES)
        self.use_provider(role, provider)
        step = self.run_step(role, state)
        why = f"роль {role}, провайдер {provider}"
        self.assertIsNotNone(step["argv"], self.note(
            f"{why}: агент не запущен: {step['refusal']}\n{step['output']}"))
        self.assertEqual(Path(step["argv"][0]).name, provider,
                         self.note(f"{why}: argv {step['argv']}"))
        step["why"] = why
        return step

    def assert_opens_docs_dir(self, step: dict, start: int = 0) -> None:
        values = add_dir_values(step["argv"], start)
        expected = real(self.docs_dir(self.TASK))
        self.assertIn(expected, [real(value) for _i, value in values],
                      self.note(f"{step['why']}: в argv нет «{ADD_DIR} "
                                f"{expected}»: {step['argv']}"))


class ClaudeStepOpensDocsDirTest(StepDocsDirSandbox):

    def test_ac4_claude_step_command_adds_docs_dir(self):
        """Шаг роли на провайдере claude открывает каталог документов задачи.

        Сценарий: карта исполнителей держит роль шага (случайно developer
        либо test_author) на claude; `run` задачи песочницы. argv первого
        запуска агента — CLI `claude`, и в нём есть флаг `--add-dir`,
        значение которого — каталог документов этой задачи.

        Ловит мутацию: `--add-dir` не добавлен в команду шага claude (роль
        теряет запись в свои артефакты); флаг добавлен с рабочей копией
        кода, с каталогом проекта без каталога задачи или с каталогом
        другой задачи — значение флага не совпадает с каталогом
        документов."""
        self.assert_opens_docs_dir(self.launched(CLAUDE))


class CodexStepOpensDocsDirTest(StepDocsDirSandbox):

    def test_ac5_codex_exec_adds_docs_dir_after_globals(self):
        """Шаг роли на провайдере codex открывает каталог документов флагом `exec`.

        Сценарий: карта исполнителей держит роль шага (случайно developer
        либо test_author) на codex с моделью раздела `codex`; `run` задачи
        песочницы. argv первого запуска агента — CLI `codex`; в нём есть
        подкоманда `exec`, после неё — `--add-dir <каталог документов
        задачи>`, а каждый глобальный флаг (`--disable`, `-c`) стоит до
        `exec`.

        Ловит мутацию: `--add-dir` не добавлен в команду codex; добавлен
        глобальным флагом до `exec` (0.155.1 его там не разбирает); добавлен
        с другим каталогом; сборка argv переставлена так, что глобальный
        флаг попал после подкоманды."""
        step = self.launched(CODEX)
        argv = [str(token) for token in step["argv"]]
        self.assertIn(EXEC, argv, self.note(f"нет подкоманды exec: {argv}"))
        exec_at = argv.index(EXEC)
        self.assert_opens_docs_dir(step, start=exec_at + 1)
        late = [token for token in argv[exec_at + 1:] if token in GLOBAL_FLAGS]
        self.assertEqual(late, [], self.note(
            f"глобальный флаг после exec: {argv}"))
        self.assertTrue(any(token in GLOBAL_FLAGS for token in argv[:exec_at]),
                        self.note(f"глобальных флагов до exec нет: {argv}"))


class StepCwdIsCodeWorktreeTest(StepDocsDirSandbox):

    def test_ac6_step_cwd_is_code_worktree_for_both_providers(self):
        """Рабочий каталог шага у обоих провайдеров — рабочая копия кода задачи.

        Сценарий: в одной песочнице шаг на claude и шаг на codex (порядок
        и роль шага — случайно). У каждого первого запуска агента `cwd=` —
        рабочая копия кода задачи (`workspace.ensure`), а не каталог
        документов задачи и не корень пульта.

        Ловит мутацию: рабочим каталогом шага сделан каталог документов
        (роль теряет код задачи) либо корень пульта; у одного из
        провайдеров `cwd` собирается иначе, чем у другого."""
        order = [CLAUDE, CODEX]
        self.rnd.shuffle(order)
        for provider in order:
            step = self.launched(provider)
            self.assertIsNotNone(step["cwd"], self.note(
                f"{step['why']}: cwd= не передан"))
            self.assertEqual(real(step["cwd"]), real(self.wt_path), self.note(
                f"{step['why']}: cwd {step['cwd']}, рабочая копия кода "
                f"{self.wt_path}, каталог документов "
                f"{self.docs_dir(self.TASK)}"))


if __name__ == "__main__":
    unittest.main()
