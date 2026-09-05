---
task: 01M1SG9YKBFG2G5YQDVBR6BVC8
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: автопамять CLI отключена у ролей курируемого слоя

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1. Ключ `"autoMemoryEnabled": false` в референсе `docs/reference/role-home/claude/settings.json` | OK | Ключ добавлен в корневой объект (settings.json:2), булево `false`, соседние ключи `permissions.deny` не тронуты. |
| 2. Тест в `tests/`, проверяющий ключ | OK | `tests/test_doctor.py::RoleHomeReferenceSettingsAutoMemoryTest` читает референсный файл и проверяет `assertIn` + `assertIs(..., False)` — ловит отсутствие ключа, `true` и строку `"false"`. |
| 3. `check_role_home_reference` не ослаблена | OK | `orchestrator/doctor.py` не входит в diff (проверено `git diff main...HEAD -- orchestrator/`  — пусто); сравнение деплой/референс идёт по полному содержимому файла, новый ключ подхватится автоматически. |

## Замечания

(нет)

## Реестр замечаний

(пусто — итерация 1, замечаний не заведено)

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1SG9YKBFG2G5YQDVBR6BVC8/acceptance_tests -p "test_*.py" -v` — 3 теста (AC-1, AC-2, AC-3), все `ok`. AC-4 — manual, обоснование в `acceptance_tests/test_manual_criteria.py` состоятельно (`.artel/` в `.gitignore`, диф ветки в принципе не видит этот путь — детерминированный тест невозможен по построению, не по лени).
- `python3 -m unittest tests.test_doctor -v` — 113 тестов, все `ok`, включая новый `RoleHomeReferenceSettingsAutoMemoryTest::test_settings_json_disables_auto_memory`.
- Прочитан текущий `docs/reference/role-home/claude/settings.json` — ключ `"autoMemoryEnabled": false` на строке 2, JSON валиден.
- `git diff main...task/... -- orchestrator/` (и отдельно `doctor.py`, `config.py`, `runner.py`) — пусто: подтверждает, что `check_role_home_reference`/`_role_home_diff` не редактировались (AC-3), а зона задачи (`docs/reference/role-home/claude/settings.json`, `tests/`) не нарушена.
- `git diff main...task/... --name-only` — только `docs/codebase-map.md`, `docs/reference/role-home/claude/settings.json`, `tests/test_doctor.py`; ни одного пути из `skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`.
- Регенерация `python3 scripts/codebase_map.py` локально (для проверки свежести) дала расхождение только в строке `built_at_sha` — содержимое карты идентично committed-версии; локальную регенерацию отменил (`git checkout -- docs/codebase-map.md`), рабочее дерево чистое. Карта в diff обновлена по конвенции (правка `tests/test_doctor.py` — `*.py` в `tests/`).

## Предложения системе

(нет)
