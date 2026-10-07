---
task: 01M4AG3QYV3E7MN7FAVA10VDJG
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Рост долгоживущих тестов: правило автора тестов и замер времени файлов задачи

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–8 разнесены по трём шагам, шаги размера MR.
- Приложение к `skills/test-authoring.md` несёт все три пункта (а)/(б)/(в) требования 1 близко к тексту SPEC; патч, извлечённый из PLAN, применяется к ветке (`git apply --check` — ок), `skills/` в диффе ветки не тронут.
- Замер main (требование 7/AC-11): топ-20 по убыванию, условия замера названы, обоснование порога учитывает поправку ANSWER-2 (одиночный прогон против параллельного) — соответствует ANSWER-2.
- «Влияние на систему» соответствует диффу: шесть файлов, схема БД, исходы и `ACCEPTANCE_TIMEOUT_SEC` не меняются, временный JUnit XML живёт в `TemporaryDirectory`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Приложение PLAN, `git apply --check` ок; планка AC-1..AC-3/AC-11 зелёная |
| 2 | OK | `advance_gates/acceptance.py:368-379`: `file_times` из JUnit XML общего прогона, запись `LONG_LIVED_FILE_REPORT_ACTION` с путём и временем каждого файла; файл без testcase — «время не измерено» |
| 3 | OK | `acceptance.long_lived_file_report`: `seconds > limit` → строка предупреждения с файлом, временем и порогом; запись журнала делается до проверки `green` и в решение не входит |
| 4 | OK | `config.py`: `LONG_LIVED_FILE_WARN_SEC = 60` с обоснованием по замеру; рубеж читает константу в момент вызова |
| 5 | OK | `fsm_autogate._log_acceptance_checklist` вставляет последний замер перед последней группой; сторож — `tests/test_acceptance_file_time.py::test_checklist_journals_latest_measurement_before_final_group` |
| 6 | OK (код) | `review.review_package` добавляет раздел «Время долгоживущих файлов последнего прогона» в границах `wrap_boundary`; сторожа этой проводки нет — R1-F1 |
| 7 | OK | Таблица Оператора из ANSWER-2, 20 строк по убыванию |
| 8 | Не полностью | Свойство «итог виден в ревью-пакете» не держит ни один тест `tests/` — R1-F1 |

## Замечания

- major — `orchestrator/review.py:885-889` (проводка) / `tests/` (нет теста) — свойство требования 6 («итог замера виден в ревью-пакете») без сторожа в `tests/`, что противоречит требованию 8 и ADR-0018 п. 3. Долгоживущий `test_ac10_review_package_contains_latest_file_times_and_warnings` проверяет только чистую `review.review_package_measurement` (`reports[-1]`), а не то, что `review_package` её зовёт и кладёт результат в текст. Проверено временной мутацией: заменил `if measurement:` на `if False:` в `review.py:887` — `tests/test_acceptance_file_time.py`, `tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py`, `tests/test_review_package.py` — 153 passed, ни одного красного (код возвращён, дерево чистое). Сценарий: рефакторинг `review_package` потеряет вставку раздела — ревьювер перестанет видеть замер, CI останется зелёным. Для карточки приёмки такой сторож есть (`test_checklist_journals_latest_measurement_before_final_group`), для пакета — нет. Предложение: в `tests/test_acceptance_file_time.py` (не в залоченном файле) — модульный тест `review_package` на `store.task_steps`, возвращающем две записи `LONG_LIVED_FILE_REPORT_ACTION` (по образцу соседнего теста карточки, с моками тех же источников, что используют существующие тесты `tests/test_review_package.py`), с заявкой «Ловит мутацию: пакет не вставляет замер — путь и предупреждение последнего прогона исчезают из текста; берётся первый замер — в тексте устаревший путь». Повтором AC-10 это не будет: долгоживущий тест держит выбор последнего отчёта чистой функцией, новый — проводку в сборщик пакета.
- minor — `orchestrator/review.py:9-13` — `review_package_measurement` вставлена между импортами и `WORKTREE_NOTE` (без двух пустых строк после неё), в отрыве от `review_package`. Функциональных последствий нет; при правке R1-F1 можно перенести ближе к месту использования. В реестр не заношу как блокирующее — вкус.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/review.py:885-889; tests/test_acceptance_file_time.py | Вставку замера в `review_package` не держал тест `tests/` | Потеря раздела замера в ревью-пакете прошла бы CI незамеченной | Добавлен `test_review_package_contains_latest_measurement`: проверяет путь, время и предупреждение последнего прогона в полном тексте пакета, исключает старый путь; временная мутация `if measurement:` → `if False:` теперь красит тест |

## Вердикт

changes_requested — закрыть R1-F1: добавить в `tests/test_acceptance_file_time.py` тест проводки замера в `review.review_package`. Остальная реализация соответствует SPEC; ANSWER-1/ANSWER-2 учтены.

## Проверено исполнением

- `python3 -m pytest tests/test_acceptance_file_time.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py tests/test_review_package.py tests/test_fsm_autogate.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 175 passed, 8 subtests passed.
- `python3 -m pytest tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py -p no:cacheprovider -p timeout -o timeout=240 -q` — 2 passed, 4 subtests passed (11 с; AC-4 и AC-7 на настоящем рубеже).
- Временная мутация `orchestrator/review.py:887` `if measurement:` → `if False:`; прогон `tests/test_acceptance_file_time.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py tests/test_review_package.py` — 153 passed (мутация не поймана → R1-F1); код возвращён, `git status --short` пуст.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4AG3QYV3E7MN7FAVA10VDJG` — 4 passed, код выхода 0.
- Патч из раздела «Приложение» PLAN извлечён в файл, `git apply --check` — применяется; `git diff 37b20d5c --stat -- skills/` — пусто.
- Статус CI коммита 96c9ce5d по пакету — зелёный (16 проверок); полный набор в шаге не гонял (решение Оператора 05.09).

## Предложения системе

- Класс «заявленный контрактом чистый геттер вместо проводки» (ANSWER-1 п. 4 предписал модульные тесты «функций, собирающих тексты»; автор тестов вынес тривиальные `reports[-1]` и тестирует их, а не сборщик) — при разложении долгоживущих тестов на модульные стоит требовать, чтобы модульный тест звал саму публичную сборку текста (`review_package`, `_log_acceptance_checklist`), а не вынесенную под тест обёртку; адрес — `skills/test-authoring.md`, раздел про контракт для разработчика.
