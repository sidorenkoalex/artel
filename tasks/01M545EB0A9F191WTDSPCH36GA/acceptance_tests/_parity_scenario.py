"""Сценарий шага роли для сверки с main: запускается отдельным процессом
`python3 _parity_scenario.py <дерево> <параметры JSON>` на дереве кода
(база ветки задачи либо рабочая копия) и печатает JSON — что шаг передал в
запуск агента: argv, окружение, промпт.

Дерево — первым в `sys.path`: `orchestrator` и `tests.sandbox` берутся из
него, а не из рабочей копии, где лежит этот файл. Сценарий пользуется
только поверхностью, которая есть и в базе ветки: `LightTransitionSandbox`,
`use_role_map`, `use_catalog_fixture`, `seed_developer_brief_fixtures`,
`runner.cmd_run` с подменённым `runner.spawn_agent`.

Параметры: `state` — состояние шага задачи; `provider` — `claude` либо
`codex` (обе агентские роли шага — на нём); `target` — проект задачи
(`artel` либо имя внешнего проекта, объявляемого в `targets.yaml`
песочницы с `project_skills: []`).
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TREE = Path(sys.argv[1]).resolve()
PARAMS = json.loads(sys.argv[2])
sys.path.insert(0, str(TREE))

from orchestrator import (catalog, config, keychain, models, runner,  # noqa: E402
                          store)
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_TIER,  # noqa: E402
                           FakeProc, LightTransitionSandbox, TimeWithSleep,
                           capture_new_task_id, event,
                           seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

CLAUDE, CODEX = "claude", "codex"
STUB_BIN = "/artel-test-stub-bin"
STEP_ROLES = {"tests_writing": "test_author", "review": "reviewer"}
ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""
RESULT = {}


class Scenario(LightTransitionSandbox):

    def patch(self, target, attr, value):
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def setUp(self):
        super().setUp()
        shutil.copytree(TREE / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        shutil.copytree(TREE / "skills", self.root / "skills",
                        dirs_exist_ok=True)
        seed_developer_brief_fixtures(self.root)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY",
                     "GIT_CONFIG_NOSYSTEM"):
            os.environ.pop(name, None)
        self.patch(runner, "time", TimeWithSleep(lambda _: None))
        self.patch(config, "AGENT_ATTEMPTS", 1)
        self.patch(keychain, "token", lambda slot: "tok-test")
        previous_which, previous_run = shutil.which, subprocess.run

        def which(name, *args, **kwargs):
            if name in (CLAUDE, CODEX, "gh"):
                return f"{STUB_BIN}/{name}"
            return previous_which(name, *args, **kwargs)

        def run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and cmd:
                argv = [str(part) for part in cmd]
                tool = Path(argv[0]).name
                if tool == CODEX and "login" in argv and "status" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "", "Logged in using ChatGPT\n")
                if tool == CODEX and "--version" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "codex-cli 0.155.1\n", "")
                if tool == CLAUDE and "--version" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "2.1.300 (Claude Code)\n", "")
            return previous_run(cmd, *args, **kwargs)

        self.patch(shutil, "which", which)
        self.patch(subprocess, "run", run)
        self.use_catalog_fixture()
        if PARAMS["provider"] == CODEX:
            tier = next(t for t in models.TIERS if t != FIXTURE_TIER)
            self.use_role_map(
                roles={role: {"provider": CODEX, "model_tier": tier}
                       for role in STEP_ROLES.values()},
                tiers={tier: FIXTURE_CODEX_MODEL},
                allow_experimental=(FIXTURE_CODEX_MODEL,))
        else:
            self.use_role_map()

    def test_step(self):
        conn = store.db()
        target = PARAMS["target"]
        task = self.TASK
        if target != config.DEFAULT_TARGET:
            text = config.TARGETS.read_text(encoding="utf-8")
            config.TARGETS.write_text(
                text.rstrip("\n") + "\n" + ENTRY.format(
                    name=target, base=config.MAIN_BRANCH), encoding="utf-8")
            _, task = capture_new_task_id(catalog.cmd_new, "Задача проекта")
            store.update_task(conn, task, target=target)
        store.update_task(conn, task, state=PARAMS["state"], paused=0)
        sync_spec_from_worktree(task)
        calls = []

        def spawn(cmd, *args, **kwargs):
            calls.append({"argv": [str(part) for part in cmd],
                          "env": dict(kwargs.get("env") or {}),
                          "prompt": kwargs["stdin"].read()})
            return FakeProc([event(type="result", subtype="success",
                                   is_error=False, result="готово",
                                   total_cost_usd=0.1)])

        out = io.StringIO()
        refusal = ""
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(out):
            try:
                runner.cmd_run(task)
            except SystemExit as exc:
                refusal = str(exc.code)
        RESULT.update({"root": str(self.root), "task": task,
                       "calls": calls[:1], "refusal": refusal,
                       "stdout": out.getvalue()})


if __name__ == "__main__":
    suite = unittest.TestSuite([Scenario("test_step")])
    with contextlib.redirect_stdout(io.StringIO()):
        outcome = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    errors = [text for _, text in outcome.errors + outcome.failures]
    print(json.dumps({"result": RESULT, "errors": errors}, ensure_ascii=False))
