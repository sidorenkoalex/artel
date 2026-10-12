---
task: 01M4RRW7FT1EE77EY9Y462AZKC
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: а) раздел «Меняемое поведение» непуст; в) пути-признаки (тесты): tests/, tests/test_doctor.py, tests/test_git_fixation.py, tests/test_multitarget.py, tests/test_new_argv_parsing.py, tests/test_task_model_set_units.py
spec_sha: a107a73efe8e51a78fb70254709b589d1bd9c15c
schema_version: 5
---

# SPEC-AUDIT: Проект задачи — флаг new --target, однозначный выбор проекта и клон в target-init

Третий визит аудита, разбор полный. Код сверен по рабочему каталогу
(ветка задачи, код 3142b93b). Файлов ANSWER-n.md у задачи нет. Решения
Оператора взяты из причин двух возвратов с гейта SPEC (`artel.py log`):
2026-10-12 20:02:36Z (В-1…В-3 и др.) и 2026-10-12 20:09:03Z (три правки
по прошлому аудиту: Ф-1 вариант (а), Ф-2, AC-1 на не-artel имени).
`scripts/guard.py` на SPEC — «ок».

## ТЗ и SPEC

Требования ТЗ 1–8 есть в SPEC 1–8, в том же порядке и смысле: флаг и
справка (1), сверка в начале `cmd_new` до ТЗ/клона/id (2), правило
обязательности только в командной строке через помощник в `catalog.py`,
`cmd_new(target=None)` = артель (3), строка «Проект:» с порядком
проверок и пропуском для канарейки (4), проект в выводе и журнале (5),
клон в `target-init` со сверкой имени до каталогов и перестановками
тестов (6), тесты с заявками на все семь мутаций ТЗ (7), карта (8).

Второй возврат Оператора (20:09:03Z) отработан целиком:
- Ф-1 (а): «Меняемое поведение» велит развязать `NewSetFlagTest` с боевым
  `targets.yaml` подменой `config.TARGETS` временным файлом с одной
  записью артели; утверждения строк 153-155 и 166-167 не меняются.
- Ф-2: строки про
  `tests/test_doctor.py::RecoveryCheckTest::test_artel_gets_the_same_recovery_sverka_as_any_target`
  в SPEC больше нет.
- AC-1 теперь требует не-artel имя во временном `targets.yaml` с двумя
  записями и проверяет `target=<этот проект>` (не `None`, не `artel`) и
  `tasks.target`.

Решения первого возврата (В-1 (а) — исключение для нечитаемого
`targets.yaml` и AC-9; В-2 — рамка помощника по образцу `_new_set_arg`;
В-3 — AC-5/AC-6 на не-artel проекте без клона) на месте и не
откачены.

Сверх ТЗ и ответов в SPEC требований нет: мутация на исключение В-1 и
AC-9 прямо следуют из первого возврата. Расхождений не найдено.

## Факты против кода

Подтвердилось:
- `catalog.cmd_new` — `orchestrator/catalog.py:455`; `target or
  config.DEFAULT_TARGET` — `catalog.py:512`; чтение ТЗ —
  `catalog.py:514-518`; `workspace.ensure_clone` — `catalog.py:543`; id —
  `catalog.py:546`. Порядок требования 2/4 реализуем.
- `_NEW_USAGE` — `orchestrator/artel.py:1368`, `_parse_new_args` —
  `artel.py:1371`, `_new_set_arg` — `artel.py:1530-1542`, `_cmd_new` —
  `artel.py:1545` (в SPEC «~1550», в пределах «~»). Общая справка CLI —
  `artel.py:143`. Диспетчер зовёт `_cmd_new` через лямбду
  (`artel.py:1887`).
- `projects.cmd_target_init` — `orchestrator/projects.py:40`, клон не
  заводит; сверка имени (`projects.py:43`) уже стоит до `init_project`
  (`projects.py:48`).
- `workspace.ensure_clone` — `orchestrator/workspace.py:94`, идемпотентен
  (`workspace.py:104-105`), клонирует по `url` записи
  (`workspace.py:107-111`).
- `repo_context.resolve` разрешает артель без чтения `targets.yaml` —
  `orchestrator/repo_context.py:82-89`.
- `NewSetFlagTest` — `tests/test_task_model_set_units.py:137`, голый
  `unittest.TestCase`; методы на 150-155 и 164-167, утверждения
  совпадают с перечисленными в SPEC. Образец подмены —
  `tests/sandbox.py:1135-1147` (`declared_artel_profile`, контекстный
  менеджер, `mock.patch.object(config, "TARGETS", path)`). Боевой файл —
  `orchestrator/config.py:20`, в нём одна запись `artel`
  (`targets.yaml:21`).
- `tests/test_new_argv_parsing.py:24-30` (форма возврата) и проверки
  справки `:43-70` (подстрока `new "<название>"`) — подтверждено, смена
  `_NEW_USAGE` их не трогает. В `tests/test_task_model_set_units.py`
  литерала справки нет.
- Перестановки: `cmd_target_init("sled")` сейчас до
  `make_project_repo("sled")` — `tests/test_git_fixation.py:199/202`,
  `:280/283`, `:407/410`; `tests/test_doctor.py:558/559`. Комментарии
  `tests/test_git_fixation.py:246` и `tests/test_multitarget.py:273-275`
  на месте.

Проверено прогоном (в памяти, без правки кода):
- правило требования 3 как обёртка `artel._cmd_new` (отказ без
  `--target` при >1 записи) — 100 тестов файлов, вызывающих `new` из
  CLI (`test_01m3xtf5506gf43hd51ece230t_role_refusal`,
  `test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint`,
  `test_01m3ychs4f08vtv6xx10vf92h3_task_model_set`,
  `test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension`,
  `test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight`,
  `test_analyst_role`, `test_task_model_set_units`,
  `test_new_argv_parsing`), — зелёные: песочницы держат одну запись.
