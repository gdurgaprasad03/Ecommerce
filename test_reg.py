import requests
import json

url = "http://localhost:8000/api/register/"
data = {
    "email": "test_unique_123@example.com",
    "username": "test_unique_123",
    "password": "Password123!",
    "first_name": "Test",
    "last_name": "User"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
