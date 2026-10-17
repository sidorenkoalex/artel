---
task: 01M545EDTHS47HSB59AKC1EZ9C
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: D2-2 — токен хостинга внешнего проекта и проверки doctor

## Подход
Механизм токена живёт в `orchestrator/gitcmd.py` — единственной точке
git-вызовов пульта; сигнатура `gitcmd.git(*args)` не меняется.

- `gitcmd.git` разбирает ведущие `-C`/`-c` и подкоманду. Подкоманда
  `fetch`/`push`/`pull`/`ls-remote` — кандидат в хостинговую операцию.
  Проект определяется по пути `-C` (под `config.PROJECTS/<имя>/<…>`, имя ≠
  артели; сам каталог проекта не в счёт) либо, у `push`, по позиционному
  аргументу, совпадающему с `url` записи внешнего проекта (независимо от
  `-C`). Запись берётся из `targets.load()`; файл не читается — прежнее
  поведение.
- Хостинговая операция внешнего проекта (`gitcmd.hosting_token(name, entry)`,
  общая для git, `gh` и doctor): процесс роли (`runner.in_role_environment`)
  — именованный отказ без чтения слота, для записи с `token_slot` и без;
  нет поля `token_slot` — прежняя авторизация; слот пуст — отказ с именем
  слота; иначе токен.
- git получает токен только окружением: `GIT_CONFIG_COUNT/KEY/VALUE`
  дописывают `credential.helper=` (сброс чужих помощников: глобального и с
  областью URL) и помощник пульта, который читает пароль из переменной
  окружения `ARTEL_HOSTING_TOKEN` (`"$ARTEL_HOSTING_TOKEN"` в теле shell-
  функции — значение не попадает ни в argv git, ни в argv помощника).
  `.git/config` и `GIT_CONFIG_GLOBAL` не трогаются.
- `ci.gh(..., repo=<url>)`: проект находится по `url`, `GH_TOKEN` — в
  окружении вызова; отказ — `CompletedProcess` с кодом 1 и текстом отказа
  (вызывающие уже пишут его в журнал/инцидент). Без `repo=` — как на main.
- `doctor`: `check_base_branch` — токен проекта в окружении прямого `gh`.
  Новый подмодуль `orchestrator/doctor/project_checks.py` — проверки п.5
  (7 строк на запись внешнего проекта, «неприменимо» на запись артели,
  пропуск «только в сессии Оператора» у 5.1/5.2/5.5 в процессе роли);
  зовётся из `all_checks` в цикле по записям `targets.yaml`. Порог
  свежести клона — `config.PROJECT_CLONE_STALE_HOURS = 24`.
- `_push_closing_sha` не меняется: push по URL `origin` клона получает токен
  вторым признаком (URL push).
- Песочница `tests/sandbox.py` (`TmpRootTest.setUp`, `RealGitSandbox.setUp`):
  подмена `keychain.token` на `test-token-<слот>`, снятие `ARTEL_ROLE` и
  замена `HOME`, если он — дом роли.

### ANSWER-1 (17.10.2026)
- П-2: `tests/test_doctor.py::BaseBranchCheckTest` переведён на песочницу
  правкой `setUp` — подмена `config.ROLE_HOME` временным каталогом и
  `isolate_keychain_and_role` (снятие `ARTEL_ROLE`, подмена слота), как в
  `TmpRootTest`; утверждения не менялись, приёмочные тесты не правились.
- Ф-2: уже так — `gitcmd.git` и `ci.gh(repo=)` берут запись из
  `targets.load()` по имени проекта из пути `-C` или по URL
  (`gitcmd._hosting_project`, `gitcmd.project_by_url`); `entry`
  вызывающего — только у `check_base_branch` и проверок п.5.
- Р-1: уже так — в процессе роли `check_base_branch` даёт `skip` с текстом
  отказа `gitcmd.hosting_token` (`misc_checks.py:104-106`), 5.4 — строка
  «защита базовой ветки: недоступно — <отказ>» (`project_checks.py:185`).
