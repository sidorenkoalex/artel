"""Общий код планки задачи 01M3YJ7VQ7CSBBPC8X84Z0YG3R.

Источник — код под проверкой (корень, откуда импортирован пульт), база —
точка расхождения ветки с `origin/<основная ветка>` (`gitcmd.diff_base`).
"""
import ast
import importlib
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402

#: Корень кода, который сейчас проверяется (откуда импортирован пульт).
REPO = Path(config.__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CI_WAIT_FILE = "tests/test_merge_gate_ci_wait.py"
KIND_GATE_FILE = "tests/test_ci_status_kind_gate.py"
ISOLATION_FILE = "tests/test_merge_gate_clock_isolation.py"
PULT_FILE = "orchestrator/fsm_merge_gate.py"

#: Подстроки, по которым утверждение относится к часам теста (AC-2/AC-3).
CLOCK_MARKERS = ("sleep_calls", "clock.value", "monotonic")


def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True)


def base_source(case: unittest.TestCase, rel: str) -> str:
    """Текст `rel` в базе ветки задачи (точка расхождения с origin)."""
    base = gitcmd.diff_base("HEAD", repo=REPO)
    case.assertTrue(base, "база ветки задачи не вычислена")
    res = git("show", f"{base}:{rel}")
    case.assertEqual(res.returncode, 0,
                     f"{rel} нет в базе {base}: {res.stderr.strip()}")
    return res.stdout


def current_source(case: unittest.TestCase, rel: str) -> str:
    path = REPO / rel
    case.assertTrue(path.is_file(), f"{rel} нет в коде под проверкой")
    return path.read_text(encoding="utf-8")


def test_methods(source: str) -> dict[str, ast.FunctionDef]:
    """`Класс.метод` → узел для каждого тестового метода классов модуля."""
    found = {}
    for cls in ast.parse(source).body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for node in cls.body:
            if (isinstance(node, ast.FunctionDef)
                    and node.name.startswith("test")):
                found[f"{cls.name}.{node.name}"] = node
    return found


def clock_assertions(source: str) -> dict[str, list[str]]:
    """`Класс.метод` → утверждения `self.assert*(…)` на часы теста.

    Утверждение «на часы» — его нормализованный текст (`ast.unparse`)
    содержит одну из `CLOCK_MARKERS`; переформатирование строк на сверку
    не влияет."""
    out = {}
    for key, node in test_methods(source).items():
        found = []
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr.startswith("assert")):
                text = ast.unparse(sub)
                if any(m in text for m in CLOCK_MARKERS):
                    found.append(text)
        out[key] = sorted(found)
    return out


def missing_clock_assertions(base: str, now: str) -> list[str]:
    """Утверждения на часы из базы, которых нет в текущей версии файла
    (методы, пропавшие целиком, — тоже)."""
    before, after = clock_assertions(base), clock_assertions(now)
    missing = []
    for key, asserts in before.items():
        if key not in after:
            missing.append(f"{key}: метода нет")
            continue
        left = list(after[key])
        for text in asserts:
            if text in left:
                left.remove(text)
            else:
                missing.append(f"{key}: {text}")
    return missing


def global_time_patches(source: str) -> list[str]:
    """Подмены `sleep`/`monotonic` модуля `time` целиком в тексте файла:
    `patch.object(time, "sleep"|"monotonic", …)`, `patch("time.sleep")`,
    присваивание `time.sleep = …`."""
    found = []
    names = ("sleep", "monotonic")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = ast.unparse(node.func)
            args = node.args
            if (func.endswith("patch.object") and len(args) >= 2
                    and isinstance(args[0], ast.Name) and args[0].id == "time"
                    and isinstance(args[1], ast.Constant)
                    and args[1].value in names):
                found.append(f"строка {node.lineno}: {ast.unparse(node)}")
            if (func.endswith("patch") and args
                    and isinstance(args[0], ast.Constant)
                    and args[0].value in ("time.sleep", "time.monotonic")):
                found.append(f"строка {node.lineno}: {ast.unparse(node)}")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if ast.unparse(target) in ("time.sleep", "time.monotonic"):
                    found.append(f"строка {node.lineno}: {ast.unparse(node)}")
    return found


def run_probe(case: unittest.TestCase, module: str, cls_name: str, probe):
    """Разыгрывает `probe(test)` как тестовый метод подкласса `cls_name` из
    `module` — с его настоящими `setUp`/очисткой; возвращает словарь
    наблюдений probe. Ошибка `setUp`/probe — провал с трассой."""
    mod = importlib.import_module(module)
    observed: dict = {}

    def test_probe(self):
        observed.update(probe(self))

    sub = type(f"Probe{cls_name}", (getattr(mod, cls_name),),
               {"test_probe": test_probe})
    result = unittest.TestResult()
    sub("test_probe").run(result)
    problems = [tb for _t, tb in result.errors + result.failures]
    case.assertEqual(problems, [], "probe под часами теста упал")
    return observed


def run_pytest_file(case: unittest.TestCase, rel: str) -> None:
    """Файл `rel` кода под проверкой зелёный отдельным прогоном pytest."""
    res = subprocess.run(
        [sys.executable, "-m", "pytest", rel, "-p", "no:cacheprovider", "-q"],
        cwd=REPO, capture_output=True, text=True, timeout=600)
    case.assertEqual(res.returncode, 0,
                     f"{rel} не зелёный:\n{res.stdout[-4000:]}\n"
                     f"{res.stderr[-2000:]}")
