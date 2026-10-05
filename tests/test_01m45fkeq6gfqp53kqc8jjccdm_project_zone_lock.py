"""Замок зон внутри одного внешнего проекта (AC-1).

Группа: долгоживущий
Красен до реализации: zone_lock.blocking_conflict/queue_position/forecast_overlaps и catalog._warn_zone_overlap/_zone_forecast_suffix отсекают всякую задачу не-DEFAULT_TARGET — задача внешнего проекта не получает отказа по зоне (None), не стоит в очереди (0/0), `new` не пишет предупреждения о пересечении зон, `status` не печатает «зона занята».

Песочница — `tests.sandbox.InitializedTmpRootTest`. Задачи заводятся
строкой `store.insert_task` с нужным проектом, состоянием и зонами;
«задача заняла зону» — штатным `zone_lock.claim` от её имени. Для `new`
внешнему проекту заводится клон с записью в `targets.yaml`
(`tests.sandbox.make_project_repo`), и задача идёт штатным
`catalog.cmd_new` с файлом ТЗ. Пути зон, имена проектов, состояния
держателя и ждущей задачи, число ждущих — от зерна; зерно печатается и
входит в текст каждого провала.
"""
import functools
import random
import unittest

from orchestrator import catalog, config, idgen, store, zone_lock
from tests.sandbox import (InitializedTmpRootTest, capture,
                           capture_new_task_id, make_project_repo)

EXTERNAL_PROJECTS = ("ext", "acme", "widget")
ZONE_TAKEN = "зона занята"


