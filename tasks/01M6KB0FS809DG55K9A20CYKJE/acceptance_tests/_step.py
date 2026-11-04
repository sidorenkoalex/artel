"""Общий код планки: песочница шага роли и подмены точек SPEC.

Песочница — `DeveloperBriefTmpRootTest` из `tests/sandbox.py` с
git-заглушкой, токеном и пустым предполётом (тот же набор, что у
`tests/test_agent_log.py::CmdRunLoggingTest`): `runner.cmd_run` доходит
до запуска агента, сам агент — `FakeProc` подменённого
`runner.spawn_agent`.
"""
import contextlib
import os
import random
import signal
import subprocess
from collections import Counter
from pathlib import Path
from unittest import mock

from orchestrator import artifact_branch, catalog, config, gitcmd, runner, store
from tests.sandbox import (DeveloperBriefTmpRootTest, FakeProc,
                           capture_new_task_id, fake_git,
                           sync_spec_from_worktree)

WARNING_COUNT = "счёт процессов пользователя недоступен: "


def refusal_text(count: int, limit: int) -> str:
    return f"запас процессов пользователя исчерпан: {count} из {limit}"


@contextlib.contextmanager
def step_sandbox(state: str = "in_dev"):
    """(песочница, id задачи) — задача в `state` с PLAN.md в каталоге документов."""
    box = DeveloperBriefTmpRootTest()
    box.setUp()
    previous = signal.getsignal(signal.SIGTERM)
    patchers = [
        mock.patch.object(gitcmd, "git", fake_git),
        mock.patch.object(runner.keychain, "token", lambda slot: "tok-test"),
        mock.patch("orchestrator.doctor.preflight_checks",
                   lambda role, target: []),
        mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
    ]
    for patcher in patchers:
        patcher.start()
    try:
        box.capture(catalog.cmd_init)
        _, task = capture_new_task_id(catalog.cmd_new, "Предел процессов шага")
        sync_spec_from_worktree(task)
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task))
        conn.commit()
        tdir = artifact_branch.docs_dir(task, config.DEFAULT_TARGET)
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")
        yield box, task
    finally:
        for patcher in reversed(patchers):
            patcher.stop()
        signal.signal(signal.SIGTERM, previous)
        box.doCleanups()


def read_maxproc(value):
    """Подмена `runner._read_maxprocperuid` значением `value`."""
    return mock.patch.object(runner, "_read_maxprocperuid", return_value=value)


def process_count(**kwargs):
    """Подмена `runner._user_process_count` (`return_value=` или `side_effect=`)."""
    return mock.patch.object(runner, "_user_process_count", **kwargs)


def nproc_rlimit(soft, hard):
    """Подмена `resource.getrlimit`: для `RLIMIT_NPROC` — (soft, hard)."""
    import resource
    real = resource.getrlimit

    def fake(which):
        if which == resource.RLIMIT_NPROC:
            return soft, hard
        return real(which)

    return mock.patch.object(resource, "getrlimit", fake)


def subprocess_answers(answers: dict):
    """Подмена `subprocess.run`: команде с именем-ключом (`ps`, `sysctl`)
    отвечает значение (`CompletedProcess`-заготовка `(rc, stdout)` либо
    исключение), прочие команды идут в прежний `subprocess.run`."""
    real = subprocess.run

    def fake(argv, *args, **kwargs):
        name = Path(str(argv[0] if isinstance(argv, (list, tuple)) else
                        str(argv).split()[0])).name
        if name in answers:
            answer = answers[name]
            if isinstance(answer, BaseException):
                raise answer
            rc, out = answer
            text = kwargs.get("text") or kwargs.get("universal_newlines") \
                or kwargs.get("encoding")
            return subprocess.CompletedProcess(
                argv, rc, out if text else out.encode(), "" if text else b"")
        return real(argv, *args, **kwargs)

    return mock.patch.object(subprocess, "run", fake)


def failing_agent():
    """Подмена `runner.spawn_agent`: каждая попытка падает rc=1 — шаг
    исчерпывает все `config.AGENT_ATTEMPTS` попыток (успешная попытка
    после упавшей в песочнице не выходит: аварийный чекпоинт уносит
    PLAN.md из рабочего каталога, и rc=0 тоже ретраится)."""
    return mock.patch.object(runner, "spawn_agent",
                             side_effect=lambda cmd, **kw: FakeProc(["сбой\n"], 1))


def one_attempt_agent():
    return mock.patch.object(runner, "spawn_agent",
                             return_value=FakeProc(["шаг\n"], 0))


def journal(task: str) -> list:
    return list(store.task_steps(store.db(), task))


def journal_text(rows) -> str:
    return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}" for r in rows)


def actions(rows) -> Counter:
    return Counter((r["actor"], r["action"]) for r in rows)


def seeded(seed=None) -> random.Random:
    seed = random.randrange(1 << 30) if seed is None else seed
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    rng.seed_value = seed
    return rng
