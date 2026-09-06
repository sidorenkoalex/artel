"""Общая песочница приёмочных тестов 01M1NGFK3N6MRMYGCC09H975V3 (Канарейка
v2, часть 2: привязка пина, триггер doctor, откат пина).

Расширяет `tests.sandbox.RealGitSandbox` (настоящий git-репозиторий
пульта, ветка main, один коммит) настоящим `origin`-remote локально на
диске — тот же приём, что `tasks/01M1H224X5A8W159MKF1Q24R5Y/
acceptance_tests/_sandbox.py::ArtelSelfTargetSandbox` (Stage1 pin-update),
плюс три расширения под эту задачу:

1. `merge_commit` — заводит настоящие merge-коммиты в main (`git merge
   --no-ff`) и синхронизирует их с `origin`: способ построить «N мержей
   main» из ANSWER-1 п.3 (`git rev-list --count --merges S..T`) реальной
   git-историей, не подделкой счётчика. Синхронизация с origin делает
   настоящий `git fetch` внутри `pin.cmd_pin_update` безопасным no-op —
   тест не зависит от того, вычисляет ли guard возраст относительно
   аргумента `sha` или относительно локального HEAD (ANSWER-1 не
   уточняет порядок «до fetch» буквально до байта реализации): в этой
   песочнице оба совпадают, потому что origin всегда синхронен с main.

2. `insert_run` — обёртка над `store.insert_canary_run` с расширенной
   ANSWER-1 п.2 сигнатурой (`main_sha=`, `verdict=`) и управляемым
   `created_at`: `store.now()` — секундная точность (`orchestrator/
   store.py::now`), две вставки одного теста получили бы ОДИНАКОВЫЙ
   `created_at` — «самый свежий по created_at» (ANSWER-1 п.5, AC-6) стал
   бы недетерминированным. Тест берёт время под свой контроль прямым
   `UPDATE` сразу после вставки.

3. `all_checks` — `doctor.all_checks(store.db())` с блокировкой
   настоящего `claude` (живой смоук CLI, `doctor.live_smoke`) тем же
   приёмом, что уже проверен в `tasks/T051/acceptance_tests/
   test_ac5_doctor_warns_lagging_branch.py` (git проходит по-настоящему
   через `_claude_only_run`/`_claude_only_popen`, `claude` — нет) —
   несколько приёмочных планок (`tasks/01M1P9QAG65GVF69YJEV0V18D9/
   acceptance_tests/_sandbox.py`, `tasks/T044/...`, `tasks/T049/...`)
   явно избегают `doctor.all_checks()` из-за этой цены; T051 показывает
   рабочий способ её обезвредить вместо того чтобы гадать имя ещё не
   существующей внутренней check-функции этой задачи. Ambient-токен
   (`CLAUDE_CODE_OAUTH_TOKEN`) снимает зависимость `check_token` от
   `roles.yaml`/keychain, которых эта лёгкая песочница не сеет.
"""
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, doctor, store  # noqa: E402
from tests.sandbox import RealGitSandbox, resilient_tmp_cleanup  # noqa: E402

_REAL_RUN = subprocess.run
_REAL_POPEN = subprocess.Popen


def _claude_only_run(args, **kwargs):
    """Фейк только для `claude ...`; git и остальное — в настоящий
    `subprocess.run` (образец `tests/sandbox.py::claude_only_run`,
    `tasks/T051/.../test_ac5_doctor_warns_lagging_branch.py`)."""
    if args and args[0] == "claude":
        return subprocess.CompletedProcess(list(args), 1, "", "")
    return _REAL_RUN(args, **kwargs)


def _claude_only_popen(cmd, *args, **kwargs):
    """То же для `Popen` (`doctor.live_smoke` зовёт именно его) —
    настоящий `subprocess.run` внутри себя вызывает `Popen`, поэтому
    безусловный мок `Popen` уронил бы и git, пропущенный `_claude_only_run`
    в настоящий `run` (тот же порядок рассуждений, что T051)."""
    if cmd and cmd[0] == "claude":
        raise FileNotFoundError("claude")
    return _REAL_POPEN(cmd, *args, **kwargs)


