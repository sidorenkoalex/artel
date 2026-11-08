# Записка spec_auditor

## Выяснено
- Круг 3 (spec_sha 2fef468d): решения Оператора №2.1–№2.4 внесены в SPEC полностью; адреса guard.py:1985/2036/2163-2177/2228/4399-4407/4618/4916-4930, sandbox.py:711/1609/2534/2539/2568, test_lint.py:290-296, report_outcome_sandbox.py:335, outcome_gate_sandbox.py:251, fixtures.py:42 верны.
- `pytest_style_errors_from_files` вызывается только из `long_lived_errors_from_files` (guard.py:4462), без `sandbox_sources`; вызывающие (tests_writing.py:519-526, :651-662, preflight.py:261-300, amend.py:301/1125/1390) передают дерево кодовой ветки только в `long_lived_errors_from_files`. SPEC не требует проброса — при `None` перечень берётся из `config.ROOT` (корень пульта, не дерево ветки). Не ловится ни одним AC. При пробросе tests_writing.py:651-652 передаёт `{}` при выключенном size_marks (у артели required, targets.yaml:56).
- pytest 9.1.1: `scope` у `pytest.fixture` только ключевой — позиционной формы нет.
- Существующие тесты не ломаются: `scope=` фикстур и `shared_readonly(` — только в образцах test_01m6xhm9…_shared_readonly.py (не проверяется правилами); тесты размера метками acceptance_tests/ с «Группа: долгоживущий» не пользуются.

## Не сработало
- Bash с `;`/`|` между командами частично требует одобрения; cd в /tmp запрещён.

## Где остановился
- SPEC-AUDIT.md сдан, verdict concerns.

## Чего не хватило
- В SPEC нет указания, кто передаёт `sandbox_sources` в `pytest_style_errors_from_files` на реальном пути (guard.py:4462).
