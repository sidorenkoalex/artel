"""Отказы семи мест после переноса в `gitcmd`: истечение срока, значения
срока, потоковое чтение `ls-tree` с пределом, отказ запуска git (`OSError`).

Группа: разовый
Красен до реализации: места 2, 3, 5 и 1 ловят `TimeoutExpired` в своих кадрах (событие `exception` трассировки в `brief.py`/`reference_cache.py`/`acceptance.py`), а поток `ls-tree` (AC-4 место 4, AC-6) запускается из `reference_cache.py`, не из `gitcmd.py`; тесты AC-5 и AC-8 и проверки исходов держат прежнее поведение и зелены с рождения.

Истечение срока без ожидания по реальному времени: поддельный процесс
(`_places.FakeProc`) отвечает `TimeoutExpired` на первый `communicate`/
`wait` со сроком — так его видят и `subprocess.run(timeout=…)`, и
`Popen.communicate(timeout=…)`. Срок места 4 при чтении — единственное
место, где сроком служит сам вход (дедлайн `_list_tree`), а процесс
настоящий: исполняемый `git` в `PATH` пишет порцию и спит, поэтому
дедлайн короткий (0,5 с), а потолок `CORE_REFERENCE_GIT_TIMEOUT_SEC`
поднят, чтобы остановку дал именно остаток дедлайна.

Провалидировано временным стабом реализации (удалён, не закоммичен) —
все методы зелёные.
"""
import random
import subprocess
import sys
import tracemalloc
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _places  # noqa: E402
from _places import (GITCMD_FILE, FakeProc, Repo, deadline_in,  # noqa: E402
                     exceptions_in, fake_git_dir, git_launches, raising,
                     spy_popen)

from orchestrator import acceptance, brief, config, reference_cache, tz_check  # noqa: E402
from orchestrator.advance_gates import outcome_integrity  # noqa: E402

PLACE1_OWN = ("read-tree", "add", "rm", "write-tree")
REF_FILES = (reference_cache.__file__,)


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path)


def place1_own(argv) -> bool:
    return len(argv) > 3 and argv[0] == "git" and argv[3] in PLACE1_OWN


def every(argv) -> bool:
    return True


def timeouts_out(seen) -> list:
    """События `TimeoutExpired`, дошедшие до кадров места."""
    return [s for s in seen if s[1] == "TimeoutExpired"]


# --- AC-4 -----------------------------------------------------------------

def test_ac4_place1_timeout_gives_none_and_kills_git(repo):
    """Срок своей команды места 1 истёк — `suite_tree_hash` даёт `None`, git остановлен.

    `read-tree` места 1 отдаётся поддельному процессу: первый
    `communicate(timeout=…)` отвечает `TimeoutExpired`. Ожидается `None`,
    затем у процесса `kill` и дочитывание вывода (`communicate` после
    `kill`), дальше команды места не запускаются; `TimeoutExpired` в кадр
    `acceptance.py` не выходит.

    Ловит мутацию: отказ по сроку без `kill` — в событиях процесса нет
    `kill`, процесс git остаётся жить.
    """
    with spy_popen(place1_own, FakeProc) as log, \
            exceptions_in((acceptance.__file__,)) as seen:
        result = acceptance.suite_tree_hash(repo.path, worktree=False)
    assert result is None
    fakes = [r for r in git_launches(log) if place1_own(r.argv)]
    assert len(fakes) == 1
    events = fakes[0].events
    timed = next(i for i, e in enumerate(events)
                 if e[0] == "communicate" and e[1] is not None)
    assert ("kill",) in events[timed:]
    killed = events.index(("kill",), timed)
    assert ("communicate", None) in events[killed:]
    assert timeouts_out(seen) == []


