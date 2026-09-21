---
task: 01M32K876ZCDZW8M5CZ1S5WY9J
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора по батчу вопросов аналитика (QUESTIONS.md, 6 вопросов).

Проверки ассистентской сессии 21.09 на установленном
`/opt/homebrew/bin/codex` (`codex-cli 0.155.1`): без запуска модели —
`codex features list` с разными настройками; с запуском модели (одно
обращение, вход ChatGPT Оператора, пустой временный каталог, песочница
`read-only`, поиск в интернете включён ради цен) — образец потока ниже.

Вопрос 1 — вариант C без флага `--ignore-user-config`.
Факты: `CODEX_HOME=<каталог>` с `config.toml`, где `[features] apps =
false, hooks = false`, даёт в `codex features list` обе функции `false`
— курируемый конфиг читается. Глобальный `--disable <feature>` (флаг
ПЕРЕД подкомандой) выключает каждую из одиннадцати функций: `apps`,
`browser_use`, `browser_use_external`, `browser_use_full_cdp_access`,
`computer_use`, `in_app_browser`, `plugins`, `remote_plugin`,
`plugin_sharing`, `skill_mcp_dependency_install`, `hooks` — проверено
по одной. `-c features.apps=false` работает так же.
Решение: флаг `--ignore-user-config` из команды убрать — конфиг
Оператора и так недостижим переносом `CODEX_HOME` на дом роли, а флаг
выключил бы курируемый файл. Действующий источник — курируемый
`config.toml` референса (сверка `doctor`); критичное ДУБЛИРУЕТСЯ
командой: `--disable` на каждую из одиннадцати функций, выключенная
сеть песочницы и политика подтверждений «никогда» через `-c` (точные
ключи — по документации 0.155.1, обосновать в SPEC). Офлайн-смок
требования 8 проверяет, что команда несёт эти флаги.

Вопрос 2 — вариант A с уточнением.
Факт: справка 0.155.1 — `--ignore-rules`: «Do not load user or project
execpolicy `.rules` files», то есть только файлы политики команд, не
`AGENTS.md`. Решение: `--ignore-rules` остаётся; `AGENTS.md` курируемого
дома — ДЕЙСТВУЮЩИЕ правила роли (как `CLAUDE.md` дома Claude), не
документирующий файл. `AGENTS.md` в корне рабочего каталога — ссылка на
`CLAUDE.md` репозитория («правила для агентов», защищённый путь); роль
под Codex читает его так же, как роль под Claude читает `CLAUDE.md`, —
это паритет, не дыра. Записать это в SPEC явно; полная сверка каналов
инструкций — задача 5.

Вопрос 3 — вариант A. `cache_write` = цена `input`, комментарием в
`models.yaml`: у OpenAI запись кэша отдельно не тарифицируется и
оплачивается как обычный вход. Запрет нулевой цены не трогаем.

Вопрос 4 — модели и цены (вариант A).
Идентификаторы — из `codex debug models` установленной 0.155.1 (без
сети), видимые в списке и с `supported_in_api: true`: `gpt-6-astra`,
`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5` (`gpt-reserve`
и `codex-auto-review` скрыты — не вносить).
Цены — стандартный тариф, USD за 1 млн токенов, источник
https://developers.openai.com/api/docs/pricing, дата 2026-09-21 (получены
через `codex exec` с поиском в интернете; сессия сама страницу открыть
не смогла — проверка Cloudflare; в комментарии раздела указать источник
и способ получения):

| модель | input | cache_read (cached input) | output | cache_write |
|---|---|---|---|---|
| gpt-6-astra | 10.00 | 1.00 | 50.00 | 10.00 |
| gpt-5.6-sol | 4.00 | 0.40 | 20.00 | 4.00 |
| gpt-5.6-terra | 2.00 | 0.20 | 12.00 | 2.00 |
| gpt-5.6-luna | 0.20 | 0.02 | 1.20 | 0.20 |
| gpt-5.5 | 5.00 | 0.50 | 30.00 | 5.00 |

