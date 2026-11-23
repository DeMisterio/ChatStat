import os
import json
from backend.checkpoint import get_checkpoint_dir

# Inspect the checkpoints available on this machine.
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
                