@pytest.mark.parametrize("place", [2, 3])
def test_ac4_places_2_3_timeout_named_refusal(repo, place):
    """Срок git мест 2 и 3 истёк — прежний отказ «git не ответил (TimeoutExpired)».

    Запуск git отдаётся поддельному процессу с истекающим сроком; место
    возвращает `(None, "git не ответил (TimeoutExpired)")`, а
    `TimeoutExpired` через кадры `brief.py`/`reference_cache.py` не
    проходит — его разбирает `gitcmd`.

    Ловит мутацию: функция `gitcmd` пропускает `TimeoutExpired` наружу, а
    место ловит его само — событие `exception` с `TimeoutExpired` в кадре
    места.
    """
    module = brief if place == 2 else reference_cache
    with spy_popen(every, FakeProc), exceptions_in((module.__file__,)) as seen:
        if place == 2:
            result = brief._clone_git(repo.path, "show", f"{repo.head}:a.py")
        else:
            result = reference_cache.branch_commit(repo.path, "main")
    assert result == (None, "git не ответил (TimeoutExpired)")
    assert timeouts_out(seen) == []


def test_ac4_place4_deadline_while_reading(repo, tmp_path, monkeypatch):
    """Дедлайн `_list_tree` истёк во время чтения вывода — `DEADLINE` «срок исчерпан на ls-tree».

    Настоящий процесс `git` (скрипт в `PATH`) выдаёт порцию и спит;
    дедлайн — 0,5 с. Ожидается `_Failure` с кодом `DEADLINE` и причиной
    `"срок исчерпан на ls-tree"`, процесс убит, запуск пришёл из
    `gitcmd.py`, `TimeoutExpired` в кадр `reference_cache.py` не выходит.

    Ловит мутацию: функция `gitcmd` потока отдаёт истечение срока тем же
    исходом, что ненулевой код, — место отвечает `SOURCE_FAILED`
    «ls-tree …: код -9».
    """
    monkeypatch.setenv("PATH", f"{fake_git_dir(tmp_path, 'printf partial; exec /bin/sleep 30')}"
                       f":{_places.os.environ['PATH']}")
    with mock.patch.object(config, "CORE_REFERENCE_GIT_TIMEOUT_SEC", 600), \
            spy_popen() as log, exceptions_in(REF_FILES) as seen:
        with pytest.raises(reference_cache._Failure) as info:
            reference_cache._list_tree(repo.path, repo.head, deadline_in(0.5))
    assert (info.value.alert, info.value.detail) == (
        reference_cache.DEADLINE, "срок исчерпан на ls-tree")
    [launch] = git_launches(log)
    assert launch.launcher == GITCMD_FILE
    assert launch.proc.wait(timeout=10) < 0
    assert timeouts_out(seen) == []


def test_ac4_place4_timeout_at_start_is_source_failed(repo):
    """`TimeoutExpired` при запуске процесса `ls-tree` — `SOURCE_FAILED`, не `DEADLINE`.

    Запуск git падает `TimeoutExpired` ещё в конструкторе процесса.
    Ожидается `_Failure(SOURCE_FAILED, "ls-tree: TimeoutExpired: <текст>")`.

    Ловит мутацию: функция `gitcmd` сводит любой `TimeoutExpired` к
    именованному истечению срока — место отвечает `DEADLINE` «срок
    исчерпан на ls-tree».
    """
    exc = subprocess.TimeoutExpired(["git", "ls-tree"], 7)
    with spy_popen(every, raising(exc)):
        with pytest.raises(reference_cache._Failure) as info:
            reference_cache._list_tree(repo.path, repo.head, deadline_in(60))
    assert (info.value.alert, info.value.detail) == (
        reference_cache.SOURCE_FAILED, f"ls-tree: TimeoutExpired: {exc}")


def test_ac4_place5_timeout_is_deadline(repo):
    """Срок `cat-file --batch` истёк — `DEADLINE` «срок исчерпан на cat-file».

    Запуск отдаётся поддельному процессу с истекающим сроком; ожидается
    `_Failure` с кодом `DEADLINE` и причиной `"срок исчерпан на cat-file"`,
    `TimeoutExpired` в кадр `reference_cache.py` не выходит.

    Ловит мутацию: функция `gitcmd` отдаёт истечение срока как
    `OSError`-подобный отказ запуска — место отвечает `SOURCE_FAILED`
    «cat-file: …».
    """
    with spy_popen(every, FakeProc), exceptions_in(REF_FILES) as seen:
        with pytest.raises(reference_cache._Failure) as info:
            reference_cache._cat_blobs(repo.path, [repo.blob_a], deadline_in(60))
    assert (info.value.alert, info.value.detail) == (
        reference_cache.DEADLINE, "срок исчерпан на cat-file")
    assert timeouts_out(seen) == []


