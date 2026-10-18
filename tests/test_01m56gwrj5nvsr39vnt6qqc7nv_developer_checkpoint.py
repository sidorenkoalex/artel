"""Чекпоинты developer считают своими долгоживущие файлы задачи по профилю проекта.

Группа: долгоживущий
Красен до реализации: зоны чекпоинтов developer — только заявленные зоны, `config.COMMON_ZONES` и каталог задачи, поэтому `backend/tests/test_<id>_<имя>.py` внешнего проекта снимается со стейджа (AC-1, AC-2), отменяет подтяжку (AC-3), выпадает из `pult_commit_failed_paths` (AC-4) и восстанавливается после удаления (AC-5); `git diff --cached --name-only` с распознаванием переименований прячет источник `git mv` — удаление уходит в коммит пульта, а запись о посторонних называет назначение (AC-9); AC-6 и AC-7 держат сегодняшнее поведение и зелены с рождения.

Связка «чекпоинт developer — профиль проекта (`targets.yaml`) — настоящий
git рабочей копии задачи»: задача заводится в БД песочницы в `in_dev`, её
рабочую копию заводит сам пульт (`workspace.ensure`) в клоне проекта с bare
`origin` (`tests.sandbox.RealGitSandbox`, `tests.sandbox.make_project_repo`),
роль изображается правкой файлов рабочей копии, затем зовутся публичные
чекпоинты: аварийный WIP (`checkpoint.commit_abnormal_checkpoint`, ветка
developer общей обвязки WIP-чекпоинтов), штатный
(`checkpoint.commit_success_checkpoint`), подтяжки main
(`checkpoint.commit_pull_checkpoint`), а также
`checkpoint.pult_commit_failed_paths` и
`checkpoint.restore_out_of_bounds_deletions`. Наблюдение — дерево HEAD
ветки задачи, индекс и диск рабочей копии, журнал задачи
(`store.task_steps`), возврат функций.

Учебный внешний проект — профиль с `long_lived_dir: backend/tests`, задача
с зонами `backend/src/`. Пропуск профиля (`Decision.skip`) — запись проекта
без `test_profile`; отказ (`Decision.refusal`) — испорченный `test_profile`
(вариант порчи случаен). Идентификаторы задач, имена проекта и файлов — из
`random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен): зоны
чекпоинта developer дополняются путями, для которых
`project_profile.for_task(...).profile.is_long_lived` истинно, в фильтре
коммита, в `pult_commit_failed_paths` и в праве удаления developer;
`_stray_staged_paths` читает индекс с `--no-renames`. Под ним зелены все
методы файла.
"""
import random
import unittest

from orchestrator import (catalog, checkpoint, config, project_profile, store,
                          workspace)
from tests.sandbox import RealGitSandbox, capture, make_project_repo

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
LLD = "backend/tests"
EXT_ZONES = "backend/src/"
ARTEL_ZONES = "orchestrator/checkpoint.py"
OTHER = f"{LLD}/test_other.py"

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

# Порча профиля внешнего проекта — `project_profile.decide` даёт `refusal`.
BROKEN_PROFILES = (
    PROFILE.replace("      report: junit-xml\n", "      report: tap\n"),
    PROFILE.replace("      command: [python3, -m, pytest]\n", ""),
    PROFILE.replace("test_<id>_<name>.py", "test_<name>.py"),
)


def entry(name: str, profile: str) -> str:
    return ENTRY.format(name=name, base=config.MAIN_BRANCH) + profile


