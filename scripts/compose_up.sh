#!/usr/bin/env bash
# Поднимает сервис с Postgres, делает предсказание и показывает строку в логах.
set -euo pipefail

echo "==> Сборка образа и запуск сервисов"
docker compose up -d --build

echo "==> Ждём готовности сервиса"
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/ready >/dev/null; then
        echo "сервис готов"
        break
    fi
    sleep 2
done

echo "==> Предсказание"
curl -s -X POST http://localhost:8000/v1/predict \
    -H "Content-Type: application/json" \
    -d "@valid.json"
echo

echo "==> Строки в таблице predictions"
docker compose exec -T db psql -U postgres -d churn \
    -c "SELECT request_id, score, latency_ms, status_code, ts FROM predictions;"

echo
echo "Готово. Остановить: docker compose down"
