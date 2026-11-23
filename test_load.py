import os
import json
import requests
from backend.checkpoint import get_checkpoint_dir

# Fake hash
h = "12345"
d = get_checkpoint_dir(h)
os.makedirs(d, exist_ok=True)

with open(os.path.join(d, "manifest.json"), "w") as f:
    json.dump({"stages_completed": ["09_final_result"], "last_updated": "now"}, f)
    
with open(os.path.join(d, "09_final_result.json"), "w") as f:
    json.dump({"test": "data"}, f)

files = {'file': ('dummy.json', b'{"name": "test"}')}
data = {'force_action': 'load'}
# But wait, sha256 of b'{"name": "test"}' is not "12345".
