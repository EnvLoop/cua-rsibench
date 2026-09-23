"""Build the Chinese/English technical report from curated run evidence."""
import argparse,json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Image,Flowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor,white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
pdfmetrics.registerFont(TTFont('CJK','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFont(TTFont('Serif','/System/Library/Fonts/Supplemental/Georgia.ttf'))
INK=HexColor('#18333b');TEAL=HexColor('#007366');MUTED=HexColor('#5b7076');BG=HexColor('#edf3f1');AMBER=HexColor('#a34c20')
styles={
 'title':ParagraphStyle('title',fontName='Serif',fontSize=30,leading=36,textColor=INK,spaceAfter=15),
 'h1':ParagraphStyle('h1',fontName='CJK',fontSize=21,leading=29,textColor=INK,spaceAfter=17),
 'h2':ParagraphStyle('h2',fontName='CJK',fontSize=13,leading=20,textColor=TEAL,spaceBefore=12,spaceAfter=8),
 'body':ParagraphStyle('body',fontName='CJK',fontSize=10.3,leading=17,textColor=INK,spaceAfter=10),
 'small':ParagraphStyle('small',fontName='CJK',fontSize=8.2,leading=12,textColor=MUTED,spaceAfter=8),
 'cell':ParagraphStyle('cell',fontName='CJK',fontSize=9,leading=14,textColor=INK),
 'kicker':ParagraphStyle('kicker',fontName='CJK',fontSize=9,leading=14,textColor=TEAL,spaceAfter=12),
}

for style in styles.values():style.wordWrap='CJK'

def P(text,style='body'):return Paragraph(text,styles[style])
def table(rows,widths):
 t=Table([[P(escape(str(v)),'cell') for v in row] for row in rows],colWidths=widths,hAlign='LEFT',repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BG),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#cbd8d5'))]));return t

class Pipeline(Flowable):
 def __init__(self):Flowable.__init__(self);self.width=507;self.height=205
 def draw(self):
  c=self.canv
  rows=[['数据研究 Agent','SFT JSONL','Tinker LoRA','Sampler checkpoint'],['最终选择 / 提交','独立验收','Harbor 任务','E2B 采样代理']]
  for j,labels in enumerate(rows):
   y=143-j*94
   for i,label in enumerate(labels):
    x=i*129;c.setFillColor(BG);c.setStrokeColor(TEAL);c.roundRect(x,y,117,51,5,fill=1,stroke=1)
    c.setFillColor(INK);c.setFont('CJK',10);c.drawCentredString(x+58.5,y+21,label)
    if i<3:
     c.setStrokeColor(TEAL);c.line(x+118,y+26,x+126,y+26)
     target=x+126 if j==0 else x+118;delta=-3 if j==0 else 3
     c.line(target+delta,y+29,target,y+26);c.line(target+delta,y+23,target,y+26)
  c.setStrokeColor(TEAL);c.line(445,142,445,101);c.line(442,105,445,101);c.line(448,105,445,101)
  c.setFillColor(MUTED);c.setFont('CJK',8.5);c.drawString(0,119,'固定服务与评测边界；研究者只改变允许的数据策略。')
  c.drawString(0,24,'保留每次尝试、历史最佳与失败证据；最终测试不参与选择。')

class Bars(Flowable):
 def __init__(self,items):Flowable.__init__(self);self.items=items;self.width=507;self.height=45*len(items)+35
 def draw(self):
  c=self.canv
  for i,(label,value) in enumerate(self.items):
   y=self.height-40-i*45;c.setFillColor(INK);c.setFont('CJK',10);c.drawString(0,y+8,label)
   c.setFillColor(BG);c.rect(192,y,245,23,fill=1,stroke=0)
   if value is not None:c.setFillColor(TEAL);c.rect(192,y,245*value,23,fill=1,stroke=0)
   c.setFillColor(INK);c.drawString(450,y+7,'N/A' if value is None else str(round(value*100))+'%')


def build(path):
 e=json.loads((ROOT/'outputs/evidence.json').read_text());data=json.loads((ROOT/'datasets/public/kanboard_issues.json').read_text())
 story=[]
 def add(text,style='body'):story.append(P(text,style))
 def new(k,title):story.append(PageBreak());add(k,'kicker');add(title,'h1')
 add('TECHNICAL REPORT / 2026-09-23 / PILOT EVIDENCE','kicker')
 add('CUA-RSIBench','title');add('面向真实软件操作的可验证改进基准','h1')
 add('真实应用 · 真实来源数据 · 独立验收 · 可审计训练评测链','small')
 add('摘要','h2')
 add('本项目借鉴 RSIBench-Data 的固定服务边界，把研究对象扩展到 computer use。当前实现以原生 Kanboard 为环境，用公开 issue 元数据构造可重置任务，并通过应用数据库回读验证结果。模型可见页面文字和控件，不能直接调用数据库、文件或应用 API。')
 add('我们分别记录环境执行、训练服务与任务能力证据。Tinker、E2B、Harbor 的真实服务链已完成一次端到端评测；微量训练后的目标模型在用于链路贯通的合成浏览器任务中得分为 0。这是有效的负结果，不应写成训练成功率或自我改进成果。正式提升结论仍需通过难度校准、对照实验和独立测试。')
 story.append(Pipeline())
 add('图 1　数据研究轨道的目标协议。训练与采样分离，Harbor 调度实际任务，独立验收提供选择依据。机制图不等同于完整多轮改进实验已完成。','small')
 add('本报告状态','h2')
 add('这是方法与试验性证据报告，不是成熟排行榜，也不声称已证明持续 RSI。公开代码和证据用于复核及后续扩展。此前全满分的简化任务已降为冒烟测试。')
 add('<link href="https://github.com/nanobanana123/cua-rsibench" color="#007366">代码与复现材料：github.com/nanobanana123/cua-rsibench</link>','small')

 new('01 / REAL SOFTWARE','真实环境与操作边界')
 add('正式方向采用未改写业务界面的 Kanboard 1.2.54。PHP 控制器、原生登录、项目、任务、评论、表单提交与 SQLite 持久化均来自真实应用。每次试验创建独立 E2B 环境并注入初始状态，试验结束销毁。')
 img=ROOT/'work/kanboard-public-view.png'
 if img.exists():story.append(Image(str(img),width=507,height=370))
 add('图 2　实际 E2B 中的 Kanboard 原生任务列表。公开 issue 的标题和引用编号进入真实应用，模型需要进一步打开各条记录核对来源字段。','small')
 story.append(table([['角色','权限与责任'],['被测模型','仅当前可见 DOM 文字与控件；点击、输入、选择、有限按键、返回。'],['评测主控','创建环境、注入数据、记录截图、抓取独立数据库快照。'],['Verifier','验证目标字段及无关对象完整性，不接受模型自报完成。']],[95,412]))
 add('范围限制：当前是 DOM 辅助的浏览器操作，尚不代表纯截图定位、完整 Windows/macOS 桌面或跨应用企业部署。','small')

 new('02 / DATA PROVENANCE','真实数据与构造规则分开')
 add(f'本次快照包含 {len(data["records"])} 条真实公开 issue 元数据，来自 kanboard/kanboard。采集时间为 {escape(data["collected_at"])}。排除 pull request、作者信息与正文，仅保留复核所需字段；每条记录都有来源 URL。')
 story.append(table([['数据类型','来源与处理'],['真实字段','issue 编号、标题、状态、创建/更新时间、关闭时间、标签、评论数、来源链接。'],['变换','标题最多保留 24 个词；不复制 issue 正文、评论正文、邮箱和作者画像。'],['构造字段','本地项目名、负责人、SLA 或排期规则、历史副本干扰项。明确标注为 benchmark constructs。'],['复现标识','采集时间、元数据 SHA-256、应用版本、初始状态与 verifier 版本。']],[105,402]))
 add('样例来源','h2')
 for r in data['records'][:3]:
  add(f'<link href="{r["source_url"]}" color="#007366">GitHub issue #{r["number"]}</link> · {escape(r["state"])} · updated {escape(r["updated_at"])}','small')
 add('数据真实并不自动意味着任务真实。任务指令需要合理的业务目的，操作链需要使用应用原有行为，答案则应来自可独立计算的规则。报告不把合成的分派政策冒充上游维护者的实际决策。')
 add('污染与拆分','h2');add('公开元数据可能已被模型见过，因此只能支持流程执行与规则遵循评估。正式数据研究需把训练、验收和最终测试按源 issue 与任务模板隔离，禁止把测试轨迹转成训练记录。当前校准集不被称作封闭测试集。')

 new('03 / TASK DIFFICULTY','用区分度选择任务')
 story.append(table([['层级','业务任务','主要难点'],['L1','明确单对象修改','定位真实控件，提交并回读。'],['L2','公开 backlog 排序与分派','跨任务读取真实状态和时间戳；排序选择；保留其他项目。'],['L2+','批准版本驱动的事件升级','区分原始导入、旧批准版本和新草稿；联合条件判断。'],['L3','预算与依赖约束下的排期','多个容量约束、依赖与互斥关系；全局可行性及并列规则。']],[44,173,290]))
 add('校准原则','h2');add('先用 Astra 与 Sol 的固定配置试跑，保留成功、失败、部分完成、步骤及服务异常。若所有模型几乎全对，该组任务只适合冒烟或回归；若失败主要来自接口或环境故障，则修复基础设施后再评估难度。')
 add('不能通过故意损坏环境、缩短到不合理的步数预算，或者隐藏必要信息来制造低分。每个任务必须有可执行的独立解法。较难的任务应来自真实约束组合、信息分散、状态恢复和长流程，而非单纯增加点击数量。')
 add('正式指标','h2');add('主指标为严格任务成功率，辅以逐字段完成率、未授权副作用、步骤、token、时延与基础设施失败率。不同难度和应用类型分别报告。单次执行的差异不足以宣布模型排名。')
 story.append(Bars([('简化任务定位','')]) if False else Spacer(1,10))
 add('当前状态：饱和的手写页面实验已停止并保存原始记录；原生 Kanboard 与真实元数据任务用于新一轮难度校准。')

 new('04 / VERIFICATION','独立验证与失败分类')
 add('验证依赖最终保存状态，而不是页面看起来正确或模型说已完成。Kanboard 试验比较开始和结束时的任务、评论、项目、用户角色等快照。目标字段根据固定指令重算，其余对象必须保持语义完整。')
 story.append(table([['检查','可拒绝的错误'],['目标对象','相似项目/重复引用导致改错任务，漏改负责人、优先级或复杂度。'],['无关状态','误改归档项目、删除任务、更改源描述或评论。'],['持久化','仅填写未保存、遗漏确认、页面表象与实际保存状态不一致。'],['等价归一化','仅归一化应用维护时间戳、空工时与 0、原生文本框的 LF/CRLF 换行；不忽略内容变动。'],['基础设施','API 超时、沙箱创建失败或网络中断独立记录，不视作能力得分 0。']],[108,399]))
 add('隔离模型','h2');add('被测策略是远程 API 模型，只拥有受限 GUI 动作通道，不能读取主控文件。Harbor 的 separate verifier 在另一环境运行，答案不放入 agent 环境构建目录。本地回归 fixture 中的公开答案不被称为隐藏集。')
 add('完整性证据','h2');add('请求、响应摘要、环境版本、任务哈希、候选父子关系和接受/拒绝理由共同构成证据。哈希链能揭示日志被修改，但同机哈希链不等同于对恶意主控的安全隔离。')

 new('05 / CLOUD CHAIN','真实训练与云端评测结果')
 t=e.get('tinker',{});chain=e.get('cloud_chain',{})
 story.append(table([['阶段','已核验结果'],['Tinker 训练',f'{t.get("model","N/A")}；rank 8；{t.get("steps_requested","N/A")} 步更新；{t.get("record_count","N/A")} 条训练记录；本轮计划 {t.get("scheduled_tokens","N/A")} token。'],['Checkpoint','保存 sampler weights，并从该 checkpoint 实际采样。公开摘要仅记录 checkpoint 哈希。'],['E2B 代理','带临时 Bearer 鉴权的采样服务；任务完成后销毁代理沙箱。'],['Harbor 合成任务',f'完成 {chain.get("completed","N/A")} 个任务；{chain.get("errors","N/A")} 个基础设施错误；独立 verifier reward={chain.get("reward","N/A")}。']],[105,402]))
 story.append(Spacer(1,22));story.append(Bars([('Oracle 可解性验证',1.0),('微量训练 checkpoint',chain.get('reward'))]))
 add('图 3　云端集成验证。两条柱状值来自不同角色的冒烟执行，不是模型对比，也不是训练前后提升。Oracle 得分 1 表明任务可完成，目标 checkpoint 的 0 分是被测行为失败。','small')
 add('这次训练仅验证真实权重更新与执行链，不支持学习效果结论。后续必须固定目标模型、数据接口、评测超参数和预算，以更多行为对齐的示范及独立任务检验改进。美元费用暂为 Unknown，不能按 0 元报告。')

 new('06 / PILOT TRIALS','原生界面校准记录')
 rows=[['运行','模型','步数','严格结果']]
 for r in e['trials']:
  if r['infrastructure_error']:continue
  val=r['verification'].get('success')
  rows.append([r['case'].replace('kanboard-',''),r['model'].replace('gpt-',''),r['steps'],'通过' if val else '未通过'])
 if len(rows)==1:rows.append(['暂无有效结果','-','-','-'])
 story.append(table(rows,[182,120,50,155]))
 failures=sum(bool(r['infrastructure_error']) for r in e['trials'])
 add(f'另有 {failures} 条基础设施失败记录，保留但不作为模型失败计分。单次校准结果只支持该配置下的执行证据，不能推广为模型能力排名。','small')
 add('排期失败的具体原因','h2');add('Astra 找到了可行且总价值最优的组合（价值 49），但成本为 62；符合第二层最小成本规则的方案成本为 52。严格评分因此未通过。这是条件优先级和验收完整性问题，不是网络错误。规划成本是明确构造的任务输入，并非真实上游项目预算。');
 add('为什么不继续报告先前的 +14.29 分','h2');add('旧版本的差值来自预写规则在少量 JSON fixture 上的切换，没有模型提出候选，也没有真实 UI 或隔离的隐藏集。它已明确降为回归测试结果，不能作为 RSI 提升。')
 add('后续实验准入','h2');add('只有通过环境重置、独立解法、负例验证、数据隔离和难度校准的任务才进入正式实验。正式结果还需重复运行、报告不确定性，并保留失败尝试与预算开销。')

 new('07 / RESEARCH PROTOCOL','改进实验应如何运行')
 add('两类更新对象分别报告','h2');add('Harness 轨道冻结模型权重，只允许更新注册的策略与工作流。Data 轨道冻结训练和评测服务，只改变新训练数据及允许范围内的配置。Astra/Sol 可担任研究或执行角色；它们不是本次 Tinker LoRA 训练目标。')
 add('每轮流程','h2');add('从当前已接受版本出发，运行训练任务，分析失败轨迹，产生带假设的候选；在独立验收任务上检查严格提升及逐题回归，接受后继承，拒绝则保留父版本。搜索结束并冻结最终选择后，才运行隐藏测试。')
 add('对照与统计','h2');add('至少比较冻结基线与相同预算的非递归搜索；记录最佳、最后与实际继承的版本，避免把测试集最高分用于选择。按任务族报告配对结果和多次执行，不把重复运行同一确定性规则当作独立模型采样。')
 add('不提前声称实现','h2');add('已实现的服务连通性、试验运行器和 schema 不是持续自我改进的证明。完整正式实验仍需在通过校准的真实软件任务上运行，并审计每一条结论。若改进为零或出现回归，报告必须保留该结果。')

 new('08 / REFERENCES','复现、来源与限制')
 refs=[('RSIBench-Data: Benchmarking Data-Centric Research for Recursive Self-Improvement','https://arxiv.org/abs/2607.25886'),('RSIBench-Data reference implementation','https://github.com/evolvent-ai/RSIBench-Data'),('Kanboard source and release v1.2.54','https://github.com/kanboard/kanboard/releases/tag/v1.2.54'),('Harbor documentation','https://docs.harborframework.com/'),('Tinker Python SDK','https://github.com/thinking-machines-lab/tinker'),('E2B sandbox SDK','https://github.com/e2b-dev/E2B'),('CUA-RSIBench source, evidence and reproduction','https://github.com/nanobanana123/cua-rsibench')]
 for i,(name,url) in enumerate(refs,1):add(f'[{i}] {escape(name)}<br/><link href="{url}" color="#007366">{url}</link>','small')
 add('复现范围','h2');add('代码包含任务包、应用初始化、GUI runner、训练后端、云端代理、Harbor adapter 和独立 verifier。需要自行配置提供商凭据；任何 API key、账号私有配置或完整提供商响应都不属于公开产物。')
 add('当前不能从结果推出的结论','h2');add('不能证明在未见过的应用中泛化，不能证明对 Windows/macOS 的完整控制，不能证明连续多轮模型自我提升，也不能从小样本决定 Astra/Sol 的总体排名。公开源数据、模型别名、默认服务配置与不可确认的费用均保留各自限制。')
 add('报告数据来自 outputs/evidence.json。字段为 null 表示未取得可靠证据；试验性任务结果不等同于正式发布的榜单。','small')
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 def footer(c,doc):
  c.setStrokeColor(HexColor('#cbd8d5'));c.line(44,43,551,43);c.setFillColor(MUTED);c.setFont('CJK',8);c.drawString(44,29,'CUA-RSIBench | Pilot evidence / 2026-09-23');c.drawRightString(551,29,str(doc.page))
 doc=SimpleDocTemplate(str(path),pagesize=(595,842),rightMargin=44,leftMargin=44,topMargin=43,bottomMargin=59,title='CUA-RSIBench: Real-Application Computer Use',author='CUA-RSIBench project')
 doc.build(story,onFirstPage=footer,onLaterPages=footer)
 print(path)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default='outputs/CUA-RSIBench-Technical-Report.pdf');a=p.parse_args();build(a.out)
