"""Юнит-тесты цвета CI main по первой родительской линии и его обвязки
(SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E): края `ci.main_line_status`, разбор флага
`--fixes-main`, отказ при сбое запуска guard по дереву мержа и ожидание CI
main после мержа при недоступном `gh`.

Сквозные сценарии (`approve`, `pin-update`, `doctor` на настоящем git с
подставным `gh`) — долгоживущий файл задачи
`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`; здесь — свойства, которых
он не касается. Линия коммитов и проверки — таблицей теста: `gitcmd.git`
отвечает на `rev-list`/`diff`, `ci.gh` — на `check-runs`.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, ci, config, fsm_merge_gate, gitcmd, merge_lock, store
from tests.sandbox import TmpRootTest, capture, patch_sleep, strip_dash_c


def done(name: str, conclusion: str) -> dict:
    return {"name": name, "status": "completed", "conclusion": conclusion}


class FakeLine:
    """Линия main: `commits` — от головы назад, `checks` — {sha: проверки},
    `code` — коммиты, меняющие код (остальные документные)."""

    def __init__(self, commits, checks, code=(), gh_fail=None):
        self.commits = list(commits)
        self.checks = checks
        self.code = set(code)
        self.gh_fail = gh_fail
        self.polled: list[str] = []

    def git(self, *args):
        # Сквозь `-C <клон>`: линия `main` читается в клоне артели явным
        # репозиторием (ADR-0021 п.1, этап 2).
        args = strip_dash_c(args)
        if args[:2] == ("rev-list", "--first-parent"):
            limit = int(args[2].split("=", 1)[1])
            start = self.commits.index(args[3])
            out = "\n".join(self.commits[start:start + limit])
            return subprocess.CompletedProcess(list(args), 0, out + "\n", "")
        if args[:2] == ("diff", "--name-only"):
            # Диапазон base..head по линии: код, если его меняет хоть один
            # коммит выше base до head включительно.
            base, head = args[2], args[3]
            if base.endswith("^1"):
                base = self.commits[self.commits.index(base[:-2]) + 1]
            span = self.commits[self.commits.index(head):
                                self.commits.index(base)]
            path = ("kod.py" if self.code.intersection(span)
                    else "docs/zametka.md")
            return subprocess.CompletedProcess(list(args), 0, path + "\n", "")
        return subprocess.CompletedProcess(list(args), 1, "", "не в таблице")

    def gh(self, *args, timeout=None):
        sha = args[1].split("/commits/", 1)[1].split("/", 1)[0]
        self.polled.append(sha)
        if self.gh_fail is not None:
            return subprocess.CompletedProcess(list(args), 1, "", self.gh_fail)
        runs = self.checks.get(sha, [])
        return subprocess.CompletedProcess(
            list(args), 0, json.dumps({"total_count": len(runs),
                                       "check_runs": runs}), "")

    def status(self, head=None):
        with mock.patch.object(gitcmd, "git", self.git), \
                mock.patch.object(ci, "gh", self.gh):
            return ci.main_line_status(head or self.commits[0])


def sha(n: int) -> str:
    return f"{n:040x}"


class MainLineStatusTest(unittest.TestCase):

    def test_check_skipped_on_code_commit_stops_the_walk(self):
        """Топология гейта мержа, 70 мержей подряд: голова push'а — коммит
        RETRO (документный; проверки `python`/`guard` исполнены,
        `protected-paths` пропущен — только `pull_request`), под ним снимок
        и merge-коммит с кодом без проверок. Поверх последнего мержа —
        документная заметка (`python` и `protected-paths` пропущены).

        Цвет зелёный; обход кончается на второй голове с проверками, не
        уходит к потолку.

        Ловит мутацию: класс push'а считается по диффу головы с первым
        родителем — голова RETRO документная, `protected-paths` не
        снимается и гонит опрос `gh` до потолка, исход «неизвестен».
        """
        commits, checks, code = [sha(1)], {}, set()
        checks[sha(1)] = [done("python", "skipped"),
                          done("protected-paths", "skipped"),
                          done("guard", "success")]
        for merge in range(70):
            retro, snap, merged = (sha(10 + 3 * merge + k) for k in range(3))
            commits += [retro, snap, merged]
            code.add(merged)
            checks[retro] = [done("python", "success"),
                             done("protected-paths", "skipped"),
                             done("guard", "success")]
        line = FakeLine(commits, checks, code=code)

        status = line.status()

        self.assertEqual(status.kind, ci.MAIN_GREEN, status.note)
        self.assertEqual(line.polled, commits[:5])

    def test_doc_push_keeps_check_pending_to_the_code_push(self):
        """Голова — документный push из двух коммитов поверх мержа с
        упавшим `python`: на голове `python` и `protected-paths` пропущены,
        промежуточный коммит без проверок.

        Исход — красный с коммитом мержа: документный push не снимает
        пропущенный `python` с обхода.

        Ловит мутацию: пропуск на любой голове снимает проверку с обхода
        без сверки класса push'а — документный коммит снова маскирует
        красный код под ним.
        """
        commits = [sha(i) for i in range(1, 7)]
        checks = {commits[0]: [done("python", "skipped"),
                               done("protected-paths", "skipped")],
                  commits[2]: [done("python", "failure"),
                               done("protected-paths", "skipped")],
                  commits[5]: [done("python", "success"),
                               done("protected-paths", "skipped")]}
        line = FakeLine(commits, checks, code={commits[4]})

        status = line.status()

        self.assertEqual(status.kind, ci.MAIN_RED, status.note)
        self.assertEqual(status.red_since, commits[2])

    def test_check_unresolved_within_the_cap_is_not_confirmed(self):
        """Линия длиннее потолка обхода, `python` пропущен на всех её
        документных коммитах.

        Исход — «неизвестен» с именем проверки, не зелёный.

        Ловит мутацию: проверка, не разрешившаяся за потолок, выпадает
        из цвета молча — длинная документная цепочка поверх красного кода
        снова читается зелёной.
        """
        commits = [sha(i) for i in range(1, 8)]
        checks = {c: [done("python", "skipped"), done("guard", "success")]
                  for c in commits}
        line = FakeLine(commits, checks)

        with mock.patch.object(ci, "MAIN_LINE_MAX_COMMITS", 5):
            status = line.status()

        self.assertEqual(status.kind, ci.MAIN_UNKNOWN, status.note)
        self.assertIn("python", status.note)

    def test_failure_outranks_running_check(self):
        """Голова: `guard` ещё идёт, `python` пропущен; коммит кода под ней
        — `python` упал.

        Исход — красный с коммитом падения (идущая проверка красноту не
        скрывает).

        Ловит мутацию: идущая проверка сворачивает исход в «не
        подтверждён» раньше упавшей — следующий мерж проходит поверх
        красного main.
        """
        commits = [sha(1), sha(2)]
        checks = {commits[0]: [done("python", "skipped"),
                               {"name": "guard", "status": "in_progress",
                                "conclusion": None}],
                  commits[1]: [done("python", "failure"),
                               done("guard", "success")]}

        status = FakeLine(commits, checks, code={commits[1]}).status()

        self.assertEqual(status.kind, ci.MAIN_RED, status.note)
        self.assertEqual(status.red_since, commits[1])
        self.assertIn("python=failure", status.note)

    def test_head_unknown_to_github_is_running_not_unknown(self):
        """GitHub отвечает 422 на голову (push только что, коммит ещё не
        виден).

        Исход — «идёт»: ожидание после мержа продолжает опрос.

        Ловит мутацию: 422 читается как сбой `gh` — ожидание CI новой
        головы обрывается «не дождался» на первом опросе после push.
        """
        line = FakeLine([sha(1)], {}, gh_fail="HTTP 422: No commit found")

        self.assertEqual(line.status().kind, ci.MAIN_RUNNING)

    def test_gh_failure_is_unknown(self):
        """`gh` не отвечает (не 422).

        Исход — «неизвестен» с причиной.

        Ловит мутацию: сбой `gh` даёт пустой список проверок и исход
        «идёт» — ожидание после мержа держит мьютекс до предела без
        единого ответа.
        """
        line = FakeLine([sha(1)], {}, gh_fail="gh: command not found")

        status = line.status()

        self.assertEqual(status.kind, ci.MAIN_UNKNOWN)
        self.assertIn("command not found", status.note)


class FixesMainArgTest(TmpRootTest):
    """Разбор `approve <id> <sha> --fixes-main "<основание>"` диспетчером."""

    def call(self, *args):
        argv = ["artel.py", "approve", "T001", *args]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch("orchestrator.fsm.cmd_approve") as cmd_approve:
            artel.main()
        return cmd_approve.call_args

    def test_reason_reaches_cmd_approve_and_sha_stays_positional(self):
        """`approve <id> <sha> --fixes-main "<основание>"` и тот же флаг без
        sha.

        sha — второй позиционный (либо пуст), основание — `fixes_main`.

        Ловит мутацию: флаг или его основание разбирается как sha (либо
        флаг не доходит до `fsm.cmd_approve`) — `approve` сверяет с
        фиксацией строку «--fixes-main», а исключение для чинящей main
        задачи не срабатывает.
        """
        for argv, expected_sha in (
                (["abcdef1234", "--fixes-main", "чиню README"], "abcdef1234"),
                (["--fixes-main", "чиню README"], None)):
            with self.subTest(argv=argv):
                args, kwargs = self.call(*argv)
                self.assertEqual(args[1], expected_sha)
                self.assertEqual(kwargs.get("fixes_main"), "чиню README")

    def test_flag_without_reason_is_refused(self):
        """`--fixes-main` последним аргументом либо с пустым основанием.

        Именованный отказ до исполнения.

        Ловит мутацию: флаг без основания принят — сверка красного main
        снята без следа в журнале.
        """
        for tail in (["--fixes-main"], ["--fixes-main", "  "]):
            with self.subTest(tail=tail), self.assertRaises(SystemExit) as exit_:
                self.call("abcdef1234", *tail)
            self.assertIn("--fixes-main требует основание", str(exit_.exception))


class GuardAllLaunchTest(unittest.TestCase):

    def tree(self, guard_text: str | None) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "tasks").mkdir()
        if guard_text is not None:
            (root / "scripts").mkdir()
            (root / "scripts" / "guard.py").write_text(guard_text, encoding="utf-8")
        return root

    def test_crashing_guard_is_a_violation(self):
        """`scripts/guard.py` дерева мержа падает без строки нарушений.

        Это нарушение с кодом и хвостом вывода — мерж отказан, а не пропущен.

        Ловит мутацию: ненулевой код без разобранных строк нарушений
        читается как «нарушений нет» — сломанный guard пропускает любой
        снимок в main.
        """
        tree = self.tree("raise SystemExit('guard сломан')\n")

        violations = fsm_merge_gate._guard_all_violations(tree)

        self.assertTrue(violations)
        self.assertIn("guard сломан", violations[0])

    def test_tree_without_guard_is_not_checked(self):
        """В дереве мержа нет `scripts/guard.py` (дерево не пульта).

        Сверки нет (`None`), отказа нет.

        Ловит мутацию: отсутствующий guard читается как сбой запуска —
        мерж в песочнице без кода пульта (и у внешнего дерева) отказывает.
        """
        self.assertIsNone(fsm_merge_gate._guard_all_violations(self.tree(None)))

    def test_task_retro_does_not_hide_snapshot_violation(self):
        """Снимок задачи несёт посторонний файл планки; guard не сканирует
        планку задачи, у которой есть `docs/retro/<id>.md` (закрытая
        история) — здесь guard подменён ровно этим правилом.

        Мерж отказан: guard видит дерево мержа без RETRO самой задачи.

        Ловит мутацию: guard по дереву мержа зовётся после генерации RETRO
        задачи — её RETRO скрывает посторонний файл снимка, мерж проходит
        (возврат 02.10 со стороны пульта, зерна 808019665/2803227082).
        """
        scratch = self.tree(None)
        retro = scratch / "docs" / "retro" / "T001.md"

        def write_retro(*args, **kwargs):
            retro.parent.mkdir(parents=True)
            retro.write_text("RETRO\n", encoding="utf-8")

        def guard_skipping_closed(tree):
            return [] if retro.exists() else [
                "tasks/T001/acceptance_tests/fixture.json: посторонний файл"]

        # Контекст артели — по признаку проекта (ADR-0021 п.1, этап 2).
        ctx = mock.Mock(path=config.ROOT, target=config.DEFAULT_TARGET)
        with mock.patch.object(fsm_merge_gate, "_overlay_artifact_snapshot"), \
                mock.patch.object(fsm_merge_gate, "_guard_task_root_or_refuse"), \
                mock.patch.object(fsm_merge_gate, "_drop_scratch_worktree"), \
                mock.patch.object(gitcmd, "head_sha", return_value=sha(1)), \
                mock.patch.object(store, "journal"), \
                mock.patch.object(fsm_merge_gate.fsm_postmerge,
                                  "_regenerate_and_commit_map"), \
                mock.patch.object(fsm_merge_gate.fsm_postmerge,
                                  "_generate_and_commit_retro",
                                  side_effect=write_retro), \
                mock.patch.object(fsm_merge_gate, "_guard_all_violations",
                                  side_effect=guard_skipping_closed):
            with self.assertRaises(SystemExit) as exit_:
                fsm_merge_gate._publish_merge_artifacts(
                    mock.Mock(), "T001", scratch, ctx)

        self.assertIn("fixture.json", str(exit_.exception))


class AwaitMainCiUnknownTest(TmpRootTest):

    def test_unknown_status_ends_the_wait_without_sleeping(self):
        """`gh` не отвечает на опрос новой головы main.

        Исход «не дождался» записан в журнал задачи сразу, без паузы.

        Ловит мутацию: неизвестный статус опрашивается заново до
        `MAIN_CI_WAIT_LIMIT_SEC` — мьютекс мержа держится 18 минут впустую.
        """
        store.create_schema(store.db())
        store.insert_task(store.db(), "T001", "Задача", "done",
                          "task/t001-x", config.DEFAULT_TARGET, 25.0)
        unknown = ci.MainLineStatus(ci.MAIN_UNKNOWN, sha(1), [], [], "",
                                    "CI main не подтверждён: gh не ответил")
        # Контекст артели — по признаку проекта (ADR-0021 п.1, этап 2).
        ctx = mock.Mock(path=config.ROOT, target=config.DEFAULT_TARGET)

        sleep = mock.Mock()
        with mock.patch.object(ci, "main_line_status", return_value=unknown), \
                mock.patch.object(merge_lock, "touch_heartbeat"), \
                patch_sleep(fsm_merge_gate, sleep):
            out = capture(fsm_merge_gate._await_main_ci, store.db(), "T001",
                          sha(1), ctx)

        sleep.assert_not_called()
        self.assertIn("не дождался", out)
        details = [r["detail"] for r in store.task_steps(store.db(), "T001")
                   if r["action"] == fsm_merge_gate.MAIN_CI_AFTER_MERGE_ACTION]
        self.assertTrue(details and "не дождался" in details[0], details)


if __name__ == "__main__":
    unittest.main()
