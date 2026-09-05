"""Общие фикстуры приёмочных тестов 01M1R66X5SMD3ZEDCVAJ0DR7K2 (SPEC:
guard на артефактных ветках — черновики не красят CI, сданные артефакты
проверяются строго).

Выбор интерфейса теста (обязателен для написания тестов ДО PLAN.md
разработчика — конвейер ролей ставит test_author раньше developer,
skills/test-authoring.md: «разработчик увидит задачу только после
тебя»). Требование 1 SPEC явно отдаёт выбор МЕХАНИЗМА включения режима
разработчику («параметр функции и/или CLI-флаг/переменная окружения —
решает разработчик на этапе PLAN»), но AC-9 буквально перечисляет
сценарии, которые приёмочная планка обязана закодировать уже сейчас —
кто-то должен назвать конкретный внешний контракт первым, и в этом
конвейере (лок acceptance_tests/ ставится раньше кода разработчика)
это МЕХАНИЧЕСКИ test_author — тем же приёмом, каким тесты
01M1NKVPD2A79PQ6K0JVV1B2Q1 зафиксировали представление значения поля
`zones` раньше PLAN разработчика (см. докстринг `spec_text` там же).

Решение — тестировать ТОЛЬКО НАБЛЮДАЕМУЮ поверхность `guard.py`
(CLI-вызов `main()` и функцию `orchestrator/fsm.py::guard_refuses`,
уже существующую сегодня), а не гадать о внутренней архитектуре
(остаётся ли `check_content` без нового параметра или обзаводится
им — оба пути разработчика равно закрывают требование 1's «и/или»).
Единственное, что тесты ниже ФИКСИРУЮТ как контракт — способ ВКЛЮЧИТЬ
режим с командной строки:

    python3 scripts/guard.py --all --artifact-branch

CLI-флаг `--artifact-branch`, сосуществующий с `--all` в одном вызове
(порядок — буквально пример требования 4 SPEC: «guard.py --all с новым
флагом»). Выбран флаг, а не переменная окружения: обе опции равноправны
по SPEC, но флаг читается яснее в `run:`-шаге `ci.yml` (требование 6) и
не оставляет скрытого состояния окружения между шагами джоба CI.

Это решение — контракт ЭТОЙ планки, не требование самого SPEC:
разработчик, реализующий переключение переменной окружения вместо
флага (SPEC такое явно разрешает), обязан либо подстроить свой код под
уже зафиксированный тестами флаг `--artifact-branch` (например, приняв
оба входа), либо вынести несогласие в PLAN.md как предмет ревью —
тем же путём, каким любое другое расхождение с локом снимается
(skills/test-authoring.md, «Лок»: «код будут чинить под тест, не
наоборот»).

Внутренняя логика классификации (черновик/сдан, ошибка/предупреждение)
проверяется здесь ЧЕРЕЗ ДВЕ независимые точки, ни одна из которых не
требует знания внутреннего API `check_content`:

1. `run_main(files, artifact_branch=...)` — прогоняет реальный
   `guard.main()` над временным деревом `tasks/`, `sys.argv`
   подменяется на `["scripts/guard.py", "--all"]` (+ `--artifact-branch`
   при необходимости), вывод и код возврата перехватываются — тот же
   приём вызова CLI-команды напрямую, что `tests/test_version.py::
   VersionCommandTest.run_version` (без реального `subprocess`).
2. `fsm.guard_refuses(conn, task_id, path, text=...)` — РЕАЛЬНАЯ функция,
   которую сегодня зовут все переходы `orchestrator/fsm.py` (AC-1: «в
   т.ч. всё, что сегодня зовёт guard.check/guard.check_content из
   orchestrator/fsm.py»); вызов без нового аргумента дословно
   «эмуляция перехода advance» из AC-9 — тем же путём, каким сама
   функция вызывается на переходе `spec_writing -> spec_gate`
   (`orchestrator/fsm_advance.py::spec_writing`), без остальной
   тяжёлой машинерии `cmd_advance` (git/worktree), которая для проверки
   ИМЕННО guard-отказа не нужна: `text` передан явно, до диска/git
   `guard_refuses` не достаёт.
"""
import io
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import catalog, config, fsm, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