# --- AC-5 -----------------------------------------------------------------

def test_ac5_place1_timeout_is_15_seconds(repo):
    """Каждая своя команда места 1 запускается со сроком 15 с.

    Место 1 исполняется по-настоящему (рабочая копия и `base=True`) под
    шпионом: первый срок `communicate`/`wait` каждой своей команды — 15.

    Ловит мутацию: функция `gitcmd` места 1 берёт срок
    `config.CORE_REFERENCE_GIT_TIMEOUT_SEC` (60) — у команд срок 60.
    """
    with spy_popen() as log:
        acceptance.suite_tree_hash(repo.path)
        acceptance.suite_tree_hash(repo.path, base=True, worktree=False)
    own = [r for r in git_launches(log) if place1_own(r.argv)]
    assert len(own) == 5
    assert [r.first_timeout() for r in own] == [15] * 5


@pytest.mark.parametrize("place", [2, 3])
def test_ac5_places_2_3_timeout_from_config(repo, place):
    """Срок git мест 2 и 3 — текущее значение `config.CORE_REFERENCE_GIT_TIMEOUT_SEC`.

    Значение настройки подменяется случайным (зерно печатается), место
    исполняется по-настоящему; срок запуска равен подменённому значению.

    Ловит мутацию: в функцию `gitcmd` зашит срок 60 литералом или по
    умолчанию аргумента — подмена настройки не доходит до запуска.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    value = round(random.Random(seed).uniform(5, 500), 3)
    with mock.patch.object(config, "CORE_REFERENCE_GIT_TIMEOUT_SEC", value), \
            spy_popen() as log:
        if place == 2:
            brief._clone_git(repo.path, "show", f"{repo.head}:a.py")
        else:
            reference_cache.branch_commit(repo.path, "main")
    [launch] = git_launches(log)
    assert launch.first_timeout() == value, f"зерно: {seed}"


def test_ac5_place4_stops_at_remaining_deadline(repo, tmp_path, monkeypatch):
    """Поток места 4 останавливается по остатку дедлайна, а не по потолку настройки.

    Скрипт `git` в `PATH` выдаёт порцию и спит 30 с; потолок
    `CORE_REFERENCE_GIT_TIMEOUT_SEC` поднят до 600, дедлайн — 0,5 с.
    Процесс обязан быть убит (код возврата отрицательный), а не дожит до
    конца сна (код 0).

    Ловит мутацию: функция потока получает срок
    `config.CORE_REFERENCE_GIT_TIMEOUT_SEC` вместо остатка дедлайна —
    процесс доживает до конца сна с кодом 0.
    """
    monkeypatch.setenv("PATH", f"{fake_git_dir(tmp_path, 'printf partial; exec /bin/sleep 30')}"
                       f":{_places.os.environ['PATH']}")
    with mock.patch.object(config, "CORE_REFERENCE_GIT_TIMEOUT_SEC", 600), \
            spy_popen() as log:
        with pytest.raises(reference_cache._Failure):
            reference_cache._list_tree(repo.path, repo.head, deadline_in(0.5))
    [launch] = git_launches(log)
    assert launch.proc.wait(timeout=10) < 0


def test_ac5_place5_timeout_is_remaining_deadline(repo):
    """Срок `cat-file --batch` места 5 — остаток дедлайна.

    Дедлайн — случайное число секунд вперёд (зерно печатается); срок
    запуска не больше этого числа и меньше его не более чем на 5 с.

    Ловит мутацию: место 5 передаёт в `gitcmd` срок
    `config.CORE_REFERENCE_GIT_TIMEOUT_SEC` — срок 60 вне окна остатка.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    ahead = random.Random(seed).uniform(70, 400)
    with spy_popen() as log:
        reference_cache._cat_blobs(repo.path, [repo.blob_a], deadline_in(ahead))
    [launch] = git_launches(log)
    timeout = launch.first_timeout()
    assert timeout is not None and ahead - 5 < timeout <= ahead, f"зерно: {seed}"


