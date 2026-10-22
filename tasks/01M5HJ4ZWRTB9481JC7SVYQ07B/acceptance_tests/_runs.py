"""Общий код планки: прогон pytest по файлу задачи и прогон под мутацией.

Мутация накладывается не на рабочую копию, а на её копию во временном
каталоге (без `.git`, `.artel`, `tasks/`): обрыв планки посреди прогона не
оставит мутированный `orchestrator/` в рабочей копии кода задачи.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

NEW_FILE = "tests/test_canary_parallel_protection.py"
NEIGHBOURS = ("tests/test_canary_parallel.py", "tests/test_canary_run_task.py")
LINT_NODE = "tests/test_invariants.py::DeterministicTestsLintTest"
INVARIANTS = "tests/test_invariants.py"

# Предел одного узла внутри вложенного pytest и общий предел ожидания —
# страховка от зависания, не условие проверки: оба ниже предела планки
# (120 с на тест), чтобы зависание вложенного прогона пришло красным
# утверждением, а не обрывом самой планки.
INNER_TIMEOUT = 95
WAIT_TIMEOUT = 110

_TOP_SKIP = {".git", ".artel", "tasks"}


def code_root() -> Path:
    return Path(CODE_ROOT)


def pytest_argv(*targets: str) -> list:
    return [sys.executable, "-m", "pytest", *targets, "-p", "no:cacheprovider",
            "-p", "timeout", "-o", f"timeout={INNER_TIMEOUT}", "-q"]


def run_pytest(cwd, *targets: str) -> subprocess.CompletedProcess:
    """Один последовательный прогон pytest по `targets` в каталоге `cwd`."""
    return subprocess.run(pytest_argv(*targets), cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=WAIT_TIMEOUT)


def tail(text: str, n: int = 3000) -> str:
    return text[-n:]


def _ignore(src: str, names: list) -> set:
    skip = {n for n in names if n == "__pycache__"}
    if Path(src).resolve() == code_root().resolve():
        skip |= {n for n in names if n in _TOP_SKIP}
    return skip


def copy_code(dst: Path) -> Path:
    """Копия рабочей копии кода задачи в `dst/w` (с незакоммиченным файлом
    задачи, без `.git`, `.artel` и `tasks/`)."""
    target = dst / "w"
    shutil.copytree(code_root(), target, ignore=_ignore, symlinks=True)
    return target


def mutate(root: Path, rel: str, old: str, new: str) -> None:
    """Заменяет единственное вхождение `old` в `root/rel` на `new`.

    Якорь не найден или не единственен — мутация не та, что названа в SPEC:
    отказ утверждением, а не тихий прогон немутированного кода."""
    path = root / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"якорь мутации в {rel} найден {count} раз(а), "
                             f"ожидался ровно один: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def collect_nodes(root: Path) -> list:
    res = subprocess.run(
        [sys.executable, "-m", "pytest", NEW_FILE, "--collect-only", "-q",
         "-p", "no:cacheprovider"], cwd=str(root), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=WAIT_TIMEOUT)
    nodes = [line.strip() for line in res.stdout.splitlines()
             if line.strip().startswith(NEW_FILE + "::")]
    if not nodes:
        raise AssertionError(f"в {NEW_FILE} не собрано ни одного теста "
                             f"(код {res.returncode}):\n{tail(res.stdout + res.stderr)}")
    return nodes


def run_nodes_parallel(root: Path) -> list:
    """Каждый тест файла задачи — отдельным процессом pytest, все сразу.

    Отдельный процесс на тест держит общий срок равным сроку самого долгого
    теста (под M20 — около `PARALLEL_STOP_GRACE_SEC`), а не их сумме.
    Возвращает [(узел, код возврата, вывод)]."""
    nodes = collect_nodes(root)
    logs = Path(tempfile.mkdtemp(prefix="plank-nodes-"))
    procs = []
    try:
        for i, node in enumerate(nodes):
            out = open(logs / f"{i}.log", "w+", encoding="utf-8")
            procs.append((node, out, subprocess.Popen(
                pytest_argv(node), cwd=str(root), stdout=out,
                stderr=subprocess.STDOUT, start_new_session=True)))
        deadline = time.monotonic() + WAIT_TIMEOUT
        results = []
        for node, out, proc in procs:
            try:
                code = proc.wait(timeout=max(1.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                for _, _, other in procs:
                    if other.poll() is None:
                        try:
                            os.killpg(other.pid, 9)
                        except ProcessLookupError:
                            pass
                        other.wait()
                raise AssertionError(f"вложенный прогон {node} не уложился в "
                                     f"{WAIT_TIMEOUT} с — тест повис")
            out.seek(0)
            results.append((node, code, out.read()))
        return results
    finally:
        for _, out, proc in procs:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, 9)
                except ProcessLookupError:
                    pass
                proc.wait()
            out.close()
        shutil.rmtree(logs, ignore_errors=True)


def _hung(output: str) -> bool:
    return "Timeout" in output and ("+++ Timeout" in output
                                    or "Failed: Timeout" in output)


def assert_all_green(results: list) -> None:
    bad = [(n, c, o) for n, c, o in results if c != 0]
    if bad:
        node, code, out = bad[0]
        raise AssertionError(f"без мутации тест {node} не зелёный (код {code}):\n"
                             f"{tail(out)}")


def assert_reddened(results: list, label: str) -> None:
    """Под мутацией `label` хотя бы один тест краснеет красным утверждением.

    Код вложенного pytest вне {0, 1} (прерывание `KeyboardInterrupt`, сбой
    сбора) и срабатывание таймаута pytest — не красное утверждение, а дефект
    теста (SPEC, требование 5)."""
    for node, code, out in results:
        if code not in (0, 1):
            raise AssertionError(f"мутация {label}: прогон {node} кончился кодом "
                                 f"{code}, не красным утверждением:\n{tail(out)}")
        if _hung(out):
            raise AssertionError(f"мутация {label}: тест {node} повис до таймаута "
                                 f"pytest вместо красного утверждения:\n{tail(out)}")
    if not any(code == 1 for _, code, _ in results):
        raise AssertionError(f"мутация {label} выжила: все {len(results)} тестов "
                             f"{NEW_FILE} зелёные")


def run_under_mutations(mutations, label: str) -> None:
    """Копия кода, наложение мутаций [(путь, старое, новое)], прогон файла
    задачи — хотя бы один тест обязан покраснеть."""
    tmp = Path(tempfile.mkdtemp(prefix="plank-mut-"))
    try:
        root = copy_code(tmp)
        for rel, old, new in mutations:
            mutate(root, rel, old, new)
        assert_reddened(run_nodes_parallel(root), label)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_unmutated_copy() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="plank-ctl-"))
    try:
        assert_all_green(run_nodes_parallel(copy_code(tmp)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
