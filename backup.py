import json

with open('full_backup.json') as f:
    data = json.load(f)

filtered = []
for obj in data:
    if obj['model'].startswith('finance.'):
        obj['model'] = obj['model'].replace('finance.', 'finance.')
        filtered.append(obj)

with open('finance_data.json', 'w') as f:
    json.dump(filtered, f, indent=2)
