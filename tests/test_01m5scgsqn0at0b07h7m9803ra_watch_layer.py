"""Надзор главной копии пульта за локальным слоем `.artel/targets.yaml`: сумма файла на старте шага и сверка после шага.

Группа: долгоживущий
Красен до реализации: у `checkpoint.MainCopyWatch` нет поля `local_layer_digest`, а `watch_main_copy` не сверяет сумму локального слоя — правка игнорируемого git файла проходит без предупреждения.

Связка, которую держит файл: «файл локального слоя — снимок
`main_copy_watch_start` — сверка `watch_main_copy` — таблица алертов» на
настоящем git песочницы (фикстура `real_git`, `tests.sandbox.RealGitSandbox`):
каталог `.artel/` песочницы git не отслеживает, поэтому правка файла слоя
не меняет строк `git status` — видна она только по сумме. Файл слоя —
`config.TARGETS.parent / ".artel" / "targets.yaml"` (требование 1).
Содержимое файла — от зерна `random`; зерно печатается и входит в текст
провала.
"""
import random
import subprocess
from unittest import mock

import pytest

from orchestrator import alerts, checkpoint, config, store

LETTERS = "abcdefghijkmnopqrstuvwxyz"
TASK = "01TASKLAYERWATCH"


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def layer_text(rng: random.Random) -> str:
    name = "p" + "".join(rng.choice(LETTERS) for _ in range(6))
    return f"targets:\n  {name}:\n    description:\n      base: {name}\n"


def watch_alerts(conn) -> list:
    return [row["message"] for row in alerts.open_alerts(conn)
            if row["source"] == checkpoint.MAIN_COPY_WATCH_SOURCE]


@pytest.mark.parametrize("change", ["изменение", "появление", "удаление"])
def test_ac14_layer_change_raises_watch_alert(real_git, seed, change):
    """Правка `.artel/targets.yaml` за время шага — предупреждение `MAIN_COPY_WATCH_SOURCE` с этим путём в списке изменений.

    Сценарий: старт шага записан в журнал, снимок `main_copy_watch_start`
    снят при файле слоя (для «изменение»/«удаление») или без него (для
    «появление»); затем файл переписан другим текстом, создан или удалён.
    `watch_main_copy` возвращает истину, открыт ровно один алерт источника
    `MAIN_COPY_WATCH_SOURCE`, в его тексте — `.artel/targets.yaml`.

    Ловит мутацию: сумма слоя не снимается на старте или не сверяется
    после шага; появление или исчезновение файла (сумма `None` с одной
    стороны) не считается изменением.
    """
    rng = random.Random(seed)
    conn = store.db()
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if change != "появление":
        path.write_text(layer_text(rng), encoding="utf-8")
    store.journal(conn, TASK, "developer", "agent run started", "")
    watch = checkpoint.main_copy_watch_start(conn, TASK)
    assert watch is not None
    if change == "удаление":
        path.unlink()
    else:
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        text = layer_text(rng)
        while text == before:
            text = layer_text(rng)
        path.write_text(text, encoding="utf-8")
    assert checkpoint.watch_main_copy(conn, TASK, "developer", watch), f"зерно: {seed}"
    messages = watch_alerts(conn)
    assert len(messages) == 1, f"зерно: {seed}; {messages}"
    assert ".artel/targets.yaml" in messages[0], f"зерно: {seed}; {messages}"


@pytest.mark.parametrize("present", [True, False])
def test_ac14_unchanged_layer_no_alert_no_extra_calls(real_git, seed, present):
    """Файл слоя за время шага не менялся — предупреждения нет, процессов сверх одного `git status` сверка не запускает.

    Сценарий: снимок снят при файле слоя (или без него), файл не тронут.
    `watch_main_copy` возвращает ложь, алертов источника
    `MAIN_COPY_WATCH_SOURCE` нет, за сверку запущен ровно один процесс —
    прежний `git status` главной копии.

    Ловит мутацию: сумма сравнивается с путём или временем правки и
    расходится без правки — ложное предупреждение; сумма считается
    внешним процессом или повторным `git status`.
    """
    rng = random.Random(seed)
    conn = store.db()
    path = local_file()
    if present:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(layer_text(rng), encoding="utf-8")
    store.journal(conn, TASK, "developer", "agent run started", "")
    watch = checkpoint.main_copy_watch_start(conn, TASK)
    assert watch is not None
    real_run = subprocess.run
    with mock.patch.object(subprocess, "run", side_effect=real_run) as spy:
        raised = checkpoint.watch_main_copy(conn, TASK, "developer", watch)
    assert raised is False, f"зерно: {seed}"
    assert watch_alerts(conn) == []
    assert spy.call_count == 1, f"зерно: {seed}; {spy.call_args_list}"


def test_ac14_old_constructor_form_has_no_digest(seed):
    """`MainCopyWatch(...)` прежней формы (без `local_layer_digest`) строится, поле — `None`.

    Сценарий: снимок строится тремя прежними аргументами (id старта,
    время, строки статуса) — позиционно и по именам; у обоих
    `local_layer_digest is None`, прежние поля — переданные значения.

    Ловит мутацию: поле добавлено без значения по умолчанию или не
    последним — прежний вызов конструктора падает `TypeError` или
    кладёт строки статуса в сумму.
    """
    status = frozenset({f"?? f{seed}.txt"})
    for watch in (checkpoint.MainCopyWatch(seed, "2026-01-01 00:00:00Z", status),
                  checkpoint.MainCopyWatch(start_id=seed, start_ts="2026-01-01 00:00:00Z",
                                           status=status)):
        assert watch.local_layer_digest is None
        assert watch.status == status and watch.start_id == seed
