# Записка test_author — 01M568XFYM68EYHH0C16Y7D7F0

## Выяснено
- Все AC-1…AC-9 — свойства кода kill: один долгоживущий файл tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py; acceptance_tests/ пуст (plank-run отвечает «планки нет», preflight — все проверки пройдены).
- Подставной `gh` — исполняемый скрипт в начале PATH (ci.gh зовёт `gh` по имени, env = os.environ + GH_TOKEN). Журнал событий общий с хуком pre-receive bare-origin проекта → порядок строк = порядок событий (AC-2).
- `git -c http.lowSpeedLimit=1 -c http.lowSpeedTime=2 push http://127.0.0.1:<порт>/…` на молчащем сервере обрывается за ~2 с, stderr «Operation too slow…» — проверено.
- AC-6: подставной HTTP-хостинг на `git http-backend`, молчит только на POST receive-pack с удалением ветки задачи (сверка документов и коммит закрытия kill ходят в тот же origin и пределов не имеют).
- AC-5: пустой слот с начала kill → kill отказывает ещё на сверке документов (`_refuse_unsynced_docs`, ls-remote хостинговый), поэтому слот пустеет, когда задача уже killed.
- Стаб (функция уборки, вызываемая из `_cmd_kill` при `won`; `ci.gh("pr","close",branch,"--comment",…, repo=url)`; `gitcmd.in_repo(repo,"-c","http.lowSpeedLimit=1","-c",f"http.lowSpeedTime={config.GH_TIMEOUT_SEC}","push","origin","--delete",branch)`; база в тексте — `_base_of(repo)`) — все 11 зелёные; мутация «без lowSpeed» ловится AC-6 (22 с > 14 с). Стаб откачен.

## Не сработало
- Составные bash-команды требуют подтверждения; ls/cat нет в PATH оболочки.

## Где остановился
- Планка готова: 8 красных по причине отсутствия кода, AC-7 и AC-9 (а), (б) зелёные с рождения.

## Чего не хватило
- Готового подставного HTTP-хостинга git в tests/sandbox.py нет — написан в самом файле.
