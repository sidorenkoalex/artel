"""Уборка ветки смерженной задачи в `origin` проекта: удаление, отказы, подсказки, сбои.

Группа: долгоживущий

Красен до реализации: функции `cleanup.cleanup_merged_remote` ещё нет — методы, зовущие её, падают `AttributeError`; примитив удаления kill на ответе `None` от `gitcmd.in_repo` падает `AttributeError`; методы AC-8 о kill артели держат прежнее поведение и зелёные с рождения.

Новая функция уборки зовётся по имени и подписи, предложенным SPEC:
`cleanup.cleanup_merged_remote(conn, task_id, branch, merged_sha)`.

Сценарий на настоящем git: пульт (`self.root`, он же клон артели) со своим
bare-`origin` (`self.bare`); внешний проект — клон по адресу
`repo_context.resolve(<проект>).path` со своим bare-`origin`. Ветка задачи с
собственным коммитом опубликована в `origin` своего проекта, смержена в базу
`git merge --no-ff`, база отправлена в `origin`; `merged_sha` — голова базы
после мержа. Рядом в `origin` лежат `refs/artifacts/<id>` и ветка
`artifact/<…>` — уборка их не трогает.

Хук `pre-receive` обоих bare-`origin` пишет в журнал событий каждую
принятую к разбору запись ссылки и по флагу отклоняет удаление веток
`task/*`. Подставной `gh` в начале `PATH` пишет в тот же журнал свой argv.
`gitcmd.in_repo` обёрнут шпионом: каждый вызов записан, по правилу сценария
вызов подменяется ответом `None`, ответом с ненулевым кодом или исключением.

Имя проекта, его база, id задач, предел `config.GH_TIMEOUT_SEC` и тексты
сбоев — из `random`, зерно печатается и входит в текст провала.
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (cleanup, config, gitcmd, keychain, repo_context,
                          store, workspace)
from tests.sandbox import ARTEL_TEST_PROFILE, AutoOriginSandbox, capture

ZERO_OID = "0" * 40
CLEANUP_ACTION = "уборка"
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni", "kibitka")
OTHER_BASES = ("trunk", "develop", "stable", "osnova")
ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
KINDS = ("artel", "external")


def _targets_yaml(external: str, base: str) -> str:
    entry = ("    forge: github\n    url: file:///nonexistent/{name}\n"
             "    base: {base}\n    token_slot: {name}-token\n"
             "    no_paths: []\n    project_skills: []\n"
             "    merge_gate: operator\n")
    return ("targets:\n"
            f"  {config.DEFAULT_TARGET}:\n"
            + entry.format(name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH)
            + ARTEL_TEST_PROFILE
            + f"  {external}:\n"
            + entry.format(name=external, base=base))


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


class MergedTask:
    """Смерженная задача сценария: id, ветка, `merged_sha`, клон и bare
    `origin` её проекта."""

    def __init__(self, task_id, branch, merged_sha, clone, bare):
        self.id = task_id
        self.branch = branch
        self.merged_sha = merged_sha
        self.clone = clone
        self.bare = bare


class MergedRemoteSandbox(AutoOriginSandbox):
    """Пульт с `origin`, внешний проект со своим `origin`; `merged(kind)`
    заводит смерженную задачу артели (`kind="artel"`) или проекта
    (`"external"`) в состоянии `done`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.target = (self.rng.choice(PROJECT_NAMES)
                       + str(self.rng.randrange(10, 100)))
        self.base = self.rng.choice(OTHER_BASES + (config.MAIN_BRANCH,))
        config.TARGETS.write_text(_targets_yaml(self.target, self.base),
                                  encoding="utf-8")

        self.fixture = Path(tempfile.mkdtemp(prefix="artel-merged-")).resolve()
        self.addCleanup(shutil.rmtree, self.fixture, ignore_errors=True)
        self.events = self.fixture / "events.jsonl"
        self.events.write_text("", encoding="utf-8")
        self.reject_flag = self.fixture / "reject-delete"
        self.install_fake_gh()
        patcher = mock.patch.object(keychain, "token",
                                    lambda slot: f"tok-{slot}")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.install_hook(Path(self.bare))

        ctx = repo_context.resolve(self.target)
        self.assertIsNotNone(ctx, self.why("предусловие: контекст проекта"))
        self.project = Path(ctx.path)
        self.project.mkdir(parents=True, exist_ok=True)
        self.pgit("init", "-q", "-b", self.base)
        self.pgit("config", "user.email", "project@example.invalid")
        self.pgit("config", "user.name", "project tests")
        (self.project / "README.md").write_text("проект\n", encoding="utf-8")
        self.pgit("add", "README.md")
        self.pgit("commit", "-q", "-m", "init")
        self.project_bare = self.fixture / "origin.git"
        self.git("init", "-q", "--bare", "-b", self.base,
                 str(self.project_bare))
        self.install_hook(self.project_bare)
        self.pgit("remote", "add", "origin", str(self.project_bare))
        self.pgit("push", "-q", "origin", f"{self.base}:{self.base}")
        self.calls = []
        self.rule = None

    # --- фикстура ---------------------------------------------------------

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed}, проект {self.target})"

    def pgit(self, *args: str) -> str:
        return self.git("-C", str(self.project), *args)

    def cgit(self, clone: Path, *args: str) -> str:
        return self.git("-C", str(clone), *args)

    def install_fake_gh(self) -> None:
        bin_dir = self.fixture / "bin"
        bin_dir.mkdir()
        _write_executable(bin_dir / "gh", FAKE_GH.format(
            python=sys.executable, log=str(self.events)))
        patcher = mock.patch.dict(os.environ, {
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def install_hook(self, bare: Path) -> None:
        _write_executable(bare / "hooks" / "pre-receive", PRE_RECEIVE.format(
            python=sys.executable, log=str(self.events),
            flag=str(self.reject_flag),
            text="удаление ветки задачи отклонено хостингом фикстуры: "))

    def new_id(self, prefix: str) -> str:
        return prefix + "".join(self.rng.choice(ID_ALPHABET)
                                for _ in range(22 - len(prefix)))

    def merged(self, kind: str) -> MergedTask:
        """Задача `kind` в `done`: ветка с коммитом опубликована в `origin`
        проекта, влита `--no-ff` в базу, база отправлена; рядом в `origin` —
        `refs/artifacts/<id>` и ветка `artifact/<id>`."""
        if kind == "artel":
            task_id = self.new_id("01UNITMRGART")
            clone, bare, base = self.root, Path(self.bare), config.MAIN_BRANCH
            target = config.DEFAULT_TARGET
        else:
            task_id = self.new_id("01UNITMRGEXT")
            clone, bare, base = self.project, self.project_bare, self.base
            target = self.target
        branch = f"task/{task_id.lower()}-x"
        self.cgit(clone, "checkout", "-q", "-b", branch, base)
        (clone / f"{task_id}.txt").write_text("работа\n", encoding="utf-8")
        self.cgit(clone, "add", f"{task_id}.txt")
        self.cgit(clone, "commit", "-q", "-m", f"{task_id}: работа")
        self.cgit(clone, "push", "-q", "origin", branch)
        self.cgit(clone, "checkout", "-q", base)
        self.cgit(clone, "merge", "-q", "--no-ff", "-m",
                  f"{task_id}: merge", branch)
        self.cgit(clone, "push", "-q", "origin", f"{base}:{base}")
        merged_sha = self.cgit(clone, "rev-parse", "HEAD").strip()
        docs = f"refs/artifacts/{task_id}"
        self.cgit(clone, "push", "-q", "origin", f"{branch}:{docs}")
        self.cgit(clone, "push", "-q", "origin",
                  f"{base}:refs/heads/artifact/{task_id.lower()}")
        store.insert_task(store.db(), task_id, "Смерженная задача", "done",
                          branch, target, 25.0)
        return MergedTask(task_id, branch, merged_sha, clone, bare)

    def spy_in_repo(self) -> None:
        """Шпион `gitcmd.in_repo`: вызов записан в `self.calls`; правило
        `self.rule(args)` возвращает `(True, ответ)` — подменить ответ,
        `(True, исключение)` — поднять его, иначе — настоящий вызов."""
        real = gitcmd.in_repo

        def spy(repo, *args, **kwargs):
            self.calls.append(tuple(args))
            if self.rule is not None:
                hit, value = self.rule(args)
                if hit:
                    if isinstance(value, BaseException):
                        raise value
                    return value
            return real(repo, *args, **kwargs)

        patcher = mock.patch.object(gitcmd, "in_repo", spy)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cleanup(self, task: MergedTask, branch: str | None = None) -> str:
        """Новая уборка без перехвата исключений: исключение — провал."""
        self.mark = len(self.all_events())
        return capture(cleanup.cleanup_merged_remote, store.db(), task.id,
                       task.branch if branch is None else branch,
                       task.merged_sha)

    # --- наблюдения -------------------------------------------------------

    def all_events(self) -> list:
        return [json.loads(line) for line in
                self.events.read_text(encoding="utf-8").splitlines() if line]

    def new_events(self) -> list:
        return self.all_events()[self.mark:]

    def deletions(self, branch: str) -> list:
        return [e for e in self.new_events()
                if e["kind"] == "push" and e["new"] == ZERO_OID
                and e["ref"] == f"refs/heads/{branch}"]

    def gh_calls(self) -> list:
        return [e for e in self.new_events() if e["kind"] == "gh"]

    def origin_head(self, task: MergedTask, ref: str) -> str:
        return self.git("--git-dir", str(task.bare), "for-each-ref",
                        "--format=%(objectname)", ref).strip()

    def notes(self, task: MergedTask) -> list:
        return [row["detail"] or "" for row in
                store.task_steps(store.db(), task.id)
                if row["action"] == CLEANUP_ACTION]

    def journal_text(self, task: MergedTask) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), task.id))

    def ls_remote_calls(self, branch: str) -> list:
        return [a for a in self.calls
                if "ls-remote" in a and f"refs/heads/{branch}" in a]

    def push_calls(self) -> list:
        return [a for a in self.calls if "push" in a]

    def single_note(self, task: MergedTask, out: str) -> str:
        notes = self.notes(task)
        self.assertEqual(len(notes), 1, self.why(
            f"записей «{CLEANUP_ACTION}» не одна:\n{self.journal_text(task)}"
            f"\n{out}"))
        return notes[0]

    def printed_index(self, out: str, note: str) -> int:
        """Номер последней строки вывода, занятой исходом, напечатанным с
        начала строки после отступа (причина отказа git бывает
        многострочной); провал — такого исхода нет."""
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
        self.fail(self.why(f"исход «{note}» не напечатан с отступом:\n{out}"))

    def hint_index(self, out: str, task: MergedTask, pattern: str):
        """(номер строки, захваты) строки подсказки `git -C <клон> <pattern>`
        с клоном задачи; None — такой строки нет."""
        rx = re.compile(r"git -C (\S+) " + pattern)
        expected = workspace.task_repo(task.id).resolve()
        for i, line in enumerate(out.splitlines()):
            m = rx.search(line)
            if m and Path(m.group(1)).resolve() == expected:
                return i, m.groups()[1:]
        return None

    def delete_hint(self, out: str, task: MergedTask):
        b = re.escape(task.branch)
        return self.hint_index(
            out, task, rf"push --force-with-lease=refs/heads/{b}:(\S+) "
                       rf"origin --delete refs/heads/{b}(\s|$)")


