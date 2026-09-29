"""Общий код планки 01M3P0SQQM453G9DP3NVDVGC49.

Две части:
- фикстуры текста долгоживущего файла для статической проверки
  (`guard.long_lived_errors_from_files`) — строки, на которых ждём (или не
  ждём) признак, помечены хвостовым комментарием `# @<метка>`, номер
  строки ищется по метке (`line_of`);
- песочница переходов с изолированной выгрузкой — тонкая надстройка над
  `tests/test_long_lived_transitions.py::_TransitionSandbox` (настоящий git
  пульта, bare `origin`, worktree кодовой ветки, гейты вне предмета
  подменены проходом): база ветки дополняется каталогом `tasks/` (выгрузка
  обязана его не нести) и, по требованию сценария, копией кода пульта
  (`orchestrator/`, `scripts/`, `tests/sandbox.py`) — без неё честный
  долгоживущий файл на `tests/sandbox.py` не импортируется ни в рабочей
  копии, ни в выгрузке.

Исход фикстурного долгоживущего файла переключается флагами — пустыми
файлами каталога управления `self.ctl` ВНЕ всех репозиториев: байты файла
после лока не меняются (правку отклонила бы сверка перечня), а флаг видят
оба прогона — в рабочей копии и в выгрузке.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Планка лежит в `tasks/<id>/acceptance_tests/` корня кода — и в рабочей
# копии задачи, и в материализации гейта (`acceptance.materialize_from_branch`).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import orchestrator  # noqa: E402
from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_long_lived_transitions import _TransitionSandbox  # noqa: E402

# Корень кода, который исполняет этот прогон (рабочая копия задачи на шаге,
# рабочая копия кодовой ветки на гейте) — не `Path(__file__)`: на гейте
# планка материализуется отдельно от кода.
REPO_ROOT = Path(orchestrator.__file__).resolve().parents[1]

# Номер задачи фикстур статической проверки — не номер этой задачи.
FIXTURE_TASK_ID = "01ABCDEFGHJKMNPQRSTVWXYZ00"
LABEL = "test_x.py"
CLAIM = "Ловит мутацию: фикстура статической проверки, не исполняется."

SIGN_SKIP = "пропуск"

EXPORT_HINT = ("тест привязан к настоящему репозиторию — строй копию через "
               "tests/sandbox.py")

_TAG = re.compile(r"#\s*@([\w-]+)\s*$")


def long_lived_text(body: str, group: str = guard.GROUP_LONG_LIVED) -> str:
    """Текст файла `test_*.py` с докстрингом модуля и строкой группы;
    `body` — код модуля после докстринга (без отступа)."""
    return (f'"""Фикстура файла тестов.\n\nГруппа: {group}\n"""\n'
            + body.strip("\n") + "\n")


def line_of(text: str, tag: str) -> int:
    for number, line in enumerate(text.splitlines(), start=1):
        match = _TAG.search(line)
        if match and match.group(1) == tag:
            return number
    raise AssertionError(f"метки @{tag} нет в фикстуре")


def tags_of(text: str) -> list[str]:
    return [m.group(1) for line in text.splitlines()
            if (m := _TAG.search(line))]


def errors_of(text: str, task_id: str = FIXTURE_TASK_ID) -> list[str]:
    return guard.long_lived_errors_from_files([(LABEL, text)], task_id)


def errors_on(errors: list[str], lineno: int, sign: str | None = None) -> list[str]:
    """Ошибки на строке `lineno` (с признаком `sign`, если задан)."""
    prefix = f"{LABEL}:{lineno}:"
    return [e for e in errors if e.startswith(prefix)
            and (sign is None or f"«{sign}»" in e)]


# --------------------------------------------------------------------------
# Песочница переходов с изолированной выгрузкой.

EXPORT_METHOD = "test_ac1_export_fixture"

EXPORT_FIXTURE = '''"""Фикстура долгоживущего файла: исход задают флаги каталога управления.

Группа: долгоживущий
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

CONTROL = Path({ctl!r})
HERE = Path(__file__).resolve().parents[1]

if (CONTROL / "collect").exists() and not (HERE / ".git").exists():
    raise RuntimeError("фикстура: сбор падает вне рабочей копии")


def later(case):
    getattr(case, "skip" + "Test")("фикстура: пропуск через помощника")


def toplevel(cwd):
    probe = subprocess.run(["g" + "it", "rev-parse", "--show-toplevel"],
                           cwd=cwd, capture_output=True, text=True)
    return [probe.returncode, probe.stdout.strip()]


def observe():
    record = {{"here": str(HERE), "cwd": os.getcwd(),
              "home": os.environ.get("HOME", ""),
              "dotgit": (HERE / ".git").exists(),
              "tasks": (HERE / "tasks").exists(),
              "top_here": toplevel(str(HERE)), "top_cwd": toplevel(None)}}
    with (CONTROL / "observed.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\\n")