class ProjectZoneLockSandbox(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.used_paths: set[str] = set()

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def fresh_path(self) -> str:
        """Путь файла зоны, не покрытый `config.COMMON_ZONES`, в каталоге,
        не встречавшемся в этом тесте раньше (зона-каталог одного прогона
        не задевает другой)."""
        while True:
            directory = f"pkg{self.rng.randrange(10000)}/"
            path = f"{directory}mod{self.rng.randrange(1000)}.py"
            covered = any(path == common or (common.endswith("/")
                                             and path.startswith(common))
                          for common in config.COMMON_ZONES)
            if not covered and directory not in self.used_paths:
                self.used_paths.add(directory)
                return path

    def zone_of(self, path: str) -> str:
        """Зона, пересекающаяся с `path`: сам файл либо его каталог."""
        return path if self.rng.random() < 0.5 else path.rsplit("/", 1)[0] + "/"

    def insert(self, state: str, zones: str, target: str) -> str:
        task_id = idgen.new_task_id()
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-fixture", target,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=zones)
        return task_id

    def holder(self, zones: str, target: str, state: str = "in_dev") -> str:
        """Задача `target`, занявшая свои зоны штатным захватом."""
        task_id = self.insert(state, zones, target)
        refusal, _pending = zone_lock.claim(
            self.conn, task_id, store.get_task(self.conn, task_id))
        self.conn.commit()
        self.assertIsNone(refusal, self.note(f"держатель {task_id}: {refusal}"))
        return task_id

    def conflict(self, task_id: str):
        return zone_lock.blocking_conflict(
            self.conn, task_id, store.get_task(self.conn, task_id))

    def other_project(self, project: str) -> str:
        choices = [p for p in EXTERNAL_PROJECTS + (config.DEFAULT_TARGET,)
                   if p != project]
        return self.rng.choice(choices)


class BlockingWithinProjectTest(ProjectZoneLockSandbox):

    def test_ac1_waiter_of_external_project_is_refused_by_same_project_holder(self):
        """Задача внешнего проекта ждёт зону, занятую задачей того же проекта.

        Несколько прогонов: держатель внешнего проекта (состояние — любое из
        `zone_lock.BLOCKING_STATES`) захватил зону, задача того же проекта в
        `in_dev` заявила пересекающуюся зону (тот же файл или его каталог).
        `blocking_conflict` ждущей не `None` и называет держателя.

        Ловит мутацию: в `blocking_conflict` осталась ранняя отсечка
        `t["target"] != config.DEFAULT_TARGET` (или кандидаты по-прежнему
        фильтруются по артели) — ждущая задача внешнего проекта получала бы
        `None` и стартовала бы шаг разработчика поверх занятой зоны."""
        for _ in range(4):
            project = self.rng.choice(EXTERNAL_PROJECTS)
            path = self.fresh_path()
            state = self.rng.choice(zone_lock.BLOCKING_STATES)
            occupier = self.holder(self.zone_of(path), project, state)
            waiter = self.insert("in_dev", self.zone_of(path), project)

            got = self.conflict(waiter)

            self.assertIsNotNone(got, self.note(
                f"{project}: держатель {occupier} ({state}), путь {path}"))
            self.assertEqual(got[1], occupier, self.note(f"{got}"))
            self.assertEqual(got[2], state, self.note(f"{got}"))

    def test_ac1_tasks_of_different_projects_do_not_block_each_other(self):
        """Одинаковые пути зон в разных проектах замка не дают.

        Несколько прогонов: задача проекта A (внешний или артель) захватила
        зону; задача внешнего проекта B в `in_dev` с тем же путём отказа не
        получает и в очереди этого пути не стоит. Затем в B появляется свой
        держатель того же пути — и отказ называет именно его, не задачу A.

        Ловит мутацию: ранняя отсечка по `DEFAULT_TARGET` просто удалена, а
        сверки проекта кандидата нет — задача B ждала бы задачу чужого
        проекта A (первая проверка), либо отказ называл бы держателя A
        вместо своего (вторая); отсечка оставлена — второй проверке
        отказа нет вовсе."""
        for _ in range(4):
            project_b = self.rng.choice(EXTERNAL_PROJECTS)
            project_a = self.other_project(project_b)
            path = self.fresh_path()
            foreign = self.holder(path, project_a)
            waiter = self.insert("in_dev", self.zone_of(path), project_b)

            self.assertIsNone(self.conflict(waiter), self.note(
                f"{project_b} ждёт задачу {foreign} проекта {project_a}"))
            position, _total = zone_lock.queue_position(self.conn, waiter, path)
            self.assertEqual(position, 0, self.note(
                f"{project_b} стоит в очереди {path} из-за {project_a}"))

            own = self.holder(path, project_b)
            got = self.conflict(waiter)

            self.assertIsNotNone(got, self.note(
                f"{project_b}: свой держатель {own}, путь {path}"))
            self.assertEqual(got[1], own, self.note(
                f"{got}; чужой держатель {foreign} ({project_a})"))


class QueueWithinProjectTest(ProjectZoneLockSandbox):

    def test_ac1_waiters_of_external_project_queue_on_the_zone(self):
        """Ждущие задачи внешнего проекта стоят в очереди своей зоны.

        Несколько прогонов: держатель внешнего проекта занял путь, N задач
        того же проекта в `in_dev` ждут его (N от зерна). Параллельно в
        другом проекте тот же путь держит своя задача, и её ждёт своя
        задача. Позиции ждущих внешнего проекта — ровно 1..N, общее число —
        N: ждущий чужого проекта в очередь не входит.

        Ловит мутацию: `queue_position` по-прежнему отбирает конкурентов
        только артели — ждущие внешнего проекта получали бы позицию 0 из
        0; либо проект конкурента не сверяется вовсе — ждущий чужого
        проекта раздувал бы очередь до N+1."""
        for _ in range(3):
            project = self.rng.choice(EXTERNAL_PROJECTS)
            foreign_project = self.other_project(project)
            path = self.fresh_path()
            self.holder(path, project)
            self.holder(path, foreign_project)
            self.insert("in_dev", path, foreign_project)
            count = self.rng.randint(2, 4)
            waiters = [self.insert("in_dev", self.zone_of(path), project)
                       for _ in range(count)]

            places = [zone_lock.queue_position(self.conn, w, path)
                      for w in waiters]

            self.assertEqual(sorted(p for p, _ in places),
                             list(range(1, count + 1)),
                             self.note(f"{project}, {path}: {places}"))
            self.assertEqual({t for _, t in places}, {count},
                             self.note(f"{project}, {path}: {places}"))


class NewWarnsWithinProjectTest(ProjectZoneLockSandbox):

    def run_new(self, project: str, path: str) -> tuple[str, str]:
        tz_file = self.root / f"TZ-{self.rng.randrange(1 << 20)}.md"
        tz_file.write_text(
            f"Источник: фикстура {self.seed}.\n\nТребуется:\n"
            f"1. Поправить модуль.\n\nЗоны: {path}.\n", encoding="utf-8")
        new = functools.partial(catalog.cmd_new, target=project)
        return capture_new_task_id(new, "Фикстура пересечения", str(tz_file))

    def overlap_details(self, task_id: str) -> list[str]:
        return [r["detail"] for r in store.task_steps(self.conn, task_id)
                if r["action"] == catalog.ZONE_OVERLAP_ACTION]

    def test_ac1_new_of_external_task_journals_zone_overlap(self):
        """`new` задачи внешнего проекта предупреждает о пересечении зон.

        Несколько прогонов: в проекте лежит задача (состояние — любое из
        `zone_lock.FORECAST_STATES`) с зоной, пересекающейся с путём ТЗ;
        в другом проекте тот же путь держит своя задача. `new --tz`
        заводит задачу проекта, в её журнале — запись о пересечении зон с
        id задачи того же проекта и без id задачи чужого.

        Ловит мутацию: в `_warn_zone_overlap` осталась отсечка задач
        не-`DEFAULT_TARGET` (или прогноз сверяет только с задачами артели)
        — записи журнала нет; либо прогноз не сверяет проект — в запись
        попадает задача чужого проекта."""
        project = self.rng.choice(EXTERNAL_PROJECTS)
        make_project_repo(project)
        for _ in range(2):
            path = self.fresh_path()
            state = self.rng.choice(zone_lock.FORECAST_STATES)
            same = self.insert(state, self.zone_of(path), project)
            foreign = self.insert("in_dev", path, self.other_project(project))

            out, task_id = self.run_new(project, path)

            self.assertTrue(store.task_exists(self.conn, task_id),
                            self.note(out))
            details = self.overlap_details(task_id)
            self.assertEqual(len(details), 1, self.note(f"{details}\n{out}"))
            self.assertIn(same, details[0], self.note(f"{state}: {details}"))
            self.assertNotIn(foreign, details[0], self.note(f"{details}"))


class StatusZoneTakenWithinProjectTest(ProjectZoneLockSandbox):

    def status_line(self, out: str, task_id: str) -> str:
        lines = [ln for ln in out.splitlines() if ln.startswith(task_id)]
        self.assertEqual(len(lines), 1, self.note(out))
        return lines[0]

    def test_ac1_status_marks_external_task_before_in_dev_as_zone_taken(self):
        """`status` помечает задачу внешнего проекта до `in_dev` «зона занята».

        Несколько прогонов: держатель проекта (любое из
        `zone_lock.BLOCKING_STATES`) с зоной, пересекающейся с зоной задачи
        того же проекта в одном из `zone_lock.LATER_STATES`; в другом
        проекте тот же путь держит своя задача. Строка ждущей в `status`
        несёт «зона занята» с id держателя своего проекта и без id чужого.

        Ловит мутацию: в `_zone_forecast_suffix` осталась отсечка задач
        не-`DEFAULT_TARGET` — строка внешней задачи шла бы без добавки;
        либо прогноз не сверяет проект — добавка называла бы задачу чужого
        проекта."""
        cases = []
        for _ in range(3):
            project = self.rng.choice(EXTERNAL_PROJECTS)
            path = self.fresh_path()
            occupier = self.insert(self.rng.choice(zone_lock.BLOCKING_STATES),
                                   self.zone_of(path), project)
            foreign = self.insert(self.rng.choice(zone_lock.BLOCKING_STATES),
                                  path, self.other_project(project))
            waiter = self.insert(self.rng.choice(zone_lock.LATER_STATES),
                                 self.zone_of(path), project)
            cases.append((waiter, occupier, foreign))

        out = capture(catalog.cmd_status)

        for waiter, occupier, foreign in cases:
            line = self.status_line(out, waiter)
            self.assertIn(ZONE_TAKEN, line, self.note(line))
            suffix = line[line.index(ZONE_TAKEN):]
            self.assertIn(occupier, suffix, self.note(line))
            self.assertNotIn(foreign, suffix, self.note(line))


if __name__ == "__main__":
    unittest.main()
