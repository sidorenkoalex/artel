---
task: 01M58FNWBV25FF26E7AZ9Q9912
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G1а: компоненты проекта в записи targets.yaml — схема, выбор по путям, проверки doctor

# G1а: компоненты проекта в записи targets.yaml — схема, выбор по путям, проверки doctor

## Факты

Первая задача волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, принят Оператором 19.10.2026; разделы «Решение» п. 1–3, «Описание sled после ADR», «Порядок исполнения» — строка G1а). Задача вводит схему и выбор компонентов; исполнение прогонов по компонентам (отчёт, раннер) — следующая задача G1б, не эта.

- Профиль тестов — одно поле записи проекта: `orchestrator/targets.py:43` (`PROFILE_FIELD = "test_profile"`), `:44-60` (`PROFILE_FIELDS`), `:61-73` (необязательные подполя, `PROFILE_REPORTS = ("junit-xml",)`, раннеры), проверка — `targets.py:175-190`, `:300-320` (`_check_profile`).
- Разбор — `orchestrator/project_profile.py:65-121` (`Profile`, `from_values`, маски `in_weakening_scope`, `long_lived_*`), выбор профиля задачи — `project_profile.decide` (`:143`) и `for_task` (`:175`); источник — `orchestrator/repo_context.py:139-151` (`profile_of` читает одно поле `test_profile`).
- Ключ кэша итога полного набора собственного раннера проекта — `orchestrator/acceptance.py:2146-2158` (`_own_suite_result_key`): дерево, команда, `sys.version` и пакеты Python пульта; файлы блокировки зависимостей проекта (`uv.lock`, `package-lock.json`) и версии инструментов проекта в ключ не входят — после смены зависимостей проекта устаревший зелёный итог сойдёт за свежий.
- `doctor` проверяет запись проекта (`orchestrator/doctor/project_checks.py`), но не версии инструментов проекта и не согласованность карты путей с CI проекта.
- Живой пример двух компонентов — sled (`main` 7131152): CI `ci.yml:58-63` — задание `changes` с переменными `BACKEND_RE` и `FRONTEND_RE`; `FRONTEND_RE` включает восемь файлов backend (`backend/seed/`, `backend/src/core/deadline_policy.py`, `backend/src/apps/control/constants.py` и др.); `frontend/.nvmrc` — `22`. Запись sled в `targets.yaml` в этой задаче не меняется (её переводит Оператор на этапе 2 плана).

## Требуется

1. Запись проекта может нести поле `components:` (список) вместо `test_profile`; оба поля в одной записи — отказ проверки записи. Компонент — прежние подполя профиля (`command`, `long_lived_dir`/`long_lived_name` или новый `long_lived`, `weakening_scope`, `mutation_claim_scope`, `report`, `install`, `full_suite_timeout_sec`, `runner`, `workdir`, `env`, `long_lived_imports`) и новые поля ADR-0026 п. 1: `name` (уникальное в записи), `repo` (по умолчанию — имя записи), `report_args`, `select`, `failure_errors`, `paths` (регулярные выражения путей от корня репозитория; обязательное у записи с несколькими компонентами), `paths_source` (необязательное: `{file, key}` — откуда в CI проекта взяты `paths`), `depends_on` (список `{component, via: paths|files|contract, paths}`; `contract` — только разбор и проверка формы, без исполнения), `tests`, `test_support`, `long_lived`, `plank_layout`, `tools` (`{имя инструмента: требуемая версия}`), `knowledge`, `layers`, `checks_local`. Каждое поле проверяется по форме с понятным отказом; неизвестное поле — отказ. Значение `report` дополняется `pult-vitest` (только как допустимое значение; отчётчик — G1б).
2. Прежнее поле `test_profile` читается как один компонент с именем `default`; разбор, поля `Profile`, исходы `for_task`/`decide` и все тексты для записей с `test_profile` (артель, sled сегодня) — прежние. Зафиксировать тестами до правки.
3. Выбор компонентов: функция пульта по проекту и набору путей возвращает затронутые компоненты — чьи `paths` или `test_support` задевают путь, плюс их потребители по `depends_on` (`paths` и `files`); путь, не задевший ни одного компонента, — все компоненты (не пустой выбор). У записи с одним компонентом — он. Идентификатор теста компонента: формирование и разбор `<компонент>:<путь файла от корня репозитория>::<полное имя>[#<n>]` (ADR п. 3). Формат зон задачи не меняется.
4. Пока исполнения по компонентам нет (G1б): для записи с несколькими компонентами `for_task`/`decide` отказывают задаче с явным текстом «запись проекта с несколькими компонентами исполняется после G1б»; запись с одним элементом `components:` ведёт себя как `test_profile`.
5. `doctor` для каждого проекта с `components:`: (а) версия каждого инструмента `tools` — запуск `<инструмент> --version` с окружением компонента (`env.PATH`), сравнение с требуемой (совпадение главной части версии); несовпадение — fail, инструмента нет — fail, сбой запуска — skip с причиной; (б) `paths_source`: значение переменной `key` в файле `file` клона проекта сравнивается с `paths` (и с `depends_on` вида `paths`/`files` того же компонента) — расхождение — warn с обеими строками; (в) каждый `workdir` существует в клоне. У записей с `test_profile` — новых строк нет.
6. Ключ кэша итога полного набора собственного раннера проекта включает суммы файлов блокировки зависимостей в `workdir` (`uv.lock`, `package-lock.json`, `poetry.lock`, `yarn.lock`, `pnpm-lock.yaml` — какие есть) и `tools` компонента; у артели ключ прежний.
7. Тесты детерминированы, без сети: учебные записи с одним и двумя компонентами (`depends_on` вида `files`), подмена запуска инструментов для `doctor`, учебный клон с CI-файлом для `paths_source`.

Критерии приёмки:
- запись с двумя компонентами проходит проверку записи; каждое поле с неверной формой даёт свой отказ; `test_profile` и `components:` вместе — отказ;
- выбор компонентов: путь backend → backend; путь из `depends_on` вида `files` → и поставщик, и потребитель; путь `docs/x.md` → все; у записи с одним компонентом — он;
- `doctor`: v22 при требуемой `22` — ok; v20 — fail; нет инструмента — fail; расхождение `paths` с переменной CI — warn;
- смена `package-lock.json` (или `uv.lock`) меняет ключ кэша итога; у артели ключ и все тексты прежние;
- задача на записи с двумя компонентами получает явный отказ до G1б.

Зоны: `orchestrator/targets.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/doctor/project_checks.py`, `orchestrator/doctor/cli.py`, `orchestrator/acceptance.py` (только ключ кэша `_own_suite_result_key`), `tests/`.

Только чтение: `targets.yaml`, `docs/adr/0026-project-components-and-outcome-gates.md`, `orchestrator/doctor/hung_test_watchdog.py`, `orchestrator/advance_gates/`, `orchestrator/fsm*.py`, `scripts/guard.py`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: исполнение прогонов по компонентам, отчёт JUnit и отчётчик Vitest, окружение Vitest, установка зависимостей пультом (G1б); планка и долгоживущие файлы по компоненту (G2); гейт неослабления по исходам (G3); перевод записи sled в `targets.yaml` (этап 2 плана, Оператор); многорепозиторное исполнение.

Рамка: $40. Набор моделей — по умолчанию.
