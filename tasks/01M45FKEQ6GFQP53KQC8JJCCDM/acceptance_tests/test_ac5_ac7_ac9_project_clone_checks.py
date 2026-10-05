"""AC-5, AC-7, AC-9: сверки по клону проекта вместо развилок артели.

Группа: разовый
Красен до реализации: `fsm._origin_main_source` читает `targets.yaml` в обход `repo_context.resolve`, `fsm._snapshot_split_assessment` считает `diff_bytes` только артели, а `doctor` сверяет ветку артели с локальным `main` клона без fetch.

Разовый, а не долгоживущий: сценарии ведут настоящий git (клон проекта,
голый `origin`, ветки задачи) и подменяют внутренний шов пульта
(`repo_context.resolve`), а для долгоживущей группы это запрещено.

AC-5 — сверка свежести ветки на входе в гейт (`fsm._pull_main_or_escalate`,
общий узел всех точек подтяжки): база берётся из контекста
`repo_context.resolve`; неразрешённый проект — деградация «свежа», без
сравнения и мержа. Статическая часть разбирает `orchestrator/fsm.py` и
ищет обращения к модулю `targets` (и к `config.TARGETS`) в функциях модуля.
AC-7 — снимок `diff_bytes` на входе в `merge_gate` у задачи внешнего
проекта. AC-9 — `doctor` `branch-freshness` задачи артели, чья ветка
отстала от `origin/main` клона артели, ещё не принесённого fetch'ем.
"""
import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _code_root() -> Path:
    """Корень кода: планка лежит в `tasks/<id>/acceptance_tests/` рабочей
    копии; прогон из рабочей копии — её корень."""
    for candidate in (Path(__file__).resolve().parents[3], Path.cwd()):
        if (candidate / "orchestrator" / "fsm.py").is_file():
            return candidate
    return Path.cwd()


sys.path.insert(0, str(_code_root()))

from orchestrator import (config, doctor, fsm, repo_context,  # noqa: E402
                          store)
from tests.sandbox import (InitializedTmpRootTest,  # noqa: E402
                           RealGitSandbox, SchemaConnTmpRootTest,
                           clone_artel_from_origin, make_project_repo,
                           resilient_tmp_cleanup)

PROJECT = "ext"
TASK = "T001"
BRANCH = "task/t001-ext"


def run_git(repo: Path, *args: str) -> str:
    """Настоящий git в `repo`; отказ git — провал теста с его stderr."""
    res = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} в {repo}: {res.stderr}")
    return res.stdout


def commit_file(repo: Path, rel: str, text: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    run_git(repo, "add", rel)
    run_git(repo, "commit", "-q", "-m", message)
    return run_git(repo, "rev-parse", "HEAD").strip()


# --------------------------------------------------------------- AC-5 ----

def _calls_into_targets(tree: ast.Module) -> list[str]:
    """Места `orchestrator/fsm.py`, где функция модуля сама обращается к
    записи `targets.yaml`: вызов любого атрибута модуля `targets`
    (`targets.target`, `targets.load`, …), импорт имён из него или чтение
    пути `config.TARGETS`."""
    found = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "targets"):
                found.append(f"{func.name}:{node.lineno} targets."
                             f"{node.func.attr}(...)")
            if (isinstance(node, ast.Attribute) and node.attr == "TARGETS"
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "config"):
                found.append(f"{func.name}:{node.lineno} config.TARGETS")
            if (isinstance(node, ast.ImportFrom)
                    and (node.module or "").split(".")[-1] == "targets"):
                found.append(f"{func.name}:{node.lineno} from targets import")
    for node in tree.body:
        if (isinstance(node, ast.ImportFrom)
                and (node.module or "").split(".")[-1] == "targets"):
            found.append(f"<модуль>:{node.lineno} from targets import")
    return found


class FsmHasNoOwnTargetsReadTest(unittest.TestCase):

    def test_ac5_fsm_functions_do_not_read_targets_record(self):
        """В `orchestrator/fsm.py` нет функции, читающей запись `targets.yaml`.

        Сценарий: исходник `orchestrator/fsm.py` разбирается `ast`; в телах
        его функций ищутся вызовы модуля `targets`, импорт из него и чтение
        `config.TARGETS`. Наблюдаемое: таких мест нет (сегодня —
        `_origin_main_source`, `targets.target(...)`).
        Ловит мутацию: дубль `resolve` оставлен в fsm.py (адрес и база
        читаются `targets.target(name)["url"]/["base"]` в обход
        `repo_context.resolve`) — список найденных мест не пуст и
        называет функцию и строку.
        """
        source = Path(fsm.__file__).read_text(encoding="utf-8")
        found = _calls_into_targets(ast.parse(source))
        self.assertEqual(
            found, [],
            "orchestrator/fsm.py сам читает запись targets.yaml (адрес "
            "удалённого источника/базу) вместо repo_context.resolve: "
            + "; ".join(found))


