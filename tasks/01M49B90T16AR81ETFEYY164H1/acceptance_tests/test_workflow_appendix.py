"""Приложение PLAN к `.github/workflows/ci.yml`: применяется к дереву
ветки, и сторож шага приложений `scripts/plan_appendix_ci.py
--check-workflow` проходит на файле с наложенным приложением.

Группа: разовый

Красен до реализации: PLAN.md задачи ещё нет (или в нём нет приложения к `.github/workflows/ci.yml`) — `artifact_text("PLAN.md")` даёт `None` либо приложений к `ci.yml` ноль.

Планка провалидирована стабом: тот же разбор и наложение на приложении,
снятом `git diff` с временной правки условия заданий `python`/`python-min`
в копии `ci.yml`, — тест зелёный; на приложении, ломающем шаг приложений
PLAN в `python`, — красный.

Свойства самого `ci.yml` с наложенным приложением, зависящие от наличия
открытого PR у ветки, тестом не проверяются (пометки AC-2, AC-3 ниже).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

if CODE_ROOT and CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)
from scripts import guard  # noqa: E402

WORKFLOW_REL = ".github/workflows/ci.yml"

# AC-2: manual — распознание открытого PR у ветки во время прогона push — запрос к GitHub во время прогона Actions (требование 1 оставляет способ разработчику: условие на задании, шаг запроса API, иное), и тестового контура, исполняющего задания GitHub Actions с живым ответом GitHub о PR ветки, нет; Оператор сверяет условие `python`/`python-min` в приложении PLAN к `ci.yml` (push ветки `task/**` с открытым PR — `skipped`, pull_request — исполняются) и отсутствие ключей `paths`/`paths-ignore` в триггерах `push`/`pull_request`.
# AC-3: manual — то же свойство среды: исполнится ли задание на push без открытого PR и на push `main`, решает ответ GitHub о PR ветки во время прогона Actions, тестового контура которого нет; Оператор сверяет по приложению PLAN, что на push `task/**` без открытого PR (первый push, закрытый PR) и на push `main` условие `python`/`python-min` сводится к прежнему `needs.changes.outputs.code != 'false'`.
# AC-11: manual — заявки «Ловит мутацию» у новых и изменённых методов `tests/` держит гейт выхода из `in_dev` (`advance_gates/review.py::_mutation_claim_gate`), а замер числа прогонов `python` на коммит по истории Actions — данные живого GitHub и человеческий вердикт по существу (верно ли сосчитано и по каким задачам); Оператор сверяет замер в PLAN (задачи, число до, ожидаемое после).


def git(cwd, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True)


def workflow_appendices(plan: str) -> list:
    """Приложения PLAN, правящие `.github/workflows/ci.yml`, в порядке PLAN."""
    appendices, _errors = guard.plan_appendices(plan)
    return [a for a in appendices if WORKFLOW_REL in a.paths]


def patched_workflow(tmp: Path, diffs: list) -> tuple[Path | None, str]:
    """`ci.yml` дерева HEAD с приложениями `diffs`, наложенными подряд во
    временном каталоге; (None, ответ git) — не наложилось."""
    base = git(CODE_ROOT, "show", f"HEAD:{WORKFLOW_REL}")
    if base.returncode != 0:
        return None, f"git show HEAD:{WORKFLOW_REL}: {base.stderr.strip()}"
    target = tmp / WORKFLOW_REL
    target.parent.mkdir(parents=True)
    target.write_text(base.stdout, encoding="utf-8")
    init = git(tmp, "init", "-q")
    if init.returncode != 0:
        return None, f"git init: {init.stderr.strip()}"
    for number, diff in enumerate(diffs, 1):
        patch = tmp / f"appendix-{number}.diff"
        patch.write_text(diff, encoding="utf-8")
        res = git(tmp, "apply", str(patch))
        if res.returncode != 0:
            return None, (f"приложение {number}: "
                          f"{(res.stderr or res.stdout).strip()}")
    return target, ""


def check_workflow(path: Path) -> subprocess.CompletedProcess:
    """`plan_appendix_ci.py --check-workflow <path>` вне прогона Actions:
    переменные `GITHUB_*` сняты — сторож проверяет файл как есть."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GITHUB_")}
    return subprocess.run(
        [sys.executable, str(Path(CODE_ROOT) / "scripts" /
                             "plan_appendix_ci.py"),
         "--check-workflow", str(path)],
        cwd=CODE_ROOT, env=env, capture_output=True, text=True)


class WorkflowAppendixTest(unittest.TestCase):
    """Приложение PLAN к `ci.yml` применяется и проходит сторож шага."""

    def test_ac1_workflow_appendix_applies_and_passes_check_workflow(self):
        """Приложение PLAN к `ci.yml` применяется и проходит сторож.

        Из PLAN.md задачи (ссылка документов) берутся приложения, правящие
        `.github/workflows/ci.yml`: оно есть хотя бы одно; первое
        применяется к дереву HEAD ветки (`git apply --check` помощника
        пульта); все они подряд накладываются на копию `ci.yml` HEAD во
        временном каталоге, и `python3 scripts/plan_appendix_ci.py
        --check-workflow <копия>` завершается кодом 0.

        Ловит мутацию: правка условия заданий `python`/`python-min` снесла
        или передвинула за pytest шаг `python3 scripts/plan_appendix_ci.py`
        либо сузила его условие до одного push — сторож печатает
        «::error::…» и выходит кодом 1; либо приложение снято не с текущего
        `ci.yml` (устаревшие строки контекста) — `git apply --check`
        отказывает.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи в ссылке документов нет")
        diffs = [a.diff for a in workflow_appendices(plan)]
        self.assertTrue(diffs, f"в PLAN нет приложения к {WORKFLOW_REL}")
        answer = apply_check(diffs[0])
        self.assertEqual(answer, "",
                         f"приложение к {WORKFLOW_REL} не применяется к "
                         f"HEAD: {answer}")
        with tempfile.TemporaryDirectory() as tmp:
            path, why = patched_workflow(Path(tmp), diffs)
            self.assertIsNotNone(path, why)
            res = check_workflow(path)
            self.assertEqual(res.returncode, 0,
                             f"--check-workflow отказал:\n{res.stdout}\n"
                             f"{res.stderr}")


if __name__ == "__main__":
    unittest.main()
