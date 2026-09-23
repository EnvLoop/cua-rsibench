"""Rehydrate only independently verified controller evidence after interruption."""
import json
from pathlib import Path
from .factory_corpus import VerifiedCorpus
from .factory_cases import digest,semantic_case_key


def restore_corpus(root,registry):
    corpus=VerifiedCorpus();recipes={};incomplete=[]
    for episode in sorted((Path(root)/'controller').glob('episode-*')):
        case=json.loads((episode/'case.json').read_text())
        registry.resolve(case['source_numbers'])
        if case['provenance']['snapshot_sha256']!=registry.source_hash:raise ValueError('source snapshot changed')
        # The original controller compiled this recipe; the immutable recipe hash is retained.
        key=semantic_case_key(case);recipes[key]=episode.name
        result_path=episode/'result.json'
        if not result_path.exists():incomplete.append(episode);continue
        result=json.loads(result_path.read_text())
        if result.get('infrastructure_error') is None and result['verification'].get('success'):
            corpus.add(case,result,episode.name)
    return corpus,recipes,incomplete