class FreshnessSourceFromResolveTest(RealGitSandbox):
    """Внешний проект `ext`: клон с голым `origin`, запись в `targets.yaml`
    (адрес — путь этого `origin`, база — `config.MAIN_BRANCH`), ветка
    задачи отходит от `main` клона. Главная копия пульта — git-репозиторий
    песочницы, её `origin` смотрит в тот же голый репозиторий: так откат
    на «origin/main пульта» тоже нашёл бы, с чем сравнить."""

    RECOGNISABLE_BASE = "release-ac5"

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.clone = make_project_repo(PROJECT)
        self.bare = config.PROJECTS / PROJECT / "origin.git"
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            text.replace(f"file:///nonexistent/{PROJECT}", str(self.bare)),
            encoding="utf-8")
        self.git("remote", "add", "origin", str(self.bare))
        run_git(self.clone, "branch", BRANCH, config.MAIN_BRANCH)
        store.insert_task(self.conn, TASK, "Внешняя задача", "in_dev", BRANCH,
                          PROJECT, config.DEFAULT_BUDGET_USD)
        self.real_resolve = repo_context.resolve

    def branch_head(self) -> str:
        return run_git(self.clone, "rev-parse", BRANCH).strip()

    def advance_ref_on_origin(self, ref: str) -> str:
        """Кодовый коммит поверх `main` клона, отправленный в `origin` веткой
        `ref`; локальные ветки клона остаются на месте."""
        run_git(self.clone, "checkout", "-q", "-b", "scratch-ac5",
                config.MAIN_BRANCH)
        sha = commit_file(self.clone, "app_ac5.py", "VALUE = 1\n",
                          f"код на {ref}")
        run_git(self.clone, "push", "-q", "origin", f"HEAD:refs/heads/{ref}")
        run_git(self.clone, "checkout", "-q", config.MAIN_BRANCH)
        return sha

    def pull_gate(self) -> str:
        t = store.get_task(self.conn, TASK)
        return fsm._pull_main_or_escalate(self.conn, TASK, t, "in_dev",
                                          run_plank=False)

    def test_ac5_freshness_base_comes_from_resolve(self):
        """База сверки свежести — `base` контекста `repo_context.resolve`.

        Сценарий: `resolve` проекта `ext` подменён и отдаёт контекст его
        клона с узнаваемой базой `release-ac5` (в `targets.yaml` база —
        `main`); в `origin` эта ветка на кодовый коммит впереди ветки
        задачи, а `main` в `origin` с веткой задачи совпадает. Наблюдаемое:
        узел сверки свежести возвращает «pulled», голова ветки задачи
        содержит коммит `release-ac5`.
        Ловит мутацию: база по-прежнему читается из `targets.yaml` (дубль
        `resolve` в fsm.py) — сверка идёт с `main`, ветка «свежа», исход
        «fresh», коммита `release-ac5` в ветке нет.
        """
        ahead = self.advance_ref_on_origin(self.RECOGNISABLE_BASE)
        ctx = repo_context.RepoContext(
            path=self.clone, remote=str(self.bare),
            base=self.RECOGNISABLE_BASE, target=PROJECT)

        def resolve(name):
            return ctx if name == PROJECT else self.real_resolve(name)

        with mock.patch.object(repo_context, "resolve", side_effect=resolve):
            outcome = self.pull_gate()

        self.assertEqual(outcome, "pulled",
                         "сверка свежести не взяла базу из repo_context.resolve")
        contains = subprocess.run(
            ["git", "-C", str(self.clone), "merge-base", "--is-ancestor",
             ahead, BRANCH], capture_output=True, text=True)
        self.assertEqual(contains.returncode, 0,
                         f"коммит базы {self.RECOGNISABLE_BASE} не влит в "
                         f"ветку задачи")

    def test_ac5_unresolved_project_degrades_without_compare_or_merge(self):
        """Неразрешённый проект — деградация: ни сравнения, ни мержа.

        Сценарий: `origin` проекта (он же `origin` главной копии пульта) на
        кодовый коммит впереди ветки задачи по `main`, запись `targets.yaml`
        цела, но `repo_context.resolve` для проекта отдаёт `None`.
        Наблюдаемое: исход «fresh», голова ветки задачи не сдвинулась,
        коммита `origin/main` в ней нет.
        Ловит мутацию: при `None` от `resolve` fsm сам дочитывает
        `targets.yaml` либо откатывается на `"origin"`/`config.MAIN_BRANCH`
        пульта — коммит `origin/main` находится, ветка подтягивается,
        исход «pulled» и голова ветки сдвинута.
        """
        self.advance_ref_on_origin(config.MAIN_BRANCH)
        before = self.branch_head()

        def resolve(name):
            return None if name == PROJECT else self.real_resolve(name)

        with mock.patch.object(repo_context, "resolve", side_effect=resolve):
            outcome = self.pull_gate()

        self.assertEqual(outcome, "fresh",
                         "неразрешённый проект обязан деградировать в «свежа»")
        self.assertEqual(self.branch_head(), before,
                         "ветку неразрешённого проекта смержили с main")


