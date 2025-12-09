#!/usr/bin/env python3
"""Debug script to check extraction state in database"""

import sys
import json
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path('.').absolute()))

# Check database state
DB_FILE = 'data/chat_history.db'
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

print('=== Checking extraction_states table ===')
c.execute('SELECT conversation_id, updated_at FROM extraction_states ORDER BY updated_at DESC LIMIT 3')
states = c.fetchall()
for conv_id, updated in states:
    print(f'Conversation: {conv_id}, Updated: {updated}')

# Check most recent conversation
if states:
    recent_conv = states[0][0]
    print(f'\n=== Examining most recent conversation: {recent_conv} ===')
    
    c.execute('SELECT state_json FROM extraction_states WHERE conversation_id = ?', (recent_conv,))
    state_row = c.fetchone()
    
    if state_row:
        state = json.loads(state_row[0])
        print(f'State keys: {list(state.keys())}')
        if 'parsed_json' in state:
            parsed_data = state['parsed_json']
            print(f'Parsed JSON fields: {list(parsed_data.keys())}')
            # Show first field details
            if parsed_data:
                first_field = list(parsed_data.keys())[0]
                first_value = parsed_data[first_field]
                print(f'\nFirst field "{first_field}": type={type(first_value)}')
                if isinstance(first_value, dict):
                    print(f'  Dict keys: {list(first_value.keys())}')
                    if 'content' in first_value:
                        content = first_value['content']
                        print(f'  Content preview: {content[:100]}...')
                else:
                    print(f'  Value preview: {str(first_value)[:100]}...')
    
    # Check messages
    c.execute('SELECT role, message_type, timestamp FROM chat_messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 5', (recent_conv,))
    messages = c.fetchall()
    print(f'\n=== Recent messages for {recent_conv} ===')
    for role, msg_type, timestamp in messages:
        print(f'{role} ({msg_type}) at {timestamp}')

conn.close()
print('\nDone!')