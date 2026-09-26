---
task: 01M32K876ZCDZW8M5CZ1S5WY9J
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Провайдер codex: запуск codex exec, дом роли, ключ API, разбор вывода

Источник: план провайдеров ролей, принятый Оператором 20.09
(docs/research/providers-codex-plan.md, задача 4 «Провайдер codex»;
раздел 5 «Особенности Codex CLI»; решения Оператора 20.09: авторизация
Codex у ролей — ключ API `OPENAI_API_KEY`, сеть роли под Codex
запрещена, смешанные ярусы разрешены, тариф — публичный прейскурант
модели из `models.yaml`). Предшественники смержены: задача 1
(01M2ZNTHSN — пакет `orchestrator/providers/`), задача 2 (01M3009Y9A,
01M300A14K — каталог, ярусы, тариф на модель), задача 3 (01M31ZHSA6 —
разбор вывода, стоимость и сигнатуры провалов у провайдера; 01M31ZHWJW —
токены в `status`/RETRO/`report`).

Факты:
- Интерфейс провайдера — `orchestrator/providers/base.py::
  RoleExecutorProvider`: `command(model)`, `environment(role, task_id)`,
  `home_reference()`, `preflight(role)` и его части (`check_cli_found`,
  `check_cli_version`, `check_token`, `check_home_reference`),
  `cli_tool()`, `installed_cli_version()`, `model_verdict(model)`,
  `live_smoke_command(prompt)`, разбор строки вывода в событие общего
  вида (`ToolCall`, `ToolResult`, `RunResult` — после 01M31ZHSA6),
  сигнатуры классов провала. Единственная реализация —
  `orchestrator/providers/claude.py::ClaudeProvider`; реестр —
  `orchestrator/providers/__init__.py::PROVIDERS`.
- Манифест стека (`orchestrator/stack.py`) собирает `REQUIRED_TOOLS` из
  `cli_tool()` всех провайдеров реестра: зарегистрированный провайдер
  сегодня автоматически становится ОБЯЗАТЕЛЬНЫМ инструментом пульта.
- Каталог `models.yaml` (защищённый путь) несёт раздел провайдера
  (`cli`, `min_cli_version`, `cost_from_cli`, модели с прейскурантом по
  четырём видам). Раздела `codex` нет.
- Токен роли Claude приходит из слота keychain
  (`orchestrator/keychain.py::token(slot)`) переменной окружения;
  ambient-переменная Оператора сильнее слота.
- Установленный Codex CLI на машине Оператора (21.09): стабильная
  установка Homebrew `/opt/homebrew/bin/codex`, `codex-cli 0.155.1` —
  тот же способ, что у Claude Code (`/opt/homebrew/bin/claude`); пульт
  находит его резолвом манифеста по PATH. Альфа-сборка внутри ChatGPT.app
  (`0.154.0-alpha.6.2`) для пульта не используется — меняется молча с
  обновлением приложения. Минимальная версия провайдера — 0.155.1, если
  аналитик не обоснует иную. `codex exec` (проверено на 0.155.1 без
  запуска модели): промпт аргументом или со stdin (`-`), `--json`
  (события JSONL в stdout), `-m/--model`, `-s/--sandbox
  read-only|workspace-write|danger-full-access`, `-C/--cd <каталог>`,
  `--skip-git-repo-check`, `--ephemeral`, `--ignore-user-config` (не
  читать `$CODEX_HOME/config.toml`, авторизация остаётся из
  `CODEX_HOME`), `--ignore-rules`, `-c key=value` (переопределение
  конфига), `--enable/--disable <feature>`, `--strict-config`,
  `-o/--output-last-message <файл>`. Флага политики подтверждений у
  `exec` нет (задаётся конфигом). Вход Оператора (`codex login status`:
  «Logged in using ChatGPT», `~/.codex`) роли не передаётся; `codex
  login --with-api-key` читает ключ со stdin — роли не нужен, ключ
  приходит переменной `OPENAI_API_KEY`.
- Функции, включённые по умолчанию (`codex features list`, 0.155.1):
  `apps`, `browser_use`, `browser_use_external`,
  `browser_use_full_cdp_access`, `computer_use`, `in_app_browser`,
  `plugins`, `remote_plugin`, `plugin_sharing`, `hooks`,
  `skill_mcp_dependency_install`. План 20.09 исходил из «хуков у Codex
  нет» — в этой версии хуки есть (`hooks` stable).
- Формат событий `--json` на живом запуске: см. «Образец потока» ниже.

