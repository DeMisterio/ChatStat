import json
import httpx
import re
import traceback
from backend.progress_tracker import set_custom_stage_text

def call_ollama(model_name, prompt, expect_json=False, enable_thinking=False):
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 16384,
            "temperature": 0.2 if expect_json else 0.7
        }
    }
    if expect_json:
        payload["format"] = "json"
        
    # Gemma 4 thinking mode if supported
    if enable_thinking:
        # Give it space to think
        payload["options"]["num_predict"] = 2048
        
    try:
        with httpx.Client(timeout=600.0) as client:
            resp = client.post("http://localhost:11434/api/generate", json=payload)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            else:
                print(f"Ollama error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Ollama call failed: {e}")
    return None

def compute_advanced_analysis(stats, text_msgs, model_name, task_id=None):
    print(f"Starting advanced analysis with {model_name}...")
    
    # 1. Topic Descriptions
    if 'clusters' in stats and stats['clusters']:
        if task_id:
            set_custom_stage_text(task_id, f"Анализ тем через {model_name}...")
        for cluster in stats['clusters']:
            prompt = f"""У нас есть тема сообщений из переписки. 
Ключевые слова: {', '.join(cluster.get('top_words', []))}
Примеры сообщений:
{chr(10).join(cluster.get('examples', []))}
Размер темы: {cluster.get('size')} сообщений.

Сформулируй короткое название этой темы (свойство "title") и одно-два предложения описания, о чем была эта тема и какой в целом был тон обсуждения (свойство "description").
Верни ТОЛЬКО строгий JSON: {{"title": "...", "description": "..."}}"""
            
            res = call_ollama(model_name, prompt, expect_json=True)
            if res:
                try:
                    parsed = json.loads(res)
                    if 'title' in parsed: cluster['name'] = parsed['title']
                    if 'description' in parsed: cluster['description'] = parsed['description']
                except json.JSONDecodeError:
                    # Regex fallback
                    title_match = re.search(r'"title"\s*:\s*"([^"]+)"', res)
                    desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', res)
                    if title_match: cluster['name'] = title_match.group(1)
                    if desc_match: cluster['description'] = desc_match.group(1)

    # 2. General Summary Essay
    if task_id:
        set_custom_stage_text(task_id, f"Написание резюме от AI...")
        
    topics_list = []
    if 'clusters' in stats:
        topics_list = [f"{c.get('name', 'Тема')} ({c.get('size')} сообщ.)" for c in stats['clusters'][:10]]
        
    top_words = list(stats.get('top_words_overall', {}).keys())[:15]
    emo_portrait = stats.get('emotional_portrait', {})
    
    essay_prompt = f"""Основываясь на агрегированной статистике чата, напиши связное эссе-резюме (150-250 слов) о характере этой переписки и отношениях между участниками. Не придумывай того, чего нет в данных, интерпретируй статистику.

Статистика:
Топ темы разговоров: {', '.join(topics_list)}
Частые слова: {', '.join(top_words)}
Эмоциональный профиль участника: {json.dumps(emo_portrait, ensure_ascii=False)}

Ответь связным текстом, как профессиональный аналитик."""

    essay_res = call_ollama(model_name, essay_prompt, expect_json=False)
    if essay_res:
        # Strip thinking trace if Gemma returns <think>...</think>
        essay_res = re.sub(r'<think>.*?</think>', '', essay_res, flags=re.DOTALL).strip()
        stats['ai_summary'] = essay_res

    # 3. Breaking points validation
    if 'breaking_points' in stats and stats['breaking_points']:
        if task_id:
            set_custom_stage_text(task_id, f"Проверка переломных моментов...")
        confirmed_breaks = []
        rejected_breaks = []
        text_msgs_sorted = text_msgs.sort_values('datetime').reset_index()
        for bp_date in stats['breaking_points']:
            try:
                bp_datetime = text_msgs_sorted[text_msgs_sorted['date_only_str'] == bp_date]['datetime'].iloc[0]
                idx = text_msgs_sorted[text_msgs_sorted['datetime'] == bp_datetime].index[0]
                start_idx = max(0, idx - 10)
                end_idx = min(len(text_msgs_sorted), idx + 10)
                context_msgs = text_msgs_sorted.iloc[start_idx:end_idx]
                
                context_text = "\n".join([f"[{r['author_name']}] {r['text']}" for _, r in context_msgs.iterrows()])
                
                prompt = f"""Вот фрагмент переписки (окно 20 сообщений), где статистически был замечен резкий перелом тональности:
{context_text}

Действительно ли здесь происходит реальное изменение в отношениях/тоне, конфликт, или важная новость? Или это ложное срабатывание (например, общая шутка с грубыми словами)?
Верни строгий JSON: {{"is_real_turning_point": true/false, "reason": "краткое объяснение почему"}}"""
                
                res = call_ollama(model_name, prompt, expect_json=True, enable_thinking=True)
                if res:
                    try:
                        parsed = json.loads(res)
                        if parsed.get("is_real_turning_point"):
                            confirmed_breaks.append(bp_date)
                        else:
                            rejected_breaks.append(bp_date)
                    except:
                        confirmed_breaks.append(bp_date)
                else:
                    confirmed_breaks.append(bp_date)
            except Exception:
                confirmed_breaks.append(bp_date)
                
        stats['breaking_points_confirmed'] = confirmed_breaks
        stats['breaking_points_rejected'] = rejected_breaks
        
    # 4. Best kind message
    if 'emo_joy' in text_msgs.columns:
        if task_id:
            set_custom_stage_text(task_id, f"Поиск самого доброго момента...")
        try:
            top_kind = text_msgs[text_msgs['word_count'] > 3].nlargest(5, 'emo_joy')
            if not top_kind.empty:
                candidates_text = ""
                for i, (_, row) in enumerate(top_kind.iterrows()):
                    candidates_text += f"Вариант {i+1}. [{row['author_name']}] {row['text']}\n"
                    
                prompt = f"""Из этих 5 сообщений с высокой статистической оценкой радости/добра выбери одно, которое по-настоящему самое тёплое, доброе и искреннее (без учета иронии).
{candidates_text}

Верни строгий JSON: {{"best_index": 1, "reason": "почему"}} (где best_index от 1 до 5)"""

                res = call_ollama(model_name, prompt, expect_json=True, enable_thinking=True)
                best_idx = 1
                if res:
                    try:
                        parsed = json.loads(res)
                        best_idx = parsed.get("best_index", 1)
                    except Exception:
                        pass
                
                best_idx = max(1, min(5, best_idx)) - 1
                if best_idx < len(top_kind):
                    best_row = top_kind.iloc[best_idx]
                    stats['kindest_message'] = {
                        'author': best_row['author_name'], 
                        'text': best_row['text'], 
                        'date': str(best_row['datetime']),
                        'ai_verified': True
                    }
        except Exception as e:
            print(f"Error in kindest message: {e}")

    # 5. Emotional arcs titles
    if 'emotional_arcs' in stats and stats['emotional_arcs']:
        if task_id:
            set_custom_stage_text(task_id, f"Нарратив эмоциональных арок...")
            
        new_arcs = {}
        for period, dom_emo in stats['emotional_arcs'].items():
            try:
                period_msgs = text_msgs[text_msgs['arc_period'] == period]
                if not period_msgs.empty:
                    sample = period_msgs.sample(min(10, len(period_msgs)))['text'].tolist()
                    prompt = f"""Период переписки. Доминирующая эмоция (статистически): {dom_emo}.
Примеры сообщений в этот период:
{chr(10).join(sample)}

Сформулируй короткую фразу-заголовок для этого периода (например: "период восторга и знакомства" или "бытовая рутина").
Верни ТОЛЬКО строгий JSON: {{"title": "..."}}"""
                    res = call_ollama(model_name, prompt, expect_json=True)
                    if res:
                        try:
                            parsed = json.loads(res)
                            if 'title' in parsed:
                                new_arcs[period] = {'emotion': dom_emo, 'title': parsed['title']}
                            else:
                                new_arcs[period] = {'emotion': dom_emo, 'title': dom_emo}
                        except:
                            new_arcs[period] = {'emotion': dom_emo, 'title': dom_emo}
                    else:
                        new_arcs[period] = {'emotion': dom_emo, 'title': dom_emo}
                else:
                    new_arcs[period] = {'emotion': dom_emo, 'title': dom_emo}
            except Exception:
                new_arcs[period] = {'emotion': dom_emo, 'title': dom_emo}
                
        stats['emotional_arcs_narrative'] = new_arcs

    if task_id:
        set_custom_stage_text(task_id, "Завершение Advanced Analysis...")
        
    return stats
