"""Five-minute authenticated list/search workload; see run_locust_benchmark.py."""
import re
from locust import HttpUser, between, task


class InventoryUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        response = self.client.get('/login', name='login form')
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
        if not match:
            raise RuntimeError('Login CSRF token not found')
        with self.client.post('/login', data={'csrf_token': match.group(1), 'identity': 'load-admin',
                              'password': 'LoadTestOnly123!'}, name='login', catch_response=True) as result:
            if result.status_code != 200 or '/login' in result.url:
                result.failure('Login failed')
                raise RuntimeError('Login failed')

    @task(2)
    def listing(self):
        with self.client.get('/components', name='inventory list', catch_response=True) as response:
            if response.status_code != 200 or '/login' in response.url:
                response.failure('Inventory list failed or redirected to login')

    @task(1)
    def search(self):
        with self.client.get('/components', params={'q': 'Performance Component 001234'},
                             name='inventory search', catch_response=True) as response:
            if response.status_code != 200 or '/login' in response.url:
                response.failure('Inventory search failed or redirected to login')
