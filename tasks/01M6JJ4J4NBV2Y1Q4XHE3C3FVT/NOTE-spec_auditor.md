# Записка spec_auditor

## Выяснено
- Факты SPEC о коде сверены: config.py:57, claude.py:45/:122(:114 — def), codex.py:136/:437-443, runner.py:1017/:1093, artel.py:2562, gitcmd.py:25, plank_helper.py:66-67, mutation_run.py:467, checkpoint.py:1393-1428 — верны. Неточность: `_push_plan` — gitcmd.py:1123, а :258-276 — GIT_GLOBALS_WITH_VALUE/GIT_BUILTINS.
- Тесты PATH (test_providers.py:260, test_multitarget.py:941, test_codex_login_shell_path.py:199-201, direct_git тест :575-581) проверяют только [0] и `git --version` — с обёрткой вторым элементом совместимы.
- tests/direct_git.py:56-58: при обёртке на PATH ускорение теряется наверняка (which git ≠ /usr/bin/git).
- Вердикт concerns: замер перенесён из SPEC в PLAN (против ТЗ п.6); AC не покрывают часть форм требований 2–3; AC-1 не ловит потолок на PROJECTS вместо ROOT; doctor п.7 может сам выполнить разрушительный git clean в ROOT; AC-10 не называет роли.

## Не сработало
- Bash с `cd`/`sed` под запретом — читал файлы через python3.

## Где остановился
- SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
- Нет единого места перечня команд пульта в role_prompt.py — команды разбросаны по docs_dir_note/suite_run_note/_reviewer_checks_note.
