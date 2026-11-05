---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/forge.py, orchestrator/gitlab_adapter.py, orchestrator/doctor/project_checks.py, orchestrator/ci.py, orchestrator/ci_rerun.py, orchestrator/cleanup.py, docs/codebase-map.md, tests/
budget_usd: 85
---

# SPEC: Ручной мерж для GitHub, часть 2 — открытие пары `github` + `target-human`, проверки записи и строки `doctor`

## Контекст
Часть 1 (задача 01M6M1799YCY5HXMHHD71SHJET, смержена 05.11) дала `_GitHub`
функции MR, но пара `github` + `target-human` по-прежнему закрыта
(`orchestrator/targets.py:31-33`, `SUPPORTED_PAIRS = {("github",
"operator"), ("gitlab", "target-human")}`). Эта задача открывает пару и
закрывает то, что в проекте людей на GitHub опасно или не проверено:
повтор CI пультом (`ci.trigger_rerun` зовёт настоящие `gh run rerun`/`gh
run watch`, `orchestrator/ci.py:1793-1837`), поле `policy.ci_required_jobs`,
которое `_GitHub` не читает (`orchestrator/gitlab_adapter.py:417-418`,
`orchestrator/ci.py:27`), закрытие PR при `kill` до отправки
(`orchestrator/cleanup.py:311-312`, `:245`), и проверку `doctor`
`project-ci-file-no-paths`, которая знает только `.gitlab-ci.yml`
(`orchestrator/doctor/project_checks.py:668`, `:740-750`). Решения
Оператора 01.11 и 04.11 (ТЗ), 05.11 — `ANSWER-1.md` (мандат на правку трёх
файлов тестов, монолит с рамкой $85).

Сверка ТЗ с кодом ветки (HEAD 2b62f8a03, часть 1 в ней): номера строк
фактов 1–13 совпадают; отличий `_check_delivery` для GitHub нет
(требование 2); строки `doctor` для записи GitHub `target-human` строятся
так, как называет требование 4; пять тестов «ожидаются зелёными» ТЗ на
ветке до правок зелёные (91 passed).

## Требования

1. **Открыть пару.** `SUPPORTED_PAIRS` — `{("github", "operator"),
   ("github", "target-human"), ("gitlab", "target-human")}`; комментарий над
   константами (`orchestrator/targets.py:25-30`) описывает новый состав.
   Неподдержанной остаётся `gitlab` + `operator`; функция
   `unsupported_reason` не правится — текст причины меняется только перечнем
   пар.
2. **Те же проверки записи.** Запись `github` + `target-human` проходит
   ровно через `_check_delivery` (`orchestrator/targets.py:622-726`) и
   правило источника полного набора `full_suite`
   (`orchestrator/targets.py:1137-1160`) — без новых исключений для GitHub.
3. **`project-ci-file-no-paths` для GitHub.** Для записи с `target-human`
   хостинга без конвейеров (`not forge.ci_by_pipeline`, без сравнения
   значения `forge` с литералом) строка строится всегда, без условия
   `full_suite`; для хостинга с конвейерами (GitLab) — прежнее условие
   (компонент с `full_suite` ci/both). Проверяемый путь — по реализации
   хостинга: GitLab — файл `.gitlab-ci.yml`, как сейчас; GitHub — каталог
   `.github/workflows/`: `ok`, если
   `config.is_protected_path(".github/workflows/<любой файл>", no_paths
   записи)` истинно для КАЖДОГО имени файла каталога (любой записью
   `no_paths`, для которой формула истинна); иначе `fail` с именем каталога.
   Проба одним или несколькими конкретными именами файла этого не
   доказывает. По формуле `config.is_protected_path`
   (`orchestrator/config.py:818-849`) это ровно записи трёх видов: строка,
   которая является префиксом `.github/workflows/` (включая саму
   `.github/workflows/`, `.github/`, `.github`); `**/workflows/`;
   `**/.github/`. Записи `**/`, `**/<имя файла>` и префиксы, длиннее
   `.github/workflows/` (например `.github/workflows/c`), каталог не
   покрывают — `fail`. Маски вида `*` для GitHub не принимаются. Проверка
   выполняется не пробой самим путём каталога `.github/workflows/` (она
   истинна для записи `**/`, хотя ни один файл под каталогом ей не покрыт)
   и не одним фиксированным именем файла (оно пропускает записи на
   отдельный файл вида `**/<имя>` и `.github/workflows/<имя>`): запись
   `**/` и записи на отдельный файл дают `fail` при любом имени.
