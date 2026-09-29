"""Песочница планки задачи 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ: ВЛОЖЕННАЯ задача
target `artel` на НАСТОЯЩЕМ git (`RealPultGitTest`, tests/test_git_fixation.py
— пульт `config.ROOT` с артефактной веткой задачи) плюс bare `origin` и
worktree кодовой ветки (`workspace.ensure`, тот же приём, что
`tests/test_timeout_checkpoint.py::_WorktreeCheckpointTest`).

Почему настоящий git, а не `LightTransitionSandbox`: предмет критериев —
дифф кодовой ветки против базы (`gitcmd.diff_base`), наличие пути в
`origin/main`, SHA-256 содержимого файла на голове кодовой ветки, дерево
коммита лока в ветке документов. Заглушка `gitcmd.git` лёгкой песочницы
отвечает на всё это вымыслом, и тест проверял бы не код, а заглушку.

База ветки несёт два файла `tests/`, заведённых на `main` ДО ветки задачи:
`tests/test_existing.py` (файл без префикса задачи) и
`tests/test_<id чужой задачи>_legacy.py` (долгоживущий файл «уже
смерженной» задачи). Оба несут метод `test_ac1_…` — одноимённый методу
критерия AC-1 вложенной задачи (AC-10).

Переходы после `tests_writing` наблюдаются через публичные входы
(`fsm.cmd_advance`, `fsm.cmd_approve`) и названную SPEC точку гейта мержа
(`fsm_merge_gate._cmd_approve_merge_gate` после `_sync_main_or_wait`).
Гейты этих переходов, НЕ относящиеся к предмету планки (ёмкость, зоны,
приложения, заявка мутации, неослабление, переделка ревью, CI, origin,
подтяжка main, полный набор, автогейт), подменены проходом: иначе
песочнице пришлось бы изображать CI, GitHub и ревью целиком. Лок
каталога приёмочных тестов (`_acceptance_lock_refuses`) и прогон планки
(`acceptance.run`) НЕ подменяются — они часть предмета (AC-13, AC-18,
AC-19).
"""
import contextlib
import hashlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (acceptance, artifact_branch, checkpoint, ci,  # noqa: E402
                          config, fsm, fsm_advance, fsm_autogate,
                          fsm_merge_gate, github_adapter, gitcmd, runner,
                          store, workspace)
from tests.test_git_fixation import PLAN_READY, RealPultGitTest  # noqa: E402

REFUSAL_PREFIX = "переход отклонён"
MANIFEST_NAME = "long_lived.sha256.txt"
# Подсказка требования 7 — две опорные части, между которыми реализация
# вправе поставить своё тире/кавычки.
HINT_CODE = re.compile(r"код\s+чинится\s+под\s+тест", re.I)
HINT_AMEND = "amend-tests"

# Идентификатор «уже смерженной» задачи, чей долгоживущий файл лежит в
# базе: правдоподобный ULID, отличный от id вложенной задачи.
OTHER_TASK_ID = "01M3AAAAAAAAAAAAAAAAAAAAAA"

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
{extra}---

# SPEC: вложенная песочница

## Контекст

## Требования

## Критерии приёмки

{criteria}

## Не входит
"""

REVIEW_APPROVED = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: вложенная песочница
"""

# Файл планки вложенной задачи (разовый): `methods` — имена методов
# `test_ac<n>_…`, все проходят.
PLANK_TEMPLATE = '''"""Фикстура разового файла планки вложенной задачи.

Группа: разовый
Зелёный с рождения: фикстура вложенной песочницы — входные данные сценария.
"""
import unittest


class FixturePlankTest(unittest.TestCase):
{methods}
'''

PLANK_METHOD = '''
    def {name}(self):
        """Фикстурный метод разового файла."""
        self.assertEqual(1 + 1, 2)
'''

# Долгоживущий файл вложенной задачи: без единого признака требования 3
# задачи 1 (только стандартная библиотека, ни `tasks/`, ни id задачи, ни
# закрытых имён), у каждого метода — заявка мутации, входы от `random`
# с напечатанным зерном. `body` — строки уровня модуля после импортов.
LONG_LIVED_TEMPLATE = '''"""Фикстура долгоживущего файла вложенной задачи.

Группа: {group}
Красен до реализации: фикстура вложенной песочницы — входные данные сценария.
"""
import random
import unittest
{body}

class FixtureLongLivedTest(unittest.TestCase):
{methods}
'''

