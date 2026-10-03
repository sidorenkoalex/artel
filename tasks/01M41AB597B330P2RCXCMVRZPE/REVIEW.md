---
task: 01M41AB597B330P2RCXCMVRZPE
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Перефиксация не узаконивает сдвиг ссылки документов мимо пульта

## Фаза A — план
- Таблица покрытия полна (требования 1–10), шаги — единицы размера MR.
- Требование 8: отказ от приложения к инварианту 25 обоснован (формулировка
  «фиксация = голова ссылки, сдвиг — инцидент» уже покрывает поведение);
  AC-12 тогда не применяется — согласен.
- «Влияние на систему» сходится с diff: 11 модулей `orchestrator/`, 7 файлов
  `tests/` только с добавленным `store.record_fixation` после коммита-
  имитации записи пульта (+ докстринг одного метода). Удалённых строк в
  `tests/` нет (`git diff d1279b85 -- tests/ | grep -c '^-[^-]'` → 0) —
  утверждения не тронуты, ослабления нет. Добавленный `record_fixation` в
  песочницах — не сужение проверки: он изображает перефиксацию, которую
  настоящий автокоммит делает сам (`checkpoint._commit_step_artifacts_to_branch`).
- Риск `DocsRefIncident` (`SystemExit`) в `auto.py` разобран: `auto` — процесс
  одной задачи, `cmd_auto` журналирует «цикл оборван» и пробрасывает; задача
  к этому моменту уже в `escalated`. Принимаю.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Узел зовут `set_state`, `answer`/`zones-extend`, `amend-tests` ×2, `snapshot.commit_closing`, `doctor --fix`, чекпоинты (`_docs_ref_drift`), гейт перечня `tests_writing`. Других вызовов `commit_files`/`record_fixation` в `orchestrator/` без сверки нет (grep, см. ниже); `catalog.py:623` — заведение ссылки без фиксации. |
| 2 | OK, кроме R1-F1 | Сдвиг (голова прочитана) — эскалация без паспорта/фиксации, именованный отказ, журнал. |
| 3 | OK | Сравнение только в `fixation.ref_drift`; `_docs_ref_moved_past_pult` заменена обёрткой. |
| 4 | OK | Законные записи перефиксируют сами (в т.ч. новый `record_fixation` в `tests_writing.py:348`); AC-7/AC-10 зелёные. |
| 5 | Не так | Удалённая ссылка при живой фиксации читается как «голова не прочитана», и команды Оператора/гейт перечня пишут корневой коммит и перефиксируют его — R1-F1. Для честно молчащего git — OK (AC-8). |
| 6 | OK | `fsm._cmd_approve` → `legitimize` только после `confirm_fixation` с явным sha. |
| 7 | OK | `fixation.read` → `artifact_branch.ref_head` в репозитории задачи; AC-10 с приманкой в git главной копии зелёный. |
| 8 | OK | Приложения нет, обоснование в PLAN. |
| 9 | OK | Долгоживущий файл задачи, заявки «Ловит мутацию» у всех методов; заявка изменённого `test_step_refixation` правдоподобна. |
| 10 | OK | `cleanup._warn_moved_ref`: журнал + предупреждение с sha, `killed` без паспорта, коммита закрытия нет, сверка с `origin` пропущена, чтобы не опубликовать подмену. |

## Замечания

