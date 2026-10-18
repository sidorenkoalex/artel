---
task: 01M58FNWBV25FF26E7AZ9Q9912
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G1а (часть 1) — компоненты проекта в записи targets.yaml: схема, profile_of, выбор по путям

## Фаза A: план
- Таблица покрытия PLAN.md полна: требования 1–11 сопоставлены шагам 1–5.
- Шаги проверяемые и размера MR: один модуль на шаг, тесты отдельным шагом.
- Подход не конфликтует с архитектурой. Схема проверяется отдельной `_check_components` рядом с `_check_profile`, а `_check_profile` и `_profile_value_error` не тронуты, поэтому тексты `test_profile` прежние. Ширину перехвата задаёт подкласс `ComponentsPending(TargetsError)`. Решение «пустой набор путей — все компоненты» названо в «Подходе» и «Рисках». SPEC этот случай не называет, решение консервативно.
- «Влияние на систему» сходится с diff: изменены 4 файла зоны и добавлен `tests/test_project_components.py`. Вне зоны правок нет, гейты и тесты не тронуты. Путь отката — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py` `check`: `components` вместе с `test_profile` — отказ (AC-3 зелёный). |
| 2 | OK | Требуется непустое отображение; имя с `:` — отказ; `name` — неизвестное поле. |
| 3 | OK | Все поля сверены по `COMPONENT_FIELDS` и `_component_value_error`. Пробой проверено: `paths: 1` и `depends_on.paths: 1` дают отказ, а не исключение; `env` с `GITHUB_TOKEN` отвергается (вид `mapping` переиспользован, правило секретов действует и в компонентах); для `workdir`/`env`, `long_lived`/пары, `repo` и `long_lived_imports` у артели работают правила `_check_component_rules`. |
| 4 | OK | Путь `test_profile` в `profile_of` и `decide` не изменён; `components()` для `test_profile` даёт `default`, для ABSENT — `()`. |
| 5 | OK | `ProfileAnswer.multi=False` по умолчанию. У единственного компонента без обязательного подполя исход UNREAD, причина называет компонент и подполе. |
| 6 | OK | `Component(name, fields)`, `components`, `select_components`, `test_id`, `parse_test_id`. |
| 7 | OK | `_touches`: `paths` + `test_support` + `depends_on` вида `paths`/`files`; путь, не задевший ни одного компонента, даёт все компоненты; у записи с одним компонентом выбор — он. |
| 8 | OK | `parse_test_id` режет по первому `:`, затем по первому `::`; номер берётся только из десятичного хвоста после `#`. |
| 9 | OK | `decide` — отказ с причиной; `full_suite_limit` бросает `TargetsError(reason)`; `suite_run` не тронут (AC-8 планки зелёный). |
| 10 | OK | `_task_own_profile` бросает `ComponentsPending`; `drop_from_code_copy` перехватывает только этот подкласс, `rmtree` идёт до вызова (AC-9 планки зелёный). |
| 11 | OK | Учебные записи пишутся текстом и читаются `targets.load`; неверные формы проверяются словарём в `check`; сети нет. |

Наблюдения ниже не дотягивают до minor со сценарием поломки в этой задаче, поэтому в реестр не заведены:
- `targets.py` `_check_components`: ключ компонента не строкой (`targets.check` вызван со словарём `{1: …}`) даёт `TypeError` вместо `TargetsError`. Через `targets.load` недостижимо: ключи `yamlmini` — всегда строки.
- `depends_on.<поставщик>.paths: []` проходит проверку: зависимость, которая никогда не срабатывает. В перечень отказов SPEC этот случай не входит.
- `decide` на единственном компоненте с UNREAD без `multi` пишет «(поле test_profile записи…)». Причина при этом называет компонент и подполе, так что отказ читается, но слово «test_profile» в нём неточно.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — по каждому требованию SPEC реализовано так, как задано. Blocker и major нет, реестр пуст.

## Проверено исполнением
- `python3 orchestrator/artel.py plank-run 01M58FNWBV25FF26E7AZ9Q9912`: 7 passed, код выхода pytest 0 (`test_until_g1b_refusals.py`, AC-8–AC-10).
- `python3 -m pytest -q tests/test_01m58fnwbv25ff26e7az9q9912_components.py tests/test_project_components.py tests/test_acceptance_suite_profile.py tests/test_project_profile.py tests/test_project_profile_gates.py tests/test_repo_context.py tests/test_01m45fjvgqt1k0p8hdexzx6hs7_*.py tests/test_01m52ee*.py tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py tests/test_full_suite_profile_timeout.py tests/test_multitarget.py`: 176 passed, 510 subtests passed.
- Проба `targets.check` словарями на граничных формах (`paths: 1`, `depends_on.paths: 1`, `depends_on.paths: []`, `env` с `GITHUB_TOKEN`, ключ-число, единственный компонент без `command`, маска `''`). Результаты — в таблице и наблюдениях выше.
- Свежесть карты: `codebase_map.render` в памяти совпадает с `docs/codebase-map.md` без строки `built_at_sha`; файл не перезаписывался.
- Диф `tests/`: существующие тесты не изменены, добавлен только `tests/test_project_components.py`. Его 4 метода несут «Ловит мутацию» с наблюдаемым расхождением: `contract` → выбран бы `web`; без ветки «все» → `()`; без проверки разделителей → кортеж вместо `ValueError`; `#` без номера. Долгоживущий файл задачи эти тесты не повторяют.

## Предложения системе
- Пакет не говорит, как проверить свежесть карты без записи в рабочий каталог: у `scripts/codebase_map.py` нет режима `--check`, пришлось собирать `render` вручную.
