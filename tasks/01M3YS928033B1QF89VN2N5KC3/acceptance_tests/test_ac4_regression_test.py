"""AC-4: новый файл регрессионного теста — красный до исправления, зелёный после.

Группа: разовый
Красен до реализации: ветка задачи ещё не добавила в `tests/` ни одного нового файла теста с «Ловит мутацию:» — кандидатов нет.

Кандидаты — файлы `tests/**/test_*.py`, добавленные веткой задачи от
точки расхождения с `origin/<основная>` (`gitcmd.diff_base`), в тексте
которых есть «Ловит мутацию:». Хотя бы один кандидат обязан:
- быть зелёным отдельным прогоном pytest в коде под проверкой;
- быть красным ПРОВАЛОМ теста (код pytest 1, не ошибка сбора) на коде
  базы: база ветки разворачивается во временный каталог (`git archive`),
  поверх кладутся новые файлы ветки под `tests/` (сам кандидат и его
  новые помощники), правки существующих файлов — нет.
"""
import io
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from _plank import REPO_ROOT, added_paths, diff_base, git, run_pytest, tail

MUTATION_LINE = "Ловит мутацию:"


def _extract(data: bytes, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)


class RegressionTestFileTest(unittest.TestCase):
    """Новый регрессионный тест воспроизводит причину детерминированно."""

    def setUp(self):
        self.base = diff_base()
        self.assertTrue(self.base, "база ветки задачи не вычислена")
        self.added_tests = [p for p in added_paths(self.base)
                            if p.startswith("tests/")
                            and (REPO_ROOT / p).is_file()]
        self.candidates = [
            p for p in self.added_tests
            if p.endswith(".py") and Path(p).name.startswith("test_")
            and MUTATION_LINE in (REPO_ROOT / p).read_text(encoding="utf-8")]

    def test_ac4_new_regression_file_red_on_base_green_now(self):
        """Хотя бы один новый тест-файл с заявкой мутации: база — красный, ветка — зелёный.

        Ловит мутацию: регрессионный тест не воспроизводит причину
        (зелёный и на базе — например, сам подменяет CLI так же, как
        исправление) либо красен и после исправления — ни один кандидат
        не проходит пару «красный/зелёный», тест красный с их выводом.
        """
        self.assertTrue(self.candidates,
                        "нет нового файла tests/**/test_*.py с "
                        f"«{MUTATION_LINE}» (добавлено в tests/: "
                        f"{self.added_tests})")
        archive = git("archive", "--format=tar", self.base)
        self.assertEqual(archive.returncode, 0,
                         archive.stderr.decode(errors="replace"))
        report = []
        with tempfile.TemporaryDirectory() as tdir:
            base_tree = Path(tdir) / "base"
            base_tree.mkdir()
            _extract(archive.stdout, base_tree)
            for rel in self.added_tests:
                target = base_tree / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / rel, target)
            for rel in self.candidates:
                now = run_pytest([rel])
                if now.returncode != 0:
                    report.append(f"{rel}: не зелёный на ветке "
                                  f"(код {now.returncode}):\n{tail(now)}")
                    continue
                before = run_pytest([rel], cwd=base_tree)
                if before.returncode == 1:
                    return
                report.append(f"{rel}: на базе код {before.returncode}, "
                              f"ожидался провал теста (1):\n{tail(before)}")
        self.fail("ни один кандидат не красный на базе и зелёный на "
                  "ветке:\n" + "\n".join(report))


if __name__ == "__main__":
    unittest.main()
