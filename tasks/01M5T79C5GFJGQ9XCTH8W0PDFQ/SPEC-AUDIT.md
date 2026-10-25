---
task: 01M5T79C5GFJGQ9XCTH8W0PDFQ
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py, tests/test_01m4s24963r9h18an2xdp6r15b_cache.py, tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py, tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py, tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py, tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py, tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py, tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py, tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py, tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py, tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py, tests/test_invariants.py, tests/test_outcome_gate_module.py, tests/test_report_outcome_module.py; в) пути-признаки (гейты): orchestrator/advance_gates/outcome_integrity.py; в) защищённые пути: tests/test_invariants.py."
spec_sha: 8fef23630a6b75911e6340098dba7ed03bfd9c37
schema_version: 5
---

# SPEC-AUDIT: Скорость пульта, git 3: чтения git из клона и рабочей копии — через gitcmd

## ТЗ и SPEC
Требования ТЗ 1–5 и четыре критерия приёмки ТЗ перенесены в SPEC: это требования 1–5 и AC-1…AC-9. Списки «Не входит» и «Только чтение» совпадают с ТЗ. ANSWER-n нет.

Решение Оператора на гейте SPEC №1 (шесть пунктов) отражено, как и при прошлом аудите: требование 4 и AC-9 (п. 1), требование 1, AC-2 (п. 2), требование 2 (п. 3), требование 3 и AC-8 (п. 4), «Контекст» п. 4, AC-4 и AC-8 (п. 5), AC-1 (п. 6).

Решение Оператора на гейте SPEC №2 отражено полностью:
- (1) AC-4 у места 1: «процесс git по истечении срока остановлен (`kill` и дочитывание вывода)», тест ловит мутацию «отказ по сроку без `kill`». Требование 2 называет то же для равноценной функции места 1.
- (2) AC-7 у места 1: `cwd` = `config.ROOT`, отсутствующий каталог даёт исход AC-8. Требование 3 называет тот же `cwd`.
- (3) Подмена `mock.patch.object(acceptance, "subprocess", fake)` названа в требовании 4 сведением разработчику без отдельного AC, все 10 мест перечислены, требуется назвать их в PLAN.

Сверх ТЗ и решений в SPEC ничего не добавлено. Требований ТЗ, потерянных в SPEC, нет. Решения Оператора между собой не расходятся.

## Факты против кода
Код сверен на 1f02aff4 (рабочий каталог шага). С прошлого аудита код не менялся, утверждения «Контекста» о местах 1–7 подтверждены прежде и перепроверены у места 1:
- Место 1 — `orchestrator/acceptance.py:2943-2954`: `Popen(["git","-C",str(root),*args], cwd=config.ROOT, env=gitcmd.pult_env(env), …, text=True)` вне `try` (`OSError` выходит наружу); `communicate(timeout=15)`; по `TimeoutExpired` — `process.kill()` и `process.communicate()` (`:2951-2952`), затем `None`. `GIT_INDEX_FILE` — `:2931`.
- Места 2–7: `brief.py:543-560`, `reference_cache.py:294-309`, `:347-399`, `:402-418`, `tz_check.py:147-154`, `outcome_integrity.py:576-589` — сроки, тексты отказов и исходы `OSError` совпадают с «Контекстом», AC-4, AC-8.
- Перечень подмен модуля целиком в требовании 4 полон: `grep 'patch.object(acceptance, "subprocess"' tests/` даёт ровно 10 мест, совпадающих с SPEC (`own_run_path.py:250`, `profile_callers.py:727`, `pult_pytest_unchanged.py:264`, `suite_durations.py:732`, `launch_places.py:213`, `test_report_outcome_module.py:1187`, `:1211`, `:1336`, `:1344`, `pytest_own_places.py:858`).
- Утверждение SPEC о `PytestSpy` верно: `tests/test_report_outcome_module.py:76-87` — не-pytest argv уходит в настоящие `REAL_RUN`/`REAL_POPEN`.
- Прочие подмены `acceptance.subprocess.run` (`test_acceptance.py:99`, `test_suite_run.py:350`, `test_full_suite_profile_timeout.py:84` и др.) подменяют атрибут глобального модуля `subprocess`: место 1 идёт через `Popen`, после переноса в `gitcmd` — через тот же глобальный `subprocess.Popen`, видимость не меняется.
- Других подмен атрибута `subprocess` у `reference_cache`/`brief`/`tz_check` в `tests/` нет; у `outcome_integrity` — только `test_outcome_gate_module.py:2525` (названа в SPEC).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | Место оставлено на `subprocess.*` или переведено на `acceptance._launch`/`_run_capture`: шпион функции `gitcmd` не вызван, шпион `Popen` видит запуск git мимо неё. |
| AC-2 | да | Любое место возвращено на прямой `subprocess.run`/`Popen` (в том числе место 7 с argv в переменной). Сторож, запрещающий сам импорт, красен на `outcome_integrity.py`. |
| AC-3 | да | Места 2/3/5 уведены с глобального `subprocess.run` (`external_brief.py:236-250`); удалён импорт `subprocess` в `outcome_integrity.py` (`test_outcome_gate_module.py:2525`); первый параметр новой функции `gitcmd` назван не по `_FIRST_ARG_REPO_NAMES` (`explicit_repo.py:63`, `:208`). |
| AC-4 | да | Пропущен `TimeoutExpired`; у места 4 `TimeoutExpired` при запуске сведён к `DEADLINE`; изменён текст причины; у места 1 отказ по сроку без `kill`. |
| AC-5 | да | 15 заменено другим значением; срок по умолчанию из `gitcmd` вместо константы; полный срок вместо остатка; срок появился у мест 6–7. |
| AC-6 | да | Вывод читается целиком, предел проверяется после чтения; процесс не убит при переборе; код возврата проверяется раньше предела. |
| AC-7 | да | Пропал `-C`, пропал маркер `pult_env` или `GIT_INDEX_FILE`, у места 1 сменён `cwd`, текст вместо байт, лишний процесс git. |
| AC-8 | да | Место 1 глотает `OSError`; места 2/3 теряют имя исключения; место 6 отдаёт не 127; место 7 теряет текст `_Prepare`. |
| AC-9 | да | Место 1 или 4 перешло на `subprocess.run` (под `SpyRun` `write-tree` получает фейковый sha); место 2/3/5/6/7 ушло на `Popen` или на `gitcmd.git`/`in_repo`. |

