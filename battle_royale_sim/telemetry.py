import json
_events = []

def log_event(event_type, payload):
    _events.append({'type': event_type, 'payload': payload})

def flush():
    with open('telemetry.json', 'w') as f:
        json.dump(_events, f, indent=2)
