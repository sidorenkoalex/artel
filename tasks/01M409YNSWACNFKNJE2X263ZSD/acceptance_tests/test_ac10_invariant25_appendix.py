"""PLAN.md несёт применимое приложение с правкой инварианта 25.

Группа: разовый

Красен до реализации: в ссылке документов задачи нет PLAN.md (разработчик ещё не начинал), значит нет и приложения с правкой инварианта 25 — чтение PLAN из ссылки отказывает.

Группа «разовый»: предмет — PLAN.md этой задачи в ссылке документов и его
приложения; после мержа приложение применено, проверять его не на чем.

PLAN.md читается из ссылки документов `refs/artifacts/<id>`
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`), не с диска.
Приложения разбирает тот же узел, что гейт приложений PLAN
(`guard.plan_appendices`: разделы «## Приложение…», блоки ```diff).
Правка инварианта 25 узнаётся по строке таблицы реестра: среди приложений
к `docs/invariants.md` есть дифф, который убирает строку `| 25 | …` и
добавляет новую строку `| 25 | …`, где сказано, что репозиторий фиксации
упразднён (корень «упраздн»), и нет формулировки «грязная копия». Точную
формулировку тест не навязывает.

Применимость — исполнением: копия рабочей копии кода (файлы `git ls-files
--cached --others --exclude-standard` корня, в который выложена планка) во
временном каталоге со своим `git init`; каждое приложение PLAN по порядку —
`git apply --check`, затем `git apply` (так их кладёт мерж: подряд на одно
дерево). Подтверждение в самом PLAN — упоминание прогона `git apply
--check`.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _plank import CODE_ROOT, read_plan

from scripts import guard

INVARIANTS_DOC = "docs/invariants.md"
ROW_25 = "| 25 |"
ABOLISHED_STEM = "упраздн"
DIRTY_COPY = "грязная копия"
APPLY_CHECK = "git apply --check"


def invariant25_edits(appendices) -> list:
    """Приложения к `docs/invariants.md`, переписывающие строку 25 реестра:
    новая строка говорит об упразднении и не несёт «грязная копия»."""
    found = []
    for appendix in appendices:
        if INVARIANTS_DOC not in appendix.paths:
            continue
        lines = appendix.diff.splitlines()
        removed = any(line.startswith("-" + ROW_25) for line in lines)
        added = [line.lower() for line in lines if line.startswith("+" + ROW_25)]
        if removed and added and all(
                ABOLISHED_STEM in line and DIRTY_COPY not in line
                for line in added):
            found.append(appendix)
    return found


def copy_code_tree(src: Path, dest: Path) -> None:
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


class Invariant25AppendixTest(unittest.TestCase):

    def test_ac10_invariant25_appendix_applies(self):
        """Приложение с правкой инварианта 25 есть в PLAN, ложится на код задачи, и PLAN подтверждает `git apply --check`.

        Сценарий: PLAN.md читается из ссылки документов задачи; среди его
        приложений есть дифф к `docs/invariants.md`, переписывающий строку
        25 реестра: новая строка говорит об упразднении репозитория
        фиксации и не несёт «грязная копия». Все приложения PLAN подряд
        проходят `git apply --check` и `git apply` на копии рабочей копии
        кода; текст PLAN называет прогон `git apply --check`.

        Ловит мутацию: правка инварианта внесена прямо в ветку или забыта
        (приложения нет); новая строка 25 сохранила «грязная копия»; хунк
        не совпадает с текущим текстом реестра — `git apply --check`
        отказывает; PLAN не подтверждает проверку применимости.
        """
        text, reason = read_plan()
        self.assertIsNotNone(text, f"PLAN.md не прочитан из ссылки: {reason}")
        appendices, errors = guard.plan_appendices(text)
        self.assertTrue(invariant25_edits(appendices), (
            f"в PLAN нет приложения, переписывающего строку 25 реестра "
            f"{INVARIANTS_DOC} (упразднение, без «{DIRTY_COPY}»); приложения: "
            f"{[a.paths for a in appendices]}, ошибки разбора: {errors}"))
        self.assertIn(APPLY_CHECK, text,
                      "PLAN не подтверждает прогон git apply --check")

        tmp = tempfile.mkdtemp(prefix="artel-inv25-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tree = Path(tmp)
        copy_code_tree(CODE_ROOT, tree)

        failures = apply_in_order(tree, appendices)
        self.assertEqual(failures, [], "приложения PLAN не применились")


if __name__ == "__main__":
    unittest.main()
