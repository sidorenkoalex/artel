"""Миссии ролей задачи артели и белый список команд роли — против кода базы ветки задачи.

Группа: разовый
Зелёный с рождения: на коде до правки код ветки и код базы совпадают — тексты миссий равны, белый список прежний (совместимое условие ⊆ с разностью ⊆ {guard} выполнено); тест держит неизменность миссий артели и даёт белому списку прирасти только командой guard.

Эталон «до правки» снимается исполнением: дерево базы ветки задачи
(`DIFF_BASE` помощника пульта) выкладывается `git archive` во временный
каталог, и один и тот же зонд (`PROBE` ниже) собирает миссии
`role_prompt.mission_brief_package` и множество
`artel._ROLE_ALLOWED_COMMANDS` сначала в дереве базы, затем в рабочей
копии кода задачи (`CODE_ROOT`) — каждый раз отдельным процессом
`python3`, чтобы модули не смешались. Зонд работает в песочнице дерева,
которое исполняет (`tests.sandbox.TmpRootTest` того же дерева): пути
`config` — во временном каталоге, запись артели с профилем тестов —
`targets.yaml` песочницы; корень пульта на время сборки — один и тот же
фиксированный путь, рабочий каталог и каталог документов — фиксированные
строки, идентификаторы задач — от зерна теста (одного на оба прогона).
Брифы и ревью-пакет (`brief.*_component`/`*_brief`, `step_notes_block`,
`review.review_package`) подменены пустыми в обоих деревьях: миссия от них
не зависит. Варианты — `conn=None` и задача проекта артели в БД; роли —
analyst, developer, spec_auditor, test_author, reviewer. Исход сборки,
отказавшей исключением (сегодня — spec_auditor при `conn=None`: журнал
входа в аудит читается из БД), записывается именем исключения и тоже
сравнивается с базой.
"""
import json
import os
import random
import subprocess
import sys
import tarfile
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

ROLES = ("analyst", "developer", "spec_auditor", "test_author", "reviewer")
NEW_COMMAND = "guard"

PROBE = r'''
import json, sys, unittest
from pathlib import Path
from unittest import mock

TREE, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, TREE)

from orchestrator import artel, brief, config, review, role_prompt, store
from tests.sandbox import TmpRootTest

ROLES = ("analyst", "developer", "spec_auditor", "test_author", "reviewer")
STATE_OF = {"analyst": "spec_writing", "spec_auditor": "spec_audit",
            "test_author": "tests_writing", "developer": "in_dev",
            "reviewer": "review"}
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
EMPTY = {brief: ("analyst_map_component", "test_author_answer_component",
                 "developer_brief", "spec_auditor_brief", "step_notes_block"),
         review: ("review_package", "previous_verdict_sha")}


class Probe(TmpRootTest):

    def test_probe(self):
        import random
        rng = random.Random(SEED)
        for module, names in EMPTY.items():
            for name in names:
                if hasattr(module, name):
                    patcher = mock.patch.object(module, name, return_value="")
                    patcher.start()
                    self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        conn = store.db()
        missions = {}
        fixed_root = Path("/pult-root-" + str(SEED))
        for role in ROLES:
            task_id = "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))
            store.insert_task(conn, task_id, "Задача зонда", STATE_OF[role],
                              "task/" + task_id.lower() + "-probe",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
            t = store.get_task(conn, task_id)
            for variant, c in (("conn=None", None), ("задача в БД", conn)):
                key = variant + "/" + role
                with mock.patch.object(config, "ROOT", fixed_root):
                    try:
                        mission, _b, _p = role_prompt.mission_brief_package(
                            c, task_id, t, role, "/cwd-probe-" + str(SEED),
                            "/docs-probe-" + str(SEED) + "/" + task_id)
                        missions[key] = mission
                    except Exception as exc:
                        missions[key] = "исключение " + type(exc).__name__
        Path(OUT).write_text(json.dumps({
            "missions": missions,
            "allowed": sorted(artel._ROLE_ALLOWED_COMMANDS)},
            ensure_ascii=False), encoding="utf-8")


result = unittest.TextTestRunner(stream=sys.stderr, verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(Probe))
sys.exit(0 if result.wasSuccessful() else 1)
'''


def probe(tree: Path, out: Path, seed: int) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    res = subprocess.run([sys.executable, "-c", PROBE, str(tree), str(out),
                          str(seed)], cwd=tree, env=env, capture_output=True,
                         text=True, timeout=100)
    if res.returncode != 0 or not out.is_file():
        raise AssertionError(f"зонд в {tree} не отработал (код "
                             f"{res.returncode}):\n{res.stdout[-2000:]}\n"
                             f"{res.stderr[-4000:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def base_tree(dest: Path) -> Path:
    """Дерево базы ветки задачи без каталога задач."""
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "archive",
                          "--format=tar", DIFF_BASE, "--", ".",
                          ":(exclude)tasks"], capture_output=True, timeout=60)
    if res.returncode != 0:
        raise AssertionError(f"git archive {DIFF_BASE}: "
                             f"{res.stderr.decode('utf-8', 'replace')}")
    with tarfile.open(fileobj=BytesIO(res.stdout)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:
            tar.extractall(dest)
    return dest


class ArtelMissionsUnchangedTest(unittest.TestCase):

    def test_ac9_artel_missions_and_allowlist_against_base(self):
        """Миссии пяти ролей задачи артели совпадают байт в байт с кодом базы ветки; белый список прирастает только командой `guard`.

        Сценарий: зонд собирает миссии analyst, developer, spec_auditor,
        test_author и reviewer задачи артели — при `conn=None` и по задаче
        проекта артели в БД — сначала кодом базы ветки задачи, затем кодом
        ветки, на одинаковых входах. Тексты каждой пары (вариант, роль)
        равны; по задаче в БД миссия собрана у каждой роли без исключения.
        Прежнее множество `_ROLE_ALLOWED_COMMANDS` — подмножество нового, а
        разность нового и прежнего — подмножество {`guard`}.

        Ловит мутацию: развилка миссий по проекту задачи задела ветку
        артели — «Прогони scripts/guard.py» заменён командой пульта, пункт
        5 test_author или строка ревьювера переписаны и у артели — текст
        пары отличается от эталона базы; в белый список роли попала ещё
        одна команда или из него выпала прежняя — разность не ⊆ {guard}
        либо прежнее множество не ⊆ нового.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        with tempfile.TemporaryDirectory(prefix="ac9-base-") as tmp:
            tmp = Path(tmp)
            base = base_tree(tmp / "tree")
            before = probe(base, tmp / "before.json", seed)
            after = probe(Path(CODE_ROOT), tmp / "after.json", seed)
        note = f"зерно: {seed}; база {DIFF_BASE}"
        for role in ROLES:
            key = f"задача в БД/{role}"
            self.assertFalse(after["missions"][key].startswith("исключение "),
                             f"{note}; {key}: {after['missions'][key]}")
        self.assertEqual(sorted(after["missions"]), sorted(before["missions"]),
                         note)
        for key in sorted(before["missions"]):
            with self.subTest(key=key):
                self.assertEqual(after["missions"][key], before["missions"][key],
                                 f"{note}; миссия {key} изменилась")
        old, new = set(before["allowed"]), set(after["allowed"])
        self.assertLessEqual(old, new, f"{note}; выпали: {sorted(old - new)}")
        self.assertLessEqual(new - old, {NEW_COMMAND},
                             f"{note}; лишние: {sorted(new - old - {NEW_COMMAND})}")


if __name__ == "__main__":
    unittest.main()
