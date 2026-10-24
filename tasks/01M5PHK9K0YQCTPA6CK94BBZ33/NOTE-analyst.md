# Записка analyst

## Выяснено
- Итерация 2 (возврат аудита, 5 отклонений). Сверка AST на ed38d987: при другом ast.dump совпадают GATE_ACTIONS (:81 / id :63–64), VITEST_KIND (:162–170 / :121–124), spec_text (:181–188 / :135–140) и оператор `from orchestrator import …` (:62–63 / :49–50; те же модули — не переименовывать). Дословно совпадают 17 не-импортов: REAL_POPEN, CROCKFORD, LETTERS, PLANK_DIR, VITEST_BIN, VITEST_REPORT_ARGS, LONG_TEMPLATE, OUTCOME_ACTION, APPROVED_DETAIL, CLAIM, ENTRY_HEAD, PLAN_READY, MATRIX_HEADERS, ulid, flow, arg_value, js_source.
- IdOutcomeGateSandbox :167–516; её помощники исхода — gate_refusal (:503), no_gate_refusal (:513, текст как у outcome, но GATE_ACTIONS другой → id_no_gate_refusal); подготовка — in_dev_task (:363), operator_mandate (:451).
- Помощники без утверждений тестовых классов: Ac4PrepareTest.prepared :1121, Ac11MandateTest.broken_task :2263; assert_prepare :1134 зовёт self.refusal.
- mutation-run пишет лог каждого патча (`_log_path(..., f"-{label}")`, mutation_run.py:465) — по нему PLAN может назвать упавшее утверждение.

## Не сработало
- guard: «AC-6.» в начале строки внутри текста AC — повтор номера; ссылки на критерии не ставить в начало строки.

## Где остановился
- SPEC.md исправлен по отклонениям 1–5 (контекст :47–78, п.3, п.7, п.9, п.16, AC-3, AC-7, AC-8, AC-9, AC-18, «Не входит»), status: ready, guard ок.
- Решения итерации 2: совпадающие дословно 17 имён — одно определение (копия или импорт, выбор роли); вызов помощника из помощника — голым именем; prepared/broken_task — функции модуля теста; карта — только генератором.

## Чего не хватило
- Список совпадающих имён в ТЗ был неточен — сверять AST самому.
