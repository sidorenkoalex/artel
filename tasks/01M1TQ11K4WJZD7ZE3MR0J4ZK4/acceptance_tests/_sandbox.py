"""Общие фикстуры приёмочных тестов 01M1TQ11K4WJZD7ZE3MR0J4ZK4 (SPEC:
«подсказка потолка по калибровке при new и на гейте SPEC»).

Два независимых угла требований 2/3 SPEC, оба уже применялись прежними
задачами тем же приёмом:

- `NewHintSandbox` (`tests.sandbox.TmpRootTest`) — `catalog.cmd_new` с
  файлом ТЗ, несущим «Рамка: $N», «Требуется:» и «Зоны:» (требование 2).
  Тот же приём, что `tests/test_catalog_new_race.py::
  PeekTaskNumberRaceTest` уже держит для `cmd_new` (копия `templates/`,
  `cmd_init` до `cmd_new` — счётчики/сев не нужны, но `cmd_init` заводит
  схему БД, которую `store.insert_task`/`store.db()` иначе не создаёт).
- `GateHintSandbox` (`tests.sandbox.RealGitSandbox`) — SPEC на
  артефактной ветке пульта, `fsm.cmd_advance` в `spec_gate`, затем
  `fsm.cmd_approve` (требование 3). Тот же приём, что `tests/
  test_zones_approve.py::ZonesApproveTest` уже держит для approve на
  `spec_gate` (артефактная ветка — единственный источник, с которого
  FSM читает SPEC.md, `orchestrator/artifact_source.resolve` всегда
  `foreign=True`).

Интерфейс `orchestrator.budget.recommended_budget_usd(ac_count,
zone_files) -> float` — придуман этими тестами (SPEC требование 1
называет только состав таблицы: пороги по числу критериев и файлов
зоны, значения ADR-0014; имя функции/атрибута SPEC не называет). Тот же
приём уже применён `config.TOKEN_RATES` (tasks/
01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/test_ac1_token_rate_table.py,
докстрока: «SPEC называет только состав данных ..., не имя атрибута/
полей — разработчик реализует под эту форму»). Файлы `test_ac1_ac2_*`
проверяют её значения напрямую через гейт SPEC — принудительно занижая
`budget_usd`, чтобы получить строку предупреждения (AC-6/AC-10),
буквальный формат которой несёт число-ориентир таблицы: не нужно знать
имя функции, чтобы прочитать число из этой строки, но нужно её
СУЩЕСТВОВАНИЕ, ради которого файлы `test_ac5..ac11` и проверяют
поведение `new`/approve по существу.

Не `test_*.py` — guard.py читает AC-разметку и маркер красноты только
из `test_*.py` (scripts/guard.py::scan_acceptance_tests/
scan_redness_markers) — этот файл вспомогательный, не сам критерий.
"""
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, catalog, config, fsm, store  # noqa: E402
from tests.sandbox import (RealGitSandbox, TmpRootTest, capture,  # noqa: E402
                           capture_new_task_id)

# Строка предупреждения — буквально по AC-6/AC-10: «рамка ниже
# калибровки: $N против ~$M». Допуск на ".00"/иные десятичные хвосты
# (`(?:\.\d+)?`) — SPEC не фиксирует формат чисел (целое или с копейками),
# кодовая база вокруг (`budget.py`, `catalog.py::cmd_status`) сегодня
# смешивает оба стиля.
WARNING_RE = re.compile(
    r"рамка ниже калибровки: \$(?P<n>\d+(?:\.\d+)?) против "
    r"~\$(?P<m>\d+(?:\.\d+)?)")


def dollar_re(amount) -> re.Pattern:
    """Регэксп на присутствие суммы `amount` в выводе с допуском на
    десятичный хвост (`$35` либо `$35.00`), с границей слова после
    числа, чтобы `$350` не засчитался как `$35`."""
    return re.compile(rf"\${amount}(?:\.\d+)?\b")


def zone_paths(n: int) -> str:
    """`n` синтетических путей зоны через запятую — конкретное имя файла
    не имеет значения ни для одного AC, важно только их число."""
    return ", ".join(f"module_{i}.py" for i in range(1, n + 1))


def ac_items(n: int) -> str:
    """`n` строк `AC-<k>. текст.` — формат раздела «Критерии приёмки»
    (`scripts/guard.py::AC_ITEM`)."""
    return "\n".join(f"AC-{i}. Критерий фикстуры номер {i}."
                     for i in range(1, n + 1))


def trebuetsya_items(n: int) -> str:
    """`n` нумерованных пунктов раздела «Требуется:» ТЗ."""
    return "\n".join(f"{i}. Пункт фикстуры номер {i}."
                     for i in range(1, n + 1))


