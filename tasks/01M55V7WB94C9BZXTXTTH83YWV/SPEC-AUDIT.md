---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/; в) пути-признаки (гейты): orchestrator/advance_gates/, orchestrator/fsm_advance.py, orchestrator/fsm_autogate.py, orchestrator/fsm_merge_gate.py
spec_sha: f5f0ffa5c93253130f0db1eaff86fc86b1cdaa95
schema_version: 5
---

# SPEC-AUDIT: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## ТЗ и SPEC
ANSWER-n и решений Оператора на гейте SPEC в брифе нет.

ТЗ → SPEC:
- ТЗ п.1 (GH_REPO для `gh api`, `--repo` для `gh run`/`gh pr`, токен слота;
  артель без изменений) → SPEC требования 1–2. Есть.
- ТЗ п.2 (перечень функций и вызывающих по `ci.py`, `ci_rerun.py`,
  `acceptance.py`, `fsm_merge_gate.py`, `advance_gates/`) → SPEC требование 3.
  Есть, перечень полный (сверка ниже).
- ТЗ п.3 (зафиксировать тестами вызовы артели до правки) → требование 4, AC-1.
  Есть, но AC-1 уже перечня (отклонение 2).
- ТЗ п.4 (подставной `gh`; `verifying_status`/`branch_status`/`trigger_rerun`
  внешней задачи) → требование 5, AC-4, AC-5, AC-6. Есть.
- Критерии приёмки ТЗ → AC-1, AC-2/AC-3, AC-4. Есть.
- Зоны, «только чтение», «Не входит» → frontmatter `zones` и раздел «Не входит».
  Совпадают с ТЗ.

SPEC → ТЗ: требований сверх ТЗ нет. AC-7 (передача из `ci_rerun.py` и
`fsm_merge_gate.py`) следует из ТЗ п.2 («доходит до всех функций на пути
`ci-rerun` … гейта мержа»). Оговорка «сверка CI main остаётся только для
артели» — уточнение рамки ТЗ («без изменения логики гейтов»), не новое
требование.

## Факты против кода
Подтвердилось (рабочий каталог = main 0180d1df):
- `ci.gh` `:39`, `--repo` в конец argv `ci.py:63`, `cwd=config.ROOT` `ci.py:73`,
  токен в `GH_TOKEN` только при наличии `project` и токена `ci.py:65-71`.
- `check_runs_page` `:118` (передаёт `repo` как `--repo`, `:127-129`);
  `check_runs` `:143` без `repo`, зовёт `check_runs_page(sha, page)` `:169`;
  `run_list` `:198`, `repo` принимает `:213`;
  `_commit_workflow_runs` `:371` (`gh api` `:383` без repo);
  `_inherited_from_main` `:474` (`head_sha` с клоном `:478`,
  `failed_check_names(main_sha)` без repo `:481`);
  `verifying_status` `:600` и `branch_status` `:767` — клон только в `head_sha`
  (`:612`, `:778`) и `_unexecuted_full_suite`; `_no_checks_by_branch` `:674`
  зовёт `run_list(branch)` без repo `:678`; `failed_check_names` `:732`;
  `accepted_full_suite` `:823`, ранний отказ внешнему `:829-830`;
  `_main_line_runs` `:974`, `main_line_status` `:1029` (`check_runs(commit)`
  без repo `:1070`); `find_run_id` `:1136` (`gh api` `:1162`, `check_runs` `:1181`);
  `check_run_workflow_run` `:1211` (`:1221`); `trigger_rerun` `:1235`
  (`head_sha(branch)` без клона `:1256`, `gh run rerun`/`watch` `:1254`, `:1262`, `:1267`).
- Вызывающие: `ci_rerun.py:123`, `:158`, `:224`, `:232`, `:244`, `:267`, `:279`,
  `:298`; `fsm_merge_gate.py:290`, `:293`, `:341`, `:579`, `:618`, ранние выходы
  `is_artel` `:571`, `:614`; `acceptance.py:2069`, `:2087`, `:2184`;
  `github_adapter.py:168`, `:193`, `:306` (через `_gh_repo_kwargs` `:103-111`,
  `ctx.remote` = `url`); `fsm_advance.py:453`, `fsm_autogate.py:287` — клон
  передают. Поиск `ci.<функция>(` по `orchestrator/` и `scripts/` других
  вызывающих не нашёл, кроме названных в «Не входит» `pin.py:86`,
  `doctor/main_ci.py:33`; `advance_gates/` функций `ci` не зовёт. Перечень полон.
- `targets.yaml:70` — `url: https://github.com/sledproject/sled`.
- Тестов, утверждающих `--repo` у `gh api`, в `tests/` нет (единственное
  упоминание `--repo` — `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:166-198`,
  это `gh pr ready` адаптера).

