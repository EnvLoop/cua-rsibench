"""Render the completed executable-factory study from audited evidence only."""
import json,re
from pathlib import Path
from build_report import render,markdown_table
ROOT=Path(__file__).resolve().parents[1]

def score(value):return 'Unscored' if value is None else f'{value*100:.1f}%'

def manuscript(d):
    if not d['audit_pass'] or not d['search_finished'] or not d['all_final_executions_finished']:
        raise ValueError('finish and audit the prescribed search and final executions before publishing')
    campaigns=d['campaigns'];trained=[a for c in campaigns for a in c['attempts'] if a.get('optimizer_steps')]
    values={'ROUND_COUNT':str(sum(len(c['attempts']) for c in campaigns)),'TRAINED_COUNT':str(len(trained)),'TOTAL_TOKENS':f'{sum(c["used_training_tokens"] for c in campaigns):,}'}
    values['SELECTION_SENTENCE']=' '.join(f'{c["researcher"]} retains {c["selected"]} at {score(c["selection_score"])} selection success.' for c in campaigns)
    table=[['Researcher','Trained / rounds','First / best / last scored','Selected','Train tokens']]
    for c in campaigns:
        valid=[a['evaluation']['score'] for a in c['attempts'] if a['evaluation']['status']=='scored']
        table.append([c['researcher'].replace('gpt-',''),f'{sum(bool(a.get("optimizer_steps")) for a in c["attempts"])} / {len(c["attempts"])}',
            ' / '.join(score(x) for x in (valid[0],max(valid),valid[-1])) if valid else 'Unscored',c['selected'],f'{c["used_training_tokens"]:,}'])
    values['CAMPAIGN_TABLE']=markdown_table(table)
    values['TRAJECTORY_ANALYSIS']=' '.join(f'{c["researcher"]} ends with an incumbent score of {score(c["selection_score"])} after {len(c["attempts"])} research rounds. Its valid candidate scores, in execution order, are '+', '.join(score(a['evaluation']['score']) for a in c['attempts'] if a['evaluation']['status']=='scored')+'.' for c in campaigns)
    by_label={r['label']:r for r in d['final_executions']};table=[['Comparison role','Repetition 1 / 2','Complete mean']];means={}
    for role,labels in d['final_comparison']['bindings'].items():
        vals=[by_label[x]['evaluation']['score'] for x in labels];means[role]=sum(vals)/len(vals) if all(x is not None for x in vals) else None
        table.append([role,' / '.join(score(x) for x in vals),score(means[role])])
    values['FINAL_TABLE']=markdown_table(table)
    values['FINAL_SENTENCE']='The base final mean is '+score(means['base'])+'; the Astra- and Sol-selected means are '+score(means['astra'])+' and '+score(means['sol'])+', respectively.'
    values['FINAL_ANALYSIS']=values['FINAL_SENTENCE']+' '+('All prescribed final executions have valid scores.' if all(x is not None for x in means.values()) else 'At least one final execution is infrastructure-invalid; its complete mean remains undefined.')
    shared=[r for r in ('astra','sol') if d['final_comparison']['bindings'][r]==d['final_comparison']['bindings']['base']]
    if shared:values['FINAL_ANALYSIS']+=' The '+', '.join(shared)+' selection is the base checkpoint and shares the base executions.'
    text=(ROOT/'tools/factory_report_template.md').read_text()
    for k,v in values.items():text=text.replace('{{'+k+'}}',v)
    if '{{' in text or re.search(r'[\u3400-\u9fff]',text):raise ValueError('invalid English manuscript')
    return text

if __name__=='__main__':
    out=ROOT/'outputs';data=json.loads((out/'factory-study.json').read_text());text=manuscript(data)
    (out/'CUA-RSIBench-Technical-Report.md').write_text(text)
    render(text,out/'CUA-RSIBench-Technical-Report.pdf',out)
