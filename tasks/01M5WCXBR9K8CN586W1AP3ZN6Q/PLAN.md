---
task: 01M5WCXBR9K8CN586W1AP3ZN6Q
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab А1.2 — doctor, forge-probe и песочница без живого HTTP

## Подход
Реализация хостинга выбирается реестром `forge.IMPLEMENTATIONS` по полю
`forge` записи — без литералов `"github"`/`"gitlab"` и без
`targets.FORGES` (требования 1, 2; AC-6):

- `misc_checks.check_base_branch`: реализация записи, у которой есть
  `project_info`, сверяет базу через `forge.project_info`
  (`ok`/`warn`, причина адаптера — `skip`); реализация без неё
  (сегодня GitHub) — прежний путь `gh repo view` без изменений; значение
  `forge` вне реестра — `skip` с причиной.
- новая `misc_checks.check_token_expiry(conn, name, entry)`: `None` (строки
  нет), если у реализации нет `token_expiry` (GitHub); иначе строка
  `token-expiry-<проект>` по `forge.token_expiry`. Пороги — константы
  реализации (`TOKEN_EXPIRY_WARN_DAYS`, `TOKEN_NO_EXPIRY_TASKS_WARN` у
  `gitlab_adapter`), число задач — `store.project_tasks` без `killed`.
  Ошибка запроса и отсутствие токена — `skip` с причиной адаптера.
- `doctor/__init__.py` импортирует коллаборанта `forge` и экспортирует
  `check_token_expiry`; `doctor/cli.py:all_checks` добавляет строку сразу
  за `base-branch`, если она есть.
- `artel.py`: команда `forge-probe <проект> [--job <имя>]` — только чтение
  через `forge.token_user/project_info/token_expiry/protections/
  branch_pipeline/job_test_report`; отчёт — по sha конвейера из
  `branch_pipeline`, без конвейера — его причина. Токен не печатается:
  выводятся только поля результатов и причины адаптера (они токена не
  несут — часть 1). Вне белого списка ролей (ходит в сеть с токеном
  проекта), строка справки — в блоке «Команды:».
- `tests/sandbox.py::isolate_keychain_and_role`: если
  `gitlab_adapter.transport` — исходная функция (снимок при импорте
  песочницы), ставит подмену, бросающую `URLError(ConnectionRefusedError)`;
  транспорт, уже подменённый тестом до песочницы, не трогается, подмена
  теста после песочницы перекрывает её обычным образом.

## Шаги
1. Песочница: снимок исходного транспорта и условная подмена в
   `isolate_keychain_and_role`.
2. `misc_checks.py`: `check_base_branch` через реестр, `check_token_expiry`;
   фасад `doctor/__init__.py`; регистрация в `doctor/cli.py`.
3. `artel.py`: `forge-probe` (+ справка).
4. Карта кодовой базы, прогон долгоживущих файлов задачи и тестов
   затронутых модулей (`test_doctor.py`, тесты части 1, help registry,
   A0).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 3 |
| 4 | 2, 3 |
| 5 | 1 |

## Влияние на систему
- Песочница только усиливается: связка ключей и признак роли не
  меняются, добавляется запрет живого HTTP к GitLab; приоритет транспорта
  теста сохранён при обоих порядках (матрица неослабления SPEC).
- Путь GitHub в `check_base_branch` переносится без правки тела;
  `test_doctor.py::BaseBranchCheckTest` без правки (адрес `file://`
  отвергается адаптером до токена — `skip`).
- `forge.py`/`gitlab_adapter.py` не меняются. Откат — revert merge-коммита.

## Риски
- Строка `token-expiry-<проект>` добавляет обращение к хостингу в каждый
  `doctor` для gitlab-записей (таймаут адаптера 20 с на запрос) — только
  чтение, ошибки — `skip`.

## Проверка
- Долгоживущие файлы задачи: 35 passed. Своих тестов не добавлял — все
  свойства SPEC (AC-1…AC-6) покрыты долгоживущими файлами test_author.
- `tests/test_doctor.py`, тесты частей 1 и А0, help registry, fixtures —
  388 passed; `test_doctor_*`, `test_invariants.py`, role_refusal,
  codebase_map, multitarget и др. — 271 passed. Карта регенерирована.

## Предложения системе