# --------------------------------------------------------------- AC-7 ----

class ExternalDiffBytesSnapshotTest(SchemaConnTmpRootTest):

    def test_ac7_external_task_gets_diff_bytes_from_project_clone(self):
        """У задачи внешнего проекта на входе в `merge_gate` есть `diff_bytes`.

        Сценарий: клон проекта `ext` с `origin`, ветка задачи от `main` с
        одним кодовым коммитом; снимок входа в `merge_gate`
        (`fsm._snapshot_split_assessment`). Наблюдаемое: `diff_bytes` равен
        размеру в байтах `git diff main...<ветка>` в клоне проекта (база —
        `main` = `origin/main`, ветка от неё и отходит; хвостовой перевод
        строки вывода git допускается в обе стороны).
        Ловит мутацию: diff по-прежнему считается только для артели
        (`target == config.DEFAULT_TARGET`) либо в клоне артели —
        `diff_bytes` остаётся NULL или несёт чужое число.
        """
        clone = make_project_repo(PROJECT)
        run_git(clone, "checkout", "-q", "-b", BRANCH)
        commit_file(clone, "src/feature_ac7.py",
                    "def feature():\n    return 'ac7'\n", "код задачи")
        run_git(clone, "checkout", "-q", config.MAIN_BRANCH)
        raw = run_git(clone, "diff", f"{config.MAIN_BRANCH}...{BRANCH}")
        self.assertTrue(raw.strip())
        # Размер диффа — с завершающим переводом строки вывода git или без
        # него (пульт читает вывод git, срезая хвост).
        expected = {len(raw.encode("utf-8")),
                    len(raw.rstrip("\n").encode("utf-8"))}
        store.insert_task(self.conn, TASK, "Внешняя задача", "acceptance",
                          BRANCH, PROJECT, config.DEFAULT_BUDGET_USD)

        fsm._snapshot_split_assessment(self.conn, TASK,
                                       store.get_task(self.conn, TASK))

        self.assertIn(store.get_task(self.conn, TASK)["diff_bytes"], expected,
                      "diff_bytes внешней задачи не равен размеру диффа её "
                      "кодовой ветки от базы в клоне проекта")


# --------------------------------------------------------------- AC-9 ----

class ArtelBranchFreshnessViaCloneOriginTest(InitializedTmpRootTest):

    def test_ac9_artel_task_behind_clone_origin_main_warns(self):
        """Ветка артели, отставшая от `origin/main` клона, даёт warn `doctor`.

        Сценарий: клон артели заведён из голого `origin`; ветка задачи
        артели — на `main` клона; затем в `origin` из другой рабочей копии
        уходит `config.STALE_BRANCH_WARN_COMMITS + 1` коммитов, клон их ещё
        не fetch'ил (локальный `main` клона с веткой совпадает).
        Наблюдаемое: `doctor.check_branch_freshness` даёт `warn`
        `branch-freshness`, называющий задачу.
        Ловит мутацию: для артели оставлена своя ветка логики — сравнение с
        локальным `main` клона без fetch базы — отставание 0, проверка «ok».
        """
        work = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, work)
        bare = self.root / "artel-origin.git"
        run_git(self.root, "init", "-q", "--bare", str(bare))
        pusher = Path(work.name) / "pusher"
        run_git(self.root, "clone", "-q", str(bare), str(pusher))
        run_git(pusher, "config", "user.email", "artel@example.invalid")
        run_git(pusher, "config", "user.name", "artel tests")
        run_git(pusher, "checkout", "-q", "-b", config.MAIN_BRANCH)
        commit_file(pusher, "README", "artel\n", "init")
        run_git(pusher, "push", "-q", "origin", config.MAIN_BRANCH)

        clone = clone_artel_from_origin(bare)
        run_git(clone, "branch", BRANCH, config.MAIN_BRANCH)
        conn = store.db()
        store.insert_task(conn, TASK, "Задача артели", "in_dev", BRANCH,
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

        for n in range(config.STALE_BRANCH_WARN_COMMITS + 1):
            commit_file(pusher, f"code_{n}.py", f"N = {n}\n", f"main {n}")
        run_git(pusher, "push", "-q", "origin", config.MAIN_BRANCH)

        checks = doctor.check_branch_freshness(conn)

        warns = [c for c in checks
                 if c.name == "branch-freshness" and c.status == "warn"]
        self.assertTrue(
            any(TASK in c.detail for c in warns),
            f"нет warn branch-freshness для задачи артели, отставшей от "
            f"origin/{config.MAIN_BRANCH} клона: "
            f"{[(c.status, c.detail) for c in checks]}")


if __name__ == "__main__":
    unittest.main()