class DeletedTest(MergedRemoteSandbox):

    def test_ac1_deleted_branch_journal_print_and_bounded_args(self):
        """Голова ветки входит в смерженный main: ветки в `origin` нет, ссылка документов цела, одна запись «удалена», оба вызова git — с пределом.

        Сценарий (артель и внешний проект, `config.GH_TIMEOUT_SEC` — из
        `random`): после уборки `refs/heads/<ветка>` в bare-`origin` нет,
        `refs/artifacts/<id>` есть; в журнале одна запись «уборка» с
        исходом «ветка origin <ветка>: удалена», он же напечатан строкой с
        отступом; вызов `ls-remote origin refs/heads/<ветка>` и вызов `push
        … --delete refs/heads/<ветка>` несут пары `-c http.lowSpeedLimit=1`
        и `-c http.lowSpeedTime=<предел>`.

        Ловит мутацию: чтение головы через `ls-remote` без `-c`-пар (или
        предел зашит числом вместо `config.GH_TIMEOUT_SEC`) — у вызова нет
        пары с текущим пределом; удаление не выполняется — ветка в
        `origin` осталась; исход не записан в журнал либо не напечатан —
        записи «уборка» нет / строки с отступом нет.
        """
        limit = self.rng.randrange(7, 300)
        self.spy_in_repo()
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                self.calls.clear()
                with mock.patch.object(config, "GH_TIMEOUT_SEC", limit):
                    out = self.run_cleanup(task)

                note = f"ветка origin {task.branch}: удалена"
                self.assertEqual(self.single_note(task, out), note,
                                 self.why(out))
                self.printed_index(out, note)
                self.assertEqual(
                    self.origin_head(task, f"refs/heads/{task.branch}"), "",
                    self.why(f"ветка осталась в origin:\n{out}"))
                self.assertTrue(
                    self.origin_head(task, f"refs/artifacts/{task.id}"),
                    self.why("ссылки документов нет в origin"))
                reads = self.ls_remote_calls(task.branch)
                deletes = [a for a in self.push_calls() if "--delete" in a
                           and f"refs/heads/{task.branch}" in a]
                self.assertTrue(reads, self.why(f"нет ls-remote: {self.calls}"))
                self.assertTrue(deletes, self.why(f"нет push --delete: {self.calls}"))
                for args in (reads[0], deletes[0]):
                    self.assertTrue(
                        _has_pair(args, "-c", "http.lowSpeedLimit=1")
                        and _has_pair(args, "-c", f"http.lowSpeedTime={limit}"),
                        self.why(f"вызов без предела {limit}: {args}"))


