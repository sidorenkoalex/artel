---
task: 01M4AG3QYV3E7MN7FAVA10VDJG
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Рост долгоживущих тестов: правило автора тестов и замер времени файлов задачи

## Фаза A: план

- PLAN с прошлой итерации изменился только разделами «Проверки» и «Закрытие замечаний ревью» (R1-F1); таблица покрытия требований 1–8 полна, шаги размера MR, приложение к `skills/test-authoring.md` несёт пункты (а)/(б)/(в), замер main — таблица ANSWER-2 с условиями и обоснованием порога. Замечаний к плану нет.
- «Влияние на систему» соответствует диффу итерации: с `96c9ce5d` изменён только `tests/test_acceptance_file_time.py` (`git diff 96c9ce5d --stat -- orchestrator/ skills/ templates/ gates.yaml roles.yaml .github/` — пусто).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Приложение PLAN; планка AC-1..AC-3/AC-11 зелёная (`plank-run`) |
| 2 | OK | Без изменений с итерации 1: `advance_gates/acceptance.py` пишет `LONG_LIVED_FILE_REPORT_ACTION` с путём и временем каждого файла; держит `test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py::test_ac4…` |
| 3 | OK | `acceptance.long_lived_file_report`: `>` порога → предупреждение; исход рубежа не меняется (AC-7 на настоящем рубеже) |
| 4 | OK | `config.LONG_LIVED_FILE_WARN_SEC = 60` с обоснованием |
| 5 | OK | `fsm_autogate._log_acceptance_checklist`; сторож `test_checklist_journals_latest_measurement_before_final_group` |
| 6 | OK | `review.py:885-889`; теперь сторож проводки — `test_review_package_contains_latest_measurement` |
| 7 | OK | Таблица ANSWER-2, 20 строк по убыванию |
| 8 | OK | Все свойства 2–6 держат тесты `tests/`; новый тест не повторяет долгоживущий AC-10 (тот держит чистую `review_package_measurement`, новый — вставку в `review_package`) |

## Замечания

Блокирующих и major нет. R1-F1 закрыт: новый тест зовёт сам `review.review_package` (источники подменены, `store.task_steps` отдаёт две записи замера), проверяет заголовок раздела, путь/время/предупреждение последнего замера и отсутствие пути первого. Заявка «пропускает замер / берёт первый» исполнима — обе мутации проверены (см. «Проверено исполнением»). Тест модульный, без песочницы — соответствует правилу (а) задачи.

- minor (перенесено из итерации 1, не в реестре) — `orchestrator/review.py:10-13` — `review_package_measurement` стоит между импортами и `WORKTREE_NOTE` без пустых строк после неё. Функциональных последствий нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/review.py:885-889; tests/test_acceptance_file_time.py:60-103 | Вставку замера в `review_package` не держал тест `tests/` | Потеря раздела замера в ревью-пакете прошла бы CI незамеченной | Принято: `test_review_package_contains_latest_measurement` краснеет на обеих заявленных мутациях (`if False:` и выбор первого отчёта) |

## Вердикт

approved — R1-F1 закрыт, реестр закрыт целиком, реализация соответствует SPEC и ANSWER-1/ANSWER-2.

## Проверено исполнением

- `python3 -m pytest tests/test_acceptance_file_time.py tests/test_review_package.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py tests/test_fsm_autogate.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 176 passed, 8 subtests passed.
- Временная мутация 1: `orchestrator/review.py:887` `if measurement:` → `if False:`; `tests/test_acceptance_file_time.py` — 1 failed (`test_review_package_contains_latest_measurement`), 3 passed. Код возвращён.
- Временная мутация 2: `review.py:886` — в `review_package_measurement` передан только первый отчёт (`[:1]`); `tests/test_acceptance_file_time.py` — 1 failed (тот же тест), 3 passed. Код возвращён, `git status --short` пуст.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4AG3QYV3E7MN7FAVA10VDJG` — 4 passed, код выхода 0.
- `git diff 96c9ce5d --stat -- orchestrator/ skills/ templates/ gates.yaml roles.yaml .github/` — пусто (код и защищённые пути в итерации не менялись; `test_…_transition_time.py` прогнан в итерации 1 — 2 passed).
- CI коммита 2f898112 по пакету — зелёный (16 проверок); полный набор в шаге не гонял (решение Оператора 05.09).

## Предложения системе

- Модульный тест сборщика `review.review_package` требует подмены 14 источников через `ExitStack` — дорого и хрупко к рефакторингу; стоит выделить в `review.py` сборку частей пакета из уже полученных данных (чистую функцию), чтобы тесты разделов пакета не мокали весь ввод. Адрес — `orchestrator/review.py::review_package`.
