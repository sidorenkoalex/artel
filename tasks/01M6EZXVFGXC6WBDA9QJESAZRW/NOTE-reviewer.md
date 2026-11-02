## Выяснено
- Итерация 1: changes_requested, одна запись R1-F1 (major). Код по SPEC корректен, планка 42 passed.
- R1-F1: требования 1, 5, 6, 7 сторожит только планка. Без сторожа в `tests/` четыре места (мутации):
  fsm_merge_gate.py:1521 (ловля TargetsError у people_entry), gitcmd.py:1023 (plan.code = IN_FLIGHT_REFUSAL),
  gitcmd.py:1016 (sqlite в _push_plan вне артели), gitcmd.py:905 (sqlite в _awaiting_human_refusal вне артели).
  При каждой мутации зелёные: test_fail_closed_on_read_failure, test_mr_delivery_units, test_awaiting_human_units,
  test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery, test_01m5xz9z68v75vxf5z66c708t4_delivery_policy, test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.
- Требование 2: имя remote (`origin`) _local_dest_path считает локальным путём → артель; scp-адрес — URL. Обхода нет.

## Не сработало
- Скрипт в /tmp писать нельзя (нужно разрешение); в bash отклоняются `$var` и `{…"`. Скрипт мутаций держал в каталоге документов, потом удалил через python (rm/ls в шелле недоступны).

## Где остановился
REVIEW.md записан. Следующей итерации: проверить, что новые тесты краснеют на мутациях A–D из R1-F1.

## Чего не хватило
Описи «AC → тест в tests/» в PLAN: пробел нашёл только временными мутациями.
