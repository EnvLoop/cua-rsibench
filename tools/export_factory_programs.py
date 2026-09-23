"""Publish bounded researcher-authored Python snapshots, with provenance and hashes."""
import argparse,hashlib,json,re
from pathlib import Path
from cursibench.factory_roster import study_roster
ROOT=Path(__file__).resolve().parents[1]

def export(study,destination):
    study=Path(study).resolve();out=Path(destination);out.mkdir(parents=True,exist_ok=True);manifest=[]
    for name in study_roster(study):
        state=json.loads((study/(name+'-campaign.json')).read_text())
        if state['final_selection'] is None:raise ValueError('finish the research search before publishing its program snapshots')
        factory_root=study/state['protocol']['factory_directory'] if state['protocol'].get('factory_directory') else ROOT/'work'
        for attempt in state['attempts']:
            number=int(attempt['attempt_id'].split('-')[-1]);factory=factory_root/f'factory-{name}-{number:02}';snapshot=factory/'workspace/final-files.json'
            if snapshot.exists():
                files=json.loads(snapshot.read_text())['files'];origin='bounded end-of-round workspace snapshot'
            else:
                saved={}
                for event in json.loads((factory/'research-history.json').read_text()):
                    action,reply=event['action'],event['reply']
                    if action.get('type')=='write' and reply.get('written'):
                        saved[action['path']]={'path':action['path'],'content':action['content'],'sha256':reply['sha256']}
                files=list(saved.values());origin='controller-recorded source writes; complete historical snapshot unavailable'
            row={'researcher':name,'round':number,'origin':origin,'files':[]}
            for entry in sorted(files,key=lambda x:x['path']):
                relative=Path(entry['path'])
                if relative.suffix!='.py':continue
                if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe snapshot path')
                content=entry['content'];actual=hashlib.sha256(content.encode()).hexdigest()
                if actual!=entry['sha256']:raise ValueError('program snapshot checksum mismatch')
                if re.search(r'[\u3400-\u9fff]|(?:tml-|e2b_|sk-)[A-Za-z0-9_-]{20,}',content):raise ValueError('non-English text or possible secret in source snapshot')
                target=out/f'{name}-round-{number:02}'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
                row['files'].append({'path':str(target.relative_to(out)),'sha256':actual})
            manifest.append(row)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (out/'README.md').write_text('# Researcher-authored programs\n\nThese are recorded Python programs authored by the study researchers. They ran inside the restricted research workspace with approved inputs. They are evidence artifacts, not trusted setup scripts for execution on a host machine. File hashes and snapshot origins are recorded in manifest.json. Earlier programs are retained even when the round did not produce a scored candidate.\n')
    print(json.dumps({'rounds':len(manifest),'python_files':sum(len(r['files']) for r in manifest)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',default='work/factory-study-02');p.add_argument('--out',default='outputs/factory-programs');a=p.parse_args();export(a.study,a.out)
