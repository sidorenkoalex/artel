---
task: 01M5WCXBR9K8CN586W1AP3ZN6Q
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/doctor/misc_checks.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, orchestrator/artel.py, tests/sandbox.py
merge_after: 01M5WCXBM7WCMRWCBWNCHMAR3T, 01M5W27CY7K7NR9347NKD8F0NX
budget_usd: 25
---

# SPEC: GitLab А1.2 — doctor, проверочная команда forge-probe и песочница без живого HTTP

## Контекст
Это часть 2 деления задачи 01M5W670PHF08VPZWDRM5BY56W (ADR-0029 п. 8,
шаг А1). Часть 1 (01M5WCXBM7WCMRWCBWNCHMAR3T) дала `orchestrator/forge.py`
и `orchestrator/gitlab_adapter.py`. В них есть `forge.project_info`
(`default_branch`, `access_level`), `forge.token_user`, `forge.token_expiry`,
`forge.protections`, `forge.branch_pipeline`, `forge.job_test_report` и
константы `gitlab_adapter.TOKEN_EXPIRY_WARN_DAYS = 14`/
`TOKEN_NO_EXPIRY_TASKS_WARN = 10`. Сейчас `doctor/misc_checks.py:check_base_branch`
для всех хостингов, кроме github, отдаёт `skip` «сверка не реализована».
Строки о сроке токена и команды `forge-probe` нет. Тестовая песочница
`tests/sandbox.py::isolate_keychain_and_role` (`tests/sandbox.py:663`) даёт
непустой токен `fake_keychain_token`. Если doctor начнёт ходить в GitLab,
тест с таким токеном и без своей подмены транспорта сделает живой
HTTP-запрос. Требования и критерии взяты из SPEC родителя с учётом его
ANSWER-1 и решений гейта SPEC 26.10 (О-1): требования 11–13 и 15, AC-12
(вывод `doctor`/`forge-probe`), AC-16, AC-17, AC-18, AC-21.

## Требования
1. `doctor/misc_checks.py:check_base_branch` для `forge: gitlab` сверяет
   базу записи с `default_branch` из сведений проекта (`forge.project_info`)
   вместо `skip`. Совпадает — `ok`, расходится — `warn`. Если сверка
   невозможна (нет токена, ошибка HTTP, сеть недоступна, адрес сервера не
   строится из `url`) — `skip` с именованной причиной адаптера.
2. Строка `doctor` о сроке токена GitLab:
   - до истечения `gitlab_adapter.TOKEN_EXPIRY_WARN_DAYS` (14) дней или
     меньше — `warn`;
   - токен без срока: при числе задач проекта меньше
     `gitlab_adapter.TOKEN_NO_EXPIRY_TASKS_WARN` — информационная строка
     (не `warn`), при числе не меньше порога — `warn`. «Число задач
     проекта» — все задачи этого проекта в БД пульта, кроме `killed`;
   - без токена — `skip` с причиной.

   Строка регистрируется в `doctor/cli.py`. Новые коллаборанты
   `misc_checks` идут через фасад `doctor/__init__.py`. Реализация
   выбирается через `forge`, без сравнения значения `forge` с литералами.
3. Команда `forge-probe <проект> [--job <имя>]` в `orchestrator/artel.py`
   работает только на чтение и печатает:
   - пользователя токена и его уровень доступа в проекте;
   - срок токена;
   - защищённые ветки и теги;
   - последний конвейер базовой ветки: sha, итог, задания;
   - при `--job` — сводку отчёта тестов задания (число тестов по исходам).

   Команда ничего не создаёт и не меняет.
4. `forge-probe` и `doctor` работают и для записи с неподдержанным
   хостингом (`targets.SUPPORTED_FORGES` не расширяется). Токен не
   появляется в выводе `doctor` и `forge-probe`.
5. Песочница тестов без живого HTTP.
   `tests/sandbox.py::isolate_keychain_and_role` подменяет транспорт
   `gitlab_adapter` по умолчанию. Подмена не обращается к сети и отдаёт
   отказ соединения, который адаптер превращает в именованную причину.
   Тест, который получил токен песочницы (`fake_keychain_token`) и не
   подменил транспорт сам, живого HTTP-обращения не делает. Подмена,
   которую тест ставит сам, имеет приоритет над подменой песочницы. Это
   усиление изоляции; правка общего помощника идёт по мандату Оператора
   26.10 (решение гейта SPEC родителя, О-1, вариант (а)) с матрицей
   неослабления ниже.

## Критерии приёмки
AC-1. Фикстурное значение токена не встречается в выводе `doctor` и
выводе `forge-probe` (требование 4).

AC-2. `doctor.check_base_branch` для `forge: gitlab` на подменённом API
сверяет базу записи с `default_branch` проекта. Совпадает — `ok`,
расходится — `warn`. Без токена — `skip` с именованной причиной,
транспорт не вызван (требование 1).

AC-3. Строка `doctor` о сроке токена GitLab на подменённом API
(требование 2):
- срок через `TOKEN_EXPIRY_WARN_DAYS` дней или меньше — `warn`;
- срок дальше порога — не `warn`;
- токен без срока при числе задач проекта меньше
  `TOKEN_NO_EXPIRY_TASKS_WARN` — информационная строка, не `warn`;
- токен без срока при числе задач проекта не меньше порога — `warn`;
- задачи проекта в состоянии `killed` в счёт не идут: токен без срока при
  числе задач не-`killed` меньше порога и числе всех задач (с `killed`)
  не меньше порога — информационная строка, не `warn`;
