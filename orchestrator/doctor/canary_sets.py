"""Согласованность наборов ролей канарейки (SPEC
01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 9).

Набор живёт в локальном слое пульта (`canary_sets:`, файл ВНЕ git) и
читается прогоном `canary --k <N> --set <имя>`. Без этой строки опечатка
в имени роли, модель, выпавшая из каталога, и провайдер вне реестра
обнаруживались бы только на самом прогоне — то есть уже после того, как
за них заплачено попыткой.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from orchestrator import doctor

CANARY_SETS_CHECK = "canary-sets"


def check_canary_sets() -> doctor.Check:
    """Каждый набор `canary_sets:` ссылается на существующие роли, на
    модели каталога и на известных реестру провайдеров (требование 9,
    AC-13).

    `warn` — наборов в слое нет вовсе (в том числе слоя нет на диске):
    пульт без наборов исправен, но сказать про него «наборы согласованы»
    нельзя — иначе отсутствие набора Оператор узнавал бы только из отказа
    `--set`.

    Статус `experimental` у модели набора сам по себе НЕ `fail`: явное
    разрешение на такую модель собирает слой эфемерного клона
    (`canary._clone_local_layer_text`), а не запрещает здесь — иначе
    `doctor` пульта с заведённым Codex-набором был бы красным постоянно, и
    красная строка перестала бы значить «набор битый».

    Расхождение «провайдер роли ≠ провайдер её модели» этой строкой НЕ
    проверяется намеренно: его называет отказ самого прогона до клона
    (`canary._check_set_entries_or_exit`) и соседняя строка `model-provider-cli`
    — предмет здесь именно ССЫЛКИ набора, то есть то, что перестаёт
    существовать без его правки.
    """
    try:
        sets = doctor.models.load_canary_sets()
    except doctor.models.LocalLayerMissingError as exc:
        return doctor.Check(
            CANARY_SETS_CHECK, "warn",
            f"наборы ролей канарейки не заведены: {exc} — "
            f"{doctor.models.LOCAL_FIX_HINT}")
    except doctor.models.ModelsError as exc:
        return doctor.Check(CANARY_SETS_CHECK, "fail",
                            f"наборы ролей канарейки не разобраны: {exc}")
    if not sets:
        return doctor.Check(
            CANARY_SETS_CHECK, "warn",
            f"наборов ролей канарейки в {doctor.config.MODELS_LOCAL} нет "
            f"(раздел '{doctor.models.CANARY_SETS_KEY}:'): `canary --k <N>` "
            f"идёт набором по умолчанию {doctor.config.CANARY_DEFAULT_SET}")
    # Каталог — ОДНИМ чтением на весь перебор наборов (тот же приём, что
    # `check_models_local`): иначе каждая запись каждого набора
    # перечитывала бы `models.yaml`.
    catalog, _local = doctor.models.layers_or_none()
    broken, named = [], []
    for name in sorted(sets):
        entries = sets[name]
        for role, entry in entries.items():
            broken.extend(_broken_links(name, role, entry, catalog))
        named.append(f"{name}: " + ", ".join(
            f"{role} → {entry.model} ({entry.provider})"
            for role, entry in entries.items()))
    if broken:
        return doctor.Check(
            CANARY_SETS_CHECK, "fail",
            f"битые ссылки наборов ролей канарейки "
            f"{doctor.config.MODELS_LOCAL}: " + "; ".join(broken))
    return doctor.Check(CANARY_SETS_CHECK, "ok",
                        "наборы ролей канарейки согласованы — "
                        + "; ".join(named))


def _broken_links(name: str, role: str, entry, catalog) -> list:
    """Битые ссылки ОДНОЙ записи набора — все разом, не первая найденная:
    Оператор правит файл руками, и знать про обе половины записи ему нужно
    за один прогон `doctor`, а не за два."""
    problems = []
    try:
        doctor.roles.model_tier(role)
    except doctor.roles.RolesError as exc:
        problems.append(f"набор {name}: роль {role} — {exc}")
    try:
        doctor.models.catalog_model(entry.model, catalog)
    except doctor.models.ModelsError as exc:
        problems.append(f"набор {name}, роль {role}: {exc}")
    if entry.provider not in doctor.providers.PROVIDERS:
        problems.append(
            f"набор {name}, роль {role}: провайдер {entry.provider} не "
            f"зарегистрирован (известны: "
            f"{', '.join(sorted(doctor.providers.PROVIDERS))})")
    return problems