- major — `orchestrator/fixation.py:227` (`stop_on_moved_ref`), а также
  места того же класса `orchestrator/answer.py:176` (`answer`),
  `orchestrator/answer.py:233` (`zones-extend`), `orchestrator/amend.py:525`
  и `:830` (`amend-tests`, оба режима — через тот же `stop_on_moved_ref`),
  `orchestrator/advance_gates/tests_writing.py:334` (`drift.moved`-only) —
  роль, удалившая ссылку `refs/artifacts/<id>` (`git update-ref -d`, то же
  право, что и в модели угрозы SPEC), получает узаконенную подмену.
  `ref_drift` даёт `RefDrift(fixed, "")` (`moved=False`), эти места
  пропускают запись, полагаясь на докстринг «её собственная запись в ссылку
  отказывает сама», но git отвечает: `artifact_branch._write` при отсутствии
  ссылки пишет коммит БЕЗ родителя (`parent or _ABSENT_OID`), а затем
  `record_fixation` пишет его в `tasks.fixed_sha`. **Воспроизведено**
  временным тестом на песочнице `DocsRefSandbox` (файл удалён после прогона):
  задача артели в `in_dev` с фиксацией `fd1ec4cb…`; `update-ref -d`; `answer.
  cmd_zones_extend` → отказа нет, `fixed_sha` стал `98a108e1…` = новая
  голова, дерево ссылки — только `ANSWER-1.md` (SPEC.md и всё прочее
  потеряны), `fixation.check_integrity` → `None`, задача остаётся в
  `in_dev`. Это ровно то, что запрещают требование 5 и AC-8 («фиксация есть,
  а голова не прочитана — не записывает в `fixed_sha` непроверенную голову;
  сверка на старте шага остаётся fail-closed»): после такой записи сверка на
  старте больше не отказывает. Предложение: в местах, коммитящих в ссылку
  (`stop_on_moved_ref`, гейт перечня), при ЛЮБОМ расхождении с живой
  фиксацией (`drift is not None`) — не писать: при `moved` — как сейчас
  инцидент, при пустой голове — именованный отказ без коммита (либо
  различать «ссылки нет» и «git не ответил» в узле и считать отсутствие
  ссылки при фиксации сдвигом мимо пульта). Поправить докстринг
  `stop_on_moved_ref`. Добавить сторожа в `tests/` на сценарий «ссылка
  удалена при живой фиксации → `zones-extend`/`answer`/выход из
  `tests_writing`» с заявкой «Ловит мутацию: …» (долгоживущий файл задачи
  этот сценарий не держит — новый файл разработчика его не повторяет).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fixation.py:227; answer.py:176, :233; amend.py:525, :830; advance_gates/tests_writing.py:334 | Удалённая ролью ссылка при живой фиксации проходит как «голова не прочитана»; запись пульта создаёт корневой коммит и перефиксирует его | Подмена (потеря SPEC/планки из ссылки) узаконена, `check_integrity` на старте шага молчит — нарушены требование 5 / AC-8, инвариант 25 | Не писать в ссылку при любом `drift` с фиксацией (или считать отсутствие ссылки сдвигом мимо пульта); поправить докстринг; сторож в `tests/` |

## Вердикт
changes_requested — закрыть R1-F1 (класс целиком: `answer`, `zones-extend`,
`amend-tests` ×2, гейт перечня `tests_writing`) и добавить сторожа в `tests/`.
Остальная реализация соответствует SPEC; сверка временной мутацией
подтверждает, что сторожа задачи ловят снятие сверки в `set_state`.

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py
  tests/test_step_refixation.py tests/test_answer.py tests/test_amend.py
  tests/test_amend_remove.py tests/test_amend_long_lived.py
  tests/test_long_lived_transitions.py tests/test_kill_cleanup.py
  tests/test_snapshot_closing_outcome.py tests/test_doctor_fix_ignored_artifacts.py
  tests/test_git_fixation.py tests/test_cas_set_state.py
  tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py` — 184 passed,
  24 subtests passed (4 мин 07 с).
- Планка задачи (скопирована в рабочий каталог, затем убрана):
  `pytest tasks/01M41AB597B330P2RCXCMVRZPE/acceptance_tests` — 2 passed.
- Временная мутация: `store.set_state` — `drift = None` вместо
  `fixation.ref_drift(...)`; `pytest … -k "ac1 or ac2"` — 5 failed
  (AC-1, AC-2, AC-10 внешний, AC-13 ×2), код возвращён `git checkout`.
- Временный тест-проба R1-F1 (`update-ref -d` → `zones-extend`) — вывод
  в замечании; файл удалён, `git status` чистый.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  без строки `built_at_sha` — 0 строк расхождения: карта свежая.
- `git diff d1279b85 -- tests/ | grep -c '^-[^-]'` → 0 (удалённых/
  изменённых строк в `tests/` нет).
- grep `commit_files(|record_fixation(|update-ref` по `orchestrator/` —
  все перефиксирующие записи покрыты узлом (кроме класса R1-F1).

## Предложения системе
- Скил review-checklist / миссия ревьювера: шаг «скопируй планку в
  `tasks/<id>/` рабочего каталога» плюс уборка опасны — в рабочей копии
  `tasks/` отслеживается git'ом (артефакты других задач); уборку стоит
  явно описывать как удаление только `tasks/<id>/`, не каталога `tasks/`
  (в этом шаге я снёс `tasks/` целиком и восстановил его `git checkout -- tasks`).
