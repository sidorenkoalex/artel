"""Чекпоинт шага test_author отбирает и коммитит долгоживущие файлы по профилю проекта задачи.

Группа: долгоживущий
Красен до реализации: чекпоинт берёт каталог и шаблон долгоживущих файлов артели по умолчанию (`tests/`, `test_<id>_<name>.py`) — файл учебного проекта в `backend/tests/` откатывается как чужой, а `tests/test_<id>_<имя>.py` в корне коммитится; запись о неотобранных своих файлах называет `tests/`; при отказе профиля и у проекта без профиля файл `tests/…` коммитится как свой; AC-1 (артель) держит сегодняшнее поведение и зелён с рождения.

Связка «чекпоинт — профиль проекта (`targets.yaml`) — настоящий git
рабочей копии задачи»: задача заводится в БД песочницы, её рабочую копию
заводит сам пульт (`workspace.ensure`) в клоне проекта с bare `origin`
(`tests.sandbox.RealGitSandbox`, `tests.sandbox.make_project_repo`), роль
изображается правкой файлов рабочей копии, затем зовётся публичный
`checkpoint.commit_success_checkpoint(conn, задача, "test_author")` — тот же,
что пульт зовёт по завершении шага. Наблюдение — дерево HEAD ветки задачи,
содержимое рабочей копии и журнал задачи (`store.task_steps`).

Учебный внешний проект — профиль с `long_lived_dir: backend/tests` (вне
корня). Отказ профиля (`project_profile.Decision.refusal`) — артель без
поля `test_profile`; пропуск (`Decision.skip`) — внешний проект без него.
Идентификаторы задач, имена проектов и файлов — из `random`; зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
отбор, сверка с базой, право удаления и текст записи — по профилю задачи,
своя зона — собственные отобранные файлы; все методы зелёные. Стаб без
своей зоны в зонном фильтре даёт красный AC-4.
"""
import random
import re
import unittest

from orchestrator import (catalog, checkpoint, config, project_profile, store,
                          workspace)
from tests.sandbox import RealGitSandbox, capture, make_project_repo

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
LLD = "backend/tests"
COMMITTED_ACTION = "долгоживущие тесты закоммичены пультом за роль"
# `tests/`, не входящий в более длинный путь (`backend/tests/`).
BARE_TESTS = re.compile(r"(?<![\w/])tests/")

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: {lld}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{lld}/**/*.py]
      mutation_claim_scope: [{lld}/test_*.py]
      report: junit-xml
      install: []
"""


def entry(name: str, lld: str | None) -> str:
    text = ENTRY.format(name=name, base=config.MAIN_BRANCH)
    return text + (PROFILE.format(lld=lld) if lld is not None else "")


class ProfileCheckpointSandbox(RealGitSandbox):
    """Артель и учебный внешний проект; профили — по сценарию."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.add_synced_origin()
        self.ext = f"sled{self.word()}"

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def task_id(self) -> str:
        return "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))

    def declare(self, artel_profile: bool = True,
                ext_lld: str | None = LLD) -> None:
        """`targets.yaml` песочницы: артель (с профилем артели либо без
        поля `test_profile`) и учебный проект (`ext_lld=None` — без
        профиля), затем клон учебного проекта и `init`."""
        config.TARGETS.write_text(
            "targets:\n" + entry(ARTEL, "tests" if artel_profile else None)
            + entry(self.ext, ext_lld), encoding="utf-8")
        self.ext_clone = make_project_repo(self.ext)
        capture(catalog.cmd_init)

    def clone(self, target: str):
        return self.root if target == ARTEL else self.ext_clone

    def commit_to_main(self, target: str, files: dict) -> None:
        clone = self.clone(target)
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы базы")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def new_task(self, target: str, zones: str, task_id: str | None = None):
        task_id = task_id or self.task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          branch, target, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=zones)
        wt, error = workspace.ensure(task_id, branch, target)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        return task_id, wt

    def write(self, wt, files: dict) -> None:
        for rel, text in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def checkpoint(self, task_id: str) -> int:
        """Чекпоинт шага test_author; возврат — id последней записи
        журнала до вызова (граница «новых» записей)."""
        before = [row["id"] for row in store.task_steps(self.conn, task_id)]
        checkpoint.commit_success_checkpoint(self.conn, task_id, "test_author")
        return max(before, default=0)

    def new_steps(self, task_id: str, after: int) -> list:
        return [row for row in store.task_steps(self.conn, task_id)
                if row["id"] > after]

    def head_files(self, wt) -> set:
        return set(self.git("-C", str(wt), "ls-tree", "-r", "--name-only",
                            "HEAD").split())

    def head_text(self, wt, rel: str) -> str:
        return self.git("-C", str(wt), "show", f"HEAD:{rel}")

    def own(self, task_id: str, directory: str) -> str:
        return f"{directory}/test_{task_id.lower()}_{self.word()}.py"