LONG_LIVED_METHOD = '''
    def {name}(self):
        """Фикстурный метод долгоживущего файла.

        {claim}
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {{seed}}")
        self.assertEqual({left}, {right}, f"зерно: {{seed}}")
'''

CLAIM = "Ловит мутацию: фикстура вложенной песочницы — сумма перестаёт совпадать."


def plank_source(methods=("test_ac1_plank_fixture",)) -> str:
    return PLANK_TEMPLATE.format(
        methods="".join(PLANK_METHOD.format(name=m) for m in methods))


def long_lived_source(methods=("test_ac1_long_fixture",), group="долгоживущий",
                      body="", claim=CLAIM, failing=(), tag="") -> str:
    """Текст долгоживущего файла; `failing` — имена методов, которые
    падают при исполнении; `tag` — комментарий, меняющий байты файла без
    смены поведения (правка файла после лока)."""
    parts = []
    for m in methods:
        right = "3" if m in failing else "2"
        parts.append(LONG_LIVED_METHOD.format(name=m, claim=claim,
                                              left="1 + 1", right=right))
    text = LONG_LIVED_TEMPLATE.format(group=group, body=body,
                                      methods="".join(parts))
    if tag:
        text += f"# {tag}\n"
    return text


EXISTING_TESTS_SOURCE = '''"""Существующий файл tests/ базы (не задачи)."""
import unittest


class ExistingTest(unittest.TestCase):

    def test_ac1_legacy(self):
        """Метод базы, одноимённый критерию AC-1 вложенной задачи."""
        self.assertTrue(True)
'''


def sibling_task_id(task_id: str, keep: int) -> str:
    """Id «соседней» задачи: первые `keep` знаков совпадают с `task_id`,
    каждый следующий — другой (алфавит Crockford base32, как у ULID)."""
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    tail = "".join(alphabet[(alphabet.index(c) + 1) % len(alphabet)]
                   for c in task_id[keep:])
    return task_id[:keep] + tail


def mentions(text: str, *needles: str) -> bool:
    return all(n in text for n in needles)


