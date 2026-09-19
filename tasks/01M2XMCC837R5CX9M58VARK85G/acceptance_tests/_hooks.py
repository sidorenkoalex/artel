"""Общие помощники планки 01M2XMCC837R5CX9M58VARK85G (защита main
главной копии git-хуками).

Здесь только то, что нужно больше чем одному `test_*.py`: адреса файлов
хуков, именованный текст отказа требования 2 SPEC, временный git-репозиторий
с включёнными хуками и `origin`, а также запуск git с/без маркера пульта.

Песочница переходов FSM (`tests.sandbox.LightTransitionSandbox`) здесь не
используется и не переопределяется: предмет планки — настоящий git и
настоящие хуки, а не переходы конечного автомата.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# tasks/<id>/acceptance_tests/_hooks.py -> корень репозитория
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "scripts" / "git-hooks"
HOOK_NAMES = ("pre-commit", "pre-push")

# Значение `core.hooksPath`, которым задача включает хуки (SPEC, требование
# 4 и AC-2/AC-11) — относительный путь от корня рабочего дерева.
HOOKS_PATH_VALUE = "scripts/git-hooks"

MARKER_ENV = "ARTEL_PULT_GIT"
MARKER_VALUE = "1"

# Именованный текст отказа требования 2 SPEC, без ведущего «коммит/push»:
# pre-commit вправе сказать «коммит в main…», pre-push — «push в main…»,
# общая часть у обоих обязана быть дословной.
REFUSAL_CORE = (
    "в main главной копии — только командой пульта "
    "(note, doc-commit, pin-update, approve на merge_gate); "
    "обход по решению Оператора: ARTEL_PULT_GIT=1"
)


def squeeze(text: str) -> str:
    """Схлопнутые пробелы/переводы строк — сверка текста отказа не должна
    зависеть от того, как автор хука разбил фразу на строки."""
    return re.sub(r"\s+", " ", text).strip()


def base_env(marker: bool) -> dict:
    """Окружение git-процесса песочницы: копия окружения теста, из которой
    маркер пульта либо убран, либо выставлен явно."""
    env = {k: v for k, v in os.environ.items() if k != MARKER_ENV}
    if marker:
        env[MARKER_ENV] = MARKER_VALUE
    return env


def run_git(repo: Path, *args: str, marker: bool = False,
            stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, env=base_env(marker),
                          input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def output(res: subprocess.CompletedProcess) -> str:
    return squeeze(f"{res.stdout}\n{res.stderr}")


class HookedRepoTest(unittest.TestCase):
    """Временный репозиторий с веткой main, одним коммитом и ВКЛЮЧЁННЫМИ
    хуками задачи (`core.hooksPath = scripts/git-hooks`).

    Файлы хуков копируются из репозитория и получают бит исполнения уже в
    песочнице: предмет тестов ниже — логика самих хуков, а не режим файлов
    в индексе git (его отдельно проверяют тесты doctor, AC-10/AC-11).
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve() / "repo"
        self.repo.mkdir(parents=True)

        self.git_ok("init", "-q", "-b", "main")
        self.git_ok("config", "user.email", "plank@artel.invalid")
        self.git_ok("config", "user.name", "plank")
        # Первый коммит — ДО включения хуков: иначе pre-commit отказал бы
        # самой подготовке песочницы.
        self.write("marker.txt", "main\n")
        self.git_ok("add", "marker.txt")
        self.git_ok("commit", "-q", "-m", "init")

        self.install_hooks()

    # --- вспомогательное ---------------------------------------------------

    def install_hooks(self) -> None:
        dest = self.repo / "scripts" / "git-hooks"
        dest.mkdir(parents=True, exist_ok=True)
        for name in HOOK_NAMES:
            src = HOOKS_DIR / name
            self.assertTrue(
                src.is_file(),
                f"нет файла хука {src} — требование 1 SPEC ещё не выполнено")
            shutil.copy2(src, dest / name)
            os.chmod(dest / name, 0o755)
        self.git_ok("config", "core.hooksPath", HOOKS_PATH_VALUE)

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def git_ok(self, *args: str, marker: bool = False) -> str:
        res = run_git(self.repo, *args, marker=marker)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def head(self) -> str:
        return self.git_ok("rev-parse", "HEAD", marker=True).strip()

    def stage(self, rel: str, text: str) -> None:
        self.write(rel, text)
        # `git add` хуков не запускает — маркер не нужен.
        self.git_ok("add", rel)

    def commit(self, message: str, *, marker: bool
               ) -> subprocess.CompletedProcess:
        return run_git(self.repo, "commit", "-q", "-m", message, marker=marker)

    def add_origin(self) -> Path:
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "--bare", str(origin)],
                       check=True, capture_output=True)
        self.git_ok("remote", "add", "origin", str(origin))
        return origin

    def push(self, refspec: str, *, marker: bool
             ) -> subprocess.CompletedProcess:
        return run_git(self.repo, "push", "origin", refspec, marker=marker)