class NothingToDeleteTest(MergedRemoteSandbox):

    def test_ac2_absent_branch_and_repeated_call_say_nothing_to_delete(self):
        """Ветки в `origin` нет — исход «нет — удалять нечего» без push; повторный вызов после удаления — тот же исход.

        Сценарий (артель и внешний проект): (1) ветку задачи заранее
        удалили из `origin` — уборка пишет «ветка origin <ветка>: нет —
        удалять нечего», вызова `push` нет, хук `origin` удаления не
        видел; (2) у второй задачи первая уборка удаляет ветку, вторая —
        пишет тот же исход «нет — удалять нечего» без `push`.

        Ловит мутацию: пустой вывод `ls-remote` не различается и уборка всё
        равно пушит удаление — в вызовах появляется `push`; повтор после
        удаления пишет «удалена» или «оставлено — …» (код возврата пуша
        несуществующей ветки читается как успех/отказ).
        """
        self.spy_in_repo()
        for kind in KINDS:
            with self.subTest(kind=kind, case="заранее нет"):
                task = self.merged(kind)
                self.cgit(task.clone, "push", "-q", "origin", "--delete",
                          task.branch)
                self.calls.clear()
                out = self.run_cleanup(task)
                note = f"ветка origin {task.branch}: нет — удалять нечего"
                self.assertEqual(self.single_note(task, out), note, self.why(out))
                self.printed_index(out, note)
                self.assertEqual(self.push_calls(), [], self.why(f"{self.calls}"))
                self.assertEqual(self.deletions(task.branch), [])
            with self.subTest(kind=kind, case="повтор"):
                task = self.merged(kind)
                self.run_cleanup(task)
                self.calls.clear()
                out = self.run_cleanup(task)
                notes = self.notes(task)
                self.assertEqual(
                    notes[-1], f"ветка origin {task.branch}: нет — удалять нечего",
                    self.why(f"{self.journal_text(task)}\n{out}"))
                self.assertEqual(self.push_calls(), [], self.why(f"{self.calls}"))


