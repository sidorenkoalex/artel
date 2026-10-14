---
task: 01M4XVM49PP5WHSXT5S8JW85WN
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

# ANSWER: разрешённая capability-проба доверенного канала C

Оператор14.10 разрешил подготовку расширения доверенного канала и пересмотра ADR/SPEC без ослабления проверок/лимитов. Выбран C как исследовательский этап ADR-0025. Продуктовая реализация нового broker пока не разрешена этим ответом: сперва проверяем доступность в настоящей среде роли. Политика UNKNOWN и новый SPEC остаются на согласование.

Developer: выполнить только ограниченную IPC-пробу из реальной инструментальной команды Codex (вложенный shell/новая сессия), без полных tests/, изменения кода/SPEC/планки/прав песочницы. Вне sandbox запущен временный broker PID15302, endpoint /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/cap-probe-14.sock. Его PID и путь — данные конкретной пробы, не постоянное удостоверение и не разрешающий token. Проба использует kernel peer PID; broker читает ancestry/start-time вне sandbox и сравнивает с текущим lease.pgid. Endpoint находится в существующем suite-run каталоге; если connect/peer credentials запрещены — зафиксировать точный отказ, не обходить и не менять права. Пробу выполнить сразу, broker ждёт ограниченное время.

Пример одноразового клиента через stdin (можно адресно адаптировать для надёжного ограниченного чтения):
```python
import json,os,socket,struct
s=socket.socket(socket.AF_UNIX);s.settimeout(5)
s.connect('/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/cap-probe-14.sock')
assert struct.unpack('i',s.getsockopt(0,2,4))[0]==15302
s.sendall(json.dumps({'pid':os.getpid(),'ppid':os.getppid(),'pgid':os.getpgrp(),'sid':os.getsid(0)}).encode())
parts=[]
while True:
 part=s.recv(65536)
 if not part:break
 parts.append(part)
 assert sum(map(len,parts))<1048576
s.close();print(json.loads(b''.join(parts)))
```

После пробы сохранить фактический результат в PLAN/NOTE: доступIPC, kernelpeer, ancestryдоактивногоagentanchor, топологияshell; не выдавать успешную macOS-пробу за Linux/Claude или за готовую productionреализацию. Если новый SPEC ещё не согласован, оставить PLAN status: escalate с фактическим handoff для аналитика. Никаких fallback на ENV/одинPGID или нового продукта до согласования. Потолок45 и старые проверки сохраняются.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| Источник контекста, исследованиеC | СтарыйPGIDнеудостоверяетвложенныйCodex | Исследуется усиление | НастоящаяIPC-пробаpeerPID/ancestry, пока не productionтест | Не объявлятьреализацию |
| Sandbox/ps | Запретpsвролинеснимается | Да | IPCвсуществующихправах, processAPIтольковне sandbox | Приdenied остановиться |
| Тесты/лимиты/гейты | ТекущийSPEC,ADR0024,старыеassertions | Да | Вэтойпробе неизменны | Безослабления/ростапотолка |
| UNKNOWN/операторfull | Новыйoutageисходещёнепринят | Требуетсярешение | ЧерновикADR0025/SPECпредложение | Не внедрять досогласования |

Независимая проверка: canary_orphan_tz_audit — pass ADR-0025 как рамки исследования; продуктовый выпуск не согласован. Этот ответ разрешает только ограниченную capability-пробу по текущему мандату Оператора.
