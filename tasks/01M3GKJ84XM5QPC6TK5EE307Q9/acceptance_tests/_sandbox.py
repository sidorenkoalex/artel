"""Общие помощники планки 01M3GKJ84XM5QPC6TK5EE307Q9 (пересечение зон при
заведении и аддитивные конфликты документов при подтяжке main).

Два предмета, нужные больше чем одному файлу планки:

1. **Зоны при `new`/`status`** (`ZoneOverlapSandbox`) — сев задач с
   заполненными колонками `zones`/`zones_extension` и состоянием, ТЗ с
   заданной строкой «Зоны:», разбор напечатанного `status`. Тонкая
   надстройка над `tests/sandbox.py::InitializedTmpRootTest`, своих
   патчей git/FSM не заводит.
2. **Подтяжка main против НАСТОЯЩЕГО git** (`AdditivePullSandbox`) —
   требование 11 SPEC называет `tests/sandbox.py::RealGitSandbox`
   буквально: аддитивность определяется стадиями индекса, оставленными
   неудачным `git merge`, и заглушкой git этого не изобразить. Здесь —
   сев базы/двух сторон расхождения и один вызов `pull.evaluate`
   напрямую (`repo_path=self.root` — режим внешнего клона, при котором
   `workspace.ensure` не зовётся вовсе и merge идёт прямо в этом
   репозитории).

Лёгкую песочницу переходов FSM (`LightTransitionSandbox`) этот файл не
копирует и не переопределяет: сценариям планки нужен настоящий git
(пункт 2) либо вовсе не нужны переходы (пункт 1).

Имя с ведущим подчёркиванием — единственная форма общего кода планки,
которую checkpoint не отбрасывает (skills/test-authoring.md).
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, pull, store  # noqa: E402
from tests.sandbox import (InitializedTmpRootTest, RealGitSandbox,  # noqa: E402
                           capture_new_task_id)

TASK_ID = "01M3GKJ84XM5QPC6TK5EE307Q9"

# --- зоны при заведении и в `status` ------------------------------------

#: Фиксированный текст действия журнала (SPEC требование 2): запись
#: находится по действию, не по вариативному detail.
OVERLAP_ACTION = "пересечение зон при заведении"

#: Добавка строки `status` (SPEC требование 3) — префикс перед id задачи,
#: занявшей зону.
ZONE_TAKEN_PREFIX = "зона занята: "

#: Состояния, которые займут зону позже (SPEC требование 1) — набор,
#: добавляемый к `zone_lock.BLOCKING_STATES`.
PRE_DEV_STATES = ("spec_writing", "spec_gate", "tests_writing")

#: Общая зона-файл и общая зона-каталог — от `config.COMMON_ZONES`, не
#: литералом: список общих зон — крутилка Оператора, планка обязана
#: пережить её поворот. Защищённые пути из выбора исключены: `new`
#: отказывает ТЗ с защищённой зоной раньше всякой сверки пересечений.
COMMON_FILE_ZONE = next(z for z in config.COMMON_ZONES
                        if not z.endswith("/") and z not in config.PROTECTED_PATHS)
COMMON_DIR_ZONE = next(z for z in config.COMMON_ZONES if z.endswith("/"))

_TZ_TEMPLATE = """Источник: фикстура приёмочной планки {task}.

Требуется:
1. Проверить предупреждение о пересечении зон при заведении.

