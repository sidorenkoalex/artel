"""Мандаты ослабления у записи из нескольких компонентов: элемент и идентификатор годны для компонента записи в границе гейта исходов, матрица засчитывает его ссылку покрытием.

Группа: долгоживущий
Красен до реализации: проверки мандата идут по единственному профилю задачи — у задачи на `backend` элемент «Ослабление тестов разрешено:» на путь `frontend` получает «путь вне области backend/tests/**…», идентификатор `frontend:…` — «компонента «frontend» нет в записи components: проекта», ссылка `frontend:…`/путь области `frontend` в ячейке «Чем покрыто после» не засчитывается («свойство остаётся и не покрыто»); у записи из нескольких компонентов `for_task` и вовсе отказывает (`decide` без зон).

Свойство проверок мандата — те же узлы, что зовёт команда `answer`
(`mandate.refusals` по строкам мандата и `mandate.matrix_refusals` по
матрице неослабления), с настоящим `project_profile.for_task` по строке
задачи. Стенд — `tests.sandbox.TaskIdSchemaConnTmpRootTest`: `targets.yaml`
песочницы с учебной записью из двух компонентов (`backend` — `junit-xml`
с pytest, `frontend` — `pult-vitest`, `depends_on` вида `files` на
`backend/seed/`) и её вариантом, где у `frontend` нет поля `report` (вне
границы гейта исходов); задача — строка БД с зонами в `backend`.

Имена файлов и тестов — из `random`; зерно печатается и входит в текст
каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`for_task` по зонам задачи и проверки мандата по компоненту находки из
компонентов записи в границе гейта исходов — все методы файла зелёные.
"""
import random
import string

from orchestrator import config, project_profile, store
from orchestrator.advance_gates import mandate
from tests.sandbox import TaskIdSchemaConnTmpRootTest, make_project_repo

WEAKENING = mandate.TEST_WEAKENING_MANDATE_MARKER
BY_ID = mandate.TEST_ID_MANDATE_MARKER
OUT_OF_AREA = "гейт неослабления тестов другие пути не рассматривает"
NOT_IN_RECORD = "нет в записи components: проекта"
ID_OUT_OF_BOUNDS = ("мандат по идентификатору действует только у компонента "
                    "записи components: с полем report")