class ExportFixtureTest(unittest.TestCase):

    def setUp(self):
        if (CONTROL / "error").exists() and not (HERE / ".git").exists():
            raise RuntimeError("фикстура: ошибка setUp вне рабочей копии")

    def {method}(self):
        """Метод фикстуры.

        Ловит мутацию: фикстура песочницы, исход задают флаги.
        """
        if (CONTROL / "observe").exists():
            observe()
        if (CONTROL / "roundabout").exists():
            self.assertTrue((HERE / ".git").exists(), "нет рабочей копии")
        if (CONTROL / "red").exists():
            self.fail("фикстура: красен в обоих прогонах")
        if (CONTROL / "skip").exists():
            later(self)
'''

HONEST_METHOD = "test_ac1_docs_branch_in_copy"

# Честный долгоживущий файл пульта (AC-9, AC-11): ветка документов
# строится во временной копии `RealGitSandbox`, каталог
# `tasks/<id>/acceptance_tests/` проверяется в ней.
HONEST_FIXTURE = '''"""Фикстура честного долгоживущего файла на tests/sandbox.py.

Ветка документов строится во временной копии песочницы.

Группа: долгоживущий
"""
import random

from orchestrator import artifact_branch, gitcmd
from tests.sandbox import RealGitSandbox


class DocsBranchInCopyTest(RealGitSandbox):

    def {method}(self):
        """Планка задачи, закоммиченная в ветку документов временной копии,
        видна в её дереве в каталоге приёмочных тестов задачи.

        Ловит мутацию: commit_files пишет мимо ветки документов — пути в
        её дереве нет.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {{seed}}")
        task = f"T{{seed}}"
        plank = self.root / f"tasks/{{task}}/acceptance_tests/test_x.py"
        rel = plank.relative_to(self.root).as_posix()
        sha = artifact_branch.commit_files(task, {{rel: "x = 1\\n"}},
                                           f"{{task}}: планка")
        self.assertTrue(sha, f"зерно: {{seed}}")
        listed = gitcmd.ls_tree_files(artifact_branch.branch_name(task),
                                      f"tasks/{{task}}/acceptance_tests")
        self.assertIn(rel, listed or [], f"зерно: {{seed}}")
'''


def honest_fixture() -> str:
    return HONEST_FIXTURE.format(method=HONEST_METHOD)


class SpyPopen(subprocess.Popen):
    """Записывает argv каждого процесса (в т.ч. через `subprocess.run`)."""

    calls: list = []

    def __init__(self, args, *rest, **kwargs):
        SpyPopen.calls.append(args)
        super().__init__(args, *rest, **kwargs)


def archive_calls(calls: list) -> list:
    """Вызовы `git archive` среди записанных argv."""
    found = []
    for argv in calls:
        if isinstance(argv, (str, bytes)):
            text = argv.decode() if isinstance(argv, bytes) else argv
            if re.search(r"\bgit\b.*\barchive\b", text):
                found.append(argv)
            continue
        parts = [str(a) for a in argv]
        if parts and Path(parts[0]).name == "git" and "archive" in parts:
            found.append(argv)
    return found


class ExportSandbox(_TransitionSandbox):
    """`_TransitionSandbox` + каталог `tasks/` в базе ветки, копия кода
    пульта (`COPY_CODE`) и каталог управления флагами `self.ctl`."""

    COPY_CODE = False
    CODE_PATHS = ("orchestrator", "scripts", "tests/__init__.py",
                  "tests/sandbox.py", "pyproject.toml")

    def setUp(self):
        super().setUp()
        self.ctl = Path(tempfile.mkdtemp(prefix="artel-export-ctl-")).resolve()
        self.addCleanup(shutil.rmtree, self.ctl, ignore_errors=True)
        # Путь каталога управления попадает литералом в фикстуру
        # долгоживущего файла — он обязан не нести признаков сам.
        self.assertNotIn("tasks/", str(self.ctl))
        self.assertNotIn(self.TASK.lower(), str(self.ctl).lower())
        self.extend_base()

    def extend_base(self) -> None:
        added = ["tasks/README.md"]
        readme = self.root / "tasks" / "README.md"
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text("каталог задач базы ветки\n", encoding="utf-8")
        if self.COPY_CODE:
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            for rel in self.CODE_PATHS:
                src, dst = REPO_ROOT / rel, self.root / rel
                if src.is_dir():
                    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
                elif src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, dst)
                else:
                    continue
                added.append(rel)
        self.git("add", "-f", "--", *added)
        self.git("commit", "-q", "-m", "база: tasks/ и код пульта")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.wt_git("merge", "-q", "--ff-only", config.MAIN_BRANCH)
        self.base_sha = self.wt_git("rev-parse", "HEAD").strip()

    def export_fixture(self) -> str:
        return EXPORT_FIXTURE.format(ctl=str(self.ctl), method=EXPORT_METHOD)

    def arm(self, *flags: str) -> None:
        for flag in flags:
            (self.ctl / flag).write_text("", encoding="utf-8")

    def disarm(self) -> None:
        for flag in ("collect", "error", "roundabout", "red", "skip", "observe"):
            (self.ctl / flag).unlink(missing_ok=True)

    def observations(self) -> list[dict]:
        path = self.ctl / "observed.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def own_name(self) -> str:
        return Path(self.own).name


def real(path: str) -> str:
    return os.path.realpath(path) if path else path


def is_within(path: str, root: Path) -> bool:
    try:
        Path(real(path)).relative_to(real(str(root)))
        return True
    except ValueError:
        return False
