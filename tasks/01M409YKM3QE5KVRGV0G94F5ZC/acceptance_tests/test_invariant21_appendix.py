"""Приложение к PLAN с правкой инварианта 21 применимо, и с ним
`tests/test_invariants.py` зелёный.

Группа: разовый

Красен до реализации: в ссылке документов задачи нет PLAN.md (разработчик ещё не начинал), значит нет и приложения с правкой инварианта 21 — чтение PLAN из ссылки отказывает.

Группа «разовый»: предмет — PLAN.md этой задачи в ссылке документов и его
приложение; после мержа приложение применено, и проверять его не на чем.

PLAN.md читается из ссылки документов `refs/artifacts/<id>`
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`), не с диска.
Приложения разбирает тот же узел, что гейт приложений PLAN
(`guard.plan_appendices`: разделы «## Приложение…», блоки ```diff).
Правка инварианта 21 узнаётся по строке таблицы реестра: среди
приложений к `docs/invariants.md` есть дифф, который убирает строку
`| 21 | …` и добавляет новую строку `| 21 | …`, говорящую о каталоге
документов (корень «документ») — точную формулировку тест не навязывает.

Проверка исполнением: копия рабочей копии кода (файлы `git ls-files
--cached --others --exclude-standard` корня, в который выложена планка,
`Path(__file__).parents[3]`) во временном каталоге, свой `git init` в ней;
каждое приложение PLAN по порядку — `git apply --check`, затем `git apply`
(так их кладёт мерж: подряд на одно дерево). Затем
`tests/test_invariants.py` копии — pytest с `-n` рабочими xdist (весь
модуль одним процессом идёт около двух минут — дольше потолка одного теста
планки), окружение без `ARTEL_ROLE`: унаследованный маркер шага роли
красит тесты, запускающие пульт отдельным процессом (урок части (а),
«Материалы» SPEC).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, config, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01M409YKM3QE5KVRGV0G94F5ZC"
CODE_ROOT = Path(__file__).resolve().parents[3]
INVARIANTS_DOC = "docs/invariants.md"
INVARIANTS_TEST = "tests/test_invariants.py"
ROW_21 = "| 21 |"
DOCS_STEM = "документ"
#: Рабочих xdist на прогон модуля инвариантов — столько же, сколько у
#: полного набора пульта (`config.FULL_SUITE_WORKERS`, значение `-n`).
WORKERS = str(config.FULL_SUITE_WORKERS)


def invariant21_edits(appendices) -> list:
    """Приложения к `docs/invariants.md`, переписывающие строку 21 реестра
    так, что новая строка говорит о каталоге документов."""
    found = []
    for appendix in appendices:
        if INVARIANTS_DOC not in appendix.paths:
            continue
        lines = appendix.diff.splitlines()
        removed = any(line.startswith("-" + ROW_21) for line in lines)
        added = [line for line in lines if line.startswith("+" + ROW_21)]
        if removed and any(DOCS_STEM in line.lower() for line in added):
            found.append(appendix)
    return found


def copy_code_tree(src: Path, dest: Path) -> None:
    """Файлы рабочей копии `src` (отслеживаемые и новые неигнорируемые) —
    в `dest`, со своим `git init` (без коммита: `git apply` нужен лишь
    репозиторий)."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=src, capture_output=True, check=True).stdout.decode("utf-8")
    for rel in filter(None, listed.split("\0")):
        source = src / rel
        if not source.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True,
                   capture_output=True)


def apply_in_order(tree: Path, appendices) -> list:
    """`git apply --check`, затем `git apply` каждого приложения подряд;
    список отказов `(пути, ответ git)`."""
    failures = []
    for appendix in appendices:
        for args in (["--check"], []):
            res = subprocess.run(["git", "apply", *args, "-"], cwd=tree,
                                 input=appendix.diff, capture_output=True,
                                 text=True)
            if res.returncode != 0:
                failures.append((appendix.paths, " ".join(args) or "apply",
                                 (res.stderr or res.stdout).strip()[:500]))
                break
    return failures


def run_invariants(tree: Path) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items()
           if key != config.ARTEL_ROLE_ENV}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", INVARIANTS_TEST, "-q",
         "-p", "no:cacheprovider", "-p", "xdist", "-n", str(WORKERS)],
        cwd=tree, env=env, capture_output=True, text=True, timeout=110)


class Invariant21AppendixTest(unittest.TestCase):

    def test_ac12_invariant21_appendix_applies_and_invariants_stay_green(self):
        """Приложение с правкой инварианта 21 ложится на код задачи, и инварианты зелёные.

        Сценарий: PLAN.md читается из ссылки документов задачи; среди его
        приложений есть правка строки 21 реестра `docs/invariants.md`,
        называющая каталог документов. Все приложения PLAN подряд проходят
        `git apply --check` и `git apply` на копии рабочей копии кода
        задачи; на этой копии `tests/test_invariants.py` зелёный.

        Ловит мутацию: приложения с правкой инварианта 21 нет (правка
        внесена прямо в ветку либо забыта); хунк приложения не совпадает
        с текущим текстом реестра — `git apply --check` отказывает;
        приложение к `tests/test_invariants.py` (или код задачи) ломает
        инварианты — модуль красный."""
        text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
        self.assertIsNotNone(text, f"PLAN.md не прочитан из ссылки: {reason}")
        appendices, errors = guard.plan_appendices(text)
        self.assertTrue(invariant21_edits(appendices), (
            f"в PLAN нет приложения, переписывающего строку 21 реестра "
            f"{INVARIANTS_DOC} с каталогом документов; приложения: "
            f"{[a.paths for a in appendices]}, ошибки разбора: {errors}"))

        tmp = tempfile.mkdtemp(prefix="artel-inv21-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tree = Path(tmp)
        copy_code_tree(CODE_ROOT, tree)

        failures = apply_in_order(tree, appendices)
        self.assertEqual(failures, [], "приложения PLAN не применились")

        res = run_invariants(tree)
        self.assertEqual(res.returncode, 0, (
            f"{INVARIANTS_TEST} с приложениями PLAN красный:\n"
            f"{(res.stdout + res.stderr)[-3000:]}"))


if __name__ == "__main__":
    unittest.main()
