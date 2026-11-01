import base64, json, pathlib

OUT = pathlib.Path("/home/user/garrettoscarerickson-ctrl.github.io/d4-bracket")
silk = base64.b64encode(open("/tmp/ps2p.ttf", "rb").read()).decode()
pix = base64.b64encode(open("/tmp/jersey.ttf", "rb").read()).decode()

# (name, monogram, bg, fg) -- bg = card color, fg = text color
T = lambda n, m, bg, fg="#fff", s=None: dict(n=n, m=m, bg=bg, fg=fg, s=s)
TBD = T("TBD", "?", "#8a8f99", "#fff")

# Bracket order: each group of 4 = one district (pairs feed a district final),
# each group of 8 = one region.
LEFT = [  # Regions 1 & 2  (s = first-round score)
    T("KENOWA HILLS", "KH", "#4b2a83", "#ffd447", 49), T("GR CHRISTIAN", "GC", "#7a1f2b", s=35),
    T("LUDINGTON", "LU", "#f47b20", "#111", 19), T("FRUITPORT", "F", "#13294b", "#ff4b4b", 15),
    T("FH EASTERN", "FE", "#1b1b1f", "#ff4b4b", 33), T("BIG RAPIDS", "BR", "#c8102e", s=12),
    T("UNITY CHRISTIAN", "UC", "#13294b", s=46), T("SPRING LAKE", "SL", "#f4f6fa", "#1d3c8f", 18),
    T("EDWARDSBURG", "E", "#f47b20", "#111", 27), T("VICKSBURG", "V", "#b3121b", s=14),
    T("PORTLAND", "P", "#f4f6fa", "#c8102e", 22), T("PAW PAW", "PP", "#9b1b1f", s=13),
    T("SOUTH CHRISTIAN", "SC", "#1d4f9c", s=63), T("MARSHALL", "M", "#c8102e", s=27),
    T("LAKESHORE", "L", "#f4f6fa", "#13294b", 49), T("HASTINGS", "H", "#003a8c", "#ffd447", 44),
]
RIGHT = [  # Regions 3 & 4
    T("GOODRICH", "G", "#0f6b37", s=45), T("WILLIAMSTON", "W", "#f47b20", "#111", 6),
    T("ST. JOHNS", "SJ", "#f4f6fa", "#c8102e", 49), T("BRANDON", "B", "#1b1b1f", "#ff4b4b", 21),
    T("DIVINE CHILD", "DC", "#003a8c", "#ffd447", 45), T("LANSING SEXTON", "S", "#b3121b", s=27),
    T("ADRIAN", "A", "#6d1a36", "#ffd447", 65), T("TECUMSEH", "T", "#1b1b1f", "#ff4b4b", 27),
    T("EAST ENGLISH", "EE", "#1d3c8f", "#ffd447", 22), T("LUTHERAN NORTH", "LN", "#f4f6fa", "#13294b", 36),
    T("MARYSVILLE", "MV", "#4b2a83", s=44), T("SOUTHEASTERN", "SE", "#f47b20", "#111", 24),
    T("DETROIT CODY", "C", "#7a1f2b", "#ffd447", 16), T("ST. CLAIR", "SC", "#f4f6fa", "#13294b", 41),
    T("COUNTRY DAY", "CD", "#ffd200", "#111", 24), T("LAMPHERE", "L", "#1d4f9c", s=0),
]

html = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Division 4 Playoffs 2026</title>
<style>
@font-face{font-family:Silk;src:url(data:font/ttf;base64,__SILK__)}
@font-face{font-family:Pix;src:url(data:font/ttf;base64,__PIX__)}
html,body{margin:0;background:#111}
#c{position:relative;width:1600px;height:1260px;overflow:hidden;
  background:#2f6fe6;
  background-image:linear-gradient(rgba(255,255,255,.035) 2px,transparent 2px),linear-gradient(90deg,rgba(255,255,255,.035) 2px,transparent 2px);
  background-size:16px 16px;font-family:Pix,sans-serif}
