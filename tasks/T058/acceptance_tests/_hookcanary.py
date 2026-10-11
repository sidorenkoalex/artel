"""Общая инфраструктура приёмочных тестов T058 (не `test_*.py` — не
подхватывается `unittest discover`, только импортом из `test_ac*.py`,
по образцу `tasks/T051/acceptance_tests/_sandbox.py`).

Канарейка — реальный `SessionStart`-хук project-слоя, реально прогоняемый
через установленный `claude` CLI. `PreToolUse` (буквальная формулировка
AC-1) требует, чтобы модель реально решила вызвать инструмент — живой,
платный API-вызов; AC-1 сама оставляет простор («и иные»): любой хук
того же класса (project-слой, тот же вектор конфиг-инъекции инцидента
T046) годится, если критерий проверяет именно факт «исполняется/не
исполняется», а не конкретное событие. `SessionStart` регистрируется и
исполняется на старте CLI ДО обращения к API — проверено вручную этой
же связкой флагов на установленной в этом окружении версии `claude`:

    claude -p <промпт> -d hooks --debug-file <path>

без валидного токена падает на "Not logged in" уже ПОСЛЕ строки
"Hook SessionStart:startup (SessionStart) success: <канарейка>" в
debug-логе — офлайн, бесплатно, детерминированно. С `--setting-sources
user` (единственный подтверждённый `claude --help` флаг, реально
исключающий project/local-слой из резолвинга) та же канарейка не
регистрируется вовсе ("Hooks: Found 0 total hooks in registry") — это
и есть наблюдаемая пара «сработала/не сработала», а не гипотеза.

Аутентификация обнулена (временный HOME + вычищенные
ANTHROPIC_API_KEY/CLAUDE_CODE_OAUTH_TOKEN) в КАЖДОМ прогоне — не ради
проверки роли (её уже делает `runner.role_env`), а ради безопасности
самого теста на машине, где `claude` реально залогинен (Оператор):
хук успевает сработать до проверки авторизации, а после нею процесс
всё равно падает без сетевого вызова — ни разу не потратив бюджет.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CANARY_MARKER = "T058-PROJECT-HOOK-CANARY-NE-DOLZHNA-SRABOTAT"
CANARY_TIMEOUT_SEC = 30


def write_canary_hook(project_dir: Path) -> None:
    """Кладёт `.claude/settings.json` с канареечным `SessionStart`-хуком
    в `project_dir` — «тестовый project-конфиг» из формулировки AC-1/AC-2."""
    claude_dir = Path(project_dir) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command",
                            "command": f"echo {CANARY_MARKER}"}]}
            ]
        }
    }
    (claude_dir / "settings.json").write_text(
        json.dumps(settings), encoding="utf-8")


def canary_fired(cmd: list, cwd, env: dict) -> bool:
    """Реально прогоняет `cmd` (+ диагностические флаги) через настоящий
    `claude` CLI из `cwd`/`env` и смотрит, зарегистрировался и сработал
    ли канареечный хук синтетического project-слоя.

    Не предполагает НИКАКОГО конкретного механизма изоляции (SPEC T058,
    требование 1 оставляет выбор PLAN'у) — только то, что `cmd`/`cwd`/
    `env` реально передаются вызывающим кодом, а не изобретаются здесь.
    """
    debug_fd, debug_path = tempfile.mkstemp(suffix=".log")
    os.close(debug_fd)
    fake_home = tempfile.mkdtemp()
    try:
        run_env = dict(env)
        for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
            run_env.pop(key, None)
        run_env["HOME"] = fake_home
        # CLAUDE_CONFIG_DIR (если унаследован от текущего процесса — сам
        # тест выполняется ролью под пультом, ADR-0003 п.14) сильнее HOME
        # при резолвинге user-слоя логина: не обнулить его отдельно значило
        # бы, что прогон AC-2 в реальном окружении Оператора мог случайно
        # утащить настоящую авторизацию из курируемого слоя и потратить
        # деньги на настоящий API-вызов вместо безопасного офлайн-падения
        # на "Not logged in".
        run_env["CLAUDE_CONFIG_DIR"] = str(Path(fake_home) / ".claude")
        diag_cmd = [*cmd, "-d", "hooks", "--debug-file", debug_path]
        try:
            subprocess.run(diag_cmd, cwd=str(cwd), env=run_env, input="ok",
                           capture_output=True, text=True,
                           timeout=CANARY_TIMEOUT_SEC)
        except (OSError, subprocess.TimeoutExpired):
            pass
        log_path = Path(debug_path)
        text = (log_path.read_text(encoding="utf-8", errors="ignore")
                if log_path.exists() else "")
        return CANARY_MARKER in text
    finally:
        Path(debug_path).unlink(missing_ok=True)
        shutil.rmtree(fake_home, ignore_errors=True)
