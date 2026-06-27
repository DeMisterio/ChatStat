import pandas as pd
import numpy as np
import re
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from bertopic import BERTopic
from scipy.stats import pearsonr
import time
import httpx

from backend.models import get_sentence_model, get_sentiment_pipeline, get_emotion_pipeline
from backend.stopwords import EMOJI_CATEGORIES, SLANG_WORDS, COMPLIMENTS, APOLOGIES, get_all_stopwords
from backend.progress_tracker import update_task_progress

def get_emoji_category(emoji_char):
    for cat, emojis in EMOJI_CATEGORIES.items():
        if emoji_char in emojis:
            return cat
    return 'other'

def compute_embeddings(df: pd.DataFrame, task_id: str = None, embedding_quality: str = "high"):
    """Computes embeddings for messages in batches and updates progress."""
    text_msgs = df[df['clean_text'].str.len() > 0].copy()
    if text_msgs.empty:
        return text_msgs
        
    model = get_sentence_model(quality=embedding_quality)
    texts = text_msgs['clean_text'].tolist()
    
    batch_size = 64
    total_batches = (len(texts) + batch_size - 1) // batch_size
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        emb = model.encode(batch, show_progress_bar=False)
        embeddings.append(emb)
        if task_id:
            update_task_progress(task_id, "embeddings", (i + len(batch)) / len(texts))
            
    text_msgs['embedding'] = list(np.vstack(embeddings))
    return text_msgs

def compute_sentiment(df: pd.DataFrame, task_id: str = None):
    """Computes sentiment for messages in batches and updates progress."""
    text_msgs = df[df['clean_text'].str.len() > 0].copy()
    if text_msgs.empty:
        return text_msgs
        
    pipeline = get_sentiment_pipeline()
    emotion_pipeline = get_emotion_pipeline()
    
    # Ensure text is not too long for BERT (max 512 tokens, we truncate string roughly)
    texts = text_msgs['clean_text'].str.slice(0, 1500).tolist()
    
    batch_size = 64
    sentiments = []
    emotions = []
    
    # HuggingFace pipeline with list
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        results = pipeline(batch, truncation=True, max_length=512)
        sentiments.extend(results)
        
        emo_results = emotion_pipeline(batch, truncation=True, max_length=512)
        emotions.extend(emo_results)
        
        if task_id:
            update_task_progress(task_id, "sentiment", (i + len(batch)) / len(texts))
            
    # Map 'positive', 'neutral', 'negative' to scores 1, 0, -1
    score_map = {'positive': 1, 'neutral': 0, 'negative': -1}
    text_msgs['sentiment_label'] = [r['label'] for r in sentiments]
    text_msgs['sentiment_score'] = [score_map.get(r['label'], 0) for r in sentiments]
    
    # Extract emotion scores
    # CEDR typically has: joy, sadness, surprise, fear, anger, no_emotion
    joy_scores, sadness_scores, surprise_scores, fear_scores, anger_scores, neutral_scores = [], [], [], [], [], []
    for emo_list in emotions:
        if isinstance(emo_list, dict):
            emo_list = [emo_list]
        emo_dict = {d['label']: d['score'] for d in emo_list}
        joy_scores.append(emo_dict.get('joy', 0))
        sadness_scores.append(emo_dict.get('sadness', 0))
        surprise_scores.append(emo_dict.get('surprise', 0))
        fear_scores.append(emo_dict.get('fear', 0))
        anger_scores.append(emo_dict.get('anger', 0))
        neutral_scores.append(emo_dict.get('no_emotion', 0))
        
    text_msgs['emo_joy'] = joy_scores
    text_msgs['emo_sadness'] = sadness_scores
    text_msgs['emo_surprise'] = surprise_scores
    text_msgs['emo_fear'] = fear_scores
    text_msgs['emo_anger'] = anger_scores
    text_msgs['emo_neutral'] = neutral_scores
    
    # Identify dominant emotion
    emotion_labels = ['joy', 'sadness', 'surprise', 'fear', 'anger', 'no_emotion']
    def get_dominant(row):
        scores = [row['emo_joy'], row['emo_sadness'], row['emo_surprise'], row['emo_fear'], row['emo_anger'], row['emo_neutral']]
        return emotion_labels[np.argmax(scores)]
        
    text_msgs['dominant_emotion'] = text_msgs.apply(get_dominant, axis=1)
    
    return text_msgs

