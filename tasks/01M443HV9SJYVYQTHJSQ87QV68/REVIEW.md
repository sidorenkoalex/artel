---
task: 01M443HV9SJYVYQTHJSQ87QV68
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: CI ветки задачи проверяет код вместе с приложениями PLAN

## Фаза A — план
- Таблица покрытия полна: все требования 1–8 привязаны к шагам; шаги — единицы размера MR (сценарий + юнит-тесты; ворота мержа; документ; приложение к `ci.yml` + карта).
- Подход в рамках конвенций: `ci.yml` меняется только приложением; `docs/operator-session.md` правится в ветке по ANSWER-1 (вариант а) с мандатом «Расширение зон разрешено». Мандат перенесён в раздел PLAN «Расширение зон».
- Сторож AC-8 вынесен в шаг job `guard` внутри того же приложения (`--check-workflow`), его логика покрыта `tests/test_plan_appendix_ci.py` на синтетических workflow — так тест остаётся зелёным на ветке без приложения. Это законная форма требования 7: «внутри того же приложения».
- «Влияние на систему» сходится с диффом: 5 файлов кода и документа + карта; гейт `in_dev` (`advance_gates/plan_appendix.py`) получил только необязательный `*flags`, вызов гейта без флагов не менялся; существующие тесты не тронуты (дифф `tests/` — только новый файл `tests/test_plan_appendix_ci.py`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `scripts/plan_appendix_ci.py::run` — `ls-remote` → `docs_ref_for_branch` → `fetch` без имени назначения → `guard.plan_appendices` → `git apply` подряд. Шаг в jobs `python`/`python-min` стоит до pytest и до снимка `refs-before`, условие `push && refs/heads/task/` (приложение 1). |
| 2 | OK | `task_branch` отсекает не-`task/**` и pull_request без вызова git; без ссылки, без PLAN.md и без приложений — код 0 и дерево не тронуто (долгоживущий test_ac2). |
| 3 | OK | Отказ `git apply` — код 1, в stderr «приложение N (<пути>) не накладывается…: <ответ git>». |
| 4 | OK | `commit`/`push` не вызываются; `fetch` без refspec назначения (только FETCH_HEAD). Долгоживущий test_ac4 проверяет это через обёртку git. |
| 5 | OK | `fsm_merge_gate._appendix_already_in_main`: `--reverse --check` → запись журнала «приложение PLAN уже в main: <пути>» с номером и `continue`. При пустом `paths` — `("ok", [])` без пустого коммита. |
| 6 | OK | Частичное наложение: обратная проверка не проходит → прежний `_return_inapplicable_appendix` (долгоживущий test_ac6). |
| 7 | OK | Приложение 1 к `ci.yml` (шаг в `python`, `python-min` и сторож в `guard`) проходит `git apply --check`; правка `docs/operator-session.md` в диффе ветки по ANSWER-1. |
| 8 | OK | Долгоживущие файлы покрывают требования 1, 3, 5, 6 (заявки «Ловит мутацию» есть и проверены мутациями ниже); юнит-тесты в `tests/test_plan_appendix_ci.py` несут заявки; существующие тесты не изменены. |

## Замечания

Блокирующих и major-замечаний нет.

Наблюдение без записи в реестре (последствие безвредно):
- `scripts/plan_appendix_ci.py::plan_text` берёт sha из `ls-remote`, а `fetch` делает отдельно. Если пульт сдвинет ссылку документов между этими двумя вызовами, старого sha в неглубокой объектной базе может не оказаться. Тогда `cat-file -e` вернёт «PLAN.md нет», и сценарий выйдет с кодом 0 без приложений. Ложно-зелёного CI при этом не будет: тесты, которым приложение нужно, останутся красными, а следующий пуш прогонит шаг заново. Изменится только текст сообщения. Если когда-нибудь трогать этот код, стоит читать `FETCH_HEAD`, а не sha из `ls-remote`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: в итерации 1 замечаний нет.

## Вердикт
approved

## Проверено исполнением
- `python3 …/orchestrator/artel.py plank-run 01M443HV9SJYVYQTHJSQ87QV68` — 3 passed (AC-7 ×2, AC-8), код выхода pytest 0.
- Приложение 1 извлечено из PLAN.md через `guard.plan_appendices` (1 приложение, ошибок разбора нет, путь `.github/workflows/ci.yml`). `git apply --check` на чистом дереве ветки (HEAD 97997320) — применяется.
- `python3 scripts/plan_appendix_ci.py --check-workflow .github/workflows/ci.yml`: без приложения — две `::error::` (нет шага в `python` и `python-min`), с временно наложенным приложением — «шаг приложений PLAN есть в jobs python, python-min». С приложением же `pytest tests/test_invariants.py -k "CiJobs or ci"` — 12 passed, 7 subtests passed. После этого `ci.yml` восстановлен (`git checkout`), `git status` чист.
- `pytest tests/test_plan_appendix_ci.py tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py tests/test_plan_appendix.py tests/test_merge_gate_ci_wait.py tests/test_fsm_merge_gate_done_snapshot.py tests/test_id_format_guard.py` — 79 passed.
- Временная мутация 1: `_appendix_already_in_main` всегда возвращает False (ворота с одним прямым `git apply`) — `test_ac5_appendix_already_in_main_is_accepted_and_journaled` красный, test_ac6 зелёный. Код возвращён.
- Временная мутация 2: в `run` отказ `git apply` проглатывается (`continue` вместо `return 1`) — `test_ac3_inapplicable_appendix_fails_with_its_name` красный. Код возвращён.
- `python3 scripts/codebase_map.py` на ветке — карта по содержимому совпадает, расхождение только в `built_at_sha`. Карта восстановлена, `git status --porcelain` пуст.
- Полный набор `tests/` не гонял: по решению Оператора от 05.09 его гоняет CI. Пакет фиксирует зелёный CI коммита 97997320 (16 проверок).

## Предложения системе
- Гейт применимости на выходе `in_dev` (`orchestrator/advance_gates/plan_appendix.py::_plan_appendix_gate`) и новый сценарий CI одинаково откажут приложению, которое уже есть в базе ветки после подтяжки main. Приём уже наложенного (`--reverse --check`) теперь умеют только ворота мержа. Это граница SPEC («Не входит»), но остаётся тупик: Оператор внёс правку в main, ветка подтянула main — задача застревает на `in_dev`/CI, пока роль не уберёт приложение из PLAN. Стоит отдельной задачей выровнять три точки по одному правилу.