class NotMergedHeadTest(MergedRemoteSandbox):

    def test_ac3_head_beyond_merged_main_left_with_log_hint(self):
        """Голова ветки в `origin` несёт коммит сверх смерженного main: ветка остаётся, строка сверки `log --oneline`, подсказки удаления нет.

        Сценарий (артель и внешний проект): после мержа в ветку задачи в
        `origin` уходит ещё один коммит. Уборка: ветка в `origin` с той же
        головой, вызова `push` нет; в журнале исход «ветка origin <ветка>:
        оставлено — голова <sha> не входит в смерженный main <merged_sha>»;
        после напечатанной строки исхода — строка `git -C <клон> log
        --oneline <merged_sha>..<sha>`; строки с `--delete` в выводе нет;
        в журнале нет текста подсказки.

        Ловит мутацию: проверка `is_ancestor` снята (или перевёрнута) —
        ветка с несмерженным коммитом удалена из `origin`; строка сверки не
        печатается или печатается до исхода; печатается подсказка удаления;
        подсказка записана в журнал.
        """
        self.spy_in_repo()
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                self.cgit(task.clone, "checkout", "-q", task.branch)
                (task.clone / f"{task.id}-extra.txt").write_text(
                    "сверх\n", encoding="utf-8")
                self.cgit(task.clone, "add", f"{task.id}-extra.txt")
                self.cgit(task.clone, "commit", "-q", "-m", "сверх мержа")
                self.cgit(task.clone, "push", "-q", "origin", task.branch)
                self.cgit(task.clone, "checkout", "-q", "-")
                head = self.origin_head(task, f"refs/heads/{task.branch}")
                self.calls.clear()

                out = self.run_cleanup(task)

                note = (f"ветка origin {task.branch}: оставлено — голова "
                        f"{head} не входит в смерженный main {task.merged_sha}")
                journal = self.single_note(task, out)
                self.assertEqual(journal, note, self.why(out))
                at = self.printed_index(out, note)
                hint = self.hint_index(
                    out, task, rf"log --oneline {task.merged_sha}\.\.{head}()")
                self.assertIsNotNone(hint, self.why(f"нет строки сверки:\n{out}"))
                self.assertGreater(hint[0], at, self.why(out))
                self.assertNotIn("--delete", out, self.why(out))
                self.assertNotIn("log --oneline", journal)
                self.assertEqual(self.push_calls(), [], self.why(f"{self.calls}"))
                self.assertEqual(
                    self.origin_head(task, f"refs/heads/{task.branch}"), head,
                    self.why("ветка с несмерженным коммитом изменена в origin"))


