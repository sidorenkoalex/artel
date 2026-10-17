---
task: 01M545EDTHS47HSB59AKC1EZ9C
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_doctor.py; в) пути-признаки (песочница ролей): orchestrator/runner.py; в) защищённые пути: skills/; г) budget_usd 45 ≥ 45"
spec_sha: ca8e0a7fd600a4ed9970788df46a119a47b52767
schema_version: 5
---

# SPEC-AUDIT: D2-2 — токен хостинга внешнего проекта и проверки doctor

Проверен SPEC sha ca8e0a7f (сверено `git hash-object` файла каталога
документов). ANSWER-n.md у задачи нет. Решения Оператора на гейте SPEC
№1–№3 — по содержанию.

## ТЗ и SPEC
- ТЗ п.1 → требования 1–4, 8; ТЗ п.2.1–2.7 → требование 5.1–5.7; «для
  артели неприменимо» → требование 6; ТЗ п.3 → требование 7; ТЗ п.4 →
  требование 9; «Не входит» ТЗ перенесено. Потерь нет.
- Решение №3 внесено полностью: П-1 — требование 9, последний пункт;
  А-1 — требование 9 («ни один тест не читает настоящую связку ключей»,
  `tests/test_doctor.py:670-692`, `token_slot` из `entry`); В-1 — AC-7,
  последнее предложение, и AC-8 5.2; Ф-1 — требование 5.6 и AC-8 5.6;
  В-2 — AC-2; запись без `token_slot` в процессе роли — требование 7 и
  AC-10. Решения №1 и №2 — как и в прошлом визите, на месте.
- Сверх ТЗ: warn «нет токена проекта» (5.5), исключение `-C
  .artel/projects/<имя>`, признак URL push, перечень подкоманд remote —
  все из решений Оператора №1–№2. Новых требований без источника нет.

## Факты против кода
Подтвердилось:
- `orchestrator/github_adapter.py:168`, `:193`, `:306` — три вызова
  `ci.gh` с `**gh_repo_kwargs`; `ci.gh(repo=)` — URL форджа
  (`orchestrator/ci.py:38-67`), вызов без `env=`, cwd `config.ROOT`.
- `orchestrator/doctor/misc_checks.py:91-94` — прямой
  `subprocess.run(["gh", "repo", "view", entry["url"], …])` без `env`.
- `orchestrator/doctor/artifact_branches.py:126-146` —
  `_push_closing_sha`, push по URL на `:137`; `:171-174` — главная копия
  источником только при `repo_context.is_artel`.
- `orchestrator/ci.py:1148`, `:1207`, `:1240` (а также `:1248`, `:1253`
  того же `trigger_rerun`) — без `repo=`; `verifying_status` `:586`,
  `trigger_rerun` `:1221`.
- `orchestrator/runner.py:1116-1130` `in_role_environment`,
  `:1133-1141` `_is_role_home` (Материалы SPEC называют 1116-1133,
  требование 9 — 1132-1141; обе ссылки в пределах функций).
- `orchestrator/suite_run.py:781-782` снимает только `ARTEL_ROLE`, `HOME`
  остаётся.
- `tests/sandbox.py:1057-1065` `_PROJECT_TARGET_ENTRY` с `token_slot`.
- `tests/test_doctor.py:629-692` `BaseBranchCheckTest`, `EXTERNAL_ENTRY`
  без `token_slot` — с правилом «`token_slot` из `entry`» тест остаётся
  на прежней авторизации и keychain не читает.
- `orchestrator/brief.py:593` `project_skills_refusal`;
  `orchestrator/repo_context.py:75` `clone_path`; `config.py:50`
  `PROJECTS`, `:63` `ROLE_HOME`, `:799` `COMMON_ZONES` (с `config.py`).