class Ac1ArtelCheckpointUnchangedTest(ProfileCheckpointSandbox):

    def test_ac1_artel_commits_own_file_and_discards_out_of_mandate(self):
        """Артель с профилем артели: свой `tests/test_<id>_<имя>.py` коммитится, прочее откатывается.

        База ветки несёт `app_<слово>.py`; роль пишет свой новый
        долгоживущий файл и правит файл базы. После чекпоинта свой файл —
        в HEAD ветки задачи с текстом роли, файл базы в HEAD и на диске —
        прежний, в журнале — запись «долгоживущие тесты закоммичены
        пультом за роль». Несколько случайных задач.

        Ловит мутацию: подстановка профиля сломала путь артели (каталог
        профиля склеен с префиксом без `/`, или отбор идёт по
        `long_lived_dir` внешнего проекта по умолчанию) — свой файл артели
        не попадёт в HEAD, либо правка файла базы окажется закоммиченной.
        """
        self.declare()
        base_rel = f"app_{self.word()}.py"
        self.commit_to_main(ARTEL, {base_rel: "VALUE = 1\n"})
        for _ in range(2):
            task_id, wt = self.new_task(ARTEL, "orchestrator/, tests/")
            own = self.own(task_id, "tests")
            text = f"# свой {self.word()}\n"
            self.write(wt, {own: text, base_rel: "VALUE = 2\n"})
            after = self.checkpoint(task_id)
            with self.subTest(file=own):
                self.assertIn(own, self.head_files(wt),
                              self.note(f"свой файл артели {own} не закоммичен"))
                self.assertEqual(self.head_text(wt, own), text, self.note(own))
                self.assertEqual(self.head_text(wt, base_rel), "VALUE = 1\n",
                                 self.note("правка файла базы закоммичена"))
                self.assertEqual((wt / base_rel).read_text(encoding="utf-8"),
                                 "VALUE = 1\n",
                                 self.note("правка вне мандата не откачена"))
                actions = [r["action"] for r in self.new_steps(task_id, after)]
                self.assertIn(COMMITTED_ACTION, actions, self.note(str(actions)))


