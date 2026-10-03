"""Шаг роли не удаляет отслеживаемые файлы вне путей, которые ей разрешено
менять.

После шага любой роли удалённые отслеживаемые файлы вне каталога своей
задачи под `tasks` (для developer — ещё и вне зон задачи вместе с
`config.COMMON_ZONES`) восстанавливаются из HEAD и не попадают в коммит
пульта; журнал задачи получает одну именованную запись с числом
восстановленных файлов и первыми из их путей — одну и ту же для developer,
test_author и reviewer. Удаление внутри зон developer не трогается и уходит
в коммит пульта, как раньше.

Группа: долгоживущий
Красен до реализации: чекпоинт developer снимает удаления вне зон со стейджа, но файлы остаются удалёнными на диске и записи с числом нет; у reviewer штатный шаг ничего не откатывает; откат test_author/reviewer пишет запись без числа восстановленных файлов.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`): репозиторий
пульта с bare `origin`, в `main` — отслеживаемые исторические каталоги задач
под `tasks` (имена и число файлов от зерна, только буквы — число в записи
журнала не спутать с частью пути), файлы зоны задачи `pkg/` и общей зоны
`tests/`. Для каждой роли — своя задача target по умолчанию (зоны `pkg/`) со
своей рабочей копией кода (`workspace.ensure`). Шаг роли изображён прямо:
роль удаляет файлы в рабочей копии, затем — тем же порядком, что у
завершения шага в `runner` — штатный успешный путь
(`checkpoint.commit_success_checkpoint`, затем
`checkpoint.commit_step_artifacts`) либо аварийный
(`checkpoint.commit_abnormal_checkpoint`).
"""
import random
import re
import unittest

from orchestrator import checkpoint, config, store, workspace
from tests.sandbox import RealGitSandbox

LETTERS = "ABCDEFGHJKMNPQRSTVWXYZ"
ZONE = "pkg/"
ZONE_FILES = {"pkg/mod.py": "VALUE = 1\n", "pkg/keep.py": "KEEP = 1\n"}
COMMON_ZONE_FILE = ("tests/test_common_zone_fixture.py",
                    "def test_common():\n    pass\n")
ROLE_STATES = {"developer": "in_dev", "test_author": "tests_writing",
               "reviewer": "review"}


