"""Общая песочница приёмочных тестов 01M2DTT96FS25SHXP0HDTWARQH (модель
роли из roles.yaml — флаг `--model` в команде шага и `model=` в
журнале).

Не копия `disk_backed_*`/`advance_from_in_dev` из `tests/sandbox.py`
(test-authoring, «Лёгкая песочница переходов») — это не песочница
переходов FSM: задача остаётся в прежнем состоянии, проверяется один
прогон `runner.cmd_run` (argv команды и записи журнала шага). Общий код
между файлами этой планки — сборка временного `roles.yaml` с
управляемым полем `model` и учёт денег шага (`FakeProc`/события потока),
которые нужны и файлу про argv, и файлу про журнал.
"""
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import catalog, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import (DeveloperBriefTmpRootTest, FakeProc, FakeStream,  # noqa: E402
                           capture_new_task_id, event, fake_git,
                           sync_spec_from_worktree)

_REAL_ROLES_TEXT = (_REPO_ROOT / "roles.yaml").read_text(encoding="utf-8")

# Артефакт, обязательный на диске рабочего каталога роли этого состояния
# (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3, требование 3) — без него успешная
# попытка (rc=0) честно ретраится вместо одного тихого прогона, которого
# ждут тесты этой планки (см. `tests/test_agent_prompt.py::_STEP_ARTIFACT`).
_STEP_ARTIFACT = {"in_dev": "PLAN.md", "review": "REVIEW.md"}
_STATE_FOR_ROLE = {"developer": "in_dev", "reviewer": "review"}


def result_event(usd=0.5, **fields) -> str:
    """Финальное событие запуска: в нём стоимость и, опционально, usage
    (см. `tests/test_step_cost.py::result_event` — та же форма)."""
    return event(type="result", subtype="success", is_error=False,
                result="готово", total_cost_usd=usd, **fields)


def assistant_event(usage=None) -> str:
    """Промежуточное событие потока: usage — в `message.usage` (см.
    `tests/test_step_cost.py::assistant_event`)."""
    message = {"role": "assistant", "content": [{"type": "text", "text": "работаю"}]}
    if usage is not None:
        message["usage"] = usage
    return event(type="assistant", message=message)


def timeout_then_killed_proc(lines) -> mock.Mock:
    """Процесс, чей `wait()` сперва бросает `TimeoutExpired` — таймаут
    шага без ретрая (см. `tests/test_step_cost.py::timeout_then_killed_proc`
    — та же форма, `agent_pid` мока не `int`, group-kill не трогается)."""
    proc = mock.Mock(stdout=FakeStream(lines))
    proc.wait.side_effect = [
        runner.subprocess.TimeoutExpired(cmd="claude", timeout=config.AGENT_TIMEOUT_SEC),
        -9,
    ]
    return proc


def roles_yaml_text(model_by_role: dict) -> str:
    """Реальный текст `roles.yaml` репозитория с полем `model:`,
    вставленным сразу под заголовком названной роли (или без вставки,
    если значение — `None`) — `skills:`/`token_slot:` реальных ролей не
    трогаются, от них зависит остальной путь шага (текст промпта, слот
    keychain)."""
    lines = _REAL_ROLES_TEXT.splitlines(keepends=True)
    for role, model in model_by_role.items():
        anchor = f"  {role}:\n"
        for i, line in enumerate(lines):
            if line == anchor:
                if model is not None:
                    lines[i] = line + f"    model: {model}\n"
                break
        else:
            raise AssertionError(f"роль {role!r} не найдена в roles.yaml")
    return "".join(lines)


class ModelFlagPipelineTest(DeveloperBriefTmpRootTest):
    """Один прогон `runner.cmd_run` (роль developer/reviewer) с
    управляемым `roles.yaml`: argv команды и журнал шага доступны через
    `argv_of`/`journal_details`/`all_step_rows`."""

    def setUp(self):
        super().setUp()
        # ДО `cmd_new` (SPEC T048): сам заводит ветку/worktree через
        # `gitcmd`, без фейка ушёл бы в реальный репозиторий пульта.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает id ULID (SPEC T094, требование 2) — забираем
        # реальный через `capture_new_task_id`, не `self.capture`.
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Модель роли")
        sync_spec_from_worktree(self.TASK)

        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def set_roles_yaml(self, **model_by_role) -> None:
        """Подменяет `config.ROLES` на временный файл: реальный
        `roles.yaml`, с `model:` заданной/снятой у названных ролей."""
        path = self.root / "roles-under-test.yaml"
        path.write_text(roles_yaml_text(model_by_role), encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_state(self, role: str) -> str:
        state = _STATE_FOR_ROLE[role]
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()
        marker = _STEP_ARTIFACT[state]
        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / marker).write_text("маркер\n", encoding="utf-8")
        return state

    def run_agent(self, role: str, proc=None) -> mock.Mock:
        """Прогон шага роли `role` с подменённым процессом; возвращает
        мок `spawn_agent`. `proc` — по умолчанию один успешный (rc=0)
        FakeProc с финальным событием без usage."""
        self.set_state(role)
        if proc is None:
            proc = FakeProc([result_event(usd=0.1)])
        with mock.patch.object(runner, "spawn_agent", return_value=proc) as popen:
            self.capture(runner.cmd_run, self.TASK)
        return popen

    def argv_of(self, popen: mock.Mock) -> list:
        return popen.call_args.args[0]

    def journal_details(self, action: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action)).fetchall()]

    def all_step_rows(self) -> list:
        return store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
