"""Общая песочница приёмочных тестов задачи 01M1GV6H5DDDCWW4G3GW1D3A1X
(«Границы недоверенных данных в брифах ролей»).

Не сканируется guard'ом на AC-маркеры/тест-методы (только test_*.py,
SPEC T081) — файлы test_ac*.py этого каталога делят с ним фикстуры.

Реализация маркеров границ ещё не существует (эта задача её вводит) —
поэтому тесты не могут знать заранее точный текстовый формат маркера
(какой символ-разделитель, каким словом называется «открывающий»/
«закрывающий» и т.п.). Вместо этого `marker_id_for`/`marker_span` ищут
маркер СТРУКТУРНО: непредсказуемый идентификатор — это токен вида
[A-Za-z0-9_-]{8,} (покрывает hex/uuid4/token_hex/token_urlsafe —
разумный диапазон форматов), который встречается И непосредственно
ПЕРЕД, И непосредственно ПОСЛЕ тела компонента в тексте. Такой подход
не подсказывает реализации конкретный синтаксис маркера — тест ловит
сам факт парной обвязки с общим идентификатором, а не конкретные слова.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import brief, config, context_package, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402

TASK = "T001"
BRANCH = "task/t001-granitsy-nedoveryonnykh-dannykh"

MAP_FRESH = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
            "---\n\n# Карта\n")
SPEC_SMALL = "# SPEC\n\nМаркер-текста-SPEC.\n"
CONVENTIONS_SMALL = "# Конвенции проекта\n\nМаркер-текста-CLAUDE.\n"

TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{8,}")


def _candidate_tokens(s: str) -> set:
    return set(TOKEN_RE.findall(s))


def marker_id_for(text: str, content: str, window: int = 500) -> str:
    """Непредсказуемый идентификатор границы, обёрнутой вокруг `content`
    внутри `text`: единственный токен-кандидат, общий для окна СРАЗУ
    ПЕРЕД и окна СРАЗУ ПОСЛЕ вхождения `content`.

    Кандидатов не один — тест сам объясняет причину провала (граница не
    опознана, а не абстрактный `KeyError`/`IndexError`)."""
    idx = text.find(content)
    if idx < 0:
        raise AssertionError(
            f"содержимое компонента не найдено в тексте целиком: "
            f"{content[:80]!r}")
    end = idx + len(content)
    before = text[max(0, idx - window):idx]
    after = text[end:end + window]
    candidates = _candidate_tokens(before) & _candidate_tokens(after)
    if len(candidates) != 1:
        raise AssertionError(
            "не найден ровно один общий идентификатор границы вокруг "
            f"компонента {content[:40]!r} (кандидаты: {candidates!r}) — "
            "открывающий и закрывающий маркеры обязаны нести общий "
            "непредсказуемый токен вплотную к телу компонента")
    return candidates.pop()


def marker_span(text: str, content: str, token: str,
                window: int = 500) -> tuple:
    """(индекс вхождения `token` до `content`, индекс вхождения `token`
    после `content`) — позиции открывающего и закрывающего маркера."""
    idx = text.find(content)
    if idx < 0:
        raise AssertionError(f"содержимое не найдено: {content[:80]!r}")
    end = idx + len(content)
    before = text[max(0, idx - window):idx]
    after = text[end:end + window]
    open_pos = before.rfind(token)
    close_pos = after.find(token)
    if open_pos == -1 or close_pos == -1:
        raise AssertionError(
            f"токен {token!r} не найден по обе стороны компонента "
            f"{content[:40]!r}")
    return max(0, idx - window) + open_pos, end + close_pos


class BriefSandbox(TmpRootTest):
    """docs/codebase-map.md + CLAUDE.md + tasks/<TASK>/SPEC.md на диске —
    тот же минимум, что tests/test_brief.py::BriefUnitTest."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            MAP_FRESH, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            CONVENTIONS_SMALL, encoding="utf-8")
        (config.TASKS / TASK).mkdir(parents=True)
        (config.TASKS / TASK / "SPEC.md").write_text(
            SPEC_SMALL, encoding="utf-8")
        store.create_schema(store.db())
        self.conn = store.db()

    def write_spec(self, text: str) -> None:
        (config.TASKS / TASK / "SPEC.md").write_text(text, encoding="utf-8")

    def write_conventions(self, text: str) -> None:
        (self.root / "CLAUDE.md").write_text(text, encoding="utf-8")

    def write_answer(self, n: int, marker_text: str) -> None:
        # Фикстура НЕ несёт полный набор полей реального frontmatter
        # (`author_role`/`schema_version`) намеренно: это — 8+-символьные
        # ASCII-токены, буквально повторяющиеся между СОСЕДНИМИ
        # компонентами (ANSWER рядом с QUESTIONS, SPEC рядом с PLAN) —
        # `marker_id_for` находил бы их как ложного «общего кандидата»
        # независимо от реального маркера границы, которого сегодня нет.
        # Для проверяемого здесь поведения (обвязка маркерами) состав
        # frontmatter не важен — важно только, что тело `marker_text`
        # доходит до брифа как есть.
        (config.TASKS / TASK / f"ANSWER-{n}.md").write_text(
            "---\ntask: " + TASK + "\ntype: answer\nstatus: ready\n---\n\n"
            f"# ANSWER-{n}: ответ Оператора\n\n## Ответы\n\n{marker_text}\n",
            encoding="utf-8")

    def write_questions(self, marker_text: str) -> None:
        (config.TASKS / TASK / "QUESTIONS.md").write_text(
            "---\ntask: " + TASK + "\ntype: questions\nstatus: draft\n---\n\n"
            f"# QUESTIONS\n\n## Вопросы\n\n1. **Вопрос?** — {marker_text} "
            "— дефолт: A.\n",
            encoding="utf-8")

    def build_developer_brief(self, git=fake_git) -> str:
        with mock.patch.object(gitcmd, "git", git):
            return brief.developer_brief(self.conn, TASK)

    def build_analyst_brief(self, git=fake_git) -> str:
        with mock.patch.object(gitcmd, "git", git):
            return brief.analyst_map_component(self.conn, TASK)

    def build_test_author_brief(self, git=fake_git):
        with mock.patch.object(gitcmd, "git", git):
            return brief.test_author_answer_component(self.conn, TASK)

    def journal_details(self, actor: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE actor=? ORDER BY id", (actor,))]


# --------------------------------------------------------------- review.py
#
# Frontmatter фикстур ниже намеренно НЕ полный (нет `author_role`): это
# 8+-символьный ASCII-токен, буквально повторяющийся между СОСЕДНИМИ
# компонентами пакета (SPEC/PLAN/прошлый REVIEW/форма) — `marker_id_for`
# находил бы его как ложного «общего кандидата» вместо/вместе с
# реальным маркером границы. `review.review_package` не разбирает
# frontmatter, так что для проверяемого здесь поведения состав полей
# не важен.

SPEC_MD = """---
task: {task}
type: spec
status: approved
---

# SPEC: границы недоверенных данных

## Требования
1. Маркер-тела-SPEC-ревью-пакета.
"""

PLAN_MD = """---
task: {task}
type: plan
status: ready
---

# PLAN: границы недоверенных данных

## Подход
Маркер-тела-PLAN-ревью-пакета.
"""

REVIEW_MD = """---
task: {task}
type: review
status: changes_requested
iteration: 1
---

# REVIEW: границы недоверенных данных

## Замечания
major — Маркер-тела-прошлого-REVIEW.
"""

FORM_MD = """---
task: T000
type: review
status: draft
---

# REVIEW: <заголовок>

## Замечания
"""


def standard_files(task: str = TASK, with_prev_review: bool = False) -> dict:
    files = {
        f"tasks/{task}/SPEC.md": SPEC_MD.format(task=task),
        f"tasks/{task}/PLAN.md": PLAN_MD.format(task=task),
        "templates/REVIEW.md": FORM_MD,
    }
    if with_prev_review:
        files[f"tasks/{task}/REVIEW.md"] = REVIEW_MD.format(task=task)
    return files


class FakeGitDiff:
    """Заглушка `gitcmd.git` для `review.review_package`: `show` — по
    словарю `files`, `diff`/`diff --stat` — по заготовленным строкам,
    остальное — «чисто» (rc=0, пусто)."""

    def __init__(self, files=None, diff="diff --git a b\n+тело-диффа",
                stat="a.py | 1 +"):
        self.files = dict(files or {})
        self.diff = diff
        self.stat = stat
        self.calls = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        if args and args[0] == "show":
            _, rel = args[1].split(":", 1)
            if rel not in self.files:
                return subprocess.CompletedProcess(
                    list(args), 128, "",
                    f"fatal: path '{rel}' does not exist")
            return subprocess.CompletedProcess(list(args), 0, self.files[rel], "")
        if args and args[0] == "rev-parse" and "--verify" in args:
            return subprocess.CompletedProcess(list(args), 1, "", "")
        if args and args[0] == "diff" and "--stat" in args:
            return subprocess.CompletedProcess(list(args), 0, self.stat, "")
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(list(args), 0, self.diff, "")
        return subprocess.CompletedProcess(list(args), 0, "", "")


def build_review_package(git, task: str = TASK, branch: str = BRANCH,
                         title: str = "Границы недоверенных данных",
                         **kw) -> dict:
    """`review.review_package` под фейковым git — `config.ROOT` подменён на
    пустой временный каталог на время вызова (без этого неудавшийся `git
    show` откатывается на чтение НАСТОЯЩЕГО дерева пульта — см. тот же
    приём в tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests/_sandbox.py)."""
    from orchestrator import review
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(gitcmd, "git", git), \
                mock.patch.object(config, "ROOT", Path(tmp)):
            return review.review_package(task, title, branch, **kw)
