---
task: 01M5WCXBR9K8CN586W1AP3ZN6Q
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab А1.2 — doctor, проверочная команда forge-probe и песочница без живого HTTP

## Фаза A — план
- Таблица покрытия полна: требования 1–5 → шаги 1–3; шаг 4 — карта и прогоны.
- Шаги по размеру — единицы MR. Подход «реализация хостинга берётся из
  `forge.IMPLEMENTATIONS`, а `hasattr` решает, есть ли функция» не
  конфликтует с архитектурой части 1: `forge._call` выбирает реализацию так же.
- «Влияние на систему» сходится с diff: 5 файлов зоны SPEC и карта.
  `forge.py` и `gitlab_adapter.py` не тронуты, путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `misc_checks.py`: у gitlab есть `project_info` → `_base_branch_by_project_info` (ok/warn, причина адаптера → skip). У `_GitHub` (`forge.py:115`) нет `project_info` → прежний путь `gh repo view` с телом без правок. Значение `forge`, которого нет в реестре (в том числе `None`), → skip, как раньше. Литерала `"github"` нет (AC-6 зелёный). |
| 2 | OK | `check_token_expiry`: пороги берутся из констант реализации; срок `days <= limit` → warn (истёкший тоже warn); бессрочный токен: `tasks >= limit` → warn, иначе ok; в счёт идут только задачи проекта (`store.project_tasks`), кроме `killed`; причина адаптера → skip; у `_GitHub` нет `token_expiry` → `None`, строки нет. Регистрируется в `cli.py` сразу после `base-branch`, коллаборант `forge` подключён через фасад `doctor/__init__.py`. |
| 3 | OK | `artel.py::_cmd_forge_probe` — только функции чтения `forge`. Отчёт берётся по `pipeline.sha` из `branch_pipeline`; без конвейера печатается причина. Все вызовы — GET (AC-4 зелёный). |
| 4 | OK | `targets.SUPPORTED_FORGES` не тронут; печатаются только поля результатов и причины адаптера; AC-1 зелёный в трёх режимах ответа сервера. Мелочь, не дефект: при `access_level=None` строка напечатает «None». |
| 5 | OK | `tests/sandbox.py`: снимок `_GITLAB_TRANSPORT` при импорте, подмена ставится, только если транспорт исходный. Сигнатура `refused_gitlab_transport(method, url, headers, body, timeout)` совпадает с позиционным вызовом `gitlab_adapter.py:248`. `errno` в sandbox уже импортирован (`tests/sandbox.py:66`). `reload(gitlab_adapter)`, при котором снимок разошёлся бы с атрибутом, в `tests/` и `orchestrator/` нет (проверено grep). |

Матрица неослабления: связка ключей и признак роли в `isolate_keychain_and_role` не изменились, подмена только добавлена. `test_doctor.py`, тесты части 1 и А0 не правились и зелёные.

## Замечания
Нет замечаний уровня blocker, major или minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5wcxbr9k8cn586w1ap3zn6q_gitlab_doctor_probe.py tests/test_01m5wcxbr9k8cn586w1ap3zn6q_sandbox_no_http.py tests/test_doctor.py`: 149 passed, 3 subtests passed.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`: 207 passed (часть 1 и сторож А0 без правки).
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py tests/test_sandbox_determinism_helpers.py`: 24 passed, 125 subtests passed (новая команда вне белого списка ролей, строка справки на месте).
- `artel.py plank-run 01M5WCXBR9K8CN586W1AP3ZN6Q`: отказ «планки нет — в refs/artifacts нет test_*.py». Планка задачи — это только долгоживущие файлы `tests/`, их прогон выше.
- Свежесть карты: `codebase_map.build_modules` + `render` в память, сравнение с `docs/codebase-map.md` без строки `built_at_sha` → совпадает (файл не перезаписывался).
- Временную мутацию не вносил: шаг ревью код не правит. Заявки тестов песочницы (безусловная подмена → `own_before` красный; подмены нет → `create_connection` вызван) прямо следуют из их утверждений.

## Предложения системе
- `plank-run` отказывает задаче, у которой вся планка — долгоживущие `tests/test_<id>_*.py` (папка `acceptance_tests/` пуста). Было бы полезно, чтобы команда в этом случае прогоняла файлы из перечня лока, а не отказывала.
