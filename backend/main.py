import os
import tempfile
import asyncio
import json
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from backend.progress_tracker import (
    create_task, update_task_stage, set_task_error, 
    set_task_result, get_task_status, finish_stage,
    set_custom_stage_text, set_task_facts, update_task_progress
)
from backend.parser import parse_telegram_export
from backend.parser_whatsapp import parse_whatsapp_export
from backend.preprocessing import process_dataframe
from backend.stats_structural import compute_structural_stats
from backend.stats_semantic import compute_embeddings, compute_sentiment, compute_semantic_stats
from backend.auth_hf import router as hf_auth_router, load_hf_token_on_startup
from backend.checkpoint import (
    get_file_hash, get_manifest, init_checkpoint,
    save_checkpoint, load_checkpoint, is_stage_cached,
    cleanup_old_checkpoints, delete_checkpoint, get_checkpoint_dir
)
import numpy as np
import psutil

app = FastAPI(title="Telegram Chat Analyzer")

@app.on_event("startup")
async def startup_event():
    cleanup_old_checkpoints(days=30)
    load_hf_token_on_startup()

app.include_router(hf_auth_router)

@app.delete("/api/checkpoints/{file_hash}")
async def delete_saved_checkpoint(file_hash: str):
    success = delete_checkpoint(file_hash)
    if success:
        return {"message": "Checkpoint deleted"}
    return JSONResponse(status_code=404, content={"error": "Checkpoint not found"})

@app.get("/api/system_stats")
async def get_system_stats():
    return {"cpu_percent": psutil.cpu_percent(interval=None)}

