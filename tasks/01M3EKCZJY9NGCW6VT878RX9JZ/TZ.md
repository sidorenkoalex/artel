---
task: 01M3EKCZJY9NGCW6VT878RX9JZ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Codex: вход по подписке ChatGPT вместо ключа API; ожидание каталога в test_models

# ТЗ: Codex: вход по подписке ChatGPT вместо ключа API; ожидание каталога в test_models

Источник: план провайдеров ролей (docs/research/providers-codex-plan.md,
раздел 6 п.1 — решение Оператора 22.09.2026: авторизация Codex у ролей —
вход по подписке ChatGPT, а не ключ API; раздел 7.1 — задача 4.1а).
Факты живых запусков Codex CLI 0.155.1 от 22.09 —
docs/research/codex-live-check-2026-09-22.md (раздел «Выводы для задач
линии»). Предшественник смержен: 01M32NH6P053978AER66P0X4GN (провайдер
codex: команда, окружение, дом роли, каталог, doctor). Следующая задача
линии — 01M32NH9QTC1T6FNH8JD79662R (разбор вывода Codex) — стартует после
мержа этой: обе меняют orchestrator/providers/codex.py.

Факты (пин fd83eb5d):
- `CodexProvider.environment` (orchestrator/providers/codex.py) отдаёт
  `HOME`, `CODEX_HOME` дома роли и `OPENAI_API_KEY` из слота keychain
  `config.OPENAI_API_KEY_SLOT` (ambient-переменная сильнее слота);
  `secret_env_names()` — `("OPENAI_API_KEY",)`; `check_token` зовёт
  `doctor.check_codex_api_key` (orchestrator/doctor/preflight.py),
  проверка `codex-api-key` смотрит только наличие ключа.
- Белый список окружения ролей `stack.ROLE_ENV_ALLOWLIST`
  (orchestrator/stack.py) содержит `OPENAI_API_KEY`: заданный Оператором
  ключ сегодня попадает и в шаги ролей на Claude (строка doctor
  `foreign-provider-secrets`, orchestrator/doctor/isolation.py).
- Команда шага несёт переопределения конфигурации `CONFIG_OVERRIDES`
  (сеть песочницы, политика подтверждений), те же ключи дословно стоят в
  референсе дома docs/reference/role-home/codex/config.toml; проверка
  изоляции части 1 сверяет обе половины.
- Живые факты 22.09 (отчёт выше): ключ API у Оператора без баланса, путь
  отменён; вход ChatGPT хранит и продлевает сам Codex в системном
  Keychain при `cli_auth_credentials_store=keyring` и
  `forced_login_method=chatgpt`; `codex exec` читает ключ из
  `CODEX_API_KEY`, а не из `OPENAI_API_KEY`; при изолированном `HOME`
  роли на macOS вход отказывает `persist_failed` («A default keychain
  could not be found»), пока в `.artel/home/Library/Preferences` нет
  указателя на связку ключей (`security default-keychain -d user -s
  <путь связки>` с `HOME` дома роли; связка и секреты не копируются);
  после этого `codex login status` с домом роли отвечает «Logged in using
  ChatGPT», короткий шаг проходит без ключа API.
- `tests/test_models.py::test_three_models_with_status_and_price_date`
  красный на пине (1 из 37): ждёт ровно три модели Claude, а приложение
  `models.yaml` части 1 добавило пять моделей OpenAI при мерже, после CI
  ветки.

Требуется:
1. Вход и шаг задают один способ авторизации: в команду шага codex
   добавляются переопределения `cli_auth_credentials_store=keyring` и
   `forced_login_method=chatgpt`; те же ключи с теми же значениями — в
   референсе `config.toml` дома роли. Проверка изоляции продолжает
   требовать дословного совпадения двух половин.
2. `CodexProvider.environment` отдаёт только дом роли (`HOME`,
   `CODEX_HOME`) и не читает keychain; ключ API роли не передаётся ни из
   слота, ни из окружения Оператора. Запись в Keychain Оператора
   (`artel-openai-api-key`) пульт не удаляет и не читает; судьбу
   константы `config.OPENAI_API_KEY_SLOT` (удалить или оставить с
   пометкой «не используется») обосновать в SPEC.
