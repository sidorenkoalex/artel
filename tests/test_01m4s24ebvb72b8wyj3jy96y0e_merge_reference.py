"""Пересборка справочника ядра после мержа: последний шаг `approve` на
`merge_gate` зовёт `reference_cache.get_reference(..., reason="merge",
sha=final_sha)` после push, перевода в `done`, коммита закрытия, уборки и
ожидания CI main; на исходе push «main сдвинулся» не зовёт; коммитов не
создаёт; у проекта без поля `core_reference` побочных эффектов не даёт;
исключение любого типа из шага, из записи журнала и из алерта обработчика
мерж не срывает.

Группа: долгоживущий

Красен до реализации: модуля `orchestrator.reference_cache` (К-3а) ещё нет — подмена `reference_cache.get_reference` падает на импорте модуля; после К-3а без кода задачи шаг после мержа не вызывает `get_reference` — вызовов ноль.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): главная копия
пульта, она же клон артели, и bare `origin` рядом. Классу с кодом пульта
(`COPY_CODE`) первый коммит несёт копию `orchestrator/` и `scripts/`
репозитория и заглушку карты кодовой базы: регенерация карты на мерже даёт
отдельный коммит карты (шаг карты `fsm_postmerge` после приложений), так
что голова, отправленная в main (`final_sha`), отличается и от коммита
плотницкого merge, и от коммита приложений, и от головы ветки задачи.
Задача заводится прямо на `merge_gate`: кодовая ветка от origin/main
(опубликована), ссылка документов — коммит вспомогательного репозитория,
отправленный в репозиторий задачи и его `origin`, затем фиксация. Команда —
диспетчером `artel.main()` тем же argv, что набирает Оператор (`approve`).
GitHub изображает подставной `gh` в начале `PATH` (все проверки зелёные),
часы подставные — ожидание CI без реального ожидания.

Подменённый `get_reference` записывает в момент вызова наблюдаемое
состояние: состояние задачи, голову main origin, наличие RETRO закрытия в
`refs/artifacts/<id>` origin, действия журнала задачи, наличие ветки задачи,
ссылки и статус главной копии. Исход push «main сдвинулся» — хук
`pre-receive` bare `origin`, один раз отвергающий push в main текстом
«non-fast-forward». Сбой записи журнала и подъёма алерта внутри шага —
подмены `store.journal`/`alerts.raise_alert`, бросающие исключение, только
пока в стеке вызовов стоит кадр, из которого вызван `get_reference`.

Идентификаторы задач, код задачи, тексты исключений и справочника
выбираются случайно; зерно печатается и входит в текст провала.
"""
import contextlib
import inspect
import io
import os
import random
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import NamedTuple
from unittest import mock

from orchestrator import alerts, artel, catalog, config, fsm_merge_gate, store
from tests.sandbox import RealGitSandbox, capture, patch_pult_sleep

GET_REFERENCE = "orchestrator.reference_cache.get_reference"
REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = config.TASKS.name
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MAP_REL = "docs/codebase-map.md"
MAP_PLACEHOLDER = ("---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n"
                   "# Карта кодовой базы (заглушка песочницы)\n")
WORKTREE_REMOVED = "worktree убран"
BRANCH_REMOVED = "ветка убрана"
MAIN_MOVED = "main сдвинулся во время окна — повтор подтяжки"

# Подставной `gh`: зелёные проверки на любой коммит, пустые списки прогонов
# и запросов на слияние; прочие вызовы — отказ.
FAKE_GH = r'''
import json, re, sys
args = sys.argv[1:]
joined = " ".join(args)
if args[:1] == ["api"] and "/check-runs" in joined:
    page = re.search(r"[?&]page=(\d+)", joined)
    runs = [{"name": "тесты кода", "status": "completed",
             "conclusion": "success"}]
    shown = runs if page is None or page.group(1) == "1" else []
    print(json.dumps({"total_count": len(runs), "check_runs": shown},
                     ensure_ascii=False))
    sys.exit(0)
if args[:2] in (["run", "list"], ["pr", "list"], ["pr", "view"]):
    print("[]")
    sys.exit(0)
sys.stderr.write("gh песочницы: вызов не поддержан: " + joined + "\n")
sys.exit(1)
'''

