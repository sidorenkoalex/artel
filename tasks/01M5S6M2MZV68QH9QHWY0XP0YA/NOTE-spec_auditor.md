# Записка spec_auditor — 01M5S6M2MZV68QH9QHWY0XP0YA

## Выяснено
- Факты SPEC о коде подтверждены: project_profile.py:535-557 (VitestFlags, таблица), :610-631 (test_id/parse_test_id); acceptance.py:656-685 (_vitest_head, каталог cache:680-684); pult_vitest_reporter.js:48-56/:74/:92; agent_log.py:259-260; advance_gates/acceptance.py:344-349; tests_writing.py:1185-1188; tests/test_report_outcome_module.py:1487.
- ADR-0026 пп. 2–3 уже поправлены (e503fe10, строки 28, 30, 31).
- Мандат на гейте SPEC принимает answer.py:428-435 (_spec_gate_answer_text); матрица нужна в тексте ANSWER (mandate.py:665).
- node не объявлен в stack.DECLARED_TOOLS (python3, git, gh, claude); в PATH роли (runner.py:1103) node есть случайно — /opt/homebrew/bin, v26.10.0.
- Единственный существующий тест на находку повтора использует #2 (tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py:92, 1061) — правка гейтов n>=2 его не трогает.

## Не сработало
- Bash с $VAR и `cd ... &&` в составной команде требует подтверждения — абсолютные пути, по одной команде.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns, status ready.

## Чего не хватило
- Какой гейт гоняет tests/outcome_gate_sandbox.py (FAIL_TO_PASS tests_writing или приёмка) — AC-15 его не называет.
