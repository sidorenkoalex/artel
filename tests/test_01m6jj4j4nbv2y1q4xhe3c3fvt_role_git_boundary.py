"""Граница git роли: PATH роли с обёрткой git и канал корня механизма отказа.

Группа: долгоживущий
Свойства кода окружения роли (`runner.role_env`) — обязаны держаться и после
мержа задачи. Проверки исхода вызовов git в песочнице пульта живут в
приёмочных тестах задачи.

Красен до реализации: `runner.role_env` не ставит ни каталог обёртки `orchestrator/role_bin/` вторым элементом PATH, ни `ARTEL_GIT_GUARD_ROOT`/`GIT_CEILING_DIRECTORIES`.
"""
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from orchestrator import config, providers, runner

WRAPPER_DIR = Path(runner.__file__).resolve().parent / "role_bin"
GUARD_ROOT = "ARTEL_GIT_GUARD_ROOT"
CEILING = "GIT_CEILING_DIRECTORIES"


def _resolved(item: str) -> Path | None:
    try:
        return Path(item).resolve()
    except OSError:
        return None


def _real_git() -> str:
    """Настоящий git процесса теста — первый `git` по PATH без каталога обёртки."""
    path = os.pathsep.join(item for item in os.environ.get("PATH", "").split(os.pathsep)
                           if item and _resolved(item) != WRAPPER_DIR)
    found = shutil.which("git", path=path)
    if found is None:
        raise RuntimeError("git не найден в PATH процесса теста")
    return found


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_ac16_wrapper_dir_second_in_role_path_before_git(tmp_root, provider):
    """Каталог обёртки — второй элемент PATH роли сразу после `.artel/venv/bin`, раньше каталога git.

    Окружение собирается `runner.role_env` для роли провайдера в песочнице
    пульта. Наблюдается: первый элемент PATH — `<.artel/venv>/bin`, второй —
    `orchestrator/role_bin/` рядом с модулем `runner`, а каталог настоящего
    git стоит в PATH позже него.

    Ловит мутацию: обёртка добавлена в конец PATH (после каталога git) или
    перед `.artel/venv/bin` — индекс каталога обёртки не 1 и git по PATH роли
    находится мимо неё.
    """
    env = runner.role_env("developer", "T001", provider=providers.get(provider))
    items = env["PATH"].split(os.pathsep)
    git_dir = Path(_real_git()).resolve().parent
    resolved = [_resolved(item) for item in items]

    assert items[0] == str(config.VENV_DIR / "bin"), items
    assert resolved[1] == WRAPPER_DIR, items
    assert git_dir in resolved, (git_dir, items)
    assert resolved.index(git_dir) > 1, (git_dir, items)


def test_ac16_wrapper_version_matches_real_git(tmp_root):
    """`git --version` через обёртку совпадает с выводом настоящего git.

    Обёртка `orchestrator/role_bin/git` зовётся напрямую под окружением роли.
    Наблюдается: код 0 и stdout, равный stdout `git --version` настоящего git.

    Ловит мутацию: обёртка печатает собственную строку версии либо отказывает
    вызову, не обращающемуся к репозиторию, — stdout или код расходятся.
    """
    env = runner.role_env("developer", "T001")
    wrapper = WRAPPER_DIR / "git"
    real = subprocess.run([_real_git(), "--version"], capture_output=True, text=True,
                          timeout=60)

    via = subprocess.run([str(wrapper), "--version"], env=env, cwd=str(tmp_root.root),
                         capture_output=True, text=True, timeout=60)

    assert via.returncode == 0, via.stderr
    assert via.stdout == real.stdout


def test_ac19_role_env_carries_resolved_guard_root_and_ceiling(tmp_root, monkeypatch):
    """`ARTEL_GIT_GUARD_ROOT` и `GIT_CEILING_DIRECTORIES` равны разрешённому `config.ROOT`.

    Корень пульта подменяется на случайный каталог песочницы, достижимый через
    символическую ссылку (и на сам каталог); `config.PROJECTS` — под тем же
    корнем. Наблюдается: обе переменные окружения роли равны пути корня после
    разрешения ссылок (на macOS `/var` → `/private/var`).

    Ловит мутацию: значение берётся без `resolve()` (путь через ссылку или
    `/var/...` вместо `/private/var/...`); потолок и корень механизма считаются
    из разных источников — одна из переменных расходится с разрешённым корнем.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    for _ in range(3):
        real = tmp_root.root / f"pult-{rng.randrange(10 ** 6)}"
        (real / ".artel" / "projects").mkdir(parents=True, exist_ok=True)
        link = tmp_root.root / f"link-{rng.randrange(10 ** 6)}"
        link.symlink_to(real, target_is_directory=True)
        for root in (link, real):
            monkeypatch.setattr(config, "ROOT", root)
            monkeypatch.setattr(config, "PROJECTS", root / ".artel" / "projects")

            env = runner.role_env("developer", "T001")

            expected = str(real.resolve())
            assert env.get(GUARD_ROOT) == expected, f"зерно: {seed}; {root}"
            assert env.get(CEILING) == expected, f"зерно: {seed}; {root}"