class RestoreDeletedSandbox(RealGitSandbox):
    """Исторические каталоги задач, зона `pkg/` и файл общей зоны в HEAD."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.historic = {}
        for _ in range(2 + self.rng.randrange(4)):
            task_dir = "H" + self.word()
            names = self.rng.sample(["SPEC.md", "PLAN.md", "REVIEW.md",
                                     "RETRO.md", "QUESTIONS.md"],
                                    2 + self.rng.randrange(3))
            for name in names:
                rel = "/".join(("tasks", task_dir, name))
                self.historic[rel] = f"# {task_dir}\nстрока\nстрока\n"
        files = dict(self.historic)
        files.update(ZONE_FILES)
        files[COMMON_ZONE_FILE[0]] = COMMON_ZONE_FILE[1]
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "исторические каталоги и зоны")
        self.add_synced_origin()
        self.conn = store.db()
        self.serial = 0

    def word(self, size: int = 8) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def explain(self, extra: str = "") -> str:
        return f"зерно: {self.seed}; {extra}"

    def new_task(self, role: str) -> tuple:
        """(id, рабочая копия) задачи роли в её состоянии, зоны — `pkg/`."""
        self.serial += 1
        task_id = "01M0000000000000000000RST" + LETTERS[self.serial]
        branch = f"task/fixture-restore-{self.serial}"
        store.insert_task(self.conn, task_id, "Фикстура восстановления",
                          ROLE_STATES[role], branch, config.DEFAULT_TARGET, 25.0)
        store.update_task(self.conn, task_id, zones=ZONE)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, f"рабочая копия кода не заведена: {error}")
        return task_id, wt

    def wt_git(self, wt, *args: str) -> str:
        return self.git("-C", str(wt), *args)

    def delete_historic(self, wt) -> list:
        """Роль удаляет случайное непустое подмножество исторических файлов."""
        doomed = sorted(self.rng.sample(sorted(self.historic),
                                        max(4, len(self.historic) // 2)))
        for rel in doomed:
            (wt / rel).unlink()
        return doomed

    def finish_step(self, task_id: str, role: str, path: str) -> None:
        if path == "штатный":
            checkpoint.commit_success_checkpoint(self.conn, task_id, role)
            checkpoint.commit_step_artifacts(self.conn, task_id, role)
        else:
            checkpoint.commit_abnormal_checkpoint(self.conn, task_id, role,
                                                  "rc=1")

    def new_rows(self, task_id: str, before: int) -> list:
        return [dict(r) for r in store.task_steps(self.conn, task_id)
                if r["id"] > before]

    def last_row_id(self, task_id: str) -> int:
        rows = store.task_steps(self.conn, task_id)
        return rows[-1]["id"] if rows else 0

    def restore_rows(self, rows: list, doomed: list) -> list:
        """Записи журнала, несущие число восстановленных и хотя бы один путь."""
        count = re.compile(rf"(?<![\w.]){len(doomed)}(?![\w.])")
        return [r for r in rows
                if count.search(r["detail"] or "")
                and any(rel in (r["detail"] or "") for rel in doomed)]

    def assert_restored_not_committed(self, wt, doomed: list, note: str) -> None:
        for rel in doomed:
            path = wt / rel
            self.assertTrue(path.is_file(),
                            self.explain(f"{note}: {rel} не восстановлен"))
            self.assertEqual(path.read_text(encoding="utf-8"),
                             self.historic[rel], self.explain(f"{note}: {rel}"))
        self.assertEqual(self.wt_git(wt, "status", "--porcelain", "--", "tasks"),
                         "", self.explain(f"{note}: git status по tasks не чист"))
        in_head = set(self.wt_git(wt, "ls-tree", "-r", "--name-only", "HEAD",
                                  "--", "tasks").split())
        missing = [rel for rel in doomed if rel not in in_head]
        self.assertEqual(missing, [],
                         self.explain(f"{note}: удаление ушло в коммит пульта"))

    def run_role_step(self, role: str, path: str) -> tuple:
        """(записи восстановления, удалённые пути) шага роли."""
        task_id, wt = self.new_task(role)
        before = self.last_row_id(task_id)
        doomed = self.delete_historic(wt)
        self.finish_step(task_id, role, path)
        note = f"{role}, путь {path}, удалено {len(doomed)}"
        self.assert_restored_not_committed(wt, doomed, note)
        return self.restore_rows(self.new_rows(task_id, before), doomed), doomed


class DeveloperStepTest(RestoreDeletedSandbox):

    def test_ac6_developer_mass_deletion_restored_zone_deletion_committed(self):
        """Массовое удаление исторических каталогов developer восстановлено.

        Сценарий: шаг developer на штатном и на аварийном пути удаляет
        случайное число отслеживаемых исторических файлов `tasks` (вне зон),
        правит и удаляет файлы зоны задачи `pkg/` и удаляет файл общей зоны
        `tests/`. После шага исторические файлы восстановлены из HEAD с
        прежним текстом, `git status` по `tasks` пуст, HEAD рабочей копии их
        по-прежнему несёт (удаления в коммите пульта нет); в журнале задачи
        ровно одна запись с числом восстановленных файлов и первыми из их
        путей. Удаления внутри зон не восстановлены: `pkg/keep.py` и файл
        общей зоны нет ни на диске, ни в HEAD, коммит пульта их удаление
        несёт.

        Ловит мутацию: восстановление не сделано — чекпоинт developer лишь
        снимает удаления вне зон со стейджа, файлы остаются удалёнными на
        диске; восстановление не учитывает зоны — удалённый `pkg/keep.py`
        или файл общей зоны `tests/` возвращается из HEAD; запись журнала
        пишется на каждый файл или без числа — записей с числом не одна.
        """
        for path in ("штатный", "аварийный"):
            with self.subTest(path=path):
                task_id, wt = self.new_task("developer")
                head_before = self.wt_git(wt, "rev-parse", "HEAD").strip()
                before = self.last_row_id(task_id)
                doomed = self.delete_historic(wt)
                (wt / "pkg" / "mod.py").write_text(f"VALUE = {self.seed}\n",
                                                   encoding="utf-8")
                (wt / "pkg" / "keep.py").unlink()
                (wt / COMMON_ZONE_FILE[0]).unlink()

                self.finish_step(task_id, "developer", path)

                note = f"developer, путь {path}, удалено {len(doomed)}"
                self.assert_restored_not_committed(wt, doomed, note)
                rows = self.restore_rows(self.new_rows(task_id, before), doomed)
                self.assertEqual(len(rows), 1, self.explain(
                    f"{note}: записей восстановления не одна: {rows}"))

                self.assertNotEqual(self.wt_git(wt, "rev-parse", "HEAD").strip(),
                                    head_before, self.explain(f"{note}: коммита нет"))
                in_head = set(self.wt_git(wt, "ls-tree", "-r", "--name-only",
                                          "HEAD").split())
                for rel in ("pkg/keep.py", COMMON_ZONE_FILE[0]):
                    self.assertFalse((wt / rel).exists(), self.explain(
                        f"{note}: удаление в зоне {rel} восстановлено"))
                    self.assertNotIn(rel, in_head, self.explain(
                        f"{note}: удаление в зоне {rel} не закоммичено"))


class ReadOnlyRolesStepTest(RestoreDeletedSandbox):

    def test_ac7_test_author_and_reviewer_get_same_restore_record(self):
        """У test_author и reviewer — та же запись восстановления, что у developer.

        Сценарий: на штатном и аварийном пути шаг developer, test_author и
        reviewer (у каждого своя задача в своём состоянии) удаляет случайное
        число отслеживаемых исторических файлов `tasks`. После шага файлы
        восстановлены из HEAD, `git status` по `tasks` пуст; у каждой роли в
        журнале ровно одна запись с числом восстановленных файлов и первыми
        из их путей, и её действие журнала то же, что у записи developer.

        Ловит мутацию: штатный шаг reviewer по-прежнему ничего не откатывает
        — удалённые файлы остаются удалёнными; откат test_author/reviewer
        пишет прежнюю запись «откат вне мандата» без числа восстановленных
        файлов — записи с числом нет; для developer и прочих ролей заведены
        разные действия журнала — действия записей не совпадают.
        """
        for path in ("штатный", "аварийный"):
            actions = {}
            for role in ("developer", "test_author", "reviewer"):
                with self.subTest(path=path, role=role):
                    rows, doomed = self.run_role_step(role, path)
                    self.assertEqual(len(rows), 1, self.explain(
                        f"{role}, путь {path}, удалено {len(doomed)}: записей "
                        f"восстановления не одна: {rows}"))
                    actions[role] = rows[0]["action"]
            with self.subTest(path=path, check="одно действие"):
                self.assertEqual(len(actions), 3, self.explain(f"{actions}"))
                self.assertEqual(len(set(actions.values())), 1,
                                 self.explain(f"действия записей: {actions}"))


if __name__ == "__main__":
    unittest.main()
