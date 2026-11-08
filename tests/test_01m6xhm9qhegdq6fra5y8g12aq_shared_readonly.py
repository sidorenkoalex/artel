"""Общая фикстура только для чтения `tests.sandbox.shared_readonly` и её сторож.

Группа: долгоживущий
Красен до реализации: функции `shared_readonly` в `tests/sandbox.py` ещё нет — импорт модуля-образца в подпроцессе pytest падает, отчёт junit не несёт ожидаемых исходов.

Каждый тест пишет модуль-образец во временный каталог и прогоняет его
отдельным подпроцессом pytest с отчётом junit: исход тестов образца, их
порядок и ошибки подготовки и завершения видны только в отдельном прогоне.
Подпроцесс идёт с явным путём файла, с `PYTHONPATH` на корень дерева, с
пределом времени и в своей группе процессов; после каждого прогона тест
снимает эту группу целиком. Дочерние процессы образца — `/bin/sleep 30`
полным путём (в `PATH` шага роли `/bin` нет).
"""
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.sandbox import ALL_CONFIG_ATTRS


CODE_ROOT = Path(__file__).resolve().parent.parent
RUN_LIMIT_S = 100

HEADER = '''\
import os
import subprocess
from pathlib import Path

from orchestrator import config, store
from tests.sandbox import (OriginRealGitSandbox, RealGitSandbox,
                           shared_readonly)

OUT = Path(@OUT@)


def note(name, value):
    (OUT / name).write_text(str(value), encoding="utf-8")


def count_build():
    with open(OUT / "builds", "a", encoding="utf-8") as fh:
        fh.write("1\\n")
'''

# Модуль-образец сторожа: читающий тест, загрязняющий, два после него.
GUARD_SAMPLE = HEADER + '''

def build(sb):
    count_build()
    note("root", os.path.realpath(sb.root))
    (sb.root / "tracked.txt").write_text("abcdef\\n", encoding="utf-8")
    sb.git("add", "tracked.txt")
    sb.git("commit", "-q", "-m", "tracked")
    note("branch", sb.git("symbolic-ref", "--short", "HEAD").strip())
@BUILD@


shared = shared_readonly(@SANDBOX@, build)


def test_1_read(shared):
    shared.sandbox.git("status")


def test_2_pollute(shared):
    sb = shared.sandbox
@POLLUTE@


def test_3_after(shared):
    note("body_3", 1)


def test_4_after(shared):
    note("body_4", 1)
'''

READ_SAMPLE = HEADER + '''

def build(sb):
    count_build()
    tracked = sb.git("ls-files").split("\\n")[0]
    path = sb.root / tracked
    stat = path.stat()
    os.utime(path, (stat.st_atime - 1000, stat.st_mtime - 1000))
    note("tracked", tracked)


shared = shared_readonly(RealGitSandbox, build)


def read(shared):
    shared.sandbox.git("status")
    conn = store.db_readonly()
    try:
        conn.execute("SELECT name FROM sqlite_master").fetchall()
    finally:
        conn.close()


def test_1_read(shared):
    read(shared)


def test_2_read(shared):
    read(shared)


def test_3_read(shared):
    read(shared)
'''

LIVE_CHILD_SAMPLE = HEADER + '''

def build(sb):
    count_build()
    script = "echo $$ > " + str(OUT / "pid") + "; echo ready; exec /bin/sleep 30"
    proc = subprocess.Popen(["/bin/sh", "-c", script], stdout=subprocess.PIPE,
                            text=True)
    proc.stdout.readline()


shared = shared_readonly(RealGitSandbox, build)


def test_1_body(shared):
    note("body_1", 1)


def test_2_body(shared):
    note("body_2", 1)
'''

FAILING_CLEANUP_SAMPLE = HEADER + '''

def boom():
    raise RuntimeError(@TOKEN@)


class FailingCleanupSandbox(RealGitSandbox):
    def setUp(self):
        super().setUp()
        self.addCleanup(boom)


def build(sb):
    count_build()


shared = shared_readonly(FailingCleanupSandbox, build)


def test_1_read(shared):
    note("body_1", 1)


def test_2_read(shared):
    note("body_2", 1)
'''


