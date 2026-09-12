---
task: 01M29BANMM8X8JWJ5GDTJWKB0Z
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: прогоны тестов ролями и шаг CI на минимальной версии Python — через pytest с таймаутом, тем же раннером, что у пульта

## Соответствие SPEC

Гейт плана (Фаза A): требования 1–4 покрыты шагами 1–2 плана,
требования 2–3 (защищённые пути `.github/`, `skills/`) корректно
вынесены в приложения к PLAN.md для Оператора — это единственно
доступный ролям путь менять защищённые пути. Подход не конфликтует
с конвенциями (`orchestrator/acceptance.py::_pytest_command` как
образец формы команды). Шаги — проверяемые единицы, размер MR разумный
(одна f-строка кода + один тестовый файл).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/role_prompt.py:63-67` — пункт 5 миссии test_author несёт `python3 -m pytest {task_ref}/acceptance_tests -p no:cacheprovider -p timeout -o timeout={stack.PER_TEST_TIMEOUT_SEC}`, значение подставлено из константы (проверено подменой на 999 в тесте, см. ниже). |
| 2 | OK (manual, Оператор) | Приложение 1 PLAN.md — дифф `.github/workflows/ci.yml`: `requirements.lock` перед прогоном, pytest-команда с `timeout=120` и комментарием об известном ограничении. Проверено `git apply --check` — применяется чисто и на HEAD этой ветки, и на `main` (`.github/` не расходится между веткой и main). |
| 3 | OK (manual, Оператор) | Приложения 2–3 PLAN.md — диффы `skills/test-authoring.md` и `skills/coding-standards.md`: unittest → pytest той же формы, фраза про общий раннер/таймаут с пультом, слова «в переднем плане с таймаутом» сохранены в обоих файлах. Проверено `git apply --check` — оба применяются чисто на HEAD ветки и на main. |
| 4 | OK | `tests/test_role_prompt_test_author_mission.py` (новый, 39 строк) — 4 теста: форма команды с сегодняшним значением константы, форма с подменённой константой (999, не литерал), неизменность остального текста пункта 5, отсутствие `unittest discover`. Планка задачи (`tasks/.../acceptance_tests/`) добавляет тот же охват + статическую проверку AC-3 (что именно этот тест есть в основном наборе). Существующие тесты `role_prompt.py`/`brief.py` не тронуты и не ослаблены (diff --stat подтверждает: только новый файл). |

## Замечания

Замечаний нет.

## Реестр замечаний

Пусто — замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M29BANMM8X8JWJ5GDTJWKB0Z/acceptance_tests -p no:cacheprovider -p timeout -o timeout=120 -v` — 5 тестов, все зелёные.
- `python3 -m pytest tests/test_role_prompt_test_author_mission.py tests/test_agent_prompt.py tests/test_brief.py tests/test_advance_refusal_history.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 44 теста (6 subtests), все зелёные.
- `python3 scripts/guard.py tasks/01M29BANMM8X8JWJ5GDTJWKB0Z/SPEC.md` и тот же для `PLAN.md` — оба «ок».
- `git apply --check` для всех трёх приложенных к PLAN.md unified-диффов (`.github/workflows/ci.yml`, `skills/test-authoring.md`, `skills/coding-standards.md`) — применяются чисто; дополнительно проверено, что `.github/` и `skills/` не разошлись между этой веткой и `main` (`git diff main...HEAD --stat -- .github/ skills/` пуст), то есть диффы применимы и на голове main, не только на ветке задачи.
- `python3 scripts/codebase_map.py` локально — расхождение с закоммиченной картой только в строке `built_at_sha` (ожидаемо, не признак дефекта); локальную регенерацию отменил (`git checkout -- docs/codebase-map.md`), в диффе задачи ничего не менял.
- Сверка diff --stat: только `docs/codebase-map.md`, `orchestrator/role_prompt.py`, `tests/test_role_prompt_test_author_mission.py` — вне зоны задачи (`orchestrator/role_prompt.py`, `tests/`) изменений нет, защищённые пути (`.github/`, `skills/`) не тронуты напрямую.
- CI коммита c2dd8503 — зелёный (7 проверок), согласно статусу verifying в пакете.

## Предложения системе

<Пусто.>
