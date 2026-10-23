"""Git в процессах тестов — напрямую, без системной обёртки xcrun.

На macOS `/usr/bin/git` — обёртка, которая находит каталог инструментов
разработчика и запускает оттуда настоящий git (тот же файл, версия,
`--exec-path` и конфигурация). Каждый запуск через обёртку дороже прямого
на 80–140 мс, а тесты пульта запускают git сотнями раз на тест. Каталог
настоящего git вставляется в PATH процесса тестов перед `/usr/bin`;
PATH боевого пульта не меняется (SPEC 01M5KJNE39PHV9EAWJCHK7QDFS).

Вставляется сам каталог, а не ссылка на файл: git вычисляет
`--exec-path` от пути запуска.
"""

import os
import shutil
import subprocess
import sys
from typing import Callable

USR_BIN = "/usr/bin"
XCODE_SELECT_TIMEOUT_SEC = 5


def _xcode_select_dir() -> str | None:
    try:
        proc = subprocess.run(["xcode-select", "-p"], capture_output=True,
                              text=True, timeout=XCODE_SELECT_TIMEOUT_SEC)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _first_index(elements: list[str], directory: str) -> int | None:
    for i, element in enumerate(elements):
        if element and os.path.normpath(element) == directory:
            return i
    return None


def prefer_direct_git(environ, platform: str = sys.platform,
                      developer_dir: Callable[[], str | None] | None = None
                      ) -> str | None:
    """Вставляет `<каталог разработчика>/usr/bin` в `environ["PATH"]`
    перед первым `/usr/bin`, если git по этому PATH — обёртка
    `/usr/bin/git`. Возвращает вставленный каталог; `None` — PATH не
    изменён (не macOS, git уже не через обёртку, каталог не найден)."""
    if platform != "darwin":
        return None
    path = environ.get("PATH")
    if path is None:
        return None
    git = shutil.which("git", path=path)
    if git is None or os.path.normpath(git) != USR_BIN + "/git":
        return None
    elements = path.split(os.pathsep)
    usr_bin_index = _first_index(elements, USR_BIN)
    if usr_bin_index is None:
        return None
    if developer_dir is not None:
        devdir = developer_dir()
    else:
        devdir = environ.get("DEVELOPER_DIR") or _xcode_select_dir()
    if not devdir:
        return None
    direct_dir = os.path.join(devdir, "usr", "bin")
    direct_git = os.path.join(direct_dir, "git")
    if not (os.path.isfile(direct_git) and os.access(direct_git, os.X_OK)):
        return None
    present = _first_index(elements, os.path.normpath(direct_dir))
    if present is not None and present < usr_bin_index:
        return None
    elements.insert(usr_bin_index, direct_dir)
    environ["PATH"] = os.pathsep.join(elements)
    return direct_dir
