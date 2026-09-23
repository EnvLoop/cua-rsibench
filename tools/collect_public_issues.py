"""Collect public issue metadata only; no authors, emails, bodies or credentials."""
import datetime,hashlib,json,subprocess
from pathlib import Path
repo='kanboard/kanboard'
raw=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/issues?state=all&per_page=100&sort=created&direction=desc']))
rows=[]
for issue in raw:
    if 'pull_request' in issue:continue
    # At most 24 words from any issue title; no copied issue body/comment text.
    title=' '.join(issue['title'].split()[:24])
    rows.append({'number':issue['number'],'title':title,'state':issue['state'],
                 'created_at':issue['created_at'],'updated_at':issue['updated_at'],
                 'closed_at':issue['closed_at'],'labels':[x['name'] for x in issue['labels']],
                 'comment_count':issue['comments'],'source_url':issue['html_url']})
data={'source_repo':repo,'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'source_type':'public GitHub issue metadata','transformations':['PRs excluded','titles capped at 24 words','authors and bodies excluded'],
      'records':rows}
data['records_sha256']=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
Path('datasets/public/kanboard_issues.json').write_text(json.dumps(data,indent=2,ensure_ascii=False))
print('collected',len(rows),'real issues; source URLs retained')
