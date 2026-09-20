#!/usr/bin/env bash
# Разворачивает сервис в локальном кластере kind и проверяет ответ модели.
set -euo pipefail

export MSYS_NO_PATHCONV=1   # Git Bash на Windows иначе портит пути вида /app

CLUSTER=mlpro
IMAGE=churn-service:1.0

echo "==> Кластер $CLUSTER"
if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
    echo "уже существует"
else
    kind create cluster --name "$CLUSTER"
fi

echo "==> Сборка образа $IMAGE"
docker build -t "$IMAGE" .

echo "==> Загрузка образа в кластер"
kind load docker-image "$IMAGE" --name "$CLUSTER"

echo "==> Секрет с паролем и строкой подключения"
kubectl create secret generic churn-secrets \
    --from-literal=POSTGRES_PASSWORD=postgres \
    --from-literal=DATABASE_URL=postgresql://postgres:postgres@postgres:5432/churn \
    --dry-run=client -o yaml | kubectl apply -f -

echo "==> Манифесты"
kubectl apply -f k8s/

echo "==> Ждём выката"
kubectl rollout status deployment/postgres --timeout=180s
kubectl rollout status deployment/churn-service --timeout=180s

echo "==> Поды"
kubectl get pods

echo "==> Предсказание через port-forward"
kubectl port-forward svc/churn-service 8080:80 >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

curl -s -X POST http://localhost:8080/v1/predict \
    -H "Content-Type: application/json" \
    -d "@valid.json"
echo

echo "==> Строки в таблице predictions внутри кластера"
kubectl exec deploy/postgres -- psql -U postgres -d churn \
    -c "SELECT request_id, score, latency_ms, status_code FROM predictions;"

echo
echo "Готово. Снести кластер: kind delete cluster --name $CLUSTER"