def capture_call(fn, *args, **kwargs) -> str:
    """Вывод вызова; `SystemExit` — часть вывода (именованный отказ)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            buf.write(f"\nSystemExit: {exc}")
    return buf.getvalue()


class LongLivedSandbox(RealPultGitTest):
    """Вложенная задача в `tests_writing` с worktree кодовой ветки."""

    CRITERIA = "AC-1. Единственный критерий вложенной песочницы."
    SPEC_EXTRA = ""
    WITH_PLANK = True

    def setUp(self):
        super().setUp()
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.prefix = self.TASK.lower()
        self.other_prefix = OTHER_TASK_ID.lower()
        # База ветки: существующие файлы tests/ на main ДО ветки задачи.
        tests_dir = self.root / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_existing.py").write_text(
            EXISTING_TESTS_SOURCE, encoding="utf-8")
        (tests_dir / f"test_{self.other_prefix}_legacy.py").write_text(
            long_lived_source(), encoding="utf-8")
        self.git("add", "tests")
        self.git("commit", "-q", "-m", "база: существующие tests/")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        wt_path, error = workspace.ensure(self.TASK, self.branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt = wt_path
        self.base_sha = self.wt_git("rev-parse", "HEAD").strip()
        files = {"SPEC.md": SPEC_TEXT.format(
            task=self.TASK, extra=self.SPEC_EXTRA, criteria=self.CRITERIA)}
        if self.WITH_PLANK:
            files["acceptance_tests/test_ac1_plank.py"] = plank_source()
        self.artifact_commit(files, "SPEC и планка вложенной задачи")
        self.set_row(state="tests_writing")

    # ------------------------------------------------------------ БД/журнал
    def set_row(self, **fields) -> None:
        store.update_task(store.db(), self.TASK, **fields)

    def row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.row()["state"]

    def last_step_id(self) -> int:
        row = store.db().execute(
            "SELECT MAX(id) AS m FROM steps WHERE task_id=?",
            (self.TASK,)).fetchone()
        return row["m"] or 0

    def steps_since(self, step_id: int) -> list[str]:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? AND id>? "
            "ORDER BY id", (self.TASK, step_id)).fetchall()
        return [f"{r['action']} {r['detail'] or ''}" for r in rows]

    # ------------------------------------------------------ кодовая ветка
    def ll_path(self, name: str) -> str:
        return f"tests/test_{self.prefix}_{name}.py"

    def wt_git(self, *args: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.wt), "-c", "user.name=artel tests",
             "-c", "user.email=artel@example.invalid", *args],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def wt_write(self, rel: str, text: str) -> None:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def wt_commit(self, files: dict | None = None, remove=(), rename=None,
                  message: str = "правка кодовой ветки") -> None:
        """Коммит в кодовую ветку задачи мимо пульта (сценарная правка):
        `files` — записать, `remove` — удалить, `rename` — (из, в)."""
        for rel, text in (files or {}).items():
            self.wt_write(rel, text)
        for rel in remove:
            self.wt_git("rm", "-q", "--", rel)
        if rename:
            self.wt_git("mv", rename[0], rename[1])
        self.wt_git("add", "-A", "--", ".", f":(exclude)tasks/{self.TASK}")
        self.wt_git("commit", "-q", "-m", message)

    def reset_branch(self) -> None:
        """Кодовая ветка — снова ровно база (между сценариями одного теста);
        задача — снова в `tests_writing` без лока."""
        self.wt_git("reset", "-q", "--hard", self.base_sha)
        self.wt_git("clean", "-q", "-fd", "--", ".",
                    f":(exclude)tasks/{self.TASK}")
        self.set_row(state="tests_writing", tests_locked_sha=None)

    def branch_text(self, rel: str) -> str | None:
        """Текст `rel` в дереве головы кодовой ветки; `None` — пути нет."""
        res = subprocess.run(["git", "show", f"{self.branch}:{rel}"],
                             cwd=self.root, capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else None

    # ------------------------------------------------------------ чекпоинт
    def checkpoint(self, kind: str, role: str = "test_author") -> list[str]:
        """Чекпоинт шага роли; записи журнала, появившиеся за него.

        `success` — исход «шаг завершён» (rc=0) тем же узлом, которым его
        проводит `runner` (`runner._finish_ok`: чекпоинт кода, затем
        автокоммит артефактов); `timeout` — WIP-чекпоинт таймаута шага."""
        before = self.last_step_id()
        conn = store.db()
        if kind == "success":
            pump = types.SimpleNamespace(error=None, cost=None)
            capture_call(runner._finish_ok, conn, self.TASK, role, pump, 0,
                         "попытка 1/1", "")
        elif kind == "timeout":
            capture_call(checkpoint.commit_timeout_checkpoint, conn,
                         self.TASK, role)
        else:
            raise AssertionError(f"неизвестный чекпоинт {kind!r}")
        return self.steps_since(before)

    def head_sha256(self, rel: str) -> str:
        """SHA-256 байтов `rel` в дереве головы кодовой ветки."""
        res = subprocess.run(["git", "show", f"{self.branch}:{rel}"],
                             cwd=self.root, capture_output=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return hashlib.sha256(res.stdout).hexdigest()

    def branch_has(self, rel: str, rev: str | None = None) -> bool:
        res = subprocess.run(["git", "cat-file", "-e",
                              f"{rev or self.branch}:{rel}"],
                             cwd=self.root, capture_output=True)
        return res.returncode == 0

    def push_main_file(self, rel: str, text: str) -> None:
        """Путь появляется в `origin/main` ПОСЛЕ ответвления ветки задачи."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", rel)
        self.git("commit", "-q", "-m", f"main: {rel}")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")

    # --------------------------------------------------- ветка документов
    def artifact_branch(self) -> str:
        return artifact_branch.branch_name(self.TASK)

    def artifact_commit(self, files: dict, message: str) -> None:
        artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/{rel}": text for rel, text in files.items()},
            f"{self.TASK}: {message}")

    def artifact_show(self, rel: str, rev: str | None = None):
        return gitcmd.show(rev or self.artifact_branch(),
                           f"tasks/{self.TASK}/{rel}")

    def manifest_at_lock(self) -> str | None:
        locked = self.row()["tests_locked_sha"]
        self.assertTrue(locked, "лок tests_locked_sha не записан")
        text, _ = gitcmd.show(locked,
                              f"tasks/{self.TASK}/acceptance_tests/{MANIFEST_NAME}")
        return text

    # ---------------------------------------------------------- переходы
    def advance(self) -> tuple[str, list[str]]:
        before = self.last_step_id()
        out = capture_call(fsm.cmd_advance, self.TASK)
        return out, self.steps_since(before)

    def exit_tests_writing(self) -> tuple[str, list[str]]:
        self.set_row(state="tests_writing")
        return self.advance()

    def lock_with(self, files: dict) -> None:
        """Кодовая ветка несёт `files` (долгоживущие файлы задачи), выход
        из `tests_writing` пройден — перечень и лок записаны."""
        if files:
            self.wt_commit(files, message="долгоживущие файлы задачи")
        out, entries = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev",
                         f"выход из tests_writing не пройден: {entries!r}\n{out}")

    def in_dev_patches(self) -> contextlib.ExitStack:
        stack = contextlib.ExitStack()
        for name in ("_capacity_gate_refuses", "_zones_gate_refuses",
                     "_plan_appendix_gate_refuses",
                     "_test_integrity_gate_refuses",
                     "_review_rework_gate_refuses"):
            stack.enter_context(mock.patch.object(fsm_advance, name,
                                                  return_value=False))
        for name in ("_mutation_claim_gate", "_origin_push_gate"):
            stack.enter_context(mock.patch.object(fsm_advance, name,
                                                  return_value=None))
        stack.enter_context(mock.patch.object(
            fsm, "_pull_main_or_escalate", return_value="fresh"))
        return stack

    def advance_in_dev(self) -> tuple[str, list[str]]:
        """`in_dev -> verifying` (PLAN.md ready в ветке документов)."""
        self.artifact_commit({"PLAN.md": PLAN_READY.format(task=self.TASK)},
                             "PLAN готов")
        self.set_row(state="in_dev")
        with self.in_dev_patches():
            return self.advance()

    def advance_verifying(self) -> tuple[str, list[str]]:
        """`verifying -> review` (CI ветки зелёный)."""
        self.set_row(state="verifying")
        with mock.patch.object(ci, "verifying_status",
                               return_value=(ci.VERIFYING_GREEN,
                                             "CI ветки зелёный (тест)")):
            return self.advance()

    def advance_review(self) -> tuple[str, list[str]]:
        """`review -> acceptance` (REVIEW.md approved в ветке документов)."""
        self.artifact_commit({"REVIEW.md": REVIEW_APPROVED.format(task=self.TASK)},
                             "REVIEW approved")
        self.set_row(state="review", reviewed_iter=0)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(fsm, "guard_refuses",
                                                  return_value=False))
            stack.enter_context(mock.patch.object(fsm, "_dirty_refuses",
                                                  return_value=False))
            stack.enter_context(mock.patch.object(
                fsm_advance, "_review_escalation_sha_gate", return_value=None))
            stack.enter_context(mock.patch.object(
                fsm_autogate, "_maybe_autogate_acceptance", return_value=None))
            return self.advance()

    def approve_acceptance(self) -> tuple[str, list[str]]:
        """`acceptance -> merge_gate` командой `approve`."""
        self.set_row(state="acceptance")
        green = acceptance.FullSuiteRun(True, acceptance.FULL_SUITE_GREEN,
                                        "1 passed in 0.01s", None,
                                        "зелёный прогон (тест)")
        before = self.last_step_id()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(fsm, "confirm_fixation",
                                                  return_value=True))
            stack.enter_context(mock.patch.object(
                fsm, "_pull_main_or_escalate", return_value="fresh"))
            stack.enter_context(mock.patch.object(acceptance, "full_suite",
                                                  return_value=green))
            stack.enter_context(mock.patch.object(github_adapter, "undraft_mr",
                                                  return_value=None))
            out = capture_call(fsm.cmd_approve, self.TASK)
        return out, self.steps_since(before)

    def merge_gate_body(self) -> tuple[tuple | None, str, list[str]]:
        """Тело гейта мержа до CI: подтяжка — «свежо», CI — сторож-исход
        `("wait", …)`, до которого тело доходит, только если ни один
        рубеж после `_sync_main_or_wait` не отказал."""
        self.set_row(state="merge_gate")
        before = self.last_step_id()
        result = {}
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                fsm_merge_gate, "_protected_path_diff_gate", return_value=False))
            stack.enter_context(mock.patch.object(
                fsm_merge_gate, "_test_integrity_diff_gate", return_value=False))
            stack.enter_context(mock.patch.object(
                fsm_merge_gate, "_ensure_branch_head_published",
                return_value="ok"))
            stack.enter_context(mock.patch.object(
                fsm, "_pull_main_or_escalate", return_value="fresh"))
            stack.enter_context(mock.patch.object(
                fsm_merge_gate, "_ci_ready_or_wait",
                side_effect=lambda task_id, note, branch: ("wait", branch)))
            conn = store.db()
            out = capture_call(
                lambda: result.setdefault("outcome", fsm_merge_gate.
                                          _cmd_approve_merge_gate(
                                              conn, self.TASK, "merge_gate",
                                              store.get_task(conn, self.TASK))))
        return result.get("outcome"), out, self.steps_since(before)

