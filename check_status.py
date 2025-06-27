import requests

# Check if server is running
try:
    response = requests.get("http://localhost:8000/status/34c1bc2f-455c-422e-9e8f-b2b1bccdcc22")
    print("Status response:", response.json())
except Exception as e:
    print("Error:", e) 