NOT_COVERED = "свойство остаётся и не покрыто"
HEADERS = ("Что меняется",
           "Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка)",
           "Остаётся ли свойство после изменения",
           "Чем покрыто после (тест файл:строка) или «не покрыто»",
           "Решение")

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    components:
      backend:
        command: [python3, -m, pytest]
        report: junit-xml
        long_lived_dir: backend/tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [backend/tests/**]
        mutation_claim_scope: [backend/tests/test_*.py]
        failure_errors: [AssertionError]
        tests: [backend/tests/**/test_*.py]
        paths: [^backend/]
      frontend:
        command: [node_modules/.bin/vitest, run, --config, vitest.config.js, --allowOnly=false, --update=false, --retry=0]
{report}        tests: [frontend/src/**/*.test.jsx]
        long_lived: frontend/src/<dir>/<name>.<id>.test.jsx
        weakening_scope: [frontend/src/**]
        mutation_claim_scope: [frontend/claims/**]
        paths: [^frontend/]
        depends_on:
          backend:
            via: files
            paths: [^backend/seed/]
"""
FRONTEND_REPORT = "        report: pult-vitest\n        failure_errors: [AssertionError]\n"


def matrix(elements, remains: str, covered: str) -> str:
    row = (", ".join(f"`{e}`" for e in elements),
           "находка гейта исходов — сломан правкой", remains, covered, "ок")
    return ("## Матрица неослабления\n\n"
            "| " + " | ".join(HEADERS) + " |\n"
            + "|" + "---|" * len(HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")


class MandateComponentsSandbox(TaskIdSchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(string.ascii_lowercase)
                       for _ in range(size))

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def project(self, frontend_report: bool = True) -> str:
        name = f"uch{self.word()}"
        text = config.TARGETS.read_text(encoding="utf-8")
        entry = HEAD.format(name=name,
                            report=FRONTEND_REPORT if frontend_report else "")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + entry,
                                  encoding="utf-8")
        make_project_repo(name, origin=False)
        return name

    def backend_task(self, target: str) -> str:
        task_id = "01" + "".join(self.rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                                 for _ in range(24))
        store.insert_task(self.conn, task_id, "Задача на backend", "in_dev",
                          f"task/{task_id.lower()}-b", target, 25.0)
        store.update_task(self.conn, task_id,
                          zones=f"backend/{self.word()}.py, backend/seed/")
        return task_id

    def frontend_path(self) -> str:
        return f"frontend/src/{self.word()}/{self.word()}.test.jsx"

    def frontend_id(self) -> str:
        return project_profile.test_id("frontend", self.frontend_path(),
                                       f"кнопка {self.word()}")

    def refusals(self, text: str, task_id: str) -> list:
        return mandate.refusals(text, None, conn=self.conn, task_id=task_id)


class Ac13WeakeningElementTest(MandateComponentsSandbox):

    def test_ac13_frontend_path_element_accepted_on_backend_task(self):
        """Элемент «Ослабление тестов разрешено:» на путь области `frontend` у задачи на `backend`: ни отказа «путь вне области», ни «свойство остаётся и не покрыто» при ссылке `frontend:…` или пути области `frontend`.

        Сценарий: несколько случайных путей тестов `frontend/src/…`;
        строка мандата проверяется `mandate.refusals`, матрица с
        «остаётся» и ячейкой «Чем покрыто после» — идентификатор
        `frontend:…` либо путь файла области `frontend` —
        `mandate.matrix_refusals`.

        Ловит мутацию: область элемента — только профиль компонента
        задачи (`backend`) — отказ «путь вне области backend/tests/**»;
        покрытие ячейки по профилю задачи — «свойство остаётся и не
        покрыто».
        """
        target = self.project()
        task_id = self.backend_task(target)
        for _ in range(3):
            path = self.frontend_path()
            got = self.refusals(f"{WEAKENING} {path}\n", task_id)
            self.assertEqual(got, [], self.note(f"элемент {path}: {got}"))
            for covered in (f"`{self.frontend_id()}`", self.frontend_path()):
                text = matrix([path], "остаётся", covered)
                got = mandate.matrix_refusals(text, [path], conn=self.conn,
                                              task_id=task_id)
                self.assertFalse([r for r in got if NOT_COVERED in r],
                                 self.note(f"ячейка {covered}: {got}"))

    def test_ac13_out_of_bounds_component_path_refused(self):
        """Компонент находки вне границы гейта исходов (`frontend` без `report`): элемент на путь `frontend` не годен — отказ «путь вне области … другие пути не рассматривает».

        Ловит мутацию: годность элемента по любому компоненту записи без
        условия `in_outcome_bounds` — элемент на путь компонента вне
        границы принят.
        """
        target = self.project(frontend_report=False)
        task_id = self.backend_task(target)
        for _ in range(3):
            path = self.frontend_path()
            got = self.refusals(f"{WEAKENING} {path}\n", task_id)
            self.assertEqual(len(got), 1, self.note(str(got)))
            self.assertIn(path, got[0], self.note(got[0]))
            self.assertIn("путь вне области", got[0], self.note(got[0]))
            self.assertIn(OUT_OF_AREA, got[0], self.note(got[0]))


class Ac14TestIdElementTest(MandateComponentsSandbox):

    def test_ac14_frontend_id_accepted_on_backend_task(self):
        """Идентификатор `frontend:…` в «Ослабление теста по идентификатору разрешено:» у задачи на `backend` годен, матрица «остаётся, покрыто `frontend:…`» без отказа.

        Ловит мутацию: компонент идентификатора сверяется с компонентом
        профиля задачи — «компонента «frontend» нет в записи components:
        проекта (компонент профиля — «backend»)»; покрытие ячейки по
        профилю задачи — «свойство остаётся и не покрыто».
        """
        target = self.project()
        task_id = self.backend_task(target)
        for _ in range(3):
            cid = self.frontend_id()
            got = self.refusals(f"{BY_ID} {cid}\n", task_id)
            self.assertEqual(got, [], self.note(f"{cid}: {got}"))
            self.assertFalse([r for r in got if NOT_IN_RECORD in r])
            text = matrix([cid], "остаётся", f"покрыто `{self.frontend_id()}`")
            got = mandate.matrix_refusals(text, [], conn=self.conn,
                                          task_id=task_id, test_ids=[cid])
            self.assertFalse([r for r in got if NOT_COVERED in r],
                             self.note(f"{cid}: {got}"))

    def test_ac14_unknown_and_out_of_bounds_components_refused(self):
        """Идентификатор компонента, которого нет в записи, — прежний отказ «… нет в записи components: проекта»; компонента записи вне границы — отказ «мандат по идентификатору действует только у компонента записи components: с полем report».

        Ловит мутацию: идентификатор любого компонента принят (проверка
        «есть в записи» снята); компонент вне границы гейта исходов
        принят без условия `report`.
        """
        target = self.project()
        task_id = self.backend_task(target)
        stranger = f"web{self.word(3)}"
        cid = project_profile.test_id(stranger, self.frontend_path(), "случай")
        got = self.refusals(f"{BY_ID} {cid}\n", task_id)
        self.assertEqual(len(got), 1, self.note(str(got)))
        self.assertIn(f"компонента «{stranger}» {NOT_IN_RECORD}", got[0])
        target = self.project(frontend_report=False)
        task_id = self.backend_task(target)
        cid = self.frontend_id()
        got = self.refusals(f"{BY_ID} {cid}\n", task_id)
        self.assertEqual(len(got), 1, self.note(str(got)))
        self.assertIn(ID_OUT_OF_BOUNDS, got[0], self.note(got[0]))
        self.assertNotIn(NOT_IN_RECORD, got[0], self.note(got[0]))
