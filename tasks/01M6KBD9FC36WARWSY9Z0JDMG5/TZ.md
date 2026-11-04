---
task: 01M6KBD9FC36WARWSY9Z0JDMG5
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Команда target-set: правка поля записи проекта в локальном слое

# Команда пульта правки поля записи проекта в локальном слое `.artel/targets.yaml`

## Факты

1. Запись внешнего проекта живёт в локальном слое `.artel/targets.yaml` (`targets.local_path`, `orchestrator/targets.py:191`); сведение слоёв — `targets.layers` (`orchestrator/targets.py:250`), проверка значений записи — `targets.merge_local` (`orchestrator/targets.py:444`, там же запрет записи `artel` в локальном слое). Команды пульта для записи — только `target-init` (каталог и клон, `orchestrator/projects.py:47`) и `targets-migrate` (перенос записи из репозитория, `orchestrator/projects.py:111`). Команды, меняющей одно поле записи, нет.
2. Инцидент 04.11: задача стенда 01M6HWP40X94FYE7FS0N63VMCS остановилась на переходе из `tests_writing` с отказом «честный FAIL_TO_PASS — список «провал проверки» не задан у компонента app» (`orchestrator/advance_gates/tests_writing.py:1300`). Поле `failure_errors` компонента вписано в файл вручную по решению Оператора — обход, строка копилки 04.11 (8fa671cc).
3. Схема полей:
   - перечни разделов — `targets.LOCAL_FIELDS` (`orchestrator/targets.py:349`; разделы description, policy, machine);
   - поля компонента — `targets.COMPONENT_FIELDS` (`orchestrator/targets.py:98`), из них поля `policy.components.<к>` — `targets.LOCAL_POLICY_SCOPES` (`orchestrator/targets.py:394`), поля `description.components.<к>` — `COMPONENT_FIELDS` без `LOCAL_POLICY_SCOPES`;
   - поля `machine.components.<к>` — `targets.LOCAL_MACHINE_COMPONENT_FIELDS` (`orchestrator/targets.py:395`);
   - чтение `failure_errors` профилем — `orchestrator/project_profile.py:446`, сборка профилей — `project_profile.component_profiles` (`orchestrator/project_profile.py:472`).
4. Запись текста подмножеством `yamlmini` с проверкой «собранное читается так же» уже есть у `targets-migrate`: `projects._render` (`orchestrator/projects.py:252`), `projects._QUOTE_MARKS` (`orchestrator/projects.py:104`), `projects._Unwritable` (`orchestrator/projects.py:107`), атомарная запись — `projects._write_atomic` (`orchestrator/projects.py:353`).
5. Компонент «в границе отчёта» — `acceptance.in_outcome_bounds` (`orchestrator/advance_gates/acceptance.py:213`, принимает профиль); для него гейт честного FAIL_TO_PASS требует непустой `failure_errors`, но узнаётся это только на переходе задачи, после работы test_author.
6. Под признаком роли команды вне закрытого списка `_ROLE_ALLOWED_COMMANDS` (`orchestrator/artel.py:2566`) отказывают (`_role_allowed_command`, `orchestrator/artel.py:2580`; `_refuse_if_role_restricted`, `orchestrator/artel.py:2614`). Тест `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py` требует, чтобы каждая команда диспетчера была названа в блоке команд справки.
7. Запись журнала без задачи — образец `orchestrator/notes.py:414` (`store.journal(conn, None, …, target=…)`).

## Требуется

1. Команда `target-set <проект> <путь поля> <значение>`. Путь — через точку от записи проекта: `description.<поле>`, `description.components.<к>.<поле>`, `policy.<поле>`, `policy.components.<к>.<поле>`, `machine.<поле>`, `machine.components.<к>.<поле>`. Последний сегмент — поле; путь во вложенное отображение (`env.X`, `tools.<инструмент>`, `depends_on`) — отказ с причиной. Значение — литерал подмножества `yamlmini`: строка, число, `true`/`false`, список `[a, b]`. Команда:
   - отказывает для проекта `config.DEFAULT_TARGET` (его запись — в `targets.yaml` репозитория, правка — `doc-commit`) и для проекта, которого нет в локальном слое;
   - отказывает для поля, которого нет в перечне раздела (факт 3), с перечнем допустимых полей; значения проверяет `targets.merge_local` — собственный проверяльщик значений не пишется;
   - собирает новый текст: файл пересобирается целиком из разобранных данных через `projects._render`; если в прежнем тексте есть строка, начинающаяся с `#`, — отказ, файл не записан;
   - сверка в два шага, иначе отказ без записи: (а) разобранное отображение нового текста отличается от прежнего ровно одним листом по указанному пути; (б) `targets.layers()` загружается без ошибки, сведённые записи прочих проектов равны прежним;
   - если журнал недоступен (`store.db_usable()` ложно) — отказ до записи файла, текст `projects.NO_JOURNAL`;
   - перед записью сохраняет прежний файл копией в каталоге `config.LOGS` с уникальным именем `targets-<время UTC до секунд>[-<n>].yaml` (создание без перезаписи), печатает путь копии; запись — `projects._write_atomic`;
   - пишет в журнал пульта запись без задачи «target-set: <путь>: <было> → <стало>» с `target=<проект>` и печатает её.