# Флаг CLI, зафиксированный этой планкой (см. докстринг модуля выше).
ARTIFACT_BRANCH_FLAG = "--artifact-branch"

FIXTURE_TASK_ID = "01M1R66X5SMD3ZEDCVAJ0DR7K2-FIXTURE"


# --------------------------------------------------------------------------
# guard.main() через реальный CLI-вход, без subprocess (см. п.1 докстринга).

def run_main(files: dict, *, artifact_branch: bool = False) -> tuple:
    """Прогоняет `guard.main()` над деревом `files` (rel_path -> текст),
    материализованным во временном каталоге, с `sys.argv` вида
    `["scripts/guard.py", "--all"]` (+ `ARTIFACT_BRANCH_FLAG`, если
    `artifact_branch=True`). Возвращает `(exit_code, stdout)`.

    `--all` — единственный режим CLI, который SPEC (требование 4, AC-5)
    называет буквально в связке с новым флагом; явный список файлов в
    сочетании с флагом ACs не описывают и здесь не тестируется.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        argv = ["scripts/guard.py", "--all"]
        if artifact_branch:
            argv.append(ARTIFACT_BRANCH_FLAG)

        prior_cwd = Path.cwd()
        try:
            os.chdir(root)
            with mock.patch.object(sys, "argv", argv):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = guard.main()
        finally:
            os.chdir(prior_cwd)
        return code, buf.getvalue()


SUMMARY_LINE = re.compile(
    r"^сдано (\d+) / черновиков (\d+) / нарушений (\d+)$")


def parse_summary(stdout: str):
    """`(сдано, черновиков, нарушений)` из ПЕРВОЙ строки stdout (требование
    5) — `None`, если первая строка не совпадает с форматом буквально."""
    first_line = stdout.splitlines()[0] if stdout else ""
    match = SUMMARY_LINE.fullmatch(first_line)
    return tuple(int(g) for g in match.groups()) if match else None


# --------------------------------------------------------------------------
# fsm.guard_refuses() — реальная точка вызова guard на переходах (см. п.2
# докстринга); песочница даёт только БД, без git/worktree.

class GuardRefusesSandbox(TmpRootTest):
    """`fsm.guard_refuses(conn, task_id, path, text=...)` c минимальной
    задачей в БД. `path` не читается с диска (`text` передан явно), поэтому
    ни git, ни worktree/`fake_git` этой песочнице не нужны — только
    `TmpRootTest` (пути `config` во временном каталоге, схема БД ставится
    `cmd_init`)."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.TASK = "01GUARDARTIFACTBRANCHFX"
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "guard artifact-branch fixture",
                          "spec_writing", f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, 15.0)

    def guard_refuses(self, text: str, name: str = "SPEC.md") -> bool:
        path = config.TASKS / self.TASK / name
        return fsm.guard_refuses(self.conn, self.TASK, path, text=text)


# --------------------------------------------------------------------------
# Тексты фикстур: SPEC (draft/ready, с/без zones), и generic-шаблоны
# четырёх типов требования 2 (spec/plan/review/test_report) для проверки
# «черновик/сдан» независимо от конкретного содержательного правила.
#
# schema_version: 1 в generic-шаблонах — намеренно: требование 2 не
# гейтит черновик/сдан-различение версией схемы (в отличие от AC-разметки/
# zones/реестра, каждое из которых version-gated отдельно) — фикстуры
# ниже проверяют РАЗЛИЧЕНИЕ ПО STATUS в чистом виде, не смешивая его с
# version-gating других правил. Дело zones-специфичных сценариев (AC-9)
# несёт свой отдельный, версии-4 шаблон SPEC ниже.

SPEC_ZONES_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: {status}
schema_version: 4
{zones_line}---

# SPEC: фикстура zones {task}

## Контекст
Фикстура приёмочного теста 01M1R66X5SMD3ZEDCVAJ0DR7K2.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры.

