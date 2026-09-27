"""Общее для нескольких файлов планки задачи 01M3H5FEXH5M9HGZYT3BCDX5C4
(не `test_*.py`: подхватывается только импортом из `test_ac*.py`).

Три вещи, которые нужны больше чем одному критерию:

1. Текст карты исполнителей с ОДНОЙ agent-ролью на ярусе, отличном от
   яруса остальных (AC-1, AC-2), и копия дерева кода, в которой этот
   текст лежит настоящим `roles.yaml`. Копия, а не правка файла на
   месте: `tests/test_runner_role_model.py::_roles_yaml_text` и
   `tests/sandbox.py` читают карту исполнителей путём, вычисленным от
   `__file__` собственного модуля (`Path(__file__).resolve()` — символы
   ссылок не помогут), а правка файла репозитория на время прогона
   оставила бы дерево пульта испорченным при любом обрыве.
2. Прогон pytest подпроцессом с управляемым `cwd` — единственный способ
   отдать тестам `tests/` другую карту исполнителей, не импортируя их в
   процесс планки.
3. Сравнение файлов `tests/` с главной веткой (AC-4, AC-5): база —
   `gitcmd.diff_base` (тот же узел, которым пульт считает точку
   расхождения ветки задачи), разбор — `scripts/guard.py`
   (`qualified_test_methods`/`test_skip_markers`), чтобы «что считается
   тестовым методом» здесь и на гейте решалось одним кодом.

Роль, которую планка уводит на отдельный ярус, и сами ярусы берутся
ДИНАМИЧЕСКИ: роль — первая agent-роль карты, чьё имя не встречается в
тексте прогоняемых файлов («не названная тестом» в формулировке
критериев), ярусы — из `orchestrator/models.py::TIERS`. Ни имя роли, ни
имя яруса в планке литералом не зашиты: и то, и другое — крутилка
Оператора в защищённых файлах.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd, models, yamlmini  # noqa: E402
from scripts import guard  # noqa: E402

#: Корень дерева КОДА под проверкой — тот же, от которого пульт читает
#: `roles.yaml` и запускает `tests/` (`orchestrator/config.py::ROOT`).
REPO_ROOT = Path(config.ROOT).resolve()

STACK_TEST = "tests/test_stack_optional_tools.py"
ROLE_MODEL_TEST = "tests/test_runner_role_model.py"
PREFLIGHT_TEST = "tests/test_runner_model_preflight.py"
DOCTOR_TEST = "tests/test_models_doctor.py"

TESTS_DIR = "tests"

#: Каталоги, которые копии дерева не нужны: `.git` (копия и не должна
#: быть репозиторием — прогон в ней ничего не коммитит), `.artel`
#: (рабочее состояние пульта, включая worktree самой этой задачи),
#: `tasks` (артефакты; планка живёт в них и копировала бы себя).
_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".artel", "tasks", "__pycache__", ".pytest_cache", "*.pyc",
    ".mypy_cache", "node_modules", ".venv", "venv")

#: Строки итога pytest, называющие упавший/сломавшийся тест по nodeid
#: (`-rfE`): и провал, и ошибка — одинаково красный исход.
_FAILED_NODEID = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M)


def real_roles_text() -> str:
    """Настоящая карта исполнителей репозитория текстом."""
    return (REPO_ROOT / "roles.yaml").read_text(encoding="utf-8")


def agent_roles(text: str) -> dict:
    """{agent-роль: её ярус} по тексту карты исполнителей — тот же
    критерий agent-роли, что у `orchestrator/stack.py::model_providers`
    (`executor: agent`)."""
    entries = yamlmini.mapping(text).get("roles") or {}
    return {role: entry.get("model_tier")
            for role, entry in entries.items()
            if isinstance(entry, dict) and entry.get("executor") == "agent"}


def roles_text_with_tiers(text: str, tiers: dict) -> str:
    """Тот же текст карты исполнителей, где у каждой роли из `tiers`
    поле `model_tier` заменено заданным значением (существующее поле
    снимается, новое встаёт сразу под заголовком роли — тот же приём,
    что `tests/test_runner_role_model.py::_roles_yaml_text` применяет к
    одной роли). Остальные строки файла не трогаются."""
    out, current = [], None
    for line in text.splitlines(keepends=True):
        head = line.rstrip()
        is_role_header = (line.startswith("  ") and not line.startswith("    ")
                          and head.endswith(":"))
        if is_role_header:
            current = head.strip().rstrip(":")
            out.append(line)
            if current in tiers:
                out.append(f"    model_tier: {tiers[current]}\n")
            continue
        if not line.startswith("    "):
            current = None
        if current in tiers and line.lstrip().startswith("model_tier:"):
            continue
        out.append(line)
    return "".join(out)


def role_not_named_in(targets) -> str:
    """Первая agent-роль карты, чьё имя не встречается в тексте ни
    одного из файлов `targets` — «роль, не названная тестом» из
    формулировки AC-1/AC-2."""
    texts = [(REPO_ROOT / target).read_text(encoding="utf-8")
             for target in targets]
    for role in sorted(agent_roles(real_roles_text())):
        if all(role not in text for text in texts):
            return role
    raise AssertionError(
        f"в карте исполнителей нет agent-роли, не названной файлами "
        f"{', '.join(targets)} — критерий говорит о роли, которую тест не "
        f"называет")


def spread_roles_text(targets) -> tuple:
    """(текст карты, роль-одиночка, её ярус, ярус остальных) для сценария
    критериев AC-1/AC-2: ровно одна agent-роль, не названная целевыми
    файлами, стоит на ярусе перечня `models.TIERS`, отличном от яруса
    остальных agent-ролей.

    Ярусы берутся от `models.TIERS`, а не литералами: перечень — крутилка
    Оператора, и планка обязана пережить её поворот. Ярус остальных ролей
    проставляется явно всем agent-ролям, а не наследуется из файла:
    критерий требует, чтобы отличалась РОВНО одна роль, а распределение
    ролей по ярусам в самом `roles.yaml` Оператор меняет когда угодно.
    """
    assert len(models.TIERS) >= 2, models.TIERS
    base_tier, other_tier = models.TIERS[0], models.TIERS[1]
    role = role_not_named_in(targets)
    text = real_roles_text()
    tiers = {name: base_tier for name in agent_roles(text)}
    tiers[role] = other_tier
    return roles_text_with_tiers(text, tiers), role, other_tier, base_tier


def repo_copy(tmpdir, roles_text: str) -> Path:
    """Копия дерева кода во временном каталоге, у которой `roles.yaml` —
    заданный текст. Возвращает корень копии: прогон pytest с этим `cwd`
    читает и код, и карту исполнителей именно оттуда."""
    dest = Path(tmpdir) / "code"
    shutil.copytree(REPO_ROOT, dest, ignore=_COPY_IGNORE, symlinks=True)
    (dest / "roles.yaml").write_text(roles_text, encoding="utf-8")
    return dest


def pytest_env(*extra_path) -> dict:
    """Окружение прогона-подпроцесса: без унаследованных настроек pytest
    родительского прогона и без записи `__pycache__` в проверяемое
    дерево."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in extra_path)
    return env


