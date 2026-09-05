"""Общие фикстуры приёмочных тестов 01M1NKVPD2A79PQ6K0JVV1B2Q1 (SPEC:
«Механика зон» — эта ветка/задача реализует ЧАСТЬ 1: машиночитаемое поле
`zones:` во frontmatter SPEC и общий список зон вне конфликта, по разделу
SPEC «Оценка объёма и деление» (нарезка на 3 подзадачи; часть 3 уже
заведена отдельной задачей 01M1P9QCHPHSCEA6TK13PV85SP и зависит от мержа
этой части в main).

Часть 1 не трогает `orchestrator/auto.py`/`doctor.py`/`catalog.py`
(занятость зоны, часть 2) и не трогает `orchestrator/fsm_advance.py`
(сверка диффа при `in_dev -> review`, часть 3) — только `orchestrator/
store.py` (схема), `orchestrator/config.py` (общий список), `orchestrator/
fsm.py` (сохранение `zones` при `approve` на `spec_gate`), `scripts/
guard.py` (требование поля). `test_scope_markers.py` в этом же каталоге
объясняет, почему AC-5..AC-15 (части 2 и 3) несут пометку `skip`, а не
тест, — тот же класс решения, что уже применён к защищённым путям в
прецеденте tasks/01M1KS8K9RXWHX2PW3ZKB0P903 (`test_ac_manual_and_escalate_
markers.py`).

Чёрный ящик над `scripts.guard.check_content` для текстовых проверок
(AC-1, AC-4) — тот же приём, что `tasks/01M1KS8K9RXWHX2PW3ZKB0P903/
acceptance_tests/_sandbox.py`; git-песочница `ZonesApproveSandbox` — для
проверки сохранения в БД при `approve` (AC-3), тем же приёмом, что
`tests/test_git_fixation.py::RealPultGitTest`/`tests/sandbox.py::
RealGitSandbox` (артефактная ветка пульта — ЕДИНСТВЕННЫЙ источник, с
которого FSM читает SPEC.md, `orchestrator/artifact_source.resolve`
сегодня всегда возвращает `foreign=True` — читать с диска мимо git нельзя
ни для одной задачи, включая self/артель).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from scripts import guard  # noqa: E402
from orchestrator import artifact_branch, config, fsm, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

FIXTURE_TASK_ID = "01M1NKVPD2A79PQ6K0JVV1B2Q1-FIXTURE"

# Версия схемы, начиная с которой поле `zones:` обязано быть заполнено
# (AC-1: «version-gated ... по образцу requires_ac_markup/requires_split_
# assessment»). SPEC не называет число буквально — вывод строится тем же
# способом, каким сама история guard.py уже дважды поднимала
# `SUPPORTED_SCHEMA_VERSION` (1 -> 2 требованием AC-разметки, T023; 2 -> 3
# требованием секции «Оценка объёма и деление», T100/01M1KS8K9RXWHX2PW3ZKB0P903)
# — очередной шаг версии-гейтинга новой обязательной проверки следующим
# целым числом, 3 -> 4: САМА эта задача несёт `schema_version: 3` без
# `zones:` (tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/SPEC.md) и обязана остаться
# валидной, что исключает переиспользование версии 3 для новой обязательной
# проверки (сломало бы обратную совместимость, которую сам AC-1 требует
# сохранить). Тесты ниже НЕ полагаются на точное число ради самого факта
# отказа — они проверяют, что сообщение отказа называет поле `zones`
# буквально (см. докстринг NewVersionRequiresZonesFieldTest), а не просто
# «список ошибок непуст»: непустой список уже и сегодня возвращается для
# любой ещё не поддерживаемой версии по ДРУГОЙ причине (schema_errors,
# «новее поддерживаемой») — assertion на непустоту в одиночку был бы
# зелёным уже сейчас, до этой задачи, и не ловил бы ни одной мутации.
NEW_ZONES_VERSION = 4

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: {version}
budget_usd: 15
{zones_line}---

# SPEC: фикстура теста поля zones

## Контекст
Фикстура приёмочного теста задачи 01M1NKVPD2A79PQ6K0JVV1B2Q1 — короткий
безобидный текст, не связанный с реальной механикой пульта.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры.

## Не входит
- Всё остальное.
"""


