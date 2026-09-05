---
task: 01M1RQ12JVHE3PQYDFV1XPSTQ3
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: бриф роли называет артефакты путём от рабочего каталога роли, не от корня пульта

## Контекст итерации 2

Ревью-пакет строит инкрементальный diff от sha предыдущего вердикта
(`ac2028d8`) до HEAD — этот диапазон целиком состоит из «подтяжки main»
(коммит `4425692a`), принесшей в ветку объём уже смерженных в main чужих
задач (ADR-0014, R6 `store.py`→`schema.py`, R7 разбор
`fsm_merge_gate`, отключение автопамяти) — тот же класс ложного сигнала,
что уже зафиксирован в `docs/backlog.md` (задача о трёхточечном диффе
гейтов, 01M1SG9T96) и в памяти прошлых ревью (напр. REVIEW.md
01M1SD5RHTJ0H0SR0615SVCJM5, итерация 2). Ни SPEC.md, ни PLAN.md для ЭТОЙ
задачи в пакете не показаны вовсе («не показан: в ветке — fatal: path …
does not exist», «в дереве — No such file or directory») — по той же
причине: артефакты этой задачи живут в артефактной ветке
(`artifact/01m1rq12jvhe3pqydfv1xpstq3`), не в кодовой, а пакет искал их
в кодовой ветке/рабочем дереве без материализации.

Проверено вручную: `git merge-base --is-ancestor main HEAD` — main
является предком HEAD. Реальный diff этой ветки относительно main:

```
docs/codebase-map.md         |  3 +-
orchestrator/review.py       |  7 +++
orchestrator/role_prompt.py  | 12 ++++--
orchestrator/runner.py       | 61 +++++++++++++++++++++++++++++++--
tests/test_agent_failure.py  | 13 +++++++
tests/test_agent_log.py      | 22 +++++++++--
tests/test_agent_prompt.py   | 12 +++++++
tests/test_doctor.py         |  8 +++++
tests/test_git_fixation.py   | 20 ++++++++++-
tests/test_invariants.py     | 14 ++++++++
tests/test_multitarget.py    | 10 +++++++
tests/test_review_package.py | 25 +++++++++++--
tests/test_step_cost.py      |  8 +++++
```

— ровно зона задачи (`orchestrator/brief.py, orchestrator/role_prompt.py,
orchestrator/runner.py, tests/`, расширенная на `orchestrator/review.py`
мандатом ANSWER-2.md) плюс `docs/codebase-map.md`. `orchestrator/brief.py`
не тронут (расследование PLAN «Подход»: утечка жила не там). Ревью ниже
ведётся по этому реальному diff, прочитанному из артефактной ветки и
рабочего каталога (материализован на диске), не по инкрементальному
пакету, который к содержанию этой задачи отношения не имеет.

## Фаза A: проверка плана

