import re
import string
import pymorphy3
import emoji
from backend.stopwords import ALL_STOPWORDS, PARASITE_WORDS, PROFANITY_AND_EXCLAMATIONS, TECHNICAL_GARBAGE, REACTIVE_PHRASES, LAUGH_REGEX

# Initialize pymorphy3 analyzer once
morph = pymorphy3.MorphAnalyzer()

# Regex to remove punctuation
PUNCTUATION_REGEX = re.compile(f"[{re.escape(string.punctuation)}«»…—–]")

# URL Regex
URL_REGEX = re.compile(r'https?://\S+|www\.\S+')

def extract_emojis(text: str) -> list:
    """Extracts all emojis from text as a list using the emoji library."""
    return [e['emoji'] for e in emoji.emoji_list(text)]

def remove_emojis(text: str) -> str:
    """Removes all emojis from text."""
    return emoji.replace_emoji(text, replace='')

def get_clean_tokens(text: str, exclude_categories: list[str] = None) -> list[str]:
    """
    Single source of truth for text cleaning and lemmatization.
    exclude_categories can contain: 'stopwords', 'profanity', 'technical'
    """
    if not isinstance(text, str) or not text.strip():
        return []
        
    if exclude_categories is None:
        exclude_categories = ['stopwords']
        
    # Strip URLs if requested
    if 'technical' in exclude_categories:
        text = URL_REGEX.sub(' ', text)
        
    text_no_emoji = remove_emojis(text)
    text_lower = text_no_emoji.lower()
    text_no_punct = PUNCTUATION_REGEX.sub(' ', text_lower)
    tokens = text_no_punct.split()
    
    clean_tokens = []
    
    for token in tokens:
        lemma = morph.parse(token)[0].normal_form
        
        if LAUGH_REGEX.match(lemma) or LAUGH_REGEX.match(token):
            continue
            
        if len(lemma) <= 1:
            continue
            
        exclude = False
        if 'stopwords' in exclude_categories and lemma in ALL_STOPWORDS:
            exclude = True
        if 'profanity' in exclude_categories and (lemma in PROFANITY_AND_EXCLAMATIONS or token in PROFANITY_AND_EXCLAMATIONS):
            exclude = True
        if 'technical' in exclude_categories and lemma in TECHNICAL_GARBAGE:
            exclude = True
            
        if not exclude:
            clean_tokens.append(lemma)
            
    return clean_tokens

def is_topic_worthy(semantic_tokens: list[str], raw_text: str) -> bool:
    """Checks if a message is substantive enough for topic clustering."""
    if not isinstance(raw_text, str):
        return False
        
    # Condition 1: Less than 3 meaningful tokens
    if len(semantic_tokens) < 3:
        return False
        
    # Condition 2: 1-2 words in raw text
    tokens_raw = raw_text.split()
    if len(tokens_raw) <= 2:
        return False
        
    # Condition 3: Exact match with a reactive phrase (ignoring punctuation and case)
    clean_raw = PUNCTUATION_REGEX.sub('', raw_text.lower().strip())
    if clean_raw in REACTIVE_PHRASES:
        return False
        
    return True

def clean_and_tokenize(text: str) -> dict:
    """
    Returns a dictionary with extracted features for the text.
    """
    if not isinstance(text, str) or not text.strip():
        return {
            'clean_text': '',
            'clean_tokens': [],
            'semantic_tokens': [],
            'extracted_emojis': [],
            'parasite_count': 0,
            'profanity_count': 0,
            'is_topic_worthy': False
        }
        
    extracted_emojis = extract_emojis(text)
    text_no_emoji = remove_emojis(text)
    
    # Clean text for ML (keep stopwords, just normalize spaces)
    clean_text = ' '.join(text_no_emoji.split())
    
    # Standard tokens for general stats (only drop stopwords)
    clean_tokens = get_clean_tokens(text, exclude_categories=['stopwords'])
    
    # Strict tokens for semantic clustering and dictionaries
    semantic_tokens = get_clean_tokens(text, exclude_categories=['stopwords', 'profanity', 'technical'])
    
    # Calculate parasites and profanity from raw split text
    tokens = PUNCTUATION_REGEX.sub(' ', text_no_emoji.lower()).split()
    parasite_count = 0
    profanity_count = 0
    
    for token in tokens:
        lemma = morph.parse(token)[0].normal_form
        if token in PARASITE_WORDS or lemma in PARASITE_WORDS:
            parasite_count += 1
        if token in PROFANITY_AND_EXCLAMATIONS or lemma in PROFANITY_AND_EXCLAMATIONS:
            profanity_count += 1
                
    worthy = is_topic_worthy(semantic_tokens, text)
    
    return {
        'clean_text': clean_text,
        'clean_tokens': clean_tokens,
        'semantic_tokens': semantic_tokens,
        'extracted_emojis': extracted_emojis,
        'parasite_count': parasite_count,
        'profanity_count': profanity_count,
        'is_topic_worthy': worthy
    }

def process_dataframe(df):
    """Applies preprocessing to the entire DataFrame."""
    if df.empty:
        return df
        
    # Apply processing to text column
    processed = df['text'].apply(clean_and_tokenize)
    
    # Expand dictionary into new columns
    df['clean_text'] = processed.apply(lambda x: x['clean_text'])
    df['clean_tokens'] = processed.apply(lambda x: x['clean_tokens'])
    df['semantic_tokens'] = processed.apply(lambda x: x['semantic_tokens'])
    df['extracted_emojis'] = processed.apply(lambda x: x['extracted_emojis'])
    df['parasite_count'] = processed.apply(lambda x: x['parasite_count'])
    df['profanity_count'] = processed.apply(lambda x: x['profanity_count'])
    df['is_topic_worthy'] = processed.apply(lambda x: x['is_topic_worthy'])
    
    return df