def process_chat_in_background(task_id: str, filepath: str, source: str, llm_mode: str = "none", llm_model: str = "qwen3:4b", advanced_llm_model: str = "gemma4:31b", file_hash: str = None, force_action: str = None, topic_count: str = "auto", embedding_quality: str = "high"):
    try:
        config = {
            "llm_mode": llm_mode,
            "llm_model": llm_model,
            "advanced_llm_model": advanced_llm_model,
            "topic_count": topic_count,
            "embedding_quality": embedding_quality
        }
        
        # If user explicitly requested to just load everything
        if force_action == "load":
            result = load_checkpoint(file_hash, "09_final_result")
            if result is None:
                raise ValueError("Не удалось загрузить данные из кэша (возможно, файл был удалён). Начните анализ заново.")
            set_task_result(task_id, result)
            update_task_stage(task_id, "done")
            finish_stage(task_id, "done")
            return
            
        init_checkpoint(file_hash, "upload", source, config)
        
        # 1. Parsing
        update_task_stage(task_id, "parsing")
        
        temp_dir = None
        if source == "encrypted" or filepath.endswith(".enc"):
            set_custom_stage_text(task_id, "Расшифровка файла в памяти...")
            key_b64 = os.environ.get('CHATSTAT_DECRYPT_KEY')
            if not key_b64:
                set_task_error(task_id, "Загружен зашифрованный файл (.enc), но ключ CHATSTAT_DECRYPT_KEY не установлен на сервере.")
                return
            
            import base64
            import tempfile
            from backend.encryption import decrypt_file
            
            try:
                key_bytes = base64.b64decode(key_b64)
                with open(filepath, "rb") as f:
                    ciphertext = f.read()
                plaintext = decrypt_file(ciphertext, key_bytes)
            except Exception as e:
                set_task_error(task_id, f"Ошибка расшифровки: неверный ключ или повреждённый файл. Детали: {e}")
                return
                
            temp_dir = tempfile.mkdtemp()
            if plaintext.startswith(b'{') or plaintext.startswith(b'['):
                temp_filepath = os.path.join(temp_dir, "decrypted.json")
                source = "telegram"
                with open(temp_filepath, "wb") as f: f.write(plaintext)
            elif plaintext.startswith(b'PK'):
                temp_filepath = os.path.join(temp_dir, "decrypted.zip")
                source = "whatsapp"
                with open(temp_filepath, "wb") as f: f.write(plaintext)
                import zipfile
                try:
                    with zipfile.ZipFile(temp_filepath, 'r') as z:
                        txt_files = [n for n in z.namelist() if n.endswith('.txt')]
                        if txt_files:
                            z.extract(txt_files[0], temp_dir)
                            temp_filepath = os.path.join(temp_dir, txt_files[0])
                except zipfile.BadZipFile:
                    pass
            else:
                temp_filepath = os.path.join(temp_dir, "decrypted.txt")
                source = "whatsapp"
                with open(temp_filepath, "wb") as f: f.write(plaintext)
                
            filepath = temp_filepath
            set_custom_stage_text(task_id, "Парсинг расшифрованного файла...")

        if is_stage_cached(file_hash, "01_parsed"):
            df = load_checkpoint(file_hash, "01_parsed")
        else:
            if source == "whatsapp":
                df = parse_whatsapp_export(filepath)
                error_msg = "Чат пуст или неверный формат (ожидается экспорт чата WhatsApp)."
            else:
                df = parse_telegram_export(filepath)
                error_msg = "Чат пуст или неверный формат (ожидается result.json из Telegram)."
                
            if df.empty:
                set_task_error(task_id, error_msg)
                return
            save_checkpoint(file_hash, "01_parsed", df)
            
        # Calculate brief facts for frontend
        if not df.empty:
            msg_count = len(df)
            author_counts = df['author_name'].value_counts()
            if len(author_counts) >= 2:
                most_active = author_counts.index[0]
                most_quiet = author_counts.index[-1]
            elif len(author_counts) == 1:
                most_active = author_counts.index[0]
                most_quiet = author_counts.index[0]
            else:
                most_active = "Неизвестно"
                most_quiet = "Неизвестно"
            
            set_task_facts(task_id, {
                "total_messages": f"{msg_count:,}".replace(',', ' '),
                "most_active": str(most_active),
                "most_quiet": str(most_quiet)
            })

        finish_stage(task_id, "parsing")
        
        # 2. Preprocessing
        update_task_stage(task_id, "preprocessing")
        if is_stage_cached(file_hash, "02_preprocessed"):
            df = load_checkpoint(file_hash, "02_preprocessed")
        else:
            df = process_dataframe(df)
            save_checkpoint(file_hash, "02_preprocessed", df)
        finish_stage(task_id, "preprocessing")
        
        # 3. Structural stats
        update_task_stage(task_id, "structural")
        if is_stage_cached(file_hash, "03_structural_stats"):
            structural_stats = load_checkpoint(file_hash, "03_structural_stats")
        else:
            structural_stats = compute_structural_stats(df)
            save_checkpoint(file_hash, "03_structural_stats", structural_stats)
        finish_stage(task_id, "structural")
        
        # 4. Embeddings
        update_task_stage(task_id, "embeddings")
        set_custom_stage_text(task_id, "Подготавливаем эмбеддинги для глубокого анализа...")
        if is_stage_cached(file_hash, "04_embeddings"):
            text_msgs = df[df['clean_text'].str.len() > 0].copy()
            emb_array = load_checkpoint(file_hash, "04_embeddings")
            text_msgs['embedding'] = list(emb_array)
        else:
            text_msgs = compute_embeddings(df, task_id, embedding_quality)
            if not text_msgs.empty and 'embedding' in text_msgs.columns:
                save_checkpoint(file_hash, "04_embeddings", np.vstack(text_msgs['embedding'].values))
        finish_stage(task_id, "embeddings")
        
        # 5. Sentiment
        update_task_stage(task_id, "sentiment")
        if is_stage_cached(file_hash, "05_sentiment_emotions"):
            text_msgs = load_checkpoint(file_hash, "05_sentiment_emotions")
            if 'embedding' not in text_msgs.columns and not text_msgs.empty:
                if is_stage_cached(file_hash, "04_embeddings"):
                    emb_array = load_checkpoint(file_hash, "04_embeddings")
                    text_msgs['embedding'] = list(emb_array)
        else:
            text_msgs = compute_sentiment(text_msgs, task_id)
            # drop embedding list to save parquet correctly
            save_df = text_msgs.drop(columns=['embedding'], errors='ignore')
            save_checkpoint(file_hash, "05_sentiment_emotions", save_df)
        finish_stage(task_id, "sentiment")
        
        # 6. Semantic stats
        update_task_stage(task_id, "semantic")
        set_custom_stage_text(task_id, "Группируем темы и ищем скрытые паттерны (может занять время)...")
        use_llm = (llm_mode in ['light', 'advanced'])
        semantic_stats = compute_semantic_stats(df, text_msgs, use_llm=use_llm, llm_model=llm_model, topic_count=topic_count, embedding_quality=embedding_quality, file_hash=file_hash, task_id=task_id)
        finish_stage(task_id, "semantic")
        
        # 7. Advanced Analysis
        if llm_mode == "advanced":
            update_task_stage(task_id, "advanced")
            if is_stage_cached(file_hash, "08_advanced_analysis"):
                semantic_stats = load_checkpoint(file_hash, "08_advanced_analysis")
            else:
                from backend.stats_advanced import compute_advanced_analysis
                try:
                    semantic_stats = compute_advanced_analysis(semantic_stats, text_msgs, advanced_llm_model, task_id)
                    save_checkpoint(file_hash, "08_advanced_analysis", semantic_stats)
                except Exception as e:
                    print(f"Advanced analysis failed: {e}")
            finish_stage(task_id, "advanced")
        
        # Combine
        final_result = {
            "source": source,
            "structural": structural_stats,
            "semantic": semantic_stats,
            "participants": df['author_name'].dropna().unique().tolist(),
            "total_messages": len(df)
        }
        
        save_checkpoint(file_hash, "09_final_result", final_result)
        
        # Save cache for search
        from backend.progress_tracker import tasks
        if task_id in tasks and 'embedding' in text_msgs.columns:
            tasks[task_id]['search_cache'] = {
                'text_msgs': text_msgs[['author_name', 'text', 'datetime', 'embedding']].copy()
            }
            
        set_task_result(task_id, final_result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        set_task_error(task_id, f"Произошла ошибка при анализе: {str(e)}")
    finally:
        # Cleanup temp dir if created for encryption
        if 'temp_dir' in locals() and temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    llm_mode: str = Form("none"),
    llm_model: str = Form("qwen3:4b"),
    advanced_llm_model: str = Form("gemma4:31b"),
    force_action: str = Form(None),
    topic_count: str = Form("auto"),
    embedding_quality: str = Form("high")
):
    valid_exts = {".json": "telegram", ".txt": "whatsapp", ".zip": "whatsapp", ".enc": "encrypted"}
    ext = os.path.splitext(file.filename)[1].lower()
    
    if ext not in valid_exts:
        return JSONResponse(status_code=400, content={"error": "Поддерживаются только .json, .txt и .zip файлы."})
        
    content = await file.read()
    import hashlib
    sha256_hash = hashlib.sha256(content).hexdigest()
    
    # Check if needs decision
    manifest = get_manifest(sha256_hash)
    if manifest and force_action is None:
        if "09_final_result" in manifest.get("stages_completed", []):
            return JSONResponse(status_code=200, content={
                "status": "needs_decision", 
                "file_hash": sha256_hash, 
                "last_updated": manifest.get("last_updated")
            })
            
    # Save to checkpoint source
    dir_path = get_checkpoint_dir(sha256_hash)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"source{ext}")
    with open(filepath, "wb") as f:
        f.write(content)
        
    source = valid_exts[ext]
    
    # If zip, extract first txt
    if ext == ".zip":
        import zipfile
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                txt_files = [n for n in z.namelist() if n.endswith('.txt')]
                if not txt_files:
                    return JSONResponse(status_code=400, content={"error": "В ZIP-архиве не найден .txt файл чата."})
                
                extracted_path = z.extract(txt_files[0], path=dir_path)
                filepath = extracted_path
        except zipfile.BadZipFile:
            return JSONResponse(status_code=400, content={"error": "Неверный ZIP-архив."})
    
    task_id = create_task()
    
    background_tasks.add_task(
        process_chat_in_background, 
        task_id, filepath, source, llm_mode, llm_model, advanced_llm_model, sha256_hash, force_action, topic_count, embedding_quality
    )
    
    return {"task_id": task_id, "source": source, "file_hash": sha256_hash}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    return get_task_status(task_id)

