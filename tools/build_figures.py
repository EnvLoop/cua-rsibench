"""Standalone publication figures from original, audited pilot results."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/figures';OUT.mkdir(exist_ok=True)
e=json.loads((ROOT/'outputs/evidence.json').read_text());runs=e['data_campaigns']
plt.rcParams.update({'font.size':9,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
BLUE='#3154a5';TEAL='#087f73';ORANGE='#b2632a';GRAY='#637080'
def save(fig,name):
 for kind in ('png','pdf','svg'):
  path=OUT/f'{name}.{kind}';fig.savefig(path,dpi=220,bbox_inches='tight',facecolor='white')
  if kind=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
 plt.close(fig)
fig,ax=plt.subplots(figsize=(6.7,2.4));ax.set_xlim(-.1,10.1);ax.set_ylim(-.35,3.1);ax.axis('off')
labels=[('Researcher','Data recipe\n+ hypothesis'),('Training data','Verified train-only\nJSONL'),('Tinker SFT','Fresh fixed-base\nLoRA update'),('Checkpoint','Persistent sampler\nweights'),('E2B proxy','Authenticated\ninference'),('Harbor task','Native browser\nexecution'),('Verifier','Saved-state\ncomparison'),('Selection','Strict gain; keep\nhistorical best')]
coords=[(.1,2.1),(2.65,2.1),(5.2,2.1),(7.75,2.1),(7.75,.55),(5.2,.55),(2.65,.55),(.1,.55)]
for (title,subtitle),(x,y) in zip(labels,coords):
 ax.add_patch(FancyBboxPatch((x,y),2.2,.7,boxstyle='round,pad=0.02',linewidth=.8,edgecolor=BLUE,facecolor='#f0f4fb'))
 ax.text(x+1.1,y+.47,title,ha='center',va='center',weight='bold',fontsize=9)
 ax.text(x+1.1,y+.19,subtitle,ha='center',va='center',fontsize=7.1,linespacing=1.05,color=GRAY)
for i in range(7):
 x,y=coords[i];xx,yy=coords[i+1]
 start=(x+2.23,y+.35) if i<3 else ((x+1.1,y-.03) if i==3 else (x-.03,y+.35))
 end=(xx-.03,yy+.35) if i<3 else ((xx+1.1,yy+.73) if i==3 else (xx+2.23,yy+.35))
 ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=11,color=BLUE,lw=1.2))
ax.add_patch(FancyArrowPatch((1.2,1.3),(1.2,2.05),arrowstyle='-|>',mutation_scale=11,color=TEAL,lw=1.3,linestyle='--'))
ax.text(1.38,1.65,'Selection feedback',color=TEAL,fontsize=8,va='center')
ax.text(5,.03,'Final-test evidence is withheld from the researcher. Runtime and scoring stay fixed within each version.',ha='center',fontsize=8,color=GRAY)
save(fig,'pipeline')
fig,axs=plt.subplots(2,2,figsize=(6.7,4.3),layout='constrained',sharex='col')
for col,r in enumerate(runs):
 a=r['attempts'];x=[v['attempt'] for v in a];reward=[v['evaluation'].get('reward') for v in a];valid=[v['evaluation'].get('valid_action_rate') for v in a]
 ax=axs[0,col];ax.set_title(r['researcher']);ax.plot(x,[100*v if v is not None else float('nan') for v in reward],'-o',color=BLUE,ms=5)
 missing=[xx for xx,y in zip(x,reward) if y is None];ax.scatter(missing,[-15]*len(missing),marker='x',color=ORANGE,s=45,zorder=5)
 ax.axhline(-7,color='#bec7d1',lw=.6);ax.set_ylim(-24,110);ax.set_yticks([-15,0,50,100],['N/A','0','50','100']);ax.set_ylabel('Strict reward (%)');ax.grid(axis='y',alpha=.15)
 ax=axs[1,col]
 for xx,v,rv in zip(x,valid,reward):
  if v is not None:ax.scatter(xx,v*100,facecolor='white' if rv is None else TEAL,edgecolor=ORANGE if rv is None else TEAL,s=34)
 ax.set_ylim(-5,110);ax.set_yticks([0,50,100]);ax.set_ylabel('Valid actions (%)');ax.set_xlabel('Original attempt');ax.set_xticks(x);ax.grid(axis='y',alpha=.15)
fig.suptitle('Valid interaction syntax does not imply successful task completion',fontsize=11)
save(fig,'candidate-trajectories')
fig,axs=plt.subplots(1,2,figsize=(6.7,2.7),layout='constrained',sharey=True)
for ax,r in zip(axs,runs):
 x=[a['cumulative_training_tokens']/1000 for a in r['attempts']];y=[a['evaluation'].get('reward') for a in r['attempts']]
 ax.plot([0]+x,[0]+[100*v if v is not None else float('nan') for v in y],'-o',color=BLUE,ms=4)
 for xx,v in zip(x,y):
  if v is None:ax.scatter([xx],[-15],marker='x',color=ORANGE,s=45)
 ax.set_title(r['researcher']);ax.set_ylim(-24,110);ax.set_yticks([-15,0,50,100],['N/A','0','50','100']);ax.set_xlabel('Cumulative training tokens\n(thousands)');ax.axhline(-7,color='#bec7d1',lw=.6);ax.grid(axis='y',alpha=.15)
axs[0].set_ylabel('Strict reward (%)');save(fig,'budget-frontier')
print('Exported 3 figures in PNG, PDF and SVG')