def compute_semantic_stats(df: pd.DataFrame, text_msgs: pd.DataFrame, use_llm: bool = False, llm_model: str = "qwen3:4b", topic_count: str = "auto", embedding_quality: str = "high", file_hash: str = None, task_id: str = None) -> dict:
    from backend.checkpoint import is_stage_cached, load_checkpoint, save_checkpoint
    from backend.progress_tracker import set_custom_stage_text
    
    if df.empty or text_msgs.empty:
        return {}
        
    stats = {}
    authors = df['author_name'].dropna().unique().tolist()
    
    # Get top authors to avoid memory explosion in group chats
    author_counts = df['author_name'].value_counts()
    top_authors = author_counts.head(10).index.tolist()
    
    # Check if we have semantic_extras already
    if file_hash and is_stage_cached(file_hash, "08_semantic_extras"):
        stats = load_checkpoint(file_hash, "08_semantic_extras")
        return stats

    # 26. Top 20 frequent words
    all_tokens_df = text_msgs.explode('clean_tokens').dropna(subset=['clean_tokens'])
    stats['top_words_overall'] = all_tokens_df['clean_tokens'].value_counts().head(20).to_dict()
    stats['top_words_author'] = {}
    for author in top_authors:
        author_tokens = all_tokens_df[all_tokens_df['author_name'] == author]['clean_tokens']
        stats['top_words_author'][author] = author_tokens.value_counts().head(20).to_dict()
        
    stats['word_cloud_overall'] = all_tokens_df['clean_tokens'].value_counts().head(100).to_dict()
    stats['word_cloud_author'] = {author: all_tokens_df[all_tokens_df['author_name'] == author]['clean_tokens'].value_counts().head(100).to_dict() for author in top_authors}
    
    text_msgs['week_str'] = text_msgs['datetime'].dt.to_period('W').astype(str)
    stats['sentiment_timeline'] = text_msgs.groupby('week_str')['sentiment_score'].mean().to_dict()
    
    text_msgs['date_only_str'] = text_msgs['datetime'].dt.date.astype(str)
    daily_sentiment = text_msgs.groupby('date_only_str')['sentiment_score'].mean()
    stats['most_positive_days'] = daily_sentiment.nlargest(5).to_dict()
    stats['most_negative_days'] = daily_sentiment.nsmallest(5).to_dict()
    
    all_emojis_df = text_msgs.explode('extracted_emojis').dropna(subset=['extracted_emojis'])
    stats['top_emojis_overall'] = all_emojis_df['extracted_emojis'].value_counts().head(15).to_dict()
    
    author_emojis = {}
    for author in top_authors:
        author_emojis[author] = all_emojis_df[all_emojis_df['author_name'] == author]['extracted_emojis'].value_counts()
    stats['top_emojis_author'] = {a: s.head(15).to_dict() for a, s in author_emojis.items()}
        
    if len(authors) >= 2:
        a1, a2 = authors[0], authors[1]
        e1 = set(author_emojis[a1].index) if a1 in author_emojis else set()
        e2 = set(author_emojis[a2].index) if a2 in author_emojis else set()
        stats['exclusive_emojis'] = {
            a1: list(e1 - e2)[:10],
            a2: list(e2 - e1)[:10]
        }
        
    text_msgs['emoji_count'] = text_msgs['extracted_emojis'].apply(len)
    stats['avg_emojis_per_message'] = text_msgs.groupby('author_name')['emoji_count'].mean().to_dict()
    
    pure_emoji_mask = (text_msgs['emoji_count'] > 0) & (text_msgs['word_count'] == 0)
    stats['pure_emoji_messages_percentage'] = (text_msgs[pure_emoji_mask].groupby('author_name').size() / text_msgs.groupby('author_name').size() * 100).fillna(0).to_dict()
    
    all_emojis_df['category'] = all_emojis_df['extracted_emojis'].apply(get_emoji_category)
    stats['emoji_categories'] = all_emojis_df[all_emojis_df['category'] != 'other'].groupby(['author_name', 'category']).size().unstack(fill_value=0).to_dict('index')
    
    stats['parasite_counts'] = text_msgs.groupby('author_name')['parasite_count'].sum().to_dict()
    stats['profanity_counts'] = text_msgs.groupby('author_name')['profanity_count'].sum().to_dict()
    
    # Topics caching logic
    worthy_mask = text_msgs['is_topic_worthy'] == True
    worthy_msgs = text_msgs[worthy_mask].copy()
    
    stats['topic_exclusion_percentage'] = 0.0
    if len(text_msgs) > 0:
        excluded = len(text_msgs) - len(worthy_msgs)
        stats['topic_exclusion_percentage'] = excluded / len(text_msgs) * 100
        
    if 'embedding' in worthy_msgs.columns and len(worthy_msgs) > 10:
        texts = worthy_msgs['clean_text'].tolist()
        embeddings = np.vstack(worthy_msgs['embedding'].values)
        
        topics_loaded = False
        if file_hash and is_stage_cached(file_hash, "06_topics"):
            topic_model = load_checkpoint(file_hash, "06_topics")
            if topic_model is not None:
                topics_loaded = True
                # Need to predict topics
                topics, _ = topic_model.transform(texts, embeddings=embeddings)
        
        if not topics_loaded:
            min_topic_size = max(15, len(worthy_msgs) // 200)
            nr_topics = "auto"
            if topic_count != "auto":
                try:
                    nr_topics = int(topic_count)
                except ValueError:
                    pass
            vectorizer_model = CountVectorizer(ngram_range=(1, 2), stop_words=list(get_all_stopwords()), min_df=3)
            topic_model = BERTopic(embedding_model=get_sentence_model(quality=embedding_quality), vectorizer_model=vectorizer_model, language="multilingual", nr_topics=nr_topics, min_topic_size=min_topic_size, calculate_probabilities=False, verbose=False)
            
            texts_for_bertopic = worthy_msgs['semantic_tokens'].apply(lambda x: ' '.join(x)).tolist()
            topics, _ = topic_model.fit_transform(texts_for_bertopic, embeddings=embeddings)
            
            outlier_count = topics.count(-1)
            if outlier_count / len(topics) > 0.3:
                try:
                    new_topics = topic_model.reduce_outliers(texts_for_bertopic, topics, strategy="embeddings", embeddings=embeddings)
                    topic_model.update_topics(texts_for_bertopic, topics=new_topics, vectorizer_model=vectorizer_model)
                    topics = new_topics
                except Exception:
                    pass
                    
            if file_hash:
                save_checkpoint(file_hash, "06_topics", topic_model)
                
        worthy_msgs['cluster'] = topics
        text_msgs.loc[worthy_mask, 'cluster'] = topics
        
        topic_info = topic_model.get_topic_info()
        clusters_info = []
        
        labels_cached = False
        labels_dict = {}
        if file_hash and is_stage_cached(file_hash, "07_topic_labels"):
            labels_dict = load_checkpoint(file_hash, "07_topic_labels")
            if labels_dict:
                labels_cached = True
                
        for _, row in topic_info.iterrows():
            topic_id = row['Topic']
            if topic_id == -1: continue
                
            top_words = [w[0] for w in topic_model.get_topic(topic_id)[:5]]
            examples = worthy_msgs[worthy_msgs['cluster'] == topic_id]['text'].head(3).tolist()
            name = " / ".join(top_words[:3])
            
            if labels_cached and str(topic_id) in labels_dict:
                name = labels_dict[str(topic_id)]
            elif use_llm:
                if task_id:
                    set_custom_stage_text(task_id, f"Генерация названий тем через LLM ({llm_model})...")
                try:
                    prompt = f"""Вот ключевые слова и примеры сообщений из одной темы переписки в мессенджере:
Ключевые слова: {', '.join(top_words)}
Примеры сообщений:
1. {examples[0] if len(examples) > 0 else ''}
2. {examples[1] if len(examples) > 1 else ''}
3. {examples[2] if len(examples) > 2 else ''}

Придумай короткое название этой темы (2-4 слова, на русском, как заголовок).
Ответь ТОЛЬКО названием, без пояснений и кавычек."""
                    
                    response = httpx.post(
                        "http://localhost:11434/api/generate",
                        json={"model": llm_model, "prompt": prompt, "stream": False},
                        timeout=300.0
                    )
                    if response.status_code == 200:
                        llm_name = response.json().get('response', '').strip(' "''')
                        if llm_name:
                            name = llm_name
                except Exception as e:
                    print(f"Ollama error: {e}")
            
            clusters_info.append({
                'id': topic_id,
                'size': row['Count'],
                'top_words': top_words,
                'examples': examples,
                'name': name
            })
            
        stats['clusters'] = clusters_info
        
        if file_hash and not labels_cached:
            new_labels_dict = {str(c['id']): c['name'] for c in clusters_info}
            save_checkpoint(file_hash, "07_topic_labels", new_labels_dict)
            
        # Dynamics over time
        worthy_msgs['datetime'] = pd.to_datetime(worthy_msgs['datetime'])
        try:
            texts_for_bertopic = worthy_msgs['semantic_tokens'].apply(lambda x: ' '.join(x)).tolist()
            topics_over_time = topic_model.topics_over_time(texts_for_bertopic, topics, worthy_msgs['datetime'].tolist(), nr_bins=20, datetime_format="%Y-%m")
            # Format to dict for frontend
            time_dict = {}
            for _, row in topics_over_time.iterrows():
                t_str = row['Timestamp'].strftime('%Y-%m')
                if t_str not in time_dict:
                    time_dict[t_str] = {}
                time_dict[t_str][row['Topic']] = row['Frequency']
            stats['topic_dynamics'] = time_dict
        except Exception:
            # Fallback
            worthy_msgs['month_str'] = worthy_msgs['datetime'].dt.to_period('M').astype(str)
            stats['topic_dynamics'] = worthy_msgs.groupby(['month_str', 'cluster']).size().unstack(fill_value=0).to_dict('index')
    
    # 35. Lexical diversity
    lexical_diversity = {}
    for author in top_authors:
        author_tokens = all_tokens_df[all_tokens_df['author_name'] == author]['clean_tokens']
        total = len(author_tokens)
        unique = author_tokens.nunique()
        lexical_diversity[author] = unique / total if total > 0 else 0
    stats['lexical_diversity'] = lexical_diversity
    
    # 36. Signature phrases (Log-Odds Ratio approx) - use semantic_tokens
    semantic_tokens_df = text_msgs[text_msgs['is_topic_worthy']].explode('semantic_tokens').dropna(subset=['semantic_tokens'])
    stats['signature_phrases'] = {}
    if len(top_authors) >= 2:
        # For each author, compare their frequencies against all other authors combined
        author_freqs = {}
        for a in top_authors:
            author_freqs[a] = semantic_tokens_df[semantic_tokens_df['author_name'] == a]['semantic_tokens'].value_counts()
            
        for a in top_authors:
            freq_a = author_freqs[a]
            other_authors = [x for x in top_authors if x != a]
            
            # Combine frequencies of others
            freq_others = pd.Series(dtype=int)
            for oa in other_authors:
                freq_others = freq_others.add(author_freqs[oa], fill_value=0)
                
            total_a = freq_a.sum() or 1
            total_others = freq_others.sum() or 1
            
            common_words = set(freq_a.head(1000).index).intersection(set(freq_others.head(1000).index))
            ratios = []
            for w in common_words:
                f1 = freq_a.get(w, 0) / total_a
                f2 = freq_others.get(w, 0) / total_others
                if f1 > 0 and f2 > 0:
                    ratios.append((w, f1 / f2))
                    
            ratios.sort(key=lambda x: x[1], reverse=True)
            stats['signature_phrases'][a] = [x[0] for x in ratios[:10]]
        
    # 37. Mentions (capitalized words not at start)
    # Improved NER with length and pronoun filters
    import pymorphy3
    from backend.preprocessing import morph
    mentions = []
    
    BAD_NER = {'я', 'ты', 'он', 'она', 'оно', 'мы', 'вы', 'они', 'а', 'и', 'в', 'с', 'у', 'о', 'к', 'по'}
    
    for txt in text_msgs[text_msgs['is_topic_worthy']]['text'].dropna():
        if isinstance(txt, str):
            words = txt.split()
            if len(words) > 1:
                # Exclude first word
                caps = [w.strip('.,!?') for w in words[1:] if w.istitle()]
                for cap in caps:
                    if len(cap) < 3:
                        continue
                    lemma = morph.parse(cap)[0].normal_form
                    if lemma.lower() in BAD_NER:
                        continue
                    mentions.append(lemma.title())
                    
    stats['top_mentions'] = dict(Counter(mentions).most_common(10))
    
    # 38. Plan extraction
    plan_regex = re.compile(r'\b(завтра|сегодня|в субботу|в воскресенье|в пятницу|на выходных)\b', re.IGNORECASE)
    plans = df[df['text'].str.contains(plan_regex, na=False, regex=True)].head(20)[['datetime', 'author_name', 'text']]
    plans['datetime'] = plans['datetime'].astype(str)
    stats['extracted_plans'] = plans.to_dict('records')
    
    # 39. Q to Statement ratio
    questions = df['text'].str.contains(r'\?', na=False)
    statements = ~questions & (df['text'].str.len() > 0)
    q_counts = df[questions].groupby('author_name').size()
    s_counts = df[statements].groupby('author_name').size()
    stats['question_ratio'] = (q_counts / (s_counts + q_counts) * 100).fillna(0).to_dict()
    
    # 40 & 41. Apologies & Compliments
    stats['apologies_count'] = all_tokens_df[all_tokens_df['clean_tokens'].isin(APOLOGIES)].groupby('author_name').size().to_dict()
    stats['compliments_count'] = all_tokens_df[all_tokens_df['clean_tokens'].isin(COMPLIMENTS)].groupby('author_name').size().to_dict()
    
    # 42. Formality index
    slang_counts = all_tokens_df[all_tokens_df['clean_tokens'].isin(SLANG_WORDS)].groupby('author_name').size()
    total_words = all_tokens_df.groupby('author_name').size()
    stats['slang_percentage'] = (slang_counts / total_words * 100).fillna(0).to_dict()
    
    # 44 & 45. Lowest sentiment messages & Breaking points
    if 'sentiment_score' in text_msgs:
        lowest_msgs = text_msgs.nsmallest(10, 'sentiment_score')[['datetime', 'author_name', 'text', 'sentiment_score']]
        lowest_msgs['datetime'] = lowest_msgs['datetime'].astype(str)
        stats['lowest_sentiment_messages'] = lowest_msgs.to_dict('records')
        
        # 45. Breaking points
        # 7-day rolling average
        text_msgs = text_msgs.sort_values('datetime')
        daily_sentiment = text_msgs.groupby('date_only_str')['sentiment_score'].mean()
        rolling = daily_sentiment.rolling(window=7, min_periods=1).mean()
        diffs = rolling.diff().abs()
        top_breaks = diffs.nlargest(5).index.tolist()
        stats['breaking_points'] = top_breaks
        
    # 46. Irony heuristic
    # Negative sentiment + laugh emoji
    if 'sentiment_score' in text_msgs:
        laugh_emojis = EMOJI_CATEGORIES['laugh']
        def has_laugh(emojis):
            return any(e in laugh_emojis for e in emojis)
            
        irony_mask = (text_msgs['sentiment_score'] < 0) & text_msgs['extracted_emojis'].apply(has_laugh)
        stats['irony_percentage'] = (text_msgs[irony_mask].groupby('author_name').size() / total_words * 100).fillna(0).to_dict()
        stats['irony_is_estimate'] = True
        
    # 47. Bigrams
    bigrams = []
    for tokens in semantic_tokens_df['semantic_tokens']:
        if isinstance(tokens, list) and len(tokens) >= 2:
            bigrams.extend(zip(tokens[:-1], tokens[1:]))
    
    stats['top_bigrams'] = {}
    if len(bigrams) > 0:
        stats['top_bigrams'] = {' '.join(k): v for k, v in Counter(bigrams).most_common(15)}
    
    # 48. CAPS LOCK
    def is_caps(txt):
        if not isinstance(txt, str) or len(txt) < 4: return False
        alphas = [c for c in txt if c.isalpha()]
        if not alphas: return False
        return sum(1 for c in alphas if c.isupper()) / len(alphas) > 0.6
        
    caps_msgs = text_msgs[text_msgs['text'].apply(is_caps)].groupby('author_name').size()
    stats['caps_percentage'] = (caps_msgs / len(text_msgs) * 100).fillna(0).to_dict()
    
    # 49. Emotional sync
    if len(top_authors) >= 2 and 'sentiment_score' in text_msgs:
        # Create a time-series per author
        daily_sentiments = {a: text_msgs[text_msgs['author_name'] == a].groupby('date_only_str')['sentiment_score'].mean() for a in top_authors}
        
        sync_results = {}
        # Calculate pairwise for all combinations
        from itertools import combinations
        for a1, a2 in combinations(top_authors, 2):
            common_days = daily_sentiments[a1].index.intersection(daily_sentiments[a2].index)
            if len(common_days) > 5:
                corr, _ = pearsonr(daily_sentiments[a1][common_days], daily_sentiments[a2][common_days])
                sync_results[f"{a1} & {a2}"] = float(corr)
            else:
                sync_results[f"{a1} & {a2}"] = 0.0
        stats['emotional_sync_correlation'] = sync_results
    else:
        stats['emotional_sync_correlation'] = None
            
    # 50. Couple Dictionary (N-grams frequent here)
    # Just reusing top bigrams that are highly frequent
    stats['couple_dictionary'] = list(stats['top_bigrams'].keys())[:5]
    
    # === NEW SEMANTIC METRICS (TZ #5) ===
    from sklearn.metrics.pairwise import cosine_similarity
    from backend.reference_phrases import CARE_PHRASES, GRATITUDE_PHRASES, FLIRT_PHRASES, HUMOR_PHRASES
    
    # 1. Emotional Portrait
    emo_cols = ['emo_joy', 'emo_sadness', 'emo_anger', 'emo_fear', 'emo_surprise']
    if all(c in text_msgs.columns for c in emo_cols):
        stats['emotional_portrait'] = text_msgs.groupby('author_name')[emo_cols].mean().to_dict('index')
        
        # 2. Emotional Arcs (14-day window)
        text_msgs['arc_period'] = text_msgs['datetime'].dt.floor('14D').astype(str)
        arcs = text_msgs.groupby('arc_period')['dominant_emotion'].agg(lambda x: x.mode()[0] if not x.empty else 'neutral')
        stats['emotional_arcs'] = arcs.to_dict()
        
        # 3. Kindest Message
        kind_msgs = text_msgs[text_msgs['word_count'] > 3]
        if not kind_msgs.empty:
            kindest = kind_msgs.loc[kind_msgs['emo_joy'].idxmax()]
            stats['kindest_message'] = {'author': kindest['author_name'], 'text': kindest['text'], 'date': str(kindest['datetime']), 'score': float(kindest['emo_joy'])}
            
        # 4. Warmest & Tensest Dialogues
        if len(text_msgs) >= 5:
            text_msgs = text_msgs.sort_values('datetime')
            text_msgs['rolling_joy'] = text_msgs['emo_joy'].rolling(5).mean()
            text_msgs['rolling_anger'] = text_msgs['emo_anger'].rolling(5).mean()
            authors = text_msgs['author_name'].values
            text_msgs['unique_authors_in_window'] = [len(set(authors[i-4:i+1])) if i >= 4 else np.nan for i in range(len(authors))]
            
            valid_windows = text_msgs[text_msgs['unique_authors_in_window'] >= 2]
            if not valid_windows.empty:
                warmest_idx = valid_windows['rolling_joy'].idxmax()
                tensest_idx = valid_windows['rolling_anger'].idxmax()
                
                warmest_pos = text_msgs.index.get_loc(warmest_idx)
                tensest_pos = text_msgs.index.get_loc(tensest_idx)
                
                warmest_dialogue = text_msgs.iloc[max(0, warmest_pos-4):warmest_pos+1]
                tensest_dialogue = text_msgs.iloc[max(0, tensest_pos-4):tensest_pos+1]
                
                stats['warmest_dialogue'] = warmest_dialogue[['author_name', 'text', 'datetime']].assign(datetime=lambda x: x['datetime'].astype(str)).to_dict('records')
                stats['tensest_dialogue'] = tensest_dialogue[['author_name', 'text', 'datetime']].assign(datetime=lambda x: x['datetime'].astype(str)).to_dict('records')
                
    # 5. Semantic similarity metrics
    if 'embedding' in text_msgs.columns and len(text_msgs) > 0:
        emb_matrix = np.vstack(text_msgs['embedding'].values)
        model = get_sentence_model(quality=embedding_quality)
        
        def get_max_sim(phrases):
            if not phrases: return np.zeros(len(emb_matrix))
            phrase_embs = model.encode(phrases)
            sims = cosine_similarity(emb_matrix, phrase_embs)
            return sims.max(axis=1)
            
        text_msgs['sim_care'] = get_max_sim(CARE_PHRASES)
        text_msgs['sim_gratitude'] = get_max_sim(GRATITUDE_PHRASES)
        text_msgs['sim_flirt'] = get_max_sim(FLIRT_PHRASES)
        text_msgs['sim_humor'] = get_max_sim(HUMOR_PHRASES)
        
        stats['care_detected'] = text_msgs[text_msgs['sim_care'] > 0.65].groupby('author_name').size().to_dict()
        stats['gratitude_detected'] = text_msgs[text_msgs['sim_gratitude'] > 0.65].groupby('author_name').size().to_dict()
        stats['flirt_detected'] = text_msgs[text_msgs['sim_flirt'] > 0.65].groupby('author_name').size().to_dict()
        
        from sklearn.metrics.pairwise import paired_cosine_distances
        if len(emb_matrix) > 1:
            distances = paired_cosine_distances(emb_matrix[1:], emb_matrix[:-1])
            text_msgs['emb_shift'] = np.insert(distances, 0, 0.0)
        else:
            text_msgs['emb_shift'] = 0.0
            
        humor_mask = (text_msgs['sim_humor'] > 0.6) & (text_msgs['emb_shift'] > 0.4)
        stats['humor_detected'] = text_msgs[humor_mask].groupby('author_name').size().to_dict()
        
        # 6. Semantic Style Similarity
        if len(top_authors) == 2:
            a1_emb = emb_matrix[text_msgs['author_name'] == top_authors[0]].mean(axis=0)
            a2_emb = emb_matrix[text_msgs['author_name'] == top_authors[1]].mean(axis=0)
            stats['style_similarity'] = float(cosine_similarity([a1_emb], [a2_emb])[0][0] * 100)
        elif len(top_authors) > 2:
            # For groups, find top-3 most similar pairs
            author_embs = {}
            for a in top_authors:
                a_mask = text_msgs['author_name'] == a
                if a_mask.any():
                    author_embs[a] = emb_matrix[a_mask].mean(axis=0)
                    
            pairs = []
            a_list = list(author_embs.keys())
            for i in range(len(a_list)):
                for j in range(i+1, len(a_list)):
                    sim = float(cosine_similarity([author_embs[a_list[i]]], [author_embs[a_list[j]]])[0][0] * 100)
                    pairs.append({'pair': f"{a_list[i]} & {a_list[j]}", 'sim': sim})
                    
            pairs.sort(key=lambda x: x['sim'], reverse=True)
            stats['style_similarity_group'] = pairs[:3]
            
        # 7. UMAP Projection
        try:
            import umap
            if len(emb_matrix) > 3000:
                sample_idx = np.random.choice(len(emb_matrix), 3000, replace=False)
                umap_embs = emb_matrix[sample_idx]
                umap_texts = text_msgs.iloc[sample_idx]
            else:
                umap_embs = emb_matrix
                umap_texts = text_msgs
                
            reducer = umap.UMAP(n_components=2, random_state=42)
            proj = reducer.fit_transform(umap_embs)
            
            stats['umap_projection'] = {
                'x': proj[:, 0].tolist(),
                'y': proj[:, 1].tolist(),
                'texts': umap_texts['text'].astype(str).str.slice(0, 100).tolist(),
                'topics': umap_texts['topic'].tolist() if 'topic' in umap_texts.columns else [-1]*len(umap_texts)
            }
        except Exception as e:
            stats['umap_projection'] = {}
            
    # 8. Emotional Empathy
    if len(authors) == 2 and 'sentiment_score' in text_msgs:
        text_msgs['prev_sentiment'] = text_msgs['sentiment_score'].shift(1)
        text_msgs['prev_author'] = text_msgs['author_name'].shift(1)
        
        responses = text_msgs[text_msgs['author_name'] != text_msgs['prev_author']].dropna(subset=['sentiment_score', 'prev_sentiment'])
        empathy_scores = {}
        for author in authors:
            author_responses = responses[responses['author_name'] == author]
            if len(author_responses) > 10:
                corr, _ = pearsonr(author_responses['sentiment_score'], author_responses['prev_sentiment'])
                empathy_scores[author] = float(corr) if not np.isnan(corr) else 0.0
            else:
                empathy_scores[author] = 0.0
        stats['emotional_empathy'] = empathy_scores
    elif len(authors) > 2:
        stats['emotional_empathy'] = None # Hidden for groups

    # 9. Top days by emotional amplitude
    if 'sentiment_score' in text_msgs:
        daily_amplitude = text_msgs.groupby('date_only_str')['sentiment_score'].apply(lambda x: x.abs().sum())
        stats['top_emotional_days'] = daily_amplitude.nlargest(5).to_dict()
    
    # 10. Most frequent Q->A pair
    q_mask = text_msgs['text'].str.contains(r'\?', na=False)
    text_msgs['is_question'] = q_mask
    text_msgs['prev_is_question'] = text_msgs['is_question'].shift(1)
    
    if 'prev_author' not in text_msgs.columns:
        text_msgs['prev_author'] = text_msgs['author_name'].shift(1)
        
    answers = text_msgs[(text_msgs['prev_is_question'] == True) & (text_msgs['author_name'] != text_msgs['prev_author'])]
    if not answers.empty:
        ans_tokens = answers.explode('clean_tokens').dropna(subset=['clean_tokens'])
        stats['top_answer_patterns'] = ans_tokens['clean_tokens'].value_counts().head(5).to_dict()
    # 11. Echo phrases
    if len(authors) == 2:
        a1, a2 = authors[0], authors[1]
        a1_tokens = set(text_msgs[text_msgs['author_name'] == a1].explode('clean_tokens')['clean_tokens'].dropna())
        a2_tokens = set(text_msgs[text_msgs['author_name'] == a2].explode('clean_tokens')['clean_tokens'].dropna())
        common = a1_tokens.intersection(a2_tokens)
        stats['echo_phrases'] = list(common)[:10]
    elif len(authors) > 2:
        stats['echo_phrases'] = None # Complex for groups, hiding for now
        
    if file_hash:
        from backend.checkpoint import save_checkpoint
        save_checkpoint(file_hash, "08_semantic_extras", stats)
        # Also need to make sure 07_topic_labels is cached in the loop above where topics are named
        
    return stats
