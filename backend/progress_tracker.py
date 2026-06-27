import time
import uuid
from typing import Dict, Any

# In-memory store
# { task_id: { "stage": str, "progress": int, "eta_seconds": int, "result": dict, "error": str, "start_time": float, "last_stage_time": float, "total_weight": int } }
tasks: Dict[str, Dict[str, Any]] = {}

STAGES = {
    "parsing": {"name": "Парсинг JSON...", "weight": 5},
    "preprocessing": {"name": "Очистка и лемматизация текста...", "weight": 10},
    "structural": {"name": "Вычисление структурной статистики...", "weight": 5},
    "embeddings": {"name": "Генерация эмбеддингов...", "weight": 30},
    "sentiment": {"name": "Анализ тональности и эмоций...", "weight": 25},
    "semantic": {"name": "Тематическое моделирование и семантика...", "weight": 25},
    "advanced": {"name": "Углублённый анализ (Advanced Analysis)...", "weight": 15},
    "done": {"name": "Готово!", "weight": 0}
}

def create_task() -> str:
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "stage": "Инициализация...",
        "progress": 0,
        "eta_seconds": 0,
        "start_time": time.time(),
        "accumulated_weight": 0.0,
        "result": None,
        "error": None,
        "custom_stage": None,
        "facts": None
    }
    return task_id

def update_task_stage(task_id: str, stage_key: str):
    if task_id not in tasks:
        return
        
    task = tasks[task_id]
    stage_info = STAGES.get(stage_key)
    
    if not stage_info:
        return
        
    task["stage"] = stage_info["name"]
    task["custom_stage"] = None # Reset custom text
    
    if stage_key == "done":
        task["progress"] = 100
        task["eta_seconds"] = 0
    else:
        # Progress is the accumulated weight before this stage starts
        # (Actually, better to update progress dynamically within the stage if possible,
        # but at the start of a stage, we are at the accumulated weight)
        task["progress"] = task["accumulated_weight"]

def set_custom_stage_text(task_id: str, text: str):
    if task_id in tasks:
        tasks[task_id]["custom_stage"] = text

def set_task_facts(task_id: str, facts: dict):
    if task_id in tasks:
        tasks[task_id]["facts"] = facts

def update_task_progress(task_id: str, stage_key: str, stage_progress_fraction: float):
    """
    stage_progress_fraction: 0.0 to 1.0 (how much of the CURRENT stage is done)
    """
    if task_id not in tasks:
        return
        
    task = tasks[task_id]
    stage_info = STAGES.get(stage_key)
    
    if not stage_info:
        return

    current_weight_done = stage_info["weight"] * stage_progress_fraction
    total_progress = task["accumulated_weight"] + current_weight_done
    
    task["progress"] = min(99.99, total_progress)
    
    # Calculate ETA
    elapsed = time.time() - task["start_time"]
    if total_progress > 0:
        total_estimated = elapsed / (total_progress / 100.0)
        eta = max(0, int(total_estimated - elapsed))
        task["eta_seconds"] = eta

def finish_stage(task_id: str, stage_key: str):
    if task_id in tasks and stage_key in STAGES:
        tasks[task_id]["accumulated_weight"] += STAGES[stage_key]["weight"]

def set_task_error(task_id: str, error_msg: str):
    if task_id in tasks:
        tasks[task_id]["stage"] = "error"
        tasks[task_id]["error"] = error_msg

def set_task_result(task_id: str, result: dict):
    if task_id in tasks:
        update_task_stage(task_id, "done")
        tasks[task_id]["result"] = result
        
def get_task_status(task_id: str) -> dict:
    if task_id not in tasks:
        return {"stage": "error", "error": "Task not found"}
        
    task = tasks[task_id]
    return {
        "stage": task.get("custom_stage") or task["stage"],
        "progress": task["progress"],
        "eta_seconds": task["eta_seconds"],
        "error": task["error"],
        "is_done": task["stage"] == "Готово!" or task["stage"] == "error",
        "facts": task.get("facts")
    }
