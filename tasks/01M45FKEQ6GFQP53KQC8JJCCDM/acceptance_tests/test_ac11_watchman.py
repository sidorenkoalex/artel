"""AC-11: сторож требования 4 зелен на коде ветки и ловит вписанное прямое
сравнение с `config.DEFAULT_TARGET`, называя файл и строку.

Группа: разовый
Красен до реализации: сторожа требования 4 в `tests/` ещё нет — среди путей задачи нет нового теста, разбирающего `orchestrator/advance_gates/` и `orchestrator/fsm_merge_gate.py`.

Сторож — тест, который пишет разработчик (требование 4 SPEC); его имя
планке заранее не известно, поэтому он ищется среди путей задачи
(`changed_paths()` помощника пульта): файл `tests/**/test_*.py`, текст
которого называет и `advance_gates`, и `fsm_merge_gate`, и `DEFAULT_TARGET`.
Файл разовый: предмет — тест, добавленный этой задачей.

Мутация вписывается не в рабочую копию, а в её копию во временном каталоге
(без `.git`, `.artel` и `tasks/`): сторож разбирает исходники модулей
(требование 4), git ему не нужен. Прогон — тем же интерпретатором,
`python3 -m pytest <сторож>` с корнем копии рабочим каталогом.
"""
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

ROOT = Path(CODE_ROOT)
IGNORE = shutil.ignore_patterns(".git", ".artel", "tasks", "__pycache__",
                                ".pytest_cache", "node_modules")

# Формы прямого сравнения, которые сторож обязан узнать.
FORMS = (
    "    return target == config.DEFAULT_TARGET",
    "    return target != config.DEFAULT_TARGET",
    "    return config.DEFAULT_TARGET == target",
    "    if (target or config.DEFAULT_TARGET) != config.DEFAULT_TARGET:\n"
    "        return False\n    return True",
)


def watchman_files() -> list[str]:
    found = []
    for rel in changed_paths():
        path = ROOT / rel
        if not (rel.startswith("tests/") and path.name.startswith("test_")
                and rel.endswith(".py") and path.is_file()):
            continue
        text = path.read_text(encoding="utf-8")
        if all(w in text for w in ("advance_gates", "fsm_merge_gate",
                                    "DEFAULT_TARGET")):
            found.append(rel)
    return found


def run_pytest(root: Path, files: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *files, "-p", "no:cacheprovider",
         "-q", "-x"],
        cwd=root, capture_output=True, text=True, timeout=110)


class WatchmanTest(unittest.TestCase):

    def setUp(self):
        self.files = watchman_files()
        self.assertTrue(self.files, "среди путей задачи нет сторожа: теста "
                        "tests/**/test_*.py, разбирающего advance_gates и "
                        "fsm_merge_gate на сравнение с DEFAULT_TARGET")

    def test_ac11_watchman_green_on_branch_code(self):
        """Сторож проходит на коде ветки задачи.

        Сценарий: найденный сторож прогоняется pytest в самой рабочей копии
        задачи — модули проверок п.8 на ветке прямых сравнений не держат.

        Ловит мутацию: в `advance_gates/review.py` осталась прежняя развилка
        `target != config.DEFAULT_TARGET` заявки мутации — сторож падает на
        коде ветки, код возврата pytest ненулевой.
        """
        res = run_pytest(ROOT, self.files)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])

    def test_ac11_watchman_names_injected_comparison(self):
        """Вписанное сравнение валит сторожа с именем файла и номером строки.

        Сценарий: в копию рабочей копии в конец случайно выбранного модуля
        `orchestrator/advance_gates/*.py` и, отдельным прогоном, в конец
        `orchestrator/fsm_merge_gate.py` дописывается функция с прямым
        сравнением `config.DEFAULT_TARGET` случайной формы (`==`, `!=`,
        операнды в обратном порядке, сравнение значения по умолчанию).
        Сторож обязан упасть, а его вывод — назвать имя файла и строку
        вписанного сравнения. Зерно печатается и входит в текст провала.

        Ловит мутацию: сторож разбирает только `advance_gates/`, забыв
        `fsm_merge_gate.py`, либо узнаёт лишь форму `x == config.DEFAULT_TARGET`
        — прогон с другой формой или в другом файле проходит зелёным.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rnd = random.Random(seed)
        gates = sorted(p.name for p in (ROOT / "orchestrator" / "advance_gates")
                       .glob("*.py") if p.name != "__init__.py")
        targets = [f"orchestrator/advance_gates/{rnd.choice(gates)}",
                   "orchestrator/fsm_merge_gate.py"]
        for rel in targets:
            form = rnd.choice(FORMS)
            with tempfile.TemporaryDirectory() as tmp:
                copy = Path(tmp) / "code"
                shutil.copytree(ROOT, copy, ignore=IGNORE, symlinks=True)
                path = copy / rel
                text = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
                lines = text.count("\n")
                # Пустые строки 1..2, def — строка lines+3, сравнение — lines+4.
                path.write_text(text + "\n\ndef probe_injected_fork(target):\n"
                                + form + "\n", encoding="utf-8")
                lineno = lines + 4
                res = run_pytest(copy, self.files)
            out = res.stdout + res.stderr
            ctx = f"зерно {seed}, {rel}:{lineno}, форма {form!r}"
            self.assertNotEqual(res.returncode, 0,
                                f"сторож не упал ({ctx}):\n{out[-2000:]}")
            name = re.escape(Path(rel).name)
            self.assertRegex(out, rf"{name}\D{{0,60}}\b{lineno}\b",
                             f"вывод сторожа не называет файл и строку "
                             f"({ctx}):\n{out[-3000:]}")


if __name__ == "__main__":
    unittest.main()