class RefusedTest(MergedRemoteSandbox):

    def test_ac4_refused_delete_noted_with_manual_hint(self):
        """`origin` отказывает в удалении (хук `pre-receive`): исход «оставлено — <причина>», после него подсказка ручного удаления, в журнале её нет.

        Сценарий (артель и внешний проект): хук отклоняет удаление веток
        задач. Уборка без исключения; ветка в `origin` на месте; в журнале
        одна запись «уборка» «ветка origin <ветка>: оставлено — <непустая
        причина>»; после строки исхода печатается `git -C <клон> push
        --force-with-lease=refs/heads/<ветка>:<голова> origin --delete
        refs/heads/<ветка>` с прочитанной головой; журнал текста `push
        --force-with-lease` не несёт.

        Ловит мутацию: код возврата пуша не проверяется — исход «удалена»;
        подсказка не печатается, печатается без головы/с другой головой
        или записана в журнал вместе с исходом.
        """
        self.reject_flag.write_text("1", encoding="utf-8")
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                head = self.origin_head(task, f"refs/heads/{task.branch}")

                out = self.run_cleanup(task)

                prefix = f"ветка origin {task.branch}: оставлено — "
                journal = self.single_note(task, out)
                self.assertTrue(journal.startswith(prefix), self.why(journal))
                self.assertTrue(journal[len(prefix):].strip(), self.why(journal))
                at = self.printed_index(out, journal)
                hint = self.delete_hint(out, task)
                self.assertIsNotNone(hint, self.why(f"нет подсказки:\n{out}"))
                self.assertEqual(hint[1][0], head, self.why(out))
                self.assertGreater(hint[0], at, self.why(out))
                self.assertNotIn("--force-with-lease", journal)
                self.assertEqual(
                    self.origin_head(task, f"refs/heads/{task.branch}"), head)


class LeaseTest(MergedRemoteSandbox):

    def test_ac5_branch_moved_after_read_is_not_deleted(self):
        """Ветку сдвинули потомком между чтением головы и удалением: удаление отказано, ветка в `origin` с новой головой.

        Сценарий (артель и внешний проект): шпион `gitcmd.in_repo` сразу
        после настоящего `ls-remote` ветки отправляет в `origin` коммит-
        потомок прочитанной головы. Уборка: ветка в `origin` есть и несёт
        потомка; исход «ветка origin <ветка>: оставлено — …».

        Ловит мутацию: удаление без `--force-with-lease=<ref>:<прочитанная
        голова>` (голый `push origin --delete`) — сдвинутая ветка удалена.
        """
        self.spy_in_repo()
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                old = self.origin_head(task, f"refs/heads/{task.branch}")
                tree = self.cgit(task.clone, "rev-parse", f"{old}^{{tree}}").strip()
                newer = self.cgit(task.clone, "commit-tree", tree, "-p", old,
                                  "-m", "потомок").strip()
                state = {"moved": False}

                def rule(args, task=task, newer=newer, state=state):
                    if (not state["moved"] and "ls-remote" in args
                            and f"refs/heads/{task.branch}" in args):
                        state["moved"] = True
                        self.rule = None
                        res = gitcmd.in_repo(task.clone, *args)
                        self.cgit(task.clone, "push", "-q", "origin",
                                  f"{newer}:refs/heads/{task.branch}")
                        self.rule = rule
                        return True, res
                    return False, None

                self.rule = rule
                out = self.run_cleanup(task)
                self.rule = None

                self.assertTrue(state["moved"], self.why(f"ls-remote не звался: {self.calls}"))
                self.assertEqual(
                    self.origin_head(task, f"refs/heads/{task.branch}"), newer,
                    self.why(f"сдвинутая ветка удалена:\n{out}"))
                self.assertTrue(self.single_note(task, out).startswith(
                    f"ветка origin {task.branch}: оставлено — "), self.why(out))