def spec_text(*, version: int = NEW_ZONES_VERSION,
             zones: str | None = None) -> str:
    """Текст фиктивного `SPEC.md`.

    `version` — значение frontmatter `schema_version`.

    `zones` — значение frontmatter-поля `zones:`; `None` (умолчание) —
    поле отсутствует целиком. Значение — ОДИН путь без потокового списка
    `[a, b]`: `orchestrator/yamlmini.py::frontmatter` сегодня разбирает
    frontmatter построчно голым скаляром (`scalar()`), не потоковым
    списком (`_value()`, который эта функция вообще не зовёт для
    frontmatter-блока, только для вложенных отображений вроде
    `roles.yaml`) — тесты этого файла проверяют ТРЕБОВАНИЕ поля (AC-1) и
    факт сохранения ЗНАЧЕНИЯ (AC-3), не конкретный синтаксис
    представления списка, который AC-1 не называет буквально и который
    решает разработчик.

    Одно значение `orchestrator/store.py` (а не 5+) — намеренно ниже
    `config.SPLIT_SIGNAL_ZONE_FILES`: `scripts/guard.py::_zone_paths`
    сканирует ВЕСЬ текст SPEC (включая frontmatter) на пути вида
    `orchestrator/*.py`/`scripts/*.py` как отдельный сигнал «подозрения на
    большой объём» (несвязанная механика, тот же формат путей) —
    фикстура обязана остаться НИЖЕ порога этого сигнала, иначе
    `split_assessment_errors` примешивает к результату `check_content`
    ошибку из ДРУГОЙ, не связанной с AC-1/AC-3 этой задачи проверки.
    """
    zones_line = f"zones: {zones}\n" if zones is not None else ""
    return SPEC_TEMPLATE.format(task=FIXTURE_TASK_ID, version=version,
                                zones_line=zones_line)


def check(**kwargs) -> list[str]:
    """`guard.check_content` над `spec_text(**kwargs)`."""
    return guard.check_content("SPEC.md", spec_text(**kwargs))


class ZonesApproveSandbox(RealGitSandbox):
    """Песочница approve на `spec_gate` с реальным git (AC-3).

    `RealGitSandbox` уже даёт `self.root` — настоящий git-репозиторий с
    веткой `main`, все пути `config` подменены во временный каталог, схема
    БД создана (`tests/sandbox.py`). Заводить задачу через `catalog.
    cmd_new`/`catalog.cmd_init` не нужно: `_cmd_approve` на `spec_gate`
    не читает ни `targets.yaml`, ни посев ролей/бюджета — только строку
    `tasks` (заведена здесь напрямую `store.insert_task`) и содержимое
    SPEC.md АРТЕФАКТНОЙ ветки пульта (`artifact_branch.commit_files`,
    единственный источник, `orchestrator/artifact_source.resolve` всегда
    `foreign=True`); проверено прогоном этого сценария (`fsm.cmd_advance`
    -> `spec_gate`, затем `fsm.cmd_approve`) в этой же песочнице до
    написания тестов ниже.
    """

    TASK = "01ZONESACCEPTANCETASKAC3"

    def enter_spec_gate(self, spec_text_value: str) -> str:
        """Заводит задачу, коммитит `spec_text_value` в артефактную ветку,
        переводит `spec_writing -> spec_gate`. Возвращает `fixed_sha`,
        который `approve` потребует как подтверждение (`APPROVE_NEEDS_SHA`,
        `orchestrator/fsm.py`)."""
        store.insert_task(store.db(), self.TASK, "Zones approve fixture",
                          "spec_writing", f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, 15.0)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": spec_text_value},
            f"{self.TASK}: SPEC готов")
        capture(fsm.cmd_advance, self.TASK)
        return store.get_task(store.db(), self.TASK)["fixed_sha"]

    def approve(self, sha: str) -> str:
        return capture(fsm.cmd_approve, self.TASK, sha)

    def task_row(self) -> dict:
        """Строка задачи как обычный `dict` — `sqlite3.Row` бросает
        `IndexError` на несуществующей колонке (`zones` до реализации),
        `dict.get` вместо этого мягко отдаёт `None`, оставляя красноту
        честным `assertEqual`, а не необработанным исключением (см. AC-3
        докстринги ниже)."""
        return dict(store.get_task(store.db(), self.TASK))
