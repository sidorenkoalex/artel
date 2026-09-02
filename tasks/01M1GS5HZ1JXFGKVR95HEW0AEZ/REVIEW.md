---
task: 01M1GS5HZ1JXFGKVR95HEW0AEZ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 3
---

# REVIEW: Вход в verifying требует голову ветки на origin

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (проверка головы на входе в verifying) | OK | `fsm_advance.py::review`, ветка `status == "approved"` (строки 156-171), вызывает `github_adapter.ensure_head_in_origin`, которая сверяет `gitcmd.branch_head_sha` с `gitcmd.remote_branch_sha` (`git ls-remote origin refs/heads/<branch>`) — точный sha, не факт присутствия ветки (AC-2 проверено тестом на устаревший origin-sha). |
| 2 (авто-push тем же механизмом, продолжение в том же advance) | OK | `ensure_head_in_origin` при расхождении делает `git push -u origin <branch>` — тот же вызов, что `ensure_draft_mr`; успех журналируется, `review()` продолжает выполнение (не возвращает False) в этой же ветке кода. |
| 3 (упавший push — именованный отказ, не sys.exit, состояние не меняется) | OK | Провал журналируется хелпером и в `fsm_advance.py` (`store.journal(..., "переход отклонён: голова не в origin", ...)`), `return False` — тот же приём, что у остальных отказов `review()`; текст причины байт-в-байт совпадает с AC-4. |
| 4 (различение HTTP 422 в опросе verifying) | OK | `ci._commit_not_found_in_origin` + правка `ci.verifying_status` — срабатывает только когда `check_runs` вернул `None` (не пустой список) и `why` содержит "422"; note называет причину и подсказывает `git push -u origin <branch>`. Не-422 сбои остаются нейтральными (тест-контроль есть). |
| 5 (зоны изменений) | OK | Diff ограничен `orchestrator/{fsm_advance.py, ci.py, fsm_merge_gate.py, gitcmd.py, github_adapter.py}`, `tests/`, `tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/*`, `docs/codebase-map.md` (регенерация). Ни один защищённый путь (`gates.yaml`/`roles.yaml`/`.github/`/`templates/`/`skills/`) не тронут. |
| 6 (тесты) | OK | Юнит-тесты на все узлы (`gitcmd.remote_branch_sha`, `github_adapter.ensure_head_in_origin`, `ci._commit_not_found_in_origin`/`verifying_status`) + 11 приёмочных тестов на настоящем git/bare-origin, покрывающих AC-1..AC-9. Полный `tests/` зелёный (см. «Проверено исполнением»). |
| 7 (тот же класс на входе merge_gate, общий хелпер) | OK | `fsm_merge_gate.py::_cmd_approve_merge_gate` вызывает ТОТ ЖЕ `github_adapter.ensure_head_in_origin` самой первой строкой тела (после `branch = t["branch"]`), на каждом заходе (включая повторные заходы `_cmd_approve_merge_gate_cycle` после `("wait", branch)` — проверено чтением `fsm.py`/`fsm_merge_gate.py`: возврат `("stopped",)` не читается вызывающим кодом как ошибка, цикл просто завершается, эскалации нет). Провал — `return ("stopped",)`, задача остаётся на `merge_gate`. Дублирования хелпера нет — один код на оба входа. |

Дополнительно проверены сценарии AC-1..AC-9 по отдельности (см. ниже) — все воспроизведены приёмочными/юнит-тестами и подтверждены прогоном.

## Замечания

Пусто — существенных дефектов не найдено.

## Реестр замечаний

Пусто — открытых записей нет.

## Вердикт

approved

Обоснование: все 7 требований и все 9 AC реализованы в точном соответствии с PLAN.md; отклонение PLAN от буквальной формулировки требования 1 («непосредственно перед `store.set_state`» → фактически до `store.update_task(reviewed_iter=...)`) обосновано и корректно — без этого сдвига AC-5 (повторный `advance` после починки origin) не работал бы, поскольку `reviewed_iter` съедал бы свежесть вердикта на первом же провале push. Приёмочный тест `test_ac4_ac5_push_failure_named_refusal_then_recovers.py` эмпирически подтверждает именно этот сценарий. Место вызова в `fsm_merge_gate.py` (самой первой строкой тела, на каждом заходе цикла) корректно закрывает требование 7 «в начале КАЖДОГО approve», включая повторные заходы после подтяжки main. Различение HTTP 422 в `ci.py` не путает легитимный пустой список проверок (`runs == []`) со сбоем ответа (`runs is None`) — отдельный тест это фиксирует. Ни один существующий гейт/лимit/guard не ослаблен: push выполняется только при реальном расхождении sha (регресс AC-1/AC-8 подтверждён и тестами, и содержимым diff). Откат тривиален (PLAN, «Влияние на систему»).

## Проверено исполнением

- `python3 -m unittest discover -s tests -v` — 1294 теста, все зелёные (фоновый прогон, ~124с).
- `cd tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests && python3 -m unittest discover -s . -p "test_*.py" -v` — 11 приёмочных тестов (AC-1..AC-9, включая оба метода AC-4/AC-5, AC-8, AC-9), все зелёные (~17с). AC-7 помечен легальным `# AC-7: skip` — регрессия уже покрыта штатным CI-джобом `tests/` (ci-covered класс, review-checklist).
- `python3 scripts/guard.py tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/PLAN.md` — `GUARD: ок (2 файлов)`.
- `python3 scripts/codebase_map.py` — прогнан локально для сверки: диф ограничен строкой `built_at_sha` (карта уже регенерирована коммитом 9d0c4e8 на этой ветке), содержимое совпадает — не дефект (built_at_sha не признак дефекта, review-checklist).
- Прочитаны `orchestrator/fsm_advance.py` (100-340), `orchestrator/fsm_merge_gate.py` (140-374), `orchestrator/ci.py` (1-230), `orchestrator/gitcmd.py` (1-60, 173-192), `orchestrator/github_adapter.py` (1-130), `orchestrator/fsm.py` (600-660) — сверены точки вызова хелпера, конвенция журналирования (`store.journal` сигнатура), обработка возврата `("stopped",)` циклом merge_gate, отсутствие двойного push/эскалации.

## Предложения системе

Пусто.