Требуется:
1. Провайдер `codex` — `orchestrator/providers/codex.py::CodexProvider`,
   запись в `PROVIDERS`. Команда шага: `codex exec --json` с явной
   моделью (`-m`), рабочим каталогом задачи (`-C`), песочницей
   `workspace-write` с выключенной сетью, без подтверждений (политика
   конфигом), промптом со stdin, без сохранения сессии на диск
   (`--ephemeral`), без пользовательского конфига и правил Оператора
   (`--ignore-user-config`, `--ignore-rules`). argv[0] — абсолютный путь
   из резолва манифеста, как у Claude. Точный набор флагов сверить с
   `codex exec --help` установленной версии и обосновать в SPEC.
2. Окружение роли: `CODEX_HOME` на курируемый каталог `.artel/home/.codex`
   (переписывается всегда, не наследуется от Оператора); ключ
   `OPENAI_API_KEY` из отдельного слота keychain (имя слота — в
   `config.py`), ambient-переменная Оператора сильнее слота — тем же
   приёмом, что токен Claude. Никакой другой авторизации (вход через
   ChatGPT, `auth.json` Оператора) роль не получает.
3. Курируемый дом роли — референс `docs/reference/role-home/codex/`:
   `config.toml` (модель не задаётся — только флагом; сеть песочницы
   выключена; политика подтверждений «никогда»; ВЫКЛЮЧЕНЫ функции
   `apps`, `browser_use*`, `computer_use`, `in_app_browser`, `plugins`,
   `remote_plugin`, `plugin_sharing`, `skill_mcp_dependency_install`,
   MCP-серверов нет; хуки — выключены, если аналитик не предложит
   использовать их как аналог `bash_guard` — тогда обосновать в SPEC) и
   `AGENTS.md` с правилами роли по смыслу CLAUDE.md дома Claude.
   Развёртывание и сверка развёрнутого слоя с референсом — теми же
   механизмами, что для Claude (`home_references()`, `doctor`).
4. Разбор вывода: `parse_output_line` провайдера переводит события JSONL
   Codex в событие общего вида. Итог запуска — из события завершения
   хода (`turn.completed` или фактическое имя по образцу) с `usage`:
   кэшированный вход ВЫЧИТАЕТСЯ из входа, если входит в него (сверить
   по образцу); токены рассуждений идут в `output`; `cache_write` — если
   поле есть, иначе 0. Стоимости от CLI нет: `usd is None`, стоимость
   считает пульт по тарифу модели (путь 01M31ZHSA6, `cost_from_cli:
   false`).
5. Сигнатуры провалов Codex: тексты лимитов, неверного ключа, модели,
   недоступной для ключа, обрыва — в общих классах пульта (`1a`, `1b`,
   `stream_broken`, `session_limit` не применяется — у ключа API нет окна
   подписки, `system_candidate`, `model_unsupported`). Источник текстов —
   образец и документация установленной версии; неизвестное — в
   `system_candidate`, как у Claude.
6. Манифест: инструмент `codex` НЕОБЯЗАТЕЛЬНЫЙ — пульт без Codex
   проходит `doctor` и запускает роли на Claude как сегодня; `codex`
   обязателен только тогда, когда ярус хотя бы одной agent-роли
   разрешается в модель провайдера `codex` (иначе — отказ `run`/`auto`
   до старта агента и красная строка `doctor`, как у отсутствующего
   Claude). Минимальная версия CLI — у провайдера и в каталоге.
7. Каталог: раздел `codex` в `models.yaml` — `cli: codex`,
   `min_cli_version`, `cost_from_cli: false`, модели OpenAI, доступные
   для `codex exec` по ключу API, с публичным прейскурантом по четырём
   видам и датой; статус `experimental` до зелёной канарейки на наборе
   «роль на Codex» (задача 6). `models.yaml` — защищённый путь:
   правка приложением к PLAN.
8. Предполётные проверки и `doctor`: бинарник найден и версия ≥
   минимума; ключ в слоте (есть/нет, без значения); дом роли совпадает
   с референсом; офлайн-смок изоляции (собранная команда несёт
   песочницу, выключенную сеть, `--ignore-user-config`, `CODEX_HOME` на
   дом роли, нет ключей Оператора в окружении кроме `OPENAI_API_KEY`);
   живой смок по команде (`live_smoke_command`) — только по явному
   запуску Оператора, не в обычном `doctor`.
9. Документация: `docs/stack.md` — раздел «Провайдер codex»: установка
   CLI, слот ключа, дом роли, что выключено и почему, как перевести роль
   на Codex (ярус в `.artel/models.yaml`).
