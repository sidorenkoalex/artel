"""Общие помощники планки: шпион процессов git, головы ссылки документов,
команда пульта вокруг тела сценария.

Песочница — настоящий git (`origin_real_git`, `tests/fixtures.py`): пульт —
`root`, его bare-`origin` — `add_origin()`. Шпион стоит на `subprocess.run`,
которым `gitcmd` запускает каждый git; подкоманда берётся сквозь пары
`-C <клон>` (`tests.sandbox.strip_dash_c`). Отправка ссылки документов —
вызов `git push …` с аргументом `refs/artifacts/<id>…`.

Утверждений здесь нет: помощники только готовят и наблюдают.
"""
import contextlib
import subprocess
from types import SimpleNamespace
from unittest import mock

from orchestrator import artifact_branch, config, gitcmd, lease, store
from tests.sandbox import strip_dash_c

TASK = "01PLANKONEPUSHTASK0A"
TASK_B = "01PLANKONEPUSHTASK0B"
SID = "sess-plank-one-push"

PUSH_OK = "push артефактной ветки"
PUSH_FAILED = "push артефактной ветки FAILED"

# Состояния цепочки переходов сценария (`store.set_state` со сверкой).
STATES = ("in_dev", "verifying", "review", "merge_gate")


@contextlib.contextmanager
def git_spy(answer=None):
    """Подкоманды git (без `-C <путь>`) всех процессов внутри блока.

    `answer(argv, sub)` — подменный исход вызова (или исключение); `None` —
    настоящий git."""
    calls = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            sub = strip_dash_c(cmd[1:])
            calls.append(sub)
            if answer is not None:
                res = answer(list(cmd), sub)
                if res is not None:
                    return res
        return real_run(cmd, *args, **kwargs)

    with mock.patch.object(gitcmd.subprocess, "run", side_effect=spy):
        yield calls


def is_ref_push(sub, task_id: str = "") -> bool:
    """Вызов — отправка ссылки документов (задачи `task_id`, если задан)."""
    if not sub or sub[0] != "push":
        return False
    prefix = artifact_branch.branch_name(task_id) if task_id else "refs/artifacts/"
    return any(str(arg).startswith(prefix) for arg in sub[1:])


def ref_pushes(calls, task_id: str = "") -> list:
    return [c for c in calls if is_ref_push(c, task_id)]


def fake_ok(argv) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(argv, 0, "", "")


def doc_rel(task_id: str, name: str) -> str:
    return f"tasks/{task_id}/{name}"


def commit(task_id: str, name: str, target: str | None = None) -> str:
    """Коммит документов задачи — единым узлом записи `commit_files`."""
    return artifact_branch.commit_files(
        task_id, {doc_rel(task_id, name): f"{name} {task_id}\n"},
        f"{task_id}: {name}", target=target)


def commit_fixed(task_id: str, name: str) -> str:
    """Коммит документов и его фиксация, как на чекпоинте шага: следующий
    переход не примет голову за сдвинутую мимо пульта."""
    sha = commit(task_id, name)
    store.record_fixation(store.db(), task_id)
    return sha


def area(task_id: str, body):
    """`body()` телом команды пульта: `lease.run_locked` по задаче."""
    return lease.run_locked(store.db(), task_id, SID, lambda sid: body())


def step(task_id: str, index: int) -> None:
    """Переход `STATES[index] -> STATES[index + 1]` (строка паспорта)."""
    store.set_state(store.db(), task_id, STATES[index + 1], "fsm",
                    expected_state=STATES[index], detail="сценарий планки")


def origin_head(sb, ref: str, bare=None) -> str:
    out = sb.git("ls-remote", str(bare or sb.bare), ref).split()
    return out[0] if out else ""


def local_head(sb, ref: str, repo=None) -> str:
    args = ("-C", str(repo)) if repo is not None else ()
    return sb.git(*args, "for-each-ref", "--format=%(objectname)", ref).strip()


def journal(task_id: str, action: str) -> list:
    return [r["detail"] for r in store.task_steps(store.db(), task_id)
            if r["action"] == action]


def add_task(task_id: str) -> str:
    """Строка задачи артели в `in_dev` и первый коммит её ссылки (вне
    команды — отправлен сразу)."""
    store.insert_task(store.db(), task_id, "Задача планки", STATES[0],
                      f"task/{task_id.lower()}-x", config.DEFAULT_TARGET, 25.0)
    return commit(task_id, "SPEC.md")


def make_synced(sb) -> SimpleNamespace:
    """Пульт с bare-origin; ссылка документов `TASK` совпадает с origin."""
    sb.add_origin()
    sb.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    head0 = add_task(TASK)
    return SimpleNamespace(sb=sb, ref=artifact_branch.branch_name(TASK),
                           head0=head0, branch=f"task/{TASK.lower()}-x")


def lags(env, ref: str = "") -> tuple:
    """(голова в origin, локальная голова) ссылки `ref` (по умолчанию `TASK`)."""
    ref = ref or env.ref
    return origin_head(env.sb, ref), local_head(env.sb, ref)