- Хостинговые git-вызовы пульта идут через `gitcmd.in_repo` →
  `git("-C", …)` (`orchestrator/gitcmd.py:232-243`) либо `git(…)` в
  `config.ROOT`; прямые `["git", …]` вне gitcmd
  (`acceptance.py:1783`, `reference_cache.py`, `checkpoint.py:1799`) —
  локальные; `canary.py:1182-1201` — клон пула, вне задачи.

Не учтено SPEC (на формулировку требования 9 влияет, см. П-2):
- `tests/sandbox.py:1693` — `TmpRootTest` уже подменяет
  `config.ROLE_HOME` на каталог песочницы, поэтому признак по `HOME` в
  тестах песочницы сегодня и так ложен; `ARTEL_ROLE` песочница не
  снимает (`grep ARTEL_ROLE tests/sandbox.py` — пусто).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | подстановка токена/`-c credential.helper` для артели или путей под `config.ROOT` вне `PROJECTS` |
| AC-2 | да | один из трёх вызовов `github_adapter` идёт без `GH_TOKEN` |
| AC-3 | да | нет пустого `credential.helper` перед помощником пульта; запись помощника в `.git/config` клона |
| AC-4 | да | пустой слот — молчаливый проход или отказ без имени слота |
| AC-5 | да | токен в argv (`-c credential.helper=!echo <токен>`), в stderr отказа, в журнале шагов, в `role_env` |
| AC-6 | да | 5.7 не вызывает `project_skills_refusal` или даёт warn вместо fail |
| AC-7 | да | `FETCH_HEAD` после fetch; fail вместо warn при отсутствии `FETCH_HEAD`; fetch doctor мимо механизма токена |
| AC-8 | да | одна из трёх форм `on:` не распознана; 5.6 fail вместо warn; маска не раскрыта; 5.4 fail вместо «недоступно»; печать значения токена |
| AC-9 | да | молчаливый пропуск проверок п.5 у артели |
| AC-10 | да | чтение слота до проверки признака роли; признак только по `ARTEL_ROLE`; запись без `token_slot` в роли проходит |
| AC-11 | да | признак проекта только по `-C` — push из источника вне `PROJECTS` идёт без токена |
| AC-12 | да | токен для локальных подкоманд; `-C .artel/projects/<имя>` под механизмом; `push --delete`/`ls-remote` вне перечня |
| AC-13 | да | признак URL push не действует под `config.ROOT` |
| AC-14 | да | `check_base_branch` без `GH_TOKEN` |
| AC-15 | да | запись без `token_slot` отказывает или получает подстановку |
| AC-16 | да | подмена не общая (только в отдельных классах) или вызывает `security` |

Замечание к AC-10 и `BaseBranchCheckTest` — П-2 ниже.

## Зоны
- Зоны SPEC: `gitcmd.py`, `ci.py`, `github_adapter.py`, `repo_context.py`,
  `projects.py`, `doctor/`, `tests/`; константа порога 5.1 — в
  `orchestrator/config.py`, общая зона (`config.py:799`). Хватает.
- Механизму в `gitcmd.git` нужно чтение `targets.yaml` (модуль
  `orchestrator/targets.py` — только импорт, не правка) и `keychain.token`
  (только вызов) — правка вне зон не требуется.
- `orchestrator/runner.py` (сигнал песочницы ролей) — только читается
  (`in_role_environment`); окружение роли не расширяется, требование 3
  запрещает токен в нём.
- Защищённые пути: `skills/` только читается (5.7); `tests/test_invariants.py`
  и `**/conftest.py` требования менять не заставляют. Приложений PLAN не
  нужно.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| окружение `gitcmd.git` для хостинговых подкоманд | артель: argv/env как на main (`gitcmd.py:32-46`) | да | AC-1, AC-12 | остаётся |
