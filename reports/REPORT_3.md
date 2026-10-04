Задание 2.1


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



Задание 2.2


![alt text](../images/mlflow_registry.png)

1 запуск
🧪 View experiment at: http://mlflow.localhost/#/experiments/1
{"run_id": "a558e75b911948c1a3cb797aef51d165", "version": "1", "C": 0.0003, "pr_auc": 0.4701, "data_md5": "e37acb17", "champion_before": null, "champion_pr_auc_before": null, "min_gain": 0.01, "promoted": true}


2 запуск 
🧪 View experiment at: http://mlflow.localhost/#/experiments/1
{"run_id": "6893118ceb6c4419948f5e13ef6ca8d8", "version": "2", "C": 0.0001, "pr_auc": 0.4661, "data_md5": "e37acb17", "champion_before": "1", "champion_pr_auc_before": 0.4701, "min_gain": 0.01, "promoted": false}


3 запуск 
🧪 View experiment at: http://mlflow.localhost/#/experiments/1
{"run_id": "9c7ce7add5bd4f909fa469f0a040b84e", "version": "3", "C": 1.0, "pr_auc": 0.4865, "data_md5": "e37acb17", "champion_before": "1", "champion_pr_auc_before": 0.4701, "min_gain": 0.01, "promoted": true}


Задание 2.3


$ curl -s http://churn.localhost/health
{"status":"ok","model_version":"bank-churn/3","model_source":"registry: bank-churn@champion","log_level":"INFO"}(churn-service) 


$ curl http://churn.localhost/health
{"status":"ok","model_version":"bank-churn/2","model_source":"registry: bank-churn@champion","log_level":"INFO"}(churn-service) 


16 секунд прошло


Задание 2.4

Ссылка на зеленый прогон:
https://github.com/overcast17/churn-service/actions/runs/37218649782/job/111484468363


Скрин Runners:
![alt text](../images/runners.png)


Скрин из deploy, где видно runner: 
![alt text](../images/deploy_runner.png)


Задание 2.5 


Артемий@Artemiy MINGW64 /g/Postupashki_MLPRO_2026/churn-service (mlops)
$ dvc push
Collecting                                              |1.00 [00:00,  312entry/s]
Pushing
Everything is up to date.
(churn-service) 


![alt text](../images/mlflow_different_md5.png)