class GitFailuresTest(MergedRemoteSandbox):

    def setUp(self):
        super().setUp()
        self.spy_in_repo()

    def test_ac6a_none_on_read_noted_with_two_hints(self):
        """`in_repo` вернул `None` на `ls-remote`: исход «оставлено — git не ответил», push нет, подсказки `ls-remote` и удаления.

        Сценарий (артель и внешний проект): шпион отвечает `None` на чтение
        головы ветки. Уборка без исключения; исход в журнале «ветка origin
        <ветка>: оставлено — git не ответил»; вызова `push` нет; после
        строки исхода печатаются `git -C <клон> ls-remote origin
        refs/heads/<ветка>` и затем `git -C <клон> push
        --force-with-lease=refs/heads/<ветка>:<…> origin --delete
        refs/heads/<ветка>`.

        Ловит мутацию: ответ `None` не разобран — `AttributeError` из
        уборки; `None` читается как «ветки нет» — исход «нет — удалять
        нечего» без подсказок; подсказка `ls-remote` не печатается или
        печатается после подсказки удаления.
        """
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                self.rule = lambda args, b=task.branch: (
                    ("ls-remote" in args and f"refs/heads/{b}" in args), None)
                self.calls.clear()
                out = self.run_cleanup(task)
                self.rule = None

                note = f"ветка origin {task.branch}: оставлено — git не ответил"
                self.assertEqual(self.single_note(task, out), note, self.why(out))
                at = self.printed_index(out, note)
                self.assertEqual(self.push_calls(), [], self.why(f"{self.calls}"))
                b = re.escape(task.branch)
                read = self.hint_index(out, task,
                                       rf"ls-remote origin refs/heads/{b}(\s|$)")
                delete = self.delete_hint(out, task)
                self.assertIsNotNone(read, self.why(f"нет подсказки ls-remote:\n{out}"))
                self.assertIsNotNone(delete, self.why(f"нет подсказки удаления:\n{out}"))
                self.assertLess(at, read[0], self.why(out))
                self.assertLess(read[0], delete[0], self.why(out))

    def test_ac6b_nonzero_ls_remote_reason_carries_stderr(self):
        """`ls-remote` завершился ненулевым кодом: причина исхода несёт его stderr, push нет.

        Сценарий (артель и внешний проект): шпион отвечает на чтение
        головы кодом 128 и stderr из `random`. Исход «ветка origin <ветка>:
        оставлено — <причина>», причина содержит текст stderr; вызова
        `push` нет.

        Ловит мутацию: код возврата `ls-remote` не проверяется — пустой
        stdout читается как «ветки нет» (исход «нет — удалять нечего»);
        причина не берёт stderr.
        """
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                text = f"fatal: сбой чтения фикстуры {self.rng.randrange(10 ** 9)}"
                failed = subprocess.CompletedProcess(["git"], 128, "", text + "\n")
                self.rule = lambda args, b=task.branch: (
                    ("ls-remote" in args and f"refs/heads/{b}" in args), failed)
                self.calls.clear()
                out = self.run_cleanup(task)
                self.rule = None

                prefix = f"ветка origin {task.branch}: оставлено — "
                journal = self.single_note(task, out)
                self.assertTrue(journal.startswith(prefix), self.why(journal))
                self.assertIn(text, journal, self.why(journal))
                self.assertEqual(self.push_calls(), [], self.why(f"{self.calls}"))

    def test_ac6c_none_on_push_noted_with_read_head_hint(self):
        """`in_repo` вернул `None` на push удаления: исход «оставлено — git не ответил», подсказка удаления с прочитанной головой.

        Сценарий (артель и внешний проект): чтение головы настоящее, шпион
        отвечает `None` на `push … --delete`. Уборка без исключения;
        исход «ветка origin <ветка>: оставлено — git не ответил»; после
        него подсказка `git -C <клон> push
        --force-with-lease=refs/heads/<ветка>:<голова> origin --delete
        refs/heads/<ветка>` с головой ветки в `origin`; ветка на месте.

        Ловит мутацию: примитив удаления читает `res.returncode` у `None` —
        `AttributeError`; подсказка удаления на этом исходе не печатается
        или несёт не прочитанную голову.
        """
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                head = self.origin_head(task, f"refs/heads/{task.branch}")
                self.rule = lambda args: (("push" in args and "--delete" in args),
                                          None)
                out = self.run_cleanup(task)
                self.rule = None

                note = f"ветка origin {task.branch}: оставлено — git не ответил"
                self.assertEqual(self.single_note(task, out), note, self.why(out))
                at = self.printed_index(out, note)
                hint = self.delete_hint(out, task)
                self.assertIsNotNone(hint, self.why(f"нет подсказки:\n{out}"))
                self.assertEqual(hint[1][0], head, self.why(out))
                self.assertGreater(hint[0], at, self.why(out))
                self.assertEqual(
                    self.origin_head(task, f"refs/heads/{task.branch}"), head)

    def test_ac6g_exception_inside_cleanup_noted_without_hint(self):
        """Исключение внутри уборки: исход «оставлено — <тип>: <текст>», без подсказки и без исключения наружу.

        Сценарий (артель и внешний проект): шпион поднимает
        `RuntimeError` с текстом из `random` на чтении головы. Вызов
        возвращается без исключения; исход «ветка origin <ветка>: оставлено
        — RuntimeError: <текст>»; в выводе нет строк `git -C`.

        Ловит мутацию: исключение не перехвачено — `RuntimeError` выходит
        из уборки; исход без имени типа; после исхода печатается
        подсказка.
        """
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                text = f"сбой фикстуры {self.rng.randrange(10 ** 9)}"
                self.rule = lambda args, b=task.branch: (
                    ("ls-remote" in args and f"refs/heads/{b}" in args),
                    RuntimeError(text))
                out = self.run_cleanup(task)
                self.rule = None

                note = (f"ветка origin {task.branch}: оставлено — "
                        f"RuntimeError: {text}")
                self.assertEqual(self.single_note(task, out), note, self.why(out))
                self.printed_index(out, note)
                self.assertNotIn("git -C", out, self.why(out))


