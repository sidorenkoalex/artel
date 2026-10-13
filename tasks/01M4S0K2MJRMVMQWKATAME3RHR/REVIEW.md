---
task: 01M4S0K2MJRMVMQWKATAME3RHR
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Команда `knowledge` для роли — карточки по месту, журнал обращений, подсказка в миссии (К-4б)

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–14 разнесены по шагам 1–6.
- Шаги размером с MR (по одному модулю зоны на шаг), не микрооперации.
- Подход согласован с архитектурой. Тяжёлые модули импортируются внутри
  функций, чтобы не замкнуть цикл `notes → knowledge_cards`. Чтение БД
  идёт через `mode=ro` тем же приёмом, что у `preflight`. Запись — коротким
  соединением `store.db()`, сбой записи уходит в очередь `suite_lock`.
  «Влияние на систему» сходится с diff: изменены ровно 5 модулей зоны,
  добавлены `tests/test_knowledge_command.py` и карта. Откат — revert
  merge-коммита, схема БД и FSM не меняются.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artel.py`: строка в справке, запись в перечне модулей, `knowledge` в `_ROLE_ALLOWED_COMMANDS`, запись в диспетчере. `cmd_knowledge`: роль без `ARTEL_TASK` получает отказ до открытия БД; `t["id"] != env_task` сверяет полный id; неизвестная задача отказывает в `store.get_task` → `sys.exit`, и `_open_db_readonly` при этом закрывает соединение (перехват `BaseException`). |
| 2 | OK | Сортировка — `match` К-4а (`kind != SYSTEM, key`). Срез `[:OUTPUT_MAX]`, строка «ещё N по запросу (уточни путь)» уходит внутрь границы, если в ней есть проектные ключи. Обёртка — `wrap_boundary(new_run_id())`, перед ней `BOUNDARY_INSTRUCTION`. Подробность системного отказа усечена `[:200]`. `task_project`: NULL или пустое значение → `DEFAULT_TARGET`, ключа нет → `None`. |
| 3 | OK | `_status_line` печатает «карточки <вид> не прочитаны: <код>»; при любом отказе после выдачи — `sys.exit(1)`; NOT_SET_UP — строкой, код возврата 0. |
| 4 | OK | Чтение — только `mode=ro`. Запись — `_journal_write`: `store.db()`, затем перехват `(sqlite3.Error, OSError)` → `defer_journal`. Сбой очереди — одна строка в stderr через `watch.safe_text`. |
| 5 | OK | Литеральные значения констант, автор `knowledge-cards`. В `detail`: префикс, роль из `roles.load()`, запрос через `json.dumps(safe_text(...), ensure_ascii=False)`, числа по видам, число помеченных, коды отказов, sha256. Запрос, отвергнутый формой (`match(query, ())`), даёт выход до записи. |
| 6 | OK | `access_tally` не считает к пределу записи с префиксом «предел журнала обращений исчерпан». Запись «предел исчерпан» пишется один раз: условие `elif not exhausted`. Записи `HINT_REFUSAL_ACTION` в счёт не входят (фильтр по действию). |
| 7 | OK | `deferrable` принимает `ACCESS_ACTION`. Автор досыла этого действия — `JOURNAL_ACTOR`, прочих — `DEFERRED_ACTOR`. `_access_admitted` держит счёт задачи за проход досыла; запись сверх предела убирается из очереди. Правило досыла (переименование) не тронуто. Поле `detail` уже проверено на `str` в `_deferred_text`, так что `.startswith` не упадёт на подложенном файле. |
| 8 | OK | `tests_writing.py`: исключается только пара «автор `JOURNAL_ACTOR` + действие обращения или отказа подсказки». Запись того же автора с другим действием сравнивается как обычно (AC-12 зелёный). |
| 9 | OK | `_Freshness._element`: системная карточка задачи внешнего проекта сверяется с `main` (`ls-tree` → режим `120000` / не блоб → `cat-file -s` → `gitcmd.show`), остальные — с рабочей копией. Если каталога нет, пишется «свежесть не проверена: рабочей копии задачи нет». |
| 10 | OK | `resolve(strict=True)` сравнивается с прямой склейкой пути, затем `lstat` S_ISREG, предел размера, `O_NOFOLLOW\|O_NONBLOCK` + `fstat`. Кэш `_files` по ключу (источник, путь). `ast.parse` идёт под `catch_warnings` с перехватом четырёх классов. Обход `if`/`try`/`TryStar`, классы — вложенно. В остальных файлах символ ищется как отдельное слово. |
| 11 | OK | `role_prompt.knowledge_hint_note` дописывается в общий хвост для всех ролей. `hint_line` выводит ключи без текста карточек, предел ключей, «и ещё N», «тем нет», коды отказа. Журнал пишется только при отказе, через `journal_warning_once(key=None)`; при `conn is None` не пишется. `sqlite3.Error` шаг не роняет. Тесты миссий и брифов проходят без правки ожиданий (прогон ниже). |
| 12 | OK | Комментарий над `_ROLE_ALLOWED_COMMANDS` переписан, фраза «журнала не трогает» заменена описанием досыла очереди. Планка AC-1 по комментарию зелёная. |
| 13 | OK | Тесты: долгоживущие файлы задачи и `tests/test_knowledge_command.py`. В каждом новом тесте есть заявка «Ловит мутацию» с наблюдаемым симптомом. `AccessTallyTest` частично пересекается с долгоживущим AC-9 (запись «предел исчерпан» вне счёта), но проверяет общую функцию счёта напрямую и добавляет случай `detail=None`. Чистым повтором не считаю. |
| 14 | OK | `docs/codebase-map.md` свежая: регенерация `scripts/codebase_map.py` дала расхождение только в строке `built_at_sha`; файл возвращён `git checkout`. |

Системная целостность: изменённых или удалённых утверждений в
существующих `tests/` нет — diff `tests/` состоит из одного нового файла.
Долгоживущие файлы задачи вне diff (лок). Правка последнего из них
(`982f2a63`, подмена `step_notes_block`) сделана по решению Оператора
13.10; утверждения не тронуты, добавлена только подмена компонента брифа.
Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`,
`.github/`) не тронуты. Гейт `tests_writing` стал строже, а не слабее.