@app.websocket("/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            status = get_task_status(task_id)
            await websocket.send_json(status)
            if status["is_done"]:
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    from backend.progress_tracker import tasks
    if task_id not in tasks:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
        
    task = tasks[task_id]
    if task["stage"] == "error":
        return JSONResponse(status_code=400, content={"error": task["error"]})
        
    if task["stage"] != "Готово!":
        return JSONResponse(status_code=202, content={"message": "Still processing"})
        
    import math
    def clean_nan(obj):
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: clean_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_nan(i) for i in obj]
        return obj
        
    cleaned_result = clean_nan(task.get("result", {}))
    return cleaned_result

from pydantic import BaseModel
class SearchQuery(BaseModel):
    query: str

@app.post("/api/search/{task_id}")
async def search_chat(task_id: str, payload: SearchQuery):
    from backend.progress_tracker import tasks
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    from backend.models import get_sentence_model
    
    if task_id not in tasks or 'search_cache' not in tasks[task_id]:
        return JSONResponse(status_code=404, content={"error": "Chat data not found or not processed completely"})
        
    cache = tasks[task_id]['search_cache']
    text_msgs = cache['text_msgs']
    
    model = get_sentence_model()
    q_emb = model.encode(payload.query)
    
    doc_embs = np.vstack(text_msgs['embedding'].values)
    sims = cosine_similarity([q_emb], doc_embs)[0]
    
    top_indices = sims.argsort()[-20:][::-1]
    
    results = []
    for idx in top_indices:
        msg = text_msgs.iloc[idx]
        results.append({
            "author": msg['author_name'],
            "text": msg['text'],
            "datetime": str(msg['datetime']),
            "score": float(sims[idx])
        })
        
    return {"results": results}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
