# Записка spec_auditor

## Выяснено
- Аудит круга 4 (SPEC sha 1ce5b3d1, после решений №3.1–№3.3). Решения №3.1–3.3 отражены (AC-7 короткие строки, AC-3/5/6 up/run+поле+значение, AC-6 второй сервис).
- Факты кода на c6940f280 подтверждены заново: acceptance.py:222-224, 830-834 (начинается «1: »), 944-955, 1049-1117, 1114, 1286, возврат 1290-1291, 3676. Тесты ядра: @TREE@ = dirname(project-directory) (compose_run.py:143-148), self.tree = sandbox.root (:262), sandbox.py:1946 resolve; test_ac15 (:1723) литерал не держит.
- Опыт realpath повторён: r.git#main в дереве; ../.. → сосед; ссылки; '' → cwd; None → TypeError.
- Отклонения (concerns): build.cache_from/cache_to type=local (путь машины, не в SPEC и не в «Не входит»); pid/ipc `container:`/`service:` (чужое пространство имён); к сведению — ссылка :1287-1290 в треб. 3, сервис не словарь → AttributeError (:1090). guard ок.

## Не сработало
- awk в Bash просит подтверждения; ls недоступен.

## Где остановился
- SPEC-AUDIT.md сдан (ready, concerns).

## Чего не хватило
- docker нет — поведение cache_to type=local опытом не проверено.
