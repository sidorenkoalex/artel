# Записка spec_auditor

## Выяснено
- Аудит №6 (spec_sha 40895667…), вердикт concerns. П-1 и П-2 аудита №5 закрыты: AC-1 SPEC.md:181–185, AC-7 :248–253, ссылки на stale_cycles больше нет.
- Р-1: SPEC.md:41–44 (role_nproc_limit зовёт _spawn_and_wait, то есть каждая попытка) противоречит :91–94 (один раз до _run_attempts, runner.py:333/889).
- Р-2: сигнатура runner.role_nproc_limit не задана, а тесты AC-1/3/4/7 зовут её напрямую. Предложено `role_nproc_limit() -> int`.
- Подмены spawn_agent в tests/ принимают **kwargs. В Popen пробрасывают только не-claude argv, поэтому nproc_limit их не ломает.

## Не сработало
- В Bash отклоняются cd+git, ls, cat; grep и sed по абсолютным путям работают.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Ничего существенного.
