"""Приёмочные тесты 01M297HFSKV3GVZJ9YF20FZEZE (AC-4..AC-6): новая
проверка `doctor` «pin-unpushed» — непушенные коммиты HEAD `config.ROOT`
относительно `origin/<config.MAIN_BRANCH>` после `git fetch origin`.

Красен до реализации: `doctor.check_pin_unpushed` — функция ЭТОЙ задачи,
её ещё нет в `orchestrator/doctor/` (единственная сегодняшняя сверка
пина, `check_root_pin`, — другая семантика: `ls-remote` без `fetch` и
только `ok`/`warn`, никогда `fail`, см. материалы SPEC.md). Импорт
`doctor.check_pin_unpushed` падает `AttributeError` — все четыре теста
красны по этой причине. Имя функции — по единственному соглашению
именования во всём пакете `orchestrator/doctor/` (каждая `check_<суффикс>`
заводит `Check("<суффикс-через-дефис>", ...)`, без исключений: `check_
root_pin` -> `"root-pin"`, `check_branch_freshness` -> `"branch-freshness"`,
`check_canary_trigger` -> `"canary-trigger"` и т.д.) — «условно pin-unpushed»
SPEC.md транслируется в `check_pin_unpushed`.

Настоящий git (`RealGitSandbox` из `tests/sandbox.py` + свой bare
`origin`): предмет проверки — исход РЕАЛЬНОГО `git fetch`/сверки
предковости, заглушкой `gitcmd.git` не изобразить (тот же приём, что
`tests/test_doctor.py::CanaryTriggerCheckTest`, соседний реальный
git-чек в том же пакете).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


def _git_in(cwd: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                         text=True)
    assert res.returncode == 0, f"git {' '.join(args)} упал: {res.stderr}"
    return res.stdout


class _PinUnpushedSandbox(RealGitSandbox):
    """`config.ROOT` — настоящий git-репозиторий (один коммит на
    `config.MAIN_BRANCH`, из `RealGitSandbox`) с настоящим bare
    `origin`, изначально синхронным с HEAD."""

    def setUp(self):
        super().setUp()
        self.origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin",
                f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def local_only_commit(self, message: str, filename: str) -> str:
        """Коммит в `config.ROOT`, никогда не запушенный в `origin`."""
        (self.root / filename).write_text("x\n", encoding="utf-8")
        self.git("add", filename)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def break_origin(self) -> None:
        self.git("remote", "set-url", "origin",
                 str(self.root / "no-such-origin-here"))


class PinUnpushedOkTest(_PinUnpushedSandbox):

    def test_ac5_head_equal_to_origin_is_ok(self):
        """HEAD `config.ROOT` совпадает с `origin/<MAIN_BRANCH>` (только
        что запушен) — проверка обязана вернуть `ok`, не `fail`/`warn`.

        Ловит мутацию: сравнение предковости инвертировано (например,
        `is_ancestor(origin_sha, root_sha)` вместо `is_ancestor(root_sha,
        origin_sha)`) — при точном совпадении шас обе формы дают одно и
        то же True, но сорвало бы соседний AC-4 (см. тот файл); здесь
        отдельно фиксируем сам факт `ok` на синхронном пине как базовую
        линию, не зависящую от направления сравнения.
        """
        check = doctor.check_pin_unpushed()

        self.assertEqual(check.status, "ok")

    def test_ac5_head_ancestor_of_origin_is_ok(self):
        """HEAD `config.ROOT` — СТРОГИЙ предок `origin/<MAIN_BRANCH>`
        (кто-то другой запушил дальше в origin, локальный пин не
        уходил вперёд) — тоже `ok` (критерий явно перечисляет оба случая:
        «совпадает с ИЛИ является его предком»).

        Ловит мутацию: критерий сужен до точного равенства шас (`==`)
        без слоя `is_ancestor` — эта пометка `ok` расширяет случай
        строгого предка, отдельного от точного совпадения; такая мутация
        красит именно этот тест, не test_ac5_head_equal_to_origin_is_ok.
        """
        clone_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, clone_dir, ignore_errors=True)
        _git_in(clone_dir.parent, "clone", "-q", str(self.origin),
               str(clone_dir))
        _git_in(clone_dir, "config", "user.email",
               "artel-tests@example.invalid")
        _git_in(clone_dir, "config", "user.name", "artel tests")
        (clone_dir / "ahead.txt").write_text("y\n", encoding="utf-8")
        _git_in(clone_dir, "add", "-A")
        _git_in(clone_dir, "commit", "-q", "-m", "origin ушёл вперёд")
        _git_in(clone_dir, "push", "-q", "origin", config.MAIN_BRANCH)

        check = doctor.check_pin_unpushed()

        self.assertEqual(check.status, "ok")


class PinUnpushedFailTest(_PinUnpushedSandbox):

    def test_ac4_unpushed_head_fails_and_lists_the_commits(self):
        """HEAD `config.ROOT` ушёл ВПЕРЁД `origin/<MAIN_BRANCH>` (два
        коммита сделаны прямо в главной копии и не запушены) — проверка
        обязана вернуть `fail`, сообщение — перечислить sha и первую
        строку КАЖДОГО непушенного коммита и подсказать `note`/`pin --to`/
        `pin-update`.

        Ловит мутацию: сверка предковости пропущена/инвертирована — при
        HEAD, ушедшем вперёд origin, `is_ancestor(HEAD, origin)` ложно, и
        неверная реализация (например, всегда `ok`, либо сравнение
        `HEAD == origin_sha`, которое здесь тоже ложно, но не ведёт к
        `fail` без явной ветки на этот случай) не даст ожидаемый статус
        и текст.
        """
        sha1 = self.local_only_commit("документный коммит один",
                                      "doc-one.txt")
        sha2 = self.local_only_commit("документный коммит два",
                                      "doc-two.txt")

        check = doctor.check_pin_unpushed()

        self.assertEqual(check.status, "fail")
        self.assertIn(sha1[:7], check.detail)
        self.assertIn("документный коммит один", check.detail)
        self.assertIn(sha2[:7], check.detail)
        self.assertIn("документный коммит два", check.detail)
        self.assertIn("note", check.detail)
        self.assertIn("pin --to", check.detail)
        self.assertIn("pin-update", check.detail)


class PinUnpushedWarnTest(_PinUnpushedSandbox):

    def test_ac6_fetch_failure_is_warn_not_ok(self):
        """`git fetch origin <MAIN_BRANCH>` отказывает (origin недоступен)
        — статус обязан быть `warn` с текстом «сверка с origin
        невозможна», НЕ `ok` (критерий явно противопоставляет её
        деградации `check_root_pin`, которая в этом же случае отвечает
        `ok`).

        Ловит мутацию: копирование деградации `check_root_pin` (fetch/
        ls-remote не ответил -> `ok`) вместо собственной ветки `warn`,
        которую явно требует AC-6.
        """
        self.break_origin()

        check = doctor.check_pin_unpushed()

        self.assertEqual(check.status, "warn")
        self.assertIn("сверка с origin невозможна", check.detail)


if __name__ == "__main__":
    unittest.main()
