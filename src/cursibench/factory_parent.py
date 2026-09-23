"""Carry a data factory and verified training experience into a feedback round."""
import hashlib
import json
import shutil
from pathlib import Path
from .factory_recovery import restore_corpus


def inherit(parent,destination,registry):
    parent=Path(parent);destination=Path(destination)
    spec=json.loads((parent/'spec.json').read_text())
    if spec['source_hash']!=registry.source_hash:raise ValueError('parent uses a different source snapshot')
    # Verify the parent before copying its private episode evidence.
    restore_corpus(parent,registry)
    for episode in (parent/'controller').glob('episode-*'):
        shutil.copytree(episode,destination/'controller'/episode.name)
    corpus,recipes,incomplete=restore_corpus(destination,registry)
    if incomplete:raise ValueError('parent contains an unresolved native rollout')
    snapshot=parent/'workspace/final-files.json'
    if snapshot.exists():
        files=json.loads(snapshot.read_text())['files'];origin='complete bounded workspace snapshot'
    else:
        files={}
        for event in json.loads((parent/'research-history.json').read_text()):
            action=event['action'];reply=event['reply']
            if action.get('type')=='write' and reply.get('written'):
                content=action['content'];actual=hashlib.sha256(content.encode()).hexdigest()
                if actual!=reply['sha256']:raise ValueError('parent source-write integrity mismatch')
                files[action['path']]={'path':action['path'],'content':content,'sha256':actual}
        files=list(files.values());origin='controller-recorded source writes; full old filesystem snapshot unavailable'
    for entry in files:
        if hashlib.sha256(entry['content'].encode()).hexdigest()!=entry['sha256']:raise ValueError('parent snapshot integrity mismatch')
    # Regenerate data artifacts from the inherited programs; retain script/config files.
    source_files=[x for x in files if x['path'].endswith(('.py','.md','.txt','.json')) and not x['path'].endswith('examples.json')]
    return corpus,recipes,source_files,{'parent':str(parent),'source_origin':origin,'verified_episodes':len(corpus.episodes)}