@pytest.mark.parametrize("place", [6, 7])
def test_ac5_places_6_7_run_without_timeout(repo, place):
    """Места 6 и 7 запускают git без срока.

    Место исполняется по-настоящему; ни `communicate`, ни `wait` его
    запуска не получают срока.

    Ловит мутацию: при переносе место 7 получает срок
    `CORE_REFERENCE_GIT_TIMEOUT_SEC` — у `communicate` появляется срок.
    """
    with spy_popen() as log:
        if place == 6:
            tz_check._git(repo.path, "show", f"{repo.head}:a.py")
        else:
            outcome_integrity._added_lines(repo.path, repo.base, repo.head)
    [launch] = git_launches(log)
    assert launch.timeouts and all(t is None for t in launch.timeouts)


# --- AC-6 -----------------------------------------------------------------

def test_ac6_place4_over_limit_stops_git(repo, tmp_path, monkeypatch):
    """Вывод `ls-tree` сверх предела — `OVER_LIMITS`, процесс остановлен, вывод не копится.

    Скрипт `git` в `PATH` пишет бесконечно (`yes`); предел
    `CORE_REFERENCE_MAX_LISTING_BYTES` — случайный (зерно печатается).
    Ожидается `_Failure(OVER_LIMITS, "вывод ls-tree > <предел> байт")`,
    запуск из `gitcmd.py`, процесс завершён ненулевым кодом, пик памяти
    вызова — не больше нескольких пределов.

    Ловит мутацию: функция потока при переборе предела не убивает
    процесс, а дочитывает вывод до конца — бесконечный вывод упирается в
    дедлайн, место отвечает `DEADLINE`.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    limit = random.Random(seed).randrange(50_000, 400_000)
    monkeypatch.setenv("PATH", f"{fake_git_dir(tmp_path, 'exec /usr/bin/yes 0123456789abcdef')}"
                       f":{_places.os.environ['PATH']}")
    tracemalloc.start()
    try:
        with mock.patch.object(config, "CORE_REFERENCE_MAX_LISTING_BYTES", limit), \
                spy_popen() as log:
            with pytest.raises(reference_cache._Failure) as info:
                reference_cache._list_tree(repo.path, repo.head, deadline_in(20))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert (info.value.alert, info.value.detail) == (
        reference_cache.OVER_LIMITS, f"вывод ls-tree > {limit} байт"), f"зерно: {seed}"
    [launch] = git_launches(log)
    assert launch.launcher == GITCMD_FILE
    assert launch.proc.wait(timeout=10) != 0
    assert peak < 4 * limit + (1 << 20), f"пик {peak}, зерно: {seed}"


def test_ac6_place4_nonzero_exit_is_source_failed(repo, tmp_path, monkeypatch):
    """Ненулевой код возврата `ls-tree` — `SOURCE_FAILED` «ls-tree <sha>: код <код>».

    Скрипт `git` в `PATH` завершается случайным кодом (зерно печатается);
    ожидается прежний `_Failure(SOURCE_FAILED, "ls-tree <sha>: код <код>")`
    и запуск из `gitcmd.py`.

    Ловит мутацию: функция потока сводит ненулевой код к пустому выводу —
    место отвечает пустым списком записей без отказа.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    code = random.Random(seed).randrange(1, 120)
    monkeypatch.setenv("PATH", f"{fake_git_dir(tmp_path, f'exit {code}')}"
                       f":{_places.os.environ['PATH']}")
    with spy_popen() as log:
        with pytest.raises(reference_cache._Failure) as info:
            reference_cache._list_tree(repo.path, repo.head, deadline_in(60))
    assert (info.value.alert, info.value.detail) == (
        reference_cache.SOURCE_FAILED, f"ls-tree {repo.head}: код {code}"), f"зерно: {seed}"
    [launch] = git_launches(log)
    assert launch.launcher == GITCMD_FILE


# --- AC-8 -----------------------------------------------------------------

OS_ERRORS = [
    FileNotFoundError(2, "No such file or directory", "git"),
    PermissionError(13, "Permission denied", "git"),
    OSError(24, "Too many open files"),
]


