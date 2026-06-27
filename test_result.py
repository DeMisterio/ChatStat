import json
from backend.main import clean_nan

with open("backend/.checkpoints/339c7702504777d90594d2a28c38b5e072f808d24015bfb1ad1c2fb6a96da728/09_final_result.json") as f:
    data = json.load(f)

# The loaded data is just a dict.
# Let's check if there are any issues printing it or sending it to JS.
# We will dump it as a JSON string to ensure jsonable_encoder would succeed.

try:
    s = json.dumps(clean_nan(data))
    print("Cleaned JSON size:", len(s))
except Exception as e:
    print("JSON dump failed:", str(e))