# Хук bare `origin`: первый push в main отвергается текстом класса «main
# сдвинулся», следующие принимаются. Метка — файл рядом с хуком.
PRE_RECEIVE = '''#!/bin/sh
while read old new ref; do
  if [ "$ref" = "refs/heads/{main}" ] && [ ! -f "{marker}" ]; then
    touch "{marker}"
    echo "error: failed to push some refs: non-fast-forward" >&2
    exit 1
  fi
done
exit 0
'''


class Reference(NamedTuple):
    """Ответ `get_reference` в форме интерфейса К-3а."""
    text: str
    note: str
    state: str


def plank_text() -> str:
    """Планка задачи песочницы из одного метода; метка собирается заменой,
    чтобы сканер планки пульта не принял литерал за тест ЭТОГО файла."""
    return ('"""Планка задачи песочницы."""\nimport unittest\n\n\n'
            "class Fixture(unittest.TestCase):\n"
            "    def test_@ac1_fixture(self):\n        pass\n").replace("@ac", "ac")


def spec_text(task: str) -> str:
    return (f"---\ntask: {task}\ntype: spec\nauthor_role: analyst\n"
            f"status: ready\nschema_version: 5\nzones: kod/\nbudget_usd: 10\n---\n\n"
            f"# SPEC: задача {task}\n\n"
            f"## Контекст\n\nЗадача песочницы мержа.\n\n## Требования\n\n"
            f"1. Требование.\n\n## Критерии приёмки\n\n@AC-1. Критерий.\n\n"
            f"## Не входит\n\n- Ничего.\n").replace("@AC", "AC")


def plan_text(task: str, appendix: str = "") -> str:
    return (f"---\ntask: {task}\ntype: plan\nauthor_role: developer\n"
            f"status: ready\nschema_version: 1\n---\n\n# PLAN: задача {task}\n\n"
            f"## Подход\n\nФикстура.\n\n## Шаги\n\n## Покрытие требований\n\n"
            f"## Влияние на систему\n{appendix}")


