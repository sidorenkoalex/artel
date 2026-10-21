"""AC-8: новые тесты задачи — без сна, без циклов по часам, без сети; сигнал себе — только после проверки обработчика; без настоящего реестра и журналов пульта.

Группа: разовый
Зелёный с рождения: до реализации новые тесты задачи — только эта планка, написанная по тем же правилам; тест краснеет, если разработчик добавит в `tests/` новый тест-файл, нарушающий правило.

Почему разовый: проверяемый перечень — новые тесты ЭТОЙ задачи: файлы
планки рядом с этим файлом и файлы `tests/*.py`, добавленные диффом задачи
(`changed_paths()` помощника пульта, отсутствующие в базе `DIFF_BASE`).

Проверка — разбором текста (`ast`), без исполнения:
- вызов `sleep(…)`/`time.sleep(…)` с аргументом, отличным от литерала 0;
- цикл `while`, в условии или теле которого читаются часы (`time.time`,
  `time.monotonic`, `time.perf_counter`, `datetime.now`);
- сеть: импорт `socket`, `requests`, `urllib.request`, `http.client`,
  `urllib3`, вызов `socket.socket`/`create_connection`/`urlopen`;
- `os.kill(os.getpid(), …)` — в той же функции раньше по тексту стоит
  вызов `signal.getsignal`, а между ними — `raise`/`self.fail`/`assert…`
  (падение без отправки);
- файл, обращающийся к реестру живого прогона или каталогу журналов при
  исполнении (вызов `live_runs`/`live_run_note`/`live_marks`/
  `registry_view`/`_live_dir`/`cmd_canary_live`/`artel.main`, атрибут
  `CANARY_LIVE_DIRNAME`/`LOGS`), обязан строиться на песочнице
  `tests.sandbox` (импорт из неё) либо подменять `_live_dir`/`config.ROOT`
  (`mock.patch.object(…, "_live_dir" | "ROOT", …)`).
"""
import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

HERE = Path(__file__).resolve().parent
CLOCKS = {("time", "time"), ("time", "monotonic"), ("time", "perf_counter"),
          ("datetime", "now")}
NET_MODULES = ("socket", "requests", "urllib.request", "http.client", "urllib3")
NET_CALLS = {"create_connection", "urlopen"}
#: Обращения к реестру и журналам пульта при исполнении: вызовы и атрибуты.
REGISTRY_CALLS = {"live_runs", "live_run_note", "live_marks", "registry_view",
                  "_live_dir", "cmd_canary_live", "artel.main"}
REGISTRY_ATTRS = {"CANARY_LIVE_DIRNAME", "LOGS"}