| окружение `ci.gh` (`GH_TOKEN`) | вызовы без `repo=` на авторизации Оператора (`ci.py:58-61`) | да | AC-1, «Не входит» | остаётся |
| `check_base_branch` | `tests/test_doctor.py:629-692` | да, без правки утверждений (требование 9) | тот же тест; см. П-2 | остаётся |
| общая подмена `keychain.token` в `tests/sandbox.py` | локальные подмены `mock.patch.object(runner.keychain, "token", …)` (`tests/test_doctor.py:136`, `:258`, `:313`; `tests/test_invariants.py:274`) | да — локальная подмена поверх общей сильнее | AC-16 | остаётся |
| песочница снимает `ARTEL_ROLE` / подменяет `HOME` | сторож `conftest.py:72` читает `ARTEL_ROLE` процесса pytest | да, если снятие — в окружении теста, не в `os.environ` до сбора | не покрыто явно (см. Е-1) | вопрос формы реализации |

Раздела «Меняемое поведение» в SPEC нет; смены ожиданий существующих
тестов требования не задают (требование 4, требование 9 о
`test_doctor.py:670-692`) — раздел не нужен.

## Пути обхода гейтов
- Е-1 (мягкое). Требование 9 «песочница снимает `ARTEL_ROLE`» можно
  выполнить снятием переменной из `os.environ` на импорте
  `tests/sandbox.py` — это гасило бы и сторож `conftest.py:72`, если тот
  читает окружение позже импорта, и признак роли для всего процесса
  pytest. SPEC не говорит, что снятие — в рамке теста (setUp/cleanup).
  Ловится ревью; отмечено как уточнение формы.
- Иных путей буквального выполнения в обход смысла не нашёл: AC-5 требует
  отсутствия токена в argv помощника, AC-3/AC-11 — проверки `git
  credential fill` при конкурирующих помощниках, AC-10 — невызов подмены
  слота.

## Вердикт
concerns — отклонения мелкие, решаемы на гейте без возврата аналитику:

1. П-2. Охват нейтрализации признака роли (требование 9, последний
   пункт; AC-10). Требование говорит о песочнице `tests/sandbox.py`, а
   `BaseBranchCheckTest` (`tests/test_doctor.py:629`) — plain
   `unittest.TestCase` вне песочницы: при прогоне, запущенном процессом
   роли, `HOME` = настоящий `config.ROLE_HOME`
   (`orchestrator/suite_run.py:781-782` снимает только `ARTEL_ROLE`), и по
   требованию 7 `check_base_branch("sled", …)` для записи без
   `token_slot` отказал бы — `test_matching_base_branch_is_ok`
   (`tests/test_doctor.py:670-680`) покраснел бы вопреки требованию 9.
   Нужно уточнить: нейтрализация — процессная для `tests/` либо
   `BaseBranchCheckTest` переводится на песочницу (правка setUp, не
   утверждений). Дополнительно: `TmpRootTest` уже подменяет
   `config.ROLE_HOME` (`tests/sandbox.py:1693`), так что «подменяет HOME»
   в песочнице избыточно, а снятие `ARTEL_ROLE` — нет (Е-1).
2. Ф-2. «`token_slot` механизм требования 1 берёт из записи `entry`,
   переданной вызывающим» (требование 9) — у `gitcmd.git` (сигнатура не
   меняется, требование 1) и `ci.gh(repo=<URL>)`
   (`orchestrator/ci.py:38`) записи от вызывающего нет: механизм там
   читает `targets.yaml` по имени проекта из пути `-C` / по URL. SPEC
   стоит сузить правило до вызовов с `entry` (`check_base_branch`,
   проверки doctor п.5), иначе оно читается как запрет чтения
   `targets.yaml` механизмом.
3. Р-1. Исход `check_base_branch` и 5.4 в процессе роли не назван:
   требование 7 пропускает «только в сессии Оператора» лишь 5.1, 5.2, 5.5,
   а `gh` в `check_base_branch` (`orchestrator/doctor/misc_checks.py:91`)
   — хостинговая операция и получит именованный отказ; 5.4 даст
   «недоступно» (не fail), а исход строки `base-branch` (сегодня отказ
   `gh` → `skip`, `misc_checks.py:97-99`) — не определён (skip или fail).
   Дефолт: skip с текстом отказа.