Без изменений с итерации 1 (PLAN.md правился только в разделе «Правки
итерации 2», отчитывающемся об исправлении R1-F1/R1-F2, — сама
архитектура подхода не менялась). Таблица покрытия требований полна,
подход обоснован расследованием (утечка в `review.py`, не в `brief.py`),
размер MR — три точечных изменения кодовой базы плюс регрессия тестов.
Зона расширена мандатом Оператора (ANSWER-2.md, раздел «Расширение зон»
в PLAN.md) — легитимно.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) | OK | `orchestrator/review.py:42` — новая ветка `except FileNotFoundError` возвращает `"(не показан: в ветке — {in_branch}; в дереве — файл не найден)"` вместо `str(exc)`, которое несло `str(config.ROOT / rel)` целиком. Приёмочный тест `test_ac1_prompt_never_carries_the_absolute_tasks_path` — 4 subTest (по роли), зелёные. |
| 2 (AC-2) | OK | `runner.py::role_cwd_path` — чистая формула без побочных эффектов, идентичная формуле внутри `role_cwd` (для self/артели `workspace.ensure(...)` при успехе возвращает тот же `workspace.path(task_id)`, что и `role_cwd_path`, — сверено чтением `workspace.py:60-62`); `role_cwd()` теперь использует её же (снятие дублирования). `role_prompt.mission_brief_package` дописывает буквальную строку рабочего каталога в конец `mission` БЕЗУСЛОВНО, после всех четырёх веток (`role_prompt.py:112-113`) — распространяется на все роли без исключения. Приёмочный тест `test_ac2_prompt_states_the_real_role_cwd_for_every_role` — 4 subTest, зелёные. |
| 3/4 (AC-3..AC-7) | OK | `_missing_required_artifact` (`runner.py:643`) проверяет диск РЕАЛЬНОГО `cwd`, вызывается между веткой `rc != 0` и веткой `pump.error` — то есть ДО `commit_step_artifacts`/`shutil.rmtree` (иначе проверка «после» была бы бессмысленна, как явно предупреждает докстринг AC-5 приёмочного теста). `or` для analyst (SPEC.md ИЛИ QUESTIONS.md), проверка каталога (не конкретного файла) для test_author — соответствует формулировкам AC-4/AC-6 буквально. Отказ классифицируется тем же путём, что и `rc != 0` (WIP-чекпоинт `commit_abnormal_checkpoint`, `("failed", reason, None)`) — ретраи/эскалация не дублируются, используют существующий механизм `cmd_run`. Штатный путь (AC-7) не тронут — проверка не меняет исход, когда файл на месте. Все 5 приёмочных тестов (`Ac3`..`Ac7`) зелёные. |
| 8 (AC-8, регрессия) | OK — R1-F1 исправлено | Реальный прогон 9 файлов, которые итерация 1 назвала упавшими (`test_agent_failure`, `test_agent_log`, `test_doctor`, `test_git_fixation`, `test_invariants`, `test_multitarget`, `test_step_cost`, `test_agent_prompt`, `test_review_package`) — **473 passed, 268 subtests passed**, 0 failures (см. «Проверено исполнением»). Дополнительно перепрогнаны ещё 15 файлов из перечня PLAN «Влияние на систему» — все зелёные. |

## Замечания

- minor — `tests/test_review_package.py:817-839` (`test_worktree_fallback_is_journaled`, правка R1-F1) — изменённая проверка (точное вхождение строки `"не из ветки, а из рабочего дерева: templates/REVIEW.md"` заменено на два независимых `assertIn`) обоснована докстрингом/инлайн-комментарием по существу (маркер `tasks/<id>/REVIEW.md`, добавленный тем же фиксом, теперь тоже честно входит в список `from_worktree` и может стоять раньше по алфавиту — свойство под тестом от порядка не зависит), но не несёт явной заявки `Ловит мутацию: …` по конвенции `skills/test-authoring.md` — тот же класс пробела, что уже отмечался ревью соседних задач этой волны рефакторинга (напр. REVIEW.md 01M1RA0R9AH9RBAHD4A2Z5SEWQ, «Предложения системе»; REVIEW.md 01M1SD5NZ79MWCEJDJ9JP6EPWS, «Предложения системе»). Не блокирует — свойство теста не ослаблено, обоснование по существу присутствует; предложение — явно решить на уровне скила, распространяется ли требование маркера на точечные правки существующих юнит-тестов.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/runner.py:883 (+ 7 файлов tests/) | Новая проверка обязательного артефакта ломала 26 тестов существующего набора | AC-8 было нарушено шире заявленного | Подтверждено исполнением: перепрогнаны все 9 файлов итерации 1 (в т.ч. полный список из 26 упавших тестов) — 473 passed, 268 subtests passed, 0 failures. Сидирование маркера обоснованно для каждого класса песочницы (`config.WORKTREES`/`config.TASKS`/артефактная ветка — где именно этот класс тестов читает `role_cwd`) — читал diff всех 7 файлов, ни один существующий `assert` не ослаблен, только добавлено сидирование фикстуры. |
| R1-F2 | accepted | docs/codebase-map.md | Карта не была регенерирована после добавления `role_cwd_path` | CI-джоб codebase-map красил бы диф | Подтверждено: `role_cwd_path` присутствует в перечне публичных функций `orchestrator/runner.py` в закоммиченной карте; локальная регенерация даёт расхождение только в `built_at_sha` (не дефект, см. review-checklist.md) — карта свежая по содержимому. |

