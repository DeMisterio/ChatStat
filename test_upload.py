import requests

# 1. First upload a dummy file to create a checkpoint
files = {'file': ('dummy.json', b'{"name": "test"}')}
res = requests.post("http://127.0.0.1:8000/api/upload", files=files)
print("First upload:", res.json())

# 2. Upload with force_action="load"
files = {'file': ('dummy.json', b'{"name": "test"}')}
data = {'force_action': 'load'}
res2 = requests.post("http://127.0.0.1:8000/api/upload", files=files, data=data)
print("Second upload (load):", res2.json())
if "task_id" in res2.json():
    task_id = res2.json()["task_id"]
    # Check status
    import time
    time.sleep(0.5)
    res_status = requests.get(f"http://127.0.0.1:8000/api/status/{task_id}")
    print("Status:", res_status.json())
    
    # Check result
    res_result = requests.get(f"http://127.0.0.1:8000/api/result/{task_id}")
    print("Result HTTP status:", res_result.status_code)
    try:
        print("Result:", str(res_result.json())[:200])
    except Exception as e:
        print("Result text:", res_result.text[:200])
