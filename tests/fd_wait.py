"""Ожидание готовности дескриптора на чтение без предела номера (SPEC
01M5G6PDQA7AYDYDPA7DD5JD4S, требования 5-7; ANSWER-3).

`select.select` отказывает `ValueError: filedescriptor out of range in
select()` на дескрипторе с номером от `FD_SETSIZE` (1024): в исполнителе
xdist, где дескрипторов открыто много, это роняло тесты, ждавшие канал.
Вне Darwin ожидание идёт через `selectors.DefaultSelector` (epoll/poll —
без такого предела). На Darwin `poll`/`kqueue` не сообщают конец файла
именованного канала (FIFO), поэтому там остаётся прежний `select.select` и
перенос дескриптора выше 1024 не делается (ANSWER-3, вариант A).
"""
import fcntl
import os
import resource
import select
import selectors
import sys

#: Номер, не меньше которого `high_fd` переносит дескриптор, — заведомо
#: выше `FD_SETSIZE`, чтобы `select.select` на нём отказал.
HIGH_FD = 1100


def select_limited() -> bool:
    """Платформа ждёт прежним `select.select` (Darwin, ANSWER-3)."""
    return sys.platform == "darwin"


def wait_readable(fileobj, timeout: float) -> bool:
    """Готов ли `fileobj` (дескриптор либо объект с `fileno()`) к чтению за
    `timeout` секунд; конец файла — тоже готовность."""
    if select_limited():
        ready, _, _ = select.select([fileobj], [], [], timeout)
        return bool(ready)
    with selectors.DefaultSelector() as selector:
        selector.register(fileobj, selectors.EVENT_READ)
        return bool(selector.select(timeout))


def high_fd(test, fd: int) -> int:
    """Переносит `fd` на номер не меньше `HIGH_FD` (`fcntl.F_DUPFD`) и
    закрывает исходный; возвращает новый номер. Мягкий предел
    `RLIMIT_NOFILE`, если он не пускает такой номер, поднимается в пределах
    жёсткого и возвращается в `test.addCleanup`."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    want = HIGH_FD + 64
    if soft != resource.RLIM_INFINITY and soft < want:
        raised = want if hard == resource.RLIM_INFINITY else min(want, hard)
        resource.setrlimit(resource.RLIMIT_NOFILE, (raised, hard))
        test.addCleanup(resource.setrlimit, resource.RLIMIT_NOFILE, (soft, hard))
    moved = fcntl.fcntl(fd, fcntl.F_DUPFD, HIGH_FD)
    os.set_inheritable(moved, False)
    os.close(fd)
    return moved
