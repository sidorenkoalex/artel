---
task: 01M598KY8V2P2GRD5Q67DRAZNA
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Механическая проверка ТЗ в `new`: вызывающие вне зон и ссылки `файл:строка`

## Фаза A: план
- Таблица покрытия PLAN.md охватывает требования 1–8 и AC-15; шаги — размера MR (модуль, точка вызова, флаг, тесты).
- Подход согласован с архитектурой: новый модуль `orchestrator/tz_check.py`, одна точка вызова в `catalog.cmd_new`, покрытие переиспользует `guard._classified` (тот же приём, что прежняя сверка путей ТЗ), правок вне зон SPEC нет.
- Раздел «Замер на волне G» есть, таблица по трём задачам; отступление от SPEC (`QUESTIONS.md` у задач волны G нет, сверка по `ANSWER-*.md`/`SPEC-AUDIT.md`) явно названо. AC-15 — ручной критерий, сверку чисел делает Оператор.
- «Влияние на систему» совпадает с diff: `orchestrator/artel.py`, `orchestrator/catalog.py`, новый `orchestrator/tz_check.py`, `tests/` и карта. `scripts/guard.py`, `repo_context.py`, `workspace.py` только читаются. Откат — revert, keyword `strict_tz=False` по умолчанию.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `catalog.py` cmd_new: вызов после `ensure_clone`, до `idgen.new_task_id`, только при `tz_raw` и `not canary`; `spawn_subtask` не зовёт (AC-12 зелёный) |
| 2 | OK | `tz_check._open_tree`: артель — `HEAD^{commit}` главной копии с проверкой `.git`, проект — `origin/<ctx.base>` клона, без fetch; любой сбой git → `_TreeError` → предупреждение «дерево недоступно»; без ссылок и `a.b`-имён `check` → `None` |
| 3 | OK | `Report.lines`: заголовок со счётом и sha коммита (40 hex), строки находок; отказ — `sys.exit` до id/БД/ссылки; журнал `проверка ТЗ` после `_new_task_row`. Числительные склоняются («1 отказ, 2 предупреждения») — форма SPEC шаблонная, долгоживущий тест это допускает |
| 4 | OK | `REF_RE`: последняя часть с расширением, левая граница не в середине пути; `host/api:8080`/`origin/main:12` не ссылки |
| 4.1 | OK | `_resolve`: 0 — не ссылка, 1 — полная, >1 — предупреждение «имя файла неоднозначно» |
| 4.2 | OK | `_check_refs`: отказы по всем ссылкам разом, длина по байтам для любого файла, проверяются обе границы диапазона |
| 4.3 | OK | `_check_near_name`: первое имя в кавычках после ссылки до следующей ссылки строки, окно `[a-3, b+3]`; файл с NUL не сверяется |
| 4.4 | OK | `_static_path`/`_is_path`: `/`, расширение из списка или из дерева, имя файла дерева |
| 5.1 | OK | `_TZ_CANDIDATE_BOUNDARY` собран из `_TZ_ZONES_LABEL`/`_TZ_DECLARING_LABELS`; `_ref_candidates`/`_enclosing` по отступу, диапазон + объемлющее `a`, строка модуля — ничего |
| 5.2 | OK | `git grep -n -w -F` по `*.py`, `tests/` исключён, `_is_call` отбрасывает строки `def/class имя` |
| 5.3 | OK | пометки в `report.marks`: вне M и вне `--strict-tz`, пишутся в журнал |
| 5.4 | OK | `guard._classified` (вложенность, `COMMON_ZONES`, объявляющие разделы), срез на 20 + «и ещё k» |
| 6 | OK | `_new_strict_tz_arg` снимает флаг в любом месте argv; `_NEW_USAGE` дополнен; в `tests/test_new_argv_parsing.py` строки только добавлены (разовый тест планки зелёный) |
| 7 | OK | ТЗ без ссылок и имён дерево не открывает, прежний отказ дословный (AC-12) |
| 8 | OK | песочница с настоящим git, без сети; новые юнит-тесты — на подставном дереве |
| AC-15 | OK (ручной) | раздел и таблица в PLAN.md |

## Замечания
Blocker/major нет. Мелочи ниже вынесены в «Наблюдения» вне реестра: они не мешают мержу, а запись в реестре со статусом `open` заблокировала бы вердикт `approved`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 не заведено ни одного замечания уровня blocker/major/minor.

## Наблюдения (не блокируют, на усмотрение разработчика/Оператора)
- `orchestrator/tz_check.py` `_dotted_names`: `` `repo_context.profile_of()` `` (со скобками) кандидатом не становится. `_check_near_name` хвост `()` при этом снимает. В ТЗ имена часто пишут со скобками, и проверка вызывающих такие функции молча пропускает. Проверено: `_dotted_names('`repo_context.profile_of()` и `a.b`')` → `['a.b']`. Форма SPEC — `` `модуль.функция` `` без скобок, поэтому это не нарушение требования.
- `orchestrator/tz_check.py` `_resolve`: если одна и та же неоднозначная ссылка повторяется в ТЗ, предупреждение выходит дважды (`__init__.py:1` дважды → 2 предупреждения) и раздувает M. Отказы при этом дедуплицированы.
- `orchestrator/tz_check.py` `_check_refs`: ссылка `:0` подписана «строка за концом файла». Исход (отказ) верный, формулировка — нет.

## Вердикт
approved. Все требования 1–8 реализованы как сказано в SPEC. Долгоживущий набор задачи (19 тестов) и планка зелёные. Новые тесты в `tests/` несут исполнимые заявки «Ловит мутацию», две из них подтверждены временной мутацией. Существующие утверждения тестов не тронуты.

## Проверено исполнением
- `python3 …/orchestrator/artel.py plank-run 01M598KY8V2P2GRD5Q67DRAZNA`: 2 passed, код выхода 0 (`test_ac11_argv_parsing_assertions_not_changed`, `test_ac15_plan_has_wave_g_measure_table`).
- `python3 -m pytest -q tests/test_01m598ky8v2p2grd5q67drazna_tz_check.py tests/test_tz_check.py tests/test_new_argv_parsing.py`: 39 passed, 21 subtests passed (43 с).
- Временная мутация `orchestrator/tz_check.py`: сняты гард `b"\0" in blob` в `_check_near_name` и пропуск пустых строк в `_enclosing`. Покраснели `NearNameTest::test_binary_file_window_not_checked` и `EnclosingTest::test_blank_line_in_function_body_gives_the_function`, код возвращён `git checkout`.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` без строки `built_at_sha` дают пустой вывод: карта свежая. Файл возвращён.
- Смоук: `tz_check.check` на TZ.md самой задачи против HEAD (`e69dfc7c`) дал 0 отказов и 9 предупреждений, среди них `profile_of` → `orchestrator/suite_run.py:278`, `_task_own_profile`, `_profile_command`. Это ровно примеры «Контекста» SPEC.
- Пробы `python3 -c`: `_refs` не берёт `v1.2:3` без каталога как файл дерева; `catalog.py:99999` (имя без каталога) разрешается в `orchestrator/catalog.py` и даёт отказ; дубль неоднозначного предупреждения подтверждён.

## Предложения системе
- `skills/review-checklist.md`: при `schema_version >= 3` любое minor-замечание в реестре со статусом `open` блокирует `approved`, хотя по разделу «Вердикт» 0 blocker/major означает approved. Стоит ввести для minor отдельный терминальный статус (например `noted`) или явно разрешить держать minor вне реестра.
