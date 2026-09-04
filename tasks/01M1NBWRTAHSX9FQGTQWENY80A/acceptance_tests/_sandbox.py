"""Общая песочница приёмочных тестов задачи 01M1NBWRTAHSX9FQGTQWENY80A
(ANSWER-n.md в ревью-пакете).

НЕ подкласс `tests.test_review_package.CmdRunReviewPackageTest` (первая
версия этого файла делала именно так) — та фикстура САМА несёт ~10
тестовых методов; наследование конкретного `TestCase` с готовыми
`test_*` в базовый класс, импортируемый КАЖДЫМ из пяти `test_ac*.py`
этого каталога, заставляет `unittest discover` заново собрать и
прогнать эти ~10 методов в КАЖДОМ импортирующем модуле (тестовый id
называет класс по его настоящему `__module__`, но набор `TestCase`
подтягивается через `dir()` того модуля, где он ИМПОРТИРОВАН, а не
только определён) — экспериментально проверено при написании этого
файла: пять файлов дали «Ran 110 tests» вместо ожидаемых ~60, из них
~50 — чистое дублирование одного и того же прогона. Здесь — свой
`TestCase`, ТОЛЬКО с `setUp`/хелперами, без единого `test_*` — тот же
приём, что `tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/
_sandbox.py::HeadInOriginSandbox` (тоже голый `unittest.TestCase` без
тестов, не подкласс готового теста).

`setUp` — адаптация `tests.test_review_package.CmdRunReviewPackageTest.
setUp` (тот же `FakeGit`/`catalog.cmd_new`/`runner.cmd_run` каркас, что
уже используют существующие тесты ревью-пакета) — переиспользуются
только ДАННЫЕ модуля (`FakeGit`, `SPEC_MD`, `PLAN_MD`, `FORM_MD`, не
`TestCase`), копия логики setUp неизбежна ровно из-за проблемы выше.

`FakeGit` сама по себе НЕ эмулирует `git ls-tree` (нужную поиску ВСЕХ
`ANSWER-n.md` задачи на ветке — тем же способом, каким уже сегодня ищет
ПОСЛЕДНИЙ ANSWER `brief._latest_answer_rel` для чужой ветки,
`gitcmd.ls_tree_files`): её `__call__` матчит `"--name-only" in args`
раньше, чем успевает заметить `args[0] == "ls-tree"` — тот же флаг несёт
и `git diff --name-only` (сверка свежести карты), и `git ls-tree -r
--name-only`. Экспериментально проверено при написании этого файла:
временный стаб реализации, вызывающий `gitcmd.ls_tree_files`, находил
НОЛЬ файлов ANSWER на этой заглушке, хотя `self.git.files` их нёс —
`AnswerAwareFakeGit` ниже — минимальная подмена ИМЕННО `ls-tree`,
отвечающая путями из `self.files`, остальное делегирует оригиналу.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import FakeProc, SpyRun, capture, capture_new_task_id  # noqa: E402
from tests.test_review_package import FakeGit, FORM_MD, PLAN_MD, SPEC_MD  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


class AnswerAwareFakeGit(FakeGit):
    """`FakeGit` + `git ls-tree -r --name-only <branch> -- <rel_dir>`,
    отвечающий путями `self.files`, чей ключ лежит под `rel_dir` (см.
    докстринг модуля — иначе `--name-only` в аргументах `ls-tree`
    матчится веткой `FakeGit`, предназначенной для СОВСЕМ ДРУГОГО
    запроса, сверки свежести карты)."""

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        if args and args[0] == "ls-tree":
            self.calls.append(list(args))
            if self.returncode:
                return subprocess.CompletedProcess(
                    list(args), self.returncode, "", self.stderr)
            rel_dir = args[-1].rstrip("/") + "/"
            paths = [p for p in self.files if p.startswith(rel_dir)]
            return subprocess.CompletedProcess(
                list(args), 0, "\n".join(paths), "")
        return super().__call__(*args)


class AnswerInReviewPackageSandbox(unittest.TestCase):
    """Доводит свежую задачу до состояния `review` на заглушке
    `gitcmd.git` (`FakeGit`) и даёт `run_agent`/`prompt`/`package_text`/
    `journal_details`/`add_answer` — без единого собственного `test_*`
    (см. докстринг модуля)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in ("skills", "templates"):
            shutil.copytree(REPO / name, root / name)
        (root / "docs").mkdir()
        (root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        for attr, value in (("ROOT", root),
                            ("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        skill_files = {f"skills/{p.name}": p.read_text(encoding="utf-8")
                       for p in (root / "skills").glob("*.md")}
        self.git = AnswerAwareFakeGit(files={
            "templates/REVIEW.md": FORM_MD,
            "CLAUDE.md": (root / "CLAUDE.md").read_text(encoding="utf-8"),
            **skill_files,
        })
        git_patcher = mock.patch.object(gitcmd, "git", self.git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        wt_patcher = mock.patch.object(
            runner.workspace, "ensure",
            lambda task_id, branch: (root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)

        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Ревью-пакет вместо свободного чтения")
        self.git.files.update({f"tasks/{self.TASK}/SPEC.md": SPEC_MD,
                               f"tasks/{self.TASK}/PLAN.md": PLAN_MD})
        self.git.calls.clear()
        self.tdir = config.TASKS / self.TASK

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def run_agent(self, state: str) -> tuple[str, list[str]]:
        self.set_state(state)
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = capture(runner.cmd_run, self.TASK)
        self.prompt_path = Path(popen.call_args.kwargs["stdin"].name)
        return out, popen.call_args.args[0]

    def prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def add_answer(self, n: int, text: str) -> None:
        """Кладёт `tasks/<TASK>/ANSWER-<n>.md` В ВЕТКУ задачи (`self.git.
        files`) — тем же способом, каким фикстура уже кладёт туда
        SPEC.md/PLAN.md (штатная картина: артефакты закоммичены в ветку, а
        не лежат в рабочем дереве пульта)."""
        self.git.files[f"tasks/{self.TASK}/ANSWER-{n}.md"] = text

    PACKAGE_MARKER = "--- РЕВЬЮ-ПАКЕТ ---"

    def package_text(self) -> str:
        """Только сам ревью-пакет из промпта — БЕЗ миссии и скилов роли.

        Скил ревьювера `review-checklist.md` (состав `roles.yaml:
        reviewer.skills`) сам по себе легитимно содержит слово «ANSWER»
        (пример симметрии `fixed`/`rejected`, «ANSWER-1, вариант B») —
        поиск по ПОЛНОМУ промпту (`self.prompt()`) поймал бы это упоминание
        как ложное срабатывание, не имеющее отношения к содержимому
        ревью-пакета. Тесты этой задачи, которым важно именно содержимое
        пакета (а не всего промпта), обязаны читать через этот метод."""
        prompt = self.prompt()
        idx = prompt.index(self.PACKAGE_MARKER)
        return prompt[idx + len(self.PACKAGE_MARKER):]