## Зоны
- Зоны SPEC — `gitcmd.py`, пять модулей и `tests/` — покрывают все требования; `docs/codebase-map.md` входит в `config.COMMON_ZONES` (`config.py:821`).
- Защищённый `tests/test_invariants.py` лежит внутри зоны `tests/`, но SPEC ставит его в «Только чтение», требование 5 и AC-2 запрещают правку. Приложение PLAN не нужно.
- `tests/sandbox.py` только читается. Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Путь запуска мест 1–7 | Число процессов git: `test_01m4s24963r9h18an2xdp6r15b_cache.py:296`, `test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py:547` | да | Те же тесты (AC-3), AC-7 | ок |
| Срок мест 1–5 и остановка процесса | `cache.py:510`, `:971`; `acceptance.py:2949-2952` | да | AC-4, AC-5 | ок |
| Предел вывода `ls-tree` | `reference_cache.py:388-392`; `cache.py:482` | да | AC-6 | ок |
| Изоляция тестов от боевого `ROOT` | `SpyRun`/`fake_git` (`sandbox.py:1682`, `:2173`) | да | AC-9 | ок |
| Явный репозиторий у примитивов `gitcmd` | `test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py:208` | да | AC-3 | ок |
| Инвариант 33 | `tests/test_invariants.py:1879` | да, не трогается | Сам тест | ок |
| `OSError` и `cwd` места 1 | `acceptance.py:2944-2945` | да | AC-7, AC-8 | ок |
| Исход 10 тестов под подменой `acceptance.subprocess` | сами тесты (требование 4) | да (по коду) | сами тесты, полный набор | ок, сведение разработчику |

Раздела «Меняемое поведение» в SPEC нет, и это верно: ожидания существующих тестов не меняются.

## Пути обхода гейтов
1. Альтернатива AC-9 «доказательство в PLAN по коду» для подмен `gitcmd.git`/`in_repo`/`show`/`ls_tree_files` тестом не проверяется. Её допускает ТЗ (требование 4), это не отклонение; ревью сверяет доказательство с кодом.
2. Сведение о 10 тестах под подменой `acceptance.subprocess` — без AC по решению Оператора №2; исход держит полный набор `tests/`.

Других путей не нашёл.

## Вердикт
**pass.** Отклонений нет: оба решения Оператора на гейте SPEC внесены, факты о коде подтверждены (`orchestrator/acceptance.py:2943-2954`, перечень подмен `tests/…` совпадает с требованием 4), каждый AC ловит правдоподобную мутацию.

Замечание без отклонения: «Материалы» SPEC ссылаются на `SPEC-AUDIT.md`, «Вердикт» пп. 1–6 — этот аудит перезаписывает файл, пункты 1–6 там теперь из решения Оператора №1 (журнал гейта), не из текущего вердикта.
