"""Приёмочные тесты AC-4, AC-5 (tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/SPEC.md,
«Критерии приёмки»).

AC-4: `role_env` передаёт роли только переменные окружения из явного
белого списка (HOME, CLAUDE_CONFIG_DIR, git-идентичность, токен роли,
LANG/LC_*, TMPDIR, TERM, переменные CLI `claude`) — переменные
`os.environ` Оператора вне этого списка роли не передаются.

AC-5: Белый список переменных окружения роли объявлен в манифесте, у
каждой переменной в списке — причина, зачем она роли нужна.

Красен до реализации:
- `test_ac4_*` — сегодня `role_env` строит `env = dict(os.environ)`
  (копия целиком), поэтому ЛЮБАЯ переменная Оператора (в т.ч. заведомый
  мусор вроде `AWS_SECRET_ACCESS_KEY` в тесте ниже) проходит в
  окружение роли — тест краснеет на `assertNotIn`.
- `test_ac5_*` — `orchestrator/stack.py` (манифест, часть 1) ещё не
  существует в этом дереве: импорт падает уже на `from orchestrator
  import stack`.

Предположение об интерфейсе (решение test_author, а не факт из кода):
белый список объявлен константой `orchestrator.stack.ROLE_ENV_ALLOWLIST`
— словарём {имя: причина} либо итерируемым из пар (имя, причина); тест
принимает обе формы (`_allowlist_items`), чтобы не привязывать планку к
конкретному контейнеру там, где сам SPEC называет только имена
переменных, а не структуру данных. Имя константы — то, под которое
пишется реализация этой же задачи (`orchestrator/stack.py` — в зоне
части 3, а не только части 1, см. SPEC «Оценка объёма и деление»).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import runner  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

# AC-14: существующий набор `tests/` зелёный после изменений (включая
# обновлённые без ослабления тесты role_env T019/T020, ADR-0003 п.14) —
# сквозная регрессия по ВСЕМУ дереву, не свойство одного сценария;
# `tests/` целиком гоняет CI (skills/test-authoring.md, решение
# Оператора 05.09), не шаг test_author.
# AC-14: manual — полный набор tests/ (включая role_env T019/T020) в шаге не гоняется, это делает CI на приёмке

FAKE_TOOL_PATHS = {
    "python3": "/opt/fake-pyenv/shims/python3",
    "git": "/usr/bin/git",
    "gh": "/usr/local/bin/gh",
    "claude": "/usr/local/bin/claude",
}


def _fake_which(name, *args, **kwargs):
    return FAKE_TOOL_PATHS.get(name)


def _stub_git(*args):
    import subprocess
    return subprocess.CompletedProcess(list(args), 1, "", "")


# Мусор — не из белого списка ни по одному критерию SPEC: ни git-
# идентичность, ни токен, ни локаль/TMPDIR/TERM, ни HOME/CLAUDE_CONFIG_DIR.
GARBAGE_ENV = {
    "SOME_RANDOM_VAR": "нежелательное",
    "AWS_SECRET_ACCESS_KEY": "утечёт-если-скопируют-всё",
    "NVM_DIR": "/home/operator/.nvm",
    "OPERATOR_SHELL_HISTFILE": "/home/operator/.zsh_history",
}

# Явно названные в требовании 2 SPEC — должны пройти, если заданы у
# Оператора (LC_* — представитель семейства, LC_ALL).
ALLOWLISTED_ENV = {
    "LANG": "ru_RU.UTF-8",
    "LC_ALL": "ru_RU.UTF-8",
    "TMPDIR": "/tmp/operator-tmp",
    "TERM": "xterm-256color",
}


class RoleEnvAllowlistTest(TmpRootTest):

    def _role_env_with(self, extra_environ: dict) -> dict:
        # `clear=True` — принципиально: без него ambient-переменные МАШИНЫ
        # прогона (USER/SHELL/PWD/...), не упомянутые ни в GARBAGE_ENV, ни
        # в ALLOWLISTED_ENV, остались бы в os.environ и тест не отличил
        # бы «прошло по белому списку» от «случайно уцелело из ambient».
        full_env = {"PATH": "/usr/bin:/bin", **extra_environ}
        with mock.patch.dict(runner.os.environ, full_env, clear=True), \
                mock.patch("shutil.which", side_effect=_fake_which), \
                mock.patch.object(runner.gitcmd, "git", _stub_git):
            return runner.role_env()

    def test_ac4_vars_outside_the_allowlist_do_not_cross_into_role_env(self):
        """Переменные Оператора вне белого списка не попадают в
        окружение роли, даже если явно заданы в `os.environ`.

        Ловит мутацию: `env = dict(os.environ)` без последующей фильтрации
        (сегодняшняя реализация) переносит `AWS_SECRET_ACCESS_KEY` и
        прочий GARBAGE_ENV в окружение роли один в один — `assertNotIn`
        краснеет.
        """
        env = self._role_env_with({**GARBAGE_ENV, **ALLOWLISTED_ENV})

        for name in GARBAGE_ENV:
            self.assertNotIn(name, env,
                             f"{name} не входит в белый список, но попал в окружение роли")

    def test_ac4_allowlisted_vars_from_the_requirement_text_do_cross(self):
        """LANG/LC_*/TMPDIR/TERM — явно названные требованием 2 — доходят
        до роли, если заданы у Оператора.

        Ловит мутацию: белый список, реализованный слишком узко (например,
        забывший TMPDIR/TERM), даст `assertEqual(env.get(name), value)`
        красным именно на пропущенной переменной.
        """
        env = self._role_env_with({**GARBAGE_ENV, **ALLOWLISTED_ENV})

        for name, value in ALLOWLISTED_ENV.items():
            self.assertEqual(env.get(name), value,
                             f"{name} — в белом списке требования 2, но не дошла до роли")

    def test_ac5_allowlist_is_declared_in_the_manifest_with_a_reason_each(self):
        """Белый список — структура данных в `orchestrator/stack.py`
        (манифест), не список внутри кода `role_env`, и у каждой
        переменной есть непустая причина.

        Ловит мутацию: белый список, зашитый прямо в тело `role_env`
        (например, локальным `set` без манифеста и без причин) — этот
        тест не найдёт `orchestrator.stack.ROLE_ENV_ALLOWLIST` и
        покраснеет на `AttributeError`/`ImportError`, а не на содержимом.
        """
        from orchestrator import stack

        allowlist = stack.ROLE_ENV_ALLOWLIST
        items = _allowlist_items(allowlist)
        names = {name for name, _reason in items}

        required = ("HOME", "CLAUDE_CONFIG_DIR",
                   "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                   "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
                   "CLAUDE_CODE_OAUTH_TOKEN", "TMPDIR", "TERM", "LANG")
        missing = [name for name in required if name not in names]
        self.assertFalse(missing, f"в манифесте нет записи для: {missing}")

        without_reason = [name for name, reason in items if not (reason and reason.strip())]
        self.assertFalse(without_reason,
                         f"переменные без причины в манифесте: {without_reason}")


def _allowlist_items(allowlist):
    """Нормализует белый список к списку пар (имя, причина) независимо
    от того, объявлен ли он словарём {имя: причина} или итерируемым пар —
    структура данных манифеста не часть критерия, только его содержимое."""
    if isinstance(allowlist, dict):
        return list(allowlist.items())
    return [tuple(item) for item in allowlist]


if __name__ == "__main__":
    unittest.main()