## Вердикт

approved

## Проверено исполнением

- Расхождение пакета с реальностью: `git merge-base --is-ancestor main HEAD` (main — предок HEAD), `git diff main...HEAD --stat` — 13 файлов, ровно зона задачи + `docs/codebase-map.md`; `git log --all --oneline -- 'tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/*'` — артефакты задачи (SPEC.md/PLAN.md/REVIEW.md итерации 1/ANSWER-2.md) найдены в `artifact/01m1rq12jvhe3pqydfv1xpstq3`, прочитаны оттуда (`git show <sha>:tasks/.../SPEC.md` и т.д.) — причина, по которой пакет их не показал: они не в кодовой ветке/рабочем дереве без материализации, а в артефактной ветке (штатная механика, `conventions-core.md`).
- `python3 -m pytest tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/acceptance_tests/ -q` — 7 passed, 12 subtests passed (все AC-1..AC-7).
- `python3 -m pytest tests/test_agent_failure.py tests/test_agent_log.py tests/test_doctor.py tests/test_git_fixation.py tests/test_invariants.py tests/test_multitarget.py tests/test_step_cost.py tests/test_agent_prompt.py tests/test_review_package.py -q` — **473 passed, 268 subtests passed** (это ровно 9 файлов и полный список из 26 тестов, названных упавшими в REVIEW.md итерации 1 — регрессия R1-F1 подтверждена исправленной).
- `python3 -m pytest tests/test_brief.py tests/test_review_freshness.py tests/test_acceptance_tests_flow.py tests/test_analyst_role.py tests/test_auto_cycle.py tests/test_multitarget_invariants.py tests/test_step_autocommit.py tests/test_step_refixation.py tests/test_timeout_checkpoint.py tests/test_advance_refusal_history.py tests/test_canary.py tests/test_checkpoint_external_step_artifacts.py tests/test_diff_not_collected_alerts.py tests/test_failure_classification.py tests/test_lease_pgid_store.py -q` — 323 passed, 32 subtests passed (остаток перечня PLAN «Влияние на систему»).
- `python3 scripts/guard.py tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/SPEC.md tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/PLAN.md` — «GUARD: ок (2 файлов)».
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в строке `built_at_sha` (`role_cwd_path` уже присутствует в закоммиченной версии) — не дефект (review-checklist.md, класс подтверждён T053/T072); откачено `git checkout -- docs/codebase-map.md`, рабочее дерево чистое кроме `tasks/<id>/` (материализация роли).
- Чтение кода вне пакета (материализованный рабочий каталог и артефактная ветка): `orchestrator/review.py::artifact_text`, `orchestrator/role_prompt.py::mission_brief_package`, `orchestrator/runner.py::role_cwd_path/role_cwd/_missing_required_artifact/run_agent_once`, `orchestrator/workspace.py::path/ensure` (сверка равенства формул `role_cwd_path`/`role_cwd` для self/артели) — причина чтения: пакет не показал SPEC/PLAN/diff этой задачи вовсе (см. «Контекст итерации 2»), без прямого чтения кода и артефактной ветки вердикт был бы невозможен.
- Полный набор `tests/` не гонял (решение Оператора 05.09, гоняет CI на каждый пуш) — прогнаны планка задачи и 24 файла из зоны/перечня PLAN, реально пересекающиеся с правкой.

## Предложения системе

- Ревью-пакет для этой задачи не показал ни SPEC.md, ни PLAN.md («не показан: fatal: path does not exist в ветке; No such file or directory в дереве») и построил инкрементальный diff, целиком состоящий из чужой «подтяжки main» — оба симптома одной причины: генератор пакета искал артефакты и точку сравнения в кодовой ветке/рабочем дереве без материализации из головы артефактной ветки, хотя единственный путь артефактов в git — именно артефактная ветка (`conventions-core.md`). Тот же класс уже отмечен в `docs/backlog.md` (трёхточечный дифф, 01M1SG9T96) применительно к гейтам — стоит явно проверить, покрывает ли будущий фикс и сборку самого ревью-пакета, раз он тоже промахивается мимо материализации/базы сравнения, а не только гейты `fsm_advance.py`.