class Ac3ExternalCheckpointByProfileTest(ProfileCheckpointSandbox):

    def test_ac3_own_file_in_profile_dir_committed_root_file_discarded(self):
        """Учебный проект с `backend/tests`: свой файл там коммитится, файл в корневом `tests/` и правка файла базы откатываются.

        База ветки несёт `backend/tests/test_<id>_<слово>.py` с префиксом
        задачи. Роль пишет новый `backend/tests/test_<id>_<имя>.py`,
        `tests/test_<id>_<имя>.py` в корне и правит файл базы. После
        чекпоинта: свой файл — в HEAD с текстом роли; корневого файла нет
        ни в HEAD, ни на диске; файл базы в HEAD и на диске — прежний.

        Ловит мутацию: отбор кандидатов чекпоинта по-прежнему идёт по
        `tests/` артели — свой файл `backend/tests/…` откатится и не
        попадёт в HEAD, а корневой `tests/test_<id>_…` закоммитится; либо
        сверка с базой ветки смотрит дерево базы под `tests/`, а не под
        `backend/tests/` — правка файла базы с префиксом задачи будет
        принята за новый свой файл и закоммичена.
        """
        self.declare()
        task_id = self.task_id()
        base_rel = self.own(task_id, LLD)
        self.commit_to_main(self.ext, {base_rel: "# база\n"})
        task_id, wt = self.new_task(self.ext, f"backend/src/, {LLD}/", task_id)
        own = self.own(task_id, LLD)
        root = self.own(task_id, "tests")
        text = f"# свой {self.word()}\n"
        self.write(wt, {own: text, root: "# не по профилю\n",
                        base_rel: "# правка базы\n"})
        self.checkpoint(task_id)
        head = self.head_files(wt)
        self.assertIn(own, head, self.note(f"свой файл {own} не закоммичен"))
        self.assertEqual(self.head_text(wt, own), text, self.note(own))
        self.assertNotIn(root, head, self.note(f"{root} закоммичен"))
        self.assertFalse((wt / root).exists(),
                         self.note(f"{root} не откачен с диска"))
        self.assertEqual(self.head_text(wt, base_rel), "# база\n",
                         self.note("правка файла базы закоммичена"))
        self.assertEqual((wt / base_rel).read_text(encoding="utf-8"),
                         "# база\n", self.note("правка файла базы не откачена"))

    def test_ac3_deleting_own_committed_file_reaches_branch(self):
        """Учебный проект: удаление своего уже закоммиченного файла `backend/tests/…` доезжает до ветки.

        Первый чекпоинт коммитит свой новый файл; роль удаляет его в той же
        `tests_writing`; второй чекпоинт обязан закоммитить удаление — в
        HEAD файла нет и на диске он не восстановлен.

        Ловит мутацию: право удаления своих файлов (`restore_out_of_bounds_
        deletions`) по-прежнему считает своим только `tests/test_<id>_…` —
        удалённый `backend/tests/…` восстановится из HEAD и останется в
        ветке.
        """
        self.declare()
        task_id, wt = self.new_task(self.ext, f"backend/src/, {LLD}/")
        own = self.own(task_id, LLD)
        self.write(wt, {own: "# свой\n"})
        self.checkpoint(task_id)
        self.assertIn(own, self.head_files(wt),
                      self.note("первый чекпоинт не закоммитил свой файл"))
        (wt / own).unlink()
        self.checkpoint(task_id)
        self.assertNotIn(own, self.head_files(wt),
                         self.note("удаление своего файла не доехало до ветки"))
        self.assertFalse((wt / own).exists(),
                         self.note("удалённый свой файл восстановлен"))

    def test_ac3_not_selected_record_names_profile_dir(self):
        """Учебный проект: запись о неотобранных своих файлах называет `backend/tests/`, не `tests/`.

        Роль пишет свой файл, затем индекс рабочей копии портится — git не
        отвечает на её статус, и чекпоинт не может отобрать свои файлы.
        Новая запись журнала `checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION`
        обязана назвать каталог `backend/tests/` и не называть голый
        `tests/`. Несколько случайных задач.

        Ловит мутацию: текст записи по-прежнему собран литералом «свои
        файлы tests/» — каталог профиля в записи не появится.
        """
        self.declare()
        for _ in range(2):
            task_id, wt = self.new_task(self.ext, f"backend/src/, {LLD}/")
            self.write(wt, {self.own(task_id, LLD): "# свой\n"})
            index = self.git("-C", str(wt), "rev-parse", "--path-format=absolute",
                             "--git-path", "index").strip()
            with open(index, "wb") as fh:
                fh.write(b"not an index")
            after = self.checkpoint(task_id)
            details = [r["detail"] or "" for r in self.new_steps(task_id, after)
                       if r["action"] == checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION]
            with self.subTest(task=task_id):
                self.assertTrue(details, self.note("записи о неотобранных нет"))
                for detail in details:
                    self.assertIn(f"{LLD}/", detail, self.note(detail))
                    self.assertIsNone(BARE_TESTS.search(detail),
                                      self.note(f"запись называет tests/: {detail}"))


