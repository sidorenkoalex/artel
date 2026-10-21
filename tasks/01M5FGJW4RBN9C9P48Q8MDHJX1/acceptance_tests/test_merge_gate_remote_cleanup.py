"""Тело гейта мержа после успешного push убирает ветку задачи в `origin` проекта; до push и на «moved» — нет.

Группа: разовый

Красен до реализации: тело гейта мержа после `done` не трогает ветку задачи в `origin` — ветка остаётся, записи «уборка» нет; методы AC-7 и AC-8 держат то, чего гейт делать не должен, и зелёные с рождения.

Почему разовый: проводка проверяется вызовом закрытого тела гейта
`fsm_merge_gate._cmd_approve_merge_gate` и шпионами закрытых шагов
`_await_main_ci`/`_rebuild_core_reference` — правила долгоживущей группы
такого не допускают; свойства самой уборки (исходы, подсказки, сбои git,
условность удаления) держит долгоживущий файл задачи в `tests/`.

Тело гейта зовётся напрямую с подтверждённым CI ветки — тем же приёмом,
что `tests/test_fsm_merge_gate_done_snapshot.py` (внешний проект) и
`tests/test_plan_appendix.py::MergeAppendixTest` (артель). Хук `pre-receive`
bare-`origin` проекта пишет каждую принятую к разбору запись ссылки в журнал
событий и по флагу отклоняет удаление веток `task/*`; подставной `gh` в
начале `PATH` пишет туда же свой argv. `gitcmd.in_repo` обёрнут шпионом:
вызов записан вместе с состоянием задачи на момент вызова.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import (acceptance, artifact_branch, catalog, ci,  # noqa: E402
                          config, fsm_merge_gate, gitcmd, keychain, store)
from tests.sandbox import (RealGitSandbox, artel_target_entry,  # noqa: E402
                           capture, init_bare_origin, resilient_tmp_cleanup)

ZERO_OID = "0" * 40
CLEANUP_ACTION = "уборка"
TARGET = "extproj"
EXT_TASK = "01MRGREMOTEEXT00000001"
ART_TASK = "01MRGREMOTEART00000001"
REJECT_TEXT = "удаление ветки задачи отклонено хостингом фикстуры: "

FAKE_GH = '''#!{python}
import json, sys
with open({log!r}, "a", encoding="utf-8") as f:
    f.write(json.dumps({{"kind": "gh", "argv": sys.argv[1:]}}) + "\\n")
'''

PRE_RECEIVE = '''#!{python}
import json, os, sys
reject = os.path.exists({flag!r})
bad = []
with open({log!r}, "a", encoding="utf-8") as f:
    for line in sys.stdin:
        old, new, ref = line.split()
        f.write(json.dumps({{"kind": "push", "old": old, "new": new,
                            "ref": ref}}) + "\\n")
        if reject and new == "0" * 40 and ref.startswith("refs/heads/task/"):
            bad.append(ref)
if bad:
    sys.stderr.write({text!r} + " ".join(bad) + "\\n")
    sys.exit(1)
'''


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _has_pair(args, flag: str, value: str) -> bool:
    return any(args[i] == flag and args[i + 1] == value
               for i in range(len(args) - 1))


class GateSandboxMixin:
    """Общая обвязка: журнал событий, хук, подставной `gh`, шпионы."""

    TASK = ""

    def setup_observers(self) -> None:
        self.fixture = Path(tempfile.mkdtemp(prefix="artel-mrg-")).resolve()
        self.addCleanup(shutil.rmtree, self.fixture, ignore_errors=True)
        self.events = self.fixture / "events.jsonl"
        self.events.write_text("", encoding="utf-8")
        self.reject_flag = self.fixture / "reject-delete"
        bin_dir = self.fixture / "bin"
        bin_dir.mkdir()
        _write_executable(bin_dir / "gh", FAKE_GH.format(
            python=sys.executable, log=str(self.events)))
        self.patch_dict(os.environ, {
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")})
        self.calls = []
        self.raise_on_done_read = None
        real = gitcmd.in_repo

        def spy(repo, *args, **kwargs):
            state = store.task_state(store.db(), self.TASK)
            self.calls.append((state, tuple(args)))
            if (self.raise_on_done_read is not None and state == "done"
                    and "ls-remote" in args
                    and f"refs/heads/{self.branch}" in args):
                raise self.raise_on_done_read
            return real(repo, *args, **kwargs)

        self.patch(gitcmd, "in_repo", spy)
        self.await_ci = mock.MagicMock(wraps=fsm_merge_gate._await_main_ci)
        self.patch(fsm_merge_gate, "_await_main_ci", self.await_ci)
        self.rebuild = mock.MagicMock(
            wraps=fsm_merge_gate._rebuild_core_reference)
        self.patch(fsm_merge_gate, "_rebuild_core_reference", self.rebuild)

    def patch(self, target, attr, replacement) -> None:
        patcher = mock.patch.object(target, attr, replacement)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_dict(self, target, values) -> None:
        patcher = mock.patch.dict(target, values)
        patcher.start()
        self.addCleanup(patcher.stop)

    def install_hook(self, bare: Path) -> None:
        _write_executable(Path(bare) / "hooks" / "pre-receive",
                          PRE_RECEIVE.format(python=sys.executable,
                                             log=str(self.events),
                                             flag=str(self.reject_flag),
                                             text=REJECT_TEXT))

    def approve(self):
        """Тело гейта без перехвата исключений: (возврат, вывод)."""
        t = store.get_task(store.db(), self.TASK)
        box = {}

        def body():
            box["result"] = fsm_merge_gate._cmd_approve_merge_gate(
                store.db(), self.TASK, "merge_gate", t,
                confirmed_ci_note="зелёный (тест)")
        out = capture(body)
        return box["result"], out

    # --- наблюдения -------------------------------------------------------

    def events_list(self) -> list:
        return [json.loads(line) for line in
                self.events.read_text(encoding="utf-8").splitlines() if line]

    def deletions(self) -> list:
        return [e for e in self.events_list()
                if e["kind"] == "push" and e["new"] == ZERO_OID
                and e["ref"] == f"refs/heads/{self.branch}"]

    def origin_has(self, ref: str) -> bool:
        res = subprocess.run(["git", "--git-dir", str(self.bare_origin),
                              "for-each-ref", ref], capture_output=True,
                             text=True)
        return bool(res.stdout.strip())

    def origin_head(self, ref: str) -> str:
        res = subprocess.run(["git", "--git-dir", str(self.bare_origin),
                              "for-each-ref", "--format=%(objectname)", ref],
                             capture_output=True, text=True)
        return res.stdout.strip()

    def state(self) -> str:
        return store.task_state(store.db(), self.TASK)

    def notes(self) -> list:
        return [row["detail"] or "" for row in
                store.task_steps(store.db(), self.TASK)
                if row["action"] == CLEANUP_ACTION]

    def journal_text(self) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), self.TASK))

    def done_calls(self) -> list:
        return [args for state, args in self.calls if state == "done"]

    def printed_end(self, out: str, note: str) -> int:
        """Номер последней строки вывода, занятой исходом, напечатанным
        после отступа; провал — такого исхода нет."""
        start = 0
        while True:
            pos = out.find(note, start)
            if pos < 0:
                break
            line_start = out.rfind("\n", 0, pos) + 1
            lead = out[line_start:pos]
            if lead and not lead.strip():
                return out[:pos + len(note)].count("\n")
            start = pos + 1
        self.fail(f"исход «{note}» не напечатан с отступом:\n{out}")

    def assert_deleted_with_bounded_args(self, result, out) -> None:
        self.assertEqual(result, ("done",), f"{out}\n{self.journal_text()}")
        self.assertEqual(self.state(), "done")
        note = f"ветка origin {self.branch}: удалена"
        self.assertEqual(self.notes(), [note],
                         f"{self.journal_text()}\n{out}")
        self.printed_end(out, note)
        self.assertFalse(self.origin_has(f"refs/heads/{self.branch}"),
                         f"ветка задачи осталась в origin:\n{out}")
        self.assertTrue(self.origin_has(f"refs/artifacts/{self.TASK}"),
                        "ссылки документов нет в origin")
        calls = self.done_calls()
        reads = [a for a in calls if "ls-remote" in a
                 and f"refs/heads/{self.branch}" in a]
        deletes = [a for a in calls if "push" in a and "--delete" in a
                   and f"refs/heads/{self.branch}" in a]
        self.assertTrue(reads, f"нет ls-remote ветки после done: {calls}")
        self.assertTrue(deletes, f"нет push --delete после done: {calls}")
        for args in (reads[0], deletes[0]):
            self.assertTrue(
                _has_pair(args, "-c", "http.lowSpeedLimit=1")
                and _has_pair(args, "-c",
                              f"http.lowSpeedTime={config.GH_TIMEOUT_SEC}"),
                f"вызов без предела: {args}")


class ExternalGateSandbox(GateSandboxMixin, RealGitSandbox):
    """Задача внешнего проекта `extproj` на `merge_gate`: ветка с коммитом
    в клоне проекта, ссылка документов опубликована в его `origin`."""

    TASK = EXT_TASK

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        pult_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pult_origin, ignore_errors=True)
        init_bare_origin(pult_origin, self.git)
        self.git("remote", "add", "origin", str(pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.branch = f"task/{self.TASK.lower()}-x"
        config.TARGETS.write_text(
            "targets:\n"
            f"  {TARGET}:\n"
            "    forge: github\n"
            f"    url: http://localhost/{TARGET}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {TARGET}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")
        store.insert_task(store.db(), self.TASK, "Задача внешнего проекта",
                          "merge_gate", self.branch, TARGET,
                          config.DEFAULT_BUDGET_USD)
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.bare_origin = Path(bare_tmp.name) / "origin.git"
        init_bare_origin(self.bare_origin)
        self.clone = config.PROJECTS / TARGET / "repo"
        self.clone.mkdir(parents=True)
        self.wgit("init", "-q", "-b", config.MAIN_BRANCH)
        self.wgit("remote", "add", "origin", str(self.bare_origin))
        self.wgit("config", "user.email", "artel@example.invalid")
        self.wgit("config", "user.name", "artel tests")
        (self.clone / "marker.txt").write_text("main\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", "init")
        self.wgit("push", "-q", "origin", config.MAIN_BRANCH)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": "план\n"},
            f"{self.TASK}: план")
        self.wgit("checkout", "-q", "-b", self.branch)
        (self.clone / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.wgit("add", "feature.txt")
        self.wgit("commit", "-q", "-m", f"{self.TASK}: код фичи")
        self.patch(ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.patch(keychain, "token", lambda slot: f"tok-{slot}")
        self.setup_observers()
        self.install_hook(self.bare_origin)

    def wgit(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.clone,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)}: {res.stderr}")
        return res.stdout


class ArtelGateSandbox(GateSandboxMixin, RealGitSandbox):
    """Задача артели на `merge_gate`: ветка с коммитом в репозитории пульта
    (он же клон артели), bare-`origin` пульта синхронен с main."""

    TASK = ART_TASK

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry(base=config.MAIN_BRANCH,
                                              url="http://localhost/artel"),
            encoding="utf-8")
        self.bare_origin = self.add_synced_origin()
        capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-x"
        self.checkout(self.branch, create=True)
        (self.root / "feature.txt").write_text("код задачи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код задачи")
        self.checkout(config.MAIN_BRANCH)
        store.insert_task(store.db(), self.TASK, "Задача артели",
                          "merge_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        text = (f"---\ntask: {self.TASK}\ntype: plan\nauthor_role: developer\n"
                f"status: ready\nschema_version: 2\n---\n\n# PLAN\n\n"
                f"## Подход\n\nФикстура.\n")
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": text},
            f"{self.TASK}: PLAN.md")
        self.patch(acceptance, "run_full_suite",
                   lambda root: (True, "42 passed (тест)"))
        self.patch(ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.patch(ci, "main_line_status", lambda sha, repo=None:
                   ci.MainLineStatus(ci.MAIN_GREEN, sha, [], [], "",
                                     "зелёный (тест)"))
        self.setup_observers()
        self.install_hook(self.bare_origin)


class ArtelMergeTest(ArtelGateSandbox):

    def test_ac1_artel_merge_deletes_origin_branch(self):
        """Мерж задачи артели: ветки в `origin` пульта нет, ссылка документов на месте, одна запись «удалена», оба вызова git с пределом.

        Сценарий: тело гейта доводит задачу артели до `done` (`("done",)`).
        В bare-`origin` нет `refs/heads/<ветка>`, есть
        `refs/artifacts/<id>`; у задачи ровно одна запись «уборка» —
        «ветка origin <ветка>: удалена», она же напечатана с отступом;
        после `done` шпион видел `ls-remote … refs/heads/<ветка>` и `push …
        --delete refs/heads/<ветка>`, оба с `-c http.lowSpeedLimit=1` и `-c
        http.lowSpeedTime=<config.GH_TIMEOUT_SEC>`.

        Ловит мутацию: `_cleanup_merged_task` не зовёт новую уборку (или
        зовёт только для внешнего проекта) — ветка артели осталась в
        `origin`, записи «уборка» нет; вызовы без `-c`-пар предела.
        """
        result, out = self.approve()
        self.assert_deleted_with_bounded_args(result, out)


class ExternalMergeTest(ExternalGateSandbox):

    def test_ac1_external_merge_deletes_origin_branch(self):
        """Мерж задачи внешнего проекта: ветки в `origin` проекта нет, ссылка документов на месте, одна запись «удалена», оба вызова git с пределом.

        Сценарий: тело гейта доводит задачу проекта до `done`. Ветка
        задачи, опубликованная гейтом в bare-`origin` проекта, оттуда
        удалена; `refs/artifacts/<id>` есть; ровно одна запись «уборка»
        «ветка origin <ветка>: удалена», напечатана с отступом; после
        `done` вызовы `ls-remote` и `push … --delete` ветки несут пары
        предела.

        Ловит мутацию: новая уборка не вызвана из `_cleanup_merged_task` —
        ветка осталась в `origin` проекта; уборка ходит в `origin` пульта
        вместо клона проекта — ветка проекта осталась; вызовы без предела.
        """
        result, out = self.approve()
        self.assert_deleted_with_bounded_args(result, out)

    def test_ac4_refused_delete_task_done_ci_awaited_hint_printed(self):
        """`origin` отклоняет удаление: задача `done`, `_await_main_ci` вызван, исход «оставлено — <причина>», подсказка напечатана и не в журнале.

        Сценарий: хук bare-`origin` проекта отклоняет удаление веток
        задач. Тело гейта возвращает `("done",)`, задача `done`, шпион
        `_await_main_ci` вызван; запись «уборка» «ветка origin <ветка>:
        оставлено — <причина>»; после строки исхода — `git -C <клон> push
        --force-with-lease=refs/heads/<ветка>:<голова> origin --delete
        refs/heads/<ветка>` с головой ветки в `origin`; запись журнала
        подсказки не несёт.

        Ловит мутацию: отказ удаления поднимает исключение/`sys.exit` и
        обрывает гейт до `_await_main_ci`; подсказка не печатается или
        пишется в журнал вместе с исходом.
        """
        self.reject_flag.write_text("1", encoding="utf-8")

        result, out = self.approve()

        self.assertEqual(result, ("done",), f"{out}\n{self.journal_text()}")
        self.assertEqual(self.state(), "done")
        self.assertTrue(self.await_ci.called, "_await_main_ci не вызван")
        notes = self.notes()
        self.assertEqual(len(notes), 1, self.journal_text())
        prefix = f"ветка origin {self.branch}: оставлено — "
        self.assertTrue(notes[0].startswith(prefix), notes[0])
        self.assertTrue(notes[0][len(prefix):].strip(), notes[0])
        head = self.origin_head(f"refs/heads/{self.branch}")
        self.assertTrue(head, "ветка удалена вопреки отказу хука")
        end = self.printed_end(out, notes[0])
        tail = f" push --force-with-lease=refs/heads/{self.branch}:{head} " \
               f"origin --delete refs/heads/{self.branch}"
        hint_lines = [i for i, line in enumerate(out.splitlines())
                      if "git -C " in line and line.rstrip().endswith(tail)]
        self.assertTrue(hint_lines, f"нет подсказки удаления:\n{out}")
        self.assertGreater(hint_lines[-1], end, out)
        self.assertNotIn("--force-with-lease", notes[0])

    def test_ac6g_exception_in_cleanup_keeps_merge_done(self):
        """Исключение внутри новой уборки: исход «оставлено — <тип>: <текст>», подсказки нет, задача `done`, `_await_main_ci` и `_rebuild_core_reference` выполнены.

        Сценарий: шпион `gitcmd.in_repo` поднимает `RuntimeError` на
        чтении головы ветки задачи, как только задача в `done`. Тело
        гейта возвращает `("done",)` без исключения; запись «уборка»
        «ветка origin <ветка>: оставлено — RuntimeError: <текст>»; в
        выводе нет строк подсказки `git -C`; шпионы `_await_main_ci` и
        `_rebuild_core_reference` вызваны.

        Ловит мутацию: исключение не перехвачено — `RuntimeError` выходит
        из тела гейта, `_await_main_ci`/`_rebuild_core_reference` не
        вызваны; исход без имени типа; печатается подсказка.
        """
        text = "сбой фикстуры чтения головы"
        self.raise_on_done_read = RuntimeError(text)

        result, out = self.approve()

        self.assertEqual(result, ("done",), f"{out}\n{self.journal_text()}")
        self.assertEqual(self.state(), "done")
        self.assertEqual(self.notes(),
                         [f"ветка origin {self.branch}: оставлено — "
                          f"RuntimeError: {text}"], self.journal_text())
        self.assertNotIn("git -C", out, out)
        self.assertTrue(self.await_ci.called, "_await_main_ci не вызван")
        self.assertTrue(self.rebuild.called, "_rebuild_core_reference не вызван")

    def test_ac7_refusal_before_push_keeps_origin_branch(self):
        """Отказ гейта до push (`_checks_local_refuse`): ветка в `origin` на месте, записи «уборка» нет.

        Сценарий: шаг локальных проверок отказывает. Тело гейта
        возвращает `("stopped",)`; ветка задачи, опубликованная гейтом в
        `origin` проекта, на месте; хук не видел её удаления; записи
        «уборка» у задачи нет.

        Ловит мутацию: уборка ветки в `origin` поставлена в тело гейта до
        push мержа (например, рядом с публикацией артефактов мержа) — на
        отказе после неё ветка уже удалена, запись «уборка» есть.
        """
        self.patch(fsm_merge_gate, "_checks_local_refuse",
                   lambda *a, **k: True)

        result, out = self.approve()

        self.assertEqual(result, ("stopped",), out)
        self.assertTrue(self.origin_has(f"refs/heads/{self.branch}"), out)
        self.assertEqual(self.deletions(), [])
        self.assertEqual(self.notes(), [], self.journal_text())

    def test_ac7_moved_keeps_origin_branch(self):
        """Исход push «moved»: ветка в `origin` на месте, записи «уборка» нет.

        Сценарий: push мержа отвечает «main сдвинулся»
        (`_push_merged_main` -> `"moved"`). Тело гейта возвращает
        `("moved", <ветка>)`; ветка задачи в `origin` проекта на месте,
        хук не видел её удаления; записи «уборка» нет.

        Ловит мутацию: уборка вызвана до проверки исхода push (сразу после
        `_push_merged_main`, без условия `"ok"`) — на «moved» ветка
        удалена, запись «уборка» есть.
        """
        self.patch(fsm_merge_gate, "_push_merged_main",
                   lambda *a, **k: "moved")

        result, out = self.approve()

        self.assertEqual(result, ("moved", self.branch), out)
        self.assertTrue(self.origin_has(f"refs/heads/{self.branch}"), out)
        self.assertEqual(self.deletions(), [])
        self.assertEqual(self.notes(), [], self.journal_text())

    def test_ac8_no_gh_after_merge(self):
        """После перехода в `done` тело гейта не запускает `gh` ни разу.

        Сценарий: подставной `gh` в начале `PATH`; шпион
        `_finalize_done_state` отмечает число записей журнала событий в
        момент перехода в `done`. После `("done",)` записей `gh` позже
        этой отметки нет.

        Ловит мутацию: уборка после мержа закрывает PR (`gh pr close` по
        образцу kill) — запись `gh` после отметки.
        """
        mark = {}
        real = fsm_merge_gate._finalize_done_state

        def finalize(*args, **kwargs):
            real(*args, **kwargs)
            mark["at"] = len(self.events_list())

        self.patch(fsm_merge_gate, "_finalize_done_state", finalize)

        result, out = self.approve()

        self.assertEqual(result, ("done",), out)
        self.assertIn("at", mark, "переход в done не выполнен")
        after = [e for e in self.events_list()[mark["at"]:]
                 if e["kind"] == "gh"]
        self.assertEqual(after, [], f"gh после мержа: {after}")


if __name__ == "__main__":
    unittest.main()
