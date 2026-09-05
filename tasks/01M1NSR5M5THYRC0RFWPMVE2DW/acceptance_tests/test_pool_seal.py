"""AC-1, AC-3, AC-4 (SPEC.md, требования 1-2) — команда `canary
pool-seal`: берёт открытый пул из `~/.artel-canary`, кладёт его
зашифрованным `openssl`-файлом `canary/pool.sealed` в репозиторий
пульта, ничего сама не коммитит, печатает число шаблонов и отпечаток
содержимого.

# AC-1: escalate — половина критерия («один зашифрованный файл,
# openssl внешней командой, не хранит открытый текст») протестирована
# ниже (`test_ac1_...`) без цитаты конкретного шифра; вторая половина
# буквы критерия («aes-256-gcm») ЭМПИРИЧЕСКИ ПРОВЕРЕНА неисполнимой —
# см. секцию «## Эскалация» в конце этого докстринга.

## Эскалация

### Вопросы (батч общий с AC-13, `test_pool_role_isolation.py`)
1. (САМЫЙ блокирующий, новый вопрос к контексту SPEC) `openssl enc`
   НЕ умеет AEAD-шифры вообще — проверено эмпирически В ЭТОЙ рабочей
   копии на ДВУХ реализациях `openssl` разом:
   - `/usr/bin/openssl` (LibreSSL 3.3.6, штатный macOS без какой-либо
     установки) — `openssl enc -aes-256-gcm ...` падает с `bad decrypt`
     на ЧИСТОМ ШИФРОВАНИИ (не расшифровке), при любой комбинации флагов
     (`-K`/`-iv` явным hex, `-pass`/`-pbkdf2`, с `-e`/без);
   - `/opt/homebrew/bin/openssl` (настоящий OpenSSL 3.6.3, из Homebrew —
     то есть уже ДОПОЛНИТЕЛЬНАЯ установка, которой требование 1 SPEC
     явно хотело избежать) — падает ИНАЧЕ, но так же однозначно:
     `enc: AEAD ciphers not supported` — команда `openssl enc`
     СТРУКТУРНО не поддерживает AEAD-шифры (нет способа передать/
     принять тег аутентификации через эту команду ни в одной из версий
     OpenSSL начиная с 1.1.0, где `-aes-256-gcm` был помечен
     experimental и позже явно отключён для `enc`).
   Обоснование SPEC («openssl — стандартный CLI-инструмент без
   дополнительной установки на macOS/Linux», требование выбора
   инструмента) верно ТОЛЬКО для наличия самого `openssl`, но не для
   конкретно `aes-256-gcm` через `enc` — эта комбинация не работает ни
   на штатном macOS, ни даже на настоящем свежем OpenSSL. Что делать?
   - (a) шифрование `openssl enc -aes-256-cbc -pbkdf2` (без AEAD) +
     отдельная аутентификация конкатенацией `openssl dgst -sha256
     -hmac <ключ>` (encrypt-then-MAC руками, тот же принцип, что дал
     бы AEAD) — остаётся В ПРЕДЕЛАХ голого `openssl`, без новой
     зависимости, ценой готового кода вместо одного флага;
   - (b) `openssl enc -aes-256-cbc -pbkdf2` БЕЗ дополнительной
     аутентификации — просто confidentiality, без целостности; проще,
     но слабее свойства, которое требование 1 подразумевало словом
     «AEAD»;
   - (c) пересмотреть отклонение `age` (обоснование его отклонения —
     «лишняя зависимость, openssl и так есть» — предполагало, что
     голый `openssl` тривиально даёт AEAD; раз это не так, вес довода
     меняется: `age` даёт AEAD «из коробки» одной командой, ценой
     установки инструмента, которого сегодня в пульте действительно нет).
   - Дефолт при молчании: вариант (a) — ближе всего к букве и духу
     требования 1 (AEAD-эквивалентная целостность, только `openssl`,
     без новой внешней зависимости), не самый простой в реализации.
2. (см. `test_pool_role_isolation.py`) — литерал `permissions.deny`
   для «команды расшифровки» (AC-13).

### Контекст
Обоснование выбора `openssl` в разделе «Контекст» SPEC написано
аналитиком ДО проверки конкретной команды `enc -aes-256-gcm` на
реальном инструменте — экспериментально это первая проверка данного
факта во всём проекте (грep по кодовой базе на `aes-256-gcm`/`enc
-gcm` вне этой задачи пуст). Ошибка небольшая по объёму текста SPEC
(один параметр одной команды), но меняет объём кода реализации
(вариант (a) — рукописный encrypt-then-MAC, не однострочный вызов) и
влияет на формулировку самого AC-1, которую тест обязан закрепить
буквально.

### Блокирует
`test_ac1_...` в этом файле проверяет ТОЛЬКО ту часть AC-1, что не
зависит от ответа (файл один, реально зашифрован, вызов внешнего
`openssl`); утверждение «шифр — именно aes-256-gcm» тестом не
закреплено до ответа на вопрос 1 — с любым из вариантов (a)/(b)/(c)
годится РАЗНЫЙ `assertIn`/иной способ проверки (наличие HMAC-тега,
иное имя шифра, другой внешний бинарник), закреплять один из них
раньше решения — то самое «подгонка под свой вкус», которую
escalation-rules запрещает.

Красен до реализации: команды `canary pool-seal` сегодня нет — `canary`
принимает только каталог ТЗ v1 (`orchestrator/canary.py::cmd_canary`,
позиционный `tz_dir`) и в текущем дереве ещё не несёт код пула v2
(часть 1, 01M1NEEWH5K1XPFRDGRMPYSBXJ, в этой рабочей копии не смержена
— см. TZ.md/контекст SPEC), так что `pool-seal` как первый позиционный
аргумент либо трактуется как каталог ТЗ и падает на «каталог не
найден», либо (после мержа части 1) — «в пуле нет файлов *.md»; в
обоих случаях `canary/pool.sealed` не появляется, и `test_ac1_.../
test_ac4_...` падают на `assertTrue(self.sealed_path.exists())`/
`assertRegex` соответственно.

`test_ac3_pool_seal_does_not_commit_the_sealed_file_itself` — честное
исключение, ЗЕЛЁНОЕ С РОЖДЕНИЯ вакуозно: «pool-seal не вызывает git»
тривиально верно и ДО того, как pool-seal вообще существует (звать
git неоткуда — команды нет), так что этот тест начинает нести
содержательную проверку только с момента появления самой команды
(тогда мутация «разработчик добавил `git add`/`git commit` внутрь
pool-seal» покраснила бы `self.git_spy.calls`), не раньше — тот же
класс неотличимости «нет фичи» от «фича есть и корректно не коммитит»,
что и в других файлах этой планки (см. `test_pool_restore.py`, AC-7).
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PoolBaseSandbox  # noqa: E402

TEMPLATE_A = "# Шаблон А\n\nСекретный маркер тела: alpha-marker-77213.\n"
TEMPLATE_B = "# Шаблон Б\n\nСекретный маркер тела: beta-marker-90542.\n"
TEMPLATE_C = "# Шаблон В\n\nСекретный маркер тела: gamma-marker-31488.\n"


class PoolSealTest(PoolBaseSandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            "a.md": TEMPLATE_A, "b.md": TEMPLATE_B, "c.md": TEMPLATE_C})

    def test_ac1_pool_seal_writes_one_encrypted_file_via_external_openssl(self):
        """`canary pool-seal` кладёт РОВНО ОДИН файл `canary/pool.sealed`
        в корне репозитория пульта; его байты не несут открытого текста
        шаблонов (реально зашифрован), а зашифровала его внешняя команда
        `openssl` (требование 1 SPEC: `subprocess`, тот же приём, что
        `keychain.py` для `security`), не питоновская крипто-библиотека
        в обход требования. Конкретный ШИФР (`aes-256-gcm` в букве
        AC-1) тестом НЕ закреплён — см. маркер эскалации в начале
        файла: `openssl enc` эмпирически не умеет AEAD-шифры вообще,
        нужно решение Оператора, каким именно способом добирать
        аутентификацию средствами голого `openssl`.

        Ловит мутацию: разработчик кладёт пул НЕзашифрованным (простое
        копирование каталога или конкатенация файлов) — `assertNotIn`
        по маркерам тела шаблонов ловит открытый текст; шифрование
        питоновской библиотекой (`cryptography`/`hashlib`+ручной XOR)
        вместо внешней команды — `run_mock`/`self.git_spy` (тот же
        `subprocess`) не увидели бы вызова `openssl` вовсе.
        """
        with mock.patch.object(subprocess, "run",
                              wraps=subprocess.run) as run_mock:
            output = self.seal()

        self.assertTrue(
            self.sealed_path.exists(),
            f"canary/pool.sealed не создан после pool-seal: {output}")
        self.assertTrue(self.sealed_path.is_file())
        # Ровно один файл пула в репозитории — не каталог с копиями.
        canary_repo_dir = self.sealed_path.parent
        self.assertEqual(
            [p.name for p in canary_repo_dir.iterdir() if p.is_file()
             and p.name != "guids.txt"],
            ["pool.sealed"],
            f"в {canary_repo_dir} лежит не один файл пула: "
            f"{sorted(canary_repo_dir.iterdir())}")

        sealed_bytes = self.sealed_path.read_bytes()
        for marker in ("alpha-marker-77213", "beta-marker-90542",
                      "gamma-marker-31488"):
            self.assertNotIn(
                marker.encode("utf-8"), sealed_bytes,
                f"canary/pool.sealed несёт открытый текст шаблона "
                f"({marker!r}) — пул не зашифрован")

        openssl_calls = [
            c for c in run_mock.call_args_list
            if c.args and isinstance(c.args[0], (list, tuple))
            and c.args[0] and Path(str(c.args[0][0])).name == "openssl"]
        self.assertTrue(
            openssl_calls,
            f"pool-seal не вызвал внешнюю команду `openssl` (требование 1 "
            f"SPEC): зафиксированные вызовы subprocess.run: "
            f"{run_mock.call_args_list}")

    def test_ac3_pool_seal_does_not_commit_the_sealed_file_itself(self):
        """`pool-seal` кладёт файл на диск, но НЕ коммитит его сама —
        требование 2 SPEC явно отделяет запись файла от коммита
        («коммит — Оператора, штатным путём»).

        Ловит мутацию: разработчик добавляет `git add`/`git commit`
        внутрь `pool-seal` «для удобства» — `self.git_spy.calls`
        (`tests.sandbox.SpyRun`, перехватывает `subprocess.run` —
        ОБЩИЙ атрибут модуля `subprocess`, тот же для `gitcmd` и для
        вызова `openssl` этой же командой, поэтому здесь фильтруются
        именно git-вызовы, а не вообще любой `subprocess.run`)
        перестанет быть пустым.
        """
        self.seal()
        git_calls = [c for c in self.git_spy.calls
                    if c and Path(str(c[0])).name == "git"]
        self.assertEqual(
            git_calls, [],
            f"pool-seal вызвал git самостоятельно: {git_calls} — коммит "
            f"принадлежит Оператору (требование 2 SPEC), не команде")

    def test_ac4_pool_seal_prints_template_count_and_content_fingerprint(self):
        """Вывод `pool-seal` называет число шаблонов пула (3 в этой
        песочнице) и несёт отпечаток (хэш) содержимого — строку из
        восьми и более hex-символов, не само число шаблонов.

        Ловит мутацию: разработчик печатает только число либо только
        отпечаток (забыл вторую половину требования 2) — один из двух
        `assertTrue`/`assertRegex` ниже падает.
        """
        output = self.seal()
        self.assertRegex(
            output, r"(?<!\d)3(?!\d)",
            f"вывод pool-seal не называет число шаблонов пула (3): {output!r}")
        hex_tokens = re.findall(r"[0-9a-f]{8,}", output.lower())
        self.assertTrue(
            hex_tokens,
            f"вывод pool-seal не несёт отпечатка (hex-хэша) содержимого "
            f"пула: {output!r}")


if __name__ == "__main__":
    unittest.main()