4. **Явные исходы прочих строк `doctor` для GitHub `target-human`** —
   закрепляются тестами без правки кода: `project-support` — `ok`;
   `project-submodules` и строки хука `pre-push` — есть;
   `project-ci-reruns` — нет; `token-expiry` — нет.
5. **Полный цикл в песочнице.** Задача вымышленного проекта `github` +
   `target-human` проходит путь: вход в `verifying` (черновой PR открыт
   `ensure_forge_draft_mr`) → `approve` на `merge_gate` → `awaiting_human`
   (черновик снят, исполнитель назначен) → вливание в локальном `origin` →
   `mr-sync` «влит этим MR» → `mr-sync --confirm` → `done`. `kill` такой
   задачи после отправки не трогает ни ветку, ни PR, `gh pr close` не
   вызывается.
6. **Документация.** `docs/codebase-map.md` описывает затронутые тесты и
   строки `doctor`.
7. **Без повтора CI в проекте людей.** `ci.trigger_rerun` для клона
   проекта с `targets.merged_by_project_people` не зовёт `gh` и до любого
   вызова `gh` возвращает «ре-ран CI не запущен: …» с причиной (как отказ
   GitLab). Исход гейта мержа на красном CI — прежний путь неудачного
   повтора (`orchestrator/fsm_merge_gate.py:320-338`): запись `flake-rate`
   «повтор не запущен: …», выход «merge отклонён: <статус> … задача осталась
   на гейте merge», задача на `merge_gate`. Чтения статуса CI на этом пути
   (`ci.branch_status` → `gh api …/check-runs`, `orchestrator/ci.py:257-282`,
   `orchestrator/fsm_merge_gate.py:316`, `:372`) остаются: модуль гейта
   только для чтения, без них нет и красного статуса; запрет — на вызовы
   `gh` из самого `trigger_rerun` (поиск прогона, `run rerun`, `run watch`).
   Команда Оператора `ci-rerun` для такого проекта отказывает текстом,
   начинающимся с «ре-ран CI не запущен: », не вызвав `gh` ни разу. Сейчас
   `gh` зовётся до `trigger_rerun` на каждом пути команды: чтение статуса
   `ci.verifying_status` (`orchestrator/ci_rerun.py:156`) — до проверки
   состояния `verifying` (`:158-162`), затем `ci.check_run_workflow_run` на
   пути зависшей проверки (`:223`), `ci.failed_check_names` на красном пути
   (`:274`, `:289`); `ci.head_sha` на `:250` читает голову через git, а не
   через `gh` (`orchestrator/ci.py:237-254`). Поэтому отказ проекта людей
   стоит после проверок `--reason` (`:136-151`, они `gh` не зовут) и до
   чтения статуса на `:156`, в любом состоянии задачи: для задачи проекта
   людей вне `verifying` прежний отказ «задача в состоянии …, а повтор CI
   допустим только в verifying; статус CI ветки …» сменяется этим отказом.
   Для артели и записей `operator` (в том числе GitHub) поведение команды и
   гейта прежнее.
8. **`ci_required_jobs` только у хостинга, который его читает.** Запись
   проекта людей (`targets.merged_by_project_people`) с заданным
   `policy.ci_required_jobs`, у которой реализация хостинга в реестре
   `forge` это поле не читает, отказывает при загрузке с именем поля и
   хостинга. Признак реализации (по образцу `_check_full_suite_source`,
   `orchestrator/targets.py:1137-1160`) — атрибут модуля или класса
   реализации `READS_CI_REQUIRED_JOBS`: у `gitlab_adapter` — `True`, у
   `_GitHub` его нет или `False`. Решение —
   `getattr(_hosting_registry().get(hosting), "READS_CI_REQUIRED_JOBS",
   False)` по реестру `forge.IMPLEMENTATIONS` (`orchestrator/forge.py:365`,
   через `targets._hosting_registry`, `orchestrator/targets.py:1163-1170`),
   не литерал хостинга и не `CI_BY_PIPELINE`. GitLab и записи `operator`
   (в том числе `github` + `operator`) — без изменений. Исход для пустого
   списка `ci_required_jobs: []` не закрепляется.
