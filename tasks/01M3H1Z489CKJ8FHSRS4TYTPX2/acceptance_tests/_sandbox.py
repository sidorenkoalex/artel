"""Общие помощники планки 01M3H1Z489CKJ8FHSRS4TYTPX2 — заведение
подзадачи деления против НАСТОЯЩЕГО git-репозитория.

Предмет всех сценариев планки — один вызов `catalog.spawn_subtask` и его
наблюдаемые следы: колонка `tasks.zones` подзадачи, её журнал и stdout.
Настоящий git нужен потому, что `spawn_subtask` коммитит `tasks/<id>/`
плотницки в артефактную ветку пульта (`artifact_branch.commit_files` →
прямой `subprocess.run`), и сценарий AC-1 читает собранный `TZ.md` из
этой ветки — заглушкой git это не изобразить. Поэтому база —
`tests/sandbox.py::RealGitSandbox`, тот же, что у существующего
юнит-теста этой функции (`tests/test_catalog_spawn_subtask.py`).

Лёгкую песочницу переходов FSM (`LightTransitionSandbox`) этот файл не
копирует и не переопределяет: переходов в сценариях планки нет вовсе —
`spawn_subtask` зовётся напрямую, как её зовёт `fsm.
_spawn_division_subtasks` (родитель уходит в `killed` уже ПОСЛЕ всех
подзадач, поэтому в момент каждого заведения он ещё в `spec_gate` — это
и воспроизводит `seed_parent` ниже).

Имя с ведущим подчёркиванием — единственная форма общего кода планки,
которую checkpoint не отбрасывает (skills/test-authoring.md).
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK_ID = "01M3H1Z489CKJ8FHSRS4TYTPX2"

#: Родитель деления: строка задачи в `spec_gate` — состояние, в котором
#: `fsm._approve_spec_gate` зовёт `spawn_subtask` (в `killed` родитель
#: уходит после заведения всех подзадач).
PARENT_ID = "T700"
PARENT_STATE = "spec_gate"

#: Название родителя несёт путь НАМЕРЕННО: ссылка «Родительская задача:
#: <id> — <название>» становится первой строкой `TZ.md` подзадачи, и
#: критерий AC-1 отдельно требует, чтобы эта строка разбору зон не
#: мешала. Путь выбран так, что с зонами фикстур он не пересекается ни
#: буквально, ни по вложенности.
PATH_IN_PARENT_TITLE = "orchestrator/runner.py"
PARENT_TITLE = f"Родитель деления: правка {PATH_IN_PARENT_TITLE}"

#: Зоны фикстур. Общие зоны (`config.COMMON_ZONES`) выпадают из сверки
#: пересечений (`zone_lock._own_paths`), поэтому пригодность этих путей
#: проверяется от config в `setUp` — список общих зон крутит Оператор.
SHARED_ZONE = "orchestrator/pull.py"
OTHER_ZONE = "docs/operator-session.md"

#: Чужой target: любой, кроме основного. Замок зон — механика только
#: основного target'а, и `_warn_zone_overlap` берёт target из параметра.
FOREIGN_TARGET = "acme"

_TZ_BODY = """Зоны: {zones}.
Порядок: первая, без зависимостей

Текст ТЗ подзадачи деления — фикстура планки {task}.
"""


def tz_body(zones: str) -> str:
    """Тело подраздела секции «## Деление» со строкой «Зоны: …» ПЕРВОЙ
    строкой — так его и отдаёт `guard`/`fsm` из SPEC родителя, и именно
    поэтому строка ссылки на родителя оказывается ровно перед ней."""
    return _TZ_BODY.format(zones=zones, task=TASK_ID)


#: Подраздел без строки «Зоны:» вовсе и подраздел с пустой строкой
#: «Зоны:» — два случая AC-2 одним словом «или».
TZ_BODY_WITHOUT_ZONES_LINE = """Порядок: первая, без зависимостей

Текст ТЗ подзадачи деления без строки зон — фикстура планки.
"""
TZ_BODY_EMPTY_ZONES_LINE = """Зоны:
Порядок: первая, без зависимостей

Текст ТЗ подзадачи деления с пустой строкой зон — фикстура планки.
"""


def overlap_lines(out: str, task_id: str, zone: str) -> list:
    """Строки вывода, называющие РАЗОМ id пересекающейся задачи и общий
    путь: предупреждение ищется по строке целиком, а не по рассыпанным по
    выводу словам.

    Одного id для опознания предупреждения мало: строку «… создана
    делением <id родителя> …» печатает само заведение подзадачи, и поиск
    по одному id родителя находил бы её всегда — вместе с ложной
    зеленотой позитивных сценариев и ложной краснотой негативных.
    """
    return [line for line in out.splitlines()
            if task_id in line and zone in line]


def zone_set(column: str | None) -> set:
    """Колонка `tasks.zones` как множество путей — сверка идёт по составу
    зон, а не по вёрстке строки: склейку элементов запятой делает общая
    механика записи (`catalog._record_preliminary_zones`), а не эта
    задача."""
    if not column:
        return set()
    return {piece.strip() for piece in column.split(",") if piece.strip()}


class SubtaskZoneSandbox(RealGitSandbox):
    """Пульт со свежим git-репозиторием, схемой БД и строкой родителя
    деления в `spec_gate`; сценарий сам заводит подзадачи через
    `catalog.spawn_subtask`.

    Зоны родителя по умолчанию не заполнены (`NULL`): пересечение с
    родителем — предмет ОТДЕЛЬНОГО сценария, и в остальных он не должен
    подмешивать свой id в вывод.
    """

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        # Предпосылка о config, а не о сегодняшнем значении (урок 28.08):
        # попади фикстурная зона в общий список, сверка пересечений
        # отбрасывала бы её, и сценарии планки зеленели бы вхолостую.
        for zone in (SHARED_ZONE, OTHER_ZONE):
            self.assertEqual(
                {zone}, zone_lock._own_paths(zone),
                f"фикстурная зона {zone} покрыта config.COMMON_ZONES — "
                f"сверка пересечений её отбросит, и сценарии планки "
                f"потеряют предмет: возьми зону вне общего списка")
        self.seed_parent()

    def seed_parent(self) -> None:
        store.insert_task(self.conn, PARENT_ID, PARENT_TITLE, PARENT_STATE,
                          f"task/{PARENT_ID.lower()}-delenie",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def set_parent_zones(self, zones: str) -> None:
        """Зоны родителя — те, что записал approve его гейта SPEC."""
        store.update_task(self.conn, PARENT_ID, zones=zones)

    def spawn(self, body: str, *, title: str = "Часть деления",
              target: str | None = None) -> tuple:
        """(stdout, id подзадачи) — одно заведение подзадачи деления от
        `PARENT_ID`, тем же вызовом, каким его делает
        `fsm._spawn_division_subtasks` (`target` родителя параметром).

        Свой перехват stdout, а не `tests.sandbox.capture`: тот принимает
        только позиционные аргументы, а `target` у `spawn_subtask`
        keyword-only.
        """
        buf = io.StringIO()
        with redirect_stdout(buf):
            sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE, title,
                                           body, target=target)
        return buf.getvalue(), sub_id

    def row(self, task_id: str):
        return store.get_task(self.conn, task_id)

    def zones_of(self, task_id: str):
        return self.row(task_id)["zones"]

    def journal_actions(self, task_id: str) -> list:
        return [r["action"] for r in store.task_steps(self.conn, task_id)]

    def journal_details(self, task_id: str, action: str) -> list:
        return [r["detail"] or "" for r in store.task_steps(self.conn, task_id)
                if r["action"] == action]