def indent(lines: list[str]) -> str:
    return "\n".join("    " + line for line in lines) if lines else "    pass"


def run_sample(out: Path, text: str, env_extra=None, before_kill=None):
    """Пишет образец `out/sample_mod.py`, прогоняет его подпроцессом pytest
    и снимает группу процессов подпроцесса. `before_kill(proc)` — до снятия
    группы. Отдаёт (код выхода, {имя теста: [тексты <error>/<failure>]},
    {имя теста: [теги исходов]}, вывод)."""
    sample = out / "sample_mod.py"
    sample.write_text(text, encoding="utf-8")
    (out / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    report = out / "report.xml"
    env = dict(os.environ)
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST"):
        env.pop(name, None)
    env["PYTHONPATH"] = str(CODE_ROOT)
    env.update(env_extra or {})
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", str(sample), "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(out / "pytest.ini"), "--rootdir", str(out),
         f"--junitxml={report}", "-q"],
        cwd=str(out), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=RUN_LIMIT_S)
        if before_kill is not None:
            before_kill(proc)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if proc.poll() is None:
            proc.wait(timeout=10)
    errors: dict[str, list[str]] = {}
    outcomes: dict[str, list[str]] = {}
    if report.is_file():
        for case in ET.parse(report).getroot().iter("testcase"):
            name = case.get("name")
            errors.setdefault(name, [])
            outcomes.setdefault(name, [])
            for child in case:
                if child.tag in ("error", "failure", "skipped"):
                    outcomes[name].append(child.tag)
                    errors[name].append(
                        f"{child.get('message') or ''}\n{child.text or ''}")
    return proc.returncode, errors, outcomes, output


def read_note(out: Path, name: str) -> str:
    path = out / name
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


@pytest.fixture
def out_dir():
    with tempfile.TemporaryDirectory(prefix="shared-ro-sample-") as tmp:
        yield Path(tmp)


def test_ac1_reading_tests_share_one_build(out_dir):
    """Три читающих теста делят одну сборку и проходят без ошибок.

    `build` сдвигает время изменения отслеживаемого файла, так что первый
    `git status` переписывает индекс; каждый тест ещё и открывает БД пульта
    на чтение (`store.db_readonly`). Песочница несёт символьную ссылку
    `repo -> root` — обход каталога обязан завершиться. Счётчик сборок —
    строки файла-метки, а не `scope` фикстуры.

    Ловит мутацию: песочница строится на каждый тест (фикстура уровня
    функции без кэша модуля) — в файле-метке три строки вместо одной; либо
    отпечаток читает индекс побайтно / берёт время изменения файлов — после
    первого `git status` первый тест получает `<error>` при завершении,
    второй и третий — ошибку подготовки «загрязнено»; либо обход
    разыменовывает `repo -> root` — прогон зависает до предела и отчёта нет.
    """
    code, errors, outcomes, output = run_sample(
        out_dir, READ_SAMPLE.replace("@OUT@", repr(str(out_dir))))
    names = ["test_1_read", "test_2_read", "test_3_read"]
    assert sorted(outcomes) == names, output
    assert all(outcomes[n] == [] for n in names), (errors, output)
    assert code == 0, output
    assert (out_dir / "builds").read_text(encoding="utf-8").splitlines() \
        == ["1"], output


