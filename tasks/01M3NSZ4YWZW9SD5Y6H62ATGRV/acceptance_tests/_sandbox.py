"""Песочница планки задачи 01M3NSZ4YWZW9SD5Y6H62ATGRV: вложенная задача
target `artel` на НАСТОЯЩЕМ git — пульт `config.ROOT` с веткой документов
(`artifact_branch`), bare `origin` и worktree кодовой ветки.

Основа — `tests/test_long_lived_transitions.py::_TransitionSandbox`
(задача 2 ADR-0020): она уже умеет заводить свой долгоживущий файл
`tests/test_<id>_alpha.py`, выходить из `tests_writing` настоящими гейтами
(перечень сумм пишется в дерево лока) и коммитить в кодовую ветку. Здесь
только надстройка сценария правки после лока: правка Оператора в worktree
без коммита, вызов `amend.cmd_amend_tests`, снимок трёх голов (кодовая
ветка, ветка документов, `tests_locked_sha`), ожидаемый перечень по
байтам головы кодовой ветки и сверка сумм тем же узлом, что стоит на
переходах (`advance_gates.acceptance._long_lived_manifest_refuses`).

Почему настоящий git, а не `LightTransitionSandbox`: предмет критериев —
коммиты в две ветки, SHA-256 байтов блоба на голове кодовой ветки, дерево
коммита лока и pathspec настоящего `git diff`; заглушка отвечала бы на всё
это вымыслом.

Вложенная задача (переопределено поверх `_TransitionSandbox`): два
критерия SPEC; разовая планка `acceptance_tests/test_ac1_plank.py`
покрывает AC-1 (и AC-2 — при `PLANK_COVERS_AC2 = True`), долгоживущий
файл `tests/test_<id>_alpha.py` несёт метод `test_ac2_long_fixture`.
"""
import contextlib
import hashlib
import importlib.util
import io
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (amend, artifact_branch, brief, gitcmd,  # noqa: E402
                          store)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_long_lived_transitions import (  # noqa: E402
    SPEC_TEXT, _TransitionSandbox)

MANIFEST_NAME = guard.LONG_LIVED_MANIFEST_NAME
FIXED_RUN_ID = "0123456789abcdef0123456789abcdef"

PLANK_TEMPLATE = '''"""Фикстура разовой планки вложенной задачи.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):
{methods}'''

