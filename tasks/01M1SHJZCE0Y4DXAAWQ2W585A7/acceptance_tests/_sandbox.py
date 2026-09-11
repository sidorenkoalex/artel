"""Общие фикстуры приёмочных тестов 01M1SHJZCE0Y4DXAAWQ2W585A7 (SPEC:
подзадачи деления заводит пульт из раздела «Деление» SPEC при approve).

Формат секции «## Деление» и её проверка `scripts/guard.py` (AC-1..AC-4,
AC-13, AC-14) — чёрный ящик над `guard.check_content`, тем же приёмом,
что уже применён в `tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/
_sandbox.py` и `tasks/01M1KS8K9RXWHX2PW3ZKB0P903/acceptance_tests/
_sandbox.py`: содержательная проверка не привязана к конкретному имени
внутренней функции guard'а (SPEC требование 1 не называет его буквально
— "сама функция либо её внутренняя реализация, решает разработчик"),
только к наблюдаемому результату `check_content`.

Сквозной сценарий `approve` на `spec_gate` (AC-5..AC-9, AC-11, AC-12) —
`SplitApproveSandbox`, тем же приёмом, что `ZonesApproveSandbox` того же
соседнего файла: `tests.sandbox.RealGitSandbox` (настоящий git-репозиторий
во временном каталоге, все пути `config` подменены), задача заводится
напрямую `store.insert_task`, SPEC.md — плотницким коммитом в
артефактную ветку пульта (`artifact_branch.commit_files`) — единственный
источник, с которого `orchestrator/fsm.py` читает SPEC.md на этой ветке
(`artifact_source.resolve` сегодня всегда `foreign=True`). `fsm.
cmd_advance` доводит `spec_writing -> spec_gate`, `fsm.cmd_approve` —
предмет проверки всех сквозных AC.

Зоны фикстуры (`orchestrator/foo_zone.py`) — вымышленный путь, не
пересекающийся ни с одним реальным модулем и ни с одним элементом
`config.COMMON_ZONES`: тесты общих/непокрытых зон (AC-4/AC-14) отдельно
подставляют настоящий элемент `COMMON_ZONES` и заведомо чужой путь.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from scripts import guard  # noqa: E402
from orchestrator import artifact_branch, config, fsm, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

PARENT_TASK_ID = "01SHJZFIXTUREPARENTTASK1"
PARENT_TITLE = "Родительская фикстура деления"
FIXTURE_ZONE = "orchestrator/foo_zone.py"

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
budget_usd: 15
{zones_line}---

# SPEC: {title}

## Контекст
Фикстура приёмочного теста задачи 01M1SHJZCE0Y4DXAAWQ2W585A7 — короткий
безобидный текст, не связанный с реальной механикой пульта.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры (без сквозной AC-разметки не обязателен —
schema_version 1 не требует её, `guard.requires_ac_markup`).
{division_section}
## Не входит
- Всё остальное.
"""


def division_subsection(title: str, *, zones: str, order: str, tz_text: str,
                        budget: str | None = None) -> str:
    """Текст одного подраздела `### <название>` секции «Деление»
    (требование 1 SPEC): поля `Зоны:`/`Порядок:`, необязательное
    `Рамка:`, затем свободный текст ТЗ."""
    lines = [f"### {title}", "", f"Зоны: {zones}", f"Порядок: {order}"]
    if budget is not None:
        lines.append(f"Рамка: {budget}")
    lines.append("")
    lines.append(tz_text)
    return "\n".join(lines)


def division_section(subsections: list) -> str:
    if not subsections:
        return ""
    body = "\n\n".join(subsections)
    return f"\n## Деление\n{body}\n\n"


def spec_text(*, task: str = PARENT_TASK_ID, title: str = PARENT_TITLE,
             zones: str | None = None, subsections: list | None = None) -> str:
    zones_line = f"zones: {zones}\n" if zones is not None else ""
    return SPEC_TEMPLATE.format(
        task=task, title=title, zones_line=zones_line,
        division_section=division_section(subsections or []))


FIRST_SUBTASK_TITLE = "Первая подзадача деления"
SECOND_SUBTASK_TITLE = "Вторая подзадача деления"
FIRST_SUBTASK_TZ = "Текст ТЗ первой подзадачи сквозной фикстуры деления."
SECOND_SUBTASK_TZ = "Текст ТЗ второй подзадачи сквозной фикстуры деления."


def two_valid_subsections() -> list:
    """Секция «## Деление» из 2 валидных подразделов (обе зоны совпадают
    с frontmatter `zones:` родителя, заданным той же константой
    `FIXTURE_ZONE`) — общая фикстура сквозных сценариев `approve`
    (AC-5..AC-9, AC-11, AC-12): единственное, что у них варьируется, —
    поведение ПОСЛЕ `approve`, не форма самой секции."""
    return [
        division_subsection(
            FIRST_SUBTASK_TITLE, zones=FIXTURE_ZONE,
            order="первая, без зависимостей", tz_text=FIRST_SUBTASK_TZ),
        division_subsection(
            SECOND_SUBTASK_TITLE, zones=FIXTURE_ZONE,
            order="после части 1", tz_text=SECOND_SUBTASK_TZ),
    ]


def check(**kwargs) -> list:
    """`guard.check_content` над `spec_text(**kwargs)` — проверка формата
    секции «Деление» (AC-1..AC-4, AC-13, AC-14), без git и без approve."""
    return guard.check_content("SPEC.md", spec_text(**kwargs))


class SplitApproveSandbox(RealGitSandbox):
    """Песочница `approve` на `spec_gate` с реальным git (AC-5..AC-9,
    AC-11, AC-12) — та же конструкция, что `ZonesApproveSandbox`
    (`tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/_sandbox.py`)."""

    TASK = PARENT_TASK_ID
    TITLE = PARENT_TITLE

    def enter_spec_gate(self, spec_text_value: str) -> str:
        """Заводит родителя, коммитит `spec_text_value` в его артефактную
        ветку, переводит `spec_writing -> spec_gate`. Возвращает
        `fixed_sha`, который `approve` потребует как подтверждение
        (`APPROVE_NEEDS_SHA`, `orchestrator/fsm.py`)."""
        store.insert_task(store.db(), self.TASK, self.TITLE,
                          "spec_writing", f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, 15.0)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": spec_text_value},
            f"{self.TASK}: SPEC готов")
        capture(fsm.cmd_advance, self.TASK)
        return store.get_task(store.db(), self.TASK)["fixed_sha"]

    def approve(self, sha: str | None = None) -> str:
        return capture(fsm.cmd_approve, self.TASK, sha)

    def task_row(self, task_id: str | None = None) -> dict:
        return dict(store.get_task(store.db(), task_id or self.TASK))

    def all_task_ids(self) -> set:
        return {row["id"] for row in store.all_tasks(store.db())}

    def titles_by_id(self, ids) -> dict:
        return {row["id"]: row["title"] for row in store.all_tasks(store.db())
               if row["id"] in ids}

    def journal_text(self, task_id: str | None = None) -> str:
        rows = store.task_steps(store.db(), task_id or self.TASK)
        return "\n".join(f"{r['action']} | {r['detail'] or ''}" for r in rows)
