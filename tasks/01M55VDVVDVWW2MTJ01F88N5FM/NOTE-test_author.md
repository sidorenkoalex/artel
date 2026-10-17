# Записка test_author — 01M55VDVVDVWW2MTJ01F88N5FM

## Выяснено
- Все AC-1..AC-6 — свойства кода: один долгоживущий файл
  tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py;
  acceptance_tests/ пуст (plank-run поэтому отвечает «планки нет» — штатно).
- Песочница — образец tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py
  (RealGitSandbox + add_synced_origin + make_project_repo + workspace.ensure +
  checkpoint.commit_step_artifacts + fsm.cmd_advance) и
  tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py (answer.cmd_answer).
- tests/mandate_matrix.py кладёт в «Чем покрыто после» `tests/mandate_matrix.py:1`
  — у внешнего проекта после требования 4 это не покрытие; в файле матрица своя.
- AC-3: после answer в in_dev переход держит гейт неотработанного ANSWER
  (review.py::_answer_gate) — тест пишет в журнал «agent run finished» developer.
- AC-4 «отказ»: испорченное подполе test_profile ломает разбор targets.yaml
  целиком → решение «контекст не разрешён» (тоже refusal). Ожидаемый текст
  тест берёт из project_profile.for_task(...).refusal/.skip.
- Стаб (решение профиля в mandate.refusals + scope в matrix_refusals обоих
  каналов, у артели прежний текст) — все 6 методов зелёные, стаб откачен.
- До реализации: красны AC-2, AC-3, AC-4, AC-6 и внешняя половина AC-5;
  AC-1 и артельная половина AC-5 зелёные. preflight — всё «пройдена».

## Не сработало
- Bash: cat/ls недоступны, составные команды требуют одобрения — только
  одиночные grep/python3/git.

## Где остановился
- Готово к сдаче. Карту docs/codebase-map.md не регенерировал: правку вне
  tests/ пульт откатил бы — это шаг разработчика.

## Чего не хватило
- Гейт неотработанного ANSWER на пути in_dev -> verifying нашёлся только
  прогоном стаба.
