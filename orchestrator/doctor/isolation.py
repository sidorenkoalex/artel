"""Пакет orchestrator/doctor -- офлайн-смоук изоляции project-/user-слоя.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from pathlib import Path
import os
import tempfile

from orchestrator import doctor


# --- смоук изоляции (требование 6) -------------------------------------

def isolation_smoke(role: str = "developer") -> doctor.Check:
    """Маркеры project- и user-слоя не достигают env/промпта роли.

    user-слой: `role_env()` копирует ambient `os.environ`, затем всегда
    переписывает HOME на курируемый `config.ROLE_HOME` — проверка
    подменяет ambient HOME на временный каталог с маркером (НЕ реальный
    $HOME Оператора — офлайн-смоук им не пользуется вовсе) и убеждается,
    что итоговое окружение роли этот каталог не унаследовало.

    project-слой (CLAUDE.md рабочего каталога): `role_cwd()` эфемерного
    target'а — безопасный для записи каталог `.artel/projects/
    <synthetic>/workspace/` (gitignored, не реальный клон), маркер в нём
    проверяется на промпт роли — тот собирается только из
    `config.ROOT/skills/*.md` (`runner.cmd_run`), cwd в сборку не входит
    структурно.

    project-/local-хуки (SPEC T058, инцидент T046): реальный `claude`
    шага роли резолвит `.claude/settings.json`/`.claude/settings.local.
    json` от cwd через git независимо от того, что несёт промпт, —
    проверка выше это не ловит. Здесь — структурная, офлайн проверка
    (без реального запуска `claude`, тем же приёмом, что и два маркера
    выше): единственная защита от этого вектора — флаг `--setting-
    sources`, реально попадающий в argv `run_agent_once`
    (`orchestrator/runner.py:572`) из `config.AGENT_SETTING_SOURCES`;
    здесь сверяется, что сама константа не включает `project`/`local`.
    Дискриминирующую половину критерия (канарейка реально не/срабатывает)
    проверяют локальные приёмочные `tasks/T058/acceptance_tests/
    test_ac1_ac2_role_hook_isolation.py` — они гоняют настоящий `claude`
    против настоящей канарейки на реально построенных `cmd`/`cwd`/`env`
    шага и не дублируются здесь намеренно (см. PLAN.md T058, «Подход»):
    живой прогон на каждый `doctor` не офлайн и не бесплатен.

    MCP-вектор (SPEC T069, требование 2): `claude` резолвит `.mcp.json`
    рабочего каталога — право коммита в целевой проект означало бы
    возможность подключить произвольный MCP-сервер в шаг роли. Защита —
    флаг `--strict-mcp-config` в реальном argv шага (`runner.role_cmd()`,
    единый источник для запуска и для этой проверки — SPEC T069, «тот же
    приём, что уже применён к --setting-sources», здесь буквально: сама
    сборка cmd, а не только константа). Живая дискриминирующая проверка
    того же класса, что и у project-/local-хуков выше, здесь не
    построена: экспериментально подтверждено (см. докстринг
    `tasks/T069/acceptance_tests/test_ac1_strict_mcp_command.py`), что
    свежий project-scope MCP-сервер в headless `-p`-режиме не
    подключается структурно ни с флагом, ни без него — различающего
    живого сигнала нет.
    """
    leaks = []

    prior_home = os.environ.get("HOME")
    with tempfile.TemporaryDirectory() as fake_home:
        (Path(fake_home) / ".claude").mkdir(parents=True)
        (Path(fake_home) / ".claude" / "CLAUDE.md").write_text(
            doctor.ISOLATION_MARKER, encoding="utf-8")
        os.environ["HOME"] = fake_home
        try:
            env = doctor.runner.role_env(role)
        except OSError as exc:
            # Тот же класс отказа, что уже ловят `check_git_identity`/
            # `_live_smoke_run` (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN, AC-6):
            # объявленный инструмент манифеста не найден — не повод
            # уронить весь `doctor` необработанным исключением.
            return doctor.Check("isolation-smoke", "fail",
                        f"окружение роли не подготовлено: {exc}")
        finally:
            if prior_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = prior_home
    if env.get("HOME") == fake_home or any(
            doctor.ISOLATION_MARKER in str(v) for v in env.values()):
        leaks.append("user-слой: HOME роли не отведён от ambient-значения")

    project_dir = doctor.runner.role_cwd(None, None, doctor.ISOLATION_SMOKE_TARGET)
    try:
        (project_dir / "CLAUDE.md").write_text(doctor.ISOLATION_MARKER, encoding="utf-8")
        try:
            skill_names = doctor.roles.skills(role)
            prompt_text = "\n\n".join(
                (doctor.config.ROOT / "skills" / f"{s}.md").read_text(encoding="utf-8")
                for s in skill_names)
        except (doctor.roles.RolesError, OSError, UnicodeDecodeError) as exc:
            return doctor.Check("isolation-smoke", "fail",
                        f"промпт роли не собран для проверки: {exc}")
        if doctor.ISOLATION_MARKER in prompt_text:
            leaks.append("project-слой: маркер CLAUDE.md рабочего каталога "
                        "просочился в промпт роли")
    finally:
        doctor.shutil.rmtree(doctor.config.PROJECTS / doctor.ISOLATION_SMOKE_TARGET, ignore_errors=True)

    excluded_sources = {"project", "local"}
    active_sources = {s.strip() for s in doctor.config.AGENT_SETTING_SOURCES.split(",")}
    if active_sources & excluded_sources:
        leaks.append("project-хук: --setting-sources шага роли не "
                    f"исключает {sorted(active_sources & excluded_sources)} "
                    "— project-/local-слой клиентских настроек "
                    "(включая хуки) достижим шагом роли")

    cmd = doctor.runner.role_cmd()
    if "--strict-mcp-config" not in cmd:
        leaks.append("MCP-вектор: --strict-mcp-config отсутствует в "
                    "команде запуска шага роли — .mcp.json рабочего "
                    "каталога достижим шагом")

    if leaks:
        return doctor.Check("isolation-smoke", "fail", "; ".join(leaks))
    return doctor.Check("isolation-smoke", "ok",
                 "маркеры project-/user-слоя не достигли env/промпта роли, "
                 "project-/local-хуки исключены из resolve-сурсов шага, "
                 "MCP-конфиг рабочего каталога изолирован "
                 "(--strict-mcp-config)")


