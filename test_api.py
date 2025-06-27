import requests
import time

# API endpoint
BASE_URL = "http://localhost:8000"

# Submit video for processing
response = requests.post(
    f"{BASE_URL}/generate",
    json={"youtube_url": "https://www.youtube.com/watch?v=QmFT-L45i2w"}
)

if response.status_code != 200:
    print(f"Error submitting video: {response.text}")
    exit(1)

job_id = response.json()["job_id"]
print(f"Job ID: {job_id}")

# Poll for status
while True:
    status_response = requests.get(f"{BASE_URL}/status/{job_id}")
    status = status_response.json()
    print(f"Status: {status}")
    
    if status["status"] == "completed":
        # Download the PDF
        pdf_response = requests.get(f"{BASE_URL}/result/{job_id}")
        with open("instructions.pdf", "wb") as f:
            f.write(pdf_response.content)
        print("PDF downloaded as instructions.pdf")
        break
    elif status["status"] == "failed":
        print(f"Processing failed: {status.get('error')}")
        break
    
    time.sleep(5)  # Wait 5 seconds before checking again 