- `target-init` с `ensure_clone` и отказом при его неудаче (обёртка
  `projects.cmd_target_init`) — 349 тестов из 17 файлов, вызывающих
  `target-init` (`test_doctor`, `test_git_fixation`, `test_multitarget` и
  14 приёмочных `test_01m…`). Падают 6 методов, и только из-за setUp,
  который перечислен в «Меняемом поведении»: `RecoveryCheckTest` (3
  метода, общий setUp) и три класса `External*` из
  `tests/test_git_fixation.py`. Перечень перестановок полон и не
  избыточен. `NoFixationRepoTest`
  (`tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py:200`) клон
  кладёт заранее (`:66-80`) и зелёный.

Мелкое (не отклонение): требование 5 в части вывода уже держится на
main — `catalog.py:556` печатает «(target {target}, …)». Новое по
существу — только проект в `detail` записи `created` (сейчас там
название, `catalog.py:595`); это AC-6 и проверяет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | флаг не передан в `cmd_new` (на не-artel имени задача уйдёт в artel / `target=None`); флаг без значения проглочен или стал названием; справка без `--target <имя>` |
| AC-2 | да | сверка после чтения ТЗ (нечитаемый `--tz` даст отказ о ТЗ без перечня); после `ensure_clone`, id, строки БД (останутся строка, ссылка, каталог клона); отказ без перечня проектов |
| AC-3 | да | при двух записях `new` без флага ушёл в artel; при одной записи `new` без флага отказывает |
| AC-4 | да | правило требования 3 перенесено в `cmd_new` — вызов без `target` (канарейка) отказывает |
| AC-5 | да | «Проект:» не сверяется; две строки без отказа; сверка после `ensure_clone` (появится каталог клона); отказ при `canary=True` |
| AC-6 | да | проект не пишется в запись `created`; флаг не передан (задача не на проекте) |
| AC-7 | да | `target-init` не зовёт `ensure_clone`; пересоздаёт клон; при неудаче клона код 0, нет причины или каталоги убраны |
| AC-8 | да | каталоги создаются до сверки имени (на main уже держится — `projects.py:43-48`, `tests/test_multitarget.py:313-319`; регрессионная страховка) |
| AC-9 | да | исключение В-1 не реализовано (отказ `new` артели при нечитаемом `targets.yaml` — в `cmd_new` или правилом CLI); нет предупреждения |

## Зоны

Зоны SPEC: `orchestrator/artel.py`, `orchestrator/catalog.py`,
`orchestrator/projects.py`, `tests/`, `docs/codebase-map.md` — совпадают
с ТЗ и покрывают всё, что требуют требования 1–8, включая подготовку
`NewSetFlagTest` и перестановки в `tests/`. Защищённые пути
(`config.PROTECTED_PATHS`) не задеты; песочница ролей не расширяется;
пути «только чтение» ТЗ перенесены в «Не входит».

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Сверка проекта с `targets.yaml` в начале `cmd_new` (треб. 2) | `new` артели работает при сломанном `targets.yaml` (`orchestrator/repo_context.py:82-89`) | да, исключение В-1 | AC-9 | ок |
| Правило «>1 записи → нужен `--target`» в CLI (треб. 3) | форма вызова `cmd_new` без `target` — `tests/test_task_model_set_units.py:166-167` | да; после развязки с боевым `targets.yaml` — и при записи sled | тот же тест с подменой `config.TARGETS` | ок |
| Помощник `--target` до `_parse_new_args` (треб. 1, В-2) | пара `(title, tz_path)` — `tests/test_new_argv_parsing.py:24-30` | да | тот же тест | ок |
| `target-init` заводит клон (треб. 6) | `target-init` без клона завершался успехом — setUp `tests/test_git_fixation.py:199,280,407`, `tests/test_doctor.py:558` | меняется по ТЗ п. 6: при неудаче клона — отказ, каталоги остаются | AC-7; прежние утверждения переставленных тестов | ок (ТЗ п. 6, «Меняемое поведение») |
| `target-init`: сверка имени до каталогов | `tests/test_multitarget.py:313-319` | да | тот же тест и AC-8 | ок |
| `cmd_new(target=None)` при нескольких записях | `orchestrator/canary_drive.py` (вызов без `target`) | да | AC-4 | ок |

Раздел «Меняемое поведение»: смен литералов утверждений не объявлено;
строки — перестановки подготовки и правка комментариев, без строк вида
`- ` (guard их как смену литерала не разбирает) — нарушений формы нет.

## Пути обхода гейтов

- Прошлый путь О-1 (зелёный на ветке тест, краснеющий на main после
  записи sled) закрыт требованием развязки `NewSetFlagTest`.
- Прошлый О-2 (AC-1 на `--target artel`) закрыт: AC-1 требует не-artel
  имя и `target` не `None`/`artel`.
- Новых путей не найдено. Остаточная неопределённость, не обход:
  исключение В-1 сформулировано для `target=None`; `--target artel` при
  нечитаемом `targets.yaml` по тексту требования 2 отказывает
  (имя не сверить). Это строже и согласуется с ТЗ п. 2.

## Вердикт

**pass.** Все пункты обоих возвратов Оператора отработаны, утверждения
SPEC о коде подтверждены (`catalog.py:455-556`, `artel.py:1368-1550`,
`projects.py:40-55`, `workspace.py:94-118`, `repo_context.py:82-89`,
`tests/test_task_model_set_units.py:137-167`), каждый AC ловит
правдоподобную мутацию, зоны и матрица полны. Отклонений нет.