def run_pytest(cwd, targets, plugins=(), path_extra=(), timeout=300):
    """Прогон pytest подпроцессом: `targets` — пути файлов либо nodeid,
    `plugins` — модули `-p`, `path_extra` — каталоги в `PYTHONPATH`
    (корень дерева плюс каталог плагина). Возвращает
    `subprocess.CompletedProcess`."""
    cwd = Path(cwd)
    command = [sys.executable, "-m", "pytest", *targets,
               "-p", "no:cacheprovider", "-q", "-rfE", "--tb=short"]
    for plugin in plugins:
        command += ["-p", plugin]
    return subprocess.run(command, cwd=str(cwd),
                          env=pytest_env(cwd, *path_extra),
                          capture_output=True, text=True, timeout=timeout)


def run_report(result) -> str:
    """Вывод прогона для сообщения об ошибке ассерта — оба потока и код
    возврата: без них красная планка называла бы только «не ноль»."""
    return (f"returncode={result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}")


def failed_nodeids(output: str) -> list:
    """Nodeid упавших и сломавшихся тестов из итога прогона (`-rfE`)."""
    return _FAILED_NODEID.findall(output)


# ------------------------------------------------- сравнение с main
#
# Мутация «локальный слой называет модель только у одного яруса» (AC-5)
# ставится плагином pytest: подменяется `models.load_local`, через
# который идут ОБА входа резолва цепочки (`resolve_role` и
# `layers_or_none`). Сохраняется ярус ПЕРВОЙ agent-роли карты, а не
# первый попавшийся: тест, у которого все роли на одном ярусе, при такой
# мутации остаётся зелёным, и красным становится ровно тот, который
# развёл роли по разным ярусам, — то есть регрессионный тест критерия.
ONE_TIER_PLUGIN_NAME = "artel_one_tier_local_layer"

