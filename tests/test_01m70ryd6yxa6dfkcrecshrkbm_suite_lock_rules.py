"""Правила команды `suite-lock` без процессов: текст держателя вида
`внешний`, разбор аргументов до взятия замка, основание записи замка и
отказ процессу роли.

Группа: долгоживущий
Красен до реализации: модуля `orchestrator/suite_hold.py` ещё нет — импорт в теле тестов AC-5/AC-10/AC-11 падает, а `suite_lock.describe` вида `внешний` даёт текст `suite-run` (AC-3); AC-9 зелёный с рождения — `suite-lock` вне белого списка ролей уже сейчас.

Поверхности решения (`suite_lock.describe`, `suite_hold.refusal`,
`suite_hold.reason_text`) проверяются малыми тестами: полный перебор
случаев литералами `parametrize`, значения внутри случая — от `random`,
зерно печатается и входит в текст провала.
"""
import random
import string
import sys

import pytest

from orchestrator import artel, config, runner, suite_lock

pytestmark = pytest.mark.size("small")

EXTERNAL = "внешний"
ROLE_REFUSAL = "команда недоступна процессу роли"
LETTERS = string.ascii_letters + string.digits + "абвгдеёжзийклмнопрстуфхцчшщэюя"
ID_LETTERS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def seeded() -> tuple[int, random.Random]:
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def word(rng: random.Random, low: int, high: int) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(rng.randint(low, high)))


def phrase(rng: random.Random) -> str:
    return " ".join(word(rng, 1, 8) for _ in range(rng.randint(1, 5)))


# --------------------------------------------------------------- AC-3

@pytest.mark.parametrize("kind", [EXTERNAL, "suite-run", "гейт", "notes"])
def test_ac3_describe_external_kind_and_old_kinds(kind):
    """Держатель словами по виду: `внешний` — «внешней команды «<основание>» (pid N)», прежние виды — прежние тексты.

    Сценарий: запись держателя вида `kind` со случайными pid, задачей и
    основанием; `suite_lock.describe` сравнивается с образцом вида целиком.
    Запись `suite-run` — прежней формы, без поля `kind`.

    Ловит мутацию: вид `внешний` не различается и идёт веткой `suite-run`
    («suite-run задачи None (pid N)»); основание выпало из текста или
    взято без «ёлочек»; общий текст на все виды меняет «гейта задачи …»
    или «notes (pid N)».
    """
    seed, rng = seeded()
    pid = rng.randint(2, 99999)
    task = "".join(rng.choice(ID_LETTERS) for _ in range(26))
    reason = phrase(rng)
    if kind == EXTERNAL:
        holder = {"task_id": None, "pid": pid, "run": None, "kind": kind,
                  "reason": reason}
        expected = f"внешней команды «{reason}» (pid {pid})"
    elif kind == "suite-run":
        holder = {"task_id": task, "pid": pid, "run": rng.randint(1, 9)}
        expected = f"suite-run задачи {task} (pid {pid})"
    elif kind == "гейт":
        holder = {"task_id": task, "pid": pid, "run": None, "kind": kind}
        expected = f"гейта задачи {task} (pid {pid})"
    else:
        holder = {"task_id": None, "pid": pid, "run": None, "kind": kind}
        expected = f"notes (pid {pid})"

    assert suite_lock.describe(holder) == expected, f"зерно {seed}: {holder}"


# --------------------------------------------------------------- AC-5

@pytest.mark.parametrize("case, refused", [
    ("over", True),
    ("zero", True),
    ("negative", True),
    ("nonnumeric", True),
    ("equal", False),
    ("absent", False),
])
def test_ac5_limit_bound_from_patched_constants(monkeypatch, case, refused):
    """Предел `--limit` судится от разности подменённых констант, не от литерала 900.

    Сценарий: `config.FULL_SUITE_LOCK_WAIT_SEC` и
    `config.FULL_SUITE_TIMEOUT_SEC` подменены случайными значениями с
    разностью, отличной от 900; `suite_hold.refusal` на корректном вызове с
    `--limit` больше разности, `0`, `-5`, `x` — непустой текст отказа; с
    `--limit`, равным разности, и без `--limit` — `None`.

    Ловит мутацию: граница — литерал 900 (значение «разность + 1» при
    разности меньше 900 проходит, «разность» больше 900 — отказ);
    сравнение `>=` вместо `>` (равное разности отклоняется); ноль или
    отрицательное значение проходят; нечисловое значение роняет разбор
    исключением вместо отказа.
    """
    from orchestrator import suite_hold

    seed, rng = seeded()
    bound = rng.choice([rng.randint(30, 899), rng.randint(901, 3000)])
    timeout = rng.randint(60, 2000)
    monkeypatch.setattr(config, "FULL_SUITE_TIMEOUT_SEC", timeout)
    monkeypatch.setattr(config, "FULL_SUITE_LOCK_WAIT_SEC", timeout + bound)
    value = {"over": str(bound + 1), "zero": "0", "negative": "-5",
             "nonnumeric": "x", "equal": str(bound)}.get(case)
    limit = [] if value is None else ["--limit", value]
    argv = ["--reason", phrase(rng), *limit, "--", "true"]

    verdict = suite_hold.refusal(argv)

    where = f"зерно {seed}: граница {bound}, argv {argv}, ответ {verdict!r}"
    if refused:
        assert isinstance(verdict, str) and verdict, where
    else:
        assert verdict is None, where


