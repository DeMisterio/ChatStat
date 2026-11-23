emotions = [{'label': 'joy', 'score': 0.9}]
for emo_list in emotions:
    emo_dict = {d['label']: d['score'] for d in emo_list}