ONE_TIER_PLUGIN_SOURCE = '''
"""Плагин прогона: локальный слой моделей называет модель только у
одного яруса — состояние песочницы до починки задачи."""
from orchestrator import models, roles

_original_load_local = models.load_local


def _kept_tier(layer):
    try:
        entries = roles.load()
    except Exception:
        entries = {}
    for role, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("executor") != "agent":
            continue
        try:
            tier = roles.model_tier(role)
        except Exception:
            continue
        if tier in layer.tiers:
            return tier
    return next(t for t in models.TIERS if t in layer.tiers)


def _one_tier_load_local(*args, **kwargs):
    layer = _original_load_local(*args, **kwargs)
    if len(layer.tiers) <= 1:
        return layer
    keep = _kept_tier(layer)
    return layer._replace(tiers={keep: layer.tiers[keep]})


models.load_local = _one_tier_load_local
'''


def write_one_tier_plugin(tmpdir) -> Path:
    """Кладёт плагин мутации во временный каталог и отдаёт этот каталог
    (его же нужно добавить в `PYTHONPATH` прогона)."""
    plugin_dir = Path(tmpdir) / "plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / f"{ONE_TIER_PLUGIN_NAME}.py").write_text(
        ONE_TIER_PLUGIN_SOURCE, encoding="utf-8")
    return plugin_dir


def main_base_ref() -> str:
    """Точка расхождения ветки задачи с главной веткой — тем же узлом,
    каким её считает сам пульт (`gitcmd.diff_base`: `origin/<main>`, если
    ref заведён, иначе локальная главная ветка). Пустая строка — git не
    ответил."""
    branch = gitcmd.current_branch() or "HEAD"
    return gitcmd.diff_base(branch) or ""


def tests_files_at(ref: str) -> list:
    """Пути `tests/*.py` в дереве `ref`; `None` — git не ответил."""
    paths = gitcmd.ls_tree_files(ref, TESTS_DIR)
    if paths is None:
        return None
    return sorted(p for p in paths if p.endswith(".py"))


def text_at(ref: str, rel: str):
    """Текст файла `rel` в дереве `ref`; `None` — файла там нет."""
    return gitcmd.show(ref, rel)[0]


def text_on_disk(rel: str):
    """Текст файла `rel` рабочей копии кода; `None` — файла нет."""
    path = REPO_ROOT / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def changed_tests_files(ref: str) -> list:
    """Пути `tests/*.py`, чей текст на диске отличается от текста в
    дереве `ref` (включая удалённые и добавленные)."""
    base = tests_files_at(ref) or []
    disk = sorted(
        str(p.relative_to(REPO_ROOT).as_posix())
        for p in (REPO_ROOT / TESTS_DIR).rglob("*.py"))
    return [rel for rel in sorted(set(base) | set(disk))
            if text_at(ref, rel) != text_on_disk(rel)]


def changed_test_methods(base_source, head_source) -> list:
    """Квалифицированные имена тестовых методов HEAD-версии файла, которых
    в базовой версии нет вовсе либо текст которых изменился, — та же
    пара критериев («новая» и «изменённая»), которой пользуется
    `scripts/guard.py::test_functions_without_mutation_claim`."""
    if head_source is None:
        return []
    head = guard.qualified_test_methods(head_source)
    base = guard.qualified_test_methods(base_source) if base_source else {}
    changed = []
    for name, node in head.items():
        base_node = base.get(name)
        if base_node is not None and \
                ast.get_source_segment(head_source, node) == \
                ast.get_source_segment(base_source, base_node):
            continue
        changed.append(name)
    return sorted(changed)


def nodeid(rel: str, qualified: str) -> str:
    """`tests/test_x.py` + `Class::test_y` -> nodeid pytest."""
    return f"{rel}::{qualified}"
