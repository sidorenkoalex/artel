# Записка spec_auditor

## Выяснено
- `_read_decision_file` на 32ec975d — fsm.py:1934-1940, не 1928-1934 (SPEC/ТЗ).
- Ветвление approve на spec_gate: fsm.py:1486 (деление), 1491-1492 (skip_tests/AC), 1507 (set_state tests_writing) — подтверждено.

- blob sha SPEC = f545e41c… совпал; guard.spec_unclassified_paths(SPEC) = [].
- НАХОДКА: `watch` НЕ печатает запись указания вовсе — `watch._matches_class` (watch.py:227-253) знает только state ->, гейты, отказы, agent run, бюджет, auto, CI, pytest; watch.py вне зон. И `safe_text` (watch.py:268) экранирует переводы строк. Требование 10 («watch и log печатают деталь целиком») ложно для watch. `log` (catalog.py:1566-1575) печатает целиком — верно.
- Белый список ролей — «не граница» по докстрингу `_refuse_if_role_restricted` (artel.py:2616+); ТЗ факт 3 «роль подделать не может» завышен, но тот же доверительный канал у reject-причин.
- answer на spec_gate отказывает строкам зон/merge_after (answer.py:239-256) — отказ --note, «называющий answer <id> <файл>», для этих маркеров ведёт в тупик.
- Смещения строк (HEAD=32ec975d): _read_decision_file 1934-1940 (не 1928); review ANSWER-цикл 969-975 (не 965-971); «данные» 935 (не 925-930); journal reviewer 852-861; mandate.py:719; test_integrity.py:1096.
- Красная фаза: `--note` до кода берётся за sha (spec_gate в APPROVE_NEEDS_SHA, fsm.py:844) → confirm_fixation; при пустой фиксации проходит дальше; skip_tests-путь зовёт _maybe_ensure_draft_mr (gh/push) — SPEC не велит глушить.

## Не сработало
- grep с `\|` и `cd ...;` в Bash требует подтверждения — использовать `grep -n -e ... -e ...` без cd.

- Повтор проверок под lease (треб. 1, 3) не покрыт ни одним AC.
- Критерий ТЗ «зелёные без правки» SPEC унёс в «Не входит».

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. Шесть пунктов вердикта.

## Чего не хватило
- Какие классы событий печатает `watch` (watch.py:36-44, `_matches_class`): без этого утверждение ТЗ/SPEC про `watch` не проверить.
