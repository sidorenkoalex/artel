"""Проверки каталога моделей и локального слоя (SPEC
01M3009Y9AGGY6ZCFA7H1HJ1TD, требование 11) — и уборка `doctor --fix`,
кладущая шаблон локального слоя (требование 7).

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from orchestrator import doctor


def check_models_catalog() -> doctor.Check:
    """Каталог `models.yaml` разобран, и у каждой модели, на которую
    указывает ярус локального слоя, есть провайдер, минимум версии CLI и
    полный прейскурант (требование 11, AC-14).

    Полноту прейскуранта и известность провайдера проверяет сам разбор
    (`models.load_catalog` отказывает именованной ошибкой) — отдельного
    перебора полей здесь нет: одна проверка, одно место. Что остаётся
    этой строке сверх разбора — модели ЯРУСОВ: каталог может быть
    безупречен, а ярус указывать на модель, которой в нём нет, и тогда
    красной обязана быть проверка каталога, а не только локального слоя
    (Оператор чинит её, дописывая запись в каталог).

    Локальный слой нечитаем — сверять ярусы не с чем; проверка остаётся
    зелёной по своему предмету (каталог), а про слой говорит соседняя
    строка `check_models_local`.
    """
    try:
        catalog = doctor.models.load_catalog()
    except doctor.models.ModelsError as exc:
        return doctor.Check("models-catalog", "fail",
                            f"каталог моделей не разобран: {exc}")
    listed = ", ".join(sorted(catalog.models))
    try:
        local = doctor.models.load_local()
    except doctor.models.ModelsError:
        return doctor.Check(
            "models-catalog", "ok",
            f"каталог моделей {doctor.config.MODELS}: {listed}; ярусы не "
            f"сверены — локальный слой не прочитан")
    missing = sorted({model_id for model_id in local.tiers.values()
                      if model_id not in catalog.models})
    if missing:
        return doctor.Check(
            "models-catalog", "fail",
            f"каталог моделей {doctor.config.MODELS}: нет записей моделей "
            f"{', '.join(missing)}, на которые указывают ярусы "
            f"{doctor.config.MODELS_LOCAL} (есть: {listed})")
    return doctor.Check("models-catalog", "ok",
                        f"каталог моделей {doctor.config.MODELS}: {listed}")


def check_models_local() -> doctor.Check:
    """Локальный слой есть, разобран, и ярусы ВСЕХ agent-ролей
    разрешаются (требование 11, AC-14).

    Одна строка на весь слой, а не на роль: отказы перечисляются в её
    тексте — иначе `doctor` свежего пульта печатал бы четыре одинаковых
    «локального слоя нет» подряд. Модель со статусом `experimental` без
    явного разрешения попадает сюда тем же путём, что и остальные звенья:
    `resolve_role` отказывает, текст называет причину и починку.
    """
    try:
        local = doctor.models.load_local()
    except doctor.models.LocalLayerMissingError as exc:
        return doctor.Check("models-local", "fail",
                            f"локальный слой моделей: {exc} — "
                            f"{doctor.models.LOCAL_FIX_HINT}")
    except doctor.models.ModelsError as exc:
        return doctor.Check("models-local", "fail",
                            f"локальный слой моделей не разобран: {exc}")
    # Каталог — тем же одним чтением на весь перебор ролей, что и слой
    # выше (REVIEW итерации 1, R1-F3). Нечитаемый каталог отдаётся сюда
    # `None`: `resolve_role` прочитает его сам и назовёт отказ по каждой
    # роли — предмет этой строки остаётся прежним.
    catalog, _ = doctor.models.layers_or_none()
    chains, failures = [], []
    for role in doctor.agent_roles():
        try:
            resolved = doctor.models.resolve_role(role, catalog, local)
        except doctor.models.ModelsError as exc:
            failures.append(f"{role}: {exc}")
            continue
        chains.append(f"{role} → {resolved.tier} → {resolved.model}")
    if failures:
        return doctor.Check("models-local", "fail",
                            f"локальный слой моделей "
                            f"{doctor.config.MODELS_LOCAL}: "
                            f"{'; '.join(failures)}")
    return doctor.Check("models-local", "ok",
                        f"локальный слой моделей "
                        f"{doctor.config.MODELS_LOCAL}: {', '.join(chains)}")


def fix_models_local() -> None:
    """`doctor --fix` кладёт шаблон локального слоя, если файла нет
    (требование 7, AC-9). Существующий файл не перезаписывается и не
    меняется — печатается строка о том, что он оставлен как есть: молчание
    здесь неотличимо от «положил поверх»."""
    if doctor.models.ensure_local_template():
        print(f"Локальный слой моделей: шаблон положен в "
              f"{doctor.config.MODELS_LOCAL}")
    else:
        print(f"Локальный слой моделей: {doctor.config.MODELS_LOCAL} уже "
              f"существует — не тронут")
