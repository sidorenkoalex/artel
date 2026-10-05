---
task: 01M44ENQCRK02T2MWZB9HC3XHH
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: amend-tests отправляет кодовую ветку задачи в origin; verifying не ждёт до потолка коммита, которого нет в origin

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–8 сопоставлены шагам 1–3; шаги 4–5 — тест предиката и карта.
- Шаги размера MR, не микрооперации. Подход переиспользует единственный узел `github_adapter.ensure_head_in_origin` (SPEC: «второй способ не заводится») и штатный `_recovery_exit` — конфликтов с архитектурой нет.
- «Влияние на систему» совпадает с diff: `amend.py`, `ci.py`, `fsm_advance.py`, `tests/test_ci_status.py` (+ карта). Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `amend.py:728` — `_push_code_head` сразу после коммита (а), до `branch_head_sha`/`_head_digests`, т.е. до (б) `_commit_plank` и (в) сдвига лока. Вызов внутри ветки с непустым `long_changed`. |
| 2 | OK | `_push_code_head` (`amend.py:530`) — `t["is_canary"]` → no-op; тот же признак, что `fsm_advance.py:628` (`in_dev`, `_origin_push_gate`). AC-3 зелёный. |
| 3 | OK | Отказ → `_recovery_exit`: ненулевой выход, запись «amend-tests прерван», путь `amend-tests <id> --from-branch --reason «…»`; detail несёт `why` узла и «почини доступ к origin». Лок/ссылка документов не тронуты (отказ до (б)/(в)). |
| 4 | OK | `amend.py:939` — под `if long_diverged:` после `_check_code_head_long_lived`, до `if manifest:` (коммит перечня и сдвиг лока). При пустом `long_diverged` вызова нет (AC-5 со шпионом). После отказа по треб. 1 расхождение в перечне лока остаётся, так что путь восстановления `--from-branch` действительно повторит отправку. |
| 5 | OK | Режим без перечня не тронут; AC-5 (`AmendWithoutManifestTest`) — шпион 0 вызовов, голова кодовой ветки прежняя. |
| 6 | OK | `fsm_advance.py:339` — на признаке 422 зовётся узел, далее прежний путь счётчика/потолка; состояние на отказе не меняется. Исключение канарейки в `verifying` SPEC прямо не требует — PLAN обосновывает аналогией с `_origin_push_gate`; не противоречит SPEC (канарейка в origin не ходит вообще). |
| 7 | OK | Вызов только при `verifying_head_not_in_origin(note)`; зелёный выходит раньше. AC-8 (4 исхода, шпион) зелёный; `test_auto_cycle.py` (один вызов узла на зелёном пути) зелёный. |
| 8 | OK | `ci.py:350` — без «git push -u origin», есть «голова», «origin», «push», имя ветки, «пульт… при опросе verifying». `test_422_note_names_head_not_in_origin_with_a_push_hint` зелёный без правки. |

Корректность: признак 422 — префикс `HEAD_NOT_IN_ORIGIN_NOTE`, и текст исхода строится из той же константы, поэтому разъехаться они не могут. Прочие `note` `verifying_status` («у коммита … нет ни одной проверки», «CI коммита … не зелёный», «gh не ответил…») с этой строки не начинаются. Репозиторий узла (`repo_context`) и рабочая копия задачи (`workspace.task_repo`) делят refs ветки. Это подтверждено песочницей AC-1/AC-4 с настоящим голым origin.

Тесты: `VerifyingHeadNotInOriginTest` — обе заявки «Ловит мутацию» наблюдаемы: предикат-всегда-False краснит `test_422_note_is_detected`, предикат-всегда-True — `test_other_none_outcomes_are_not_detected`. Повтора долгоживущего файла задачи нет: тест проверяет предикат, а не сценарии AC. Существующие утверждения `tests/` не менялись: diff `tests/test_ci_status.py` только добавляет класс.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py tests/test_ci_status.py tests/test_amend.py tests/test_amend_long_lived.py tests/test_amend_remove.py tests/test_verifying_ceiling.py tests/test_github_adapter.py tests/test_auto_cycle.py` — 228 passed, 74 subtests passed (144 с).
- `python3 …/orchestrator/artel.py plank-run 01M44ENQCRK02T2MWZB9HC3XHH` — «планки нет: … нет файлов test_*.py; pytest не запускался». У задачи только долгоживущая группа, она прогнана выше прямым pytest.
- `grep -n is_canary orchestrator/fsm_advance.py` — признак канарейки в `verifying` (стр. 339) и в `in_dev` (стр. 628) один и тот же.
- Временную мутацию предиката запустить не удалось: правка `ci.py` через sed в шаге требовала подтверждения. Чувствительность нового класса оценена по тексту тестов, см. выше.
- CI коммита b4f8fca5 зелёный (16 проверок, по пакету).

## Предложения системе
- Приём «временная мутация» из review-checklist в шаге ревьювера упирается в запрос подтверждения на правку файла кода через Bash (`sed -i`): в неинтерактивном шаге его некому дать. Стоит описать в скиле разрешённый способ (например, `Edit` и откат `git checkout -- <файл>`) или разрешить его в `.artel/home` settings.
