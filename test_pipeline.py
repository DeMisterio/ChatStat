import requests
import time
import hashlib

content = b'{"name": "test2"}'
h = hashlib.sha256(content).hexdigest()

files = {'file': ('dummy.json', content)}
res = requests.post("http://127.0.0.1:8000/api/upload", files=files)
print("Upload 1:", res.json())
task_id = res.json()["task_id"]

while True:
    status = requests.get(f"http://127.0.0.1:8000/api/status/{task_id}").json()
    print("Status:", status["stage"])
    if status["is_done"]:
        break
    time.sleep(1)

print("Result 1:", requests.get(f"http://127.0.0.1:8000/api/result/{task_id}").status_code)

print("\n--- Loading from checkpoint ---")
files = {'file': ('dummy.json', content)}
res2 = requests.post("http://127.0.0.1:8000/api/upload", files=files, data={"force_action": "load"})
print("Upload 2:", res2.json())
task_id2 = res2.json()["task_id"]

time.sleep(1)
status2 = requests.get(f"http://127.0.0.1:8000/api/status/{task_id2}").json()
print("Status 2:", status2)

res_result2 = requests.get(f"http://127.0.0.1:8000/api/result/{task_id2}")
print("Result HTTP status:", res_result2.status_code)