Зоны: {zones}.
"""


class ZoneOverlapSandbox(InitializedTmpRootTest):
    """Пульт с инициализированной БД, без единой задачи: сценарий сам
    сеет задачи-держатели зон и заводит новую через `catalog.cmd_new`.

    `_warn_pin_divergence` заглушена — сверка пина с origin к предмету
    сверки зон отношения не имеет, а в песочнице без origin печатала бы
    посторонние строки в тот же stdout, который читают тесты.
    """

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        patcher = mock.patch.object(catalog, "_warn_pin_divergence")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tz_file = self.root / "TZ.md"

    def seed_task(self, task_id: str, state: str, zones: str, *,
                  zones_extension: str | None = None,
                  occupying: bool = False) -> str:
        """Задача основного target'а в состоянии `state` с зонами `zones`.

        `occupying` — дописывает маркер «занимает зону» (`"agent run
        started"` актором `developer`, который читает `zone_lock.
        _occupies`): нужен только сценариям про СУЩЕСТВУЮЩИЙ суффикс
        ожидания зоны, новая сверка пересечений этого признака не
        применяет (SPEC требование 1).
        """
        store.insert_task(self.conn, task_id, f"Задача {task_id}", state,
                          f"task/{task_id.lower()}-zona",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        fields = {"zones": zones}
        if zones_extension is not None:
            fields["zones_extension"] = zones_extension
        store.update_task(self.conn, task_id, **fields)
        if occupying:
            store.journal(self.conn, task_id, "developer", "agent run started",
                          "фикстура планки: код этого пребывания начат")
        return task_id

    def new_with_zones(self, zones_line: str, title: str = "Новая задача"):
        """(stdout, id заведённой задачи) — `new --tz` с ТЗ, чья строка
        «Зоны:» равна `zones_line`."""
        self.tz_file.write_text(
            _TZ_TEMPLATE.format(task=TASK_ID, zones=zones_line),
            encoding="utf-8")
        return capture_new_task_id(catalog.cmd_new, title, str(self.tz_file))

    def journal_actions(self, task_id: str) -> list:
        return [row["action"] for row in store.task_steps(self.conn, task_id)]

    def status_lines(self) -> dict:
        """{id задачи: её строка вывода `status`}."""
        out = self.capture(catalog.cmd_status)
        lines = {}
        for line in out.splitlines():
            head = line.split(" ", 1)[0]
            if head:
                lines.setdefault(head, line)
        return lines


def lines_mentioning(out: str, needle: str) -> list:
    """Строки вывода, называющие `needle` — предупреждение ищется по
    строке целиком: критерий требует id, состояние и путь В ОДНОМ
    сообщении, а не рассыпанными по выводу."""
    return [line for line in out.splitlines() if needle in line]


# --- подтяжка main против настоящего git --------------------------------

#: SPEC без AC-разметки (`schema_version: 1`): подставляется вместо
#: чтения SPEC.md с ветки, чтобы `pull.evaluate` после удачного merge
#: уходил по ветке «планки нет и не требуется» (`Pulled`), а не искал
#: артефактную ветку, которой в песочнице нет. Предмет планки — исход
#: merge, не материализация тестов.
LEGACY_SPEC = ("---\ntask: T900\ntype: spec\nauthor_role: analyst\n"
               "status: ready\nschema_version: 1\n---\n\n# SPEC\n")

#: Заглушка регенератора карты: `pull._auto_resolve_map_conflict` зовёт
#: `python3 scripts/codebase_map.py` в СЛИТОМ дереве — в песочнице
#: настоящего генератора нет, а предмет сценария AC-11 — связка
#: «карта + аддитивный документ одним коммитом», не содержимое карты.
_MAP_REGENERATOR = (
    "import pathlib\n"
    "pathlib.Path('docs').mkdir(exist_ok=True)\n"
    "pathlib.Path('docs/codebase-map.md').write_text(\n"
    "    '# Карта\\nперегенерирована\\n', encoding='utf-8')\n")

#: Документы канонического сценария: два растущих вниз списка — ровно
#: тот класс файлов, из-за которого заведена задача (контракт сессии,
#: бэклог, копилка).
DOC_A = "docs/kopilka-fixture.md"
DOC_B = "docs/backlog-fixture.md"

#: Строки базы слияния и добавки каждой из сторон.
BASE_LINES = ("- базовый пункт 1", "- базовый пункт 2", "- базовый пункт 3")
MAIN_LINE = "- добавка main"
BRANCH_LINE = "- добавка ветки задачи"

#: Примитивы git, которыми SPEC требование 5 предписывает доказывать
#: аддитивность и сливать: `git diff --no-index --numstat`, `git
#: merge-file -p --union`, чтение стадий индекса (`:1:`/`:2:`/`:3:`).
_PROBE_TOKENS = ("merge-file", "--no-index", "cat-file")
_STAGE_PREFIXES = (":1:", ":2:", ":3:")


def is_additivity_probe(argv) -> bool:
    """Вызов git — сверка аддитивности либо union-слияние (см.
    `_PROBE_TOKENS`). Читает argv целиком, поэтому одинаково опознаёт и
    `gitcmd.in_repo` (`git -C <repo> …`), и прямой `subprocess.run`."""
    args = [str(a) for a in argv]
    return (any(a in _PROBE_TOKENS for a in args)
            or any(a.startswith(_STAGE_PREFIXES) for a in args))


class AdditivePullSandbox(RealGitSandbox):
    """Настоящий git-репозиторий с базой слияния, веткой задачи и ушедшей
    вперёд `main`; `evaluate()` прогоняет через него подтяжку.

    Задача сидит в `in_dev` — состояние из
    `pull.PULL_CONFLICT_MARKED_STATES`, чтобы сценарии эскалации видели
    метку «нужен шаг роли» там, где она положена сегодня.
    """

    TASK = "T900"

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.branch = f"task/{self.TASK.lower()}-additive"
        store.insert_task(self.conn, self.TASK, "Аддитивная подтяжка",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    # -- фикстуры дерева --------------------------------------------------

    def write_lines(self, rel: str, lines) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{line}\n" for line in lines),
                        encoding="utf-8")

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def commit_all(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def seed_base(self, files: dict, *, with_map_regenerator: bool = False) -> None:
        """База слияния на `main`: `{путь: [строки]}`."""
        for rel, lines in files.items():
            self.write_lines(rel, lines)
        if with_map_regenerator:
            (self.root / "scripts").mkdir(parents=True, exist_ok=True)
            (self.root / "scripts" / "codebase_map.py").write_text(
                _MAP_REGENERATOR, encoding="utf-8")
        self.base_sha = self.commit_all("база слияния")

    def seed_branch_side(self, files: dict) -> None:
        self.checkout(self.branch, create=True)
        for rel, lines in files.items():
            self.write_lines(rel, lines)
        self.branch_sha = self.commit_all("сторона ветки задачи")

    def seed_main_side(self, files: dict) -> None:
        self.checkout(config.MAIN_BRANCH)
        for rel, lines in files.items():
            self.write_lines(rel, lines)
        self.main_sha = self.commit_all("сторона main")
        self.checkout(self.branch)

    def seed_additive_conflict(self, *rels: str,
                               with_map_regenerator: bool = False) -> None:
        """Канонический аддитивный конфликт по каждому из `rels`: база —
        `BASE_LINES`, ветка дописывает `BRANCH_LINE`, main дописывает
        `MAIN_LINE` в то же место. Ни одна сторона базовых строк не
        трогает."""
        self.seed_base({rel: BASE_LINES for rel in rels},
                       with_map_regenerator=with_map_regenerator)
        self.seed_branch_side(
            {rel: list(BASE_LINES) + [BRANCH_LINE] for rel in rels})
        self.seed_main_side(
            {rel: list(BASE_LINES) + [MAIN_LINE] for rel in rels})

    def assert_all_lines_present(self, rel: str) -> None:
        """Файл несёт ВСЕ строки базы и обе добавки, без маркеров
        конфликта."""
        text = self.read(rel)
        for line in tuple(BASE_LINES) + (MAIN_LINE, BRANCH_LINE):
            self.assertIn(line, text,
                          f"{rel}: строка {line!r} потеряна при слиянии\n{text}")
        for marker in ("<<<<<<<", "=======", ">>>>>>>"):
            self.assertNotIn(marker, text,
                             f"{rel}: в слитом файле остались маркеры "
                             f"конфликта\n{text}")

    # -- прогон подтяжки --------------------------------------------------

    def _spec_text(self, conn, task_id, branch, name):
        return LEGACY_SPEC

    def evaluate(self):
        """`pull.evaluate` над этим репозиторием — тот же вызов, что
        делает `fsm._pull_main_or_escalate`, с узлами fsm.py, поданными
        параметрами (инъекция, зафиксированная докстрингом pull.py)."""
        t = store.get_task(self.conn, self.TASK)
        return pull.evaluate(
            self.conn, self.TASK, t, "in_dev",
            origin_main_source=lambda target: None,
            origin_main_sha=lambda target: self.main_sha,
            read_branch_text_or_refuse=self._spec_text,
            repo_path=self.root)

    def evaluate_with_broken_git(self):
        """(исход, перехваченные вызовы) — то же, но каждый примитив
        сверки аддитивности/union-слияния отвечает ненулевым кодом.

        Подменяется `subprocess.run` (а не `gitcmd.git`): так отказ видят
        и вызовы через `gitcmd`, и прямой `subprocess.run`, если
        реализация выберет его. Всё остальное делегируется НАСТОЯЩЕМУ
        `subprocess.run` — сам merge, abort и чтение конфликтных файлов
        идут как обычно.
        """
        real_run = subprocess.run
        probes = []

        def fake_run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and is_additivity_probe(cmd):
                probes.append(tuple(str(a) for a in cmd))
                return subprocess.CompletedProcess(
                    list(cmd), 1, "", "fatal: искусственный сбой git")
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(subprocess, "run", fake_run):
            outcome = self.evaluate()
        return outcome, probes

    # -- наблюдения -------------------------------------------------------

    def state(self) -> str:
        return store.get_task(self.conn, self.TASK)["state"]

    def journal_texts(self) -> list:
        return [f"{row['action']} | {row['detail'] or ''}"
                for row in store.task_steps(self.conn, self.TASK)]

    def journal_actions(self) -> list:
        return [row["action"] for row in store.task_steps(self.conn, self.TASK)]

    def head_subject(self) -> str:
        return self.git("log", "-1", "--format=%s").strip()

    def head_parent_count(self) -> int:
        return len(self.git("log", "-1", "--format=%P").split())

    def commits_added_to_branch(self) -> int:
        """Сколько коммитов легло на ПЕРВОГО родителя ветки задачи с
        момента её собственной вершины: у удачной подтяжки это ровно один
        коммит слияния, отдельный коммит разрешения дал бы два."""
        out = self.git("rev-list", "--count", "--first-parent",
                       f"{self.branch_sha}..HEAD")
        return int(out.strip())

    def merge_in_progress(self) -> bool:
        return (self.root / ".git" / "MERGE_HEAD").exists()

    def worktree_dirty(self) -> str:
        return self.git("status", "--porcelain").strip()

    def pull_commit_message(self) -> str:
        return f"{self.TASK}: подтяжка {config.MAIN_BRANCH}"

    def assert_escalated_as_before(self, outcome, expected_files) -> None:
        """Прежнее поведение конфликта подтяжки байт-в-байт (SPEC
        требование 8): `Conflict` с теми же файлами, прежний текст
        `pull._merge_conflict_note` внутри прежней обёртки `detail`,
        метка `pull.PULL_CONFLICT_ROLE_STEP_MARKER` в журнале, состояние
        `escalated` и откаченный (`git merge --abort`) worktree."""
        self.assertIsInstance(
            outcome, pull.Conflict,
            f"конфликт обязан эскалировать как прежде, получено: {outcome!r}")
        self.assertEqual(sorted(expected_files), sorted(outcome.files),
                         "перечень конфликтных файлов эскалации изменился")
        self.assertEqual("escalated", self.state())
        prefix = (f"конфликт подтяжки {config.MAIN_BRANCH} в ветку "
                  f"{self.branch}: конфликтные файлы: ")
        self.assertTrue(
            outcome.note.startswith(prefix),
            f"текст эскалации изменился: ожидался прежний префикс "
            f"{prefix!r}, получено {outcome.note!r}")
        self.assertIn(
            pull.PULL_CONFLICT_ROLE_STEP_MARKER, self.journal_actions(),
            f"эскалация из in_dev обязана нести метку «нужен шаг роли»: "
            f"{self.journal_actions()}")
        self.assertFalse(self.merge_in_progress(),
                         "недоказанная аддитивность обязана откатывать "
                         "merge (git merge --abort)")
        self.assertEqual("", self.worktree_dirty(),
                         "после отката рабочее дерево обязано быть чистым")