10. Тесты (tests/): команда и окружение провайдера (без запуска CLI);
    разбор образца потока — события, итог, вычет кэша, токены
    рассуждений; стоимость шага по тарифу для модели `codex`; сигнатуры
    провалов; манифест — пульт без `codex` зелёный, ярус на `codex` без
    CLI — отказ до старта; `doctor` ok/fail по каждой новой проверке;
    дом роли разворачивается и сверяется. Существующие
    `tests/test_providers.py`, `tests/test_stack.py`, `tests/test_doctor.py`,
    `tests/test_runner_role_model.py`, `tests/test_models.py` остаются
    зелёными; перечень обновлённых ожиданий — в PLAN.

Зоны: orchestrator/providers/, orchestrator/stack.py,
orchestrator/doctor/, orchestrator/config.py,
docs/reference/role-home/codex/, docs/stack.md, tests/.

Приложением: models.yaml (раздел `codex`) — защищённый путь, применяет
пульт на мерже.

Только чтение (не менять): orchestrator/providers/claude.py (поведение
Claude не меняется), orchestrator/runner.py (зовёт провайдера роли —
после задачи 1 и 3 правка не нужна; если понадобится — вопрос
расширения зон к Оператору), orchestrator/spend.py,
orchestrator/agent_log.py, orchestrator/failure_classification.py,
orchestrator/models.py, orchestrator/keychain.py, orchestrator/catalog.py,
docs/reference/role-home/claude/, AGENTS.md и CLAUDE.md (защищённые
пути), docs/research/providers-codex-plan.md (источник), docs/backlog.md,
.artel/ (локальный слой пульта вне git).

Не входит: паритет безопасности (таблица «запрет у Claude → чем закрыт у
Codex», ADR, проверка утечки пула по логам Codex, тесты границ рабочего
каталога — задача 5); канарейка, бейзлайны и калибровка для набора «роль
на Codex», лимиты подписки (задача 6); перевод какой-либо роли на Codex
в пульте Оператора (решение Оператора после задачи 6); установка Codex CLI
на машине Оператора; вход через ChatGPT.

Образец потока (записан 21.09 ассистентской сессией с разрешения
Оператора: `codex exec --json --ephemeral --skip-git-repo-check -s
read-only -C <пустой временный каталог> "Ответь одним словом: готово"`,
codex-cli 0.154.0-alpha.6.2 — до установки 0.155.1, авторизация — вход
ChatGPT Оператора, rc=0; формат сверить с 0.155.1 по документации). stdout целиком, четыре строки:

```
{"type":"thread.started","thread_id":"01a0c52c-30bd-7132-a86a-56b86bd8602d"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"готово"}}
{"type":"turn.completed","usage":{"input_tokens":17382,"cached_input_tokens":12416,"cache_write_input_tokens":0,"output_tokens":6,"reasoning_output_tokens":0}}
```

Что из него следует:
- События: `thread.started`, `turn.started`, `item.completed` (элемент
  `agent_message` с текстом), `turn.completed` с `usage`. Модели в
  событиях нет — модель шага пульт знает сам (флаг `-m`).
- `usage`: `input_tokens` 17382, `cached_input_tokens` 12416 (меньше
  входа — кэшированный вход ВХОДИТ в `input_tokens`, вычитается:
  `input` = 4966, `cache_read` = 12416), `cache_write_input_tokens` 0,
  `output_tokens` 6, `reasoning_output_tokens` 0 (входит в выход или
  нет — по документации установленной версии, обосновать в SPEC).
- Стоимости в долларах нет ни в одном событии.
- Вызовов инструментов в образце нет: элементы `command_execution`,
  `file_change`, `mcp_tool_call`, `reasoning` и события `item.started`/
  `item.updated` разбор берёт из документации установленной версии;
  неизвестный вид события/элемента — `other`, не ошибка.
- stderr того же запуска: пять строк `ERROR rmcp::transport::worker …
  AuthRequired` — CLI поднимал MCP-серверы из пользовательского
  `~/.codex/config.toml` Оператора (запуск был без
  `--ignore-user-config`). Прямое основание требований 1-3: роль не
  читает конфиг Оператора, MCP-серверов у роли нет.
- 17 тыс. входных токенов на однословный промпт — собственный
  системный промпт CLI; учитывать в калибровке задачи 6.

Рамка: $85. Задача крупная (провайдер целиком: команда, окружение, дом,
разбор, провалы, манифест, doctor); если сигналы деления сработают,
аналитик вправе предложить деление, например «провайдер: команда,
окружение, дом, манифест, doctor» и «разбор вывода, стоимость и провалы
Codex» — решение на гейте SPEC.