3. `OPENAI_API_KEY` убирается из `stack.ROLE_ENV_ALLOWLIST`: ключ API
   OpenAI не получает ни одна роль, ни на Codex, ни на Claude.
   `CODEX_API_KEY` и `CODEX_ACCESS_TOKEN` в белый список не входят и не
   добавляются; тест фиксирует отсутствие всех трёх в собранном окружении
   шага роли на обоих провайдерах при заданных ambient-переменных.
4. Проверка `codex-api-key` заменяется проверкой `codex-chatgpt-auth`:
   `codex login status` с окружением дома роли (`HOME`, `CODEX_HOME`) и
   теми же переопределениями авторизации, что у шага; `ok` — только код
   выхода 0 и подтверждённый вход ChatGPT; вывод CLI в строку doctor не
   попадает (секреты); таймаут; отказ называет, что сделать Оператору
   (указатель связки ключей для дома роли и команду входа). Проверка
   действует там же, где сегодняшняя `codex-api-key`: только когда
   `codex` — нужный инструмент. Остаток лимита подписки проверка не
   доказывает — это сказано в тексте строки или документации.
5. Проверки изоляции: у провайдера codex нет секрета, приходящего через
   окружение; любая из переменных `OPENAI_API_KEY`, `CODEX_API_KEY`,
   `CODEX_ACCESS_TOKEN` в собранном окружении шага Codex — провал
   `codex-isolation-smoke`; строка `foreign-provider-secrets` для шагов
   Claude перестаёт называть ключ OpenAI (его больше нет в белом списке).
6. `AGENTS.md` референса дома роли: абзац об авторизации — вход ChatGPT,
   хранит и обновляет CLI, личный вход Оператора и ключи API роль не
   получает.
7. `docs/stack.md`, раздел «Провайдер codex»: вход по подписке вместо
   слота ключа — однократные шаги Оператора (указатель связки ключей для
   дома роли на macOS, команда входа с домом роли), что хранится и как
   обновляется, когда нужен повторный вход, что исключено из окружения;
   список зелёных строк doctor при переводе роли — с `codex-chatgpt-auth`
   вместо `codex-api-key`.
8. `test_three_models_with_status_and_price_date` сверяет фактический
   каталог (три модели Claude и пять OpenAI) с тем же уровнем строгости:
   статус и дата цены у каждой модели; имя теста может измениться,
   ослабление проверки — нет.
9. Роли на Claude не меняются: argv и окружение шага Claude совпадают с
   пином, кроме исчезнувшего `OPENAI_API_KEY`; существующие
   `tests/test_providers.py`, `tests/test_providers_codex.py`,
   `tests/test_stack.py`, `tests/test_doctor.py`,
   `tests/test_runner_role_model.py`, `tests/test_models.py` зелёные;
   перечень обновлённых ожиданий — в PLAN.

Зоны: orchestrator/providers/codex.py, orchestrator/stack.py,
orchestrator/doctor/, orchestrator/config.py,
docs/reference/role-home/codex/, docs/stack.md, tests/.

Только чтение (не менять): orchestrator/runner.py (собирает окружение по
белому списку и зовёт провайдера — правка не нужна; если понадобится —
вопрос расширения зон к Оператору), orchestrator/providers/base.py,
orchestrator/providers/claude.py, orchestrator/providers/__init__.py,
orchestrator/keychain.py, orchestrator/catalog.py,
docs/reference/role-home/claude/, models.yaml (защищённый путь, каталог
не меняется), AGENTS.md и CLAUDE.md (защищённые пути),
docs/research/providers-codex-plan.md и
docs/research/codex-live-check-2026-09-22.md (источники),
docs/backlog.md, .artel/ и .artel/home/Library/Preferences (локальный слой
пульта вне git; указатель связки ставит Оператор).

Не входит: разбор вывода Codex, стоимость шага и сигнатуры провалов
(задача 01M32NH9QTC1T6FNH8JD79662R); сужение белого списка окружения по
провайдеру в runner — токен Claude в шаге Codex (задача 5 линии,
паритет безопасности); автоматическая установка указателя связки ключей
при развёртывании дома роли; выполнение входа ChatGPT, перевод роли на
Codex, живой запуск модели; проверка лимита подписки ChatGPT (задача 6).

Рамка: $50. Живых запусков модели в шагах ролей нет: CLI в тестах
подменяется, `codex login status` — заглушкой процесса.
