---
task: 01M1K7KP0D8ZKRM9KTE75DCCYR
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 3
---

# REVIEW: Скилы и правила в бриф роли — из main, не из ветки задачи

## Фаза A: проверка плана

PLAN.md/SPEC.md/TZ.md не менялись с итерации 1 (`git diff f9637c4 HEAD --
tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/{PLAN,SPEC,TZ}.md` — пусто) — оценка
итерации 1 остаётся в силе без повторной проверки:

1. Покрытие: каждое требование SPEC (1-5) отражено в таблице покрытия
   PLAN.md шагами 1-3; требования 2 и 4 корректно помечены «не
   меняется» со ссылкой на «Не входит» SPEC — соответствует факту (код
   `fixation.py` и чтение артефактов задачи не тронуты диффом).
2. Размер шагов: три шага (`brief.py`, `runner.py`, тестовая
   инфраструктура) — каждый проверяемая единица, не микрооперация и не
   «сделать всё». ОК.
3. Подход не конфликтует с конвенциями: переиспользует существующий
   приём инварианта 28 (`gitcmd.show`) и существующую механику
   журналирования компонента (`component_hash`), не изобретает второй
   способ. ОК.

Эскалации PLAN.md (историческая — ANSWER-2; новая — ANSWER-3) обе
закрыты Оператором до сдачи этого шага на ревью — не пересматривается
повторно, см. итерацию 1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (скилы/CLAUDE.md — ветко-корректное чтение с `main`) | OK | `brief._main_branch_text`, `brief.skills_text` — оба через `gitcmd.show(config.MAIN_BRANCH, rel)` |
| 2 (артефакты задачи — без изменений, с ветки задачи) | OK | не тронуто диффом; regression-тесты AC-3/AC-7 зелёные |
| 3 (fingerprint отражает фактически прочитанное) | OK | `component_hash` = `context_package.sha256_of`; журналирование по факту прочитанного main-текста, теперь одним проходом после подтверждения полного чтения (см. R1-F1 ниже) |
| 4 (смена срезов через WIP не триггерит инцидент целостности) | OK | `fixation.py` не тронут; подтверждено тестом AC-5 |
| 5 (тесты подтверждают поведение, набор остаётся зелёным) | OK | 8/8 приёмочных, 1309/1309 юнит (см. «Проверено исполнением») |

| AC | Вердикт | Комментарий |
|---|---|---|
| AC-1 | OK | `runner._cmd_run` → `brief.skills_text` → `gitcmd.show` |
| AC-2 | OK | `developer_brief` → `_main_branch_text(CONVENTIONS_REL)` |
| AC-3 | OK | не тронуто; тест `test_ac3_...` зелёный |
| AC-4 | OK | `_manifest_component`/`skills_text` журналируют `sha256=component_hash(text)` по main-тексту |
| AC-5 | OK | `fixation.check_integrity` не читает скилы/CLAUDE.md; тест зелёный |
| AC-6 | OK | тест `test_ac6_...` зелёный |
| AC-7 | OK | тест `test_ac7_...` зелёный |
| AC-8 | OK | тест `test_ac8_...` зелёный |
| AC-9 | OK | штатно skip — регрессия покрыта CI-джобом `unittest discover -s tests` на каждый пуш (легальный случай «ci-covered») |

## Замечания

(пусто — единственное замечание прошлой итерации, R1-F1, закрыто; см.
«Реестр замечаний»)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/brief.py:367-397 | `skills_text` журналировала хэш скила ДО проверки, что прочитались все скилы роли | при отказе чтения скила N в журнале оставалась запись о скиле <N (частичное состояние) для шага, который не стартовал | подтверждено исправленным: `orchestrator/brief.py:387-397` — первый цикл читает и валидирует все скилы в список `texts` (ранний `return None, f"{rel}: {reason}"` при первом отказе — до этой точки `store.journal` не вызывается ни разу), второй цикл журналирует хэши уже подтверждённого полного списка. Проверено чтением diff (`git diff f9637c4 HEAD -- orchestrator/brief.py`) и исполнением: новые `tests/test_brief.py::SkillsTextTest` — `test_journals_all_skills_after_all_succeed` (оба скила читаются и журналируются) и `test_no_partial_journal_when_a_later_skill_fails` (второй скил отсутствует → `journal_details` пуст, никакой частичной записи про первый) — оба зелёные (`python3 -m pytest tests/test_brief.py -q` — 17 passed). Ровно то решение, что предлагала запись прошлой итерации. |

## Вердикт

`approved` — реестр замечаний закрыт целиком (R1-F1 → accepted),
блокеров и major нет. AC-1..AC-9 подтверждены, влияние на систему и
легальность правки залоченных фикстур по ANSWER-2 проверены в итерации
1 и не пересматривались (код артефактов не менялся).

## Проверено исполнением

- Инкрементальный diff `git diff 00e32aaf... HEAD` из пакета не собрался
  (`00e32aaf2c15059ffb72260275b29b9d2b53e8fe` не существует как объект
  в этом рабочем дереве — `git cat-file -t` даёт «could not get object
  info»); по правилу «пустой diff — повод перепроверить вручную» найден
  фактический коммит предыдущего вердикта через `git log --oneline --
  tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/REVIEW.md` → `f9637c4` («ревью
  итерация 1 — changes_requested»). Далее использован
  `git diff f9637c4 HEAD` — 4 файла: `docs/codebase-map.md`,
  `orchestrator/brief.py`, `tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/REVIEW.md`,
  `tests/test_brief.py`.
- `tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/` в рабочем дереве этого запуска
  показывался как удалённый (`git status --short`); восстановлено
  `git checkout -- tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/` (не переписыванием
  — тот же класс ситуации, что и в прошлой итерации).
- Чтение `orchestrator/brief.py:367-397` (`skills_text` целиком) —
  подтверждён двухпроходный порядок: первый цикл только читает/валидирует
  (никакого `store.journal` до полного успеха), второй — журналирует.
  Докстринг функции обновлён и явно ссылается на R1-F1/итерацию 1.
- `python3 -m pytest tests/test_brief.py -q` — 17 passed (включая два
  новых теста `SkillsTextTest`).
- `python3 -m pytest tests/ -q` — 1309 passed, 408 subtests passed, 0
  failed (было 1307 в прошлой итерации — +2 за счёт новых тестов
  `SkillsTextTest`, не регрессия).
- `python3 -m unittest discover -s
  tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/acceptance_tests -v` — Ran 8 tests,
  OK (0 failures/errors).
- `python3 scripts/guard.py tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/PLAN.md
  tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/SPEC.md
  tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/TZ.md
  tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/REVIEW.md` — «GUARD: ок (4 файлов)».
- `docs/codebase-map.md` diff — только строка `built_at_sha` (значение
  сменилось на `f9637c4...`, родительский коммит фикса — карту нельзя
  сослаться на свой же ещё не существующий коммит); список публичных
  функций `orchestrator/brief.py` не изменился (`skills_text` — та же
  сигнатура, изменение сугубо внутреннее) — не читаю это как дефект
  (правило про `built_at_sha` из скила ревьювера).
- `git diff f9637c4 HEAD -- tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/{PLAN,SPEC,TZ}.md`
  — пусто, Фаза A не пересматривалась.

## Предложения системе

(пусто)
