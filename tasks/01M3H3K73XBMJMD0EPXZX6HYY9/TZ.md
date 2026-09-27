---
task: 01M3H3K73XBMJMD0EPXZX6HYY9
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Паритет окружения шага Codex: интерпретатор и PATH как у шага Claude

# ТЗ: Паритет окружения шага Codex: интерпретатор и PATH как у шага Claude

Источник: строка копилки 27.09 и «Предложения системе» SPEC пробной
задачи 01M3H1Z489CKJ8FHSRS4TYTPX2 (первый шаг роли analyst на провайдере
Codex, модель gpt-5.6-terra). Линия провайдеров, условие перевода ролей
developer и test_author на Codex.

Факты (origin/main a6da0abe):
- Окружение процесса роли собирает `orchestrator/runner.py::role_env`:
  PATH роли — `bin/` интерпретатора `.artel/venv` первым, затем каталоги
  объявленных инструментов манифеста (`_role_path_dirs`); поверх кладётся
  `provider.environment(role, task_id)`. Для Claude голый `python3` и
  `pytest` внутри шага резолвятся в venv пульта.
- `orchestrator/providers/codex.py::CodexProvider.environment` отдаёт шагу
  `HOME` и `CODEX_HOME` курируемого дома; команда шага — `codex exec` с
  песочницей `workspace-write` (`CodexProvider.command`), курируемый
  конфиг — `docs/reference/role-home/codex/config.toml`.
- Живой шаг 27.09 (лог `.artel/logs/01M3H1Z489CKJ8FHSRS4TYTPX2-analyst-1.log`):
  команды оболочки внутри шага Codex видели `python3` версии 3.9
  (системный), `python3 scripts/guard.py` упал на аннотациях с `|`
  в `orchestrator/session.py`; роль перебором нашла `python3.13` и
  провалидировала SPEC им. То есть PATH, собранный `role_env`, до
  команд оболочки шага Codex не дошёл либо был переписан (политика
  окружения оболочки CLI, вход через login-оболочку либо иное —
  причина не установлена).
- Запись журнала «окружение: python=3.13.12 …» описывает интерпретатор
  пульта, а не то, что видит команда внутри шага.

Требуется:
1. Установить причину в SPEC (по коду провайдера, конфигу дома роли и
   справке Codex CLI 0.155.1) и устранить: команды оболочки шага Codex
   видят тот же PATH, что собрал `role_env` — `python3`, `pytest`, `git`,
   `gh` резолвятся в те же пути, что у шага Claude. Способ (ключи
   курируемого `config.toml`, `-c`-пары команды шага, окружение
   процесса) — выбрать и обосновать; если выбран ключ конфига — он
   стоит и в референсе дома, и парой команды шага, как остальные пары
   (`CONFIG_OVERRIDES`).
2. Изоляция не ослабляется: в окружение команд шага не попадают
   переменные вне белого списка манифеста и секреты чужих провайдеров;
   офлайн-смок `codex-isolation-smoke` и проверка
   `foreign-provider-secrets` остаются зелёными без правки ожиданий.
3. Офлайн-проверка паритета: тест собирает окружение и команду шага для
   роли на Codex и для роли на Claude и сверяет, что PATH и интерпретатор
   совпадают; живой запуск CLI в тестах не требуется.
4. Запись журнала шага об окружении не вводит в заблуждение: либо
   называет, что это окружение пульта, либо несёт PATH роли. Формат —
   в SPEC; существующие читатели записи не ломаются.
5. Документация: `docs/reference/role-home/codex/AGENTS.md` (и
   `config.toml`, если правится) — какой интерпретатор и PATH видит шаг.
   После мержа развёрнутый дом роли на живом пульте обновляет Оператор
   копией референса (порядок описан в docs/stack.md, этой задачей не
   правится).
6. Тесты (tests/): паритет PATH двух провайдеров; ключи окружения
   оболочки присутствуют в обеих половинах (конфиг и команда), если
   выбраны; существующие tests/test_providers_codex.py,
   tests/test_providers.py, tests/test_provider_scoped_step_env.py
   зелёные, ни один не ослаблен.

Зоны: orchestrator/providers/codex.py, orchestrator/runner.py,
docs/reference/role-home/codex/, tests/.

Только чтение (не менять): orchestrator/providers/claude.py,
orchestrator/providers/base.py, orchestrator/doctor/ (зона параллельной
задачи о предполёте analyst), orchestrator/stack.py, orchestrator/session.py, scripts/guard.py, docs/stack.md
(зона пробной задачи 01M3H1Z489CKJ8FHSRS4TYTPX2 в полёте),
orchestrator/catalog.py, docs/backlog.md, tests/test_invariants.py.

Не входит: новая строка `doctor` о паритете окружения (следующей
задачей, когда orchestrator/doctor/ свободен); перевод ролей developer
и test_author на Codex; указатель связки ключей в клоне канарейки.

Рамка: $20.
