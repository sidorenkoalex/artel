"""AC-4: помощник работает без `.artel/` и при сломанном `orchestrator`.

Планка исполняется в рабочей копии кода, в корне которой нет `.artel/`
(ни `state.db`, ни клона по `config.PROJECTS`), а пакет `orchestrator`
рабочей копии не импортируется. Помощник загружается в отдельном
процессе Python с `cwd` = рабочая копия — ровно так, как его видит планка
под pytest пульта; `artifact_text`, `branch_diff`, `changed_paths`,
`apply_check` отвечают штатно.

Группа: разовый
Красен до реализации: выкладка не кладёт `_pult.py` — загружать в отдельном процессе нечего.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import SPEC_TEXT, PlankHelperSandbox  # noqa: E402

BROKEN_INIT = 'raise ImportError("пакет orchestrator рабочей копии сломан")\n'

APPLICABLE_DIFF = """diff --git a/marker.txt b/marker.txt
--- a/marker.txt
+++ b/marker.txt
@@ -1 +1 @@
-main
+main, правка приложения
"""

# Процесс планки: `cwd` — рабочая копия, первый элемент `sys.path` — она же
# (`-c`), поэтому `import orchestrator` находит сломанный пакет рабочей копии.
CHILD = r'''
import importlib.util, json, sys
result = {}
try:
    import orchestrator  # noqa: F401
    result["orchestrator_imports"] = True
except ImportError:
    result["orchestrator_imports"] = False
spec = importlib.util.spec_from_file_location("pult_child", sys.argv[1])
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
with open(sys.argv[2], encoding="utf-8") as fh:
    diff = fh.read()
result["artifact_text"] = helper.artifact_text("SPEC.md")
result["branch_diff"] = helper.branch_diff()
result["changed_paths"] = list(helper.changed_paths())
result["apply_check"] = helper.apply_check(diff)
print(json.dumps(result))
'''


class StandaloneHelperTest(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        self.commit_code("orchestrator/__init__.py", BROKEN_INIT,
                         "сломанный пакет orchestrator рабочей копии")
        self.write_untracked("scratch/notes.txt")
        self.materialize()

    def run_child(self) -> dict:
        patch_dir = Path(tempfile.mkdtemp(prefix="plank-helper-ac4-"))
        self.addCleanup(shutil.rmtree, patch_dir, ignore_errors=True)
        patch = patch_dir / "appendix.diff"
        patch.write_text(APPLICABLE_DIFF, encoding="utf-8")
        env = {k: v for k, v in os.environ.items()
               if k != "PYTHONPATH" and not k.startswith("GIT_")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        res = subprocess.run(
            [sys.executable, "-c", CHILD, str(self.helper_path), str(patch)],
            cwd=self.wt, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0,
                         f"процесс планки упал:\n{res.stdout}\n{res.stderr}")
        return json.loads(res.stdout.strip().splitlines()[-1])

    def test_ac4_helper_answers_without_artel_dir_and_orchestrator(self):
        """Четыре функции отвечают в процессе без `.artel/` и `orchestrator`.

        Сценарий: в рабочей копии закоммичен `orchestrator/__init__.py`,
        поднимающий `ImportError`, и лежит неотслеживаемый `scratch/
        notes.txt`; `.artel/` в её корне нет. Отдельный процесс с `cwd` =
        рабочая копия убеждается, что `import orchestrator` падает, и
        зовёт помощник: `artifact_text("SPEC.md")` — SPEC ссылки,
        `branch_diff()` несёт правку `orchestrator/__init__.py`,
        `changed_paths()` — её и `scratch/notes.txt`, `apply_check`
        применимого диффа — пустая строка.

        Ловит мутацию: помощник импортирует пакет `orchestrator` рабочей
        копии (или находит репозиторий ссылки через `config.PROJECTS`
        планки, где клона нет) — процесс падает `ImportError` либо
        `artifact_text` не находит ссылку."""
        self.assertFalse((self.wt / ".artel").exists(),
                         "у рабочей копии песочницы есть .artel/")

        result = self.run_child()

        self.assertFalse(result["orchestrator_imports"],
                         "пакет orchestrator рабочей копии не сломан")
        self.assertEqual(result["artifact_text"], SPEC_TEXT)
        self.assertIn("orchestrator/__init__.py", result["branch_diff"])
        self.assertIn("orchestrator/__init__.py", result["changed_paths"])
        self.assertIn("scratch/notes.txt", result["changed_paths"])
        self.assertEqual(result["apply_check"], "")


if __name__ == "__main__":
    unittest.main()