## Не входит
- Всё остальное.
"""


def spec_zones_text(*, status: str, zones: str | None = "tests/") -> str:
    """SPEC schema_version 4 — с `zones` (по умолчанию) либо без него
    (`zones=None`). `status` — любое валидное значение для `spec`."""
    zones_line = f"zones: {zones}\n" if zones is not None else ""
    return SPEC_ZONES_TEMPLATE.format(task=FIXTURE_TASK_ID, status=status,
                                      zones_line=zones_line)


ANSWER_MISSING_SECTION = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 1
---

# ANSWER: фикстура {task}

Текст без секции «Ответы».
"""


def answer_missing_section_text() -> str:
    return ANSWER_MISSING_SECTION.format(task=FIXTURE_TASK_ID)


# Четыре типа требования 2 — шаблон и валидный ("сдан") статус, отличный
# от draft, для каждого (см. `RULES` в `scripts/guard.py`: пересечение
# статусов трёх типов даёт именно набор требования 2 — не отдельная
# константа этого файла, а проверяемое числом совпадение).
GENERIC_TEMPLATES = {
    "spec": """---
task: {task}
type: spec
author_role: analyst
status: {status}
schema_version: 1
---

# SPEC: generic-фикстура {task}

## Контекст
Фикстура.

## Требования
1. Требование.

## Критерии приёмки
1. Критерий.

## Не входит
- Остальное.
""",
    "plan": """---
task: {task}
type: plan
author_role: developer
status: {status}
schema_version: 1
---

# PLAN: generic-фикстура {task}

## Подход
Фикстура.

## Шаги
1. Шаг.

## Покрытие требований
Фикстура.

## Влияние на систему
Фикстура.
""",
    "review": """---
task: {task}
type: review
author_role: reviewer
status: {status}
schema_version: 1
---

# REVIEW: generic-фикстура {task}

## Соответствие SPEC
Фикстура.

## Замечания
Фикстура.

## Вердикт
Фикстура.
""",
    "test_report": """---
task: {task}
type: test_report
author_role: verifier
status: {status}
schema_version: 1
---

# TEST_REPORT: generic-фикстура {task}

## Матрица критериев
Фикстура.

## Вердикт
Фикстура.
""",
}

# "Сдан"-статус для generic-шаблона каждого типа — валиден по `RULES`,
# ни один не запускает никакой версии-гейтинг (schema_version: 1 везде).
NON_DRAFT_STATUS = {
    "spec": "ready",
    "plan": "ready",
    "review": "changes_requested",
    "test_report": "failed",
}

FILE_NAME_BY_TYPE = {
    "spec": "SPEC.md",
    "plan": "PLAN.md",
    "review": "REVIEW.md",
    "test_report": "TEST_REPORT.md",
}

# Стабильная фраза текущего кода (`scripts/guard.py::check_content`) —
# используется только для СЧЁТА нарушений между двумя прогонами одного и
# того же контента (AC-3), не для проверки конкретной формулировки.
MISSING_SECTION_PHRASE = "отсутствует обязательная секция"


def generic_clean_text(atype: str, status: str) -> str:
    return GENERIC_TEMPLATES[atype].format(task=FIXTURE_TASK_ID, status=status)


def generic_broken_text(atype: str, status: str) -> str:
    """Тот же шаблон без единой секции — режет текст по первому '## '
    (тот же приём, что `tests/test_advance_guard.py::TRANSITIONS`
    fixtures: `template.split("\\n## ")[0] + "\\n"`)."""
    text = generic_clean_text(atype, status)
    return text.split("\n## ")[0] + "\n"


TZ_TOO_NEW = """---
task: {task}
type: tz
author_role: operator
status: draft
schema_version: 999
---

# ТЗ: фикстура {task}

Тело свободное.
"""


def tz_too_new_text() -> str:
    return TZ_TOO_NEW.format(task=FIXTURE_TASK_ID)


QUESTIONS_MISSING_SECTION = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 1
---

# QUESTIONS: фикстура {task}

Текст без секции «Вопросы».
"""


def questions_missing_section_text() -> str:
    return QUESTIONS_MISSING_SECTION.format(task=FIXTURE_TASK_ID)
