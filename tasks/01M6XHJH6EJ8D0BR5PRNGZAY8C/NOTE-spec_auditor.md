# Записка spec_auditor 01M6XHJH6EJ8D0BR5PRNGZAY8C (визит 3, SPEC fa883b5a)

## Выяснено
- Пять отклонений визита 2 SPEC закрыл решениями второго круга (sandbox_sources, межфайловые цепочки, принятый пробел, 4 пути AC-6, несколько меток/AnnAssign).
- Новое: (1) ни один AC не ловит «правила размера исполняются до фильтра группы» (рядом с линтом, guard.py:4469) — тогда файлы планки на :518/:198/:293 краснеют; (2) _is_pytestmark_assign/_pytestmark_marks общие с гейтом неослабления и стилем (guard.py:1417, :1512, :2160, :4670) — AnnAssign в общем помощнике меняет их, а «Не входит» запрещает менять стиль; (3) путь amend.py:317 достижим только у записи components (long_lived_rule требует long_lived_template, project_profile.py:725), значит size_marks нужен компоненту, а требование 1/AC-8 — только про test_profile; (4) TmpRootTest подменяет config.ROOT (tests/sandbox.py:92) — при None и отсутствии файлов guard не должен падать; (5) мелочь: isolate_pult_db на :720, не :718.
- amend :725 имеет два механизма lint_base: worktree — голова кодовой ветки (:1097), from-branch — _locked_long_lived_texts (:1363); у :317 оба режима (:1090, :1355).

## Где остановился
SPEC-AUDIT.md: verdict concerns, status ready.

## Не сработало
- ls и составные команды через ; в Bash отклоняются.

## Чего не хватило
- Где в amend живёт база для :317 в каждом из двух режимов — искал дольше всего.