# (песочница, тело build после общей части, тело загрязнения, шаблон
# ожидаемого названия части). В шаблоне: {root} — настоящий путь корня,
# {origin} — настоящий путь голого origin, {branch} — ветка HEAD, {name},
# {other} — случайные имена прогона; {pid} — подставляется отдельно.
POLLUTION_CASES = {
    "new_row": ("RealGitSandbox", [], [
        'store.insert_task(store.db(), "T{num}", "x", "in_dev", "task/t", '
        '"artel", 1.0)',
    ], "таблица tasks"),
    "changed_row": ("RealGitSandbox", [
        '    store.insert_task(store.db(), "T{num}", "x", "in_dev", "task/t", '
        '"artel", 1.0)',
    ], [
        'store.update_task(store.db(), "T{num}", title="{name}")',
    ], "таблица tasks"),
    "new_commit": ("RealGitSandbox", [], [
        'sb.git("commit", "-q", "--allow-empty", "-m", "{name}")',
    ], "ссылка refs/heads/{branch} репозитория {root}"),
    "branch_and_tag": ("RealGitSandbox", [], [
        'sb.git("branch", "b-{name}")',
        'sb.git("tag", "t-{name}")',
    ], ("ссылка refs/heads/b-{name} репозитория {root}",
        "ссылка refs/tags/t-{name} репозитория {root}")),
    "origin_push": ("OriginRealGitSandbox", [
        '    note("origin", os.path.realpath(sb.add_origin()))',
        '    sb.git("push", "-q", "origin", "HEAD:refs/heads/main")',
    ], [
        'sb.git("commit", "-q", "--allow-empty", "-m", "{name}")',
        'sb.git("push", "-q", "origin", "HEAD:refs/heads/main")',
    ], "ссылка refs/heads/main репозитория {origin}"),
    "head_switch": ("RealGitSandbox", [
        '    sb.git("branch", "o-{name}")',
    ], [
        'sb.git("checkout", "-q", "o-{name}")',
    ], "HEAD репозитория {root}"),
    "index": ("RealGitSandbox", [], [
        '(sb.root / "tracked.txt").write_text("index {name}\\n", '
        'encoding="utf-8")',
        'sb.git("add", "tracked.txt")',
    ], "индекс репозитория {root}"),
    "worktree": ("RealGitSandbox", [], [
        '(sb.root / "tracked.txt").write_text("changed {name}\\n", '
        'encoding="utf-8")',
    ], "рабочее дерево репозитория {root}: tracked.txt"),
    "worktree_same_length": ("RealGitSandbox", [], [
        '(sb.root / "tracked.txt").write_text("abcdeg\\n", encoding="utf-8")',
    ], "рабочее дерево репозитория {root}: tracked.txt"),
    "untracked_same_length": ("RealGitSandbox", [
        '    (sb.root / "s-{name}.txt").write_text("aaaa", encoding="utf-8")',
    ], [
        '(sb.root / "s-{name}.txt").write_text("bbbb", encoding="utf-8")',
    ], "файл s-{name}.txt"),
    "new_file": ("RealGitSandbox", [], [
        '(sb.root / "n-{name}.txt").write_text("x", encoding="utf-8")',
    ], "файл n-{name}.txt"),
    "env_new": ("RealGitSandbox", [], [
        'os.environ["NEW_{upper}"] = "1"',
    ], "переменная окружения NEW_{upper}"),
    "env_changed": ("RealGitSandbox", [], [
        'os.environ["OLD_{upper}"] = "changed"',
    ], "переменная окружения OLD_{upper}"),
    "env_removed": ("RealGitSandbox", [], [
        'del os.environ["OLD_{upper}"]',
    ], "переменная окружения OLD_{upper}"),
    "cwd": ("RealGitSandbox", [], [
        '(OUT / "cwd-{name}").mkdir()',
        'os.chdir(OUT / "cwd-{name}")',
    ], "текущий каталог"),
    "config_attr": ("RealGitSandbox", [], [
        'config.{attr} = OUT / "elsewhere"',
    ], "атрибут config.{attr}"),
    "live_child": ("RealGitSandbox", [], [
        'proc = subprocess.Popen(["/bin/sleep", "30"])',
        'note("pid", proc.pid)',
    ], None),
}


