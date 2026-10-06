---
task: 01M48WR0HKZW8KJCBWDZTFC4ZY
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Тесты не спят в паузе повтора агента (ревизия тестов TR-1, TR-26)

## Фаза A: план
- Таблица покрытия полна: требования 1–9 SPEC сопоставлены шагам 1–5 или явному «не меняется». Шаги размером с MR.
- Подход (заместитель ссылки `runner.time` через уже существующий `patch_sleep`/`TimeWithSleep`) не противоречит сторожу `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`: глобальной подмены `time.sleep` нет, и прогон сторожа зелёный.
- «Влияние на систему» совпадает с диффом: изменены только `tests/sandbox.py`, `tests/test_agent_prompt.py`, `tests/test_review_freshness.py`, новый `tests/test_sandbox_retry_pause.py` и карта. `orchestrator/` не тронут. `tests/test_agent_failure.py` и `tests/test_invariants.py` в диффе ветки отсутствуют (`git diff c8548dab...HEAD --stat` по ним пуст). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `TmpRootTest.setUp` накладывает `patch_retry_pause` (`tests/sandbox.py`, `setUp`); долгоживущие `test_ac1_*`/`test_ac7_*` зелёные |
| 2 | OK | Флаг класса `REAL_RETRY_PAUSE = True`; своя `patch_sleep(runner, …)` ложится поверх умолчания и видит прежние длительности (`test_ac2_*`, `tests/test_agent_failure.py` зелёные) |
| 3 | OK | Точечный `patch_retry_pause` в `setUp` `PromptChannelTest` и `ReviewFreshnessScenarioTest` |
| 4 | OK | Приложение в PLAN: `git apply --check` rc 0, правка в `FsmTest.setUp`, которую наследуют три класса из пунктов 1, 2, 9 |
| 5 | OK | Строки `assert` существующих методов не тронуты: правки только в `setUp` и импортах. Планка AC-6 зелёная |
| 6 | OK | Время не утверждается. Замер в PLAN дан как сведения |
| 7 | OK | Сторож — долгоживущий `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py` плюс юнит-тесты `tests/test_sandbox_retry_pause.py`. Заявки подтверждены временной мутацией |
| 8 | OK | `tests/test_agent_failure.py` не изменён, прогон зелёный |
| 9 | OK | «Предложения системе» PLAN называют обе строки бэклога (планка AC-8 зелёная) |

## Замечания
Блокирующих, major и minor замечаний нет.

Проверено и дефектом не является:
- Расширение `patch_pult_sleep` на модули с `TimeWithSleep` поглощает и паузу `runner` внутри `TmpRootTest`. Без него счётчики `patch_pult_sleep` (например `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`) потеряли бы паузу. Прогон зелёный, условие только расширено. Мутация «ветки заместителя нет» ловится тестом `test_pult_sleep_patch_overrides_the_default`.
- Через `grep` проверены другие обращения к `runner.time` и `"time.sleep"` в `tests/`: остались только явные `patch_sleep(runner, …)`. Они ложатся поверх умолчания, а `TimeWithSleep.__getattr__` по-прежнему отдаёт `monotonic`/`time`.
- Юнит-тесты `tests/test_sandbox_retry_pause.py` не повторяют долгоживущий файл: они проверяют флаг отказа, совместимость с `patch_pult_sleep` и подмены в двух голых классах. Шаг роли проверяет только долгоживущий файл.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `git apply --check -v` приложения из PLAN.md, извлечённого в /tmp: `Checking patch tests/test_invariants.py...`, rc 0.
- `python3 -m pytest -q tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py tests/test_sandbox_retry_pause.py tests/test_sandbox_time_with_sleep.py tests/test_agent_prompt.py tests/test_review_freshness.py tests/test_agent_failure.py tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py tests/test_sandbox.py tests/test_multitarget.py tests/test_multitarget_invariants.py tests/test_agent_log.py tests/test_analyst_role.py tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`: 225 passed, 97 subtests passed за 17.01 с.
- `artel.py plank-run 01M48WR0HKZW8KJCBWDZTFC4ZY`: 5 passed, код выхода 0.
- Временные мутации `tests/sandbox.py` с прогоном `tests/test_sandbox_retry_pause.py`, долгоживущего файла и `..._profile_refusals.py`. После каждой мутации код возвращён, `git status` чистый:
  - `REAL_RETRY_PAUSE = True` по умолчанию: 4 failed, среди них `test_default_records_pause_instead_of_sleeping` и `test_ac7_sandbox_step_does_not_sleep_on_retry`;
  - `patch_pult_sleep` без ветки `isinstance(module_time, TimeWithSleep)`: красный `test_pult_sleep_patch_overrides_the_default`;
  - флаг игнорируется (`if True:`): красный `test_opt_out_keeps_the_real_sleep`.
- Удаление `pause_patcher.start()` из `setUp` `tests/test_agent_prompt.py`, затем из `tests/test_review_freshness.py`: красный подтест своего класса в `test_plain_sandboxes_patch_the_retry_pause`. Код возвращён.
- CI коммита 507b606c зелёный (16 проверок, по пакету).

## Предложения системе
- Песочница роли запрещает в Bash heredoc с `{…}` и `$var` (детектор «expansion obfuscation»), а запись в /tmp через Write требует подтверждения. Из-за этого приём «временная мутация» из review-checklist приходится выполнять через `python3 - <<'EOF'` без словарей. Стоит дать в скиле готовый скрипт мутации (адрес: `skills/review-checklist.md`, раздел «Сторож — проверен временной мутацией»).
