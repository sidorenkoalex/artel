"""Общая логика сканирования DNS-адресов для приёмочных тестов задачи
01M1QHQ277PQQA894X97RVEX9Y (AC-3, AC-6, AC-10).

Отдельная реализация от той, что разработчик поставит в защищённый
`tests/test_invariants.py` (структурный тест AC-6 — unified-diff-
приложение к PLAN.md, требование 3/AC-8): протокол «файл не содержит
`http(s)://<DNS-имя>` кроме `localhost`/`127.0.0.1`» проверяется здесь
СВОИМ кодом, не импортом из защищённого файла (которого на диске ветки
задачи нет и не будет до применения Оператором диффа) — тот же приём,
что `_util.py::refs_snapshot`/`diff_refs` в
`tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/
test_ac2_invariant_check_sensitivity.py`: испытывается СОСТОЯТЕЛЬНОСТЬ
правила (сканер находит нарушение и не путает loopback с DNS-именем),
а не наличие конкретного защищённого файла.
"""
import re

_URL_RE = re.compile(r"https?://[^\s'\"]+")
_EXEMPT_HOSTS = ("localhost", "127.0.0.1")


def _host_of(url: str) -> str:
    """Хост из `url` без схемы/порта/пути — точное значение, не префикс
    (AC-6: `127.0.0.1.evil.example` — DNS-имя, а не loopback, несмотря
    на общий префикс с исключённым `127.0.0.1`)."""
    rest = url.split("://", 1)[1]
    return rest.split("/", 1)[0].split(":", 1)[0]


def find_dns_addresses(text: str) -> list:
    """URL'ы `http(s)://<DNS-имя>` в `text`, кроме `localhost`/`127.0.0.1`
    (AC-6, требование 3) — список найденных совпадений в порядке
    появления."""
    return [m.group(0) for m in _URL_RE.finditer(text)
            if _host_of(m.group(0)) not in _EXEMPT_HOSTS]
