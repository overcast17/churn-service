$ kubectl get pods,ingress -A
NAMESPACE            NAME                                              READY   STATUS    RESTARTS   AGE
kube-system          pod/coredns-559f6c778d-7tg4m                      1/1     Running   0          25m
kube-system          pod/coredns-559f6c778d-zfr6h                      1/1     Running   0          25m
kube-system          pod/etcd-sem3n-control-plane                      1/1     Running   0          25m
kube-system          pod/kindnet-fvgk6                                 1/1     Running   0          25m
kube-system          pod/kube-apiserver-sem3n-control-plane            1/1     Running   0          25m
kube-system          pod/kube-controller-manager-sem3n-control-plane   1/1     Running   0          25m
kube-system          pod/kube-proxy-4bg46                              1/1     Running   0          25m
kube-system          pod/kube-scheduler-sem3n-control-plane            1/1     Running   0          25m
local-path-storage   pod/local-path-provisioner-75f7fc7dc5-hwmmh       1/1     Running   0          25m
mlops                pod/mlflow-9f98c4469-n6zrz                        1/1     Running   0          12m
traefik              pod/traefik-6d88bc478f-qh2ld                      1/1     Running   0          42s

NAMESPACE   NAME                                      CLASS     HOSTS               ADDRESS   PORTS   AGE
default     ingress.networking.k8s.io/churn-service   traefik   churn.localhost               80      6m16s
mlops       ingress.networking.k8s.io/airflow         traefik   airflow.localhost             80      6m16s
mlops       ingress.networking.k8s.io/mlflow          traefik   mlflow.localhost              80      6m16s