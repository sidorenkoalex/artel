# Записка spec_auditor (визит 3, SPEC 3e389bdb)

## Выяснено
- Отклонения визита 2 закрыты; ссылки SPEC на код сверены (acceptance.py, two_sided, fsm, amend, suite_lock, перечень 43 фикстур) — совпадают.
- amend.py:715,718 -> run_cwd = config.ROOT (acceptance.py:439): при required «каталог прогона» = корень пульта с БД; SPEC не оговаривает (отклонение 1).
- AC-7, AC-9..AC-13 для полного набора не вошли ни в D1а-1б (только точечные), ни в D1а-2 (AC-15..20); таймаут полного набора сейчас _kill_group (acceptance.py:1334,1388) — контейнер не снимет.
- «Проект не определён» в коде не бывает: store.task_target/workspace.task_target -> artel по умолчанию (store.py:701-707, workspace.py:52-58).
- Profile строится из test_profile; sandbox — поле записи; у записи без профиля Profile нет (project_profile.py:145-146).
- Файлы блокировки не названы; хеш на проект против многих деревьев прогона.
- Ключ: image имя с тегом — пересборка под тем же тегом даёт повтор итога.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, 8 отклонений; guard ок.

## Чего не хватило
- Определения «проект задачи не определён» и куда идёт cwd=None у amend — искал дольше всего (acceptance.run:439).
