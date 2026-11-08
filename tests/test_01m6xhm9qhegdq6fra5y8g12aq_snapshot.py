"""Отпечаток общего состояния `tests.sandbox.shared_state_snapshot(sb) -> dict`.

Группа: долгоживущий
Красен до реализации: функции `shared_state_snapshot` в `tests/sandbox.py` ещё нет — импорт в первом вызове отпечатка падает `ImportError`.

Песочница — общая фикстура `real_git` (`RealGitSandbox` после `setUp()`):
отпечаток снимается в процессе теста, без подпроцесса pytest.
"""
import os
import random
from pathlib import Path

import pytest

from orchestrator import config, store


def shared_state_snapshot(sb) -> dict:
    """Публичный `tests.sandbox.shared_state_snapshot`; импорт — в вызове,
    чтобы файл собирался и до реализации (краснеет тест, а не сбор)."""
    from tests.sandbox import shared_state_snapshot as snapshot
    return snapshot(sb)


def test_ac4_two_snapshots_in_a_row_are_equal(real_git):
    """Два отпечатка подряд без действий между ними равны.

    Песочница `RealGitSandbox` сразу после `setUp()`: БД пульта с схемой,
    репозиторий с коммитом, символьная ссылка `repo -> root`.

    Ловит мутацию: отпечаток открывает БД на запись (`store.db()`) или зовёт
    `git status` без отказа от записи индекса — второй снимок видит новые
    файлы/иное содержимое; либо в отпечаток попал сам процесс `ps` (его pid
    свой у каждого снимка) — снимки не равны.
    """
    first = shared_state_snapshot(real_git)
    second = shared_state_snapshot(real_git)
    assert isinstance(first, dict)
    assert first == second


def test_ac4_snapshot_without_db_does_not_create_it(real_git):
    """Отпечаток песочницы без файла БД не создаёт файл БД.

    Тест удаляет файл БД пульта песочницы (`config.DB`, с его `-wal`/`-shm`)
    после `setUp()` и снимает отпечаток; файла БД после этого нет.

    Ловит мутацию: БД читается через `store.db()` или `sqlite3.connect` без
    `mode=ro` — соединение создаёт пустой файл `config.DB`.
    """
    db = Path(config.DB)
    for suffix in ("", "-wal", "-shm", "-journal"):
        extra = db.with_name(db.name + suffix)
        if extra.exists():
            extra.unlink()
    shared_state_snapshot(real_git)
    assert not db.exists()


def act_new_row(sb, rng, monkeypatch):
    conn = store.db()
    try:
        store.insert_task(conn, f"T{rng.randint(100, 999)}", "x", "in_dev",
                          "task/t", config.DEFAULT_TARGET, 1.0)
    finally:
        conn.close()


def prepare_existing_row(sb, rng, monkeypatch):
    conn = store.db()
    try:
        store.insert_task(conn, "T001", "before", "in_dev", "task/t",
                          config.DEFAULT_TARGET, 1.0)
    finally:
        conn.close()


def act_changed_row(sb, rng, monkeypatch):
    conn = store.db()
    try:
        store.update_task(conn, "T001", title=f"after-{rng.randrange(10 ** 6)}")
    finally:
        conn.close()


def act_env_new(sb, rng, monkeypatch):
    monkeypatch.setenv(f"SNAPSHOT_NEW_{rng.randrange(10 ** 6)}", "1")


def prepare_env_existing(sb, rng, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_EXISTING", "before")


def act_env_changed(sb, rng, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_EXISTING", f"after-{rng.randrange(10 ** 6)}")


def act_new_tag(sb, rng, monkeypatch):
    sb.git("tag", f"t-{rng.randrange(10 ** 6)}")


def prepare_untracked(sb, rng, monkeypatch):
    (sb.root / "scratch.txt").write_text("aaaa", encoding="utf-8")


def act_untracked_same_length(sb, rng, monkeypatch):
    letter = rng.choice("bcdefghijk")
    (sb.root / "scratch.txt").write_text(letter * 4, encoding="utf-8")


def nothing(sb, rng, monkeypatch):
    pass


# Мутация AC-6 -> (подготовка до первого снимка, действие между снимками).
MUTATIONS = {
    "отпечаток не снимает таблицы БД": (nothing, act_new_row),
    "БД — только число строк таблицы": (prepare_existing_row, act_changed_row),
    "отпечаток не видит окружение процесса": (nothing, act_env_new),
    "окружение — только имена переменных": (prepare_env_existing,
                                            act_env_changed),
    "ссылки — только HEAD": (nothing, act_new_tag),
    "файлы — путь и размер без содержимого": (prepare_untracked,
                                             act_untracked_same_length),
}


@pytest.mark.parametrize("mutation", [
    "отпечаток не снимает таблицы БД",
    "БД — только число строк таблицы",
    "отпечаток не видит окружение процесса",
    "окружение — только имена переменных",
    "ссылки — только HEAD",
    "файлы — путь и размер без содержимого",
])
def test_ac6_snapshot_sees_change_missed_by_mutation(real_git, monkeypatch,
                                                     mutation):
    """Изменение, невидимое мутированному отпечатку, меняет настоящий отпечаток.

    Для каждой мутации AC-6 — действие, которое мутированный отпечаток не
    различит: новая строка таблицы; новое значение в существующей строке
    (число строк прежнее); новая переменная окружения; новое значение
    существующей переменной (имена прежние); новый тег (HEAD прежний);
    неотслеживаемый файл переписан той же длиной. Отпечатки до и после
    действия различаются. Значения случайны, зерно печатается.

    Ловит мутацию: та, что названа параметром, — после неё оба снимка равны
    и тест краснеет (таблицы не сняты; БД — только число строк; окружение
    не снято; окружение — только имена; ссылки — только HEAD; файлы — путь
    и размер без содержимого).
    """
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    prepare, act = MUTATIONS[mutation]
    prepare(real_git, rng, monkeypatch)
    before = shared_state_snapshot(real_git)
    act(real_git, rng, monkeypatch)
    after = shared_state_snapshot(real_git)
    assert before != after, f"зерно: {seed}; мутация «{mutation}» не видна"


def test_ac6_index_compared_by_ls_files_not_bytes(real_git):
    """`git status`, переписавший устаревший индекс, не меняет отпечаток.

    Тест сдвигает время изменения отслеживаемого файла (`os.utime`) без
    правки содержимого, снимает отпечаток, зовёт `git status` (он
    переписывает индекс — тест проверяет это по байтам `.git/index` как
    предпосылку) и снимает отпечаток снова: отпечатки равны. Сдвиг времени
    случаен, зерно печатается.

    Ловит мутацию: «отпечаток читает индекс побайтно» — байты индекса после
    `git status` иные, снимки различаются.
    """
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    shift = random.Random(seed).randint(1000, 100000)
    tracked = real_git.git("ls-files").split("\n")[0]
    path = real_git.root / tracked
    stat = path.stat()
    os.utime(path, (stat.st_atime - shift, stat.st_mtime - shift))
    index = real_git.root / ".git" / "index"
    index_before = index.read_bytes()
    before = shared_state_snapshot(real_git)
    real_git.git("status")
    assert index.read_bytes() != index_before, f"зерно: {seed}; индекс не переписан"
    after = shared_state_snapshot(real_git)
    assert before == after, f"зерно: {seed}"
