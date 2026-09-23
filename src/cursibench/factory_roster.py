"""Read exact researcher identities from a frozen study, preserving legacy names."""
import json
from pathlib import Path
from .agentrouter import RESEARCHER_MODELS

LEGACY_RESEARCHERS={'astra':'gpt-6-astra','sol':'gpt-5.6-sol'}

def study_roster(study):
    manifest=json.loads((Path(study)/'manifest.json').read_text())
    roster=manifest.get('researchers',LEGACY_RESEARCHERS)
    if not isinstance(roster,dict) or not roster:raise ValueError('study requires a researcher mapping')
    if any(RESEARCHER_MODELS.get(name)!=model for name,model in roster.items()):raise ValueError('study researcher alias/model mismatch')
    return dict(roster)
