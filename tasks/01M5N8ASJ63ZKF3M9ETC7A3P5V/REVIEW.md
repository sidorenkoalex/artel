---
task: 01M5N8ASJ63ZKF3M9ETC7A3P5V
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: CR-8, этап 1 — самодостаточная часть выкладки планки в `orchestrator/plank_layout.py`; публичные имена для закрытых имён `acceptance`

## Фаза A: план
- Покрытие: таблица PLAN закрывает требования 1–11, у каждого есть шаг или раздел. Требования 5 и 10 закрыты разделами «Поиск подмен тестами» и «Файлы tests/, прогнанные адресно», как требует AC-8.
- Размер шагов разумный: перенос, имена, `_durations_reader`, карта, прогоны.
- Конфликтов с архитектурой нет. Направление импорта `acceptance → plank_layout → gitcmd` не создаёт цикла. Отличие в связывании внутри `plank_layout.plank_layout` (глобалы нового модуля) PLAN называет честно, и оно сверено поиском подмен (см. ниже).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Тела в `orchestrator/plank_layout.py` дословны, с поправкой на внутренние имена. Публичные имена и закрытые `_inside`/`_layout_parent`/`_LAYOUT_ID` — как в требовании. Тексты всех 11 констант я сверил скриптом с `2b187a3d:orchestrator/acceptance.py`: все совпадают. Импортов `acceptance` нет. Правки докстрингов (`acceptance._layout_check`, `exclude_layout`) косметические. |
| 2 | OK | `_layout_ignore`, `_layout_check`, `_plank_plan`, `_component_layout`, `_laid_plank` остались в `acceptance.py`, их тела не тронуты. |
| 3 | OK | Блок реэкспорта `acceptance.py:1199–1222` присваивает тот же объект; AC-3 зелёный. Внутренние вызовы `acceptance.py` по-прежнему идут через прежние имена. |
| 4 | OK | 13 двойников в конце `acceptance.py`, `_last_full_suite_metrics` двойника не получил; 8 вызывающих модулей переведены (diff). Остальные обращения AC-6 не находит. |
| 5 | OK | Результат поиска есть в PLAN. Я повторил grep по `tests/` для перенесённых имён выкладки во формах `patch.object`/строкового `patch`/присваивания — пусто. |
| 6 | OK | Блок раннеров, `run_full_suite`, логика вердикта, argv, окружение и ключ кэша в diff не тронуты. |
| 7 | OK | `acceptance.py:2710–2716`: импорт внутри `try`. |
| 8 | OK | Долгоживущие файлы test_author покрывают (а)–(д). Заявки «Ловит мутацию» исполнимы, две из них я проверил временной мутацией (см. «Проверено исполнением»). |
| 9 | OK | `python3 scripts/codebase_map.py` на HEAD 7e202263 не даёт расхождений вне `built_at_sha`. |
| 10 | OK | В `tests/` против базы добавлены только два новых файла задачи. Адресный прогон есть в PLAN, выборку я повторил сам. |
| 11 | OK | Вне `acceptance.py`/`plank_layout.py` правки ограничены заменой обращения; `tests/` — только новые файлы. |

## Замечания
- minor — `orchestrator/advance_gates/two_sided.py:301`, `orchestrator/advance_gates/outcome_integrity.py:822` — после переименования вызова (имя стало на символ короче) строка-продолжение аргументов сдвинулась на один пробел от открывающей скобки. Поведение не меняется, страдает только выравнивание. Можно поправить попутно в этапе 2; блокером не считаю.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: единственное замечание minor (вкусовое) в реестр не заводится.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py tests/test_01m5n8asj63zkf3m9etc7a3p5v_durations_reader_failure.py tests/test_acceptance_plank_exclude_lock.py tests/test_acceptance_plank_layout_refusal.py tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py tests/test_task_component_places.py -p no:cacheprovider -q -n 0`: `49 passed, 201 subtests passed in 17.58s`.
- `artel.py plank-run 01M5N8ASJ63ZKF3M9ETC7A3P5V`: `4 passed`, код выхода pytest 0.
- Временная мутация 1: импорт `suite_durations` вынесен перед `try` в `_durations_reader`. `test_ac7_import_failure_keeps_run` покраснел: «исключение из прогона наружу: ModuleNotFoundError…». Код возвращён.
- Временная мутация 2: в `doctor/machine_load.py` возвращено `doctor.acceptance._process_snapshot()`. `test_ac6_…` покраснел и назвал `orchestrator/doctor/machine_load.py:9: acceptance._process_snapshot`. Код возвращён, `git status` чистый.
- Скриптом сравнил тексты 11 констант `plank_layout` с базой `2b187a3d`: все `True`. В `acceptance.py` по-прежнему используются `fcntl`/`shutil`/`NamedTuple`/`contextlib`, мёртвых импортов после переноса нет.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без `built_at_sha`: пусто, карта свежая.
- `grep` по `tests/` на подмены перенесённых имён выкладки у `acceptance`: подмен нет.

## Предложения системе
- Команды `rm`/`ls` в шаге ревьювера отклоняются окружением («command not found»/запрос подтверждения), и временный файл в каталоге документов пришлось удалять через `python3 -c os.remove`. Ревьюверу стоит держать временные скрипты вне каталога документов, иначе их подхватит автокоммит.
