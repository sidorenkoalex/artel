---
task: 01M6TRM6H57TN8V14HGFV0NQXJ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Итог и отчёт тестов задания CI у адаптера GitHub: job_result и job_test_report

# Итог и отчёт тестов задания CI у адаптера GitHub: job_result и job_test_report (ADR-0031, этап 4а)

## Факты

1. Источник полного набора `full_suite: ci | both` читает итог задания CI и его отчёт junit через `forge`: `ci.job_full_suite` (`orchestrator/ci.py`, после `:1328`) → `forge.pipeline_status`, `forge.job_result`, `forge.job_test_report` (`orchestrator/forge.py:420-432`); того же отчёта требует гейт исходов на `verifying` (ADR-0026) и проверка «красные до кода» на выходе из `tests_writing` (`orchestrator/fsm_advance.py:648-653`).
2. Реализации: `IMPLEMENTATIONS = {"github": _GitHub, "gitlab": gitlab_adapter}` (`orchestrator/forge.py:365`). У `gitlab_adapter` есть `pipeline_status`, `job_result`, `job_test_report` (`orchestrator/gitlab_adapter.py:425`, `:490`); у `_GitHub` — только `pipeline_status` по check runs коммита (`orchestrator/forge.py:231-257`); недостающая функция — `TestReport(None, "<имя>: не реализовано для github")` (`orchestrator/forge.py:415-417`).
3. Значит, проект на GitHub (в том числе артель) не может перейти на запись компонента с `report` и `full_suite: ci`: итог был бы «неизвестно» на каждой приёмке.
4. CI артели: задание полного набора — check run `ci.FULL_SUITE_JOB` (`orchestrator/ci.py:36`); при открытом PR ветки задачи набор идёт на событии `pull_request`, на `push` — пропуск условием (`.github/workflows/ci.yml`, задание `changes`, ADR-0016); оба check run привязаны к головному коммиту.
5. ADR-0031, этап 4а (принят Оператором 07.11.2026, `9d60fe8f`); этап 4б (отчёт junit в `ci.yml` и запись артели) — правка Оператора после этой задачи.

## Требуется

1. **`job_result` для GitHub:** статус последней попытки задания `job_name` у коммита `sha` по check runs (имя check run равно `job_name`; несколько — последний по времени завершения, пропущенный условием `skipped` не считается попыткой, если есть исполненный) в тех же значениях, что у адаптера GitLab; нет такого задания — причина с именем задания.
2. **`job_test_report` для GitHub:** отчёт junit последней исполненной попытки задания — артефакт прогона Actions с именем из записи компонента (новое необязательное поле компонента `ci_report_artifact`, по умолчанию `junit`; файл внутри — первый `*.xml`), разобранный общим разборщиком junit пульта (`orchestrator/reporters/outcome.py`, `parse_junit`) в «`<classname>::<name>` → исход» с теми же исходами, что у GitLab (`ci.JOB_REPORT_OUTCOMES`). Нет артефакта, срок хранения истёк, архив не разобран — `TestReport(None, <причина>)`, не пустой отчёт.
3. Чтение — через `gh api` тем же входом, что прочие вызовы адаптера GitHub (`ci.gh`, репозиторий записи), с пределом размера скачиваемого архива и пределом времени; распаковка — во временный каталог, без исполнения содержимого; пути внутри архива вне каталога — отказ.
4. `doctor` для компонента записи на GitHub с `report` и `full_suite: ci` проверяет, что поле `ci_job` и артефакт отчёта читаются у последнего зелёного коммита базы (строка `ok` / `warn` с причиной), только чтение.
5. Поведение записей без `report` и проектов на GitLab — прежнее побайтно.

## Критерии приёмки

- Given подменённый ответ `gh api` с check runs (исполненный и пропущенный условием с тем же именем) и артефактом с junit, When `forge.job_result` и `forge.job_test_report` для записи на GitHub, Then статус и отчёт — последней исполненной попытки, исходы как у GitLab;
- Given артефакта нет / срок истёк / архив повреждён / путь вне каталога в архиве / архив больше предела, Then `TestReport(None, причина)` с названной причиной, файлы вне временного каталога не созданы;
- Given вымышленная запись компонента на GitHub с `full_suite: ci` и зелёным отчётом, When приёмка, Then итог «принят из задания CI» с числом тестов отчёта; с упавшим тестом — красный с именем теста;
- Given `ci_report_artifact` не задано, Then берётся `junit`; неверный тип поля — отказ загрузки записи с именем поля;
- `doctor` — строка о чтении отчёта: `ok` при читаемом, `warn` с причиной при отсутствующем;
- записи GitLab и записи без `report` — прежние итоги; существующие тесты — зелёные без правки.

Безопасность тестов: `gh` — подмена программы или `ci.gh`, архивы отчёта собираются в тесте во временном каталоге; без сети и без настоящего репозитория на GitHub; никогда — настоящий `.artel/targets.yaml` и `targets.yaml` артели.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/forge.py`, `orchestrator/github_adapter.py` (если чтение вынесено туда), `orchestrator/ci.py` (только вызовы `gh` для артефактов, если нужны), `orchestrator/targets.py` (поле `ci_report_artifact` компонента), `orchestrator/doctor/project_checks.py` (строка о чтении отчёта), `docs/codebase-map.md` (только генерацией), `tests/` (долгоживущие файлы задачи).

Только чтение: `docs/adr/0031-test-runs-strategy.md`, `docs/adr/0026-project-components-and-outcome-gates.md`, `orchestrator/gitlab_adapter.py`, `orchestrator/acceptance.py`, `orchestrator/reporters/`, `.github/workflows/ci.yml`, `targets.yaml`, `tests/sandbox.py`, `orchestrator/fsm_advance.py`.

Не входит:
- правка настоящего локального слоя `.artel/targets.yaml` в тестах и при разработке;
- правка `.github/workflows/ci.yml` (загрузка артефакта junit) и `targets.yaml` артели — этап 4б, Оператор;
- наследование итога CI `main` (этап 5);
- изменение приёмки и гейта мержа.

Приоритет 2.

Рамка: $70. Набор моделей — по умолчанию.