.title{position:absolute;left:50%;top:22px;transform:translateX(-50%);background:#fff;border:6px solid #111;
  box-shadow:8px 8px 0 #0b2a66;padding:10px 40px 12px;text-align:center;white-space:nowrap}
.title h1{margin:0;font:400 66px/1 Silk;letter-spacing:0;color:#111}
.title h2{margin:14px 0 0;font:400 24px/1 Silk;letter-spacing:0;color:#111}
svg{position:absolute;left:0;top:0}
.card{position:absolute;display:flex;align-items:center;border:4px solid #111;box-sizing:border-box;
  font:400 33px/1 Pix;letter-spacing:0;text-shadow:2px 2px 0 rgba(0,0,0,.35);white-space:nowrap;overflow:hidden}
.card.light{text-shadow:none}
.card .logo{flex:none;width:58px;height:100%;display:flex;align-items:center;justify-content:center;
  font:400 15px/1 Silk;border-right:4px solid #111;box-sizing:border-box}
.card .nm{padding:0 10px;flex:1;overflow:hidden}
.right .logo{order:2;border-right:none;border-left:4px solid #111}
.right .nm{text-align:right}
.card .sc{flex:none;width:58px;height:100%;display:flex;align-items:center;justify-content:center;background:#111;color:#fff;font:400 18px/1 Silk;text-shadow:none}
.right .sc{order:-1}
.card.lost{filter:grayscale(.85) brightness(.62)}
.card.lost .nm{text-decoration:line-through;text-decoration-thickness:3px}
.q.win{font:400 15px/42px Silk;text-shadow:none;box-shadow:inset 0 -6px 0 rgba(0,0,0,.25), inset 0 4px 0 rgba(255,255,255,.25)}
.q{position:absolute;width:58px;height:50px;background:#7d8494;border:4px solid #111;box-sizing:border-box;
  box-shadow:inset 0 -6px 0 #5d6372, inset 0 4px 0 #a2a9b8;color:#fff;font:400 24px/42px Silk;text-align:center;
  text-shadow:3px 3px 0 #333}
.q.big{width:132px;height:58px;line-height:50px;font-size:30px;background:#9aa1b0}
.champ{position:absolute;left:50%;transform:translateX(-50%);text-align:center;font:400 30px/1.3 Silk;color:#fff;
  text-shadow:3px 3px 0 #0b2a66, -2px -2px 0 #0b2a66, 2px -2px 0 #0b2a66, -2px 2px 0 #0b2a66}
.lbl{position:absolute;font:400 13px/1 Silk;color:#fff;background:#0b2a66;padding:5px 8px;border:3px solid #111;letter-spacing:1px}
.foot{position:absolute;bottom:10px;left:0;right:0;text-align:center;font:400 12px/1 Silk;color:rgba(255,255,255,.75)}
</style></head><body><div id="c">
<div class="title"><h1>DIVISION 4 PLAYOFFS</h1><h2>MICHIGAN HIGH SCHOOL FOOTBALL</h2></div>
<svg id="lines" width="1600" height="1260"></svg>
<div id="trophy"></div>
</div>
<script>
const LEFT=__LEFT__, RIGHT=__RIGHT__;
const C=document.getElementById('c'), S=document.getElementById('lines');
const W=1600, TOP=205, PAIR=128, CARD_H=50, CARD_W=332, BOX_W=58, BOX_H=50;
const LINE='#d9ecff', EDGE='#0b2a66';
function el(cls,css,html){const d=document.createElement('div');d.className=cls;Object.assign(d.style,css);if(html!=null)d.innerHTML=html;C.appendChild(d);return d}
function seg(x1,y1,x2,y2){for(const [c,w] of [[EDGE,10],[LINE,5]]){const l=document.createElementNS('http://www.w3.org/2000/svg','line');
  l.setAttribute('x1',x1);l.setAttribute('y1',y1);l.setAttribute('x2',x2);l.setAttribute('y2',y2);l.setAttribute('stroke',c);l.setAttribute('stroke-width',w);l.setAttribute('stroke-linecap','square');(w==10?S.prepend(l):S.appendChild(l))}}
// connector from children (ys) at x edge to parent at px,py, dir=+1 rightwards
function join(xs,ys,px,py,dir){const mid=(xs+px)/2;for(const y of ys){seg(xs,y,mid,y)}seg(mid,Math.min(...ys,py),mid,Math.max(...ys,py));seg(mid,py,px,py)}
const box=(cx,cy,big)=>el('q'+(big?' big':''),{left:(cx-(big?66:BOX_W/2))+'px',top:(cy-(big?29:BOX_H/2))+'px'},'?');

function side(teams,dir){
  const right=dir<0, x0=right?W-20-CARD_W:20;
  const edge=right?x0:x0+CARD_W;
  // round x centers
  const rx=[1,2,3,4].map(i=>right? edge-28-i*74+BOX_W/2 - 0 : edge+28+i*74-BOX_W/2);
  let ys=[];
  for(let p=0;p<8;p++){
    const y=TOP+p*PAIR + (p>=4?18:0);
    const pairYs=[];const a=teams[p*2],b=teams[p*2+1];const w=a.s>b.s?a:b;
    for(let k=0;k<2;k++){const t=teams[p*2+k];const light=t.bg=='#f4f6fa'||t.bg=='#ffd200'||t.bg=='#f47b20';
      const cy=y+k*(CARD_H+4);
      const d=el('card'+(right?' right':'')+(light?' light':'')+(t===w?'':' lost'),{left:x0+'px',top:cy+'px',width:CARD_W+'px',height:CARD_H+'px',background:t.bg,color:t.fg},
        `<span class="logo" style="background:${t.fg};color:${t.bg}">${t.m}</span><span class="nm">${t.n}</span><span class="sc">${t.s}</span>`);
      pairYs.push(cy+CARD_H/2);}
    const py=(pairYs[0]+pairYs[1])/2; join(edge,pairYs,rx[0]-dir*BOX_W/2,py,dir); const wb=box(rx[0],py); wb.classList.add('win'); wb.textContent=w.m; wb.style.background=w.bg; wb.style.color=w.fg; ys.push(py);
  }
  for(let r=1;r<4;r++){const nys=[];for(let i=0;i<ys.length;i+=2){const py=(ys[i]+ys[i+1])/2;
    join(rx[r-1]+dir*BOX_W/2,[ys[i],ys[i+1]],rx[r]-dir*BOX_W/2,py,dir);box(rx[r],py);nys.push(py)}ys=nys}
  // region labels
  const regs=right?['REGION 3','REGION 4']:['REGION 1','REGION 2'];
  return {x:rx[3]+dir*BOX_W/2,y:ys[0],regs};
}
const L=side(LEFT,1), R=side(RIGHT,-1);
// championship
const cx=W/2, cy1=900, cy2=990;
box(cx,cy1,true); box(cx,cy2,true);
seg(L.x,L.y,cx-110,L.y); seg(cx-110,cy1,cx-110,L.y); seg(cx-110,cy1,cx-66,cy1);
seg(R.x,R.y,cx+110,R.y); seg(cx+110,cy2,cx+110,R.y); seg(cx+110,cy2,cx+66,cy2);
el('champ',{top:'1050px'},'STATE<br>CHAMPIONSHIP');
el('lbl',{left:'20px',top:(TOP-36)+'px'},'REGION 1');el('lbl',{left:'20px',top:(TOP+4*PAIR+18-36)+'px'},'REGION 2');
el('lbl',{right:'20px',top:(TOP-36)+'px'},'REGION 3');el('lbl',{right:'20px',top:(TOP+4*PAIR+18-36)+'px'},'REGION 4');
el('foot',{},'FIRST ROUND FINAL &middot; DISTRICT FINALS NOV. 6 &middot; STATE FINAL AT FORD FIELD');
// trophy (SVG, pixel-ish wooden Michigan plaque)
document.getElementById('trophy').outerHTML=`<svg width="250" height="440" viewBox="0 0 300 528" style="left:675px;top:222px" shape-rendering="crispEdges">
 <defs><pattern id="wood" width="40" height="12" patternUnits="userSpaceOnUse"><rect width="40" height="12" fill="#a8652e"/><rect y="3" width="26" height="3" fill="#8f5222"/><rect x="18" y="9" width="22" height="2" fill="#bb7740"/></pattern></defs>
 <!-- plaque -->
 <polygon points="70,40 230,40 250,470 50,470" fill="#1a1a1a" stroke="#111" stroke-width="6"/>
 <!-- lower peninsula mitten -->
 <path d="M150,105 L172,96 L190,112 L196,140 L212,150 L226,188 L222,232 L212,262 L232,248 L244,270 L240,320 L226,372 L200,400 L120,404 L110,360 L96,318 L100,270 L110,232 L120,196 L130,160 L138,128 Z" fill="url(#wood)" stroke="#5a3010" stroke-width="5"/>
 <!-- upper peninsula -->
 <path d="M58,96 L96,74 L140,70 L170,58 L210,66 L196,82 L160,86 L128,96 L98,100 L76,114 Z" fill="url(#wood)" stroke="#5a3010" stroke-width="5"/>
 <text x="150" y="58" text-anchor="middle" font-family="Silk" font-size="22" fill="#ffd447">2026</text>
 <text x="150" y="210" text-anchor="middle" font-family="Silk" font-size="17" fill="#ffd447">CHAMPION</text>
 <!-- pixel football -->
 <g transform="translate(130,236)"><rect x="8" y="0" width="24" height="4" fill="#5b2c0d"/><rect x="2" y="4" width="36" height="4" fill="#6e3611"/><rect x="0" y="8" width="40" height="8" fill="#6e3611"/><rect x="2" y="16" width="36" height="4" fill="#6e3611"/><rect x="8" y="20" width="24" height="4" fill="#5b2c0d"/><rect x="10" y="11" width="20" height="2" fill="#fff"/><rect x="13" y="8" width="2" height="8" fill="#fff"/><rect x="19" y="8" width="2" height="8" fill="#fff"/><rect x="25" y="8" width="2" height="8" fill="#fff"/></g>
 <text x="150" y="300" text-anchor="middle" font-family="Silk" font-size="15" fill="#3b1c06">MHSAA</text>
 <text x="150" y="430" text-anchor="middle" font-family="Pix" font-size="44" fill="#ffd447">Football</text>
 <text x="150" y="456" text-anchor="middle" font-family="Silk" font-size="13" fill="#fff">DIVISION 4</text>
 <!-- base -->
 <rect x="30" y="470" width="240" height="26" fill="#b5733a" stroke="#111" stroke-width="5"/>
 <rect x="10" y="494" width="280" height="30" fill="#8f5222" stroke="#111" stroke-width="5"/>
</svg>`;
</script></body></html>"""
html = (html.replace("__SILK__", silk).replace("__PIX__", pix)
        .replace("__LEFT__", json.dumps(LEFT)).replace("__RIGHT__", json.dumps(RIGHT)))
(OUT / "division4-bracket.html").write_text(html)

