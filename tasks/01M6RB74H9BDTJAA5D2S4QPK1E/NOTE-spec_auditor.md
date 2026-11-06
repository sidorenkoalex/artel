# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок.
- Д-1: требование 4 краснит tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:161 и tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:399[gitlab-target-human] (GitLab + token_slot без commit_author, new обязан выйти 0) — мандата нет.
- Ф-1: gitcmd._author_check_refusal (gitcmd.py:656) требует commit_author.name == username токена; автопоиск пишет name = отображаемое имя -> первая отправка ветки откажет.
- Ф-5: ветка задачи заводится от fetch с --refmap= (workspace.py:286, gitcmd.py:2144-2154) — ссылки слежения отстают, сверка «достижим из refs/remotes/origin/*» ложно откажет на чужих коммитах main.
- Ф-2/Ф-3: target-set не пишет machine.commit_author (projects.py:784-789, :889-893), хелперы выходят sys.exit — в doctor --fix обрыв всего doctor.
- В-1: исход «поля нет + API не ответил» не задан. Д-3: место сверки до gitcmd.py:1361 ломает tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_gate.py:1047. Д-4: ROLE_SKIP для новой строки не потребован.

## Не сработало
- Опыт git во временном каталоге: запуск sh-скрипта и Bash с $VAR/cd требуют подтверждения.

## Где остановился
- Готово.

## Чего не хватило
- Права запустить опыт git (Ф-5 подтверждён кодом, не опытом).
