"""Сообщение коммита пульта `gitcmd.pult_message` по записи проекта с полем `policy.commit_trailer`, с пустым полем и без поля.

Группа: разовый
Красен до реализации: поля `commit_trailer` нет в `targets.LOCAL_FIELDS` — запись с ним не загружается, `pult_message` молча берёт пустую запись и дописывает `Artel-Actor: orchestrator`; методы AC-3 зелены с рождения — они закрепляют прежнее сообщение записи без поля.

Группа «разовый» здесь — вынужденная: свойство — код, но долгоживущему
файлу `tests/` guard закрывает импорт `orchestrator.gitcmd` (признак
«git-модуль»), а `pult_message` живёт там. Загрузку поля и `target-set`
держит долгоживущий файл задачи в `tests/`.

Связка: разбор записи (`targets.target`) и текст `gitcmd.pult_message` в
песочнице `tmp_root` (пути `config` во временном каталоге). Запись
вымышленного проекта — в файле локального слоя `targets.local_path()`,
загрузка штатная, без подмены записи. Git и сеть не нужны: «коммит пульта»
(чекпоинт, подтяжка, документы задачи) берёт сообщение из `pult_message` —
единственная точка подписи по проекту задачи.

Имена проектов, тело сообщения и случайная допустимая служебная строка —
от зерна `random`; зерно печатается и входит в текст провала.
"""
import random

import pytest

from orchestrator import config, gitcmd, targets

LETTERS = "abcdefhkmnpqrsvwxyz"
KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"
TRAILER = "Harness-Actor: orchestrator"
DEFAULT_TRAILER = "Artel-Actor: orchestrator"

ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: []
      project_skills: []
      merge_gate: operator
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: github
      url: https://localhost/team/{name}
      token_slot: {name}-token
"""


class Seed:
    """Зерно сценария: печатается и входит в текст провала."""

    def __init__(self):
        self.value = random.randrange(1 << 30)
        print(f"зерно: {self.value}")
        self.rng = random.Random(self.value)

    def msg(self, text) -> str:
        return f"зерно: {self.value}; {text}"

    def name(self) -> str:
        return "q" + "".join(self.rng.choice(LETTERS) for _ in range(8))

    def trailer(self) -> str:
        """Случайная допустимая служебная строка `<Ключ>: <значение>`."""
        key = "".join(self.rng.choice(KEY_CHARS) for _ in range(self.rng.randint(1, 12)))
        value = "v" + "".join(self.rng.choice(LETTERS + " .<>@")
                              for _ in range(self.rng.randint(0, 15))).rstrip()
        return f"{key}: {value}"

    def co_author(self) -> str:
        return f"Co-authored-by: Соавтор{self.rng.randrange(100)} <co@x.example>"

    def body(self) -> str:
        """Сообщение коммита пульта до подписи: первая строка и тело."""
        return (f"T{self.rng.randrange(10 ** 6)}: чекпоинт\n\n"
                f"тело {self.rng.randrange(10 ** 6)}\n" + "\n" * self.rng.randint(0, 2))


@pytest.fixture
def seed():
    return Seed()


def quoted(value: str) -> str:
    """Литерал YAML строки в двойных кавычках (подмножество `yamlmini`)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_local(name: str, policy: dict | None = None) -> None:
    """Единственная запись вымышленного локального слоя песочницы; значения `policy` — текст YAML."""
    lines = "".join(f"      {key}: {value}\n" for key, value in (policy or {}).items())
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + ENTRY.format(name=name, base=config.MAIN_BRANCH,
                                                 policy=lines), encoding="utf-8")


def load_error(name: str) -> str | None:
    """Текст отказа загрузки записи `name`; `None` — запись загрузилась."""
    try:
        targets.target(name)
    except targets.TargetsError as exc:
        return str(exc)
    return None


def last_paragraph(message: str) -> list:
    return message.rstrip("\n").split("\n\n")[-1].splitlines()


# ------------------------------------------------------------------- AC-1


@pytest.mark.parametrize("kind", ["образец", "случайная"])
def test_ac1_trailer_replaces_default_as_last_paragraph(tmp_root, seed, kind):
    """Запись слоя с `policy.commit_trailer` — сообщение коммита пульта кончается этой строкой, `Artel-Actor` в нём нет.

    Сценарий: в файле вымышленного локального слоя — запись со случайным
    именем и `policy.commit_trailer` (образец `Harness-Actor: orchestrator`
    либо случайная допустимая строка), без `co_author`. Запись загружается
    штатно (`targets.target`); `pult_message` по проекту даёт сообщение,
    последний абзац которого — ровно эта строка, и подстроки `Artel-Actor`
    в сообщении нет.

    Ловит мутацию: поле не перенесено при сведении записи (`_flatten`
    без `commit_trailer` в перечне полей доставки) или `pult_message` не
    читает поле — в сообщении остаётся `Artel-Actor: orchestrator`.
    """
    name = seed.name()
    trailer = TRAILER if kind == "образец" else seed.trailer()
    write_local(name, {"commit_trailer": quoted(trailer)})
    note = seed.msg(f"{name}; {trailer!r}")
    assert load_error(name) is None, note + f"; {load_error(name)}"
    message = gitcmd.pult_message(seed.body(), name)
    note += f"; {message!r}"
    assert last_paragraph(message) == [trailer], note
    assert message.rstrip("\n").splitlines()[-1] == trailer, note
    assert "Artel-Actor" not in message, note