## Замечания

Блокирующих и major-замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q` по 16 файлам: четыре долгоживущих файла задачи,
  `tests/test_knowledge_command.py`, `tests/test_knowledge_cards.py`,
  `tests/test_suite_lock.py`, `tests/test_suite_run_deferred_journal.py`,
  `tests/test_checkpoint_stray_acceptance_files.py`,
  `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`,
  `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_mission.py`,
  `tests/test_role_prompt_test_author_mission.py`,
  `tests/test_runner_role_environment.py`,
  `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`,
  `tests/test_01m4s0jvb85w9ty1esgnbh97fp_targets_knowledge.py`,
  `tests/test_fsm_advance_tests_writing_test_groups.py` — 97 passed,
  201 subtests passed, 11.5 с.
- `artel.py plank-run 01M4S0K2MJRMVMQWKATAME3RHR` — 2 passed, код
  выхода pytest 0.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md`:
  изменилась только `built_at_sha`, содержимое карты совпало. Файл возвращён
  `git checkout`, рабочее дерево чистое.
- Проверить временной мутацией исключение в `tests_writing.py` не
  удалось: команда с `sed -i` не получила разрешения. Сторож AC-12 оценён
  по заявкам трёх долгоживущих тестов: они различают «исключение только по
  автору» и «исключение только `ACCESS_ACTION`».
- CI коммита 5eaba4d4 зелёный (16 проверок, данные пакета).

## Предложения системе
- Шаг ревью: временная мутация, которую требует review-checklist
  («Сторож — проверен временной мутацией»), упирается в запрос
  подтверждения составной команды (`sed -i … && pytest …; git checkout`).
  В неинтерактивном шаге его никто не даёт. Нужна штатная команда пульта
  (по образцу `plank-run`) или разрешение в `settings.json` курируемого HOME.