9. **`kill` не закрывает PR проекта людей.** Для записи с
   `targets.merged_by_project_people` уборка не зовёт `gh pr close` ни до,
   ни после отправки ветки; до отправки удаляется только ветка origin
   задачи, если она есть. Для записи хостинга без конвейеров
   (`not forge.ci_by_pipeline`, у которой до отправки прежде закрывался бы
   PR) запись журнала уборки содержит «PR не тронут: MR вливают люди
   проекта» и до отправки, и после неё: до отправки — рядом с исходом
   удаления ветки origin; после отправки — в дополнение к прежнему тексту
   «сервер проекта не тронут: ветка <ветка> отправлена, MR вливают люди
   проекта — ветка origin и MR оставлены (…)» (`orchestrator/cleanup.py:297-299`),
   который остаётся. Для GitLab `target-human` записи журнала до и после
   отправки прежние (без «PR не тронут»). Для `github` + `operator`
   закрытие PR прежнее.
10. **Правка трёх существующих файлов тестов — только в объёме мандата
    `ANSWER-1.md`.** В `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`,
    `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py`,
    `tests/test_epic_draft_promote_unsupported_project.py` параметр
    `github` + `target-human` переходит из отказных случаев в поддержанные,
    утверждения состава констант поддержки и тексты причин — к новому
    перечню пар «github + operator, github + target-human, gitlab +
    target-human». Число случаев `gitlab` + `operator` не уменьшается, вид
    их утверждений — как на main: равенство там, где на main равенство
    (`unsupported_reason`, константы поддержки, `test_ac3_*_reason_exact`,
    случай `gitlab-operator` в
    `test_ac4_reason_text_names_pair_and_supported_list`), вхождение
    полного текста причины в вывод там, где на main вхождение (действия
    `new`, `run`, `auto`, `approve`, `epic draft promote`, строка
    `project-support` — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:200`,
    `:231`, `:259`, `:291`, `:314`, `:391`,
    `tests/test_epic_draft_promote_unsupported_project.py:87`,
    `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:131`); удаление случаев `gitlab` +
    `operator`, `skip`/`xfail` и иные правки этих и прочих существующих
    тестов не делаются. Поддержанные случаи `run`, `auto`, `approve` не
    доходят до настоящего `gh` (подделка `ci.gh` или ранний `Halt` после
    проверки поддержки).

## Критерии приёмки

AC-1. (Условие-замена (б) мандата.) Для вымышленного проекта `github` +
`target-human` `targets.unsupported_reason` возвращает `None`; `new`, `run`,
`auto`, `approve` и `epic draft promote` не отказывают причиной поддержки;
строка `doctor` `project-support-<проект>` — `ok`. Ни один случай не вызывает
настоящий `gh`: `ci.gh` подменён подделкой или действие останавливается
ранним `Halt` после проверки поддержки. Ни один случай не вызывает сетевую
команду git (`clone`, `fetch`, `push`, `ls-remote`) по адресу записи: клон
проекта подготовлен заранее (образец —
`tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:176`), `origin` —
локальный голый репозиторий, или действие останавливается ранним `Halt` до
клона; шпион git не видит сетевых команд с адресом `http(s)://`.

AC-2. (Условие-замена (а) мандата.) Для вымышленного проекта `gitlab` +
`operator` `new`, `run`, `auto`, `approve` и `epic draft promote` отказывают,
строка `project-support-<проект>` — `fail`. `targets.unsupported_reason`
равен точно «гейт мержа operator не поддержан для хостинга gitlab
(поддержаны: github + operator, github + target-human, gitlab +
target-human)»; вывод каждого действия и причина строки `project-support`
содержат этот текст целиком.

AC-3. Каждый отказ `_check_delivery` из перечня полей (`branch_template`,
`ref_pattern`, `squash_before_mr`, `freshness`, `commit_template`,
`commit_author`, `co_author`, `push_options`, `push_options_forbidden`,
`ci_required_jobs`, `mr_assignee`, `draft_mr`, `max_in_flight`,
`max_awaiting`, `awaiting_holds_zones`, `mr_sync_interval_min`) даёт для
записи `github` + `target-human` тот же текст, что для `gitlab` +
`target-human` — один тест, параметризованный по обоим хостингам (зелёный с
рождения: закрепление). Запись GitHub `target-human` с компонентом
`full_suite: ci` отказывает при загрузке.

AC-4. Для записи GitHub `target-human` строка
`project-ci-file-no-paths-<проект>` есть без компонента с `full_suite`
ci/both; при `no_paths` с `.github/workflows/`, с `.github/`, с `.github`
(без `/`), с `**/workflows/` или с `**/.github/` — `ok`; без подходящей
записи, с маской `.github/*`, с `**/`, с `**/ci.yml`, `**/x`, `**/a`,
`**/main.yml`, с `.github/workflows/c`, `.github/workflows/ci.yml`,
`.github/workflows/x`, `.github/workflows/a` — `fail`, в причине названо
имя каталога `.github/workflows/`. Для записи GitLab `target-human`
— прежние условие построения строки и исходы по `.gitlab-ci.yml`.

AC-5. Для записи GitHub `target-human` в выводе `doctor` есть строки
`project-submodules-<проект>` и строки хука `pre-push`; строк
`project-ci-reruns-<проект>-…` и строки срока токена (`token-expiry`) нет.

AC-6. Полный цикл требования 5 в песочнице проходит до `done`; шпион `ci.gh`
не видит ни одного вызова `pr merge`, `pr close`, `pr comment`, `run rerun`,
`run watch`; шпион git не видит отправки в `base` и в ветку задачи после
входа в `awaiting_human`; `kill` такой задачи после отправки оставляет ветку
origin и PR, `gh pr close` не вызван.

AC-7. Прямой вызов `ci.trigger_rerun` для клона проекта `github` +
`target-human` (с `run_id` и без него) возвращает текст, начинающийся с
«ре-ран CI не запущен: », а шпион `ci.gh` не видит ни одного вызова. Красный
CI ветки такой задачи на `approve` `merge_gate` (подделка `ci.gh` отвечает
на `api`-чтения статуса красным): шпион не видит вызовов `run rerun` и
`run watch`, в журнале запись `flake-rate` с «повтор не запущен», выход
содержит «merge отклонён: », задача остаётся на `merge_gate`. `ci-rerun`
такой задачи с непустым новым `--reason` — и в `verifying` при красном
и при зависшем CI, и в состоянии не `verifying` — отказывает текстом,
содержащим «ре-ран CI не запущен: », шпион `ci.gh` не видит ни одного
вызова. У задачи `github` + `operator` (подделка `ci.gh`) — прежний вызов
`gh run rerun <id> --failed`.

AC-8. Запись `github` + `target-human` с `policy.ci_required_jobs` отказывает
при загрузке; текст отказа называет поле `ci_required_jobs` и хостинг
`github`. Та же запись с `forge: gitlab` и запись `github` + `operator` с
этим полем загружаются. Признак, не литерал и не `CI_BY_PIPELINE`: в
`forge.IMPLEMENTATIONS["github"]` подставлен подкласс `_GitHub` с
`READS_CI_REQUIRED_JOBS = True` (`CI_BY_PIPELINE` прежний, `False`) —
запись `github` + `target-human` с непустым `policy.ci_required_jobs`
загружается; в `IMPLEMENTATIONS["gitlab"]` подставлено пространство имён с
атрибутами `gitlab_adapter`, но `READS_CI_REQUIRED_JOBS = False`
(`CI_BY_PIPELINE = True`) — запись `gitlab` + `target-human` с этим полем
отказывает при загрузке с именем поля и хостинга. Подстановка — во
временной песочнице `config` теста, настоящие файлы не меняются. Исход для
пустого списка `[]` не закрепляется.

AC-9. `kill` задачи `github` + `target-human` до отправки ветки и после неё:
`gh pr close` не вызван, запись журнала «уборка» содержит «PR не тронут: MR
вливают люди проекта»; до отправки ветка origin задачи, если она есть,
удалена; после отправки ветка origin цела, а запись журнала содержит и
прежний текст «сервер проекта не тронут: ветка <ветка> отправлена».
`kill` задачи `github` + `operator` вызывает `gh pr close`, как сейчас.

AC-10. `kill` задачи `gitlab` + `target-human` до отправки ветки и после
неё: записи журнала уборки прежние (без «PR не тронут»), `gh` не вызван.

AC-11. Закрытый список вызовов `gh` части 1 (`forge._github_form_allowed`):
форма `pr create` с лишним аргументом после разрешённого хвоста —
отказ без вызова `gh` (закрепление, зелёный с рождения; мутация
`return rest == []` → `return True` этот тест краснит).

AC-12. Сторож литералов `forge`/`merge_gate` вне `orchestrator/targets.py`
(`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:425-488`)
зелёный; прежние тесты `github` + `operator`, `gitlab` + `target-human`,
`mr-sync`, точки отправки и хука, а также
`tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py`,
`tests/test_awaiting_human_units.py`, `tests/test_gitcmd_push_point.py`,
`tests/test_push_hook_stand.py`, `tests/test_mr_delivery_units.py` — зелёные
без правки.

AC-13. Дифф трёх файлов мандата (требование 10) против main: число случаев
`gitlab` + `operator` в каждом файле не меньше, чем на main; в каждом
действии (`new`, `run`, `auto`, `approve`, `epic draft promote`, строка
`project-support`) для `gitlab` + `operator` утверждается вхождение
полного текста причины в вывод — тот же вид утверждения, что на main
(`assert reason in out`/`in found[0].detail`, `check_refusal`). В
`tests/test_epic_draft_promote_unsupported_project.py` вид проверки
причины остаётся как на main: `reason = targets.unsupported_reason(name)`,
`assert reason`, `assert reason in out` (`:72-73`, `:87`); новая константа
текста причины в этом файле не вводится, правка файла — только перенос
параметра `target-human` (точный текст причины `gitlab` + `operator`
держат равенства AC-2 в двух других файлах мандата). В двух других
файлах вхождение — константой нового текста целиком; `test_ac3_*_reason_exact`,
`test_ac4_support_constants_exact`,
`test_ac4_reason_text_names_pair_and_supported_list` (случай
`gitlab-operator`: `reason == expected`) и утверждения констант поддержки
`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:172-174`
сравнивают равенством с новым составом и новым текстом; ни одно
утверждение случаев `gitlab` + `operator` не сменило вид на более слабый;
новых `skip`/`xfail` нет.

## Оценка объёма и деление

Сработавшие сигналы: 13 критериев приёмки (≥ 10); 7 файлов зоны вне общих
(`orchestrator/targets.py`, `orchestrator/forge.py`,
`orchestrator/gitlab_adapter.py`, `orchestrator/doctor/project_checks.py`,
`orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/cleanup.py`)
плюс `docs/codebase-map.md` и `tests/` (≥ 5); `budget_usd` $85 (≥ $30).

**Обоснование монолита.** Открытие пары (требование 1) и запреты проекта
людей (требования 7–9) — одна смена механики: запреты без открытия пары
недостижимы в живом пути (пара закрыта отказом поддержки), открытие без них
небезопасно — пульт повторял бы CI (`gh run rerun`) и закрывал бы PR в
проекте людей, а поле `ci_required_jobs` записи GitHub грузилось бы без
гарантии. Естественная граница (1–6 против 7–9) режет
`orchestrator/targets.py` поперёк (`SUPPORTED_PAIRS` и отказ
`ci_required_jobs`). Оператор выбрал монолит с рамкой $85 в `ANSWER-1.md`
(вопрос 2, вариант B); строку утверждения на гейте вписывает Оператор.

## Не входит

- Пара `gitlab` + `operator` (остаётся неподдержанной).
- `token_user`, `token_expiry`, `protections`, `project_info` для GitHub и
  строки `doctor` по ним (сверка автора для GitHub остаётся отложенной,
  строки срока токена нет).
- Разбор файлов `.github/workflows/` (аналог `project-ci-reruns` и
  `check_workflow_rules`).
- Проверка `policy.push_options` на совместимость с GitHub (`git push -o`),
  доступность черновых PR на тарифе, сверка автора для GitHub.
- Реализация `ci_required_jobs` для GitHub.
- Файлы `.github/` репозитория артели не меняются: `.github/workflows/`,
  `.github/` в требовании 3 и критериях — значения `no_paths` записи
  вымышленного проекта в песочнице теста.
- Правка ADR-0029 и `docs/invariants.md` (операторские коммиты).
- Проба полного цикла на живом проекте GitHub — после мержа, Оператором.
- Правка модулей только для чтения: `orchestrator/github_adapter.py`,
  `orchestrator/fsm_merge_gate.py`, `orchestrator/mr_sync.py`,
  `orchestrator/gitcmd.py`, `orchestrator/project_profile.py`,
  `orchestrator/repo_context.py`, `orchestrator/fsm_advance.py`,
  `orchestrator/catalog.py`, `orchestrator/runner.py`,
  `orchestrator/doctor/cli.py`, `orchestrator/doctor/misc_checks.py`,
  `orchestrator/doctor/git_hooks.py`, `orchestrator/config.py`,
  `scripts/git-hooks/target-human/pre-push`.
- Расхождение `project_profile.mask_matches` (маска `*` у проверки GitLab) с
  формулой гейта `config.is_protected_path` — строка копилки, не правка.
- Полный зелёный набор `tests/` и CI ветки — их держит пульт.

## Материалы

- `tasks/01M6N7CYKDAMAKENX60CBK7VQX/TZ.md` — факты 1–13 с адресами.
- `tasks/01M6N7CYKDAMAKENX60CBK7VQX/ANSWER-1.md` — мандат «Ослабление тестов
  разрешено» на три файла и матрица неослабления (условия — требование 10,
  AC-1, AC-2, AC-13); решение «монолит, $85».
- Записки разработчику (решение 4 Оператора на гейте SPEC 05.11; проверку
  тестов не меняют): `ci.head_sha` читает голову через git, а не через `gh`
  (`orchestrator/ci.py:237-254`); `branch_status` —
  `orchestrator/ci.py:1206`; в `orchestrator/cleanup.py` условие закрытия
  PR лучше строить по признаку реализации (`forge.ci_by_pipeline`), а не
  литералом `_forge_of(target) == "github"` (`:311-312`), хотя литерал
  допущен исключением сторожа; сеть вне машины перехвачена песочницей
  (`tests/sandbox.py:996-1010`), но адреса `https://localhost`/`127.0.0.1`
  и имена remote идут в настоящий git (`tests/sandbox.py:951`,
  `:964-969`) — записи файлов мандата несут `url:
  https://localhost/team/<имя>`, отсюда условие AC-1 о сетевом git.
- Записки разработчику и ревьюверу (решение 2 Оператора на гейте SPEC
  05.11, вид (б); проверку тестов не меняют): AC-4 — надёжная формула
  проверки каталога: имя файла длиннее всех записей `no_paths`, первый
  символ которого не совпадает ни с одним символом сразу после
  `.github/workflows/` в записях с этим началом, затем
  `config.is_protected_path(".github/workflows/" + имя, no_paths)`; проба
  одним фиксированным именем (например `ci.yml`) ошибается на записях
  перечня `fail` — замечание ревью. AC-8 — подстановка реализаций —
  подмена `forge.IMPLEMENTATIONS` на время теста
  (`targets._hosting_registry`, `orchestrator/targets.py:1163-1170`, читает
  его в момент вызова).
- Безопасность тестов (ТЗ): ни настоящего GitHub, ни настоящего `gh` —
  подделка `ci.gh`; связка ключей не читается; проекты вымышленные во
  временной песочнице `config`, `origin` — локальный голый репозиторий;
  никогда — настоящий клон и настоящий локальный слой; в текстах тестов —
  ни имён, ни адресов реальных проектов.
