# variant-2

Веб-приложение с обратным прокси, изолированными сетями и healthchecks.

## Стек технологий

Nginx - Reverse proxy; 
Flask - Backend приложение; 
PostgreSQL - Основное хранилище данных; 
Redis - Кэширование  

## Требования

- Docker 24.0+
- Docker Compose v2.20+
- curl для тестирования

## Быстрый запуск

```bash
# 1. Клонировать репозиторий
git clone https://github.com/poandrej23-netizen/variant-2.git
cd variant-2

# 2. Создать файл окружения
cp .env.example .env

# 3. Запустить стек
docker compose up -d

# 4. Проверить healthchecks
docker compose ps

# 5. Протестировать эндпоинты
curl http://localhost/
curl http://localhost/visits
curl http://localhost/health
