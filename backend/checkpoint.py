import os
import json
import time
import shutil
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

CHECKPOINTS_DIR = os.path.join(os.path.dirname(__file__), '.checkpoints')

STAGE_FILES = {
    "01_parsed": "01_parsed.parquet",
    "02_preprocessed": "02_preprocessed.parquet",
    "03_structural_stats": "03_structural_stats.json",
    "04_embeddings": "04_embeddings.npy",
    "05_sentiment_emotions": "05_sentiment_emotions.parquet",
    "06_topics": "06_topics.pkl", # Actually BERTopic save directory/file
    "07_topic_labels": "07_topic_labels.json",
    "08_semantic_extras": "08_semantic_extras.json",
    "09_final_result": "09_final_result.json"
}

def get_file_hash(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read in chunks to avoid memory issues with large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_checkpoint_dir(file_hash: str) -> str:
    return os.path.join(CHECKPOINTS_DIR, file_hash)

def get_manifest(file_hash: str) -> Optional[Dict]:
    manifest_path = os.path.join(get_checkpoint_dir(file_hash), "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def init_checkpoint(file_hash: str, source_filename: str, source_type: str, config: dict):
    os.makedirs(get_checkpoint_dir(file_hash), exist_ok=True)
    manifest = get_manifest(file_hash)
    if not manifest:
        manifest = {
            "file_hash": file_hash,
            "source_filename": source_filename,
            "source_type": source_type,
            "stages_completed": [],
            "last_updated": datetime.now().isoformat(),
            "config_snapshot": config
        }
        with open(os.path.join(get_checkpoint_dir(file_hash), "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    else:
        # Update config and invalidate stages if necessary
        old_config = manifest.get("config_snapshot", {})
        
        # Check if settings changed that affect ML stages
        # For simplicity, if llm settings change, invalidate from 06_topics onwards
        # In this prompt: "Стадии 06-08 зависят от настроек тем (model, n_topics, llm on/off)"
        invalidate_from = None
        if old_config.get("use_llm") != config.get("use_llm") or old_config.get("llm_model") != config.get("llm_model"):
            invalidate_from = "06_topics"
            
        if invalidate_from:
            stages_list = list(STAGE_FILES.keys())
            idx = stages_list.index(invalidate_from)
            invalid_stages = stages_list[idx:]
            manifest["stages_completed"] = [s for s in manifest["stages_completed"] if s not in invalid_stages]
            
        manifest["config_snapshot"] = config
        manifest["last_updated"] = datetime.now().isoformat()
        with open(os.path.join(get_checkpoint_dir(file_hash), "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

def update_manifest(file_hash: str, stage_name: str):
    manifest = get_manifest(file_hash)
    if manifest:
        if stage_name not in manifest["stages_completed"]:
            manifest["stages_completed"].append(stage_name)
        manifest["last_updated"] = datetime.now().isoformat()
        with open(os.path.join(get_checkpoint_dir(file_hash), "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

def save_checkpoint(file_hash: str, stage_name: str, data: Any):
    dir_path = get_checkpoint_dir(file_hash)
    os.makedirs(dir_path, exist_ok=True)
    
    file_name = STAGE_FILES.get(stage_name)
    if not file_name:
        return
        
    path = os.path.join(dir_path, file_name)
    
    if stage_name == "06_topics":
        # It's a BERTopic model
        data.save(path, serialization="pickle")
    elif file_name.endswith(".parquet"):
        data.to_parquet(path)
    elif file_name.endswith(".npy"):
        np.save(path, data)
    elif file_name.endswith(".json"):
        # Handle nan in json
        import math
        def clean_nan(obj):
            if isinstance(obj, float) and math.isnan(obj):
                return None
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [clean_nan(i) for i in obj]
            return obj
            
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean_nan(data), f, ensure_ascii=False)
            
    update_manifest(file_hash, stage_name)

def load_checkpoint(file_hash: str, stage_name: str) -> Any:
    manifest = get_manifest(file_hash)
    if not manifest or stage_name not in manifest.get("stages_completed", []):
        return None
        
    path = os.path.join(get_checkpoint_dir(file_hash), STAGE_FILES[stage_name])
    if not os.path.exists(path):
        return None
        
    if stage_name == "06_topics":
        from bertopic import BERTopic
        return BERTopic.load(path)
    elif path.endswith(".parquet"):
        return pd.read_parquet(path)
    elif path.endswith(".npy"):
        return np.load(path, allow_pickle=True)
    elif path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    return None

def is_stage_cached(file_hash: str, stage_name: str) -> bool:
    manifest = get_manifest(file_hash)
    if not manifest:
        return False
    return stage_name in manifest.get("stages_completed", [])

def cleanup_old_checkpoints(days: int = 30):
    if not os.path.exists(CHECKPOINTS_DIR):
        return
    cutoff = datetime.now() - timedelta(days=days)
    for dirname in os.listdir(CHECKPOINTS_DIR):
        dir_path = os.path.join(CHECKPOINTS_DIR, dirname)
        if os.path.isdir(dir_path):
            manifest = get_manifest(dirname)
            if manifest and "last_updated" in manifest:
                updated_dt = datetime.fromisoformat(manifest["last_updated"])
                if updated_dt < cutoff:
                    shutil.rmtree(dir_path)
            else:
                # No manifest or invalid, check folder modification time
                if datetime.fromtimestamp(os.path.getmtime(dir_path)) < cutoff:
                    shutil.rmtree(dir_path)

def delete_checkpoint(file_hash: str) -> bool:
    dir_path = get_checkpoint_dir(file_hash)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
        return True
    return False