class CanaryPinSandbox(RealGitSandbox):
    """`self.root` — пульт (main + один коммит) + настоящий bare `self.origin`."""

    def setUp(self):
        super().setUp()
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.origin)], check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.origin))
        self._merge_seq = 0
        self._run_seq = 0
        self.push_main_to_origin()

    # --- origin --------------------------------------------------------

    def push_main_to_origin(self) -> None:
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def origin_main_sha(self) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.origin), "rev-parse",
             "refs/heads/" + config.MAIN_BRANCH],
            capture_output=True, text=True)
        return res.stdout.strip() if res.returncode == 0 else ""

    # --- история ---------------------------------------------------------

    def root_head_sha(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def merge_commit(self, count: int = 1, prefix: str = "merge") -> str:
        """Заводит `count` настоящих merge-коммитов в main, возвращает
        итоговый HEAD; синхронизирует origin после каждой партии (см.
        докстринг класса, п.1)."""
        for _ in range(count):
            self._merge_seq += 1
            branch = f"{prefix}-{self._merge_seq}"
            self.checkout(branch, create=True)
            fname = f"{branch}.txt"
            (self.root / fname).write_text("x\n", encoding="utf-8")
            self.git("add", fname)
            self.git("commit", "-q", "-m", f"работа {branch}")
            self.checkout(config.MAIN_BRANCH)
            self.git("merge", "--no-ff", "-q", "-m", f"merge {branch}", branch)
        if count:
            self.push_main_to_origin()
        return self.root_head_sha()

    def branch_off_without_merging(self, name: str = "abandoned") -> str:
        """Коммит на ветке, НИКОГДА не мержащейся в main — не предок
        HEAD; сценарий «зелёный прогон не на предке T» (ANSWER-1 п.3)."""
        self.checkout(name, create=True)
        (self.root / f"{name}.txt").write_text("x\n", encoding="utf-8")
        self.git("add", f"{name}.txt")
        self.git("commit", "-q", "-m", f"тупиковая ветка {name}")
        sha = self.root_head_sha()
        self.checkout(config.MAIN_BRANCH)
        return sha

    # --- журнал канарейки (canary_runs) -----------------------------------

    def insert_run(self, main_sha: str, verdict: str,
                   created_at: str | None = None, **overrides) -> str:
        """Строка `canary_runs` (ANSWER-1 п.2, сигнатура `store.
        insert_canary_run` расширена `main_sha=`/`verdict=`); возвращает
        `run_stamp` заведённой строки."""
        self._run_seq += 1
        conn = store.db()
        run_stamp = overrides.pop(
            "run_stamp", f"202601{self._run_seq:02d}T000000Z")
        title = overrides.pop("title", "canary-template")
        task_id = overrides.pop("task_id", f"CANARY{self._run_seq:03d}")
        kwargs = dict(steps=3, cost_usd=0.5, review_iterations=0,
                     escalations=0, outcome="killed", expected_escalation=None,
                     actual_escalation=False, marker_mismatch=False)
        kwargs.update(overrides)
        store.insert_canary_run(conn, run_stamp, title, task_id,
                                main_sha=main_sha, verdict=verdict, **kwargs)
        if created_at is not None:
            conn.execute(
                "UPDATE canary_runs SET created_at=? WHERE run_stamp=? "
                "AND task_id=?", (created_at, run_stamp, task_id))
            conn.commit()
        return run_stamp

    # --- журнал шагов (steps), pin-update/pin --to ------------------------

    def steps_mentioning(self, *substrings: str, action: str | None = None) -> list:
        """Записи журнала отката/обновления пина (`task_id=config.
        PIN_UPDATE_JOURNAL_TASK_ID`, тот же способ проверки, что `tasks/
        01M1H224X5A8W159MKF1Q24R5Y/.../test_ac14_pin_update_command.py::
        steps_mentioning`), опционально отфильтрованные по `action`."""
        conn = store.db()
        rows = conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=?",
            (config.PIN_UPDATE_JOURNAL_TASK_ID,)).fetchall()
        return [r for r in rows
               if (action is None or r["action"] == action)
               and all(s in (r["detail"] or "") for s in substrings)]

    # --- doctor без реального claude ----------------------------------------

    def all_checks(self) -> list:
        with mock.patch.dict("os.environ",
                             {"CLAUDE_CODE_OAUTH_TOKEN": "test-token"}), \
             mock.patch.object(doctor.subprocess, "run",
                               side_effect=_claude_only_run), \
             mock.patch.object(doctor.subprocess, "Popen",
                               side_effect=_claude_only_popen):
            return doctor.all_checks(store.db())


if __name__ == "__main__":
    import unittest
    unittest.main()
