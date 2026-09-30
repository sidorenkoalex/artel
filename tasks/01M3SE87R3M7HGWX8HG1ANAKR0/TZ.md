---
task: 01M3SE87R3M7HGWX8HG1ANAKR0
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Признак «процесс — шаг роли» для всех провайдеров

# ТЗ: Признак «процесс — шаг роли» для всех провайдеров

Источник: строка копилки 30.09 (П1) «Признак „процесс — шаг роли“ не
срабатывает у ролей на codex»; находка независимого ревью ТЗ провайдера
opencode; решение Оператора 30.09.

Факты (пин 34b298c7):
- `runner.in_role_environment()` (`runner.py:873-882`) верно только при
  `HOME == config.ROLE_HOME` И `CLAUDE_CONFIG_DIR == config.ROLE_CONFIG_DIR`.
- `CodexProvider.environment` (`codex.py:489-496`) ставит `HOME`,
  `CODEX_HOME`, `ZDOTDIR`, но не `CLAUDE_CONFIG_DIR`. На пульте 30.09
  `runner.role_env("developer")` (боевая роль на codex): HOME совпадает,
  CLAUDE_CONFIG_DIR — нет, `ARTEL_ROLE=developer`. Признак у ролей codex
  ложен.
- На признаке держатся отказы из-под роли: расшифровка пула канарейки
  (`pool_seal.py:198`), `answer` в in_dev/review (`answer.py:162`, `:223`),
  `note` (`notes.py:1291`).
- Общий маркер уже есть: `config.ARTEL_ROLE_ENV = "ARTEL_ROLE"`
  (`config.py:69`), его ставит `runner.role_env` для любого провайдера
  (`runner.py:864-865`); по нему `artel.py` (`artel.py:969`) отказывает
  `init`/`doctor --restore`/`canary pool-seal`, по нему включается гейт
  `conftest.py`.
- Провайдер opencode (следующая задача линии) уводит `HOME` в свой
  каталог — признак по `HOME` его тоже не увидит.

Требуется:
1. `in_role_environment(env=None)` — признак по `ARTEL_ROLE`: процесс —
   шаг роли, если в окружении (по умолчанию `os.environ`) есть непустой
   `ARTEL_ROLE`. Прежнее условие по `HOME`/`CLAUDE_CONFIG_DIR` остаётся
   вторым достаточным признаком (ИЛИ), чтобы роль на claude не потеряла
   признак, если маркер снят.
2. Все потребители признака (`pool_seal`, `answer`, `notes` и любой
   найденный поиском по коду) работают через эту функцию без правки их
   логики; для роли на codex они теперь отказывают так же, как для
   claude.
3. `doctor`: офлайн-смок изоляции каждого провайдера проверяет, что для
   собранного окружения шага `in_role_environment(env)` верно.
4. `docs/stack.md` — описание признака и строка таблицы паритета
   безопасности «отказ команд пульта из-под роли» (claude, codex — да).
5. Тесты в `tests/`: окружение шага codex — признак верен («Ловит
   мутацию: признак только по HOME/CLAUDE_CONFIG_DIR»); окружение
   claude — верен; окружение Оператора без `ARTEL_ROLE` и с чужим `HOME` —
   ложен; `answer` в in_dev и `note` из-под окружения роли codex —
   отказ; расшифровка пула — отказ.

Зоны: orchestrator/runner.py, orchestrator/doctor/, docs/stack.md, tests/.

Только чтение (не менять): orchestrator/pool_seal.py, orchestrator/answer.py,
orchestrator/notes.py, orchestrator/artel.py, orchestrator/config.py,
orchestrator/providers/, conftest.py, roles.yaml, models.yaml,
scripts/guard.py, skills/, templates/, docs/adr/, docs/invariants.md,
tests/test_invariants.py, docs/backlog.md, tasks/.

Не входит: провайдер opencode; правки песочницы codex.

Рамка: $15.
