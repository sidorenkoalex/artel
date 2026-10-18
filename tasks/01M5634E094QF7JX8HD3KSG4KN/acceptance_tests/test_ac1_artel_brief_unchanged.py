"""AC-1: бриф, опись и миссии задачи артели побайтно совпадают с эталоном,
снятым тем же тестом с кода до правки.

Группа: разовый

Зелёный с рождения: до реализации код рабочей копии и код базы ветки задачи совпадают, эталон и проверяемый вывод снимаются одним дампером с одного кода — тест держит, что правка задачи не меняет бриф артели ни на байт.

Эталон снимается здесь же, при каждом прогоне: дерево `orchestrator/`,
`scripts/`, `tests/`, `templates/`, `skills/` базы ветки задачи
(`_pult.DIFF_BASE` — точка расхождения ветки с `origin/main`, пульт считает
её тем же `gitcmd.diff_base`, что гейт зон) извлекается `git archive` во
временный каталог — это «код до правки». Проверяемый вывод — то же самое с
`orchestrator/`, `scripts/`, `templates/`, `skills/` рабочей копии кода
(`_pult.CODE_ROOT`) и с `tests/` базы: песочница одна и та же, различается
только код пульта.

Дампер (строка `DUMPER`) в отдельном процессе на каждом дереве заводит
задачу артели в `tests.sandbox.LightTransitionSandbox` с зафиксированным id
(`idgen.new_task_id` подменён) и документами задачи (SPEC, TZ, QUESTIONS,
ANSWER-1, PLAN, REVIEW) и снимает с ЗАФИКСИРОВАННЫМ `run_id`
(`brief.new_run_id` подменён): брифы developer, analyst, spec_auditor,
test_author (функции `brief.*`, опись — их заголовки компонентов) и
миссии с брифами всех ролей (`role_prompt.mission_brief_package`;
ревью-пакет reviewer подменён строкой — пакет вне задачи). Путь временного
корня песочницы — единственное, что в выводе случайно, — заменяется
меткой `<ROOT>`; остальное сравнивается побайтно.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

CODE_DIRS = ("orchestrator", "scripts", "templates", "skills")
BASE_DIRS = CODE_DIRS + ("tests",)

DUMPER = r'''
import json
import shutil
import sys
from pathlib import Path
from unittest import mock

tree = Path(sys.argv[1]).resolve()
out_path = Path(sys.argv[2])
sys.path.insert(0, str(tree))

from orchestrator import brief, idgen, review, role_prompt, store
from tests import sandbox

FIXED_ID = "01M5000000000000000000AC01"
RUN_ID = "0123456789abcdef0123456789abcdef"
DOCS = {
    "SPEC.md": "# SPEC эталона\n\nТребование эталона.\n",
    "TZ.md": "# ТЗ эталона\n\nТекст ТЗ.\n",
    "QUESTIONS.md": "# QUESTIONS эталона\n\n1. Вопрос?\n",
    "ANSWER-1.md": "# ANSWER-1 эталона\n\n1. Ответ.\n",
    "PLAN.md": "# PLAN эталона\n\nШаг.\n",
    "REVIEW.md": "# REVIEW эталона\n\nЗамечание.\n",
}


class Dump(sandbox.LightTransitionSandbox):
    def runTest(self):
        pass


with mock.patch.object(idgen, "new_task_id", lambda: FIXED_ID):
    case = Dump()
    case.setUp()
try:
    root = case.root
    for name in ("templates", "skills"):
        shutil.copytree(tree / name, root / name, dirs_exist_ok=True)
    sandbox.seed_developer_brief_fixtures(root)
    case.tdir.mkdir(parents=True, exist_ok=True)
    for name, text in DOCS.items():
        (case.tdir / name).write_text(text, encoding="utf-8")
    conn = store.db()
    t = store.get_task(conn, case.TASK)
    out = {}
    with mock.patch.object(brief, "new_run_id", lambda: RUN_ID), \
            mock.patch.object(review, "review_package",
                              lambda *a, **k: "РЕВЬЮ-ПАКЕТ"), \
            mock.patch.object(review, "previous_verdict_sha",
                              lambda *a, **k: ""):
        for name in ("developer_brief", "analyst_map_component",
                     "spec_auditor_brief", "test_author_answer_component"):
            out["brief:" + name] = getattr(brief, name)(conn, case.TASK)
        for role in ("analyst", "test_author", "developer", "spec_auditor",
                     "reviewer"):
            mission, brief_text, package = role_prompt.mission_brief_package(
                conn, case.TASK, t, role, Path("/fixed/cwd"),
                docs_dir=Path("/fixed/docs"))
            out["mission:" + role] = mission
            out["mission-brief:" + role] = brief_text
            out["package:" + role] = package
    text = json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1)
    for prefix in (str(Path(root).resolve()), str(root)):
        text = text.replace(prefix, "<ROOT>")
    out_path.write_text(text, encoding="utf-8")
finally:
    case.doCleanups()
'''


def dump(tree: Path, out: Path) -> str:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    res = subprocess.run([sys.executable, "-c", DUMPER, str(tree), str(out)],
                         cwd=tree, capture_output=True, text=True, env=env,
                         timeout=100)
    if res.returncode != 0 or not out.is_file():
        raise AssertionError(f"дампер на {tree} упал (код {res.returncode}):\n"
                             f"{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
    return out.read_text(encoding="utf-8")


class ArtelBriefUnchangedTest(unittest.TestCase):

    def test_ac1_artel_briefs_and_missions_byte_identical_to_base(self):
        """Бриф и опись developer/analyst/spec_auditor/test_author и миссии
        всех ролей задачи артели — с кода базы ветки и с кода рабочей копии.

        Сценарий: один и тот же дампер с зафиксированными `run_id` и id
        задачи снимает вывод с дерева базы (эталон) и с дерева рабочей
        копии; оба вывода равны побайтно — и каждый ключ (бриф, миссия)
        отдельно, и весь текст целиком.

        Ловит мутацию: развилка «артель или внешний» в `brief.py`/
        `role_prompt.py` задевает и артель — например, заголовок
        компонента конвенций становится «CLAUDE.md пульта», пометка карты
        переезжает или миссия developer теряет «карта кодовой базы» и у
        артели; вывод рабочей копии расходится с эталоном."""
        self.assertTrue(DIFF_BASE, "база диффа ветки задачи не определена "
                                   "пультом (_pult.DIFF_BASE)")
        with tempfile.TemporaryDirectory(prefix="ac1-etalon-") as tmp:
            tmp = Path(tmp)
            base_tree, head_tree = tmp / "base", tmp / "head"
            base_tree.mkdir()
            archive = subprocess.run(
                ["git", "-C", CODE_ROOT, "archive", "--format=tar", DIFF_BASE,
                 *BASE_DIRS], capture_output=True, timeout=100)
            self.assertEqual(archive.returncode, 0,
                             archive.stderr.decode("utf-8", "replace"))
            with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
                tar.extractall(base_tree, filter="data")
            head_tree.mkdir()
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            for name in CODE_DIRS:
                shutil.copytree(Path(CODE_ROOT) / name, head_tree / name,
                                ignore=ignore)
            shutil.copytree(base_tree / "tests", head_tree / "tests",
                            ignore=ignore)

            etalon = dump(base_tree, tmp / "etalon.json")
            actual = dump(head_tree, tmp / "actual.json")

        self.assertIn("0123456789abcdef0123456789abcdef", etalon,
                      "эталон снят не с зафиксированным run_id")
        etalon_parts, actual_parts = json.loads(etalon), json.loads(actual)
        self.assertEqual(sorted(actual_parts), sorted(etalon_parts))
        for key in sorted(etalon_parts):
            with self.subTest(key=key):
                self.assertEqual(actual_parts[key], etalon_parts[key],
                                 f"{key}: вывод артели разошёлся с эталоном")
        self.assertEqual(actual.encode("utf-8"), etalon.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