- Ф-3: уже так — признак по пути `-C` берётся только под `config.PROJECTS`
  (`gitcmd._project_of_path`): весь `config.ROOT` вне него исключён.

## Шаги
1. `gitcmd.py`: разбор аргументов, определение проекта, `hosting_token`,
   окружение помощника, отказ; `config.PROJECT_CLONE_STALE_HOURS`.
2. `ci.gh`: `GH_TOKEN` проекта по `repo=`.
3. `doctor`: `check_base_branch` с токеном; `project_checks.py`; вызов из
   `all_checks`; `brief`/`project_profile` — коллаборанты фасада.
4. `tests/sandbox.py`: подмена `keychain.token`, нейтрализация признака роли.
5. Карта `docs/codebase-map.md`, прогон долгоживущего файла, планки и тестов
   затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2, 3 |
| 2 | 1, 2 |
| 3 | 1, 2, 3 |
| 4 | 1, 2 |
| 5 | 3 |
| 6 | 3 |
| 7 | 1, 3 |
| 8 | 1 |
| 9 | 4 |

## Влияние на систему
- Все git-вызовы пульта проходят через `gitcmd.git`: для локальных команд
  и для артели окружение и argv байт-в-байт прежние (AC-1); `targets.yaml`
  читается только для remote-подкоманд в области внешнего проекта и для
  `push` (сравнение URL). Ошибка чтения `targets.yaml` — прежнее поведение,
  не отказ.
- Процесс роли теряет хостинговые операции внешних проектов (требование 7)
  — артель не задета.
- Песочница: подмена `keychain.token` меняет умолчание для тестов, которые
  не подменяли слот сами (раньше на Linux CI — `None`, на машине Оператора
  — настоящая связка ключей); тест, полагавшийся на «слота нет» без своей
  подмены, был недетерминирован. Гейты, лимиты, инварианты не трогаются.
- Откат — revert merge-коммита задачи.

## Риски
- Тесты, сверяющие точное окружение git-вызова внешнего проекта с
  `token_slot` (теперь в нём `GIT_CONFIG_*`), — проверяется полным набором.
- `gh api` не принимает `--repo`: проверка 5.4 зовёт `gh` напрямую
  (`doctor.subprocess.run`) с `GH_TOKEN` проекта.

## Проверка
- `tests/test_01m545edths47hsb59akc1ez9c_project_token.py` — 18 passed;
  планка `plank-run` (AC-11) — 1 passed.
- `suite-run` №1: 5570 прошло, 1 новое падение — мой
  `tests/test_hosting_token_units.py` с адресом `https://…` (инвариант
  `NoNetworkAddressesInTestsTest`); адреса заменены на `file://`, повтор
  №2 (`--failed`) — зелёный.
- Свой тест `tests/test_hosting_token_units.py` проверен временной мутацией
  (`count = 0` в `gitcmd.hosting_env`) — красный, код возвращён.

- ANSWER-1, П-2: `BaseBranchCheckTest` из шага роли — 5 passed; с
  временно снятым `isolate_keychain_and_role` в его `setUp` — 2 failed
  (`test_matching_base_branch_is_ok`, `test_diverging_base_branch_is_warn`),
  возвращено. `tests/test_doctor.py`, `tests/test_hosting_token_units.py`,
  долгоживущий файл — 135 passed; планка — 1 passed; `suite-run` №3 —
  зелёный (5601 прошло, 0 упало, 2 пропущено).

## Предложения системе
- Класс «тест вне песочницы видит признак роли» (`ARTEL_ROLE`/`HOME` дома
  роли при локальном `pytest` из шага роли) закрыт для `BaseBranchCheckTest`
  точечно; общий кандидат — снятие признака в `conftest.py` (защищённый
  путь, решение Оператора).
- Фасад `orchestrator/doctor/__init__.py` делает `from .x import x`: функция
  с именем подмодуля затеняет сам подмодуль (`from orchestrator.doctor
  import <подмодуль>` отдаёт функцию) — наступил на это с `project_checks`.
