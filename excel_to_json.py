import pandas as pd
import json
import os

# Read the Excel file
df = pd.read_excel('states_districts.xlsx')   # change filename if needed

# Convert to dictionary: {state: [districts]}
states_dict = {}
for _, row in df.iterrows():
    state = str(row['State']).strip()
    district = str(row['District']).strip()
    states_dict.setdefault(state, [])
    if district not in states_dict[state]:
        states_dict[state].append(district)

# Sort districts
for state in states_dict:
    states_dict[state] = sorted(states_dict[state])

# Save as JSON in static folder
os.makedirs('static', exist_ok=True)
with open('static/states.json', 'w', encoding='utf-8') as f:
    json.dump(states_dict, f, indent=2, ensure_ascii=False)

print("✅ static/states.json created successfully!")
print(f"States: {len(states_dict)}")