def dotted(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    return ""


def tail2(node) -> tuple:
    name = dotted(node)
    parts = name.split(".")
    return tuple(parts[-2:]) if len(parts) >= 2 else (None, name)


def new_test_files() -> list:
    files = sorted(p for p in HERE.glob("*.py") if p.name != "_pult.py")
    for rel in changed_paths():
        if not (rel.startswith("tests/") and rel.endswith(".py")):
            continue
        path = Path(CODE_ROOT) / rel
        if not path.is_file():
            continue
        known = subprocess.run(["git", "-C", str(CODE_ROOT), "cat-file", "-e",
                                f"{DIFF_BASE}:{rel}"], capture_output=True)
        if known.returncode != 0:
            files.append(path)
    return files


def violations(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            if name.split(".")[-1] == "sleep" and name in ("sleep", "time.sleep"):
                arg = node.args[0] if node.args else None
                if not (isinstance(arg, ast.Constant) and arg.value == 0):
                    found.append(f"{path.name}:{node.lineno}: {name} с ненулевым сроком")
            if name.split(".")[-1] in NET_CALLS or name == "socket.socket":
                found.append(f"{path.name}:{node.lineno}: сеть — {name}")
        if isinstance(node, ast.While):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and tail2(sub.func) in CLOCKS:
                    found.append(f"{path.name}:{node.lineno}: цикл по часам")
                    break
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in NET_MODULES:
                    found.append(f"{path.name}:{node.lineno}: сеть — import {alias.name}")
        if isinstance(node, ast.ImportFrom) and (node.module or "") in NET_MODULES:
            found.append(f"{path.name}:{node.lineno}: сеть — from {node.module}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found += self_signal_violations(path, node)
    if touches_registry(tree) and not sandboxed(tree):
        found.append(f"{path.name}: реестр/журналы без песочницы tests.sandbox "
                     f"и без подмены _live_dir/config.ROOT")
    return found


def touches_registry(tree) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (
                dotted(node.func).split(".")[-1] in REGISTRY_CALLS
                or dotted(node.func) in REGISTRY_CALLS):
            return True
        if isinstance(node, ast.Attribute) and node.attr in REGISTRY_ATTRS:
            return True
    return False


def sandboxed(tree) -> bool:
    """Импорт из `tests.sandbox` либо подмена `_live_dir`/`ROOT` строкой имени."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("tests.sandbox", "tests"):
            return True
        if (isinstance(node, ast.Call) and dotted(node.func).split(".")[-1] == "object"
                and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in ("_live_dir", "ROOT")):
            return True
    return False


def self_signal_violations(path: Path, func) -> list:
    out = []
    calls = sorted((n for n in ast.walk(func) if isinstance(n, ast.Call)),
                   key=lambda n: (n.lineno, n.col_offset))
    for call in calls:
        if dotted(call.func) != "os.kill" or not call.args:
            continue
        target = call.args[0]
        if not (isinstance(target, ast.Call) and dotted(target.func) == "os.getpid"):
            continue
        checks = [n for n in calls if dotted(n.func) == "signal.getsignal"
                  and n.lineno < call.lineno]
        if not checks:
            out.append(f"{path.name}:{call.lineno}: os.kill(os.getpid()) без "
                       f"signal.getsignal перед ним")
            continue
        first = checks[0].lineno
        fails = [n for n in ast.walk(func)
                 if first <= getattr(n, "lineno", 0) < call.lineno
                 and (isinstance(n, (ast.Raise, ast.Assert))
                      or (isinstance(n, ast.Call)
                          and dotted(n.func).split(".")[-1].startswith(("fail", "assert"))))]
        if not fails:
            out.append(f"{path.name}:{call.lineno}: проверка обработчика без "
                       f"падения до отправки сигнала")
    return out


class TestHygieneTest(unittest.TestCase):
    """Тексты новых тестов задачи — планки и новых файлов `tests/`."""

    def test_ac8_new_tests_follow_determinism_rules(self):
        """Каждый новый тест-файл задачи разбирается и проверяется на сон, часы, сеть, сигнал себе и настоящий реестр.

        Наблюдение: перечень нарушений пуст; перечень файлов непуст (в нём
        как минимум файлы планки).

        Ловит мутацию: разработчик добавляет в `tests/` тест подкоманды,
        который ждёт ребёнка `time.sleep(0.1)` в цикле до срока по
        `time.monotonic()`, шлёт себе SIGTERM без проверки обработчика или
        пишет в `config.ROOT` без песочницы — перечень нарушений не пуст.
        """
        files = new_test_files()
        self.assertTrue(files, "новых тест-файлов задачи не найдено")
        found = []
        for path in files:
            found += violations(path)
        self.assertEqual(found, [], "\n".join(found))

    def test_ac8_checker_flags_known_violations(self):
        """Сама проверка ловит заведомые нарушения на образцовом тексте.

        Ловит мутацию: разбор не находит `time.sleep(0.5)`, цикл до срока
        по `time.monotonic()`, `import socket` или `os.kill(os.getpid(), …)`
        без `signal.getsignal` — проверка новых тестов пропускает их молча.
        """
        sample_text = (
            "import os, time, socket\n"
            "from orchestrator import canary\n"
            "def f():\n"
            "    time.sleep(0.5)\n"
            "    while time.monotonic() < 5:\n"
            "        pass\n"
            "    os.kill(os.getpid(), 15)\n"
            "    canary.live_runs()\n")
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "test_sample.py"
            sample.write_text(sample_text, encoding="utf-8")
            found = violations(sample)
        for part in ("ненулевым сроком", "цикл по часам", "import socket",
                     "без signal.getsignal", "без песочницы"):
            self.assertTrue([f for f in found if part in f], f"{part}: {found}")


if __name__ == "__main__":
    unittest.main()
