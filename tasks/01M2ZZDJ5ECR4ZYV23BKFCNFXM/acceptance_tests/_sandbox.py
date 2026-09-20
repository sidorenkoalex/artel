"""Общая надстройка песочницы планки 01M2ZZDJ5ECR4ZYV23BKFCNFXM.

Не копия `tests/sandbox.py`, а тонкая надстройка сценария поверх
`tests.sandbox.RealGitSandbox` (skills/test-authoring.md: «локальный
`_sandbox.py` планки — только тонкая надстройка сценария», ни одного
собственного `disk_backed_*`/`advance_from_in_dev` здесь нет): предмет
критериев этой задачи — поведение сборщика ревью-пакета относительно
НАСТОЯЩЕГО git-репозитория (артефактная ветка задачи, кодовая ветка,
merge-коммит подтяжки main, sha фиксации вердикта), заглушкой `gitcmd.git`
этого не изобразить.

Настоящий репозиторий пульта песочница не трогает: `RealGitSandbox`
подменяет все пути `config` временным каталогом и заводит в нём свой
`git init` (AC-11, вторая половина).
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (artifact_branch, config, review,  # noqa: E402
                          runner, store)
from tests.sandbox import RealGitSandbox  # noqa: E402

# Синтетический id задачи песочницы — не id самой задачи планки: всё, что
# читает пакет, живёт в веточном/дисковом фикстурном дереве временного
# каталога, а не в артефактах настоящей задачи.
TASK = "01MPLANKREVIEWPACKAGE0001"
BRANCH = f"task/{TASK.lower()}-revyu-paket"
TITLE = "Ревью-пакет: артефакты и инкремент"

# Тела артефактов — с уникальными маркерами: по ним тест видит, ПОПАЛО ли
# тело в пакет, независимо от оформления заголовка части.
SPEC_BODY = "МАРКЕР-ТЕЛА-SPEC"
PLAN_BODY = "МАРКЕР-ТЕЛА-PLAN"
REVIEW_BODY = "МАРКЕР-ТЕЛА-REVIEW"
FORM_BODY = "МАРКЕР-ТЕЛА-ФОРМЫ-ВЕРДИКТА"

SPEC_TEXT = f"---\ntask: {TASK}\ntype: spec\n---\n\n# SPEC\n\n{SPEC_BODY}\n"
PLAN_TEXT = f"---\ntask: {TASK}\ntype: plan\n---\n\n# PLAN\n\n{PLAN_BODY}\n"
REVIEW_TEXT = (f"---\ntask: {TASK}\ntype: review\niteration: 1\n---\n\n"
               f"# REVIEW\n\n{REVIEW_BODY}\n")
FORM_TEXT = f"---\ntask: T000\ntype: review\n---\n\n# REVIEW\n\n{FORM_BODY}\n"

ARTIFACT_NAMES = ("SPEC.md", "PLAN.md", "REVIEW.md")
ARTIFACT_TEXTS = {"SPEC.md": SPEC_TEXT, "PLAN.md": PLAN_TEXT,
                  "REVIEW.md": REVIEW_TEXT}

FIXATION_ACTION = "sha зафиксирован"
PACKAGE_ACTION = "ревью-пакет собран"
# Дословная формулировка detail якоря вердикта — её пишет переход
# `review -> in_dev` по вердикту changes_requested (AC-5).
VERDICT_DETAIL_TMPL = "замечания ревью, итерация {n}"

# Дословная причина отката требования 7/AC-8.
FALLBACK_REASON = ("инкрементальный diff пуст при непустых правках — "
                   "показан полный")

# Пути кода, которыми песочница изображает правку разработчика (A) и
# изменение, пришедшее подтяжкой main (B) — AC-7/AC-8.
DEV_FILE = "orchestrator/alpha.py"
MAIN_FILE = "orchestrator/beta.py"
DEV_MARK = "МАРКЕР-ПРАВКИ-РАЗРАБОТЧИКА"
MAIN_MARK = "МАРКЕР-ПОДТЯЖКИ-MAIN"


class ReviewPackagePlankSandbox(RealGitSandbox):
    """Репозиторий с кодовой веткой задачи, её артефактной веткой и
    рабочим каталогом шага (`config.WORKTREES/<id>`); задача заведена в БД
    песочницы в состоянии `review`."""

    TASK = TASK
    BRANCH = BRANCH

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.artifact_branch = artifact_branch.branch_name(self.TASK)
        # Шаблон вердикта живёт в main и, значит, в кодовой ветке задачи —
        # источник части «форма вердикта» этой задачей не меняется (AC-4).
        self.commit_files(config.MAIN_BRANCH, {"templates/REVIEW.md": FORM_TEXT},
                          "шаблон вердикта")
        self.git("branch", self.BRANCH, config.MAIN_BRANCH)
        self.git("branch", self.artifact_branch, config.MAIN_BRANCH)
        store.insert_task(self.conn, self.TASK, TITLE, "review", self.BRANCH,
                          config.DEFAULT_TARGET, 35.0)

    # --- фикстуры источников артефактов -------------------------------

    def commit_files(self, branch: str, files: dict, message: str) -> str:
        """Коммит `files` (путь относительно корня репозитория → текст) в
        `branch`; возвращает sha коммита, дерево возвращает на main."""
        self.git("checkout", "-q", branch)
        for rel, text in files.items():
            path = self.root.joinpath(*rel.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "--", *files)
        self.git("commit", "-q", "-m", message)
        sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", config.MAIN_BRANCH)
        return sha

    def task_rel(self, name: str) -> str:
        return f"tasks/{self.TASK}/{name}"

    def put_in_artifact_branch(self, names=ARTIFACT_NAMES) -> str:
        """Артефакты задачи — в её артефактную ветку (штатный источник)."""
        return self.commit_files(
            self.artifact_branch,
            {self.task_rel(n): ARTIFACT_TEXTS[n] for n in names},
            "артефакты задачи")

    def put_in_code_branch(self, names=ARTIFACT_NAMES) -> str:
        """Артефакты — в КОДОВУЮ ветку задачи (источник, которым они быть
        перестают, требование 1)."""
        return self.commit_files(
            self.BRANCH,
            {self.task_rel(n): ARTIFACT_TEXTS[n] for n in names},
            "артефакты в кодовой ветке")

    def drop_from_artifact_branch(self, names=ARTIFACT_NAMES) -> str:
        """Убирает артефакты из артефактной ветки отдельным коммитом — та
        же фикстура, что «в ветке их нет», но поверх уже собранного из
        ветки пакета (сравнение заголовков двух источников, AC-2)."""
        self.git("checkout", "-q", self.artifact_branch)
        self.git("rm", "-q", "--", *[self.task_rel(n) for n in names])
        self.git("commit", "-q", "-m", "артефакты убраны из ветки")
        sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", config.MAIN_BRANCH)
        return sha

    def put_in_step_workdir(self, names=ARTIFACT_NAMES) -> Path:
        """Артефакты — в каталог `tasks/<id>/` РАБОЧЕГО КАТАЛОГА ШАГА
        (worktree задачи для self-target)."""
        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        for name in names:
            tdir.joinpath(name).write_text(ARTIFACT_TEXTS[name],
                                           encoding="utf-8")
        return tdir

    def put_in_pult_copy(self, names=ARTIFACT_NAMES) -> Path:
        """Артефакты — в ГЛАВНУЮ копию пульта (`config.TASKS`), источником
        которой они быть перестают (требование 1)."""
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        for name in names:
            tdir.joinpath(name).write_text(ARTIFACT_TEXTS[name],
                                           encoding="utf-8")
        return tdir

    # --- фикстуры журнала ---------------------------------------------

    def journal_transition(self, state: str, detail: str = "") -> None:
        store.journal(self.conn, self.TASK, "fsm", f"state -> {state}", detail)

    def journal_fixation(self, code_sha: str) -> None:
        store.journal(
            self.conn, self.TASK, "fsm", FIXATION_ACTION,
            f"target={config.DEFAULT_TARGET}, sha=deadbeef, чисто=True, "
            f"код={code_sha}")

    def journal_verdict_anchor(self, code_sha: str, iteration: int = 1) -> None:
        """Якорь вердикта: переход `state -> in_dev` с detail «замечания
        ревью, итерация N» и НЕПОСРЕДСТВЕННО следующая за ним запись
        фиксации с `код=<sha>`."""
        self.journal_transition(
            "in_dev", VERDICT_DETAIL_TMPL.format(n=iteration))
        self.journal_fixation(code_sha)

    def journal_noise_fixations(self, *code_shas: str) -> None:
        """Лишние записи «sha зафиксирован» между вердиктом и входом в
        review: автокоммит артефактов, чекпоинт, подтяжка main (AC-5)."""
        for sha in code_shas:
            self.journal_fixation(sha)

    def journal_details(self, action: str) -> list:
        return [row["detail"] for row in store.task_steps(self.conn, self.TASK)
                if row["action"] == action]

    # --- фикстуры кодовой ветки ---------------------------------------

    def head(self, branch: str) -> str:
        return self.git("rev-parse", branch).strip()

    def developer_commit(self, text: str) -> str:
        """Собственный коммит ветки задачи — правка разработчика (файл A)."""
        return self.commit_files(self.BRANCH, {DEV_FILE: text},
                                 "правка разработчика")

    def main_pull_merge(self, text: str) -> str:
        """Коммит в main (файл B) и подтяжка main в ветку задачи
        merge-коммитом; возвращает sha merge-коммита."""
        self.commit_files(config.MAIN_BRANCH, {MAIN_FILE: text},
                          "чужая правка в main")
        self.git("checkout", "-q", self.BRANCH)
        self.git("merge", "-q", "--no-ff", "-m", "подтяжка main",
                 config.MAIN_BRANCH)
        sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", config.MAIN_BRANCH)
        return sha

    # --- вызовы предмета проверки -------------------------------------

    def package(self, iteration: int = 1, prev_sha: str = "") -> dict:
        return review.review_package(self.conn, self.TASK, TITLE, self.BRANCH,
                                     iteration=iteration, prev_sha=prev_sha)

    def build_prompt(self, reviewed_iter: int = 0) -> str:
        """Полный шаг сборки промпта ревьювера (`runner._build_prompt`) —
        не только функция пакета: запись журнала «ревью-пакет собран» и
        алерт заводятся именно здесь (AC-8/AC-9/AC-10)."""
        store.update_task(self.conn, self.TASK, reviewed_iter=reviewed_iter)
        task = store.get_task(self.conn, self.TASK)
        with redirect_stdout(io.StringIO()):
            return runner._build_prompt(self.conn, self.TASK, task, "review",
                                        config.DEFAULT_TARGET, "")


def part_header(text: str, label: str) -> str:
    """Строка заголовка `### …` той части пакета, которая называет `label`;
    пустая строка — такой части в пакете нет."""
    for line in text.splitlines():
        if line.startswith("### ") and label in line:
            return line
    return ""


def after_diff(text: str) -> str:
    """Хвост пакета начиная с заголовка части diff — там же живёт заметка
    под diff'ом (требования 6-8)."""
    marker = "### Diff"
    return text[text.index(marker):] if marker in text else ""


def part_body(text: str, label: str) -> str:
    """Текст части пакета от её заголовка до следующего заголовка `### `."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("### ") and label in line:
            rest = lines[i + 1:]
            for j, nxt in enumerate(rest):
                if nxt.startswith("### "):
                    return "\n".join(rest[:j])
            return "\n".join(rest)
    return ""