# ===== Гейт SPEC (требование 3, AC-1/AC-2/AC-9/AC-10/AC-11) =====

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
zones: {zones}
---

# SPEC: фикстура гейта калибровки бюджета

## Контекст
Фикстура приёмочного теста задачи 01M1TQ11K4WJZD7ZE3MR0J4ZK4 — короткий
безобидный текст, не связанный с реальной механикой пульта.

## Требования
1. Единственное требование фикстуры.

## Критерии приёмки
{ac_body}

## Не входит
- Всё остальное.
"""


def spec_text(*, task: str, ac_count: int, zone_files: int) -> str:
    return SPEC_TEMPLATE.format(task=task, zones=zone_paths(zone_files),
                                ac_body=ac_items(ac_count))


class GateHintSandbox(RealGitSandbox):
    """`RealGitSandbox` даёт git-репозиторий + схему БД (`tests/
    sandbox.py`). Задача заводится напрямую `store.insert_task` —
    `_cmd_approve` на `spec_gate` не читает ни `targets.yaml`, ни посев
    ролей (тот же вывод, что уже сделан `ZonesApproveSandbox`)."""

    def enter_spec_gate(self, task_id: str, *, ac_count: int,
                        zone_files: int, budget_usd: float) -> str:
        """Заводит задачу с `budget_usd` НАЧАЛЬНЫМ значением, коммитит
        SPEC (без поля `budget_usd` во frontmatter — `apply_spec_budget`
        тогда не трогает потолок, требование 3 говорит о ДЕЙСТВУЮЩЕМ
        потолке задачи, не о новой оценке SPEC), переводит
        `spec_writing -> spec_gate`. Возвращает `fixed_sha` для approve."""
        branch = f"task/{task_id.lower()}-x"
        store.insert_task(store.db(), task_id, "Фикстура гейта калибровки",
                          "spec_writing", branch, config.DEFAULT_TARGET,
                          budget_usd)
        artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md":
                     spec_text(task=task_id, ac_count=ac_count,
                              zone_files=zone_files)},
            f"{task_id}: SPEC готов")
        capture(fsm.cmd_advance, task_id)
        return store.get_task(store.db(), task_id)["fixed_sha"]

    def approve(self, task_id: str, sha: str) -> str:
        return capture(fsm.cmd_approve, task_id, sha)

    def task_row(self, task_id: str) -> dict:
        return dict(store.get_task(store.db(), task_id))

    def journal_details(self, task_id: str) -> list[str]:
        return [r["detail"] for r in store.task_steps(store.db(), task_id)]


# ===== `new` (требование 2, AC-5/AC-6/AC-7/AC-8) =====

TZ_TEMPLATE = """Контекст фикстуры приёмочного теста — короткий безобидный
текст, не связанный с реальной механикой пульта.

Требуется:
{trebuetsya}

Зоны: {zones}.
Не входит: всё остальное.

Рамка: ${rama}.
"""


def tz_text(*, trebuetsya_count: int, zone_files: int, rama) -> str:
    return TZ_TEMPLATE.format(trebuetsya=trebuetsya_items(trebuetsya_count),
                              zones=zone_paths(zone_files), rama=rama)


class NewHintSandbox(TmpRootTest):
    """`cmd_new` читает `templates/SPEC.md` РЕАЛЬНОГО дерева (`config.
    TEMPLATES` не входит в `ALL_CONFIG_ATTRS`, якорится на настоящий
    корень при импорте) — здесь тем не менее копируется в песочницу тем
    же приёмом, что `tests/test_catalog_new_race.py::
    PeekTaskNumberRaceTest`, ради устойчивости к будущей правке этого
    поведения. `cmd_init` заводит схему БД до `cmd_new`."""

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        self.capture(catalog.cmd_init)

    def new_with_tz(self, *, trebuetsya_count: int, zone_files: int, rama,
                    title: str = "Фикстура подсказки new") -> tuple:
        """(вывод, task_id) — `catalog.cmd_new` с файлом ТЗ, положенным в
        песочницу."""
        tz_path = self.root / "tz_fixture.md"
        tz_path.write_text(
            tz_text(trebuetsya_count=trebuetsya_count, zone_files=zone_files,
                   rama=rama),
            encoding="utf-8")
        return capture_new_task_id(catalog.cmd_new, title, str(tz_path))

    def journal_details(self, task_id: str) -> list[str]:
        return [r["detail"] for r in store.task_steps(store.db(), task_id)]

    def task_row(self, task_id: str) -> dict:
        return dict(store.get_task(store.db(), task_id))
