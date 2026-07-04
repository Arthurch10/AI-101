#!/usr/bin/env python3
"""导出自包含静态 HTML 报告 - 无需服务器，浏览器直接打开

用法:  python3 export_report.py [输出路径]
默认输出:  report.html
"""

import json
import sys

from src import database as db
from src.demo import load_demo_data
from src.analyzer import OpinionAnalyzer
from src.deep_analysis import DeepAnalyzer


def build_data(uids=None):
    """运行完整分析，返回与 /api/analyze 一致的结果字典"""
    db.init_db()
    if not db.get_all_bloggers():
        load_demo_data()

    if not uids:
        uids = [b["uid"] for b in db.get_all_bloggers()]

    OpinionAnalyzer().analyze_unprocessed(use_llm=False)

    posts, opinions = [], []
    for uid in uids:
        posts.extend(db.get_posts(uid, limit=500))
        opinions.extend(db.get_opinions(uid, limit=500))

    deep = DeepAnalyzer()
    bloggers = [db.get_blogger(u) for u in uids]

    return {
        "bloggers": [
            {"uid": b["uid"], "screen_name": b["screen_name"],
             "followers_count": b["followers_count"],
             "verified_reason": b.get("verified_reason", ""),
             "manual_selected": bool(b.get("manual_selected")),
             "post_count": db.get_blogger_post_count(b["uid"])}
            for b in db.get_all_bloggers()
        ],
        "selected": [{"uid": u, "screen_name": (db.get_blogger(u) or {}).get("screen_name", u)}
                     for u in uids],
        "trend": deep.analyze_market_trend(opinions, posts),
        "sectors": deep.analyze_sectors(opinions, posts)[:15],
        "tickers": deep.analyze_tickers(opinions, posts)[:15],
        "quant": deep.compute_quant_indicators(opinions, posts, bloggers),
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>微博财经博主 · 深度情绪分析报告</title>
<style>
  :root{--bg:#0f1420;--panel:#1a2130;--panel2:#222b3d;--border:#2c3752;--text:#e6ecf5;--muted:#8a97ad;--accent:#4f9dff;--green:#2ecc71;--red:#ff5c5c;--yellow:#f2c94c}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,"PingFang SC","Microsoft YaHei",system-ui,sans-serif;line-height:1.5}
  header{padding:20px 28px;border-bottom:1px solid var(--border);background:linear-gradient(90deg,#16203a,#0f1420)}
  header h1{margin:0;font-size:20px}
  header p{margin:4px 0 0;color:var(--muted);font-size:13px}
  .wrap{max-width:1180px;margin:0 auto;padding:22px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin-bottom:20px}
  .card h2{margin:0 0 14px;font-size:16px;display:flex;align-items:center;gap:8px}
  .badge{font-size:12px;color:var(--muted);font-weight:normal}
  .blogger-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
  .blogger{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--panel2);border:1px solid var(--border);border-radius:8px}
  .blogger.sel{border-color:var(--accent);background:#23324e}
  .blogger .name{font-weight:600}.blogger .meta{font-size:12px;color:var(--muted)}
  .star{color:var(--yellow)}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
  .kpi{background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:14px}
  .kpi .label{font-size:12px;color:var(--muted)}.kpi .val{font-size:24px;font-weight:700;margin-top:4px}.kpi .hint{font-size:11px;color:var(--muted);margin-top:4px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border)}
  th{color:var(--muted);font-weight:600}
  .bar-cell{display:flex;align-items:center;gap:8px}
  .bar{height:8px;border-radius:4px;background:var(--accent);min-width:2px}
  .bar-bg{flex:1;height:8px;border-radius:4px;background:var(--border);overflow:hidden}
  .tag{padding:2px 8px;border-radius:6px;font-size:12px;font-weight:600}
  .pos{color:var(--green)}.neg{color:var(--red)}.neu{color:var(--yellow)}
  .tag.pos{background:rgba(46,204,113,.15)}.tag.neg{background:rgba(255,92,92,.15)}.tag.neu{background:rgba(242,201,76,.15)}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  @media(max-width:820px){.grid2{grid-template-columns:1fr}}
  .summary{background:var(--panel2);border-left:3px solid var(--green);padding:12px 16px;border-radius:6px;font-size:14px}
  .rotation{display:flex;gap:24px;flex-wrap:wrap;margin-top:10px}
  .disclaimer{color:var(--muted);font-size:12px;margin-top:8px;padding:10px 14px;border:1px dashed var(--border);border-radius:8px}
</style>
</head>
<body>
<header>
  <h1>📈 微博财经博主 · 深度情绪分析报告</h1>
  <p>静态离线报告 · 生成时间 __GEN_TIME__</p>
</header>
<div class="wrap">
  <div class="card">
    <h2>① 分析范围 <span class="badge" id="scopeInfo"></span></h2>
    <div class="blogger-grid" id="bloggerGrid"></div>
  </div>
  <div class="card">
    <h2>② 市场整体走向与热度 <span class="badge" id="trendMeta"></span></h2>
    <div class="kpis" id="trendKpis"></div>
    <div style="margin-top:18px;" id="trendChart"></div>
  </div>
  <div class="grid2">
    <div class="card">
      <h2>③ 板块讨论度 · 共识 · 情绪</h2>
      <table><thead><tr><th>板块</th><th>提及</th><th>讨论热度</th><th>共识度</th><th>情绪</th></tr></thead><tbody id="sectorRows"></tbody></table>
    </div>
    <div class="card">
      <h2>④ 个股讨论度 · 情绪 · 共识</h2>
      <table><thead><tr><th>个股</th><th>提及</th><th>情绪分</th><th>博主共识</th><th>情绪</th></tr></thead><tbody id="tickerRows"></tbody></table>
    </div>
  </div>
  <div class="card">
    <h2>⑤ 量化参考指标</h2>
    <div class="kpis" id="quantKpis"></div>
    <div class="rotation" id="rotation"></div>
    <div class="summary" id="signalSummary" style="margin-top:14px;"></div>
    <div class="disclaimer">⚠️ 本报告基于微博财经博主观点的 NLP 语义与情绪分析生成，所有指标仅供参考，不构成投资建议。投资有风险，入市需谨慎。</div>
  </div>
</div>
<script>
const DATA = __DATA_JSON__;
const $=id=>document.getElementById(id);
const fmt=n=>n.toLocaleString('zh-CN');
const sentClass=s=>s>=0.15?'pos':(s<=-0.15?'neg':'neu');
function kpi(l,v,h){return `<div class="kpi"><div class="label">${l}</div><div class="val">${v}</div><div class="hint">${h||''}</div></div>`}
function barCell(v){return `<div class="bar-cell"><div class="bar-bg"><div class="bar" style="width:${v}%"></div></div><span>${Math.round(v)}</span></div>`}
function sparkline(series){
  const W=760,H=170,pad=34;
  const xs=series.map((_,i)=>pad+i*((W-2*pad)/Math.max(series.length-1,1)));
  const ys=series.map(p=>{const v=Math.max(-1,Math.min(1,p[1]));return H-pad-((v+1)/2)*(H-2*pad)});
  const zeroY=H-pad-0.5*(H-2*pad);
  const line=xs.map((x,i)=>`${i?'L':'M'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const area=`${line} L${xs[xs.length-1].toFixed(1)},${(H-pad)} L${xs[0].toFixed(1)},${(H-pad)} Z`;
  const pts=xs.map((x,i)=>`<circle cx="${x.toFixed(1)}" cy="${ys[i].toFixed(1)}" r="4" fill="#4f9dff"/>`).join('');
  const lbls=series.map((p,i)=>`<text x="${xs[i].toFixed(1)}" y="${H-10}" fill="#8a97ad" font-size="12" text-anchor="middle">${p[0]}</text>`).join('');
  const vals=series.map((p,i)=>`<text x="${xs[i].toFixed(1)}" y="${(ys[i]-10).toFixed(1)}" fill="#e6ecf5" font-size="12" text-anchor="middle">${p[1]>=0?'+':''}${p[1].toFixed(2)}</text>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-height:190px">
    <line x1="${pad}" y1="${zeroY}" x2="${W-pad}" y2="${zeroY}" stroke="#2c3752" stroke-dasharray="4 4"/>
    <path d="${area}" fill="rgba(79,157,255,.15)"/>
    <path d="${line}" fill="none" stroke="#4f9dff" stroke-width="2.5"/>
    ${pts}${vals}${lbls}
    <text x="6" y="${pad}" fill="#8a97ad" font-size="11">+1</text>
    <text x="6" y="${zeroY+4}" fill="#8a97ad" font-size="11">0</text>
    <text x="6" y="${H-pad}" fill="#8a97ad" font-size="11">-1</text>
  </svg>`;
}

function renderBloggers(){
  const selSet=new Set(DATA.selected.map(s=>s.uid));
  $('scopeInfo').textContent=`分析 ${DATA.selected.length} / ${DATA.bloggers.length} 位博主`;
  $('bloggerGrid').innerHTML=DATA.bloggers.map(b=>`
    <div class="blogger ${selSet.has(b.uid)?'sel':''}">
      <div><div class="name">${b.screen_name} ${b.manual_selected?'<span class="star">★</span>':''}</div>
      <div class="meta">${fmt(b.followers_count)} 粉丝 · ${b.verified_reason||'—'} · ${b.post_count} 帖</div></div>
    </div>`).join('');
}
function renderTrend(){
  const t=DATA.trend;
  $('trendMeta').textContent=DATA.selected.map(s=>s.screen_name).join('、');
  const dc={'上行':'pos','下行':'neg','震荡':'neu'}[t.trend_direction];
  const mc=t.momentum>=0?'pos':'neg';
  $('trendKpis').innerHTML=
    kpi('市场走向',`<span class="${dc}">${t.trend_direction}</span>`,'整体情绪方向')+
    kpi('趋势强度',t.trend_strength,'0-100')+
    kpi('市场热度',t.heat_index,'0-100 互动+频率')+
    kpi('情绪动量',`<span class="${mc}">${t.momentum>=0?'+':''}${t.momentum}</span>`,'周环比')+
    kpi('量能信号',t.volume_signal,'发帖频率')+
    kpi('平均情绪',`<span class="${sentClass(t.avg_sentiment)}">${t.avg_sentiment>=0?'+':''}${t.avg_sentiment.toFixed(3)}</span>`,`${t.total_posts} 帖 · ${fmt(t.total_engagement)} 互动`);
  $('trendChart').innerHTML='<div class="badge" style="margin-bottom:6px">近 4 周情绪趋势</div>'+sparkline(t.weekly_sentiment_trend);
}
function renderSectors(){
  $('sectorRows').innerHTML=DATA.sectors.map(s=>`<tr><td><b>${s.name}</b></td><td>${s.mention_count}</td>
    <td style="min-width:120px">${barCell(s.discussion_heat)}</td><td style="min-width:120px">${barCell(s.consensus_degree)}</td>
    <td><span class="tag ${sentClass(s.sentiment_score)}">${s.sentiment_label}</span> <span class="${sentClass(s.sentiment_score)}">${s.sentiment_score>=0?'+':''}${s.sentiment_score.toFixed(2)}</span></td></tr>`).join('');
}
function renderTickers(){
  $('tickerRows').innerHTML=DATA.tickers.map(t=>`<tr><td><b>${t.name}</b></td><td>${t.mention_count}</td>
    <td class="${sentClass(t.sentiment_score)}">${t.sentiment_score>=0?'+':''}${t.sentiment_score.toFixed(2)}</td>
    <td style="min-width:120px">${barCell(t.blogger_consensus)}</td>
    <td><span class="tag ${sentClass(t.sentiment_score)}">${t.sentiment_label}</span></td></tr>`).join('');
}
function renderQuant(){
  const q=DATA.quant;
  const bc=q.blogger_sentiment_index>=30?'pos':(q.blogger_sentiment_index<=-30?'neg':'neu');
  const sc=q.sentiment_momentum>=0?'pos':'neg';
  $('quantKpis').innerHTML=
    kpi('博主情绪指数 BSI',`<span class="${bc}">${q.blogger_sentiment_index>=0?'+':''}${q.blogger_sentiment_index}</span>`,'-100~100')+
    kpi('市场热度指数 MHI',q.market_heat_index,'0~100')+
    kpi('共识指数 CI',q.consensus_index,'0~100 越高越一致')+
    kpi('情绪动量 SM',`<span class="${sc}">${q.sentiment_momentum>=0?'+':''}${q.sentiment_momentum}</span>`,'正=改善')+
    kpi('风险偏好 RAI',q.risk_appetite_index,'0~100 看多占比');
  const r=q.sector_rotation_signal;
  $('rotation').innerHTML=(r.gaining.length?`<div><b class="pos">▲ 升温:</b> ${r.gaining.join('、')}</div>`:'')+(r.losing.length?`<div><b class="neg">▼ 降温:</b> ${r.losing.join('、')}</div>`:'');
  $('signalSummary').textContent='📊 '+q.signal_summary;
}
renderBloggers();renderTrend();renderSectors();renderTickers();renderQuant();
</script>
</body>
</html>
"""


def export(out_path="report.html", uids=None):
    from datetime import datetime
    data = build_data(uids)
    html = (HTML_TEMPLATE
            .replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
            .replace("__GEN_TIME__", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 已生成静态报告: {out_path}")
    print(f"  分析博主: {', '.join(s['screen_name'] for s in data['selected'])}")
    print(f"  市场走向: {data['trend']['trend_direction']} | 热度: {data['trend']['heat_index']} | BSI: {data['quant']['blogger_sentiment_index']}")
    print(f"  用浏览器直接打开该文件即可查看完整可视化报告。")
    return out_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "report.html"
    export(out)