Все пять — `status: experimental`, `min_cli_version: 0.155.1`,
`price_date: 2026-09-21`. Раздел провайдера: `cli: codex`,
`min_cli_version: 0.155.1`, `cost_from_cli: false`.

Вопрос 5 — вариант A: `reasoning_output_tokens` — ЧАСТЬ
`output_tokens`, отдельно не складывается. Факт живого запуска 0.155.1:
`output_tokens` 8513, `reasoning_output_tokens` 997.

Вопрос 6 — образец на 0.155.1 есть (ниже); тексты провалов — вариант
B: неизвестный провал Codex — `system_candidate` (повтор с бэкоффом, как
у Claude); сигнатура `model_unsupported` и иные классы наполняются по
живым случаям в задаче 6. Требование 5 в этой задаче — механизм
сигнатур у провайдера `codex` и класс по умолчанию, без выдуманных
текстов.

Образец потока 0.155.1 (по одной строке на каждый вид события/элемента;
длинные поля сокращены многоточием, итоговая строка — целиком):

```
{"type": "thread.started", "thread_id": "01a0c53e-4d52-7e53-8232-be96a03789f6"}
{"type": "turn.started"}
{"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "Проверю официальные цены OpenAI…"}}
{"type": "item.started", "item": {"id": "item_1", "type": "command_execution", "command": "/bin/zsh -lc 'cat …/SKILL.md'", "aggregated_output": "", "exit_code": null, "status": "in_progress"}}
{"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "command": "/bin/zsh -lc 'cat …/SKILL.md'", "aggregated_output": "---\nname: \"openai-docs\"…", "exit_code": 0, "status": "completed"}}
{"type": "item.started", "item": {"id": "exec-3892ad65-…", "type": "web_search", "query": "", "action": {"type": "other"}}}
{"type": "item.completed", "item": {"id": "exec-3892ad65-…", "type": "web_search", "query": "site:developers.openai.com API pricing …", "action": {"type": "search", "queries": ["…"]}}}
{"type": "item.started", "item": {"id": "item_9", "type": "mcp_tool_call", "server": "cua_repl", "tool": "js", "arguments": {"code": "let browser = await cua.getBrowser({url:\"https://developers.openai.com/api/docs/pricing\"});", "title": "…"}, "result": null, "error": null, "status": "in_progress"}}
{"type": "item.completed", "item": {"id": "item_9", "type": "mcp_tool_call", "server": "cua_repl", "tool": "js", "arguments": {…}, "result": {"content": [{"type": "text", "text": "No browser is available"}, …]}, "error": null, "status": "failed"}}
{"type": "turn.completed", "usage": {"input_tokens": 1310229, "cached_input_tokens": 1072000, "cache_write_input_tokens": 0, "output_tokens": 8513, "reasoning_output_tokens": 997}}
```

Что из него следует для разбора: вызов инструмента — пара
`item.started`/`item.completed` одного `item.id`; виды элементов
`command_execution` (поля `command`, `aggregated_output`, `exit_code`,
`status`), `web_search`, `mcp_tool_call` (`server`, `tool`,
`arguments`, `result`, `error`), `agent_message` (`text`); итог — только
`turn.completed`. В этом запуске: `command_execution` с `exit_code` 0 и
`status: completed`, `command_execution` с `exit_code` 6 и `status:
failed`, `mcp_tool_call` с `status: failed` при `error: null` — признак
ошибки результата брать из `status`, не из `error`; незнакомый вид
элемента или события — `other`, не ошибка.

Находка для безопасности (основание требования 3): в этом запуске, в
песочнице `read-only`, но с пользовательским конфигом Оператора, CLI
вызвал `mcp_tool_call` сервера `cua_repl` («Computer Use») и попытался
открыть браузер на машине Оператора — не вышло только потому, что
браузера не было. Функции `computer_use`, `browser_use*`, `apps`,
MCP-серверы в доме роли выключаются обязательно, и офлайн-смок это
проверяет. Расход этого запуска — 1.31 млн входных токенов (1.07 млн из
кэша) на один вопрос: учесть в калибровке задачи 6.