Не подтвердилось / неточно:
- SPEC «Материалы»: «подмены `ci.head_sha`/`ci.check_runs` … `tests/test_invariants.py::MergeNeedsGreenCiTest`».
  На деле защищённый `tests/test_invariants.py:326-328` подменяет `ci.gh`
  (`lambda *a:` — без именованных аргументов) и `ci.head_sha` (`lambda branch:`),
  не `check_runs`. Перечень подмен, держащих форму вызова у артели, неполон —
  отклонение 1.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да (литералы argv/env/cwd, зафиксированные до правки) | `GH_REPO` или `--repo` ставится и артели; `env=` передаётся артели всегда; `cwd` сменён на клон. Не ловит мутацию `accepted_full_suite` артели — функции нет в перечне AC-1 (отклонение 2) |
| AC-2 | да, при условии, что тест проходит все места `gh api` | `--repo` остаётся у `gh api`; `GH_REPO` не выставлен в `_commit_workflow_runs`/`find_run_id`/`check_run_workflow_run`. Не ловит: `GH_REPO` ставится только вместе с токеном (запись без `token_slot`, отклонение 3); `.git`/`/` в конце `url` не сняты (отклонение 4) |
| AC-3 | да | `run_list` из `_no_checks_by_branch` или `gh run rerun`/`watch` без `--repo`; `GH_TOKEN` не передан `gh run` |
| AC-4 | да | `check_runs` в `verifying_status` без репозитория проекта → 422/«голова ветки не в origin» |
| AC-5 | да | `branch_status` не передаёт репозиторий в `check_runs` |
| AC-6 | да | `trigger_rerun` читает голову в клоне артели; `find_run_id` без `GH_REPO`; `rerun`/`watch` без `--repo` |
| AC-7 | да | `ci_rerun.py:224/232/267/279/298` или `fsm_merge_gate.py:290` не передают репозиторий |

Замечание (входит в отклонение 5): AC-4/AC-5 описывают только зелёный путь,
а AC-2/AC-3 говорят «каждый вызов», не называя сценариев, которые до этих
вызовов доходят: `_inherited_from_main` → `failed_check_names(main_sha)`
(только на красном, `ci.py:660`, `:814`); `_no_checks_by_branch` → `run_list`
(только без проверок, `:627`, `:638`); `find_run_id` → `check_runs` (только
при >1 красном прогоне, `:1180-1181`); `_commit_workflow_runs` (только если у
проверок есть `check_suite.id` или ссылка на прогон, `:379-382`). Тест
зелёного пути на проверках без `check_suite` до этих мест не доходит.

## Зоны
- Зоны SPEC = зоны ТЗ: `ci.py`, `ci_rerun.py`, `acceptance.py`,
  `fsm_merge_gate.py`, `github_adapter.py`, `tests/`. Требования 1–3
  выполнимы в них: путь клона → `url` можно получить чтением
  `repo_context.resolve`/`targets` (только чтение), правка
  `repo_context.py`/`targets.py`/`gitcmd.py` не нужна. `fsm_advance.py`,
  `fsm_autogate.py` уже передают клон (`:453`, `:287`).
- Защищённые пути: из `config.PROTECTED_PATHS` (`config.py:758-764`) в зону
  попадает `tests/test_invariants.py` (через `tests/`). SPEC его правки не
  требует; если разработчик передаст `ci.gh` артели именованный аргумент или
  `repo=` в `head_sha` артели, подмены `test_invariants.py:326-328` упадут, а
  чинить их можно только приложением PLAN. Это довод в пользу отклонения 1.
- Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `ci.gh`: `gh api` внешнего проекта — `GH_REPO` вместо `--repo` | вызовы `gh` артели без добавок, env процесса — `tests/test_01m545edths47hsb59akc1ez9c_project_token.py:456-514` | да (требование 2) | тот же тест + AC-1 | остаётся |
| `ci.gh`: токен слота внешнего проекта | `GH_TOKEN` слота у `gh` с `repo=` — `test_01m545…_project_token.py:516`; без слота — старая авторизация `:844-878` | да; требование 1 держит токен | тот же тест + AC-2/AC-3. Запись без слота с `GH_REPO` не покрыта | вопрос (отклонение 3) |
| `check_runs`/`verifying_status`/`branch_status` с репозиторием проекта | инвариант 19 (неизвестный статус не зелёный): пагинация и `total_count` — `tests/test_ci_status.py:155-170`; гейт мержа — `tests/test_invariants.py:706` | да, логика исхода не меняется | те же тесты (артель) + AC-4/AC-5 | остаётся |
| Передача репозитория в `trigger_rerun`/`failed_check_names` из `ci_rerun.py` | сверка «флейк или дефект main» перед повтором — `ci_rerun.py:267-288` | да, у внешнего проекта сравнение идёт с main проекта (сейчас с артелью) | AC-7 | остаётся (усиливается) |
| Ре-ран на гейте мержа `fsm_merge_gate.py:290` | подтверждённо красный → отказ мержа — `tests/test_merge_gate_ci_wait.py:156`, `:175` | да | те же тесты + AC-7 | остаётся |
| `accepted_full_suite` (пустой отказ внешнему) | полный набор не переиспользуется для внешнего — `ci.py:829-830` | да (SPEC: «поведение остаётся») | не покрыто AC (нет в AC-1) | вопрос (отклонение 2) |
| Сверка CI main только для артели | `fsm_merge_gate.py:571`, `:614` | да («Не входит») | существующие тесты гейта мержа | остаётся |