- без токена — `skip` с причиной.

AC-4. `forge-probe <проект> --job <имя>` на подменённом API печатает
пользователя токена и уровень доступа, срок токена, защищённые ветки и
теги, последний конвейер базовой ветки (sha, итог, задания) и сводку
отчёта тестов по исходам. Все вызовы транспорта за прогон — метод `GET`.
Команда работает для записи с неподдержанным хостингом (требования 3, 4).

AC-5. В тесте под `tests/sandbox.py::isolate_keychain_and_role`, который
не подменил транспорт `gitlab_adapter` сам, запрос адаптера к записи
`forge: gitlab` с полученным токеном песочницы не открывает сетевого
соединения. Проверяется подменой `socket.create_connection`, которая
фиксирует вызов. Запрос возвращает именованную причину, а строка
`doctor.check_base_branch` для такой записи — `skip`. Транспорт,
подменённый самим тестом, вызывается вместо подмены песочницы
(требование 5).

## Оценка объёма и деление
Сработавший сигнал: в зоне 5 файлов (порог — 5).

**Обоснование монолита** (материал для решения Оператора). Задача уже
часть деления родителя, Оператор дал ей рамку $25 (ANSWER-1 родителя,
п. 4). Песочницу (`tests/sandbox.py`) нельзя отделить от строк `doctor`
для gitlab. Пока песочница не подменяет транспорт, сверка базы и строка
срока токена в `test_ac7_doctor_project_support_line` теста А0 (запись
`url: https://localhost/…`, токен `test-token-<слот>`) делают живое
HTTP-обращение. Если смержить `doctor` раньше песочницы, получится
промежуточное состояние с сетевым тестом. Если смержить песочницу
раньше, её подмену некому проверять через `doctor`. `forge-probe` в
`artel.py` формально отделим, но он небольшой и потребляет те же
функции `forge`. Ещё одна подзадача стоила бы минимум ещё одной планки
$25 и не уменьшила бы риск.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `tests/sandbox.py::isolate_keychain_and_role` подменяет транспорт `gitlab_adapter` по умолчанию (требование 5) | Изоляция связки ключей и признака роли в тестах: `tests/sandbox.py:663-680`. Нет внешних сетевых адресов в тестах: `tests/test_invariants.py::NoNetworkAddressesInTestsTest` | да, усиливается: подмена связки ключей и снятие признака роли не меняются, добавляется запрет живого HTTP к GitLab | AC-5; `NoNetworkAddressesInTestsTest` без правки | остаётся; мандат Оператора 26.10 (решение гейта SPEC родителя, О-1, вариант (а)) |
| `doctor.check_base_branch` для gitlab: `skip` → сверка через адаптер | `tests/test_doctor.py::BaseBranchCheckTest::test_non_github_forge_is_skipped` | да: без токена (или без сети под песочницей) по-прежнему `skip` | тот же тест без правки; AC-2, AC-5 | остаётся |

## Обоснование зависимостей мержа
- `01M5WCXBM7WCMRWCBWNCHMAR3T` — «часть 1» из строки ТЗ «Порядок: после
  части 1, …»: это задача GitLab А1.1, которая даёт `forge.py`/
  `gitlab_adapter.py`. Без них код этой части не работает.
- `01M5W27CY7K7NR9347NKD8F0NX` — заявлен в ТЗ буквально (А0,
  `targets.unsupported_reason`).

## Не входит
- Изменения `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py`:
  их делает часть 1. Если их не хватит — эскалация.
- Расширение `targets.SUPPORTED_FORGES` — шаг Б2.
- Правка теста А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`.
  Его `test_ac7_doctor_project_support_line` после требования 5 даёт для
  gitlab `skip` с причиной без живого HTTP. Если понадобится иная правка —
  эскалация.
- Правка существующих тестов `doctor`, в том числе
  `tests/test_doctor.py::BaseBranchCheckTest::test_non_github_forge_is_skipped`.
  Он ожидается зелёным без правки, поэтому раздела «Меняемое поведение»
  нет. Зелёность существующих тестов `doctor` для GitHub держит пульт
  (полный набор `tests/` и гейт неослабления).
- Отдельный критерий на отсутствие сравнения `forge` с литералами: его
  держит долгоживущий сторож А0 `test_ac9_no_support_literals_outside_targets`.
- Проверка фикстурного токена в журнале шагов и в текстах причин ошибок
  (AC-12 родителя в этой части): её закрыла часть 1.

## Материалы
- SPEC родителя `refs/artifacts/01M5W670PHF08VPZWDRM5BY56W:tasks/01M5W670PHF08VPZWDRM5BY56W/SPEC.md`:
  требования 11–13, 15; AC-12, AC-16, AC-17, AC-18, AC-21; «Матрица неослабления».
- `orchestrator/doctor/misc_checks.py:90` (`check_base_branch`), `:80` (`gh_env`).
- `orchestrator/forge.py:169` (`_hosting`, реестр `IMPLEMENTATIONS`), `:193` (`_call`).
- `orchestrator/gitlab_adapter.py:40-41` (константы), `:90` (`transport`),
  `:552-620` (`token_user`, `token_expiry`, `protections`, `project_info`,
  `branch_pipeline`).
- `tests/sandbox.py:663` (`isolate_keychain_and_role`).
