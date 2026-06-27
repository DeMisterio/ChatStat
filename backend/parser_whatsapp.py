import pandas as pd
import re
import datetime
from dateutil import parser as dt_parser

# Regex for bracketed format: [15.01.2024, 10:23:45] Name: Message
# or [15.01.2024, 10:23:45 PM] Name: Message
REGEX_BRACKET = re.compile(r'^\[(?P<date>[^,]+),\s*(?P<time>[^\]]+)\]\s+(?P<content>.*)$')

# Regex for hyphen format: 15.01.2024, 10:23 - Name: Message
# or 15.01.2024, 10:23 PM - Name: Message
REGEX_HYPHEN = re.compile(r'^(?P<date>\d{1,4}[./-]\d{1,2}[./-]\d{1,4}),\s*(?P<time>[^-]+)\s*-\s+(?P<content>.*)$')

# Regex for author extraction
REGEX_AUTHOR = re.compile(r'^(?P<author>[^:]+):\s+(?P<message>.*)$')

# Media placeholders
MEDIA_PATTERNS = [
    (re.compile(r'^\s*<Media omitted>\s*$', re.IGNORECASE), 'unknown_media'),
    (re.compile(r'^\s*<Прикрепленный файл:.*?\.jpg>\s*$', re.IGNORECASE), 'photo'),
    (re.compile(r'^\s*<Прикрепленный файл:.*?\.mp4>\s*$', re.IGNORECASE), 'video'),
    (re.compile(r'^\s*<Прикрепленный файл:.*?\.mp3>\s*$', re.IGNORECASE), 'voice_message'),
    (re.compile(r'^\s*<Прикрепленный файл:.*?>\s*$', re.IGNORECASE), 'document'),
    (re.compile(r'^\s*audio omitted\s*$', re.IGNORECASE), 'voice_message'),
    (re.compile(r'^\s*video omitted\s*$', re.IGNORECASE), 'video'),
    (re.compile(r'^\s*image omitted\s*$', re.IGNORECASE), 'photo'),
    (re.compile(r'^\s*Voice call\s*$', re.IGNORECASE), 'call'),
    (re.compile(r'^\s*Missed voice call\s*$', re.IGNORECASE), 'call')
]

# Deleted messages
DELETED_PATTERNS = [
    re.compile(r'^\s*This message was deleted\s*$', re.IGNORECASE),
    re.compile(r'^\s*Это сообщение удалено\s*$', re.IGNORECASE),
    re.compile(r'^\s*Данное сообщение удалено\s*$', re.IGNORECASE)
]

def clean_text(text):
    if not isinstance(text, str):
        return text
    # Remove LTR mark
    return text.replace('\u200e', '').replace('\u200f', '').strip()

def parse_whatsapp_export(filepath: str) -> pd.DataFrame:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    messages = []
    current_msg = None
    msg_id = 1
    
    for line in lines:
        line = clean_text(line)
        if not line:
            continue
            
        # Try matching bracket format
        m = REGEX_BRACKET.match(line)
        is_new_msg = False
        
        if m:
            is_new_msg = True
        else:
            # Try matching hyphen format
            m = REGEX_HYPHEN.match(line)
            if m:
                is_new_msg = True
                
        if is_new_msg:
            # Save previous message
            if current_msg:
                messages.append(current_msg)
                
            date_str = m.group('date').strip()
            time_str = m.group('time').strip()
            content = m.group('content').strip()
            
            # Parse datetime
            try:
                dt = dt_parser.parse(f"{date_str} {time_str}", dayfirst=True, fuzzy=True)
            except Exception:
                # Fallback if unparseable
                continue
                
            # Check for author
            auth_m = REGEX_AUTHOR.match(content)
            if auth_m:
                author_name = auth_m.group('author').strip()
                text = auth_m.group('message').strip()
                msg_type = "message"
            else:
                author_name = None
                text = content
                msg_type = "service"
                
            current_msg = {
                'message_id': msg_id,
                'datetime': dt,
                'author_id': author_name.lower() if author_name else None,
                'author_name': author_name,
                'text': text,
                'message_type': msg_type,
                'media_type': None,
                'is_forwarded': False,
                'is_edited': False,
                'is_deleted_placeholder': False,
                'reactions_count': 0
            }
            msg_id += 1
            
        else:
            # Multi-line message continuation
            if current_msg and current_msg['message_type'] == 'message':
                current_msg['text'] += '\n' + line
                
    # Append last message
    if current_msg:
        messages.append(current_msg)
        
    df = pd.DataFrame(messages)
    
    if df.empty:
        return pd.DataFrame(columns=[
            'message_id', 'datetime', 'author_id', 'author_name', 'text', 'clean_text',
            'message_type', 'media_type', 'is_forwarded', 'is_edited', 'reactions_count',
            'char_count', 'word_count', 'is_deleted_placeholder'
        ])
        
    # Process text post-parsing to find media and deleted placeholders
    def process_placeholders(row):
        text = row['text']
        
        # Check deleted
        for p in DELETED_PATTERNS:
            if p.match(text):
                row['is_deleted_placeholder'] = True
                row['text'] = ''
                return row
                
        # Check media
        for p, mtype in MEDIA_PATTERNS:
            if p.match(text):
                row['media_type'] = mtype
                row['text'] = ''
                return row
                
        return row

    df = df.apply(process_placeholders, axis=1)
    
    # Calculate word/char count
    df['char_count'] = df['text'].apply(lambda x: len(str(x)) if pd.notnull(x) else 0)
    df['word_count'] = df['text'].apply(lambda x: len(str(x).split()) if pd.notnull(x) else 0)
    
    df['clean_text'] = df['text']  # Initial copy, preprocessing.py will clean it properly
    
    # Ensure source field is added later in main.py, but we provide standard schema
    return df