def pollution_run(out: Path, case: str, rng: random.Random):
    """Прогоняет образец сторожа со случаем `case`; отдаёт (ожидаемые
    названия частей, ошибки junit, вывод)."""
    sandbox, build_lines, pollute_lines, expected = POLLUTION_CASES[case]
    name = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8))
    values = {"name": name, "upper": name.upper(), "num": rng.randint(100, 999),
              "attr": rng.choice(ALL_CONFIG_ATTRS)}
    text = (GUARD_SAMPLE.replace("@OUT@", repr(str(out)))
            .replace("@SANDBOX@", sandbox)
            .replace("@BUILD@", "\n".join(line.format(**values)
                                          for line in build_lines))
            .replace("@POLLUTE@", indent([line.format(**values)
                                          for line in pollute_lines])))
    env_extra = {f"OLD_{values['upper']}": "old"}
    code, errors, outcomes, output = run_sample(out, text, env_extra)
    facts = dict(values, root=read_note(out, "root"),
                 origin=read_note(out, "origin"),
                 branch=read_note(out, "branch"))
    if expected is None:
        patterns = [re.compile(rf"процесс {read_note(out, 'pid')} \S*sleep 30")]
    else:
        items = expected if isinstance(expected, tuple) else (expected,)
        patterns = [re.compile(re.escape(item.format(**facts)))
                    for item in items]
    return patterns, errors, output


@pytest.mark.parametrize("case", [
    "new_row", "changed_row", "new_commit", "branch_and_tag", "origin_push",
    "head_switch", "index", "worktree", "worktree_same_length",
    "untracked_same_length", "new_file", "env_new", "env_changed",
    "env_removed", "cwd", "config_attr", "live_child",
])
def test_ac2_pollution_named_and_spreads(out_dir, case):
    """Загрязняющий тест получает `<error>` с названием части, следующие — «загрязнено».

    Образец: читающий тест, загрязняющий (способ — случай), два после него.
    По отчёту junit: у второго теста есть `<error>` с ожидаемым названием
    части случая (настоящий путь репозитория — `os.path.realpath`, у
    `origin` — каталога голого `origin`); у третьего и четвёртого —
    `<error>` «общее состояние загрязнено тестом test_2_pollute», и их тела
    файлов-меток не оставили. Имена ветки, тега, файла, переменной и
    атрибут `config` выбираются случайно; зерно печатается.

    Ловит мутацию: отпечаток не снимает часть случая (таблицы БД, только
    число строк, окружение без значений, ссылки только HEAD, файлы без
    содержимого, процессы не перечислены, `config` не сверяется) — у второго
    теста нет `<error>` с названием части; либо названия расходятся с
    требованием 6 (путь `/var/…` вместо `/private/var/…`, имя ветки без
    `refs/heads/`) — названия нет в тексте; либо загрязнение не помечается
    для модуля — третий и четвёртый тесты исполняют тела и проходят.
    """
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    patterns, errors, output = pollution_run(out_dir, case, random.Random(seed))
    second = "\n".join(errors.get("test_2_pollute", []))
    for pattern in patterns:
        assert pattern.search(second), \
            f"зерно: {seed}; нет «{pattern.pattern}» в <error> второго теста:\n" \
            f"{second}\n{output}"
    for after in ("test_3_after", "test_4_after"):
        text = "\n".join(errors.get(after, []))
        assert "общее состояние загрязнено тестом" in text \
            and "test_2_pollute" in text, f"зерно: {seed}; {after}:\n{text}\n{output}"
    assert not (out_dir / "body_3").exists(), f"зерно: {seed}; {output}"
    assert not (out_dir / "body_4").exists(), f"зерно: {seed}; {output}"


