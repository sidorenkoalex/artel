"""Команда `suite-lock --reason "<основание>" [--limit <секунды>] --
<команда> [аргументы…]`: произвольная команда Оператора под замком полных
прогонов машины (SPEC 01M70RYD6YXA6DFKCRECSHRKBM).

07.11 замер без замка совпал с автогейтом приёмки и вызвал ложный отказ по
таймауту; 08.11 замер взял замок сценарием через `suite_lock.acquire` —
обход. Здесь то же взятие штатно: без ожидания, держатель — процесс
`suite-lock` с видом `внешний`, команда — дочерним процессом в своей группе
в пределе времени, замок снимается на любом исходе, кроме `SIGKILL` самой
`suite-lock` (его снимает следующий `acquire` как брошенный).

Предел не больше разности ожидания замка гейтом и предела полного прогона:
гейт, ставший в очередь за внешней командой, ещё успевает свой прогон.
"""
import contextlib
import signal
import subprocess
import sys
import threading

from . import config, liveness, suite_lock

HEAD = "suite-lock"
USAGE = ('синтаксис: suite-lock --reason "<основание>" [--limit <секунды>] '
         '-- <команда> [аргументы…]')
REASON_MAX = 200
# Код выхода по пределу — как у `timeout(1)`.
LIMIT_EXIT = 124
# Код выхода, если команда не запустилась (нет файла, нет прав) — как у
# оболочки.
SPAWN_EXIT = 127
_SIGNALS = (signal.SIGINT, signal.SIGTERM)


class _Signalled(Exception):
    def __init__(self, signum: int):
        super().__init__(signum)
        self.signum = signum


def reason_text(raw: str) -> str:
    """Основание для записи замка: одна строка, не длиннее `REASON_MAX`
    символов — запись читают отказы и записи журнала об ожидании."""
    return raw.replace("\n", " ").replace("\r", " ")[:REASON_MAX]


def limit_bound() -> int:
    """Наибольший предел — из констант в момент вызова (их подменяют
    тесты и может поменять Оператор)."""
    return config.FULL_SUITE_LOCK_WAIT_SEC - config.FULL_SUITE_TIMEOUT_SEC


def _parse(argv: list[str]) -> tuple[str, int, list[str]]:
    """(основание, предел, команда); `ValueError` с текстом отказа."""
    if "--" not in argv:
        raise ValueError(f"нет `--` перед командой; {USAGE}")
    split = argv.index("--")
    options, command = argv[:split], argv[split + 1:]
    reason, limit = None, None
    i = 0
    while i < len(options):
        name = options[i]
        if name not in ("--reason", "--limit"):
            raise ValueError(f"неизвестный аргумент {name!r} до `--`; {USAGE}")
        if i + 1 >= len(options):
            raise ValueError(f"{name} без значения; {USAGE}")
        value = options[i + 1]
        if name == "--reason":
            reason = value
        else:
            limit = value
        i += 2
    if reason is None or not reason.strip():
        raise ValueError(f"пустое основание --reason; {USAGE}")
    bound = limit_bound()
    if limit is None:
        seconds = bound
    else:
        try:
            seconds = int(limit)
        except ValueError:
            raise ValueError(f"--limit {limit!r} — не целое число секунд; "
                             f"{USAGE}") from None
        if seconds <= 0 or seconds > bound:
            raise ValueError(f"--limit {seconds} вне 1…{bound} с (предел — "
                             f"FULL_SUITE_LOCK_WAIT_SEC − "
                             f"FULL_SUITE_TIMEOUT_SEC)")
    if not command:
        raise ValueError(f"пустая команда после `--`; {USAGE}")
    return reason, seconds, command


def refusal(argv: list[str]) -> str | None:
    """Отказ разбора аргументов до взятия замка; `None` — вызов корректен."""
    try:
        _parse(argv)
    except ValueError as exc:
        return str(exc)
    return None


def _say(text: str) -> None:
    print(f"{HEAD}: {text}", file=sys.stderr, flush=True)


def _raise_signalled(signum, _frame) -> None:
    # Один раз: повторный сигнал не должен оборвать остановку группы и
    # снятие замка, начатые первым.
    for s in _SIGNALS:
        signal.signal(s, signal.SIG_IGN)
    raise _Signalled(signum)


@contextlib.contextmanager
def _signals(handler):
    previous = {s: signal.signal(s, handler) for s in _SIGNALS}
    try:
        yield
    finally:
        for s, old in previous.items():
            signal.signal(s, old)


def _stop(proc: subprocess.Popen) -> None:
    """Останавливает группу команды целиком. Повторный сигнал на это время
    игнорируется — остановка не обрывается на середине; команду забирает
    отдельный поток, чтобы её зомби не держал группу до `SIGKILL`."""
    with _signals(signal.SIG_IGN):
        reaper = threading.Thread(target=proc.wait, daemon=True)
        reaper.start()
        liveness.terminate_process_group(proc.pid)
        reaper.join(timeout=5)


def _exit_code(code: int) -> int:
    # Убитая сигналом команда — `128 + номер`, как в оболочке: `sys.exit`
    # с отрицательным числом дал бы `256 − номер`.
    return code if code >= 0 else 128 - code


def _run(command: list[str], limit: int) -> int:
    try:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError as exc:
        _say(f"отказ — команда не запустилась: {exc}")
        return SPAWN_EXIT
    try:
        return _exit_code(proc.wait(timeout=limit))
    except subprocess.TimeoutExpired:
        _stop(proc)
        _say(f"предел {limit} с истёк — группа процессов команды "
             f"остановлена, замок снят")
        return LIMIT_EXIT
    except _Signalled as exc:
        _stop(proc)
        _say(f"сигнал {signal.Signals(exc.signum).name} — группа процессов "
             f"команды остановлена, замок снят")
        raise


def cmd_suite_lock(argv: list[str]) -> int:
    """`suite-lock`: код выхода — код команды; 124 — предел; 128 + номер —
    сигнал `SIGINT`/`SIGTERM` самой команды `suite-lock`; 2 — отказ
    разбора; 1 — замок занят; 127 — команда не запустилась."""
    try:
        reason, limit, command = _parse(argv)
    except ValueError as exc:
        _say(f"отказ — {exc}")
        return 2
    # Обработчик ставится до взятия: сигнал между взятием и запуском тоже
    # проходит через снятие замка в `finally`.
    with _signals(_raise_signalled):
        try:
            holder = suite_lock.acquire(None, None,
                                        kind=suite_lock.KIND_EXTERNAL,
                                        reason=reason_text(reason))
            if holder is not None:
                _say(f"отказ — замок полных прогонов машины держит "
                     f"{suite_lock.describe(holder)}; повтори после его "
                     f"конца")
                return 1
            return _run(command, limit)
        except _Signalled as exc:
            return 128 + exc.signum
        finally:
            # Чужой замок `release` не трогает — сверяет pid держателя.
            suite_lock.release()
