"""Общие помощники планки задачи 01M3HWXCGHYPMA5BPV7BMBBD9X: приложения
PLAN.md к защищённым путям и текст скилов после их применения.

Предмет задачи — правки двух скилов, которые приезжают в main приложением
PLAN.md (`skills/test-authoring.md`, `skills/review-checklist.md`), а не
коммитом в ветку задачи. Наблюдаемое свойство критериев AC-2…AC-9 —
текст скила ПОСЛЕ применения приложений к базе сравнения ветки задачи,
поэтому планка собирает его одним узлом здесь:

- PLAN.md читается ТОЛЬКО с артефактной ветки задачи (`gitcmd.show` +
  `artifact_branch.branch_name`): на прогоне гейта пульт материализует на
  диск лишь `acceptance_tests/`, PLAN.md на диске рабочей копии нет;
- приложения разбираются штатным разбором пульта
  (`guard.plan_appendices`) — тем же, который читают гейт применимости на
  выходе `in_dev` и цикл мержа;
- база сравнения — единая точка правды пульта `gitcmd.diff_base` ветки
  задачи (merge-base с `refs/remotes/origin/<основная ветка>`);
- приложения применяются подряд, в порядке разбора, тем же вызовом, каким
  их применяет пульт (`plan_appendix.git_apply`), во временном каталоге с
  файлами базы: ни рабочая копия, ни репозиторий не трогаются.

Текстовые помощники (`sections`/`paragraphs`/`sentences`/`has`) сверяют
формулировки скила по стемам слов критерия, а не по дословной фразе:
абзацы скилов переносятся по строкам (и внутри обратных кавычек), поэтому
сравнение идёт по тексту без переводов строк и, для составных имён вроде
`roles.yaml`, по тексту без пробелов вовсе.
"""
import functools
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, gitcmd  # noqa: E402
from orchestrator.advance_gates import plan_appendix  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01M3HWXCGHYPMA5BPV7BMBBD9X"
TEST_AUTHORING = "skills/test-authoring.md"
REVIEW_CHECKLIST = "skills/review-checklist.md"
SKILLS = (TEST_AUTHORING, REVIEW_CHECKLIST)

# Маркер заявки мутации — им опознаётся раздел скила «о заявке мутации»
# (AC-2…AC-4 говорят «раздел о заявке мутации»/«там же», а не «раздел с
# таким-то заголовком»: заголовок разработчик вправе не трогать вовсе).
MUTATION_CLAIM_MARK = "Ловит мутацию"


class State:
    """Слепок приложений PLAN и текстов скилов: `base` — файлы базы
    сравнения, `applied` — они же после применения всех приложений."""

    def __init__(self, plan, plan_reason, branch, base_sha, base, applied,
                 appendix_paths, parse_errors, apply_failures):
        self.plan = plan
        self.plan_reason = plan_reason
        self.branch = branch
        self.base_sha = base_sha
        self.base = base
        self.applied = applied
        self.appendix_paths = appendix_paths
        self.parse_errors = parse_errors
        self.apply_failures = apply_failures

    def diagnosis(self) -> str:
        """Одна строка о состоянии приложений — подставляется в сообщение
        КАЖДОГО отказа планки: без неё «в тексте скила нет такой строки»
        не отличить от «PLAN.md ещё не заведён» и от «приложение не
        применилось»."""
        parts = [f"ветка задачи: {self.branch or '—'}",
                 f"база сравнения: {self.base_sha or '—'}"]
        if self.plan is None:
            parts.append(f"PLAN.md с артефактной ветки не прочитан: "
                         f"{self.plan_reason or '—'}")
        else:
            parts.append(f"приложений разобрано: {len(self.appendix_paths)} "
                         f"{[list(p) for p in self.appendix_paths]}")
        if self.parse_errors:
            parts.append(f"ошибки разбора: {'; '.join(self.parse_errors)}")
        if self.apply_failures:
            parts.append(f"не применились: {'; '.join(self.apply_failures)}")
        return "; ".join(parts)


