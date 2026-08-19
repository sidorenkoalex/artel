# Песочница агента Артели (Фаза 0).
# Минимум инструментов; сеть наружу ограничивается на уровне запуска
# (docker run --network + прокси-белый список: api.anthropic.com, github.com).
FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code

RUN useradd -m agent
USER agent
WORKDIR /work

# Токен роли передаётся в runtime (из keychain-слота, см. roles.yaml):
#   docker run -e GITHUB_TOKEN=$(security find-generic-password -s artel-<role> -w \
#     || security find-generic-password -s artel-token -w) ...
