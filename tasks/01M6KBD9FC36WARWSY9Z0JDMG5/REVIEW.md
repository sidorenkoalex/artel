---
task: 01M6KBD9FC36WARWSY9Z0JDMG5
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Команда target-set: правка поля записи проекта в локальном слое

## Фаза A — план
Таблица покрытия PLAN полна (требования 1–12 → шаги 1–5); шаги размера MR;
подход переиспользует `_render`/`_differences`/`_write_atomic` из
`targets-migrate` и не трогает файлы из «Не входит» SPEC. «Влияние на
систему» совпадает с diff: `projects.py`, `artel.py`, `doctor/cli.py`, две
документации, карта, новый `tests/test_projects_target_set.py`; гейты,
лимиты и белый список ролей не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `cmd_target_set`: 3 аргумента; >3 — подсказка про кавычки (`projects.py`, ветка `len(rest) > 3`) |
| 2 | OK | `_field_keys`/`_component_fields`: перечни `LOCAL_FIELDS`, `LOCAL_POLICY_SCOPES`, `COMPONENT_FIELDS` без scopes, `LOCAL_MACHINE_COMPONENT_FIELDS` |
| 3 | OK | Все отказы есть, до копии и записи; `store.db_usable()` — до копии; «без изменений» — код 0 без файла/копии/журнала. Пробами проверены `description.test_profile`, `components.app.env/tools` → «вложенное отображение»; `verify`/`knowledge`/`commit_author`/`freshness` строкой → отказ сверки `merge_local` |
| 4 | OK | `_render(edited, 0, "")` |
| 5 | OK | `_target_set_mismatches`: (а) по листьям разобранного текста + тип значения; (б) `merge_local` каждой записи в памяти, сравнение прочих |
| 6 | OK | `_backup_copy`: `open(..., "xb")`, суффикс `-<n>`, время только из `_backup_stamp()`; `_write_atomic` |
| 7 | OK | `store.journal(conn, None, "operator", "target-set", detail, target=name)`, печать; `(нет)` для отсутствующего |
| 8 | OK | `_target_set_show`: лист, раздел, запись; файл не пишется |
| 9 | OK | `target_failure_errors_check` в `doctor/cli.py`, вызов после цикла проектов вне `else`; только записи с `components`; `skip` при `TargetsError` загрузки |
| 10 | OK | `target-set` в `table` вне `_ROLE_ALLOWED_COMMANDS`; строка справки добавлена |
| 11 | OK | `docs/operator-session.md`, `docs/stack.md` «Локальный слой проектов», карта регенерирована (diff карты в пакете исключён, 223 КБ) |
| 12 | OK | Все тесты на `initialized_tmp_root` |

## Замечания
Блокеров и major нет. Тесты: заявки «Ловит мутацию» в
`tests/test_projects_target_set.py` наблюдаемы (отказ/успех и значение
файла); новые тесты не повторяют долгоживущие файлы задачи (там нет
комментария после ключа блока и значения `a#b`). Существующие тесты не
изменены (diff `tests/` — только новый файл).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py tests/test_01m6kbd9fc36warwsy9z0jdmg5_doctor_failure_errors.py tests/test_projects_target_set.py` — 44 passed.
- `artel.py plank-run 01M6KBD9FC36WARWSY9Z0JDMG5` — `test_ac2_backup_same_second.py` 1 passed, код выхода 0.
- Временный файл пробы `tests/test_zz_review_probe.py` (после прогона удалён `task-rm`), 15 passed, вывод просмотрен:
  `description.verify x`, `description.knowledge x`, `machine.commit_author x`, `policy.freshness x`, `machine.path 123` → отказ сверки `merge_local`, файл не записан;
  `description.reference` → отказ с перечнем допустимых полей; `description.test_profile`, `description.components.app.env`/`tools` → «вложенное отображение»;
  `[a, "b, c"]`, `[a]x` → отказ разбора; `'a # b'` (в кавычках) → записано `"a # b"`, `targets.load()` годен;
  `report pult-vitest` → правка с журналом `junit-xml → pult-vitest`;
  `--show` неизвестного компонента / записи `artel` → отказ, `--show` блока компонента печатает его поля.

## Предложения системе
- Миссия ревьювера не называет штатного способа временной пробы кода (файл в `tests/` + `task-rm`); тот же пробел PLAN отметил у разработчика — стоит назвать приём в `skills/review-checklist.md`.
