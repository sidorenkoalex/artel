---
task: 01M48WTP12VC8MY2BNE5JSVXKA
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Общая подготовка git-песочниц и фикстур

## Подход

Два git-шаблона создаются лениво по одному разу на процесс в каталоге
модульной фикстуры вне каталогов тестов. `setUp` копирует шаблон в свой
временный каталог, а затем выполняет прежнюю индивидуальную подготовку.
Шаблон не сохраняется в атрибутах экземпляра. Общие построители возвращают
текст записи артели и заводят bare-origin с явным `-b config.MAIN_BRANCH`.
Утверждения остаются в тестовых методах.

| Откуда | Куда |
|---|---|
| `TmpRootTest.setUp` → `seed_artel_clone_stub` (`git init` каждый раз) | шаблон заглушки в `tests/sandbox.py`, копия при каждом `setUp` |
| `RealGitSandbox.setUp` (`git init`, конфиг, первый коммит каждый раз) | шаблон однокоммитного репозитория в `tests/sandbox.py`, копия при каждом `setUp` |
| Повторные записи `targets.yaml` в `tests/` | построитель записи артели в `tests/sandbox.py` |
| Повторные `git init --bare` в `tests/` | общий помощник bare-origin в `tests/sandbox.py` |

## Шаги

1. Зафиксировать замеры до изменений; создать шаблоны и общие помощники без изменения утверждений.
2. Перевести дословные копии подготовки в разрешённых файлах `tests/`; добавить поведенческие юнит-тесты на независимость копий и HEAD origin.
3. Прогнать планку и затронутые модули; обновить карту, проверить PLAN через guard. Полный набор и его замеры ждут ответа на эскалацию.

## Покрытие требований

| Требование SPEC | Шаг |
|---|---|
| 1: шаблоны и личные копии | 1, 2 |
| 2: HEAD bare-origin | 1, 2 |
| 3: помощники и переход файлов | 1, 2 |
| 4: замеры | 1, 3 |
| 5: утверждения остаются на месте | 2, 3 |
| 6: сторожа независимости и HEAD | 2, 3 |

## Влияние на систему

Меняется только подготовка тестовых песочниц. Схема БД, сетевые ограничения,
гейты, лимиты и поведение команд пульта не меняются. Рабочие копии песочниц
по-прежнему индивидуальны; процессные шаблоны доступны только модулю.
Откат — revert одного merge-коммита задачи. Дифф тестов добавляет утверждения
нового метода и не меняет существующие; залоченные файлы не затронуты.

## Риски

Тесты, зависящие от индивидуального локального git-конфига, должны получать
его копию. Проверяю именно полным набором и планкой. `suite-run` использует
`-n auto`; для замеров 4/8 воркеров установленный xdist принимает
`PYTEST_XDIST_AUTO_NUM_WORKERS`.

## Кандидаты для Оператора: долгоживущие тесты

- `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py` — построитель записи targets.
- `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py` — построитель записи targets.
- `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py` — построитель записи targets.
- `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py` — построитель записи targets.
- `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py` — построитель записи targets.
- `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py` — построитель записи targets.
- `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py` — построитель записи targets.
- `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py` — построитель записи targets.
- `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py` — построитель записи targets.
- `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py` — построитель записи targets.
- `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` — построитель записи targets.
- `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py` — построитель записи targets и помощник bare-origin.
- `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py` — помощник bare-origin.
- `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py` — помощник bare-origin.
- `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py` — помощник bare-origin.
- `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py` — помощник bare-origin и построитель записи targets.

## Замеры

8 последовательных `setUp` в одном процессе, медиана (включая холодный
первый вызов):

| Основание | До | После |
|---|---:|---:|
| `TmpRootTest.setUp` | 30,89 мс | 7,34 мс |
| `RealGitSandbox.setUp` | 129,35 мс | 13,83 мс |

Полный набор `tests/`: `-n 4` до/после — не измерено; `-n 8` до/после — не
измерено. Вызов `PYTEST_XDIST_AUTO_NUM_WORKERS=4 python3
/Users/al.sidorenko/projects/artel/orchestrator/artel.py suite-run
01M48WTP12VC8MY2BNE5JSVXKA` после освобождения общего замка завершился
`PermissionError` при создании `.artel/logs/suite-run/lock.json`.

Проверки: 458 тестов затронутых модулей и 26 subtests прошли (362,93 с);
18 тестов `test_sandbox.py` и зафиксированного файла копий прошли (0,88 с).
Новый тест построителя `targets.yaml` покраснел при временной мутации
`return entry` вместо `return entry + ARTEL_TEST_PROFILE`; код восстановлен.
`python3 scripts/guard.py <каталог документов>/PLAN.md` — `GUARD: ок`.
Локальная планка: 2 прошли, 3 красные из-за чтения PLAN/диффа из
артефактной/кодовой веток до автокоммита шага; см. наблюдение ниже.

## Предложения системе

- `suite-run` не принимает число воркеров для сравнительного замера: приходится задавать `PYTEST_XDIST_AUTO_NUM_WORKERS`; добавить параметр `--workers` к команде пульта.
- `plank-run` читает `PLAN.md` из refs/artifacts, а новый PLAN на этапе developer лежит только в каталоге документов до автокоммита шага: локальные AC-8/AC-9 ложно красные. Нужен просмотр текущего каталога документов задачи при локальном прогоне.
- `suite-run` из шага роли создаёт замок в `.artel/logs/suite-run/lock.json`, но этот путь вне разрешённой записи роли: после освобождения замка команда завершилась `PermissionError: [Errno 1] Operation not permitted`. Пульт должен предоставить команде свой канал записи без расширения прав роли на весь каталог логов.

## Эскалация

### Вопросы

- Как выполнить обязательные четыре полных замера через штатный `suite-run`, если роль не может создать замок и логи в `.artel/logs/suite-run/`? Варианты: А) пульт предоставляет команде доступ к собственному каналу записи и повторяет шаг developer; Б) Оператор выполняет `suite-run` с 4/8 воркерами на базовой и текущей версии и передаёт четыре результата для PLAN. По умолчанию — А.

### Контекст

- `tests/sandbox.py` и разрешённые тесты изменены; карта пересобрана. Затронутые тесты зелёные, `git diff --check` зелёный. Замеры `setUp` выше.
- Отказ `suite-run`: `orchestrator/suite_run.py:622` → `orchestrator/suite_lock.py:93` → `PermissionError` на `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json`. До этого общий замок был занят прогоном `notes`; после его освобождения выявился отказ прав.
- `plank-run` читает PLAN из `refs/artifacts/<id>` до автокоммита, поэтому локально AC-8/AC-9 пока не видят текущий файл; AC-7 также смотрит коммитный дифф до чекпоинта. На следующем шаге после автокоммита планку можно повторить.

### Блокирует

- Требование 4 и AC-9: времена полного набора до/после при `-n 4` и `-n 8`; без них PLAN нельзя сдать со статусом `ready`.
