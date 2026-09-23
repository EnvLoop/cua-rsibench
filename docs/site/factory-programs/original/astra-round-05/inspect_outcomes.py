import json
from pathlib import Path
for name in ['episode-00','episode-01']:
    episode=json.loads((Path('/inputs')/(name+'.json')).read_text())
    print(name, 'verification', json.dumps(episode['verification']))
    for item in episode['trace']:
        print('step',item['step'],'outcome',json.dumps(item['outcome'])[:700])
    print('first response type',type(episode['trace'][0]['response']).__name__)