class Ac4ZonesOutsideProfileDirTest(ProfileCheckpointSandbox):

    def test_ac4_own_file_committed_foreign_discarded_zones_outside(self):
        """Учебная задача с зонами только `backend/src/`: свой файл `backend/tests/…` коммитится, чужой там же откатывается.

        Роль пишет свой `backend/tests/test_<id>_<имя>.py` и чужой
        `backend/tests/test_<слово>.py` (без префикса задачи). После
        чекпоинта свой — в HEAD, чужого нет ни в HEAD, ни на диске;
        `config.COMMON_ZONES` до и после вызова одинаков и не несёт
        каталога профиля. Несколько случайных задач.

        Ловит мутацию: зонный фильтр коммита пульта не считает своим
        долгоживущий файл профиля — `backend/tests/…` вне зон снимется со
        стейджа и не попадёт в HEAD; либо отбор своих признаёт любой
        файл каталога профиля, а не только с префиксом задачи — чужой
        файл закоммитится; либо каталог профиля дописан в
        `config.COMMON_ZONES` — проверка `COMMON_ZONES` покраснеет.
        """
        self.declare()
        common = tuple(config.COMMON_ZONES)
        for _ in range(2):
            task_id, wt = self.new_task(self.ext, "backend/src/")
            own = self.own(task_id, LLD)
            foreign = f"{LLD}/test_{self.word()}.py"
            self.write(wt, {own: "# свой\n", foreign: "# чужой\n"})
            self.checkpoint(task_id)
            head = self.head_files(wt)
            with self.subTest(file=own):
                self.assertIn(own, head, self.note(f"{own} не закоммичен"))
                self.assertNotIn(foreign, head,
                                 self.note(f"чужой {foreign} закоммичен"))
                self.assertFalse((wt / foreign).exists(),
                                 self.note(f"чужой {foreign} не откачен"))
        self.assertEqual(tuple(config.COMMON_ZONES), common,
                         self.note("config.COMMON_ZONES изменён вызовом"))
        self.assertFalse(any(z.startswith("backend") for z in config.COMMON_ZONES),
                         self.note(f"COMMON_ZONES: {config.COMMON_ZONES}"))


class Ac6RefusalCheckpointTest(ProfileCheckpointSandbox):

    def test_ac6_refusal_no_commit_and_journal_reason(self):
        """Отказ профиля (артель без `test_profile`): свой файл не коммитится, журнал называет причину.

        Роль пишет `tests/test_<id>_<имя>.py` — по умолчаниям артели свой.
        После чекпоинта его нет в HEAD, записи «долгоживущие тесты
        закоммичены пультом за роль» нет, а среди новых записей журнала
        есть запись с причиной отказа — текстом `project_profile.decide(
        артель).refusal`.

        Ловит мутацию: при `Decision.refusal` чекпоинт откатывается к
        умолчаниям артели (`tests/`, `test_<id>_<name>.py`) — файл
        закоммитится; либо отказ обработан молча — записи с причиной нет.
        """
        self.declare(artel_profile=False)
        decision = project_profile.decide(ARTEL)
        self.assertTrue(decision.refusal, self.note("сценарий не дал отказа"))
        task_id, wt = self.new_task(ARTEL, "orchestrator/, tests/")
        own = self.own(task_id, "tests")
        self.write(wt, {own: "# свой\n"})
        after = self.checkpoint(task_id)
        self.assertNotIn(own, self.head_files(wt),
                         self.note("при отказе профиля файл закоммичен"))
        steps = self.new_steps(task_id, after)
        self.assertNotIn(COMMITTED_ACTION, [r["action"] for r in steps])
        texts = [f"{r['action']} {r['detail'] or ''}" for r in steps]
        self.assertTrue(any(decision.refusal in t for t in texts),
                        self.note(f"нет записи с причиной отказа: {texts}"))


class Ac7SkipCheckpointTest(ProfileCheckpointSandbox):

    def test_ac7_skip_selects_nothing(self):
        """Учебный проект без `test_profile`: `tests/test_<id>_<имя>.py` своим не отбирается.

        Роль пишет файл по умолчаниям артели; после чекпоинта его нет в
        HEAD и записи «долгоживущие тесты закоммичены пультом за роль» нет.
        Несколько случайных задач.

        Ловит мутацию: при `Decision.skip` чекпоинт подставляет умолчания
        артели — файл отберётся своим и закоммитится.
        """
        self.declare(ext_lld=None)
        for _ in range(2):
            task_id, wt = self.new_task(self.ext, "backend/src/, tests/")
            own = self.own(task_id, "tests")
            self.write(wt, {own: "# по умолчаниям артели\n"})
            after = self.checkpoint(task_id)
            with self.subTest(file=own):
                self.assertNotIn(own, self.head_files(wt),
                                 self.note(f"{own} отобран своим и закоммичен"))
                self.assertNotIn(COMMITTED_ACTION,
                                 [r["action"] for r in self.new_steps(task_id, after)])


if __name__ == "__main__":
    unittest.main()
