"""Stage complete, separately audited cohorts locally; does not publish remotely."""
import hashlib,json,shutil,zipfile
from pathlib import Path
from pypdf import PdfReader
from build_factory_report import ROOT,load_publication,assert_english,has_recovery


def package(out=None):
    out=Path(out or ROOT/'outputs');publication=load_publication(out)
    combined=out/'combined-study.json'
    if not combined.exists() or json.loads(combined.read_text())!=publication:
        raise ValueError('combined presentation does not match the completed evidence inputs')
    names=['index.html','CUA-RSIBench-Technical-Report.pdf','CUA-RSIBench-Technical-Report.md',
           'factory-study.json','model6-study.json','combined-study.json','kanboard-real-ui.png']
    for name in names:
        p=out/name
        if not p.exists():raise ValueError('missing publication asset: '+name)
        if p.suffix in ('.html','.md','.json'):assert_english(p.read_text())
    pdf=out/'CUA-RSIBench-Technical-Report.pdf';pages=PdfReader(pdf).pages
    for page in pages:
        text=page.extract_text();assert_english(text)
        if '{{' in text or 'DRAFT -' in text:raise ValueError('unfinished PDF text')
    stems=['factory-pipeline'];program_files=[];program_index=[]
    for cohort in publication['cohorts']:
        cid=cohort['id'];stems.extend('factory-'+cid+'-'+kind for kind in ('trajectories','budget','final-matrix'))
        if has_recovery(cohort['data']):stems.append('factory-'+cid+'-final-recovered-matrix')
        directory=out/'factory-programs'/cid;manifest=directory/'manifest.json'
        if not manifest.exists():raise ValueError('missing separate program export: '+cid)
        records=json.loads(manifest.read_text());program_index.append({'cohort':cid,'manifest':cid+'/manifest.json','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()})
        for row in records:
            for item in row['files']:
                path=directory/item['path']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('program export hash changed')
                assert_english(path.read_text());program_files.append(path)
        program_files.extend([manifest,directory/'README.md'])
    index=out/'factory-programs/cohorts.json';index.write_text(json.dumps(program_index,indent=2)+'\n');program_files.append(index)
    figures=[]
    for stem in stems:
        for ext in ('png','svg','pdf'):
            path=out/'figures'/(stem+'.'+ext)
            if not path.exists():raise ValueError('missing completed-study figure: '+path.name)
            figures.append(path)
    files=[out/name for name in names]+figures+program_files
    # Explicit inventory prevents stale partial-study figures or program exports
    # from entering the public site or ZIP through a broad directory copy.
    site=ROOT/'docs/site';site.mkdir(exist_ok=True)
    for source in files:
        destination=site/source.relative_to(out);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    with zipfile.ZipFile(out/'CUA-RSIBench-Offline-Explorer.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):archive.write(path,path.relative_to(out))
    with zipfile.ZipFile(out/'CUA-RSIBench-Figures.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in figures:archive.write(path,path.relative_to(out))
    checksum_names=[name for name in names if name not in ('index.html','kanboard-real-ui.png')]+['CUA-RSIBench-Offline-Explorer.zip','CUA-RSIBench-Figures.zip']
    checks=[hashlib.sha256((out/name).read_bytes()).hexdigest()+'  '+name for name in checksum_names]
    (out/'checksums.sha256').write_text('\n'.join(checks)+'\n');(site/'checksums.sha256').write_text('\n'.join(checks[:-2])+'\n')
    print(json.dumps({'staged':True,'cohorts':len(publication['cohorts']),'pdf_pages':len(pages),'bundle_files':len(files),'report_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}))

if __name__=='__main__':package()
