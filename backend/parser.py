import json
import pandas as pd
from typing import Dict, Any, List

def extract_text(text_obj: Any) -> str:
    """Extracts plain text from Telegram's text representation."""
    if isinstance(text_obj, str):
        return text_obj
    if isinstance(text_obj, list):
        parts = []
        for item in text_obj:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and 'text' in item:
                parts.append(item['text'])
        return ''.join(parts)
    return ""

def parse_telegram_export(filepath: str) -> pd.DataFrame:
    """Parses a Telegram chat export JSON file into a normalizer DataFrame."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    messages = data.get('messages', [])
    
    # Calculate raw ID gap before filtering (Bug #5)
    raw_deleted_estimate = 0
    if messages:
        # Some messages might not have 'id', filter them out for min/max
        ids = [m.get('id') for m in messages if isinstance(m.get('id'), int)]
        if ids:
            min_id = min(ids)
            max_id = max(ids)
            expected_count = max_id - min_id + 1
            raw_deleted_estimate = max(0, expected_count - len(messages))
    
    parsed_messages = []
    
    for msg in messages:
        # Bug #3: Ignore service messages entirely for the main dataset
        if msg.get('type') == 'service':
            continue
            
        # Handle author mapping, fallback to id for anonymous/system
        author_id = msg.get('from_id')
        author_name = msg.get('from')
        
        # Explicit check for author existence so we don't pick up phantom System
        if not author_id or str(author_name).strip() == "System" or str(author_name).strip() == "Telegram":
            continue
            
        # Parse text
        raw_text = extract_text(msg.get('text', ''))
        
        # Parse reactions
        reactions = msg.get('reactions', [])
        reactions_count = 0
        if isinstance(reactions, list):
            for r in reactions:
                reactions_count += r.get('count', 1)
                
        # Media type mapping
        media_type = msg.get('media_type')
        if not media_type:
            if 'photo' in msg:
                media_type = 'photo'
            elif 'file' in msg:
                media_type = 'file'
                
        # Handle word and char counts
        # This is a naive count, clean_text will be done in preprocessing
        char_count = len(raw_text)
        word_count = len(raw_text.split()) if raw_text else 0
        
        parsed_messages.append({
            'message_id': msg.get('id'),
            'datetime': msg.get('date'),
            'author_id': author_id,
            'author_name': author_name,
            'text': raw_text,
            'message_type': msg.get('type'),
            'media_type': media_type,
            'is_forwarded': 'forwarded_from' in msg,
            'is_edited': 'edited' in msg,
            'reactions_count': reactions_count,
            'char_count': char_count,
            'word_count': word_count,
            'reactions_data': reactions, # raw reactions for later
            'grouped_id': msg.get('reply_to_message_id') # fallback for grouped if missing, but we'll try 'grouped_id' if exists
        })
        
        # Actually in telegram export it is 'grouped_id' or 'reply_to_message_id' doesn't mean grouped.
        # Let's just grab 'grouped_id'
        parsed_messages[-1]['grouped_id'] = msg.get('grouped_id')
        
    df = pd.DataFrame(parsed_messages)
    
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # Fix author names by grouping by author_id and taking the last non-null name
        author_map = df.dropna(subset=['author_name']).groupby('author_id')['author_name'].last()
        df['author_name'] = df['author_id'].map(author_map).fillna(df['author_name'])
        
        # Store raw deleted estimate in df attrs so stats module can access it
        df.attrs['raw_deleted_estimate'] = raw_deleted_estimate
        
    return df
