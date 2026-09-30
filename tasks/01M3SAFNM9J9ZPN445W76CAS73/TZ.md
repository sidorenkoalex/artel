---
task: 01M3SAFNM9J9ZPN445W76CAS73
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Провайдер opencode (часть 1): запуск ролей на OpenAI-совместимом шлюзе

# ТЗ: Провайдер opencode (часть 1) — запуск ролей на OpenAI-совместимом шлюзе

Источник: ручная проба ассистентской сессии 30.09.2026 (строка копилки
30.09 «Корпоративные модели X5 (copilot.x5.ru…» с дополнениями);
решение Оператора 30.09 завести провайдер.

Факты (пин 34b298c7, проба вне пульта во временном каталоге):
- Корпоративный шлюз `https://api-copilot.x5.ru/v1` — только
  `chat/completions` (вызов инструментов и кэш промпта работают);
  `/v1/responses` — 404. Codex 0.157.1 с `wire_api = "chat"` отказывает
  при загрузке конфигурации («no longer supported»): через провайдер
  `codex` шлюз не подключить.
- OpenCode 1.18.30 (`opencode run --pure -m <провайдер>/<модель>
  --format json`, провайдер `@ai-sdk/openai-compatible`) прошёл
  многошаговую задачу «исправить класс, добавить два метода, прогнать
  pytest» на `x5-airun-code-large` (49 с, 7 шагов) и
  `copilot-code-flash` (7 с, 6 шагов): 4/4 зелёные, тесты не тронуты.
- Поток `--format json`: события `step_start` / `tool_use` (с `tool`,
  `state.status`, `state.input`) / `text` / `step_finish` (`reason`,
  `tokens.input/output/reasoning/cache.read/cache.write`, `cost`). Для
  провайдера шлюза `cost` = 0.
- `opencode run` при стандартном вводе не с терминала ждёт продолжение
  сообщения до конца потока: без `< /dev/null` процесс висел до
  тайм-аута без единой строки (три случая в пробе). Промпт файлом на
  стандартный ввод без аргумента-сообщения (так подаёт промпт
  `orchestrator/runner.py`, `stdin=prompt_file`) принимается: ответ за 3 с.
- При отведённых XDG-каталогах и `OPENCODE_CONFIG` OpenCode всё равно
  читает навыки из `$HOME/.agents/skills` и `$HOME/.claude/skills`
  (предупреждения `duplicate skill name`); при отведённом `HOME` —
  не читает.
- Ключ шлюза один на пульт, лежит в keychain, слот `x5-copilot-api`.
  Лимит шлюза — 5 запросов в секунду на ключ; при исчерпании — 429.
  Квоты токенов на API нет (счётчик кабинета без лимита).
- Шлюз проверяет «вход + max_tokens ≤ контекст модели»; OpenCode по
  умолчанию просит ответ размером с весь контекст — нужен предел ответа
  на модель (`limit.output` в настройках провайдера).
- Образец устройства провайдера — `orchestrator/providers/codex.py`
  (дом роли, изоляция, разбор потока, сигнатуры отказов, предполёт
  `doctor`); реестр — `orchestrator/providers/__init__.py::PROVIDERS`.

Требуется:
1. Провайдер `opencode` в `orchestrator/providers/opencode.py`,
   зарегистрирован в `PROVIDERS`; интерфейс `RoleExecutorProvider` целиком.
   Команда шага — `opencode run --pure --format json -m <провайдер
   шлюза>/<модель>`; промпт — файлом на стандартный ввод, как у codex
   (без аргумента-сообщения). Любой путь запуска OpenCode из пульта
   (шаг, живой смок `doctor`) не оставляет ввод открытым потоком.
2. Окружение шага: `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`,
   `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `OPENCODE_CONFIG` — всегда в дом
   роли (как `CodexProvider.environment`), навыки и конфигурация
   Оператора в шаг не попадают. Секрет — ровно одна переменная ключа
   шлюза из слота keychain `x5-copilot-api` (имя слота — константа
   `config`); `secret_env_names` называет её.
3. Образец настроек дома роли `docs/reference/role-home/opencode/`:
   провайдер шлюза (`@ai-sdk/openai-compatible`, базовый адрес, ключ из
   переменной окружения), модели с `limit.context` и `limit.output`,
   `autoupdate: false`, `share: disabled`, правила `permission` не шире,
   чем у роли на codex.
4. Разбор потока (`parse_output_line`): события пробы → общие
   `StreamEvent`/`ToolCall`/`ToolResult`/`RunResult`; токены по видам —
   из `step_finish`, суммой по шагам. Стоимость — тарифом каталога
   (`cost_from_cli: false`), не полем `cost` OpenCode.
5. Сигнатуры отказов (`failure_signatures`): 429 шлюза — именованная
   причина «лимит шлюза» без немедленного повтора; 400 «контекст
   превышен» — своя причина; прочие — как у codex.
6. Манифест стека (`orchestrator/stack.py`): `opencode` — необязательный
   инструмент, обязательный ровно тогда, когда хоть одна роль разрешается
   на провайдера `opencode` (правило codex). `doctor`: найден CLI, версия
   не ниже минимума, ключ в слоте есть, дом роли сверен с образцом,
   офлайн-смок изоляции (нет навыков и конфигурации Оператора, нет чужих
   секретов, ввод закрыт).
7. Каталог `models.yaml`, раздел `opencode` (защищённый путь — приложением
   к PLAN): `x5-airun-code-large` (GLM-5.3-Flash) и `copilot-code-flash`
   (Qwen3.6-35B-A3B), `status: experimental`, прейскурант — рыночная цена
   разработчика модели по models.dev на 30.09 (GLM-5.3-Flash
   0.15/0.50/0.15/0.03; Qwen3.6-35B-A3B 0.248/1.485/0.248/0.248 —
   запись в кэш и чтение кэша, которых у разработчика нет, равны входу),
   в комментарии записи — модель-источник, основание и дата. Литерал
   перечня моделей в `tests/test_models.py` — той же задачей.
8. `docs/stack.md` — раздел провайдера opencode (как у codex);
   `docs/codebase-map.md` — новый модуль.
9. Тесты в `tests/`: команда шага (ввод закрыт, модель в аргументе);
   окружение (все шесть имён в дом роли, секрет только свой — «Ловит
   мутацию: HOME наследуется»); разбор записанного потока пробы в
   события и токены по видам; 429 → именованная причина без повтора;
   манифест без ролей на opencode не требует CLI; роли на claude и codex
   работают как до задачи.

Зоны: orchestrator/providers/opencode.py, orchestrator/providers/__init__.py,
orchestrator/providers/base.py, orchestrator/stack.py, orchestrator/doctor/,
orchestrator/config.py, docs/reference/role-home/opencode/, docs/stack.md,
docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/providers/claude.py,
orchestrator/providers/codex.py, orchestrator/models.py, orchestrator/runner.py,
orchestrator/roles.py, docs/reference/role-home/claude/,
docs/reference/role-home/codex/, roles.yaml, models.yaml (защищённый путь —
только приложением к PLAN), scripts/guard.py, skills/, templates/,
docs/adr/, docs/invariants.md, tests/test_invariants.py, docs/backlog.md,
tasks/.

Не входит (часть 2): поле `upstream` и отпечаток модели (`prompt_tokens`
пробы + предел контекста из отказа 400) с проверкой перед шагом и
записью фактической модели в журнал; пометка `price_basis: market` в
каталоге и отчётах; ограничение 5 запросов в секунду на всю волну.
Не входит вообще: сверка с внутренними ресурсами X5; перевод боевых
ролей на opencode (решение Оператора после канарейки).

Рамка: $60.
