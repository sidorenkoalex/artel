"""Факты задачи «бриф: шаблон артефакта роли целиком» на дереве ветки.

Группа: разовый
Красен до реализации: метод tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package ещё не несёт вставки элемента show main:templates/PLAN.md (AC-12), а карта docs/codebase-map.md не перегенерирована после добавления долгоживущего файла задачи в tests/ (AC-14); AC-11 держит неизменность пяти тестов миссий и зелен с рождения.

Критерии AC-1…AC-10 проверяет долгоживущий файл задачи в `tests/`
(`test_ac<n>_…` там). Здесь — то, что после мержа проверять не на чем:
текст тестовых файлов против базы диффа задачи (`DIFF_BASE` помощника
пульта), зелёный прогон названных методов и свежесть карты на дереве
рабочей копии ветки.
"""
# AC-13: manual — мутации требования 6 — правки ещё не написанного кода brief.py/role_prompt.py: до реализации нельзя назвать ни место, ни форму мутанта, а планка запирается раньше кода, поэтому детерминированный прогон «каждый тест краснеет на своей мутации» написать сейчас невозможно. Тесты на все мутации требования 6 с заявками «Ловит мутацию» — долгоживущий файл этой планки (tests/test_<id>_role_templates.py); автор планки прогнал их на временном стабе реализации и на её мутантах (каждая мутация требования 6 красит хотя бы один метод), ревьюер сверяет заявки дополнительных тестов разработчика по диффу.
import difflib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

REVIEW_TEST = "tests/test_review_package.py"
REVIEW_METHOD = "test_developer_step_has_no_package"
REVIEW_NODE = f"{REVIEW_TEST}::CmdRunReviewPackageTest::{REVIEW_METHOD}"
INSERTED = '["-C",root,"show","main:templates/PLAN.md"],'
MISSION_NODES = (
    "tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py",
    "tests/test_docs_dir_layout.py::MissionNamesDocsDirTest",
    "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::MissionTest",
    "tests/test_role_prompt_test_author_mission.py",
    "tests/test_long_lived_manifest.py::RolePromptTest::"
    "test_test_author_and_developer_missions_name_own_prefix",
)
MAP_REL = "docs/codebase-map.md"


def git(*args: str) -> str:
    res = subprocess.run(["git", "-C", CODE_ROOT, *args], capture_output=True,
                         text=True, encoding="utf-8")
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def base_text(rel: str) -> str:
    if not DIFF_BASE:
        raise AssertionError("база диффа задачи не определена при выкладке")
    return git("show", f"{DIFF_BASE}:{rel}")


def disk_text(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def pytest_run(*nodes: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *nodes, "-q", "-p", "no:cacheprovider",
         "-p", "timeout", "-o", "timeout=120"],
        cwd=CODE_ROOT, capture_output=True, text=True, encoding="utf-8")


def without_built_at(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if not ln.startswith("built_at_sha:")]


class MissionTestsUnchangedTest(unittest.TestCase):

    def test_ac11_mission_tests_unchanged_and_green(self):
        """Пять тестов `mission_brief_package(None, …)` не тронуты и зелёные.

        Сценарий: текст каждого из файлов `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`,
        `tests/test_docs_dir_layout.py`, `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`,
        `tests/test_role_prompt_test_author_mission.py`, `tests/test_long_lived_manifest.py`
        в рабочей копии равен тексту на базе диффа задачи; названные в ТЗ
        классы и методы этих файлов проходят прогоном pytest.

        Ловит мутацию: шаблон читается в `role_prompt.mission_brief_package`,
        а не внутри подменяемых функций брифа, — соединение `None` роняет
        тесты миссий; либо разработчик правит эти тесты под новое
        поведение — текст файла расходится с базой."""
        files = sorted({node.split("::")[0] for node in MISSION_NODES})
        for rel in files:
            with self.subTest(file=rel):
                self.assertEqual(disk_text(rel), base_text(rel),
                                 f"{rel} изменён относительно базы {DIFF_BASE}")
        res = pytest_run(*MISSION_NODES)
        self.assertEqual(res.returncode, 0,
                         f"тесты миссий красные:\n{res.stdout[-4000:]}")


