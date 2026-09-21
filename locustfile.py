from locust import HttpUser, task, between

valid_json = {
  "credit_score": 619,
  "geography": "France",
  "gender": "Female",
  "age": 42,
  "tenure": 2,
  "balance": 0.0,
  "num_of_products": 1,
  "has_cr_card": 1,
  "is_active_member": 1,
  "estimated_salary": 101348.88,
  "satisfaction_score": 2,
  "card_type": "DIAMOND",
  "point_earned": 464
}


class ApiTest(HttpUser):

    wait_time = between(0.5, 2)

    @task(1)
    def health(self):
        self.client.get("/health")

    @task(5)
    def predict(self):
        self.client.post("/v1/predict", json=valid_json)