class DeveloperCheckpointSandbox(RealGitSandbox):
    """Артель (с профилем артели) и учебный внешний проект."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.add_synced_origin()
        self.ext = f"sled{self.word()}"
        self.ext_clone = None

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def task_id(self) -> str:
        return "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))

    def write_targets(self, ext_profile: str) -> None:
        config.TARGETS.write_text(
            "targets:\n" + entry(ARTEL, PROFILE.format(lld="tests"))
            + entry(self.ext, ext_profile), encoding="utf-8")

    def declare(self) -> None:
        """`targets.yaml` песочницы с профилями обоих проектов, клон
        учебного проекта и `init`."""
        self.write_targets(PROFILE.format(lld=LLD))
        self.ext_clone = make_project_repo(self.ext)
        capture(catalog.cmd_init)

    def clone(self, target: str):
        return self.root if target == ARTEL else self.ext_clone

    def commit_to_main(self, target: str, files: dict) -> None:
        clone = self.clone(target)
        self.write(clone, files)
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы базы")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def new_task(self, target: str, zones: str, task_id: str | None = None):
        task_id = task_id or self.task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "in_dev",
                          branch, target, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=zones)
        wt, error = workspace.ensure(task_id, branch, target)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        return task_id, wt

    def write(self, root, files: dict) -> None:
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def own(self, task_id: str, directory: str = LLD, ext: str = "py") -> str:
        return f"{directory}/test_{task_id.lower()}_{self.word()}.{ext}"

    # ----------------------------------------------------------- чекпоинты

    def wip(self, task_id: str, wt) -> None:
        checkpoint.commit_abnormal_checkpoint(self.conn, task_id, "developer",
                                              "rc=1")

    def success(self, task_id: str, wt) -> None:
        checkpoint.commit_success_checkpoint(self.conn, task_id, "developer")

    def pull(self, task_id: str, wt) -> None:
        checkpoint.commit_pull_checkpoint(self.conn, task_id, wt)

    def paths_of_ac1(self):
        """Оба пути AC-1: аварийный WIP-чекпоинт developer и штатный."""
        return (("аварийный WIP-чекпоинт", self.wip),
                ("commit_success_checkpoint", self.success))

    def run_checkpoint(self, fn, task_id: str, wt) -> int:
        """Чекпоинт; возврат — id последней записи журнала до вызова."""
        before = [row["id"] for row in store.task_steps(self.conn, task_id)]
        fn(task_id, wt)
        return max(before, default=0)

    def new_steps(self, task_id: str, after: int) -> list:
        return [row for row in store.task_steps(self.conn, task_id)
                if row["id"] > after]

    def stray_details(self, task_id: str, after: int) -> list:
        return [row["detail"] or "" for row in self.new_steps(task_id, after)
                if row["action"] == checkpoint.STRAY_WORKTREE_FILES_ACTION]

    # ----------------------------------------------------------- наблюдение

    def head_files(self, wt) -> set:
        return set(self.git("-C", str(wt), "ls-tree", "-r", "--name-only",
                            "HEAD").split())

    def head_sha(self, wt) -> str:
        return self.git("-C", str(wt), "rev-parse", "HEAD").strip()

    def index_files(self, wt) -> set:
        return set(self.git("-C", str(wt), "ls-files").split())

    def status(self, wt, rel: str) -> str:
        return self.git("-C", str(wt), "status", "--porcelain=v1",
                        "--untracked-files=all", "--", rel).strip()

    def assert_committed_clean(self, wt, rel: str, where: str) -> None:
        self.assertIn(rel, self.head_files(wt),
                      self.note(f"{where}: {rel} не в коммите пульта"))
        self.assertEqual(self.status(wt, rel), "",
                         self.note(f"{where}: рабочее дерево по {rel} не чисто"))

    def assert_unstaged_not_committed(self, wt, rel: str, where: str) -> None:
        self.assertNotIn(rel, self.head_files(wt),
                         self.note(f"{where}: {rel} в коммите пульта"))
        self.assertNotIn(rel, self.index_files(wt),
                         self.note(f"{where}: {rel} не снят со стейджа"))


class Ac1OwnFileCommittedTest(DeveloperCheckpointSandbox):

    def test_ac1_own_long_lived_file_committed_by_both_checkpoints(self):
        """Свой новый `backend/tests/test_<id>_<имя>.py` коммитится аварийным WIP-чекпоинтом и штатным.

        Для каждого из двух путей — своя случайная задача внешнего проекта
        с зонами `backend/src/`; developer оставил свой долгоживущий файл
        незакоммиченным. После чекпоинта файл — в HEAD ветки задачи, а
        `git status` по нему пуст.

        Ловит мутацию: зоны чекпоинта developer не дополнены долгоживущими
        файлами задачи по профилю (или дополнены только в одном из двух
        путей) — файл снимется со стейджа как посторонний, в HEAD его не
        будет, а `git status` покажет его неотслеживаемым.
        """
        self.declare()
        for where, fn in self.paths_of_ac1():
            task_id, wt = self.new_task(self.ext, EXT_ZONES)
            own = self.own(task_id)
            self.write(wt, {own: f"# свой {self.word()}\n"})
            self.run_checkpoint(fn, task_id, wt)
            with self.subTest(path=where, file=own):
                self.assert_committed_clean(wt, own, where)


class Ac2ForeignFilesStrayTest(DeveloperCheckpointSandbox):

    def test_ac2_foreign_files_unstaged_and_named_own_committed(self):
        """Чужой `backend/tests/test_other.py` и `test_<id>_<имя>.txt` снимаются со стейджа и называются в журнале, свой `.py` коммитится.

        Для каждого из двух путей AC-1 — своя задача внешнего проекта с
        зонами `backend/src/`. developer оставил незакоммиченными свой
        `backend/tests/test_<id>_<имя>.py`, `backend/tests/test_other.py` и
        `backend/tests/test_<id>_<имя>.txt`. После чекпоинта: свой — в HEAD;
        оба чужих не в HEAD и не в индексе; новая запись
        `STRAY_WORKTREE_FILES_ACTION` называет каждый из чужих.

        Ловит мутацию: расширение зон признаёт весь каталог профиля
        `long_lived_dir` (или проверяет только префикс задачи без шаблона
        `is_long_lived`) — `test_other.py` либо `.txt` закоммитится и
        пропадёт из записи о посторонних; либо расширения нет вовсе — свой
        `.py` не попадёт в HEAD.
        """
        self.declare()
        for where, fn in self.paths_of_ac1():
            task_id, wt = self.new_task(self.ext, EXT_ZONES)
            own = self.own(task_id)
            txt = self.own(task_id, ext="txt")
            self.write(wt, {own: "# свой\n", OTHER: "# чужой\n",
                            txt: "не тест\n"})
            after = self.run_checkpoint(fn, task_id, wt)
            details = self.stray_details(task_id, after)
            with self.subTest(path=where, task=task_id):
                self.assertIn(own, self.head_files(wt),
                              self.note(f"{where}: свой {own} не закоммичен"))
                for foreign in (OTHER, txt):
                    self.assert_unstaged_not_committed(wt, foreign, where)
                    self.assertTrue(
                        any(foreign in d for d in details),
                        self.note(f"{where}: запись о посторонних не называет "
                                  f"{foreign}: {details}"))


class Ac3PullCheckpointTest(DeveloperCheckpointSandbox):

    def test_ac3_pull_commits_zone_and_own_file_without_stray_record(self):
        """Подтяжка main: `backend/src/…` и свой долгоживущий файл без иных путей вне зон коммитятся без записи о посторонних.

        Несколько случайных задач внешнего проекта с зонами `backend/src/`.

        Ловит мутацию: `commit_pull_checkpoint` зовёт фильтр без своих
        долгоживущих файлов — подтяжка откажет целиком: ни один из двух
        файлов не попадёт в HEAD, появится запись
        `STRAY_WORKTREE_FILES_ACTION` со своим файлом.
        """
        self.declare()
        for _ in range(2):
            task_id, wt = self.new_task(self.ext, EXT_ZONES)
            src = f"backend/src/m_{self.word()}.py"
            own = self.own(task_id)
            self.write(wt, {src: "VALUE = 1\n", own: "# свой\n"})
            after = self.run_checkpoint(self.pull, task_id, wt)
            with self.subTest(task=task_id):
                for rel in (src, own):
                    self.assert_committed_clean(wt, rel, "подтяжка")
                self.assertEqual(self.stray_details(task_id, after), [],
                                 self.note("запись о посторонних при подтяжке"))

    def test_ac3_pull_refuses_whole_with_foreign_file(self):
        """Подтяжка main с дополнительным `backend/tests/test_other.py` отказывает целиком.

        После чекпоинта HEAD ветки задачи не сдвинут, ни `backend/src/…`,
        ни свой файл, ни чужой не в коммите; новая запись
        `STRAY_WORKTREE_FILES_ACTION` называет `backend/tests/test_other.py`.

        Ловит мутацию: расширение зон признаёт весь каталог профиля —
        чужой файл перестанет быть посторонним, подтяжка закоммитит все
        три файла и HEAD сдвинется.
        """
        self.declare()
        task_id, wt = self.new_task(self.ext, EXT_ZONES)
        src = f"backend/src/m_{self.word()}.py"
        own = self.own(task_id)
        self.write(wt, {src: "VALUE = 1\n", own: "# свой\n", OTHER: "# чужой\n"})
        head = self.head_sha(wt)
        after = self.run_checkpoint(self.pull, task_id, wt)
        self.assertEqual(self.head_sha(wt), head,
                         self.note("подтяжка с посторонним сдвинула HEAD"))
        for rel in (src, own, OTHER):
            self.assertNotIn(rel, self.head_files(wt), self.note(rel))
        details = self.stray_details(task_id, after)
        self.assertTrue(any(OTHER in d for d in details),
                        self.note(f"запись о посторонних: {details}"))


class Ac4FailedPathsTest(DeveloperCheckpointSandbox):

    def test_ac4_failed_paths_include_own_exclude_foreign(self):
        """После записи отказа git `pult_commit_failed_paths` возвращает свой долгоживущий файл и не возвращает чужой.

        Несколько случайных задач внешнего проекта с зонами `backend/src/`:
        в журнал задачи пишется `PULT_COMMIT_GIT_FAILED_ACTION`, в рабочей
        копии незакоммиченными лежат свой `backend/tests/test_<id>_<имя>.py`
        и `backend/tests/test_other.py`.

        Ловит мутацию: `pult_commit_failed_paths` считает посторонние по
        `_zone_paths` без своих долгоживущих файлов — свой файл выпадет из
        возврата; либо расширение признаёт весь каталог профиля — в возврат
        попадёт `test_other.py`.
        """
        self.declare()
        for _ in range(2):
            task_id, wt = self.new_task(self.ext, EXT_ZONES)
            own = self.own(task_id)
            self.write(wt, {own: "# свой\n", OTHER: "# чужой\n"})
            store.journal(self.conn, task_id, "orchestrator",
                          checkpoint.PULT_COMMIT_GIT_FAILED_ACTION,
                          f"{task_id}: git commit (rc=1): учебный отказ")
            paths = checkpoint.pult_commit_failed_paths(self.conn, task_id)
            with self.subTest(task=task_id):
                self.assertIsNotNone(paths, self.note("git не ответил"))
                self.assertIn(own, paths, self.note(f"возврат: {paths}"))
                self.assertNotIn(OTHER, paths, self.note(f"возврат: {paths}"))


class Ac5RestoreDeletionsTest(DeveloperCheckpointSandbox):

    def test_ac5_own_deletion_kept_foreign_restored(self):
        """Удаление своего долгоживущего файла не восстанавливается, удаление `test_other.py` — восстанавливается из HEAD.

        База проекта несёт свой `backend/tests/test_<id>_<имя>.py` и
        `backend/tests/test_other.py`; задача с зонами `backend/src/`
        удаляет оба в рабочей копии. После
        `restore_out_of_bounds_deletions(…, "developer", …)` своего файла
        на диске нет и его нет в возврате, чужой — на диске с текстом HEAD
        и в возврате.

        Ловит мутацию: право удаления developer (`_role_may_delete`)
        считает только зоны задачи без своих долгоживущих файлов — свой
        файл восстановится на диске и войдёт в возврат; либо признаёт весь
        каталог профиля — `test_other.py` не восстановится.
        """
        self.declare()
        task_id = self.task_id()
        own = self.own(task_id)
        self.commit_to_main(self.ext, {own: "# свой\n", OTHER: "# чужой\n"})
        task_id, wt = self.new_task(self.ext, EXT_ZONES, task_id)
        (wt / own).unlink()
        (wt / OTHER).unlink()
        restored = checkpoint.restore_out_of_bounds_deletions(
            self.conn, task_id, "developer", wt)
        self.assertFalse((wt / own).exists(),
                         self.note("удаление своего файла восстановлено"))
        self.assertNotIn(own, restored, self.note(f"возврат: {restored}"))
        self.assertTrue((wt / OTHER).exists(),
                        self.note("удаление чужого файла не восстановлено"))
        self.assertEqual((wt / OTHER).read_text(encoding="utf-8"), "# чужой\n")
        self.assertIn(OTHER, restored, self.note(f"возврат: {restored}"))


class Ac6NoProfileTest(DeveloperCheckpointSandbox):

    def decision_variants(self):
        """(исход, текст профиля в записи проекта) — пропуск и отказ."""
        return (("skip", ""),
                ("refusal", self.rng.choice(BROKEN_PROFILES).format(lld=LLD)))

    def test_ac6_without_profile_zones_not_extended(self):
        """Без профиля (`skip`, `refusal`) свой `backend/tests/…` снимается со стейджа, `tests/test_<id>_<имя>.py` коммитится.

        Для каждого исхода `project_profile.decide` и каждого из двух путей
        AC-1 — своя задача внешнего проекта с зонами `backend/src/`;
        запись проекта в `targets.yaml` переписывается после заведения
        рабочей копии (без поля либо с испорченным профилем), исход
        `decide` сверяется. developer оставил незакоммиченными
        `backend/tests/test_<id>_<имя>.py` и `tests/test_<id>_<имя>.py`.
        После чекпоинта первый не в HEAD и не в индексе, второй — в HEAD
        (через `config.COMMON_ZONES`).

        Ловит мутацию: при исходе без профиля расширение зон снимает
        фильтр зон вовсе (или подставляет каталог профиля по умолчанию) —
        `backend/tests/…` закоммитится; либо отказ профиля обрывает
        чекпоинт до коммита — `tests/…` не попадёт в HEAD.
        """
        self.declare()
        for outcome, profile in self.decision_variants():
            for where, fn in self.paths_of_ac1():
                self.write_targets(PROFILE.format(lld=LLD))
                task_id, wt = self.new_task(self.ext, EXT_ZONES)
                self.write_targets(profile)
                decision = project_profile.decide(self.ext)
                self.assertIsNone(decision.profile, self.note(outcome))
                self.assertTrue(getattr(decision, outcome),
                                self.note(f"сценарий не дал исхода {outcome}"))
                ext_own = self.own(task_id)
                root_own = self.own(task_id, "tests")
                self.write(wt, {ext_own: "# по профилю\n",
                                root_own: "# общая зона\n"})
                self.run_checkpoint(fn, task_id, wt)
                with self.subTest(outcome=outcome, path=where):
                    self.assert_unstaged_not_committed(
                        wt, ext_own, f"{outcome}, {where}")
                    self.assertIn(root_own, self.head_files(wt),
                                  self.note(f"{outcome}, {where}: {root_own} "
                                            f"не закоммичен"))


class Ac7ArtelUnchangedTest(DeveloperCheckpointSandbox):

    def files(self) -> tuple[str, str]:
        return (f"tests/test_{self.word()}.py", f"docs/out_{self.word()}.md")

    def test_ac7_artel_wip_and_success_checkpoints_unchanged(self):
        """Задача артели: путь в `tests/` коммитится, путь вне зон снимается со стейджа и называется в журнале.

        Для каждого из двух путей AC-1 — своя задача артели с зонами
        `orchestrator/checkpoint.py`.

        Ловит мутацию: расширение зон по профилю у артели вытесняет
        `config.COMMON_ZONES` — путь `tests/` не закоммитится; либо у артели
        фильтр снимается — путь вне зон попадёт в HEAD.
        """
        self.declare()
        for where, fn in self.paths_of_ac1():
            task_id, wt = self.new_task(ARTEL, ARTEL_ZONES)
            common, outside = self.files()
            self.write(wt, {common: "# общая зона\n", outside: "вне зон\n"})
            after = self.run_checkpoint(fn, task_id, wt)
            with self.subTest(path=where):
                self.assert_committed_clean(wt, common, where)
                self.assert_unstaged_not_committed(wt, outside, where)
                self.assertTrue(
                    any(outside in d for d in self.stray_details(task_id, after)),
                    self.note(f"{where}: запись не называет {outside}"))

    def test_ac7_artel_pull_checkpoint_unchanged(self):
        """Задача артели, подтяжка main: путь `tests/` коммитится, с путём вне зон — отказ целиком.

        Ловит мутацию: расширение зон у артели ломает `COMMON_ZONES` в
        фильтре подтяжки — `tests/` станет посторонним и первая подтяжка
        откажет; либо фильтр снят — вторая подтяжка закоммитит путь вне
        зон.
        """
        self.declare()
        task_id, wt = self.new_task(ARTEL, ARTEL_ZONES)
        common, outside = self.files()
        self.write(wt, {common: "# общая зона\n"})
        after = self.run_checkpoint(self.pull, task_id, wt)
        self.assert_committed_clean(wt, common, "подтяжка")
        self.assertEqual(self.stray_details(task_id, after), [], self.note("запись"))

        task_id, wt = self.new_task(ARTEL, ARTEL_ZONES)
        common, outside = self.files()
        self.write(wt, {common: "# общая зона\n", outside: "вне зон\n"})
        head = self.head_sha(wt)
        after = self.run_checkpoint(self.pull, task_id, wt)
        self.assertEqual(self.head_sha(wt), head,
                         self.note("подтяжка с посторонним сдвинула HEAD"))
        self.assertTrue(
            any(outside in d for d in self.stray_details(task_id, after)),
            self.note(f"запись не называет {outside}"))

    def test_ac7_artel_failed_paths_and_restore_unchanged(self):
        """Задача артели: `pult_commit_failed_paths` берёт `tests/` и не берёт путь вне зон; восстановление удалений — наоборот.

        Ловит мутацию: у артели расширение по профилю заменяет
        `_zone_paths` — путь `tests/` выпадет из возврата
        `pult_commit_failed_paths` и его удаление восстановится; либо
        фильтр снят — путь вне зон войдёт в возврат и его удаление не
        восстановится.
        """
        self.declare()
        task_id, wt = self.new_task(ARTEL, ARTEL_ZONES)
        common, outside = self.files()
        self.write(wt, {common: "# общая зона\n", outside: "вне зон\n"})
        store.journal(self.conn, task_id, "orchestrator",
                      checkpoint.PULT_COMMIT_GIT_FAILED_ACTION,
                      f"{task_id}: git commit (rc=1): учебный отказ")
        paths = checkpoint.pult_commit_failed_paths(self.conn, task_id)
        self.assertIsNotNone(paths, self.note("git не ответил"))
        self.assertIn(common, paths, self.note(f"возврат: {paths}"))
        self.assertNotIn(outside, paths, self.note(f"возврат: {paths}"))

        base_common, base_outside = self.files()
        self.commit_to_main(ARTEL, {base_common: "# база\n",
                                    base_outside: "база\n"})
        task_id, wt = self.new_task(ARTEL, ARTEL_ZONES)
        (wt / base_common).unlink()
        (wt / base_outside).unlink()
        restored = checkpoint.restore_out_of_bounds_deletions(
            self.conn, task_id, "developer", wt)
        self.assertTrue((wt / base_outside).exists(),
                        self.note("удаление вне зон не восстановлено"))
        self.assertIn(base_outside, restored, self.note(f"возврат: {restored}"))
        self.assertFalse((wt / base_common).exists(),
                         self.note("удаление в tests/ восстановлено"))
        self.assertNotIn(base_common, restored, self.note(f"возврат: {restored}"))


class Ac9RenameTest(DeveloperCheckpointSandbox):

    def rename_case(self, target: str, zones: str, src: str, dest_dir: str):
        """База несёт `src`; новая задача делает `git mv src → свой файл`.
        Возврат — (задача, рабочая копия, назначение, текст источника)."""
        task_id = self.task_id()
        text = f"# источник {self.word()}\n"
        self.commit_to_main(target, {src: text})
        task_id, wt = self.new_task(target, zones, task_id)
        dest = self.own(task_id, dest_dir)
        (wt / dest).parent.mkdir(parents=True, exist_ok=True)
        self.git("-C", str(wt), "mv", src, dest)
        return task_id, wt, dest, text

    def check_rename(self, wt, src: str, dest: str, text: str,
                     where: str) -> None:
        head = self.head_files(wt)
        self.assertIn(dest, head, self.note(f"{where}: назначение {dest} "
                                            f"не в коммите пульта"))
        self.assertIn(src, head, self.note(f"{where}: удаление источника "
                                           f"{src} ушло в коммит пульта"))
        self.assertTrue((wt / src).exists(),
                        self.note(f"{where}: источник {src} не восстановлен"))
        self.assertEqual((wt / src).read_text(encoding="utf-8"), text,
                         self.note(where))

    def test_ac9_external_rename_into_own_file(self):
        """Внешний проект: `git mv backend/tests/test_other.py → свой файл` — назначение в коммите, источник цел и восстановлен.

        Для каждого из двух путей AC-1 — своя задача с зонами
        `backend/src/`, база которой несёт `backend/tests/test_other.py`.

        Ловит мутацию: `_stray_staged_paths` по-прежнему читает индекс с
        распознаванием переименований — источник не виден как посторонний,
        и удаление `test_other.py` уйдёт в коммит; либо расширение зон по
        профилю не сделано — назначение снимется со стейджа и в HEAD его
        не будет.
        """
        self.declare()
        for where, fn in self.paths_of_ac1():
            task_id, wt, dest, text = self.rename_case(
                self.ext, EXT_ZONES, OTHER, LLD)
            self.run_checkpoint(fn, task_id, wt)
            with self.subTest(path=where):
                self.check_rename(wt, OTHER, dest, text, where)

    def test_ac9_artel_rename_into_common_zone(self):
        """Артель: `git mv orchestrator/other.py → tests/test_<id>_<имя>.py` — назначение в коммите, источник цел и восстановлен.

        Для каждого из двух путей AC-1 — своя задача с зонами
        `orchestrator/checkpoint.py`, база которой несёт
        `orchestrator/other.py`.

        Ловит мутацию: `_stray_staged_paths` без `--no-renames` — индекс
        отдаёт только `tests/…` (в зоне), посторонних нет, и коммит пульта
        уносит удаление `orchestrator/other.py`: его не будет ни в HEAD, ни
        на диске.
        """
        self.declare()
        for where, fn in self.paths_of_ac1():
            task_id, wt, dest, text = self.rename_case(
                ARTEL, ARTEL_ZONES, "orchestrator/other.py", "tests")
            self.run_checkpoint(fn, task_id, wt)
            with self.subTest(path=where):
                self.check_rename(wt, "orchestrator/other.py", dest, text, where)

    def test_ac9_external_rename_refuses_pull(self):
        """Внешний проект, подтяжка main: переименование `test_other.py` в свой файл отказывает подтяжке, запись называет источник.

        После `commit_pull_checkpoint` HEAD ветки задачи не сдвинут, а
        новая запись `STRAY_WORKTREE_FILES_ACTION` называет
        `backend/tests/test_other.py`.

        Ловит мутацию: индекс читается с распознаванием переименований —
        источник не попадёт в посторонние: подтяжка закоммитит
        переименование (HEAD сдвинется) либо запись назовёт только
        назначение.
        """
        self.declare()
        task_id, wt, dest, _text = self.rename_case(self.ext, EXT_ZONES,
                                                    OTHER, LLD)
        head = self.head_sha(wt)
        after = self.run_checkpoint(self.pull, task_id, wt)
        self.assertEqual(self.head_sha(wt), head,
                         self.note("подтяжка с переименованием сдвинула HEAD"))
        details = self.stray_details(task_id, after)
        self.assertTrue(any(OTHER in d for d in details),
                        self.note(f"запись не называет источник: {details}"))


if __name__ == "__main__":
    unittest.main()
