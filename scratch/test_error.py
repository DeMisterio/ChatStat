def run():
    msg = "test"
    try:
        a = msg['test']
    except Exception as e:
        print(f"Exception 1: {type(e).__name__}: {str(e)}")

    try:
        a = msg.get('test')
    except Exception as e:
        print(f"Exception 2: {type(e).__name__}: {str(e)}")

    import json
    res = '"this is string"'
    try:
        parsed = json.loads(res)
        a = parsed['title']
    except Exception as e:
        print(f"Exception 3: {type(e).__name__}: {str(e)}")

run()