def pid_alive(pid: int) -> bool:
    """Процесс `pid` жив (зомби — не жив)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    res = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(pid)],
                         capture_output=True, text=True, timeout=10)
    stat = res.stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def test_ac3_live_child_of_build_fails_and_is_killed(out_dir):
    """`build`, оставивший живой дочерний процесс, роняет построение фикстуры.

    Процесс образца пишет свой pid в файл-метку и ждёт `/bin/sleep 30`. Итог
    по отчёту junit: ошибка подготовки называет этот pid, тела тестов модуля
    не исполнены (файлов-меток тел нет, у каждого теста `<error>`). Сразу по
    завершении подпроцесса pytest и ДО того, как тест снимает его группу
    процессов, процесса с этим pid нет — значит, его убила уборка помощника.

    Ловит мутацию: помощник не сверяет дочерние процессы до и после `build`
    — тела тестов исполняются, файлы-метки тел есть; либо ошибка называет
    процессы без pid — pid в тексте нет; либо уборка не убивает процесс —
    `/bin/sleep 30` ещё жив, когда подпроцесс pytest уже завершился.
    """
    alive_after_run = {}

    def check(_proc):
        pid_text = read_note(out_dir, "pid")
        alive_after_run["pid"] = pid_text
        alive_after_run["alive"] = pid_text.isdigit() and pid_alive(int(pid_text))

    code, errors, outcomes, output = run_sample(
        out_dir, LIVE_CHILD_SAMPLE.replace("@OUT@", repr(str(out_dir))),
        before_kill=check)
    pid = alive_after_run["pid"]
    assert pid.isdigit(), output
    assert sorted(outcomes) == ["test_1_body", "test_2_body"], output
    first = "\n".join(errors["test_1_body"])
    assert re.search(rf"\b{pid}\b", first), f"{first}\n{output}"
    assert all("error" in outcomes[n] for n in outcomes), output
    assert not (out_dir / "body_1").exists(), output
    assert not (out_dir / "body_2").exists(), output
    assert alive_after_run["alive"] is False, output
    assert code != 0, output


def test_ac5_failing_cleanup_fails_module_teardown(out_dir):
    """Упавшая уборка песочницы роняет завершение модуля текстом действия.

    Песочница образца регистрирует действие уборки, которое бросает
    `RuntimeError` со случайной меткой; оба теста модуля проходят телом. По
    отчёту junit: завершение модуля (оно приходится на последний тест)
    несёт `<error>` с этой меткой, прогон не зелёный. Зерно печатается.

    Ловит мутацию: уборка глотает исключения действий (как `doCleanups()`
    вне раннера unittest) — `<error>` нет, код выхода 0; либо уборка идёт
    без сбора ошибок и текст подменён общим «уборка упала» без repr
    действия — метки нет в тексте.
    """
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    token = f"cleanup-broke-{random.Random(seed).randrange(10 ** 9)}"
    code, errors, outcomes, output = run_sample(
        out_dir, FAILING_CLEANUP_SAMPLE.replace("@OUT@", repr(str(out_dir)))
        .replace("@TOKEN@", repr(token)))
    assert sorted(outcomes) == ["test_1_read", "test_2_read"], output
    last = "\n".join(errors["test_2_read"])
    assert token in last, f"зерно: {seed}; {last}\n{output}"
    assert "error" in outcomes["test_2_read"], f"зерно: {seed}; {output}"
    assert (out_dir / "body_1").exists() and (out_dir / "body_2").exists(), output
    assert code != 0, f"зерно: {seed}; {output}"


def test_ac6_pollution_spreads_to_following_tests(out_dir):
    """Мутация «загрязнение не переходит на следующие тесты» краснеет.

    Образец: второй тест заводит новую переменную окружения. Тела третьего и
    четвёртого тестов не исполняются, оба несут `<error>` «общее состояние
    загрязнено тестом test_2_pollute». Зерно имени переменной печатается.

    Ловит мутацию: сторож роняет только завершение загрязнившего теста, а
    отметку загрязнения для модуля не ставит — третий и четвёртый тесты
    исполняют тела (файлы-метки тел появляются) и проходят без `<error>`.
    """
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    _patterns, errors, output = pollution_run(out_dir, "env_new",
                                              random.Random(seed))
    for after in ("test_3_after", "test_4_after"):
        text = "\n".join(errors.get(after, []))
        assert "общее состояние загрязнено тестом" in text, \
            f"зерно: {seed}; {after}:\n{text}\n{output}"
    assert not (out_dir / "body_3").exists(), f"зерно: {seed}; {output}"
    assert not (out_dir / "body_4").exists(), f"зерно: {seed}; {output}"
