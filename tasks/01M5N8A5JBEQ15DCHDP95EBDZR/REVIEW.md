---
task: 01M5N8A5JBEQ15DCHDP95EBDZR
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Сброс удержанных записей копилки, бэклога и doc-commit — одним пушем

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–10), шаги размера MR, подход
  (параметр `ref` у сверок с умолчанием `FETCH_HEAD`, перестройка через
  `_build_*`, правки конфигурации после пакета прежним `_attempt`) не
  конфликтует с архитектурой и требованием 9 SPEC.
- «Влияние на систему» соответствует диффу (меняется только
  `orchestrator/notes.py` + карта). Одно расхождение: PLAN утверждает «правила
  правок конфигурации не меняются», а предупреждение `NO_BASE_WARNING` у них
  пропало — см. R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_flush_batch`: коммиты по порядку `_pending_paths()`, `_commit_message` прежний, один `push` (AC-1 зелёный). |
| 2 | OK | `ref=head` пакета; `known` первой — `_known_origin_main` до `_fresh_main`, k>1 — голова пакета, `knowns.setdefault` держит значение первого построения; `base_blob` живёт в `request`. Временная мутация `ref→FETCH_HEAD` краснит AC-8 и все AC-9 (6 тестов). |
| 3 | реализовано не так | Порядок/гейт/попутный пропуск — OK (AC-4), но при явном флаше правка конфигурации без `held_base` больше не печатает `NO_BASE_WARNING` (R1-F1). |
| 4 | OK | `SystemExit` построения → `_refused_print`, запись выбывает (AC-2, AC-6). |
| 5 | OK | перестройка от `_fresh_main` через `_build_*`, не больше `MAX_PUSH_ATTEMPTS` (AC-3, AC-7, AC-10). |
| 6 | OK | `unlink` только после успешного push, только у `batch`. |
| 7 | OK | `_sent_line` — три вида строк (AC-6). |
| 8 | OK | `_journal_commit` со sha своей записи после push (AC-6, AC-7). |
| 9 | OK | `_run`/`_fetch_and_build`/`_commit_and_push`/`_attempt` не тронуты, умолчания `ref="FETCH_HEAD"`. |
| 10 | OK | долгоживущий `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py`, push считает `post-receive` origin, заявки «Ловит мутацию» есть и наблюдаемы. |

## Замечания
- major — `orchestrator/notes.py:1462-1470` — при явном флаше (`note --flush`,
  `doc-commit --flush`) удержанная правка конфигурации старого формата / после
  сетевого отказа (`doc-commit gates.yaml` без `held_base`) больше не получает
  строку `<путь>: NO_BASE_WARNING`: ветка `_suite_gate_applies` делает
  `continue` раньше проверки `HELD_BASE_KEY` (:1471–1476). В базе 2b187a3d
  ветка была `if not explicit and _suite_gate_applies(...): print; continue`,
  и явный флаш доходил до предупреждения. Требование 3 SPEC: «Их правила не
  меняются»; PLAN «Влияние на систему» обещает то же. Сценарий: Оператор
  флашит `gates.yaml`, удержанный без базы, — правка уходит по одной пиновой
  сверке, а предупреждение об отсутствии защиты сценария 02.10 молча пропало
  (проверено исполнением, см. ниже). Предложение: печатать `NO_BASE_WARNING`
  до разделения на пакет/конфигурацию (или и в ветке `explicit` для
  `config_records`) и закрыть тестом в `tests/` (такого теста нет ни в базе,
  ни в долгоживущем файле задачи — не повтор).
- minor — `orchestrator/notes.py` `_flush_batch`, ветка `except OSError:
  continue` (вокруг `_commit_on_batch`) — если `_write_doc`/`_write_backlog`
  упал `OSError` после частичной записи, правка не снимается с дерева
  (`_restore_tree` зовётся только при отказе `commit`). Прежний путь
  (`_attempt` на запись) делал `checkout -f` перед КАЖДОЙ записью; теперь
  checkout только раз на попытку, и следующая запись пакета того же пути
  (`docs/backlog.md`) прочтёт `_read_backlog` из грязного дерева, а не из
  головы пакета. Предложение: в `except OSError` снимать правку так же, как
  при отказе коммита (`reset` + `_restore_tree` по `_target_rel(request)`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/notes.py:1462-1470 | явный флаш правки конфигурации без `held_base` не печатает `NO_BASE_WARNING` — `continue` раньше проверки | нарушено требование 3 SPEC («правила не меняются»); Оператор не видит, что правка `gates.yaml`/`roles.yaml` идёт без защиты сценария 02.10 | печатать предупреждение и для `config_records` при `explicit`; тест в `tests/` |
| R1-F2 | open | orchestrator/notes.py `_flush_batch` (`except OSError: continue`) | `OSError` при записи файла записи пакета оставляет правку в дереве | следующая запись пакета того же пути строится от грязного дерева, а не от головы пакета | в `except OSError` — `reset` + `_restore_tree(work_dir, _target_rel(request))` |

## Вердикт
changes_requested: исправить R1-F1 (вернуть `NO_BASE_WARNING` правкам
конфигурации при явном флаше, с тестом в `tests/`); R1-F2 — minor, желательно
в той же итерации.

## Проверено исполнением
- `artel.py plank-run 01M5N8A5JBEQ15DCHDP95EBDZR` — отказ «планки нет: … нет
  файлов test_*.py» (все тесты задачи долгоживущие, в `tests/`).
- `python3 -m pytest -p no:cacheprovider -q
  tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py tests/test_notes.py
  tests/test_doc_commit.py tests/test_doc_commit_suite_gate.py
  tests/test_notes_apply.py tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py
  tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py` — 133 passed, 9 subtests.
- Временная мутация `_flush_batch`: `ref` построения `head → "FETCH_HEAD"` —
  `-k "ac8 or ac9"`: 6 failed (AC-8 и все пять AC-9); код возвращён,
  `git status` чист.
- R1-F1: инлайн-тест на `BatchFlushSandbox` (файл удержания `doc-commit
  gates.yaml` без `held_base`, `run_full_suite` подменён зелёным, `note
  --flush`) — вывод `полный набор tests/: предел 900 с (источник: config)`,
  `NO_BASE_WARNING` в нём нет, запись отправлена (`pending: []`).
- `git diff 2b187a3d --stat -- tests/` — только новый долгоживущий файл задачи,
  существующие тесты не тронуты.

## Предложения системе
- `orchestrator/notes.py::_flush_pending`: печать `NO_BASE_WARNING` не держит
  ни один тест `tests/` — поведение, видимое Оператору, ушло молча при первой
  же перестройке цикла.
