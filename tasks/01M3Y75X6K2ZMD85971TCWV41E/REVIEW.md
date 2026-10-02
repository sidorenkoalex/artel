---
task: 01M3Y75X6K2ZMD85971TCWV41E
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Удержанный doc-commit сверяется с базой сборки; команды просмотра и снятия удержанной записи

## Фаза A: план
- Таблица покрытия полна: требования 1–8 сопоставлены шагу 1 с адресом функции.
- План в один шаг для диффа в ~280 строк — нормальная единица размера MR,
  и SPEC обосновывает монолит.
- Подход согласуется с архитектурой: база пишется в `_hold_pending`
  (покрыты оба удержания, по окну тишины и по сетевому отказу), сверка
  стоит в общей `_build_doc_commit`, поэтому одинаково действует на
  попутный флаш, `note --flush` и `doc-commit --flush`. «Влияние на
  систему» совпадает с диффом: `notes.py`, `artel.py`, новый тест, карта.
  Путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `notes.py` `_hold_pending`: `held_base` = `_blob_sha(ROOT, HEAD:<путь>)`, при отсутствии пути — `None`, то есть «файла не было». Повторное удержание базу не переписывает. |
| 2 | OK | `_build_doc_commit`: при наличии поля blob из `FETCH_HEAD` сравнивается с базой (`None == None` для нового файла), отказ называет обе sha и содержит «собери заново от origin». `_flush_pending` ловит `SystemExit` и делает `continue`: запись остаётся, остальные отправляются. |
| 3 | OK | Немедленная отправка поле базы не несёт (оно добавляется только при удержании), поэтому идёт по прежней ветке с `DOC_COMMIT_BASE_REFUSAL`. |
| 4 | OK | `_flush_pending` печатает `NO_BASE_WARNING` до попытки отправки, так что предупреждение видно и при успехе, и при отказе. |
| 5 | OK | `_pending_line`/`_print_pending`: id, вид, путь или раздел, время из метки имени файла, выдержка в 80 знаков в одну строку. |
| 6 | OK | `_drop_pending`: id ищется среди перечня файлов (обход каталога через «../» невозможен); `store.journal(..., "operator", "удержанная запись снята: <id>", <строка>)`. |
| 7 | OK | Ветки стоят в `cmd_note` после рубежа `runner.in_role_environment()` и до попутного допуша. |
| 8 | OK | `tests/test_doc_commit_held_base.py`: 4 теста, у каждого есть «Ловит мутацию: …». |

## Замечания

Блокирующих и major-замечаний нет. Наблюдения, не требующие правки:
- Тест `test_multiline_content_stays_one_line_and_truncated` в заявке
  упоминает «либо обрезка снята». Обрезку уже держит долгоживущий AC-7.
  Основное свойство этого теста (многострочное содержимое даёт одну
  строку перечня) новое, поэтому повтора по существу нет.
- Выдержка заменяет только `\n`. Символ `\r` в содержимом CRLF-документа
  остался бы в выводе, но строку вывода он не рвёт. Это вкус, не дефект.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний уровня blocker/major/minor не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py tests/test_doc_commit_held_base.py tests/test_doc_commit.py tests/test_notes.py tests/test_notes_apply.py tests/test_notes_row_format.py tests/test_doc_commit_suite_gate.py tests/test_artel_role_restricted_commands.py -p no:cacheprovider -q`: 140 passed, 26 subtests passed (68 с).
- Временная мутация 1: в `_build_doc_commit` ветка базы заменена на `if False:`, то есть осталась только пиновая сверка. Планка: 4 failed (три AC-2 и `test_ac4_new_file_appeared_in_origin_is_refused`). Код возвращён через `git checkout -- orchestrator/notes.py`.
- Временная мутация 2: в `_hold_pending` условие добавления базы заменено на `if False:`. Результат: `tests/test_doc_commit_held_base.py::NetworkHoldBaseTest::test_network_hold_stores_head_blob` FAILED, то есть заявка подтверждена. Код возвращён, `git status` чист, кроме `tasks/`.
- `python3 scripts/codebase_map.py` и затем `git diff -- docs/codebase-map.md` без строки `built_at_sha`: 0 строк расхождения, карта свежая. Регенерация отменена через `git checkout`.
- Сверка «набор не ослаблен»: дифф `tests/` состоит только из нового файла `tests/test_doc_commit_held_base.py`, существующие тесты не изменены.

## Предложения системе
- Ревью-пакет сообщает, что свежесть карты на ветке никто не проверяет.
  Проверка заняла одну команду, и её стоит делать автоматически в
  пакете (строка «карта свежа/несвежа») вместо ручного шага ревьювера.
  Адрес: сборщик ревью-пакета, раздел про `docs/codebase-map.md`.
