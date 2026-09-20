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

echo "==> Манифесты"
kubectl apply -f k8s/

echo "==> Ждём выката"
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

echo
echo "Готово. Снести кластер: kind delete cluster --name $CLUSTER"
