"""Правка инварианта 25 `docs/invariants.md` или `tests/test_invariants.py`
— только приложением к PLAN.md, проходящим `git apply --check`.

Группа: разовый

Красен до реализации: в ссылке документов задачи нет PLAN.md (разработчик ещё не начинал) — чтение PLAN из ссылки отказывает.

Группа «разовый»: предмет — дифф ветки и PLAN.md этой задачи; после мержа
проверять не на чем.

PLAN.md читается из ссылки документов `refs/artifacts/<id>`
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`), не с диска.
Приложения разбирает тот же узел, что гейт приложений PLAN
(`guard.plan_appendices`: разделы «## Приложение…», блоки ```diff).
Критерий условный: приложения к этим двум файлам может и не быть — тогда
проверять нечего, кроме того, что ветка не правит их напрямую. Если
приложение есть — PLAN называет прогон `git apply --check`, а все
приложения PLAN подряд проходят `git apply --check` и `git apply` на
копии рабочей копии кода (файлы `git ls-files --cached --others
--exclude-standard`) со своим `git init`.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _plank import CODE_ROOT, diff_base, git, read_plan

from scripts import guard

GUARDED = ("docs/invariants.md", "tests/test_invariants.py")
APPLY_CHECK = "git apply --check"


def copy_code_tree(src: Path, dest: Path) -> None:
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard",
                 cwd=src)
    assert listed.returncode == 0, listed.stderr
    for rel in filter(None, listed.stdout.split("\0")):
        source = src / rel
        if not source.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    res = git("init", "-q", cwd=dest)
    assert res.returncode == 0, res.stderr


def apply_in_order(tree: Path, appendices) -> list:
    failures = []
    for appendix in appendices:
        for args in (["--check"], []):
            res = git("apply", *args, "-", cwd=tree, input=appendix.diff)
            if res.returncode != 0:
                failures.append((appendix.paths, " ".join(args) or "apply",
                                 (res.stderr or res.stdout).strip()[:500]))
                break
    return failures


class InvariantsAppendixTest(unittest.TestCase):

    def test_ac12_invariants_edit_only_as_checked_appendix(self):
        """Правка инварианта 25 или `tests/test_invariants.py` — только приложением PLAN, применимым и подтверждённым `git apply --check`.

        Сценарий: дифф ветки от базы не трогает `docs/invariants.md` и
        `tests/test_invariants.py`; PLAN.md читается из ссылки документов;
        если среди его приложений есть дифф к одному из этих файлов — текст
        PLAN называет прогон `git apply --check`, и все приложения PLAN
        подряд ложатся на копию рабочей копии кода.

        Ловит мутацию: правка реестра или `test_invariants.py` внесена
        прямо в ветку, а не приложением; приложение есть, но хунк не
        совпадает с текущим текстом файла (`git apply --check` отказывает);
        PLAN не подтверждает проверку применимости.
        """
        base = diff_base()
        self.assertTrue(base, "база диффа ветки задачи не вычислена")
        res = git("diff", "--name-only", base, "--", *GUARDED)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.split(), [],
                         "ветка правит реестр/test_invariants.py напрямую, "
                         "а не приложением к PLAN")

        text, reason = read_plan()
        self.assertIsNotNone(text, f"PLAN.md не прочитан из ссылки: {reason}")
        appendices, errors = guard.plan_appendices(text)
        touching = [a for a in appendices
                    if any(path in GUARDED for path in a.paths)]
        if not touching:
            return
        self.assertIn(APPLY_CHECK, text,
                      "PLAN не подтверждает прогон git apply --check")

        tmp = tempfile.mkdtemp(prefix="artel-inv25-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tree = Path(tmp)
        copy_code_tree(CODE_ROOT, tree)
        failures = apply_in_order(tree, appendices)
        self.assertEqual(failures, [], f"приложения PLAN не применились; "
                                       f"ошибки разбора: {errors}")


if __name__ == "__main__":
    unittest.main()
