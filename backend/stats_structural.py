import pandas as pd
import numpy as np

def compute_structural_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
        
    stats = {}
    
    # Pre-calculate some common series
    df = df.sort_values('datetime')
    df['prev_datetime'] = df['datetime'].shift(1)
    df['time_diff'] = (df['datetime'] - df['prev_datetime']).dt.total_seconds()
    df['prev_author_name'] = df['author_name'].shift(1)
    
    authors = df['author_name'].dropna().unique().tolist()
    
    # 1 & 2. Total messages & share
    author_counts = df['author_name'].value_counts()
    total_messages = len(df)
    stats['message_counts'] = author_counts.to_dict()
    stats['message_shares'] = (author_counts / total_messages * 100).to_dict()
    
    df['prev_grouped_id'] = df.get('grouped_id', pd.Series([None]*len(df))).shift(1)
    
    is_duplicate_album = (df['author_name'] == df['prev_author_name']) & \
                         (df['time_diff'] < 2) & \
                         (df.get('grouped_id', pd.Series([None]*len(df))).notna()) & \
                         (df.get('grouped_id', pd.Series([None]*len(df))) == df['prev_grouped_id'])
                         
    collapsed_df = df[~is_duplicate_album].copy()
    collapsed_df['prev_datetime'] = collapsed_df['datetime'].shift(1)
    collapsed_df['time_diff'] = (collapsed_df['datetime'] - collapsed_df['prev_datetime']).dt.total_seconds()
    collapsed_df['prev_author_name'] = collapsed_df['author_name'].shift(1)
    
    # 3 & 4. Response times (only when author changes)
    # Also ignore time_diff < 3 seconds to avoid capturing grouped media/bots
    responses = collapsed_df[(collapsed_df['author_name'] != collapsed_df['prev_author_name']) & (collapsed_df['time_diff'] >= 3)].copy()
    valid_responses = responses[responses['time_diff'] <= 12 * 3600] # Ignore > 12h
    
    if not valid_responses.empty:
        stats['response_time'] = {
            'mean_seconds': valid_responses['time_diff'].mean(),
            'median_seconds': valid_responses['time_diff'].median()
        }
        fastest = valid_responses.loc[valid_responses['time_diff'].idxmin()]
        slowest = valid_responses.loc[valid_responses['time_diff'].idxmax()]
        stats['fastest_response'] = {
            'time': fastest['time_diff'],
            'date': fastest['datetime'].isoformat(),
            'author': fastest['author_name'],
            'text': fastest['text']
        }
        stats['slowest_response'] = {
            'time': slowest['time_diff'],
            'date': slowest['datetime'].isoformat(),
            'author': slowest['author_name'],
            'text': slowest['text']
        }
    else:
        stats['response_time'] = {'mean_seconds': 0, 'median_seconds': 0}
        
    # 5. Hours distribution
    df['hour'] = df['datetime'].dt.hour
    hour_dist = df.groupby(['author_name', 'hour']).size().unstack(fill_value=0).to_dict('index')
    stats['hours_distribution'] = hour_dist
    
    # 6. Days of week distribution
    df['weekday'] = df['datetime'].dt.weekday
    weekday_dist = df.groupby(['author_name', 'weekday']).size().unstack(fill_value=0).to_dict('index')
    stats['weekday_distribution'] = weekday_dist
    
    # 7. Heatmap (hour x weekday) overall
    heatmap = df.groupby(['weekday', 'hour']).size().unstack(fill_value=0).values.tolist()
    stats['heatmap_activity'] = heatmap # 7 rows (weekdays), 24 cols
    
    # 7b. Most active hour by day of week
    heatmap_df = df.groupby(['weekday', 'hour']).size().unstack(fill_value=0)
    peak_hours_by_day = {}
    days_map = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    for day_idx in range(7):
        if day_idx in heatmap_df.index:
            peak_hour = heatmap_df.loc[day_idx].idxmax()
            peak_hours_by_day[days_map[day_idx]] = int(peak_hour)
    stats['peak_hours_by_day'] = peak_hours_by_day
    
    # 7c. Favorite and quietest day of week
    day_totals = df['weekday'].value_counts()
    if not day_totals.empty:
        stats['favorite_day'] = days_map[day_totals.idxmax()]
        stats['quietest_day'] = days_map[day_totals.idxmin()]
    
    # 8. Longest monologue
    df['monologue_group'] = (df['author_name'] != df['author_name'].shift()).cumsum()
    monologue_counts = df.groupby(['monologue_group', 'author_name']).size()
    if not monologue_counts.empty:
        max_mono = monologue_counts.idxmax()
        stats['longest_monologue'] = {
            'author': max_mono[1],
            'count': int(monologue_counts.max())
        }
        
    # 9. Avg message length
    stats['avg_char_length'] = df.groupby('author_name')['char_count'].mean().to_dict()
    stats['avg_word_length'] = df.groupby('author_name')['word_count'].mean().to_dict()
    
    # 10. Longest & shortest (Top 10 longest)
    text_msgs = df[df['char_count'] > 0]
    if not text_msgs.empty:
        longest = text_msgs.loc[text_msgs['char_count'].idxmax()]
        shortest = text_msgs.loc[text_msgs['char_count'].idxmin()]
        stats['longest_message'] = {'author': longest['author_name'], 'text': longest['text'], 'chars': int(longest['char_count'])}
        stats['shortest_message'] = {'author': shortest['author_name'], 'text': shortest['text'], 'chars': int(shortest['char_count'])}
        
        top_10_longest = text_msgs.nlargest(10, 'char_count')[['datetime', 'author_name', 'text', 'char_count']]
        top_10_longest['datetime'] = top_10_longest['datetime'].astype(str)
        stats['top_10_longest_messages'] = top_10_longest.to_dict('records')
        
    # 11. Single-word messages
    single_word_counts = text_msgs[text_msgs['word_count'] == 1].groupby('author_name').size()
    total_text_counts = text_msgs.groupby('author_name').size()
    stats['single_word_percentage'] = (single_word_counts / total_text_counts * 100).fillna(0).to_dict()
    
    # 12. Media types
    stats['media_types'] = df['media_type'].fillna('text').value_counts().to_dict()
    
    # 13 & 14. Active streaks and longest break
    df['date_only'] = df['datetime'].dt.date
    unique_dates = sorted(df['date_only'].dropna().unique())
    if len(unique_dates) > 1:
        date_diffs = np.diff(unique_dates)
        date_diff_days = [d.days for d in date_diffs]
        
        longest_break_idx = np.argmax(date_diff_days)
        longest_break = date_diff_days[longest_break_idx]
        break_start = unique_dates[longest_break_idx].isoformat()
        break_end = unique_dates[longest_break_idx + 1].isoformat()
        
        stats['longest_break'] = {'days': longest_break, 'start': break_start, 'end': break_end}
        
        # Streak calculation
        streaks = []
        current_streak = 1
        for d in date_diff_days:
            if d == 1:
                current_streak += 1
            else:
                streaks.append(current_streak)
                current_streak = 1
        streaks.append(current_streak)
        stats['longest_streak'] = int(max(streaks))
    else:
        stats['longest_break'] = {'days': 0}
        stats['longest_streak'] = 1 if len(unique_dates) == 1 else 0

    # 15. Deleted messages (estimate or exact)
    # WhatsApp/Telegram-specific
    if 'is_deleted_placeholder' in df.columns and df['is_deleted_placeholder'].any():
        stats['deleted_messages_estimate'] = int(df['is_deleted_placeholder'].sum())
        stats['deleted_is_estimate'] = False
    else:
        stats['deleted_messages_estimate'] = df.attrs.get('raw_deleted_estimate', 0)
        stats['deleted_is_estimate'] = True
    
    # 16. Edited messages
    stats['edited_messages'] = df[df['is_edited']].groupby('author_name').size().to_dict()
    
    # 17. Peak day
    day_counts = df['date_only'].value_counts()
    if not day_counts.empty:
        peak_date = day_counts.idxmax()
        stats['peak_day'] = {'date': peak_date.isoformat(), 'count': int(day_counts.max())}
        
    # 18. Dynamics per month
    df['month_year'] = df['datetime'].dt.to_period('M').astype(str)
    stats['dynamics_monthly'] = df.groupby(['month_year', 'author_name']).size().unstack(fill_value=0).to_dict('index')
    
    # 18b. Calendar Heatmap
    stats['calendar_heatmap'] = df.groupby(df['date_only'].astype(str)).size().to_dict()
    
    # 18c. Avg response time dynamics
    if not valid_responses.empty:
        valid_responses['month_year'] = valid_responses['datetime'].dt.to_period('M').astype(str)
        stats['avg_response_monthly'] = valid_responses.groupby('month_year')['time_diff'].mean().to_dict()
    else:
        stats['avg_response_monthly'] = {}
    
    # 19. Dialog initiations & closers (> 2 hours)
    initiations = responses[responses['time_diff'] > 2 * 3600]
    total_initiations = len(initiations)
    if total_initiations > 0:
        stats['initiations_percentage'] = (initiations['author_name'].value_counts() / total_initiations * 100).to_dict()
        stats['closers_percentage'] = (initiations['prev_author_name'].value_counts() / total_initiations * 100).to_dict()
    else:
        stats['initiations_percentage'] = {}
        stats['closers_percentage'] = {}
        
    # 20. Punctuation
    stats['exclamation_counts'] = text_msgs[text_msgs['text'].str.contains('!', na=False)].groupby('author_name').size().to_dict()
    stats['question_counts'] = text_msgs[text_msgs['text'].str.contains('\?', na=False)].groupby('author_name').size().to_dict()
    
    # 21. Sessions (< 15 min gap)
    df['session'] = (df['time_diff'] > 15 * 60).cumsum()
    session_sizes = df.groupby('session').size()
    stats['avg_session_messages'] = session_sizes.mean()
    
    # 22. Length histogram
    hist, bins = np.histogram(text_msgs['char_count'].dropna(), bins=[0, 20, 50, 100, 200, 500, 1000, 5000])
    stats['char_length_histogram'] = {'bins': [str(b) for b in bins], 'counts': hist.tolist()}
    
    # 23. Forwarded messages
    stats['forwarded_counts'] = df[df['is_forwarded']].groupby('author_name').size().to_dict()
    
    # 24. Reactions
    stats['reactions_given'] = df.groupby('author_name')['reactions_count'].sum().to_dict()
    
    # 25. Long vs Short messages
    long_msgs = text_msgs[text_msgs['char_count'] > 200].groupby('author_name').size()
    short_msgs = text_msgs[text_msgs['char_count'] < 20].groupby('author_name').size()
    stats['long_vs_short'] = {
        'long': long_msgs.to_dict(),
        'short': short_msgs.to_dict()
    }
    
    # 26. Season Distribution
    df['month'] = df['datetime'].dt.month
    def get_season(month):
        if month in (12, 1, 2): return 'Зима'
        elif month in (3, 4, 5): return 'Весна'
        elif month in (6, 7, 8): return 'Лето'
        else: return 'Осень'
    df['season'] = df['month'].apply(get_season)
    stats['season_distribution'] = df['season'].value_counts().to_dict()
    
    # 27. Night Owl Index (00:00 - 06:00)
    night_msgs = df[(df['hour'] >= 0) & (df['hour'] < 6)].groupby('author_name').size()
    stats['night_owl_index'] = (night_msgs / author_counts * 100).fillna(0).to_dict()
    
    return stats