class KillNoneTest(MergedRemoteSandbox):

    def test_ac6c_kill_delete_primitive_parses_none(self):
        """`kill` задачи проекта: `in_repo` вернул `None` на push удаления — заметка «ветка origin <ветка>: оставлено — git не ответил», без `AttributeError`.

        Сценарий: задача внешнего проекта в `verifying`, её ветка
        опубликована в `origin` проекта; шпион отвечает `None` на `push …
        --delete` ветки задачи. `kill` проходит без исключения, задача в
        `killed`, в журнале уборки есть заметка «ветка origin <ветка>:
        оставлено — git не ответил».

        Ловит мутацию: `_delete_origin_branch` по-прежнему читает
        `res.returncode` без проверки на `None` — `AttributeError` из `kill`.
        """
        task_id = self.new_id("01UNITMRGKIL")
        branch = f"task/{task_id.lower()}-x"
        self.pgit("checkout", "-q", "-b", branch, self.base)
        (self.project / f"{task_id}.txt").write_text("работа\n", encoding="utf-8")
        self.pgit("add", f"{task_id}.txt")
        self.pgit("commit", "-q", "-m", f"{task_id}: работа")
        self.pgit("checkout", "-q", self.base)
        self.pgit("push", "-q", "origin", branch)
        store.insert_task(store.db(), task_id, "Задача проекта", "in_dev",
                          branch, self.target, 25.0)
        capture(lambda: store.set_state(store.db(), task_id, "verifying", "fsm",
                                        expected_state="in_dev",
                                        detail="переход теста"))
        self.spy_in_repo()
        self.rule = lambda args: (("--delete" in args
                                   and any(a.endswith(branch) for a in args)), None)

        out = capture(cleanup.cmd_kill, task_id)

        self.assertEqual(store.get_task(store.db(), task_id)["state"], "killed",
                         self.why(out))
        notes = []
        for row in store.task_steps(store.db(), task_id):
            if row["action"] == CLEANUP_ACTION:
                notes += (row["detail"] or "").split("; ")
        self.assertIn(f"ветка origin {branch}: оставлено — git не ответил", notes,
                      self.why(f"{notes}\n{out}"))


