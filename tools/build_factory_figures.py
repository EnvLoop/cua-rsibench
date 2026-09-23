"""Export research figures from the audited factory study, without simulated scores."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
from matplotlib.colors import ListedColormap
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/figures';OUT.mkdir(parents=True,exist_ok=True)
d=json.loads((ROOT/'outputs/factory-study.json').read_text())
plt.rcParams.update({'font.size':9,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
BLUE='#3154a5';TEAL='#087f73';ORANGE='#b2632a';GRAY='#637080'

def save(fig,name):
    for extension in ('png','svg','pdf'):
        p=OUT/f'{name}.{extension}';fig.savefig(p,dpi=220,bbox_inches='tight',facecolor='white')
        if extension=='svg':p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n')
    plt.close(fig)

fig,ax=plt.subplots(figsize=(7,3.0));ax.set_xlim(-.2,10.2);ax.set_ylim(-.3,3.5);ax.axis('off')
labels=[('Researcher code','Python generator\n+ data policy'),('Native task states','Approved source facts\n+ task recipes'),('GUI experience','Fixed teacher\n+ saved-state check'),('Training data','Filter / representation\n/ order / mixture'),('Tinker SFT','Fixed-base LoRA\n32 optimizer updates'),('E2B + Harbor','Checkpoint proxy\n+ native browser trials'),('Selection','Strict gain\n+ no task regression'),('Sealed final tests','Freeze checkpoint\nFresh environments')]
coords=[(0,2.3),(2.6,2.3),(5.2,2.3),(7.8,2.3),(7.8,.65),(5.2,.65),(2.6,.65),(0,.65)]
for (title,body),(x,y) in zip(labels,coords):
    ax.add_patch(FancyBboxPatch((x,y),2.2,.85,boxstyle='round,pad=.04',lw=.8,edgecolor=BLUE,facecolor='#f0f4fb'))
    ax.text(x+1.1,y+.62,title,ha='center',fontsize=8,weight='bold');ax.text(x+1.1,y+.28,body,ha='center',va='center',fontsize=7.2,color=GRAY)
for i in range(7):
    x,y=coords[i];xx,yy=coords[i+1]
    start=(x+2.25,y+.43) if i<3 else ((x+1.1,y-.05) if i==3 else (x-.05,y+.43))
    end=(xx-.05,yy+.43) if i<3 else ((xx+1.1,yy+.90) if i==3 else (xx+2.25,yy+.43))
    ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=10,lw=1.1,color=BLUE))
ax.add_patch(FancyArrowPatch((3.7,1.55),(1.1,2.22),connectionstyle='arc3,rad=-.1',arrowstyle='-|>',mutation_scale=11,color=TEAL,linestyle='--'))
ax.text(3.2,1.87,'Permitted feedback',fontsize=8,color=TEAL)
ax.text(5,.1,'Generated programs cannot access credentials, evaluator answers, or final-test feedback.',ha='center',fontsize=8,color=GRAY)
save(fig,'factory-pipeline')
fig,axs=plt.subplots(1,2,figsize=(7,2.9),layout='constrained',sharey=True)
for ax,c in zip(axs,d['campaigns']):
    rounds=[a['round'] for a in c['attempts']]
    scores=[a['evaluation']['score'] for a in c['attempts']]
    ax.plot([0]+rounds,[c['baseline']['score']*100]+[v*100 if v is not None else float('nan') for v in scores],'-o',color=BLUE,ms=5,label='Candidate')
    ax.step([0]+rounds,[c['baseline']['score']*100]+[a['best_after']*100 for a in c['attempts']],where='post',linestyle='--',color=TEAL,label='Incumbent')
    missing=[i for i,v in zip(rounds,scores) if v is None];ax.scatter(missing,[-18]*len(missing),marker='x',color=ORANGE,s=45)
    ax.axhline(-7,lw=.6,color='#bec7d1');ax.set_ylim(-28,108);ax.set_yticks([-18,0,33.333,66.667,100],['Unscored','0','33.3','66.7','100'])
    ax.set_xticks([0]+rounds);ax.set_xlabel('Research round (0 = base)');ax.set_title(c['researcher']);ax.grid(axis='y',alpha=.15)
axs[0].set_ylabel('Selection success (%)');axs[1].legend(fontsize=7,loc='upper left');save(fig,'factory-trajectories')
fig,axs=plt.subplots(1,2,figsize=(7,2.6),layout='constrained',sharey=True)
for ax,c in zip(axs,d['campaigns']):
    x=[0]+[a['cumulative_training_tokens']/1000 for a in c['attempts']];y=[0]+[a['best_after']*100 for a in c['attempts']]
    ax.step(x,y,where='post',color=TEAL);ax.scatter(x,y,s=22,color=TEAL);ax.set_title(c['researcher']);ax.set_ylim(-4,105);ax.set_xlabel('Scheduled training tokens (thousands)');ax.grid(axis='y',alpha=.15)
axs[0].set_ylabel('Retained selection success (%)');save(fig,'factory-budget')
if d.get('all_final_executions_finished'):
    lookup={r['label']:r for r in d['final_executions']};bindings=d['final_comparison']['bindings'];first=next(iter(lookup.values()));tasks=sorted(first['evaluation']['expected_tasks'])
    matrix=[]
    for task in tasks:
        row=[]
        for role in ('base','astra','sol'):
            for label in bindings[role]:
                summary=lookup[label]['evaluation'];values={x['task']:x['score'] for x in summary['tasks']};v=values.get(task);row.append(-1 if v is None else int(v))
        matrix.append(row)
    fig,ax=plt.subplots(figsize=(7,3.5),layout='constrained');ax.imshow(matrix,cmap=ListedColormap(['#e5e0d8','#e8edf5','#087f73']),vmin=-1,vmax=1,aspect='auto')
    ax.set_xticks(range(6),['Base\nR1','Base\nR2','Astra selection\nR1','Astra selection\nR2','Sol selection\nR1','Sol selection\nR2']);ax.set_yticks(range(len(tasks)),[t.replace('final-','') for t in tasks]);ax.tick_params(length=0)
    for i,row in enumerate(matrix):
        for j,v in enumerate(row):ax.text(j,i,'N/A' if v==-1 else ('Pass' if v==1 else 'Fail'),ha='center',va='center',color='white' if v==1 else '#384353',fontsize=8)
    for edge in (1.5,3.5):ax.axvline(edge,color='white',lw=3)
    ax.set_title('Six final instances / two same-seed fresh-environment repetitions',fontsize=10,pad=14);save(fig,'factory-final-matrix')
print('Factory figures exported from audit data')