def _task_branch() -> str:
    """Ветка КОДА задачи. HEAD рабочего каталога прогона — штатный ответ
    (гейт приёмки гоняет планку в worktree задачи); прогон из главной
    копии пульта (ручная сверка, `amend-tests`) стоит на main, и тогда
    ветка берётся по имени из списка веток репозитория — иначе базой
    сравнения оказалась бы голова main, а не точка расхождения ветки."""
    prefix = f"task/{TASK_ID.lower()}-"
    head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                          cwd=REPO_ROOT, capture_output=True, text=True)
    name = head.stdout.strip() if head.returncode == 0 else ""
    if name.startswith(prefix):
        return name
    listed = subprocess.run(
        ["git", "branch", "--list", f"{prefix}*", "--format=%(refname:short)"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    branches = [line.strip() for line in listed.stdout.splitlines()
                if line.strip()] if listed.returncode == 0 else []
    return branches[0] if branches else name


def _apply(appendices, base_sha: str, base: dict) -> tuple[dict, list]:
    """(тексты скилов после применения, отказы применения). Приложения
    ложатся ПОДРЯД на одно дерево — тем же порядком и тем же вызовом, что
    у гейта применимости и цикла мержа: приложение, опирающееся на строку
    предыдущего, иначе отказывало бы ложно."""
    wanted = {rel for paths in (a.paths for a in appendices) for rel in paths}
    wanted |= set(SKILLS)
    tmp = Path(tempfile.mkdtemp(prefix="artel-appendix-base-"))
    failures = []
    try:
        for rel in sorted(wanted):
            text = base[rel] if rel in base else gitcmd.show(base_sha, rel)[0]
            if text is None:
                continue  # приложение заводит новый файл — базы у него нет
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        for appendix in appendices:
            answer = plan_appendix.git_apply(tmp, appendix)
            if answer:
                failures.append(f"{', '.join(appendix.paths)}: {answer}")
        applied = {}
        for rel in SKILLS:
            path = tmp / rel
            applied[rel] = (path.read_text(encoding="utf-8")
                            if path.is_file() else None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return applied, failures


@functools.lru_cache(maxsize=1)
def state() -> State:
    """Слепок приложений PLAN задачи — один раз на процесс прогона: git
    зовётся столько раз, сколько нужно одному слепку, а не на каждый
    тестовый метод планки."""
    plan, plan_reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
    branch = _task_branch()
    base_sha = gitcmd.diff_base(branch) if branch else None
    base = {}
    if base_sha:
        for rel in SKILLS:
            base[rel] = gitcmd.show(base_sha, rel)[0]
    appendices, parse_errors = guard.plan_appendices(plan) if plan else ([], [])
    applied, failures = dict(base), []
    if appendices and base_sha:
        applied, failures = _apply(appendices, base_sha, base)
    return State(plan=plan, plan_reason=plan_reason, branch=branch,
                 base_sha=base_sha or "", base=base, applied=applied,
                 appendix_paths=tuple(tuple(a.paths) for a in appendices),
                 parse_errors=tuple(parse_errors),
                 apply_failures=tuple(failures))


def applied_text(rel: str) -> str:
    """Текст скила `rel` после применения приложений; пустая строка —
    ни базы, ни применения нет (тогда содержательные проверки критерия
    честно падают на пустом тексте, а `diagnosis()` называет причину)."""
    return state().applied.get(rel) or ""


def base_text(rel: str) -> str:
    return state().base.get(rel) or ""


# ------------------------------------------------------------- текст скила

def _flat(text: str) -> str:
    """Текст без переводов строк и повторных пробелов, в нижнем регистре:
    абзац скила перенесён по строкам, и фраза критерия ищется по нему как
    по одной строке."""
    return re.sub(r"\s+", " ", text).lower()


def _tight(text: str) -> str:
    """Текст без пробелов вовсе — для составных имён (`roles.yaml`,
    `tests/`, `ADR-0018`): скилы переносят строку и внутри обратных
    кавычек (живой пример из скила — имя `ls_tree_files`, оторванное
    переносом от `gitcmd.` перед ним)."""
    return re.sub(r"\s+", "", text).lower()


def has(text: str, needle: str) -> bool:
    """Подстрока `needle` есть в тексте — без учёта регистра и переносов
    строк (см. `_flat`/`_tight`)."""
    return needle.lower() in _flat(text) or _tight(needle) in _tight(text)


def missing(text: str, needles) -> list:
    """Те из `needles`, которых в тексте нет — сообщение отказа называет
    ровно недостающее, а не «текст не подошёл»."""
    return [n for n in needles if not has(text, n)]


def sections(text: str) -> list:
    """[(заголовок, тело)] по заголовкам `## …`; преамбула файла — секция
    с пустым заголовком."""
    out, title, body = [], "", []
    for line in text.splitlines():
        if line.startswith("## "):
            out.append((title, "\n".join(body)))
            title, body = line[3:].strip(), []
        else:
            body.append(line)
    out.append((title, "\n".join(body)))
    return out


def sections_with(text: str, needle: str) -> list:
    """Тела секций, несущих `needle` (в заголовке или в теле)."""
    return [body for title, body in sections(text)
            if has(title, needle) or has(body, needle)]


def paragraphs(text: str) -> list:
    """Абзацы — блоки, разделённые пустой строкой."""
    return [p for p in re.split(r"\n[^\S\n]*\n", text) if p.strip()]


def paragraphs_with(text: str, needle: str) -> list:
    return [p for p in paragraphs(text) if has(p, needle)]


def sentences(text: str) -> list:
    """Предложения — по точке/воскл./вопр. знаку с последующим пробелом.
    Грубо, но достаточно: проверяется соседство слов в одной фразе, а не
    грамматика."""
    return [s for s in re.split(r"(?<=[.!?])\s", text) if s.strip()]


def sentences_with(text: str, needle: str) -> list:
    return [s for s in sentences(text) if has(s, needle)]


def mutation_claim_text(text: str) -> str:
    """Текст разделов скила «о заявке мутации» — тех, что называют маркер
    `Ловит мутацию`. Именно так критерии AC-2…AC-4 адресуют место правки
    («раздел о заявке мутации», «там же»), не заголовком."""
    return "\n\n".join(sections_with(text, MUTATION_CLAIM_MARK))


NEGATIONS = ("нет", "не ", "отсутств", "недоступ")


def has_negation(text: str) -> bool:
    """В тексте есть отрицание — им критерии выражают условие «когда
    мутации с наблюдаемым расхождением НЕТ», «локальная ветка — только
    когда origin НЕДОСТУПЕН»."""
    return any(has(text, n) for n in NEGATIONS)
