import os
import json
from backend.checkpoint import get_checkpoint_dir

# Find the user's real checkpoint directory
h = "2e5e80eaa69604993bbf11fbfd1c88794324545b6ae164e7e8ebd2ad503f94b6"
for name in os.listdir("backend/.checkpoints"):
    if os.path.isdir(os.path.join("backend/.checkpoints", name)):
        print(f"Checkpoint found: {name}")
        manifest_path = os.path.join("backend/.checkpoints", name, "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                print("Manifest:", f.read()[:200])
        final_path = os.path.join("backend/.checkpoints", name, "09_final_result.json")
        if os.path.exists(final_path):
            with open(final_path) as f:
                print("09_final_result size:", len(f.read()))
                
