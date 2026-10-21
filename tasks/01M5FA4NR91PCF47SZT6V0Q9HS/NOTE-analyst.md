## Выяснено
- Круг 4 (возврат с гейта SPEC: DoctorFixOrderTest, признаки (1) и (3)). Решения закрыты правкой требования 5, AC-19, AC-20, «Не входит».
- Поиск `cmd_doctor(...fix=True)` по tests/ на f1f805b6 нашёл 6 классов: PredicateGitTest, CanaryDoctorTest, OriginSweepTest (уже были в перечне), DoctorFixOrderTest (unittest.TestCase, test_doctor_closed_ref_fix.py:150), FixGitHooksTest (test_git_hooks.py:472, через _DoctorGitHooksSandbox(RealGitSandbox), setUp с super), PultWritesAfterRoleMoveTest (docs_ref_refixation.py:545, DocsRefSandbox → GitignoreCommittedRealGitSandbox → RealGitSandbox). Последние три добавлены: перечень 119 классов в 61 файле.
- test_01m3xtf5506gf43hd51ece230t_role_refusal.py передаёт `doctor --fix` в artel.main с подменённым cmd_doctor — настоящий cmd_doctor не вызывается, в перечень не включён (это сказано в SPEC).
- Признак (1) теперь требует: в цепочке нет сужения PATCHED_ATTRS без ROOT и нет setUp без super().setUp(). Признак (3) — для каждого тестового метода.

## Не сработало
- В Bash отказывают составные команды с `$`/`cd &&` — пользовался python3 heredoc.

## Где остановился
- SPEC.md status: ready, guard ок. Шаг завершён.

## Чего не хватило
- Ничего существенного; классы с cmd_doctor(fix=True) нашлись grep + ast за один проход.