class ReviewPackageExpectationTest(unittest.TestCase):

    def test_ac12_developer_step_list_changes_by_one_insertion(self):
        """Ожидание `test_developer_step_has_no_package` меняется ровно одной вставкой.

        Сценарий: построчное сравнение `tests/test_review_package.py` базы
        диффа задачи и рабочей копии. Единственное отличие — вставка, чей
        текст без пробелов равен `["-C",root,"show","main:templates/PLAN.md"],`;
        она стоит в теле метода `test_developer_step_has_no_package` сразу
        перед элементом `["config", "--get", "user.name"]`, а строка перед
        ней завершает элемент `ls-tree … tasks/<id>`. Метод проходит
        прогоном pytest.

        Ловит мутацию: ожидание ослаблено (`assertEqual` списка заменён
        проверкой вхождения, элементы удалены или переставлены) — в
        сравнении появляется удаление или замена; вставка не в том месте
        списка; файл не тронут — вставки нет, а метод красен."""
        base = base_text(REVIEW_TEST).splitlines()
        head = disk_text(REVIEW_TEST).splitlines()
        changes = [op for op in difflib.SequenceMatcher(
            None, base, head, autojunk=False).get_opcodes() if op[0] != "equal"]
        self.assertEqual([op[0] for op in changes], ["insert"],
                         f"изменения файла — не одна вставка: {changes}")
        _tag, i1, _i2, j1, j2 = changes[0]
        inserted = "".join("".join(ln.split()) for ln in head[j1:j2])
        self.assertEqual(inserted, INSERTED, f"вставлено: {head[j1:j2]}")
        start = next(i for i, ln in enumerate(base)
                     if ln.strip().startswith(f"def {REVIEW_METHOD}("))
        end = next((i for i in range(start + 1, len(base))
                    if base[i].strip().startswith("def ")), len(base))
        self.assertTrue(start < i1 < end, "вставка вне метода")
        self.assertTrue(
            base[i1].strip().startswith('["config", "--get", "user.name"]'),
            f"после вставки идёт {base[i1]!r}")
        self.assertTrue(base[i1 - 1].strip().endswith('f"tasks/{self.TASK}"],'),
                        f"перед вставкой идёт {base[i1 - 1]!r}")
        self.assertIn("ls-tree", "\n".join(base[i1 - 3:i1]),
                      "перед вставкой — не элемент ls-tree")
        res = pytest_run(REVIEW_NODE)
        self.assertEqual(res.returncode, 0,
                         f"{REVIEW_NODE} красный:\n{res.stdout[-4000:]}")


class CodebaseMapFreshTest(unittest.TestCase):

    def test_ac14_codebase_map_matches_generator_on_branch_tree(self):
        """`docs/codebase-map.md` ветки совпадает с выводом генератора на её дереве.

        Сценарий: дерево HEAD ветки (`orchestrator/`, `scripts/`, `tests/`)
        выгружается `git archive` во временный каталог; карта строится
        функциями `scripts/codebase_map.py` ветки и сравнивается с
        закоммиченной `docs/codebase-map.md` построчно без строки
        `built_at_sha:` — тем же правилом, что CI-джоба `codebase-map`.

        Ловит мутацию: разработчик правит `orchestrator/brief.py` или
        добавляет тесты в `tests/`, не перегенерировав карту, — секции
        модулей и их публичные функции в карте расходятся с генератором."""
        sys.path.insert(0, CODE_ROOT)
        from scripts import codebase_map
        committed = git("show", f"HEAD:{MAP_REL}")
        sha = next((ln.split(":", 1)[1].strip() for ln in committed.splitlines()
                    if ln.startswith("built_at_sha:")), "")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tree.tar"
            git("archive", "--format=tar", "-o", str(archive), "HEAD",
                *codebase_map.MODULE_DIRS)
            tree = Path(tmp) / "tree"
            tree.mkdir()
            with tarfile.open(archive) as tar:
                tar.extractall(tree, filter="data")
            modules, resolved, imported_by = codebase_map.build_modules(tree)
            fresh = codebase_map.render(modules, resolved, imported_by, sha)
        diff = list(difflib.unified_diff(without_built_at(committed),
                                         without_built_at(fresh), lineterm="",
                                         n=0))
        self.assertEqual(diff, [], "карта стухла:\n" + "\n".join(diff[:40]))


if __name__ == "__main__":
    unittest.main()
