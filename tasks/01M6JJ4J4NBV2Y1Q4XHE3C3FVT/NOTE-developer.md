# Записка developer (итерация 3, возврат с гейта мержа)

## Выяснено
- Причина: две обёртки на PATH (главная копия + рабочая копия) звали друг друга. Исправлено: `role_git.is_role_wrapper` (рядом `../role_git.py` или маркер `artel-role-git-wrapper` в `role_bin/git`); `real_git` пропускает любую обёртку; `runner._resolve_declared_tools` при `which("git")` = обёртка берёт `role_git.real_git`.
- Переменной вложенного вызова нет — п. 3 возврата отменён ANSWER-1.
- Тесты: `tests/test_role_git.py::TwoWrappersTest` (копия пакета обёртки во временном каталоге, оба порядка, таймаут 10 с, своя группа + RLIMIT_NPROC, шим-счётчик git ≤3), `RoleEnvForeignWrapperTest`. Мутации красят оба.
- Планка 119 passed; затронутые модули 160 passed.

## Не сработало
- Ничего; `cat` в Bash роли нет — читать через Read.

## Где остановился
- PLAN.md итерация 3, status: ready.
- Открытый момент: долгоживущий `test_ac16_wrapper_dir_second_in_role_path_before_git` краснеет только при прямом pytest с обёрткой ДРУГОЙ копии на PATH (его `_real_git` пропускает лишь свою) — описано в PLAN «Риски», файл залочен.

## Чего не хватило
- Нет готового помощника тестов для «процесс в своей группе под лимитом процессов» — написал `run_bounded` в test_role_git.