## Пути обхода гейтов
- П-1. Передать репозиторий только в места, до которых доходят тесты AC-4/AC-5/AC-6
  (зелёный путь, проверки без `check_suite.id`), и не передать его в
  `_inherited_from_main` → `failed_check_names`, `_no_checks_by_branch` →
  `run_list`, `find_run_id` → `check_runs`, `_main_line_runs`. Буквы AC это
  не нарушает, если тест AC-2/AC-3 не обходит все места, — отклонение 5.
- П-2. Выставить `GH_REPO` внутри ветки `if token is not None` (`ci.py:69-71`) —
  AC-2 с токеном слота зелёный, у записи без `token_slot` `gh api` снова уходит
  в репозиторий артели (по `cwd`) — отклонение 3.
- П-3. Чтобы `--repo` не попадал в `gh api`, проще всего вообще не передавать
  `repo` в `check_runs_page` — проверки уйдут в репозиторий артели, у которого
  такого коммита нет (422). Это ловят AC-2 (`GH_REPO`) и AC-4. Закрыто.
- П-4. Подогнать под новую форму вызова существующие подмены `ci.gh`/`head_sha`/
  `trigger_rerun` в `tests/` (дописать `**kwargs`). Формально это не ослабление,
  но AC-1 тогда держится только на новых тестах. В защищённом
  `tests/test_invariants.py:326` такая подгонка без приложения PLAN невозможна —
  отклонение 1.

## Вердикт
concerns. SPEC верно описывает дефект, и перечень функций и вызывающих в нём
полон. Отклонения ниже решаемы на гейте Оператором (уточнением SPEC или
указанием тест-автору), возврат аналитику не нужен.

1. `SPEC.md`, «Материалы» (подмены в тестах) — перечень подмен, которые держат
   форму вызова у артели, неточен и неполон. `tests/test_invariants.py:326-328`
   (защищённый) подменяет `ci.gh` как `lambda *a:` и `ci.head_sha` как
   `lambda branch:`, а не `check_runs`. Не названы:
   `tests/test_ci_status.py:160` (`fake_gh(*args)`), `:367`/`:372`/`:798`
   (`lambda sha:`/`lambda branch:` для `check_runs`/`run_list`/`find_run_id`),
   `tests/test_main_ci_line.py:62` (`gh(self, *args, timeout=None)`),
   `tests/test_merge_gate_ci_wait.py:82` (`trigger_rerun` как `lambda branch:`).
   Требование 2 говорит про argv/env/`cwd` подпроцесса, не про форму вызова
   Python-функций. Получается, что передача `repo=`/`env=` артели «по
   умолчанию» требованию 2 не противоречит, но ломает эти подмены, в том числе
   защищённую. Предложение: явно записать в требовании 2, что у артели вызовы
   `ci.gh`, `head_sha`, `check_runs`, `run_list`, `find_run_id`,
   `trigger_rerun` идут прежней формой, без новых именованных аргументов
   (приём `ci._repo_kwargs`, `ci.py:83-95`).
2. `SPEC.md` AC-1 — нет `accepted_full_suite` (`ci.py:823`), хотя функция
   есть в перечне требования 3, стоит на пути автогейта приёмки
   (`acceptance.py:2087`) и у артели зовёт `gh` (`check_runs`,
   `_commit_workflow_runs`). Требование 4 («функций перечня требования 3»)
   и AC-1 расходятся.
3. `SPEC.md` требование 1 и AC-2 — не сказано, что `GH_REPO` ставится и у
   записи без `token_slot`. По `gitcmd.py:133-135` у такой записи токена нет,
   а `ci.gh` собирает `env` только при токене (`ci.py:69-71`). AC-2 проверяет
   только проект со слотом и пропустит П-2.
4. `SPEC.md` требование 1 («владелец и имя — из `url` проекта») — правило
   разбора `url` не задано. Поле `url` — свободный текст (`targets.py:27`),
   а сравнение адресов в пульте снимает `/` и `.git` в конце
   (`gitcmd.url_key`, `gitcmd.py:44-46`). Наивный разбор даст
   `GH_REPO=<владелец>/<имя>.git`, и тест на `https://github.com/<o>/<n>`
   этого не поймает. Предложение: правило — как у `url_key`, учебный проект
   AC-2 — с `url`, оканчивающимся на `.git` или `/`.
5. `SPEC.md` AC-2/AC-3 — «каждый вызов» не привязан к сценариям, которые до
   вызова доходят: красный путь с `_inherited_from_main` (`ci.py:660`, `:814`),
   путь без проверок с `run_list` (`:678`), `find_run_id` при двух и более
   красных прогонах (`:1180-1181`), проверки с `check_suite.id` для
   `_commit_workflow_runs` (`:379-382`). Тест только зелёного пути выполняет
   AC буквально, но пропускает П-1. Предложение: перечислить эти сценарии в
   AC-2/AC-3 либо в требовании 5.
