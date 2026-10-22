# Записка developer

## Выяснено
- `ls` в Bash недоступен — `find`/Read; `sed -i` требует подтверждения — правки только Edit.
- Сделано и зелено: guard (раздел «Заменяемые тесты»: REPLACED_TESTS_SECTION, ReplacedTest,
  is_test_id_form, parse_replaced_test_line, replaced_test_items, replaced_tests_errors в
  _content_errors; запреты: _BAN_TABLE/_table_arguments, suite с меткой; _test_calls `.each\``),
  spec_audit.signals, mandate.REPLACED_TESTS_ACTION/approved_replacements,
  fsm._replaced_tests_declaration + _approve_spec_gate, refusal_classes.REPLACEMENT_REFUSAL_ACTION,
  tests_writing._tests_writing_fail_to_pass_gate (сверка после _spec_anchor_check).
- guard_section_bans.py и replaced_approve.py — все зелёные.
- amend.py: LABELLED_REFUSAL снят; _rule_plank_errors (группа 2), _labelled_long_lived_errors
  (группа 3), _snapshot_plank_files (--from-branch), _trace_sources (долгоживущие парами при
  правиле не по умолчанию — без этого AC-1 долгоживущего .test.jsx не засчитан); guard.is_labelled_plank_test.
  amend_labelled.py — зелёный.
- AC-21: три метода переписаны на проход (Ac11: помощник assert_refused_without_writes заменён
  assert_passed + last_amend_detail; Ac25 — в методе), AMEND_REFUSAL только в assertNotIn; зелёные.
- PLAN.md написан (status draft), приложения проверены `git apply --check` (stdin) и симуляцией
  AC-22; карта регенерирована. plank-run: AC-15/AC-21 зелёные; AC-22 красен только потому, что
  PLAN.md ещё не в ссылке документов (попадёт автокоммитом шага).
- suite-run №1 запущен фоном.

## Не сработало

## Где остановился
- Далее: amend.py (снять LABELLED_REFUSAL, проверки файлов с меткой), три метода AC-21, PLAN.md
  с приложениями к templates/SPEC.md и skills/spec-authoring.md, карта.

## Чего не хватило
