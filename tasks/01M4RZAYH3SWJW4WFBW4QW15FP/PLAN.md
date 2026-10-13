---
task: 01M4RZAYH3SWJW4WFBW4QW15FP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Метрика разведки роли — команда `explore-stats` и блок в `report`

## Подход
Одна чисто читающая функция сводки `explore_metric.summarize(steps, now,
days, roles)` в новом модуле `orchestrator/explore_metric.py`; оба
потребителя — команда `explore-stats` и блок `report` — зовут её и общий
текстовый вывод `explore_metric.render_lines`, поэтому на одних данных
числа совпадают по построению (AC-15).

Ключевые решения:
- Модуль не импортирует `report`/`artel`; `_LOG_PATH_RE` объявлен заново
  тем же текстом `r"лог: (.+?), промпт: "`. Константы строки лога —
  `claude.TOOL_CALL_LINE_PREFIX`/`TOOL_ARGUMENT_LIMIT`, имена Codex —
  `codex.COMMAND_ITEM`/`FILE_CHANGE_ITEM`, префиксы и сегменты путей —
  `providers/base.py` (`WORKTREE_LOG_PREFIX`, `DOCS_LOG_PREFIX`,
  `WORKTREES_SEGMENT`, `DOCS_SEGMENT`…), действия стоимости —
  `retro.TOKEN_JOURNAL_ACTIONS`; литералов-дубликатов нет.
- `summarize` сама отбирает «agent run started» и действия стоимости,
  сортирует по `id`, связывает шаг с ближайшей следующей записью стоимости
  той же задачи и роли (следующий «agent run started» той же пары
  перехватывает ожидание — п. 5); фильтр «только задачи из `tasks`» — у
  вызывающих (команда — по `store.all_tasks`, отчёт — уже отфильтрованный
  `_all_steps`).
- Одна функция нормализации `normalize(path, task_id)` → (форма, путь)
  для `wt:`, `docs:`, абсолютных путей обеих раскладок; `edit_kind` и
  `read_key` построены на ней (п. 3, п. 6). Усечённость меряется по
  аргументу строки целиком (О-1).
- Поиск в Bash — собственный токенизатор строки оболочки (кавычки,
  разделители `; && || | ( $(` вне кавычек), первая команда
  `grep`/`rg`/`git grep` в начале команды; шаблон — `-e`/`--regexp`, иначе
  первый аргумент без `-` с пропуском флагов со значением.
- «Шагов» — шаги, чей лог прочитан; запись без лога или с нечитаемым логом
  идёт только в «логов не найдено» (медианы по ней не определены).
- `report._render` получает `now` keyword-only аргументом от `cmd_report`;
  блок — своя константа `EXPLORE_WINDOW_DAYS` (= `explore_metric.DEFAULT_DAYS`
  = 7), `OPERATOR_WINDOW_DAYS` не тронут; новых запросов к БД блок не
  делает (передаётся уже прочитанный `steps`).
- Команда: `explore_metric.cmd_explore_stats(rest)` — разбор `--days`/`--role`
  с именованными отказами (`sys.exit` текстом), три выборки
  `store.steps_of_action`, слияние по `id`; в таблице `artel.main` и в
  разделе «Команды:» справки; `_ROLE_ALLOWED_COMMANDS` не тронут.

Бюджет SPEC ($45) не пересматривается: три файла кода, один файл тестов.

## Шаги
1. `orchestrator/explore_metric.py`: нормализация пути, класс правки, ключ
   чтения, разбор поиска Bash, `summarize`, `render_lines`,
   `cmd_explore_stats`.
2. `orchestrator/artel.py`: импорт модуля, строка справки, запись
   `explore-stats` в таблице `main`.
3. `orchestrator/report.py`: `EXPLORE_WINDOW_DAYS`, `_explore_html`, секция
   «Разведка ролей (последние 7 дней)» в `_render`, `now` из `cmd_report`.
4. `tests/test_explore_metric.py` — свойства разбора поиска, не покрытые
   долгоживущими файлами задачи (`-e`/`--regexp`, `git grep`, `$(`,
   разделители в кавычках); каждый тест проверен временной мутацией
   (`$(` убран из начал команды, `-e` убран из флагов шаблона, кавычки не
   распознаются — каждый раз тест красный, код возвращён).
5. `python3 scripts/codebase_map.py` — карта пересобрана.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1, 4 |
| 7 | 1, 2 |
| 8 | 3 |
| 9 | 4 (+ долгоживущие файлы задачи) |
| 10 | 5 |

Проверка: `tests/test_01m4rzayh3swjw4wfbw4qw15fp_summarize.py` и
`tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py` — 33 passed
(повторно с новыми зёрнами — зелёные); планка `plank-run` — 2 passed;
`tests/test_report.py`, `test_01m4nz5w9ztkgtw7dgzqgmp2gp_*`,
`test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`,
`test_artel_role_restricted_commands.py`,
`test_01m3xtf5506gf43hd51ece230t_role_refusal.py`,
`test_cmd_approve_dispatch.py`, `test_codebase_map.py` — зелёные.
Полный набор `suite-run` №1: зелёный, прошло 5252, упало 0, пропущено 2.

## Влияние на систему
- Новый модуль только читает (БД — SELECT через `store.all_tasks`/
  `steps_of_action`, логи — `read_text`), git не зовёт (AC-14).
- `report`: добавлена одна секция; остальные блоки и их вход не меняются,
  число запросов к `steps` не растёт (блок работает на уже прочитанном
  `steps`). Сигнатура закрытой `_render` расширена keyword-only `now` —
  единственный вызывающий `cmd_report`.
- `artel.py`: новая строка таблицы и справки; белый список команд роли не
  расширен — под ролью команда отказывает (закрытый по умолчанию список).
- Гейты, лимиты, инварианты, существующие тесты не тронуты.
- Откат — revert коммита задачи (новый файл модуля + три правки).

## Риски
- Метрика эвристична по природе (известные слепые зоны SPEC «Не входит»:
  запись оболочкой, чтения через `cat`/Codex).
- Полный журнал (десятки тысяч записей) сортируется в Python при каждом
  `report` — линейно-логарифмически по уже материализованному списку,
  без новых запросов.

## Предложения системе
- `orchestrator/report.py` и `explore_metric.py` теперь оба держат разбор
  строки вызова лога (`_tool_calls`) и `_LOG_PATH_RE`; SPEC запрещает
  импорт `report`, поэтому общий разборщик строки лога просится в
  `agent_log.py` или `providers/base.py` отдельной задачей.
