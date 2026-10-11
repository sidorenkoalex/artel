"""Общие разборщики для приёмочных тестов T093 (не `test_*.py` — не
подхватывается `unittest discover` напрямую, только импортом из
test_ac*.py; тот же приём, что `tasks/T085/acceptance_tests/_sandbox.py`
и `tasks/T043/acceptance_tests/retro_sandbox.py`).

SPEC.md (tasks/T093/SPEC.md) не фиксирует дословный формат перечня
«уроков» — требование 3 отдаёт выбор файла и формулировки разработчику.
Парсер здесь принимает ЛЮБОЙ markdown-заголовок `#`..`######`,
содержащий слово «урок» или «дистилл» (без учёта регистра — сами эти
слова SPEC использует для явления: требования 2, 3 AC-1, заголовок и
название задачи), и читает из-под него пункты списка (`- `, `* `,
`1. `) как отдельные «уроки» — иначе тест не отличил бы явный перечень
уроков от произвольных абзацев PLAN.md («Шаги», «Риски» и т.п.).

Отдельно требование 7б называет ДРУГОЙ раздел — сводный реестр вычистки
копилки «дистиллировано → куда» (адреса исходных записей и поглотивших
их правок, не сами уроки). Слово «дистилл» встречается в его заголовке
тоже, поэтому заголовки, где рядом с «урок»/«дистилл» встречается «куда»
или сама стрелка «→» (буквальные слова формата реестра требования 7б),
разделом с уроками не считаются — иначе пункты адресного реестра
ошибочно read'ались бы как уроки без ссылок на фактуру.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

TASK_DIR = REPO_ROOT / "tasks" / "T093"

# Дословно SPEC T093, требование 6.
REQ6_FILES = frozenset({
    "skills/test-authoring.md",
    "skills/spec-authoring.md",
    "skills/review-checklist.md",
    "skills/coding-standards.md",
    "skills/conventions-core.md",
    "skills/escalation-rules.md",
    "templates/ANSWER.md",
    "templates/PLAN.md",
    "templates/QUESTIONS.md",
    "templates/REVIEW.md",
    "templates/SPEC.md",
    "templates/TEST_REPORT.md",
})

T_REF_RE = re.compile(r"\bT\d{2,4}\b")
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$", re.MULTILINE)
_BULLET_START_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\S")
LESSON_HEADING_KEYWORDS = ("урок", "дистилл")
# Заголовки адресного реестра требования 7б («дистиллировано → куда») —
# не перечень уроков, см. докстринг модуля.
_REGISTRY_HEADING_MARKERS = ("куда", "→")


# Артефакты, которые в момент прогона test_author уже лежат в
# tasks/T093/ и НЕ являются ни PLAN.md, ни «отдельным реестром»
# разработчика (AC-1): SPEC.md — вход аналитика, TZ.md — вход
# Оператора. Оба нужны как контекст задачи, но их собственный текст
# (в частности заголовки TZ.md, где буквально встречается слово
# «дистилляция» в названии задачи) не должен читаться как перечень
# выделенных уроков — иначе тест путает бриф Оператора с продуктом
# работы разработчика.
_NON_ARTIFACT_NAMES = frozenset({"SPEC.md", "TZ.md"})


def artifact_files():
    """.md-файлы прямо в tasks/T093/ (не в acceptance_tests/), кроме
    SPEC.md/TZ.md — PLAN.md и/или отдельный реестр, который AC-1
    разрешает как альтернативу."""
    if not TASK_DIR.exists():
        return []
    return sorted(p for p in TASK_DIR.glob("*.md")
                 if p.is_file() and p.name not in _NON_ARTIFACT_NAMES)


def _lesson_sections(text):
    headings = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        title = m.group(2).lower()
        if not any(kw in title for kw in LESSON_HEADING_KEYWORDS):
            continue
        if any(kw in title for kw in _REGISTRY_HEADING_MARKERS):
            continue
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        yield text[start:end]


def _items_from_section(section_text):
    items = []
    current: list[str] = []
    for line in section_text.splitlines():
        if _BULLET_START_RE.match(line):
            if current:
                items.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        items.append("\n".join(current))
    return items


def lesson_items():
    """[(путь_файла, текст_пункта), ...] по всем разделам-кандидатам
    «уроки»/«дистилляция» (кроме адресного реестра требования 7б) во
    всех .md файлах tasks/T093/."""
    found = []
    for path in artifact_files():
        text = path.read_text(encoding="utf-8")
        for section in _lesson_sections(text):
            for item in _items_from_section(section):
                found.append((path, item))
    return found


def refs_in(item_text):
    return set(T_REF_RE.findall(item_text))


def is_corpus_task(t_num):
    """t_num вроде 'T064' реально участвует в корпусе дистилляции
    требования 1 SPEC (секции «Предложения системе» PLAN.md/REVIEW.md,
    docs/retro/, ANSWER-файлы задачи t_num) — не просто упомянут где-то
    в тексте. Находки docs/audits/ требование 1 явно исключает как
    самостоятельный источник, поэтому здесь не проверяются."""
    if (REPO_ROOT / "docs" / "retro" / f"{t_num}.md").exists():
        return True
    task_dir = REPO_ROOT / "tasks" / t_num
    if task_dir.is_dir() and any(task_dir.glob("ANSWER-*.md")):
        return True
    for fname in ("PLAN.md", "REVIEW.md"):
        p = task_dir / fname
        if p.exists():
            body = guard.section_body(p.read_text(encoding="utf-8"),
                                      "Предложения системе")
            if any(line.strip().startswith(("-", "*"))
                  for line in body.splitlines()):
                return True
    return False