PLANK_METHOD = '''
    def {name}(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''

LONG_LIVED_TEMPLATE = '''"""Фикстура долгоживущего файла вложенной задачи.

{group_line}
"""
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def {method}(self):
        """Фикстурный метод.
{claim}
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, {rhs}, f"зерно: {{seed}}")
{tail}'''

CLAIM = "\n        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.\n"


def plank_source(methods=("test_ac1_plank_fixture",)) -> str:
    return PLANK_TEMPLATE.format(methods="".join(
        PLANK_METHOD.format(name=name) for name in methods))


def long_lived_source(method: str = "test_ac2_long_fixture", *,
                      group: str | None = "долгоживущий", claim: bool = True,
                      rhs: str = "2", tail: str = "") -> str:
    """Текст долгоживущего файла; параметры ломают по одной проверке:
    `group=None` — нет строки группы, `claim=False` — метод без «Ловит
    мутацию», `rhs="3"` — непромаркированное падение, `tail` — хвост
    модуля (статический признак, синтаксическая ошибка, метка правки)."""
    return LONG_LIVED_TEMPLATE.format(
        group_line=f"Группа: {group}" if group else "Фикстура без строки группы.",
        method=method, claim=CLAIM if claim else "", rhs=rhs, tail=tail)


def call(fn, *args, **kwargs) -> tuple[object, str]:
    """(код выхода, вывод): `None` — функция вернулась без `SystemExit`."""
    buf = io.StringIO()
    code = None
    with redirect_stdout(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
            buf.write(f"\nSystemExit: {exc.code}")
    return code, buf.getvalue()


def failed(code) -> bool:
    return code is not None and code != 0


class AmendSandbox(_TransitionSandbox):
    """Задача залочена (`in_dev`) с непустым перечнем: в дереве лока —
    сумма `tests/test_<id>_alpha.py` на голове кодовой ветки."""

    CRITERIA = ("AC-1. Первый критерий вложенной задачи.\n\n"
                "AC-2. Второй критерий вложенной задачи.")
    PLANK_COVERS_AC2 = False

    def setUp(self):
        super().setUp()
        methods = ["test_ac1_plank_fixture"]
        if self.PLANK_COVERS_AC2:
            methods.append("test_ac2_plank_fixture")
        self.artifact_commit(
            {"SPEC.md": SPEC_TEXT.format(task=self.TASK, criteria=self.CRITERIA),
             "acceptance_tests/test_ac1_plank.py": plank_source(methods)},
            "SPEC и планка вложенной задачи")
        self.own_text = self.own_source()
        self.lock_with_own(self.own_text)
        self.docs_branch = artifact_branch.branch_name(self.TASK)
        self.tdir = self.wt / "tasks" / self.TASK
        self.plank_dir = self.tdir / "acceptance_tests"
        self.new_path = f"tests/test_{self.TASK.lower()}_beta.py"

    def own_source(self) -> str:
        """Текст долгоживущего файла перечня на момент лока."""
        return long_lived_source()

    # --- наблюдение ---------------------------------------------------

    def heads(self) -> tuple:
        """(голова кодовой ветки, голова ветки документов, tests_locked_sha)."""
        return (gitcmd.branch_head_sha(self.branch),
                gitcmd.branch_head_sha(self.docs_branch),
                self.row()["tests_locked_sha"])

    def manifest_at(self, rev: str) -> str | None:
        text, _reason = gitcmd.show(
            rev, acceptance_gates.long_lived_manifest_rel(self.TASK))
        return text

    def plank_file_at(self, rev: str, name: str) -> str | None:
        text, _reason = gitcmd.show(
            rev, f"tasks/{self.TASK}/acceptance_tests/{name}")
        return text

    def long_lived_paths_at(self, rev: str) -> list[str]:
        present = gitcmd.ls_tree_files(rev, "tests") or []
        return sorted(p for p in present
                      if guard.is_long_lived_test_path(self.TASK, p))

    def expected_manifest(self, code_head: str) -> str:
        """Перечень Р2 по байтам долгоживущих файлов головы кодовой ветки."""
        return guard.render_long_lived_manifest(
            {p: acceptance_gates.blob_sha256(code_head, p)
             for p in self.long_lived_paths_at(code_head)})

    def changed_paths(self, old: str, new: str) -> set[str]:
        return set(gitcmd.git("diff", "--name-only", old, new).stdout.split())

    def manifest_check_refuses(self) -> tuple[bool, str]:
        """Сверка сумм — тот же узел, что на рубежах Р4 и гейте мержа."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            refused = acceptance_gates._long_lived_manifest_refuses(
                store.db(), self.TASK)
        return refused, buf.getvalue()

    def amend_events(self) -> int:
        return sum(1 for s in store.task_steps(store.db(), self.TASK)
                   if amend.AMEND_ACTION in s["action"])

    # --- действия -----------------------------------------------------

    def write_wt(self, rel: str, text: str) -> Path:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def materialize_plank(self) -> None:
        """Каталог приёмочных тестов головы ветки документов — на диск
        worktree (то, с чего Оператор начинает правку планки руками)."""
        prefix = f"tasks/{self.TASK}/"
        for rel, text in artifact_branch.read_tree(self.TASK).items():
            if rel.startswith(prefix + "acceptance_tests/"):
                self.write_wt(rel, text)

    def restore_wt(self) -> None:
        """Worktree — к голове кодовой ветки; планка на диске — к голове
        ветки документов."""
        self.wt_git("checkout", "-q", "--", "tests")
        self.wt_git("clean", "-q", "-fd", "--", "tests", "docs")
        if self.plank_dir.is_dir():
            for f in sorted(self.plank_dir.rglob("*"), reverse=True):
                if f.is_file():
                    f.unlink()
            self.materialize_plank()

    def amend(self, reason: str = "правка долгоживущего теста") -> tuple:
        return call(amend.cmd_amend_tests, self.TASK, reason)

    def amend_from_branch(self, reason: str = "восстановление") -> tuple:
        return call(amend.cmd_amend_tests, self.TASK, reason, from_branch=True)

    @contextlib.contextmanager
    def docs_branch_write_fails(self):
        """Любая запись под `tasks/<id>/` плотницким коммитом (путь ветки
        документов: `artifact_branch.commit_files` -> `write_commit`) не
        удаётся; прочие записи идут настоящим git."""
        real = artifact_branch.write_commit
        prefix = f"tasks/{self.TASK}/"

        def failing(repo, files, *args, **kwargs):
            touched = list(files) + list(kwargs.get("remove") or [])
            if any(str(rel).startswith(prefix) for rel in touched):
                return ""
            return real(repo, files, *args, **kwargs)

        with mock.patch.object(artifact_branch, "write_commit", failing):
            yield

    def sha256_of_wt(self, rel: str) -> str:
        return hashlib.sha256((self.wt / rel).read_bytes()).hexdigest()


# --- «до задачи»: база ветки задачи в настоящем репозитории ------------

def task_diff_base() -> tuple[str | None, str]:
    """(база, причина): точка расхождения ветки рабочей копии с `origin`
    (`gitcmd.diff_base`) — от неё считается «до задачи»."""
    res = gitcmd.in_repo(REPO_ROOT, "rev-parse", "--abbrev-ref", "HEAD")
    if res is None or res.returncode != 0:
        return None, "git не ответил на имя ветки рабочей копии"
    base = gitcmd.diff_base(res.stdout.strip(), repo=REPO_ROOT)
    if not base:
        return None, "gitcmd.diff_base не ответил"
    return base, ""


def text_at(rev: str, rel: str) -> str | None:
    res = gitcmd.in_repo(REPO_ROOT, "show", f"{rev}:{rel}")
    if res is None or res.returncode != 0:
        return None
    return res.stdout


def review_module_before_task() -> tuple[types.ModuleType | None, str]:
    """`orchestrator/review.py` с базы ветки задачи — отдельным модулем
    пакета `orchestrator` (его относительные импорты указывают на те же
    модули, что у текущего `review`)."""
    base, reason = task_diff_base()
    if base is None:
        return None, reason
    source = text_at(base, "orchestrator/review.py")
    if source is None:
        return None, f"orchestrator/review.py не прочитан на базе {base}"
    name = "orchestrator.review_before_task_01m3nsz4"
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "orchestrator"
    exec(compile(source, f"<review.py@{base}>", "exec"), module.__dict__)
    return module, ""


@contextlib.contextmanager
def fixed_run_id():
    with mock.patch.object(brief, "new_run_id", lambda: FIXED_RUN_ID):
        yield


def boundary_markers() -> tuple[str, str]:
    lines = brief.wrap_boundary(FIXED_RUN_ID, "x").split("\n")
    return lines[0], lines[-1]
