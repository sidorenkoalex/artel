"""AC-4 — AC-9: отказ `git clean` и его обходных форм; git вне ROOT; воспроизведение инцидента.

Группа: разовый
Предмет критериев — исход вызова git под окружением роли, а правило
долгоживущих файлов `tests/` запрещает вызов git через `subprocess`
(`scripts/guard.py::long_lived_sign_hits`); поэтому файл — в планке.

Все меняющие команды (`clean -fX`, псевдонимы, pager/fsmonitor со значением
`git clean -fX`) идут только против дублёра ROOT (`_doubler.Doubler`).
Псевдонимы вызываются с аргументами `-fX`: без механизма вызов настоящий
удалил бы игнорируемый файл копии `junk.tmp`, и это наблюдаемо.

Красен до реализации: обёртки `orchestrator/role_bin/` и механизма `orchestrator/role_git.py` ещё нет — `git clean`, псевдонимы и вызовы с pager/fsmonitor исполняются настоящим git с кодом 0 или без строки `task-rm`, а игнорируемые файлы дублёра удаляются.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _doubler import TASK_RM, Doubler, output  # noqa: E402

CLEAN = "git clean -fX"


@pytest.fixture
def pult(tmp_path, monkeypatch):
    return Doubler(tmp_path, monkeypatch)


def _call(pult, args, cwd, extra=None):
    try:
        return pult.run(args, pult.role_env(), cwd, extra)
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"git {args}: превышен таймаут {exc.timeout} с — рекурсия или "
                    f"зависание")


@pytest.mark.parametrize("form", ["own-n", "own-fX", "root-n", "root-fX",
                                  "artel-cwd-n", "C-artel-ndX"])
def test_ac4_git_clean_refused_names_task_rm(pult, form):
    """`git clean` в своей рабочей копии, в репозитории пульта, из `<ROOT>/.artel`.

    Наблюдается: ненулевой код, строка отказа называет `task-rm`,
    игнорируемые файлы дублёра (`ignored.txt`, `.artel/models.yaml`,
    `junk.tmp` копий) на месте.

    Ловит мутацию: своя рабочая копия исключена из отказа `clean` (как из
    отказа требования 2) — `git clean -fX -- junk.tmp` в ней удаляет файл с
    кодом 0; строка отказа `clean` не называет `task-rm`.
    """
    own, root = pult.own, pult.root
    args, cwd = {
        "own-n": (["clean", "-n"], own),
        "own-fX": (["clean", "-fX", "--", "junk.tmp"], own),
        "root-n": (["clean", "-n"], root),
        "root-fX": (["clean", "-fX", "--", "ignored.txt"], root),
        "artel-cwd-n": (["clean", "-n"], root / ".artel"),
        "C-artel-ndX": (["-C", str(root / ".artel"), "clean", "-ndX"], pult.outside),
    }[form]

    res = _call(pult, args, cwd)

    assert res.returncode != 0, f"{form}: {output(res)}"
    assert TASK_RM in output(res), f"{form}: {output(res)}"
    assert not pult.missing_ignored(), f"{form}: удалены {pult.missing_ignored()}"


@pytest.mark.parametrize("form", ["c-alias", "c-bang-alias", "config-common",
                                  "config-worktree", "GIT_CONFIG_PARAMETERS"])
def test_ac5_clean_aliases_refused(pult, form):
    """Псевдонимы, раскрывающиеся в `clean`, и `!`-псевдоним с `git clean -fX`.

    Формы: `git -c alias.cl=clean cl`, `git -c alias.x='!git clean -fX' x`,
    `cl = clean` в конфигурации рабочей копии (и в `config` общего `.git`
    клона, и в `config.worktree` своей копии), псевдоним через
    `GIT_CONFIG_PARAMETERS`. Наблюдается: ненулевой код, строка отказа
    механизма (называет `task-rm`, требование 3), `junk.tmp` и прочие
    игнорируемые файлы дублёра на месте.

    Ловит мутацию: механизм видит только подкоманду `clean` буквально и не
    раскрывает псевдонимы — `cl -fX` исполняется и удаляет `junk.tmp`;
    механизм не читает `config.worktree` — git сам отвечает «'cl' is not a
    git command» без строки отказа с `task-rm`.
    """
    extra = {}
    if form == "c-alias":
        args = ["-c", "alias.cl=clean", "cl", "-fX"]
    elif form == "c-bang-alias":
        args = ["-c", f"alias.x=!{CLEAN}", "x"]
    elif form in ("config-common", "config-worktree"):
        pult.write_config(form.split("-")[1], "alias.cl", "clean")
        args = ["cl", "-fX"]
    else:
        extra = {"GIT_CONFIG_PARAMETERS": "'alias.cl'='clean'"}
        args = ["cl", "-fX"]

    res = _call(pult, args, pult.own, extra)

    assert res.returncode != 0, f"{form}: {output(res)}"
    assert TASK_RM in output(res), f"{form}: {output(res)}"
    assert not pult.missing_ignored(), f"{form}: удалены {pult.missing_ignored()}"


@pytest.mark.parametrize("form", [
    "config-env-alias", "config-count-alias",
    "bang-clean-common", "bang-clean-worktree",
    "bang-echo-common", "bang-echo-worktree", "c-bang-echo"])
def test_ac6_config_env_count_and_bang_aliases_refused(pult, form):
    """`--config-env`, `GIT_CONFIG_COUNT`/`KEY_0`/`VALUE_0` и любой `!`-псевдоним.

    `!`-псевдоним из конфигурации рабочей копии отклоняется и с телом
    `!git clean -fX`, и с безвредным `!echo ok`; так же `git -c
    alias.x='!echo ok' x`. Наблюдается: ненулевой код, строка отказа
    механизма (называет `task-rm`, требование 3), игнорируемые файлы дублёра
    на месте.

    Ловит мутацию: отказ `!`-псевдонима только при `clean` в его теле —
    `!echo ok` проходит с кодом 0; механизм не читает `--config-env` или
    `GIT_CONFIG_COUNT` — `cl -fX` удаляет `junk.tmp`.
    """
    extra = {}
    if form == "config-env-alias":
        extra = {"PLANK_ALIAS_VALUE": "clean"}
        args = ["--config-env=alias.cl=PLANK_ALIAS_VALUE", "cl", "-fX"]
    elif form == "config-count-alias":
        extra = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "alias.cl",
                 "GIT_CONFIG_VALUE_0": "clean"}
        args = ["cl", "-fX"]
    elif form == "c-bang-echo":
        args = ["-c", "alias.x=!echo ok", "x"]
    else:
        _bang, body, where = form.split("-")
        pult.write_config(where, "alias.x", f"!{CLEAN}" if body == "clean" else "!echo ok")
        args = ["x"]

    res = _call(pult, args, pult.own, extra)

    assert res.returncode != 0, f"{form}: {output(res)}"
    assert TASK_RM in output(res), f"{form}: {output(res)}"
    assert not pult.missing_ignored(), f"{form}: удалены {pult.missing_ignored()}"


_PAGER_FORMS = {
    "c-pager": (["-c", f"core.pager={CLEAN}", "log"], {}, None),
    "c-fsmonitor": (["-c", f"core.fsmonitor={CLEAN}", "status"], {}, None),
    "GIT_PAGER": (["log"], {"GIT_PAGER": CLEAN}, None),
    "config-env-pager": (["--config-env=core.pager=PLANK_VALUE", "log"],
                         {"PLANK_VALUE": CLEAN}, None),
    "config-env-fsmonitor": (["--config-env=core.fsmonitor=PLANK_VALUE", "status"],
                             {"PLANK_VALUE": CLEAN}, None),
    "parameters-pager": (["log"], {"GIT_CONFIG_PARAMETERS": f"'core.pager'='{CLEAN}'"},
                         None),
    "parameters-fsmonitor": (["status"],
                             {"GIT_CONFIG_PARAMETERS": f"'core.fsmonitor'='{CLEAN}'"},
                             None),
    "count-pager": (["log"], {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.pager",
                              "GIT_CONFIG_VALUE_0": CLEAN}, None),
    "count-fsmonitor": (["status"], {"GIT_CONFIG_COUNT": "1",
                                     "GIT_CONFIG_KEY_0": "core.fsmonitor",
                                     "GIT_CONFIG_VALUE_0": CLEAN}, None),
    "config-common-pager": (["log"], {}, ("common", "core.pager")),
    "config-worktree-pager": (["log"], {}, ("worktree", "core.pager")),
    "config-common-fsmonitor": (["status"], {}, ("common", "core.fsmonitor")),
    "config-worktree-fsmonitor": (["status"], {}, ("worktree", "core.fsmonitor")),
}


@pytest.mark.parametrize("form", list(_PAGER_FORMS))
def test_ac7_pager_fsmonitor_with_git_call_refused_top_level(pult, form):
    """`core.pager`/`core.fsmonitor`/`GIT_PAGER` со значением `git clean -fX` во всех каналах.

    Каналы: `-c`, `--config-env`, `GIT_CONFIG_PARAMETERS`,
    `GIT_CONFIG_COUNT`/`KEY_0`/`VALUE_0`, `GIT_PAGER`, конфигурация рабочей
    копии (и `config` общего `.git` клона, и `config.worktree` своей копии);
    вызовы `git log` (pager) и `git status` (fsmonitor). Каждый вызов — с
    таймаутом 30 с, превышение — провал. Наблюдается: ненулевой код, строка
    отказа называет `task-rm`, игнорируемые файлы дублёра на месте.

    Ловит мутацию: механизм не читает `core.pager`/`core.fsmonitor` из
    конфигурации рабочей копии (формы config-*) — `git log`/`git status`
    исполняются с кодом 0.
    """
    args, extra, config_entry = _PAGER_FORMS[form]
    if config_entry is not None:
        where, key = config_entry
        pult.write_config(where, key, CLEAN)

    res = _call(pult, args, pult.own, extra)

    assert res.returncode != 0, f"{form}: {output(res)}"
    assert TASK_RM in output(res), f"{form}: {output(res)}"
    assert not pult.missing_ignored(), f"{form}: удалены {pult.missing_ignored()}"


@pytest.mark.parametrize("pager", ["cat", "less"])
def test_ac7_harmless_pager_passes(pult, pager):
    """`git -c core.pager=cat log` и `core.pager=less` в своей рабочей копии — код 0.

    Ловит мутацию: отказ по любому заданному `core.pager`, а не только по
    значению с вызовом git — `git log` получает ненулевой код.
    """
    res = _call(pult, ["-c", f"core.pager={pager}", "log"], pult.own)

    assert res.returncode == 0, f"{pager}: {output(res)}"


def test_ac8_git_clean_outside_root_passes(pult):
    """`git clean -f` во временном репозитории вне ROOT под окружением роли — успех.

    Ловит мутацию: отказ `clean` в любом репозитории (без проверки
    вложенности в ROOT) — код ненулевой, неотслеживаемый файл остаётся.
    """
    repo = pult.base / "free-repo"
    repo.mkdir()
    pult.git_seed("init", "-q", cwd=repo)
    stray = repo / "stray.txt"
    stray.write_text("неотслеживаемый\n", encoding="utf-8")

    res = _call(pult, ["clean", "-f"], repo)

    assert res.returncode == 0, output(res)
    assert not stray.exists()


def test_ac9_incident_clean_via_docs_dir_refused(pult):
    """Инцидент 04.11: `git -C <каталог документов задачи> clean -fX -- x.py`.

    В корне дублёра лежит игнорируемый `ignored.txt`, в каталоге документов —
    `x.py` (игнорируется через `.artel/`). Наблюдается: ненулевой код,
    игнорируемые файлы корня и `x.py` на месте.

    Ловит мутацию: границы подъёма нет и `-C` не проверяется — git
    поднимается из каталога документов до репозитория дублёра и удаляет
    `x.py` с кодом 0.
    """
    stub = pult.docs / "x.py"
    stub.write_text("print('stub')\n", encoding="utf-8")

    res = _call(pult, ["-C", str(pult.docs), "clean", "-fX", "--", "x.py"], pult.own)

    assert res.returncode != 0, output(res)
    assert stub.exists()
    assert not pult.missing_ignored(), f"удалены {pult.missing_ignored()}"