def test_ac1_trailer_after_co_author_in_one_paragraph(tmp_root, seed):
    """С `co_author` в той же записи последний абзац — строка соавтора и следом служебная строка, она последняя.

    Сценарий: запись локального слоя со случайным именем, `co_author` со
    случайным именем соавтора и `commit_trailer: "Harness-Actor:
    orchestrator"`. Последний абзац сообщения `pult_message` — ровно две
    строки: `co_author`, затем служебная; последняя строка сообщения —
    служебная, `Artel-Actor` нет.

    Ловит мутацию: служебная строка поставлена перед `co_author` (порядок
    строк абзаца обратный) или отдельным абзацем после `co_author`
    (последний абзац — одна строка).
    """
    name = seed.name()
    co_author = seed.co_author()
    write_local(name, {"co_author": quoted(co_author),
                       "commit_trailer": quoted(TRAILER)})
    note = seed.msg(name)
    assert load_error(name) is None, note + f"; {load_error(name)}"
    message = gitcmd.pult_message(seed.body(), name)
    note += f"; {message!r}"
    assert last_paragraph(message) == [co_author, TRAILER], note
    assert message.rstrip("\n").splitlines()[-1] == TRAILER, note
    assert "Artel-Actor" not in message, note


# ------------------------------------------------------------------- AC-2


@pytest.mark.parametrize("with_co_author", [False, True], ids=["без-co_author", "с-co_author"])
def test_ac2_empty_trailer_drops_line(tmp_root, seed, with_co_author):
    """`commit_trailer: ""` — служебной строки в сообщении нет, пустого завершающего абзаца нет.

    Сценарий: запись локального слоя со случайным именем и
    `commit_trailer: ""` (с `co_author` или без); загрузка без отказа
    (иначе `pult_message` молча взял бы пустую запись). Сообщение
    `pult_message`: подстроки `Artel-Actor` нет, оно не оканчивается
    пустым абзацем; с `co_author` последний абзац — строка соавтора; без
    него — первая строка и тело прежние, без подписи.

    Ловит мутацию: пустое значение даёт возврат к умолчанию `Artel-Actor`
    (`value or PULT_ACTOR_TRAILER`); пустая строка добавляется в абзац
    подписи или пустой абзац дописывается в конец сообщения.
    """
    name = seed.name()
    co_author = seed.co_author()
    policy = {"co_author": quoted(co_author)} if with_co_author else {}
    policy["commit_trailer"] = '""'
    write_local(name, policy)
    note = seed.msg(name)
    assert load_error(name) is None, note + f"; {load_error(name)}"
    original = seed.body()
    message = gitcmd.pult_message(original, name)
    note += f"; {message!r}"
    assert "Artel-Actor" not in message, note
    assert not message.endswith("\n\n"), note
    if with_co_author:
        assert last_paragraph(message) == [co_author], note
        assert message.rstrip("\n").splitlines()[-1] == co_author, note
    else:
        assert message.rstrip("\n") == original.rstrip("\n"), note


# ------------------------------------------------------------------- AC-3


@pytest.mark.parametrize("case", ["без-проекта", "запись-без-поля", "запись-с-co_author"])
def test_ac3_without_field_message_is_unchanged(tmp_root, seed, case):
    """Без поля `policy.commit_trailer` (и при `project=None`) сообщение побайтно прежнее, последняя строка — `Artel-Actor: orchestrator`.

    Сценарий: запись локального слоя со случайным именем без
    `commit_trailer` (с `co_author` или без) либо вызов с `project=None`.
    Сообщение `pult_message` равно прежней форме: тело без завершающих
    переводов строк, пустая строка, строка `co_author` (если задана),
    `Artel-Actor: orchestrator` и перевод строки.

    Ловит мутацию: отсутствующее поле читается как пустое (`.get(…, "")`)
    — служебная строка пропадает; либо меняется умолчание или разделитель
    абзаца — байты сообщения иные.
    """
    name = seed.name()
    co_author = seed.co_author()
    if case == "запись-с-co_author":
        write_local(name, {"co_author": quoted(co_author)})
    else:
        write_local(name)
    project = None if case == "без-проекта" else name
    original = seed.body()
    lines = [co_author] if case == "запись-с-co_author" else []
    expected = original.rstrip("\n") + "\n\n" + "\n".join(lines + [DEFAULT_TRAILER]) + "\n"
    message = gitcmd.pult_message(original, project)
    assert message == expected, seed.msg(f"{project}; {message!r} != {expected!r}")
