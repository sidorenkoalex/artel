# Записка test_author — 01M5DDTVZEA40ZB9BHEH4YDEE7

## Выяснено
- Долгоживущий tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py — AC-1..AC-14 (19 методов) на
  песочнице `OutcomeGateSandbox` (tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py) + сквозной
  `fsm.cmd_approve` задачи на `merge_gate` (подменены ci.branch_status — шпион, ci.main_line_status,
  github_adapter.ensure_draft_mr/undraft_mr). Разовый acceptance_tests/test_ac15_fail_to_pass_unchanged.py — AC-15.
- На базе ветки: AC-13, AC-14 и AC-15 зелёные (прежнее поведение), остальные красные из-за отсутствия кода.
- Временный стаб (гейт в fsm_merge_gate после «fresh» с базой merge-base(голова, _origin_main_sha), строка
  доказательства в PASSED_ACTION, строки пакета ревью, two_sided через _check_failure_kind) — все зелёные;
  мутации «база = diff_base», «ключ не сверяется», «гейт до _sync_main_or_wait» пойманы. Стаб откачен.
- Со стабом краснел существующий tests/test_component_report_gates.py::…merge… — как и предсказывает SPEC (треб. 8).
- Ключ компонента: acceptance.suite_result_key(<голова>^{tree}, decide(target).profile, root=выписка головы).
- Подсказка отказа подготовки на мерже ищется буквально: «повтори artel.py approve» (без двоеточия).
- preflight: все проверки пройдены; plank-run: 3 passed.

## Не сработало
- `pytest -n` — сторож роли запрещает; файл гонять последовательно (~2.5 мин, метод < 60 с).
- Карту кода (docs/codebase-map.md) роль не регенерирует: правка вне tests/ откатывается пультом.

## Где остановился
Шаг завершён.

## Чего не хватило
Где лежит планка после чекпоинта (каталог документов пустеет) — имя планки пришлось брать из `plank_text`.
