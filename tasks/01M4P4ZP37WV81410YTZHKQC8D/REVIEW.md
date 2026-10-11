---
task: 01M4P4ZP37WV81410YTZHKQC8D
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Предпроверка выхода из tests_writing для роли (`artel.py preflight <id>`)

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–12 сопоставлены шагу 1 и
  конкретным функциям (`_report`, `INPUT_FILTERS`, `_traceability`,
  `_long_lived`, `_groups`, `NOT_CHECKED`, `_open_db_readonly`, строка
  `_ROLE_ALLOWED_COMMANDS`, приложение к скилу); требование 12 закрыто
  долгоживущим файлом задачи.
- Шаг один, но размер MR (≈350 строк кода и тестов) — монолит, как
  предложил SPEC и принял Оператор на гейте SPEC; резать нечего.
- Подход не конфликтует с архитектурой: переход (`fsm.py`,
  `fsm_advance.py`, `advance_gates/*`) не тронут, модуль только зовёт
  публичные ядра guard. «Влияние на систему» соответствует diff: изменены
  ровно `orchestrator/artel.py`, новый `orchestrator/preflight.py`,
  `tests/test_preflight.py`, карта. Путь отката описан.
- Приложение к `skills/test-authoring.md` проверено планкой
  (`test_ac8_skill_appendix.py`, поправленной Оператором по ANSWER-2) —
  зелёная.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_report` печатает «<проверка>: пройдена/отказ» и строки ошибок с отступом в 2 пробела; `refused \|=` — отказ не останавливает остальные проверки (AC-1 четвёртый сценарий зелёный). |
| 2 | OK | Планка — `docs/acceptance_tests` через `rglob("*.py")` + `INPUT_FILTERS = (guard.is_extraneous_acceptance_test_file,)`, аргумент — путь от `acceptance_tests/`, та же форма, что у `checkpoint._is_stray_acceptance_test_file` (checkpoint.py:44–52, прочитан для сверки формы аргумента). SPEC.md — с диска. Долгоживущие — обход `profile.long_lived_dir` рабочей копии с `profile.is_long_lived`, без git; нет копии — одна строка, `ensure` не зовётся. |
| 3 | OK | Сверено с телами `fsm._tests_writing_ac_state` (ветко-корректный путь, fsm.py:551–586), `_tests_writing_test_groups_gate` (tests_writing.py:335–340) и `_tests_writing_long_lived_gate` (tests_writing.py:452–460): те же ядра, тот же состав и порядок; `network_addresses = repo_context.is_artel(target)`, как fsm_advance.py:539. |
| 4 | OK | Метки: `tasks/<id>/acceptance_tests/<файл>` для трассируемости/маркера/образца; `acceptance_tests/<файл>` от `guard.acceptance_test_files(docs)`; путь от корня рабочей копии для долгоживущих. Строка группы долгоживущего файла собрана тем же f-строкой, что в гейте (tests_writing.py:454–457). AC-1/3/4 сверяют с журналом настоящего `advance` — зелёные. |
| 5 | OK | `refusal` → `detail` и `refusal_hint(id)` отдельными строками, долгоживущие и группа — «профиль … не разрешён»; `skip` → «у проекта нет профиля тестов», `journal_skip` не зовётся. |
| 6 | OK | `NOT_CHECKED` — 10 пунктов в составе SPEC, печать по строке на пункт; пункт чтения со ссылки документов называет `scan_acceptance_tests`, `acceptance_traceability_errors`, `scan_redness_markers`, `scan_id_format_samples` — ровно дисковый путь `_tests_writing_ac_state`. |
| 7 | OK | Нет lease, `store.journal`, git-записи, `workspace.ensure`, выкладки планки; AC-6 и заглушки AC-9 зелёные. |
| 8 | OK | `_task_row` перехватывает `SystemExit` `store.get_task` и выходит кодом 2 с тем же сообщением; не `tests_writing` — код 2. Наблюдение без замечания: битый/без схемы файл БД даст необработанный `sqlite3.OperationalError` (traceback, код 1) — сценарий вне AC, на поведение роли при живом пульте не влияет. |
| 9 | OK | `sqlite3.connect("<uri>?mode=ro", uri=True)`, без `store.db()`. Дополнительно проверил исполнением: WAL-БД без `-wal`/`-shm` в каталоге 0555 и с файлом 0444 открывается `mode=ro` и читается. |
| 10 | OK | `"preflight"` в `_ROLE_ALLOWED_COMMANDS` (artel.py:1803); AC-8 зелёный. |
| 11 | OK | Приложение в PLAN; планка `test_ac8_skill_appendix.py` — 1 passed. |
| 12 | OK | Сторож — долгоживущий файл задачи (лок, не правился). Модуль импортирует guard только `from scripts import guard`; множество guard-функций модуля без фильтра входа совпадает с множеством трёх тел перехода (тест зелёный, временная мутация краснит — см. ниже). |

## Замечания

Blocker/major/minor-замечаний нет.

- Тесты разработчика `tests/test_preflight.py`: оба метода несут
  «Ловит мутацию: …» с наблюдаемым расхождением (код 2 → иной код и
  появившийся файл БД; «пройдена»/код 0 вместо отказа); свойства
  долгоживущего файла задачи не повторяют (нет файла БД, нет SPEC.md —
  сценарии, которых долгоживущий файл не касается).
- Существующие тесты не менялись (diff `tests/` — только новый файл).
- Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`,
  `.github/`) в diff не тронуты; приложение к скилу — только в PLAN.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py tests/test_preflight.py`
  — 24 passed, 28 subtests passed (315 с).
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4P4ZP37WV81410YTZHKQC8D`
  — `test_ac8_skill_appendix.py` 1 passed, код выхода pytest 0.
- Временная мутация сторожа: в `orchestrator/preflight.py` вызов
  `guard.id_format_sample_errors` проверки образца id заменён на
  `guard.redness_marker_errors_from_files` (мутация (а) AC-9) →
  `SentryTest::test_ac9_transition_guard_calls_equal_preflight_and_not_checked`
  FAILED; код возвращён `git checkout -- orchestrator/preflight.py`,
  `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  — расхождение только в строке `built_at_sha`, карта свежая; файл
  возвращён `git checkout`.
- Python-скрипт с `sqlite3`: WAL-БД, закрытая (нет `-wal`/`-shm`), файл
  0444 в каталоге 0555 — `connect("file:…?mode=ro", uri=True)` читает
  строки (требование 9, сценарий песочницы).
- Ручная сверка тел перехода: `orchestrator/fsm.py:501–586`,
  `orchestrator/fsm_advance.py:446–575`,
  `orchestrator/advance_gates/tests_writing.py:309–466`,
  `scripts/guard.py:1912–1928, 2509–2529, 2890–2903`.
- Полный набор `tests/` не гонял (решение Оператора 05.09): CI коммита
  fb55cb60 зелёный, 16 проверок.

## Предложения системе

- Ревью-пакет: строка «Время долгоживущих файлов — время не измерено (нет
  результата pytest)» при зелёном CI вводит в заблуждение; долгоживущий
  файл этой задачи идёт ~5 минут — полезно было бы видеть замер из CI.
