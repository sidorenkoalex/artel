"""Юнит-тесты исключения `docs/codebase-map.md` из diff ревью-пакета
(ANSWER-1 задачи 01M31DRD81092HB69J0MAKZMGH, вопрос 1, вариант A).

Предыстория: гейт ёмкости перестал мерить карту, а сборщик пакета
по-прежнему клал её ревьюверу внутрь diff (`tasks_dir_exclude` исключал
только `tasks/<id>/`) — мера гейта стала меньше того, что получает
ревьювер, на размер diff карты (R1-F1, REVIEW.md итерация 1; факт 21.09
— 47 987 байт). Здесь проверяется обратное: карты нет ни в полном, ни в
инкрементальном diff пакета, её объём назван заметкой, а исключающий
pathspec у гейта и у пакета — ОДИН узел `review.snapshot_exclude`.

Поддельный `gitcmd.git` не отдаёт заготовку на любой `diff`, а РАЗБИРАЕТ
pathspec вызова и применяет его к дереву — тест привязан к наблюдаемому
свойству «карты в диффе нет», а не к порядку аргументов (тот же приём,
что в планке задачи `acceptance_tests/test_ac5_ac7_capacity_gate_map.py`).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import config, gitcmd, review, store  # noqa: E402
from orchestrator.advance_gates import capacity  # noqa: E402

TASK = "T001"
BRANCH = "task/t001-karta"
MAP_REL = "docs/codebase-map.md"
CODE_REL = "orchestrator/models.py"


def chunk(path: str, size: int) -> str:
    """Кусок diff ровно `size` байт (ASCII) — байты меряются уже после
    `stdout.strip()` внутри `review.git_diff_part`."""
    head = f"diff --git a/{path} b/{path}\n"
    return head + "+" + "x" * max(1, size - len(head) - 1)


def matches(path: str, spec: str) -> bool:
    if spec == ".":
        return True
    if spec.startswith(":(literal)"):
        spec = spec[len(":(literal)"):]
    if spec.endswith("/"):
        return path.startswith(spec)
    return path == spec or path.startswith(spec + "/")


class PathspecAwareGit:
    """`gitcmd.git`, честно применяющий pathspec вызова `git diff` к
    дереву `files` (путь -> кусок diff), включая исключения `:!`.

    `own_paths` — ответ на `git log --name-only` (`review.own_commit_paths`):
    пути СОБСТВЕННЫХ коммитов ветки для инкрементального diff.
    """

    def __init__(self, files: dict, own_paths=()):
        self.files = dict(files)
        self.own_paths = tuple(own_paths)
        self.diff_calls: list[list[str]] = []

    def __call__(self, *args) -> subprocess.CompletedProcess:
        argv = list(args)
        if argv[:1] == ["show"]:
            # Артефактов задачи в этой песочнице нет — пакет честно
            # отметит «не показан», состава diff это не касается.
            return subprocess.CompletedProcess(argv, 128, "", "fatal: no path")
        if argv[:1] == ["log"]:
            return subprocess.CompletedProcess(
                argv, 0, "\0".join(("", *self.own_paths)), "")
        if argv[:1] == ["ls-tree"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:2] == ["rev-parse", "--verify"]:
            # Ни ветки задачи, ни ref origin/main — база берётся от
            # локального main, как и в остальных песочницах пакета.
            return subprocess.CompletedProcess(argv, 1, "", "")
        if argv[:1] == ["merge-base"]:
            return subprocess.CompletedProcess(argv, 0, argv[1], "")
        if argv[:1] == ["rev-parse"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:1] == ["diff"]:
            self.diff_calls.append(argv)
            return self._diff(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    def _diff(self, argv) -> subprocess.CompletedProcess:
        specs = argv[argv.index("--") + 1:] if "--" in argv else ["."]
        excludes = [s[2:] for s in specs if s.startswith(":!")]
        includes = [s for s in specs if not s.startswith(":!")] or ["."]
        selected = [p for p in sorted(self.files)
                    if any(matches(p, s) for s in includes)
                    and not any(matches(p, s) for s in excludes)]
        if "--stat" in argv:
            body = "\n".join(f" {p} | 2 +-" for p in selected)
        else:
            body = "\n".join(self.files[p] for p in selected)
        return subprocess.CompletedProcess(argv, 0, body, "")


class ReviewPackageMapTest(unittest.TestCase):
    """Состав diff ревью-пакета: карта в него не входит, её объём назван."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root), ("TASKS", self.root / "tasks"),
                            ("WORKTREES", self.root / ".artel" / "worktrees"),
                            ("DB", self.root / ".artel" / "state.db")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.conn = store.db()
        store.create_schema(self.conn)

    def build(self, files: dict, own_paths=(), **kwargs) -> tuple[dict, list]:
        git = PathspecAwareGit(files, own_paths)
        with mock.patch.object(gitcmd, "git", git):
            package = review.review_package(self.conn, TASK, "Карта в пакете",
                                            BRANCH, **kwargs)
        return package, git.diff_calls

    def test_full_diff_of_the_package_does_not_carry_the_map(self):
        """Итерация 1, diff ветки — код и карта. В пакет обязан попасть
        только код: карта исключена тем же pathspec `:!`, что и
        `tasks/<id>/`.

        Ловит мутацию: исключение карты добавлено только в гейт ёмкости,
        а сборщик пакета остался на прежнем pathspec — ревьювер снова
        получает байты, которых гейт не мерил.
        """
        files = {CODE_REL: chunk(CODE_REL, 400),
                 MAP_REL: chunk(MAP_REL, 900),
                 f"tasks/{TASK}/PLAN.md": chunk(f"tasks/{TASK}/PLAN.md", 300)}

        package, calls = self.build(files)

        diff_call = [c for c in calls if "--stat" not in c][0]
        self.assertIn(f":!{MAP_REL}", diff_call,
                      f"карта обязана исключаться pathspec'ом: {diff_call}")
        self.assertIn(f":!tasks/{TASK}/", diff_call,
                      f"исключение артефактов задачи обязано остаться: "
                      f"{diff_call}")
        self.assertIn(chunk(CODE_REL, 400), package["text"],
                      "diff кода обязан остаться в пакете целиком")
        self.assertNotIn(chunk(MAP_REL, 900), package["text"],
                         "тело diff карты не имеет права попасть в пакет")

    def test_incremental_diff_excludes_the_map_among_own_commit_paths(self):
        """Итерация 2 с базой вердикта: собственные коммиты ветки тронули
        и код, и карту. Инкремент обязан нести только код — исключающий
        pathspec один и тот же для обоих видов diff.

        Ловит мутацию: исключение карты добавлено только в ветку полного
        diff, а инкрементальная собирает pathspec из своих литералов —
        со второй итерации ревью карта возвращается в пакет, и гейт
        ёмкости опять мерит меньше, чем получает ревьювер.
        """
        files = {CODE_REL: chunk(CODE_REL, 400), MAP_REL: chunk(MAP_REL, 900)}

        package, calls = self.build(files, own_paths=(CODE_REL, MAP_REL),
                                    iteration=2, prev_sha="abc123")

        self.assertEqual(package["diff_type"], "инкрементальный")
        diff_call = [c for c in calls if "--stat" not in c][0]
        self.assertIn(f":!{MAP_REL}", diff_call,
                      f"инкремент обязан исключать карту тем же pathspec: "
                      f"{diff_call}")
        self.assertIn(chunk(CODE_REL, 400), package["text"])
        self.assertNotIn(chunk(MAP_REL, 900), package["text"],
                         "карта не имеет права вернуться в пакет инкрементом")

    def test_note_names_the_excluded_map_and_its_volume(self):
        """Заметка пакета называет обе исключённые части и объём карты
        цифрой в байтах; карты в диффе нет — «0 байт (изменений нет)», а
        не размер строки-плейсхолдера.

        Ловит мутацию: diff молча урезан без заметки — ревьювер читает
        сокращённый снимок как полный и не знает, сколько байт ревью не
        смотрит.
        """
        body = chunk(MAP_REL, 900)
        size = len(body.encode("utf-8"))
        files = {CODE_REL: chunk(CODE_REL, 400), MAP_REL: body}

        package, _ = self.build(files)

        self.assertIn(MAP_REL, package["text"],
                      "заметка обязана назвать исключённую карту")
        self.assertIn(f"{size} байт", package["text"],
                      "объём исключённой карты обязан быть назван цифрой")
        self.assertIn(f"tasks/{TASK}/", package["text"],
                      "исключение артефактов задачи обязано называться рядом")

        empty, _ = self.build({CODE_REL: chunk(CODE_REL, 400)})
        self.assertIn("0 байт (изменений нет)", empty["text"])
        placeholder = len(review.EMPTY_DIFF_TEXT.encode("utf-8"))
        self.assertNotIn(f"{placeholder} байт", empty["text"],
                         "пустой diff карты не имеет права меряться байтами "
                         "строки-плейсхолдера")


class SnapshotExcludeSharedNodeTest(unittest.TestCase):
    """Мера гейта ёмкости и diff пакета — один узел, а не два литерала."""

    def test_gate_and_package_share_one_exclude_pathspec(self):
        """`orchestrator/advance_gates/capacity.py` берёт исключающий
        pathspec и узел цифры импортом из `review`, а сам pathspec несёт
        оба исключения.

        Ловит мутацию: в гейте (или в пакете) заведена своя копия
        кортежа — она разойдётся ровно так, как уже разошлась один раз
        на `docs/codebase-map.md`, и заметить это будет нечем.
        """
        self.assertIs(capacity._snapshot_exclude, review.snapshot_exclude)
        self.assertIs(capacity._excluded_note, review.excluded_note)
        self.assertIs(capacity.MAP_REL, review.MAP_REL)
        self.assertEqual(review.snapshot_exclude(TASK),
                         (".", f":!tasks/{TASK}/", f":!{MAP_REL}"))


if __name__ == "__main__":
    unittest.main()