2. `target-set --show <проект> [<путь>]` — печать текущего значения поля или раздела из записи локального слоя, без записи файла.
3. Строка `doctor` `target-failure-errors` — отдельной функцией, не в `project_entry_checks` (`orchestrator/doctor/project_checks.py:31`): одна строка с перечнем компонентов в границе отчёта (по `project_profile.component_profiles` и `in_outcome_bounds`) с пустым `failure_errors` — `warn` с подсказкой `target-set <проект> description.components.<к>.failure_errors [AssertionError]`; таких нет — `ok`; локальный слой не загрузился — `skip` с причиной.
4. `target-set` (в том числе `--show`) в `_ROLE_ALLOWED_COMMANDS` не добавляется: под признаком роли отказ даёт `_refuse_if_role_restricted`. Команда названа в блоке команд справки `orchestrator/artel.py`.
5. Документация: `docs/operator-session.md` (раздел «Правки main только командами» — строка о `target-set` вместо ручной правки локального слоя), `docs/stack.md` (локальный слой проектов), `docs/codebase-map.md`.

Критерии приёмки:
- `target-set sandbox description.components.app.failure_errors [AssertionError]` во временном локальном слое песочницы меняет ровно это поле; `component_profiles` после неё возвращает новое значение; копия прежнего файла лежит в `config.LOGS` песочницы, её путь напечатан; запись в журнале;
- вторая правка в ту же секунду не затирает первую копию;
- неизвестное поле, путь во вложенное отображение, неверное значение, проект `artel`, необъявленный проект, файл с комментарием, недоступный журнал — отказ с причиной, файл байт в байт прежний;
- значение, которое `yamlmini` прочитал бы иначе, — отказ, файл прежний;
- правка `machine.path` проходит (сверка шага (а) — по разобранному тексту, не по сведённой записи);
- под признаком роли — отказ;
- строка `doctor` даёт `warn` для компонента в границе отчёта без `failure_errors`, `ok` после `target-set`, `skip` при незагружаемом слое;
- прежние тесты `targets-migrate`, `target-init`, `doctor` и реестра справки зелёные без правки.

Безопасность тестов: все тесты работают с локальным слоем во временной песочнице (`config` подменён), никогда с настоящим локальным слоем.

Зоны: `orchestrator/projects.py`, `orchestrator/artel.py` (регистрация команды и справка), `orchestrator/doctor/` (новая строка и её регистрация), `docs/operator-session.md`, `docs/stack.md`, `docs/codebase-map.md`, `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/targets.py`, `orchestrator/project_profile.py`, `orchestrator/yamlmini.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/config.py`, `orchestrator/notes.py`, `orchestrator/prune.py`.

Не входит:
- правка записи `artel` в `targets.yaml` репозитория (только `doc-commit`);
- добавление и удаление проектов и компонентов целиком;
- правка `.artel/models.yaml`;
- откат по копии (копия — для Оператора вручную);
- ручная правка самого локального слоя `.artel/targets.yaml` задачей: файл меняет только команда при исполнении;
- защита копии от `git clean -fX`: каталог `config.LOGS` лежит в игнорируемом `.artel/` — принятый риск до задачи переноса каталогов из репозитория пульта (строка бэклога 04.11, приоритет 2).

Приоритет 2. Порядок: общая зона `orchestrator/artel.py` с задачей 01M6KB0SJHDA4D4GNEM7PGZ40P (возврат с гейта SPEC файлом решения) — по очереди замка зон.

Рамка: $40. Набор моделей — по умолчанию.