class BoundariesTest(MergedRemoteSandbox):

    def test_ac7_empty_branch_does_nothing(self):
        """Пустое имя ветки: уборка ничего не делает — ни вызовов git, ни записи журнала, ни вывода.

        Сценарий (артель и внешний проект): новая функция вызвана с
        `branch=""`. Записей «уборка» у задачи нет, шпион `gitcmd.in_repo`
        не видел ни одного вызова, вывод пуст.

        Ловит мутацию: проверки пустого имени нет — уборка зовёт
        `ls-remote origin refs/heads/` и пишет исход в журнал.
        """
        self.spy_in_repo()
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                self.calls.clear()
                out = self.run_cleanup(task, branch="")
                self.assertEqual(self.notes(task), [], self.why(self.journal_text(task)))
                self.assertEqual(self.calls, [], self.why(f"{self.calls}"))
                self.assertEqual(out.strip(), "", self.why(out))
                self.assertTrue(
                    self.origin_head(task, f"refs/heads/{task.branch}"))

    def test_ac8_cleanup_touches_no_gh_and_no_artifact_refs(self):
        """Новая уборка не зовёт `gh` и не читает/не удаляет `refs/artifacts/<id>` и ветки `artifact/*`.

        Сценарий (артель и внешний проект): успешная уборка смерженной
        задачи. Подставной `gh` не запускался; ни один вызов
        `gitcmd.in_repo` не упоминает `refs/artifacts` или `artifact/`;
        в `origin` обе ссылки на месте.

        Ловит мутацию: уборка заодно закрывает PR (`gh pr close`) —
        подставной `gh` запущен; уборка удаляет и ссылки документов
        (`push --delete refs/artifacts/<id>`) — ссылки нет в `origin`.
        """
        self.spy_in_repo()
        for kind in KINDS:
            with self.subTest(kind=kind):
                task = self.merged(kind)
                self.calls.clear()
                out = self.run_cleanup(task)
                self.assertEqual(self.gh_calls(), [], self.why(out))
                touched = [a for a in self.calls
                           if any("refs/artifacts" in x or "artifact/" in x
                                  for x in a)]
                self.assertEqual(touched, [], self.why(f"{touched}"))
                self.assertTrue(self.origin_head(task, f"refs/artifacts/{task.id}"))
                self.assertTrue(self.origin_head(
                    task, f"refs/heads/artifact/{task.id.lower()}"))

    def test_ac8_artel_kill_keeps_origin_branch(self):
        """`kill` задачи артели не удаляет её ветку в `origin` пульта.

        Сценарий: задача артели в `verifying`, ветка опубликована в
        bare-`origin` пульта. После `kill` задача в `killed`, хук не видел
        удаления ветки, ветка в `origin` на месте.

        Ловит мутацию: новая уборка ветки в `origin` подключена и к пути
        kill (или проверка «не артель» снята в уборке kill) — ветка артели
        удалена из `origin` пульта.
        """
        task_id = self.new_id("01UNITMRGKAR")
        branch = f"task/{task_id.lower()}-x"
        self.git("branch", branch, config.MAIN_BRANCH)
        self.git("push", "-q", "origin", branch)
        store.insert_task(store.db(), task_id, "Задача артели", "in_dev",
                          branch, config.DEFAULT_TARGET, 25.0)
        capture(lambda: store.set_state(store.db(), task_id, "verifying", "fsm",
                                        expected_state="in_dev",
                                        detail="переход теста"))
        self.mark = len(self.all_events())

        out = capture(cleanup.cmd_kill, task_id)

        self.assertEqual(store.get_task(store.db(), task_id)["state"], "killed",
                         self.why(out))
        self.assertEqual(self.deletions(branch), [], self.why(out))
        self.assertTrue(self.git("--git-dir", str(self.bare), "for-each-ref",
                                 f"refs/heads/{branch}").strip(),
                        self.why("ветка артели удалена из origin пульта"))


if __name__ == "__main__":
    unittest.main()