@pytest.mark.parametrize("exc", OS_ERRORS, ids=lambda e: type(e).__name__)
def test_ac8_place1_oserror_escapes_suite_tree_hash(repo, exc):
    """`OSError` запуска своей команды места 1 выходит исключением из `suite_tree_hash`.

    Запуск `read-tree` места 1 падает `exc`; прочие git-вызовы настоящие.
    Ожидается то же исключение снаружи `suite_tree_hash`, не `None`.

    Ловит мутацию: функция `gitcmd` места 1 ловит `OSError` и отдаёт
    ненулевой код, как `gitcmd.git`, — `suite_tree_hash` возвращает `None`.
    """
    with spy_popen(place1_own, raising(exc)):
        with pytest.raises(type(exc)) as info:
            acceptance.suite_tree_hash(repo.path, worktree=False)
    assert str(info.value) == str(exc)


@pytest.mark.parametrize("exc", OS_ERRORS, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize("place", [2, 3])
def test_ac8_places_2_3_oserror_named_refusal(repo, place, exc):
    """`OSError` запуска git мест 2 и 3 — `(None, "git не ответил (<имя исключения>)")`.

    Ловит мутацию: функция `gitcmd` отдаёт `OSError` как ненулевой код с
    текстом в stderr — место 2 отвечает «git show: …», место 3 — «ветки
    main нет в клоне проекта».
    """
    with spy_popen(every, raising(exc)):
        if place == 2:
            result = brief._clone_git(repo.path, "show", f"{repo.head}:a.py")
        else:
            result = reference_cache.branch_commit(repo.path, "main")
    assert result == (None, f"git не ответил ({type(exc).__name__})")


@pytest.mark.parametrize("exc", OS_ERRORS, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize("place", [4, 5])
def test_ac8_places_4_5_oserror_source_failed(repo, place, exc):
    """`OSError` запуска git мест 4 и 5 — `SOURCE_FAILED` с именем и текстом исключения.

    Место 4 — `"ls-tree: <имя>: <текст>"`, место 5 —
    `"cat-file: <имя>: <текст>"`.

    Ловит мутацию: функция `gitcmd` места 5 сводит `OSError` к ненулевому
    коду — место отвечает «cat-file: код 1».
    """
    with spy_popen(every, raising(exc)):
        with pytest.raises(reference_cache._Failure) as info:
            if place == 4:
                reference_cache._list_tree(repo.path, repo.head, deadline_in(60))
            else:
                reference_cache._cat_blobs(repo.path, [repo.blob_a], deadline_in(60))
    word = "ls-tree" if place == 4 else "cat-file"
    assert (info.value.alert, info.value.detail) == (
        reference_cache.SOURCE_FAILED, f"{word}: {type(exc).__name__}: {exc}")


@pytest.mark.parametrize("exc", OS_ERRORS, ids=lambda e: type(e).__name__)
def test_ac8_place6_oserror_is_code_127(repo, exc):
    """`OSError` запуска git места 6 — результат с кодом 127 и текстом исключения в stderr.

    Ловит мутацию: функция `gitcmd` места 6 отдаёт код 1 (как
    `gitcmd.git`) — у результата `returncode` 1 вместо 127.
    """
    with spy_popen(every, raising(exc)):
        res = tz_check._git(repo.path, "show", f"{repo.head}:a.py")
    assert res.returncode == 127
    assert res.stderr == str(exc).encode()


@pytest.mark.parametrize("exc", OS_ERRORS, ids=lambda e: type(e).__name__)
def test_ac8_place7_oserror_is_prepare_refusal(repo, exc):
    """`OSError` запуска git места 7 — `_Prepare` с прежним текстом «diff -M -U0 … не получен: …».

    Ловит мутацию: функция `gitcmd` места 7 отдаёт `OSError` ненулевым
    кодом с пустым stderr — текст отказа «… git вернул код 1».
    """
    with spy_popen(every, raising(exc)):
        with pytest.raises(outcome_integrity._Prepare) as info:
            outcome_integrity._added_lines(repo.path, repo.base, repo.head)
    assert str(info.value) == (
        f"diff -M -U0 базы {repo.base[:12]} и головы {repo.head[:12]} "
        f"не получен: {exc}")
