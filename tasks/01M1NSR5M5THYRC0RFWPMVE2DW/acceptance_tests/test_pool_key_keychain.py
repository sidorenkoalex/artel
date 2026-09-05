"""AC-2 (SPEC.md, требование 1) — ключ шифрования пула добывается ТЕМ
ЖЕ механизмом, что токены ролей: `orchestrator/keychain.py::token`, не
переменной окружения, не файлом рядом с `pool.sealed`, не значением,
выведенным из содержимого пула.

Зелёный с рождения: ДО того, как `canary pool-seal`/восстановление
подключены вовсе (см. `test_pool_seal.py` докстринг модуля), оба
теста этого файла проходят — ВАКУОЗНО, не содержательно (честно, это
не «красный до реализации» — проверено прогоном с временным стабом
корректной реализации). `test_ac2_pool_seal_refuses_without_a_key_
in_keychain` видит `sealed_path` не созданным по причине «команды
`pool-seal` ещё нет» (та же причина, что и у любого другого AC этой
задачи), не по причине «код увидел `None` и отказал»; `test_ac2_
restore_uses_key_from_keychain_not_a_baked_in_secret` пропускает своё
единственное содержательное сравнение целиком (`if self.pool_dir.
exists()`), потому что восстановления тоже ещё нет. Это тот же класс
неотличимости «функциональности ещё нет» от «функциональность есть и
корректно ничего не сделала», что открыто описан в докстринге AC-7
(`test_pool_restore.py`) и AC-15 (`test_pool_role_isolation.py`) — оба
теста НАЧИНАЮТ нести содержательную проверку ровно с момента, когда
`pool-seal`/восстановление появляются вообще (тогда неверная реализация
— создание `pool.sealed` без ключа, совпадение расшифровки чужим
ключом — красит их по-настоящему, что и проверено стабом ниже), не
раньше; выдавать эту раннюю вакуозную зелень за «AC протестирован
готовым к разработке кодом» было бы нечестно, поэтому названо здесь
текстом.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import keychain  # noqa: E402
from _sandbox import PoolBaseSandbox, dir_fingerprint  # noqa: E402


class PoolKeyKeychainTest(PoolBaseSandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            "a.md": "# А\n\nтело шаблона А.\n",
            "b.md": "# Б\n\nтело шаблона Б.\n"})

    def test_ac2_restore_uses_key_from_keychain_not_a_baked_in_secret(self):
        """Печатает пул с ключом «key-A» (из `keychain.token`), стирает
        открытый пул, затем пробует восстановить его при ДРУГОМ значении
        `keychain.token` («key-B»): расшифровка обязана НЕ дать исходный
        пул — ключ приходит из keychain на каждый вызов, не запечён в сам
        `pool.sealed` и не выводится из его содержимого каким-то иным,
        не зависящим от keychain, способом.

        Ловит мутацию: разработчик один раз кладёт ключ в
        `pool.sealed`/рядом с ним и потом читает оттуда, игнорируя
        `keychain.token` при восстановлении, — расшифровка с «key-B»
        тогда ошибочно совпала бы с оригиналом, и `assertNotEqual`
        ниже упал бы.
        """
        original_fingerprint = dir_fingerprint(self.pool_dir)
        self.seal()

        import shutil
        shutil.rmtree(self.pool_dir)
        self.assertFalse(self.pool_dir.exists())

        self.pool_key = "key-B-not-the-sealing-key"
        with mock.patch.object(keychain, "token", lambda slot: self.pool_key):
            self.restore_via_init()

        if self.pool_dir.exists():
            self.assertNotEqual(
                dir_fingerprint(self.pool_dir), original_fingerprint,
                "восстановление другим ключом keychain дало тот же пул, "
                "что и оригинал — ключ не приходит из keychain на каждый "
                "вызов расшифровки")

    def test_ac2_pool_seal_refuses_without_a_key_in_keychain(self):
        """`keychain.token` возвращает `None` (слот не заведён, тот же
        контракт «нет — None», что и у `keychain.token` для токенов
        ролей, докстринг модуля) — `pool-seal` обязан отказать явно, не
        зашифровать пул placeholder-ключом и не создать `pool.sealed`
        молча с пустым/предсказуемым ключом.

        Ловит мутацию: разработчик не проверяет `None` и подставляет его
        (или `""`) в вызов `openssl` как есть — тогда `pool.sealed`,
        скорее всего, всё равно появится (либо `openssl` упадёт ПОСЛЕ
        частичной записи файла) — оба исхода ловит `assertFalse` ниже.
        """
        with mock.patch.object(keychain, "token", lambda slot: None):
            output = self.seal()

        self.assertFalse(
            self.sealed_path.exists(),
            f"pool-seal создал canary/pool.sealed без ключа в keychain: "
            f"{output!r}")


if __name__ == "__main__":
    unittest.main()