class MergeSandbox(RealGitSandbox):
    """Главная копия (она же клон артели), bare `origin`, задачи на
    `merge_gate`, подставные `gh` и часы; `COPY_CODE` — код пульта и
    заглушка карты в main."""

    COPY_CODE = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        self.prepare_main()
        self.origin = self.add_synced_origin()
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, ignore_errors=True)
        self.docs_src = Path(src) / "docs-src"
        self.git("init", "-q", "-b", "docs-src", str(self.docs_src))
        capture(catalog.cmd_init)
        self.conn = store.db()

        bindir = self.root / ".artel" / "fake-bin"
        bindir.mkdir(parents=True, exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(f"#!{sys.executable}\n{FAKE_GH}", encoding="utf-8")
        gh.chmod(0o755)
        env = mock.patch.dict(os.environ, {
            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"})
        env.start()
        self.addCleanup(env.stop)

        self.clock = 0.0
        base_mono, base_wall = time.monotonic(), time.time()
        for target, fake in (("time.monotonic", lambda: base_mono + self.clock),
                             ("time.time", lambda: base_wall + self.clock)):
            patcher = mock.patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(patch_pult_sleep(self.fake_sleep).close)

        self.tasks: dict = {}
        self.calls: list = []
        self.step_frame = None
        self.addCleanup(self.forget_frame)

    def forget_frame(self) -> None:
        self.step_frame = None

    def prepare_main(self) -> None:
        if not self.COPY_CODE:
            return
        for name in ("orchestrator", "scripts"):
            shutil.copytree(REPO / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / MAP_REL).write_text(MAP_PLACEHOLDER, encoding="utf-8")
        old = "01H" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))
        plank = self.root / TASKS_DIR / old / "acceptance_tests" / "test_old.py"
        plank.parent.mkdir(parents=True)
        plank.write_text(plank_text(), encoding="utf-8")
        retro_path = self.root / "docs" / "retro" / f"{old}.md"
        retro_path.parent.mkdir(parents=True)
        retro_path.write_text(f"# RETRO: {old}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код пульта")

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
        if self.clock > 10 * 24 * 3600:
            raise AssertionError(self.msg("ожидание не кончается"))

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # ----------------------------------------------------------------- git

    def in_repo(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

    def git_ok(self, repo: Path, *args: str) -> bool:
        try:
            self.in_repo(repo, *args)
        except AssertionError:
            return False
        return True

    def task_id(self) -> str:
        return "01T" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))

    def ref(self, task: str) -> str:
        return f"refs/artifacts/{task}"

    def retro_rel(self, task: str) -> str:
        return f"{TASKS_DIR}/{task}/RETRO.md"

    def put_docs(self, task: str, files: dict) -> None:
        """Коммит документов задачи во вспомогательном репозитории,
        отправленный в главную копию и `origin` ссылкой документов."""
        src = self.docs_src
        self.in_repo(src, "checkout", "-q", "--orphan", f"d-{task}")
        self.in_repo(src, "rm", "-rfq", "--ignore-unmatch", ".")
        for rel, text in files.items():
            path = src / TASKS_DIR / task / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.in_repo(src, "add", "-A")
        self.in_repo(src, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                     "commit", "-q", "-m", f"{task}: документы")
        sha = self.in_repo(src, "rev-parse", "HEAD").strip()
        for dest in (self.root, self.origin):
            self.in_repo(src, "push", "-q", str(dest), f"{sha}:{self.ref(task)}")

    def commit_to_main(self, files: dict) -> None:
        repo = self.root
        self.in_repo(repo, "fetch", "-q", "origin")
        self.in_repo(repo, "merge", "-q", "--ff-only", f"origin/{config.MAIN_BRANCH}")
        for rel, text in files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.in_repo(repo, "add", rel)
        self.in_repo(repo, "commit", "-q", "-m", "правка main до задачи")
        self.in_repo(repo, "push", "-q", "origin",
                     f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def make_task(self, appendix: str = "") -> dict:
        """Задача артели на `merge_gate`: кодовая ветка от origin/main,
        опубликована; ссылка документов в главной копии и origin."""
        repo = self.root
        if self.COPY_CODE:
            # Заглушка карты в main перед каждой задачей: регенерация на её
            # мерже даёт коммит карты и во втором мерже песочницы.
            self.commit_to_main({
                MAP_REL: f"{MAP_PLACEHOLDER}\n{self.rng.randrange(10 ** 9)}\n"})
        task = self.task_id()
        branch = f"task/{task.lower()}-x"
        self.in_repo(repo, "fetch", "-q", "origin")
        self.in_repo(repo, "checkout", "-q", "-b", branch,
                     f"origin/{config.MAIN_BRANCH}")
        code = f"zadacha_{task.lower()}.py"
        (repo / code).write_text(f"VALUE = {self.rng.randrange(10 ** 6)}\n",
                                 encoding="utf-8")
        self.in_repo(repo, "add", code)
        self.in_repo(repo, "commit", "-q", "-m", f"{task}: код")
        head = self.in_repo(repo, "rev-parse", "HEAD").strip()
        self.in_repo(repo, "push", "-q", "-u", "origin", branch)
        self.in_repo(repo, "checkout", "-q", config.MAIN_BRANCH)
        store.insert_task(self.conn, task, f"Задача {task}", "merge_gate", branch,
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        self.put_docs(task, {"SPEC.md": spec_text(task),
                             "PLAN.md": plan_text(task, appendix),
                             "acceptance_tests/test_ac1_fixture.py": plank_text()})
        store.record_fixation(self.conn, task)
        info = {"id": task, "branch": branch, "head": head}
        self.tasks[task] = info
        return info

    def appendix(self) -> str:
        """Раздел приложения PLAN: новый файл под защищённым путём."""
        path = f"skills/pesochnica-{self.rng.randrange(100, 999)}.md"
        return ("\n## Приложение: правка защищённых путей\n\n```diff\n"
                f"diff --git a/{path} b/{path}\n"
                "new file mode 100644\n"
                "--- /dev/null\n"
                f"+++ b/{path}\n"
                "@@ -0,0 +1 @@\n"
                f"+правка Оператора {self.rng.randrange(10 ** 9)}\n"
                "```\n")

    # ------------------------------------------------------------ команды

    def cli(self, *argv: str) -> tuple[bool, str]:
        """(успех, вывод + текст отказа или исключения) `artel.py <argv>`."""
        out = io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok, tail = False, f"\nSystemExit: {exc.code}"
            except Exception as exc:  # noqa: BLE001 — исход сценария, не сбой теста
                ok, tail = False, f"\nисключение: {exc!r}"
        return ok, out.getvalue() + tail

    def approve(self, task: dict) -> tuple[bool, str]:
        """`approve` на `merge_gate`, пока задача на гейте: (все вызовы без
        исключения и отказа, весь вывод и журнал)."""
        oks, outputs = [], []
        for _ in range(3):
            ok, out = self.cli("approve", task["id"])
            oks.append(ok)
            outputs.append(out)
            if not ok or self.state_of(task) != "merge_gate":
                break
        return all(oks), "\n".join(outputs) + "\n" + "\n".join(self.journal(task))

    # -------------------------------------------------------------- чтение

    def state_of(self, task: dict) -> str:
        return store.get_task(store.db(), task["id"])["state"]

    def journal(self, task: dict) -> list:
        return [f"{row['action']} | {row['detail'] or ''}"
                for row in store.task_steps(store.db(), task["id"])]

    def actions(self, task_id: str) -> list:
        return [row["action"] for row in store.task_steps(store.db(), task_id)]

    def origin_main(self) -> str:
        return self.in_repo(self.origin, "rev-parse",
                            f"refs/heads/{config.MAIN_BRANCH}").strip()

    def has_retro(self, task_id: str) -> bool:
        return self.git_ok(self.origin, "cat-file", "-e",
                           f"{self.ref(task_id)}:{self.retro_rel(task_id)}")

    def branch_exists(self, task: dict) -> bool:
        return bool(self.in_repo(self.root, "branch", "--list", task["branch"]).strip())

    def refs_and_tree(self) -> tuple:
        return (self.in_repo(self.root, "for-each-ref"),
                self.in_repo(self.origin, "for-each-ref"),
                self.in_repo(self.root, "status", "--porcelain"))

    def first_parent_line(self) -> list:
        return self.in_repo(self.origin, "rev-list", "--first-parent", "--reverse",
                            f"refs/heads/{config.MAIN_BRANCH}").split()

    def parents(self, sha: str) -> list:
        return self.in_repo(self.origin, "rev-list", "--parents", "-n", "1",
                            sha).split()[1:]

    def changed_files(self, sha: str) -> set:
        return set(self.in_repo(self.origin, "diff-tree", "--no-commit-id",
                                "--name-only", "-r", sha).split())

    # ---------------------------------------------------- подмена К-3а

    def recording(self, answer=None, error: BaseException | None = None):
        """Подмена `get_reference`: снимок наблюдаемого состояния в момент
        вызова и кадр вызывающего; затем ответ или исключение."""
        def fake(conn, task_id, *, reason, sha=None):
            self.step_frame = inspect.currentframe().f_back
            task = self.tasks[task_id]
            self.calls.append({
                "task_id": task_id, "reason": reason, "sha": sha,
                "state": store.get_task(store.db(), task_id)["state"],
                "origin_main": self.origin_main(),
                "retro": self.has_retro(task_id),
                "actions": self.actions(task_id),
                "branch": self.branch_exists(task),
                "refs_and_tree": self.refs_and_tree(),
            })
            if error is not None:
                raise error
            return answer
        return fake

    def in_step(self) -> bool:
        """В стеке вызовов стоит кадр, из которого вызван `get_reference`."""
        frame = inspect.currentframe()
        while frame is not None:
            if self.step_frame is not None and frame is self.step_frame:
                return True
            frame = frame.f_back
        return False

    def failing_in_step(self, real, error: BaseException):
        def wrapper(*args, **kwargs):
            if self.in_step():
                raise error
            return real(*args, **kwargs)
        return wrapper

    def brief_calls(self) -> list:
        """Вызовы без снимка ссылок — для текста провала."""
        return [{k: v for k, v in call.items() if k != "refs_and_tree"}
                for call in self.calls]

    def assert_merged(self, task: dict, ok: bool, out: str, case: str) -> None:
        self.assertTrue(ok, self.msg(f"{case}: approve сорван\n{out}"))
        self.assertEqual(self.state_of(task), "done", self.msg(f"{case}\n{out}"))
        self.assertTrue(self.has_retro(task["id"]),
                        self.msg(f"{case}: коммита закрытия нет\n{out}"))
        actions = self.actions(task["id"])
        for action in (WORKTREE_REMOVED, BRANCH_REMOVED):
            self.assertIn(action, actions, self.msg(f"{case}: нет «{action}»\n{out}"))
        self.assertFalse(self.branch_exists(task), self.msg(f"{case}: ветка не убрана"))


class ArtelCodeMergeTest(MergeSandbox):
    """Мерж задачи артели с кодом пульта и генератором карты: в main
    уходит коммит карты поверх merge (и приложений)."""

    COPY_CODE = True

    def merge_commit(self, task: dict) -> str:
        """Коммит плотницкого merge задачи на первой линии main origin."""
        found = [sha for sha in self.first_parent_line()
                 if task["head"] in self.parents(sha)[1:]]
        self.assertEqual(len(found), 1, self.msg(f"коммит merge задачи: {found}"))
        return found[0]

    def test_ac11_rebuild_is_last_step_from_final_sha_without_commits(self):
        """Мерж без приложений PLAN и с приложением; `get_reference`
        подменён и отдаёт `fresh`.

        Ровно один вызов: эта задача, `reason="merge"`, `sha` — голова main
        origin после мержа (коммит карты), не коммит merge, не коммит
        приложений и не голова ветки задачи. В момент вызова main origin уже
        на этом sha, задача `done`, RETRO закрытия в ссылке документов
        origin, в журнале «worktree убран», «ветка убрана» и запись ожидания
        CI main, ветки задачи нет. После `approve` ссылки главной копии и
        origin и статус рабочего дерева — те же, что в момент вызова.

        Ловит мутацию: пересборка из `sha=merge_sha` (коммит мержа без
        карты), из головы ветки задачи или HEAD до приложений; вызов до
        push, до `_finalize_done_state`, до `cleanup._commit_closing`, до
        уборки или до `_await_main_ci`; шаг коммитит файл кэша в main —
        sha вызова, снимок момента вызова или ссылки после `approve`
        разойдутся.
        """
        for case in ("без приложений", "с приложением"):
            with self.subTest(случай=case, зерно=self.seed):
                self.calls.clear()
                task = self.make_task(self.appendix() if case != "без приложений" else "")
                answer = Reference(f"# справочник {self.rng.randrange(10 ** 9)}\n",
                                   "", "fresh")

                with mock.patch(GET_REFERENCE, new=self.recording(answer)):
                    ok, out = self.approve(task)

                self.assert_merged(task, ok, out, case)
                self.assertEqual(len(self.calls), 1,
                                 self.msg(f"{case}: вызовы {self.brief_calls()}\n{out}"))
                call = self.calls[0]
                final = self.origin_main()
                merge = self.merge_commit(task)
                self.assertEqual((call["task_id"], call["reason"], call["sha"]),
                                 (task["id"], "merge", final), self.msg(case))
                self.assertEqual(self.changed_files(final), {MAP_REL},
                                 self.msg(f"{case}: голова main — не коммит карты"))
                line = self.first_parent_line()
                before_map = line[line.index(final) - 1]
                for other in (merge, before_map, task["head"]):
                    self.assertNotEqual(call["sha"], other, self.msg(case))
                if case != "без приложений":
                    self.assertNotEqual(before_map, merge,
                                        self.msg("фикстура: нет коммита приложений"))
                self.assertEqual(call["origin_main"], final, self.msg("вызов до push"))
                self.assertEqual(call["state"], "done", self.msg("вызов до done"))
                self.assertTrue(call["retro"], self.msg("вызов до коммита закрытия"))
                for action in (WORKTREE_REMOVED, BRANCH_REMOVED,
                               fsm_merge_gate.MAIN_CI_AFTER_MERGE_ACTION):
                    self.assertIn(action, call["actions"],
                                  self.msg(f"вызов до «{action}»"))
                self.assertFalse(call["branch"], self.msg("вызов до уборки ветки"))
                self.assertEqual(self.refs_and_tree(), call["refs_and_tree"],
                                 self.msg("шаг изменил ссылки или дерево"))


class ArtelMergeTest(MergeSandbox):
    """Мерж задачи артели без кода пульта в дереве мержа."""

    def install_moved_hook(self) -> Path:
        marker = Path(tempfile.mkdtemp()) / "rejected-once"
        self.addCleanup(shutil.rmtree, marker.parent, ignore_errors=True)
        hook = self.origin / "hooks" / "pre-receive"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(PRE_RECEIVE.format(main=config.MAIN_BRANCH, marker=marker),
                        encoding="utf-8")
        hook.chmod(0o755)
        return marker

    def test_ac11_moved_push_does_not_trigger_the_rebuild(self):
        """Первый push в main отвергнут классом «main сдвинулся», повтор в
        том же `approve` проходит.

        В журнале есть запись «main сдвинулся во время окна — повтор
        подтяжки»; `get_reference` вызван ровно один раз — после успешного
        push (main origin в момент вызова — его `sha`), задача `done`.

        Ловит мутацию: шаг пересборки стоит до проверки исхода `"moved"`
        (или зовётся и на нём) — вызовов будет два либо первый вызов увидит
        main origin, не равный своему `sha`.
        """
        task = self.make_task()
        marker = self.install_moved_hook()

        with mock.patch(GET_REFERENCE, new=self.recording(Reference("", "", "off"))):
            ok, out = self.approve(task)

        self.assertTrue(marker.exists(), self.msg(f"хук не сработал\n{out}"))
        self.assertIn(MAIN_MOVED, self.actions(task["id"]), self.msg(out))
        self.assert_merged(task, ok, out, "moved")
        self.assertEqual(len(self.calls), 1,
                         self.msg(f"вызовы: {self.brief_calls()}\n{out}"))
        call = self.brief_calls()[0]
        self.assertEqual(call["reason"], "merge", self.msg(str(call)))
        self.assertEqual(call["sha"], self.origin_main(), self.msg(str(call)))
        self.assertEqual(call["origin_main"], call["sha"], self.msg("вызов до push"))

    def test_ac11_project_without_field_has_no_side_effects(self):
        """Запись артели в `targets.yaml` песочницы без поля
        `core_reference`, настоящий `get_reference` К-3а под наблюдением.

        `get_reference` вызван с `reason="merge"` и вернул `off`; после
        `approve` задача `done`, в области проектов песочницы нет файла
        `core-reference.md`, в журнале задачи нет записей со «справочник
        ядра», новых алертов нет.

        Ловит мутацию: шаг для проекта без поля сам строит или пишет кэш,
        пишет запись журнала сборки или поднимает алерт «поле отсутствует»
        — появятся файл, запись или алерт.
        """
        from orchestrator import reference_cache
        real = reference_cache.get_reference
        seen = []

        def spy(conn, task_id, *, reason, sha=None):
            result = real(conn, task_id, reason=reason, sha=sha)
            seen.append((reason, result))
            return result

        task = self.make_task()
        before = {row["id"] for row in alerts.open_alerts(self.conn)}

        with mock.patch(GET_REFERENCE, new=spy):
            ok, out = self.approve(task)

        self.assert_merged(task, ok, out, "без поля")
        self.assertEqual([(reason, result.state) for reason, result in seen],
                         [("merge", "off")], self.msg(f"вызовы: {seen}"))
        self.assertEqual(list(config.PROJECTS.rglob("core-reference.md")), [],
                         self.msg("файл кэша записан"))
        rows = [line for line in self.journal(task) if "справочник ядра" in line]
        self.assertEqual(rows, [], self.msg(f"записи журнала: {rows}"))
        new = [dict(row) for row in alerts.open_alerts(self.conn)
               if row["id"] not in before]
        self.assertEqual(new, [], self.msg(f"новые алерты: {new}"))

    def run_failing(self, case: str, *, raised: BaseException | None,
                    journal_error: BaseException | None = None,
                    alert_error: BaseException | None = None) -> None:
        self.calls.clear()
        task = self.make_task()
        fake = self.recording(Reference("# справочник\n", "", "fresh"), raised)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch(GET_REFERENCE, new=fake))
            if journal_error is not None:
                stack.enter_context(mock.patch.object(
                    store, "journal", self.failing_in_step(store.journal, journal_error)))
            if alert_error is not None:
                stack.enter_context(mock.patch.object(
                    alerts, "raise_alert",
                    self.failing_in_step(alerts.raise_alert, alert_error)))
            ok, out = self.approve(task)
        self.step_frame = None
        self.assertEqual(len(self.calls), 1,
                         self.msg(f"{case}: вызовы {self.brief_calls()}\n{out}"))
        self.assert_merged(task, ok, out, case)

    def test_ac12_any_exception_from_get_reference_keeps_the_merge(self):
        """`get_reference` бросает `OSError`, `RuntimeError`, `ValueError` и
        `KeyError` (тип вне перечня).

        Каждый раз `approve` завершается без исключения и без `SystemExit`,
        задача `done`, RETRO закрытия в ссылке документов origin, в журнале
        «worktree убран» и «ветка убрана», ветки задачи нет.

        Ловит мутацию: шаг без `try/except` либо с перехватом перечнем
        `(OSError, RuntimeError, ValueError)` — `KeyError` (или любое из
        исключений) прервёт `approve` исключением.
        """
        for error in (OSError, RuntimeError, ValueError, KeyError):
            with self.subTest(исключение=error.__name__, зерно=self.seed):
                self.run_failing(error.__name__, raised=error(
                    f"сбой справочника {self.rng.randrange(10 ** 6)}"))

    def test_ac12_failing_journal_and_alert_inside_the_step_keep_the_merge(self):
        """Внутри шага (пока в стеке кадр, вызвавший `get_reference`) падает
        запись журнала и/или подъём алерта: `get_reference` бросает, а
        обработчик сбоя ловит `KeyError` из `store.journal`, `KeyError` из
        `alerts.raise_alert` или оба; отдельно — `get_reference` отвечает
        штатно, а падает запись журнала шага.

        Каждый раз `approve` завершается без исключения и без `SystemExit`,
        задача `done`, коммит закрытия и уборка исполнены.

        Ловит мутацию: обработчик сбоя (запись журнала и алерт) вынесен за
        `try`, либо запись журнала результата шага стоит вне `try` —
        исключение из журнала или алерта прервёт `approve`.
        """
        scenarios = (
            ("журнал обработчика", RuntimeError, KeyError, None),
            ("алерт обработчика", OSError, None, KeyError),
            ("журнал и алерт", ValueError, KeyError, RuntimeError),
            ("журнал штатного шага", None, KeyError, None),
        )
        for case, raised, journal_error, alert_error in scenarios:
            with self.subTest(случай=case, зерно=self.seed):
                n = self.rng.randrange(10 ** 6)
                self.run_failing(
                    case,
                    raised=raised(f"сбой справочника {n}") if raised else None,
                    journal_error=journal_error(f"журнал {n}") if journal_error else None,
                    alert_error=alert_error(f"алерт {n}") if alert_error else None)


if __name__ == "__main__":
    unittest.main()