# --------------------------------------------------------------- AC-10

@pytest.mark.parametrize("case, refused", [
    ("no_separator", True),
    ("nothing_after_separator", True),
    ("empty_reason", True),
    ("reason_without_value", True),
    ("no_reason", True),
    ("correct", False),
])
def test_ac10_empty_command_and_empty_reason_refused(case, refused):
    """Пустая команда и пустое основание — отказ `suite_hold.refusal`, корректный вызов — `None`.

    Сценарий: варианты вызова без `--`, без команды после `--`, с
    `--reason ""`, с `--reason` без значения, без `--reason` и корректный
    `--reason r -- true` (основание и команда — случайные слова там, где
    форма это допускает).

    Ловит мутацию: отсутствие `--` не проверяется (слова после основания
    принимаются за команду); пустой список после `--` проходит; пустая
    строка основания принимается как основание; `--reason` без значения
    берёт следующим значением `--`, а команду — без отказа; вызов без
    `--reason` проходит; отказ на корректном вызове.
    """
    from orchestrator import suite_hold

    seed, rng = seeded()
    reason = phrase(rng)
    command = rng.choice([["true"], ["echo", word(rng, 1, 6)]])
    argv = {
        "no_separator": ["--reason", reason, *command],
        "nothing_after_separator": ["--reason", reason, "--"],
        "empty_reason": ["--reason", "", "--", *command],
        "reason_without_value": ["--reason", "--", *command],
        "no_reason": ["--", *command],
        "correct": ["--reason", "r", "--", "true"],
    }[case]

    verdict = suite_hold.refusal(argv)

    where = f"зерно {seed}: argv {argv}, ответ {verdict!r}"
    if refused:
        assert isinstance(verdict, str) and verdict, where
    else:
        assert verdict is None, where


# --------------------------------------------------------------- AC-11

@pytest.mark.parametrize("case", [
    "newline_n", "newline_r", "long", "long_with_newlines", "short_plain",
    "exactly_200",
])
def test_ac11_reason_text_replaces_newlines_and_cuts_to_200(case):
    """Основание записи замка: `\\n` и `\\r` — пробел, длина — не больше 200, прочее без изменений.

    Сценарий: основание из случайных букв (без пробелов по краям и рядом с
    переводами строк); переводы строк вставлены поодиночке внутрь; длинные
    варианты — 201–400 символов. Ожидаемое — замена каждого перевода
    пробелом и обрезка до первых 200 символов; основание без переводов не
    длиннее 200 (в том числе ровно 200) — то же самое.

    Ловит мутацию: заменяется только `\\n` (`\\r` остаётся в записи
    замка); обрезка до замены или по байтам вместо символов (кириллица
    режется раньше 200); граница `< 200` вместо `<= 200` (основание ровно
    200 укорочено); переводы строк удаляются, а не заменяются пробелом.
    """
    from orchestrator import suite_hold

    seed, rng = seeded()
    if case in ("long", "long_with_newlines"):
        length = rng.randint(201, 400)
    elif case == "exactly_200":
        length = 200
    else:
        length = rng.randint(5, 200)
    chars = [rng.choice(LETTERS) for _ in range(length)]
    if case in ("newline_n", "newline_r", "long_with_newlines"):
        breaks = {"newline_n": "\n", "newline_r": "\r"}.get(case)
        spots = rng.sample(range(1, length - 1, 2),
                           rng.randint(1, min(5, (length - 2) // 2)))
        for spot in spots:
            chars[spot] = breaks or rng.choice("\n\r")
    raw = "".join(chars)
    expected = raw.replace("\n", " ").replace("\r", " ")[:200]

    got = suite_hold.reason_text(raw)

    assert got == expected, f"зерно {seed}: {raw!r} → {got!r}"


# --------------------------------------------------------------- AC-9

def test_ac9_role_process_refused_without_running_command(tmp_path,
                                                          monkeypatch):
    """`artel.main` с `suite-lock` в окружении роли — отказ «команда недоступна процессу роли», команда не запускалась, замка нет.

    Сценарий: корень пульта и `config.LOGS` — временный каталог теста,
    признак роли — `ARTEL_ROLE` со случайной ролью; `sys.argv` — корректный
    вызов `suite-lock --reason <основание> -- <python, создающий
    файл-след>`. `artel.main` завершается `SystemExit` с текстом отказа
    роли; файла-следа и файла замка нет.

    Ловит мутацию: `suite-lock` добавлен в `_ROLE_ALLOWED_COMMANDS` —
    `main` доходит до реализации, команда под замком создаёт файл-след и
    отказа роли в выходе нет.
    """
    seed, rng = seeded()
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "LOGS", tmp_path / "logs")
    monkeypatch.setenv(config.ARTEL_ROLE_ENV,
                       rng.choice(["developer", "reviewer", "test_author"]))
    trace = tmp_path / "trace"
    monkeypatch.setattr(sys, "argv", [
        "artel.py", "suite-lock", "--reason", phrase(rng), "--",
        sys.executable, "-c", f"open({str(trace)!r}, 'w').close()"])
    assert runner.in_role_environment(), f"зерно {seed}"

    with pytest.raises(SystemExit) as exit_info:
        artel.main()

    where = f"зерно {seed}: {exit_info.value.code!r}"
    assert ROLE_REFUSAL in str(exit_info.value.code), where
    assert not trace.exists(), where
    assert not suite_lock.path().exists(), where
