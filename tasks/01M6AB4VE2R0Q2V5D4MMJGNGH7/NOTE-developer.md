# NOTE developer (визит 2, после ANSWER-2)

## Выяснено
- ANSWER-2 закрыт в коде (незакоммичено — коммитит пульт):
  - п. 1: test_ac15 Б2.1б правлен по мандату (+mr_status, предел 1 чтения, докстринг). Тело гейта повторяется после ожидания CI → mr_status читался дважды; одно чтение за approve — ContextVar `_mr_incident_checked` в `_cmd_approve_merge_gate_cycle` (fsm_merge_gate.py).
  - п. 2 (б): сбой mr_status → `_people_refusal(MR_REFUSED_ACTION, "статус MR не прочитан — …")`, задача на merge_gate. Тест tests/test_mr_sync_units.py::test_gate_refuses_when_mr_status_unread (фикстура `stand` импортом из test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery).
  - п. 3 (б): первая сверка — тоже запись «mr-sync: итог сменился» («(первая сверка) → итог», mr_sync.FIRST_SYNC). Тест FirstSyncNotifiesTest.
- П. 2 (б) краснил ещё 4 теста delivery-файла (ac9, ac11×2, ac13): FakeForge.__getattr__ отвечал на mr_status отказом. Добавлен метод FakeForge.mr_status (открытый MR; fail["mr_status"] — отказ) — ВНЕ мандата → PLAN снова status: escalate (1 вопрос, дефолт — принять).
- Зелёные: 3 долгоживущих файла + delivery (36) + units — 97; test_invariants/awaiting_views/awaiting_commands/test_watch — 114; invariants с приложением — 88. Мутации трёх новых сторожей проверены. Карта регенерирована.

## Не сработало
- Bash-сторож отклоняет heredoc с `$`/f-string `{…}` внутри строк («simple_expansion») — длинный текст PLAN писать через Edit.

## Где остановился
PLAN status: escalate (вопрос о методе FakeForge.mr_status). При ответе (а) — только status: ready, код не менять. При (б) — вернуть в `_mr_incident_stops` журнал+return False, убрать FakeForge.mr_status и тест unread.

## Чего не хватило
Что тело гейта target-human исполняется дважды за approve (заход до ожидания CI и после) — видно только по журналу подделки.
