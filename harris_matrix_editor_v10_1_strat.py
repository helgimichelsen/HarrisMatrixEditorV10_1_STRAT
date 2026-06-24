import json, zipfile, re, math, xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from collections import defaultdict, deque, Counter

APP_TITLE = "Harris Matrix Editor V10.1 STRAT"
BOX_W, BOX_H = 124, 46
LEFT, TOP = 360, 110
X_STEP, Y_STEP = 176, 104
PALETTE = {
    "Structural":"#B9D7EF", "Deposit":"#F8E8A8", "Cut":"#F4B2B2", "Fill":"#F7C986",
    "Surface":"#C7E9BF", "Natural":"#D7D7D7", "Geology":"#CBCBCB", "Unexcavated":"#C2C2C2",
    "Same context":"#F3B8C8", "Unknown":"#F3F3F3"
}

def norm_id(cid):
    cid=str(cid).strip()
    if cid == "F!10": return "F110"
    if cid in ("G", "Natural", "Geology"): return "Natural/Geology"
    if cid == "U": return "Unexcavated"
    if cid in ("F8", "F29"): return "F8=F29"
    return cid

def norm_type(t):
    if not t: return "Unknown"
    s=str(t).lower()
    if any(x in s for x in ["struct","wall","sten","stone","bygning","gærde","gaerde"]): return "Structural"
    if "fill" in s: return "Fill"
    if "cut" in s: return "Cut"
    if any(x in s for x in ["surface","interface","top","muld","topsoil"]): return "Surface"
    if "unexcavated" in s: return "Unexcavated"
    if "geology" in s: return "Geology"
    if "natural" in s: return "Natural"
    if any(x in s for x in ["deposit","lag","layer","sand","flyvesand","collapse","kolaps"]): return "Deposit"
    if "=" in str(t): return "Same context"
    return str(t) if str(t) in PALETTE else "Unknown"

def pnum(x):
    m=re.search(r"\d+", str(x)); return int(m.group()) if m else 999999

def box_w(label): return max(BOX_W, min(250, len(str(label))*8+48))
def esc(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
def short(s, maxc):
    s=str(s); return s if len(s)<=maxc else s[:maxc-1]+'…'

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(APP_TITLE); self.geometry('1700x1000')
        self.nodes={}; self.edges=[]; self.groups=[]; self.phases=[]
        self.selected=None; self.selected_group=None; self.selected_phase=None
        self.drag=(0,0); self.resizing_group=False; self.moving_group=False; self.moving_phase=False; self.zoom=1.0
        self._ui(); self.new_project()

    def _ui(self):
        top=tk.Frame(self); top.pack(fill=tk.X)
        buttons=[('Ny',self.new_project),('Åbn HMCX',self.open_hmcx),('Gem HMCX',self.save_hmcx),('Åbn JSON',self.open_json),('Gem JSON',self.save_json),('Tilføj context',self.add_context),('Tilføj relation',self.add_relation),('Tilføj struktur-boks',self.add_group),('Tilføj fase-linje',self.add_phase),('Auto-layout STRAT',self.auto_layout),('Auto-fit struktur/faser',self.auto_annotations),('Kontroller',self.validate_show),('Slet valgt',self.delete_selected),('Eksport PDF',self.export_pdf),('Eksport PNG',self.export_png),('Eksport SVG',self.export_svg),('Eksport Graph',self.export_graph),('Zoom +',lambda:self.set_zoom(self.zoom*1.15)),('Zoom -',lambda:self.set_zoom(self.zoom/1.15)),('Fit',self.fit),('Søg',self.search)]
        for text,cmd in buttons: tk.Button(top,text=text,command=cmd).pack(side=tk.LEFT,padx=1,pady=2)
        main=tk.PanedWindow(self,orient=tk.HORIZONTAL); main.pack(fill=tk.BOTH,expand=True)
        left=tk.Frame(main); main.add(left, stretch='always')
        self.canvas=tk.Canvas(left,bg='white',scrollregion=(0,0,9000,6000)); self.canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        ys=tk.Scrollbar(left,orient=tk.VERTICAL,command=self.canvas.yview); ys.pack(side=tk.RIGHT,fill=tk.Y)
        xs=tk.Scrollbar(left,orient=tk.HORIZONTAL,command=self.canvas.xview); xs.pack(side=tk.BOTTOM,fill=tk.X)
        self.canvas.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        right=tk.Frame(main,width=400); main.add(right)
        tk.Label(right,text='V10.1 STRAT Inspector',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=8,pady=6)
        self.info=tk.Text(right,height=13,width=48); self.info.pack(fill=tk.X,padx=8)
        tk.Button(right,text='Opdater valgt',command=self.update_selected).pack(fill=tk.X,padx=8,pady=3)
        tk.Label(right,text='Relationer',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=8,pady=6)
        self.rels=tk.Listbox(right,height=14); self.rels.pack(fill=tk.BOTH,expand=True,padx=8)
        tk.Button(right,text='Slet valgt relation',command=self.delete_relation).pack(fill=tk.X,padx=8,pady=3)
        tk.Label(right,text='Feature type farver',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=8,pady=6)
        self.legend=tk.Canvas(right,height=250,bg='#FBFBFB'); self.legend.pack(fill=tk.X,padx=8); self.draw_legend()
        self.status=tk.StringVar(value='V10.1 STRAT klar'); tk.Label(self,textvariable=self.status,anchor='w').pack(fill=tk.X)
        self.canvas.bind('<ButtonPress-1>',self.press); self.canvas.bind('<B1-Motion>',self.drag_motion); self.canvas.bind('<Double-Button-1>',self.double)
        self.canvas.bind('<MouseWheel>',self.wheel); self.canvas.bind('<ButtonPress-3>',self.pan_start); self.canvas.bind('<B3-Motion>',self.pan_move)

    def draw_legend(self):
        self.legend.delete('all'); y=12
        for k,c in PALETTE.items():
            self.legend.create_rectangle(10,y,34,y+16,fill=c,outline='#555'); self.legend.create_text(44,y+8,text=k,anchor='w',font=('Segoe UI',9)); y+=22
        self.legend.create_text(10,y+10,text='Source relation = yngre/over',anchor='w',font=('Segoe UI',9))
        self.legend.create_text(10,y+30,text='Target relation = ældre/under',anchor='w',font=('Segoe UI',9))
        self.legend.create_text(10,y+50,text='Faser/bokse bevares og kan flyttes',anchor='w',font=('Segoe UI',9))

    def sx(self,x): return x*self.zoom
    def sy(self,y): return y*self.zoom
    def ux(self,x): return x/self.zoom
    def uy(self,y): return y/self.zoom

    def new_project(self):
        # Archaeological example from the conversation.
        self.nodes={
            'Topsoil': {'id':'Topsoil','label':'Topsoil','type':'Surface','x':LEFT+250,'y':TOP,'w':150,'h':BOX_H},
            'F1': {'id':'F1','label':'F1 muld','type':'Deposit','x':LEFT+250,'y':TOP+Y_STEP,'w':150,'h':BOX_H},
            'F2': {'id':'F2','label':'F2 flyvesand','type':'Deposit','x':LEFT+250,'y':TOP+2*Y_STEP,'w':170,'h':BOX_H},
            'F3': {'id':'F3','label':'F3 kollaps','type':'Deposit','x':LEFT+120,'y':TOP+3*Y_STEP,'w':160,'h':BOX_H},
            'F6': {'id':'F6','label':'F6 muldflade','type':'Deposit','x':LEFT+330,'y':TOP+3*Y_STEP,'w':170,'h':BOX_H},
            'F5': {'id':'F5','label':'F5 gulv','type':'Deposit','x':LEFT+120,'y':TOP+4*Y_STEP,'w':140,'h':BOX_H},
            'F4': {'id':'F4','label':'F4 bygning','type':'Structural','x':LEFT+120,'y':TOP+5*Y_STEP,'w':170,'h':BOX_H},
            'F7': {'id':'F7','label':'F7 gærde','type':'Structural','x':LEFT+330,'y':TOP+5*Y_STEP,'w':150,'h':BOX_H},
            'Unexcavated': {'id':'Unexcavated','label':'Unexcavated','type':'Unexcavated','x':LEFT+230,'y':TOP+7*Y_STEP,'w':230,'h':BOX_H},
            'Natural/Geology': {'id':'Natural/Geology','label':'Natural/Geology','type':'Geology','x':LEFT+220,'y':TOP+8*Y_STEP,'w':250,'h':BOX_H},
        }
        rel=[('Topsoil','F1'),('F1','F2'),('F2','F3'),('F2','F6'),('F2','F7'),('F3','F5'),('F5','F4'),('F6','F4'),('F6','F7'),('F4','Unexcavated'),('F7','Unexcavated'),('Unexcavated','Natural/Geology')]
        self.edges=[{'source':a,'target':b} for a,b in rel]
        self.groups=[]; self.phases=[]; self.auto_annotations({n:int((self.nodes[n]['y']-TOP)/Y_STEP) for n in self.nodes}); self.draw()

    def is_top(self,nid):
        txt=(nid+' '+str(self.nodes.get(nid,{}).get('label',''))).lower(); return nid.upper() in ('T','TOP','TOPSOIL') or 'topsoil' in txt or 'græstørv' in txt
    def is_unex(self,nid):
        txt=(nid+' '+str(self.nodes.get(nid,{}).get('label',''))).lower(); return norm_type(self.nodes.get(nid,{}).get('type'))=='Unexcavated' or 'unexcavated' in txt
    def is_geo(self,nid):
        txt=(nid+' '+str(self.nodes.get(nid,{}).get('label',''))).lower(); return norm_type(self.nodes.get(nid,{}).get('type')) in ('Natural','Geology') or 'natural' in txt or 'geology' in txt
    def bottomish(self,nid): return self.is_unex(nid) or self.is_geo(nid)

    def relation_pairs(self):
        pairs=[]
        for e in self.edges:
            a=norm_id(e['source']); b=norm_id(e['target'])
            if a in self.nodes and b in self.nodes and a!=b and not self.is_geo(a) and not self.is_top(b): pairs.append((a,b))
        if any(self.is_unex(n) for n in self.nodes) and any(self.is_geo(n) for n in self.nodes):
            u=next(n for n in self.nodes if self.is_unex(n)); g=next(n for n in self.nodes if self.is_geo(n)); pairs.append((u,g))
        return list(dict.fromkeys(pairs))

    def transitive_reduction(self, pairs):
        # For layout only: remove long/redundant links (especially many Topsoil->everything edges) when an indirect path exists.
        pairset=set(pairs); reduced=[]
        graph=defaultdict(list)
        for a,b in pairs: graph[a].append(b)
        def has_alt_path(a,b,skip):
            q=deque([a]); seen={a}
            while q:
                x=q.popleft()
                for y in graph.get(x,[]):
                    if (x,y)==skip: continue
                    if y==b: return True
                    if y not in seen: seen.add(y); q.append(y)
            return False
        for a,b in pairs:
            if not has_alt_path(a,b,(a,b)): reduced.append((a,b))
        return reduced

    def add_anchor_edges(self, pairs):
        pairs=list(pairs)
        indeg=Counter(b for a,b in pairs); out=Counter(a for a,b in pairs)
        top=next((n for n in self.nodes if self.is_top(n)), None)
        u=next((n for n in self.nodes if self.is_unex(n)), None)
        g=next((n for n in self.nodes if self.is_geo(n)), None)
        for n in self.nodes:
            if top and n!=top and not self.bottomish(n) and indeg[n]==0: pairs.append((top,n))
            if u and n!=u and n!=top and not self.is_geo(n) and out[n]==0: pairs.append((n,u))
        if u and g: pairs.append((u,g))
        return list(dict.fromkeys(pairs))

    def break_cycles(self, pairs):
        # Remove the least useful edge from any cycle for layout only; keep original list in editor.
        pairs=list(pairs); removed=[]
        def find_cycle():
            g=defaultdict(list)
            for a,b in pairs: g[a].append(b)
            temp=[]; perm=set(); active=set()
            def visit(n):
                active.add(n); temp.append(n)
                for m in g.get(n,[]):
                    if m in active:
                        return temp[temp.index(m):]+[m]
                    if m not in perm:
                        c=visit(m)
                        if c: return c
                active.remove(n); perm.add(n); temp.pop(); return None
            for n in self.nodes:
                if n not in perm:
                    c=visit(n)
                    if c: return c
            return None
        while True:
            cyc=find_cycle()
            if not cyc: break
            ce=list(zip(cyc,cyc[1:]))
            cand=ce[-1]
            # prefer removing artificial/top edge, then numeric backwards edge.
            for e in ce:
                if self.is_top(e[0]) or self.is_unex(e[0]) or pnum(e[0])>pnum(e[1]): cand=e; break
            if cand in pairs: pairs.remove(cand); removed.append(cand)
            else: break
        return pairs, removed

    def compute_levels(self, pairs):
        children=defaultdict(list); indeg={n:0 for n in self.nodes}
        for a,b in pairs:
            children[a].append(b); indeg[b]=indeg.get(b,0)+1; indeg.setdefault(a,0)
        q=deque([n for n,d in indeg.items() if d==0]); level={n:0 for n in self.nodes}; seen=set()
        while q:
            n=q.popleft(); seen.add(n)
            for m in children[n]:
                level[m]=max(level.get(m,0), level[n]+1); indeg[m]-=1
                if indeg[m]==0: q.append(m)
        for n in self.nodes:
            if n not in seen and not self.is_top(n) and not self.bottomish(n): level[n]=max(1, max(level.values())//2)
        max_mid=max([level[n] for n in self.nodes if not self.bottomish(n)] or [0])
        for n in self.nodes:
            if self.is_top(n): level[n]=0
            elif self.is_unex(n): level[n]=max_mid+2
            elif self.is_geo(n): level[n]=max_mid+3
            else: level[n]=max(1, level.get(n,1))
        return level

    def auto_layout(self):
        pairs=self.relation_pairs()
        pairs=self.add_anchor_edges(pairs)
        pairs=self.transitive_reduction(pairs)
        pairs, removed = self.break_cycles(pairs)
        level=self.compute_levels(pairs)
        buckets=defaultdict(list)
        for n,l in level.items(): buckets[l].append(n)
        # Initial numeric ordering
        order={}
        for lev in sorted(buckets):
            arr=sorted(buckets[lev], key=lambda x:(0 if x in ('F14','F21','F22') else 1, pnum(x), x))
            order[lev]=arr
        # Barycentric sweeps: place each branch under its parent(s), and parents above their children.
        parents=defaultdict(list); children=defaultdict(list)
        for a,b in pairs: children[a].append(b); parents[b].append(a)
        for _ in range(5):
            pos={n:i for lev,arr in order.items() for i,n in enumerate(arr)}
            for lev in sorted(order.keys())[1:]:
                order[lev].sort(key=lambda n: (sum(pos.get(p,0) for p in parents[n])/max(1,len(parents[n])), pnum(n), n))
            pos={n:i for lev,arr in order.items() for i,n in enumerate(arr)}
            for lev in sorted(order.keys(), reverse=True)[:-1]:
                order[lev].sort(key=lambda n: (sum(pos.get(c,0) for c in children[n])/max(1,len(children[n])) if children[n] else pos.get(n,0), pnum(n), n))
        for lev in sorted(order):
            arr=order[lev]
            for i,nid in enumerate(arr):
                self.nodes[nid]['x']=LEFT+i*X_STEP
                self.nodes[nid]['y']=TOP+lev*Y_STEP
                self.nodes[nid]['w']=box_w(self.nodes[nid].get('label', nid))
        self.auto_annotations(level)
        self.draw(); self.fit()
        msg='Auto-layout STRAT færdig'
        if removed: msg += ' (layout-cykler brudt: '+', '.join([f'{a}>{b}' for a,b in removed])+')'
        self.status.set(msg)

    def auto_annotations(self, level=None):
        if level is None: level={n:int((self.nodes[n]['y']-TOP)/Y_STEP) for n in self.nodes}
        if not self.phases:
            maxlev=max(level.values()) if level else 7
            self.phases=[{'name':'Tildækning / flyvesand','y':TOP+Y_STEP*2.5},{'name':'Forfald / kollaps','y':TOP+Y_STEP*3.5},{'name':'Brugsfase / konstruktion','y':TOP+Y_STEP*(maxlev-2.5)}]
        if not self.groups:
            self.fit_known_groups()
        else:
            self.fit_known_groups(update_existing=True)

    def fit_known_groups(self, update_existing=False):
        specs={'Bygning F4/F5/F3':['F4','F5','F3'], 'Gærde F7':['F7']}
        for name,members in specs.items():
            present=[self.nodes[m] for m in members if m in self.nodes]
            if not present: continue
            box=self.box_around(name,present)
            if update_existing:
                found=False
                for g in self.groups:
                    if name.split()[0] in g.get('name','') or any(m in g.get('name','') for m in members):
                        g.update(box); found=True; break
                if not found: self.groups.append(box)
            else:
                self.groups.append(box)

    def box_around(self,name,present):
        minx=min(n['x'] for n in present)-48; miny=min(n['y'] for n in present)-62
        maxx=max(n['x']+n.get('w',BOX_W) for n in present)+48; maxy=max(n['y']+n.get('h',BOX_H) for n in present)+48
        return {'name':name,'x':minx,'y':miny,'w':maxx-minx,'h':maxy-miny}

    def draw(self):
        self.canvas.delete('all')
        for y in range(80,5200,Y_STEP): self.canvas.create_line(self.sx(140),self.sy(y),self.sx(8600),self.sy(y),fill='#F8F8F8')
        for i,p in enumerate(self.phases):
            col='#A58E42' if i!=self.selected_phase else '#C22'
            self.canvas.create_line(self.sx(150),self.sy(p['y']),self.sx(8500),self.sy(p['y']),fill=col,dash=(10,6),width=1.5,tags=('phase',str(i)))
            self.canvas.create_text(self.sx(165),self.sy(p['y']-8),text=p['name'],anchor='sw',fill=col,font=('Segoe UI',10,'bold'),tags=('phase',str(i)))
        for i,g in enumerate(self.groups):
            col='#5D84AF' if i!=self.selected_group else '#C22'
            self.canvas.create_rectangle(self.sx(g['x']),self.sy(g['y']),self.sx(g['x']+g['w']),self.sy(g['y']+g['h']),outline=col,dash=(7,5),width=2,tags=('group',str(i)))
            self.canvas.create_text(self.sx(g['x']+10),self.sy(g['y']+18),text=g['name'],anchor='w',fill=col,font=('Segoe UI',10,'bold'),tags=('group',str(i)))
            self.canvas.create_rectangle(self.sx(g['x']+g['w']-12),self.sy(g['y']+g['h']-12),self.sx(g['x']+g['w']+2),self.sy(g['y']+g['h']+2),fill=col,outline='',tags=('gresize',str(i)))
        for e in self.edges:
            if e['source'] in self.nodes and e['target'] in self.nodes: self.draw_edge(e)
        for n in self.nodes.values(): self.draw_node(n)
        self.update_panel()

    def draw_edge(self,e):
        a,b=self.nodes[e['source']],self.nodes[e['target']]
        x1=a['x']+a.get('w',BOX_W)/2; y1=a['y']+a.get('h',BOX_H)
        x2=b['x']+b.get('w',BOX_W)/2; y2=b['y']; mid=(y1+y2)/2
        self.canvas.create_line(self.sx(x1),self.sy(y1),self.sx(x1),self.sy(mid),self.sx(x2),self.sy(mid),self.sx(x2),self.sy(y2),fill='#222',width=max(1,int(1.2*self.zoom)),capstyle=tk.ROUND,joinstyle=tk.ROUND)

    def draw_node(self,n):
        x,y,w,h=n['x'],n['y'],n.get('w',BOX_W),n.get('h',BOX_H); col=PALETTE.get(norm_type(n.get('type')),PALETTE['Unknown'])
        outline='#C22' if n['id']==self.selected else '#333'
        self.canvas.create_rectangle(self.sx(x),self.sy(y),self.sx(x+w),self.sy(y+h),fill=col,outline=outline,width=1.4,tags=('node',n['id']))
        self.canvas.create_text(self.sx(x+w/2),self.sy(y+h/2),text=short(n.get('label',n['id']),max(8,int(w/7))),font=('Segoe UI',8,'bold'),tags=('node',n['id']))

    def hit(self,event):
        x,y=self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)
        for item in reversed(self.canvas.find_overlapping(x,y,x,y)):
            tags=self.canvas.gettags(item)
            if 'node' in tags:
                for t in tags:
                    if t in self.nodes: return 'node',t
            if 'gresize' in tags:
                for t in tags:
                    if t.isdigit(): return 'gresize',int(t)
            if 'group' in tags:
                for t in tags:
                    if t.isdigit(): return 'group',int(t)
            if 'phase' in tags:
                for t in tags:
                    if t.isdigit(): return 'phase',int(t)
        return None,None

    def press(self,event):
        kind,val=self.hit(event); self.selected=self.selected_group=self.selected_phase=None; self.resizing_group=self.moving_group=self.moving_phase=False
        x,y=self.ux(self.canvas.canvasx(event.x)),self.uy(self.canvas.canvasy(event.y))
        if kind=='node': self.selected=val; n=self.nodes[val]; self.drag=(x-n['x'],y-n['y'])
        elif kind=='gresize': self.selected_group=val; g=self.groups[val]; self.resizing_group=True; self.drag=(x-(g['x']+g['w']),y-(g['y']+g['h']))
        elif kind=='group': self.selected_group=val; g=self.groups[val]; self.moving_group=True; self.drag=(x-g['x'],y-g['y'])
        elif kind=='phase': self.selected_phase=val; p=self.phases[val]; self.moving_phase=True; self.drag=(0,y-p['y'])
        self.draw()

    def drag_motion(self,event):
        x,y=self.ux(self.canvas.canvasx(event.x)),self.uy(self.canvas.canvasy(event.y)); dx,dy=self.drag
        if self.selected: self.nodes[self.selected]['x']=round(x-dx); self.nodes[self.selected]['y']=round(y-dy)
        elif self.selected_group is not None:
            g=self.groups[self.selected_group]
            if self.resizing_group: g['w']=max(110,round(x-dx-g['x'])); g['h']=max(68,round(y-dy-g['y']))
            elif self.moving_group: g['x']=round(x-dx); g['y']=round(y-dy)
        elif self.selected_phase is not None: self.phases[self.selected_phase]['y']=round(y-dy)
        self.draw()

    def double(self,event):
        kind,val=self.hit(event)
        if kind=='node':
            n=self.nodes[val]; lab=simpledialog.askstring('Label','Label:',initialvalue=n.get('label',val),parent=self)
            if lab is None: return
            typ=simpledialog.askstring('Feature Type','Structural / Deposit / Cut / Fill / Surface / Natural / Geology / Unexcavated:',initialvalue=n.get('type','Deposit'),parent=self)
            n['label']=lab; n['type']=norm_type(typ); n['w']=box_w(lab)
        elif kind=='group':
            name=simpledialog.askstring('Struktur-boks','Navn:',initialvalue=self.groups[val]['name'],parent=self)
            if name: self.groups[val]['name']=name
        elif kind=='phase':
            name=simpledialog.askstring('Fase','Navn:',initialvalue=self.phases[val]['name'],parent=self)
            if name: self.phases[val]['name']=name
        self.draw()

    def wheel(self,event): self.set_zoom(self.zoom*(1.08 if event.delta>0 else 1/1.08))
    def set_zoom(self,z): self.zoom=max(0.28,min(2.6,z)); self.draw()
    def pan_start(self,event): self.pan=(event.x,event.y)
    def pan_move(self,event):
        dx=event.x-self.pan[0]; dy=event.y-self.pan[1]
        self.canvas.xview_scroll(int(-dx/2),'units'); self.canvas.yview_scroll(int(-dy/2),'units'); self.pan=(event.x,event.y)

    def update_panel(self):
        self.info.delete('1.0',tk.END)
        if self.selected:
            n=self.nodes[self.selected]; self.info.insert('1.0',f"id={n['id']}\nlabel={n.get('label','')}\ntype={n.get('type','')}\nx={n.get('x',0)}\ny={n.get('y',0)}\nw={n.get('w',0)}\n")
        elif self.selected_group is not None:
            g=self.groups[self.selected_group]; self.info.insert('1.0',f"group={g['name']}\nx={g['x']}\ny={g['y']}\nw={g['w']}\nh={g['h']}\n")
        elif self.selected_phase is not None:
            p=self.phases[self.selected_phase]; self.info.insert('1.0',f"phase={p['name']}\ny={p['y']}\n")
        self.rels.delete(0,tk.END)
        if self.selected:
            for i,e in enumerate(self.edges):
                if e['source']==self.selected or e['target']==self.selected: self.rels.insert(tk.END,f"{i}: {e['source']} over {e['target']}")

    def update_selected(self):
        d={}
        for line in self.info.get('1.0',tk.END).splitlines():
            if '=' in line:
                k,v=line.split('=',1); d[k.strip()]=v.strip()
        if self.selected:
            n=self.nodes[self.selected]; old=n['id']; new=norm_id(d.get('id',old))
            if new!=old:
                if new in self.nodes: messagebox.showerror('Fejl','ID findes allerede'); return
                self.nodes[new]=self.nodes.pop(old); self.nodes[new]['id']=new
                for e in self.edges:
                    if e['source']==old: e['source']=new
                    if e['target']==old: e['target']=new
                self.selected=new; n=self.nodes[new]
            if 'label' in d: n['label']=d['label']; n['w']=box_w(d['label'])
            if 'type' in d: n['type']=norm_type(d['type'])
            for k in ('x','y','w'):
                if k in d:
                    try:n[k]=float(d[k])
                    except: pass
        elif self.selected_group is not None:
            g=self.groups[self.selected_group]
            if 'group' in d: g['name']=d['group']
            for k in ('x','y','w','h'):
                if k in d:
                    try:g[k]=float(d[k])
                    except: pass
        elif self.selected_phase is not None:
            p=self.phases[self.selected_phase]
            if 'phase' in d: p['name']=d['phase']
            if 'y' in d:
                try:p['y']=float(d['y'])
                except: pass
        self.draw()

    def add_context(self):
        cid=norm_id(simpledialog.askstring('Ny context','Context ID:',parent=self) or '')
        if not cid: return
        if cid in self.nodes: messagebox.showerror('Fejl','Findes allerede'); return
        typ=simpledialog.askstring('Feature Type','Structural / Deposit / Cut / Fill:',initialvalue='Deposit',parent=self) or 'Deposit'
        self.nodes[cid]={'id':cid,'label':cid,'type':norm_type(typ),'x':LEFT,'y':TOP,'w':box_w(cid),'h':BOX_H}; self.draw()

    def add_relation(self):
        a=norm_id(simpledialog.askstring('Relation','Yngre/over:',parent=self) or '')
        b=norm_id(simpledialog.askstring('Relation','Ældre/under:',parent=self) or '')
        if not a or not b: return
        self.ensure(a); self.ensure(b)
        if not any(e['source']==a and e['target']==b for e in self.edges): self.edges.append({'source':a,'target':b})
        self.draw()
    def ensure(self,cid):
        if cid not in self.nodes: self.nodes[cid]={'id':cid,'label':cid,'type':'Unknown','x':LEFT,'y':TOP,'w':box_w(cid),'h':BOX_H}
    def add_group(self):
        name=simpledialog.askstring('Struktur-boks','Navn:',initialvalue='Konstruktion',parent=self)
        if name: self.groups.append({'name':name,'x':LEFT+120,'y':TOP+160,'w':430,'h':220}); self.draw()
    def add_phase(self):
        name=simpledialog.askstring('Fase-linje','Navn:',initialvalue='Fase',parent=self)
        if name: self.phases.append({'name':name,'y':TOP+260}); self.draw()
    def delete_selected(self):
        if self.selected:
            nid=self.selected; del self.nodes[nid]; self.edges=[e for e in self.edges if e['source']!=nid and e['target']!=nid]; self.selected=None
        elif self.selected_group is not None: del self.groups[self.selected_group]; self.selected_group=None
        elif self.selected_phase is not None: del self.phases[self.selected_phase]; self.selected_phase=None
        self.draw()
    def delete_relation(self):
        sel=self.rels.curselection()
        if sel:
            idx=int(self.rels.get(sel[0]).split(':',1)[0])
            if 0<=idx<len(self.edges): del self.edges[idx]
            self.draw()

    def validate_show(self):
        pairs, removed = self.break_cycles(self.transitive_reduction(self.add_anchor_edges(self.relation_pairs())))
        if removed: messagebox.showwarning('Kontrol','Der var cykler i layout-grafen. Brudt for layout: '+str(removed))
        else: messagebox.showinfo('Kontrol','✓ Ingen cykler i layout-grafen')

    def open_hmcx(self):
        p=filedialog.askopenfilename(filetypes=[('HMCX','*.hmcx'),('All files','*.*')])
        if p: self.load_hmcx(p)
    def load_hmcx(self,path):
        try:
            with zipfile.ZipFile(path) as z:
                names=z.namelist(); xmlname='matrix.xml' if 'matrix.xml' in names else next(n for n in names if n.endswith('.xml'))
                xml=z.read(xmlname).decode('utf-8',errors='ignore'); meta=z.read('project.xml').decode('utf-8',errors='ignore') if 'project.xml' in names else ''
        except Exception as e: messagebox.showerror('HMCX fejl',str(e)); return
        root=ET.fromstring(xml); self.nodes={}; self.edges=[]; self.groups=[]; self.phases=[]; gid={}
        for el in root.iter():
            if el.tag.endswith('node'):
                graphid=el.attrib.get('id','')
                for sub in el.iter():
                    if sub.tag.endswith('hmcnode'):
                        cid=norm_id(sub.attrib.get('id') or graphid); gid[graphid]=cid; typ=norm_type(sub.attrib.get('type','Deposit'))
                        if cid=='Unexcavated': typ='Unexcavated'
                        if cid=='Natural/Geology': typ='Geology'
                        self.nodes[cid]={'id':cid,'label':cid,'type':typ,'x':float(sub.attrib.get('x','0') or 0),'y':float(sub.attrib.get('y','0') or 0),'w':box_w(cid),'h':BOX_H}; break
            elif el.tag.endswith('edge'):
                a=el.attrib.get('source'); b=el.attrib.get('target')
                if a and b:
                    a,b=norm_id(gid.get(a,a)),norm_id(gid.get(b,b))
                    if a!=b and not any(e['source']==a and e['target']==b for e in self.edges): self.edges.append({'source':a,'target':b})
        for m in re.finditer(r'<phase name="([^"]+)" y="([^"]+)"',meta): self.phases.append({'name':m.group(1),'y':float(m.group(2))})
        for m in re.finditer(r'<group name="([^"]+)" x="([^"]+)" y="([^"]+)" w="([^"]+)" h="([^"]+)"',meta): self.groups.append({'name':m.group(1),'x':float(m.group(2)),'y':float(m.group(3)),'w':float(m.group(4)),'h':float(m.group(5))})
        self.normalize(); self.auto_layout(); self.status.set(f'Åbnede {Path(path).name}: {len(self.nodes)} contexts, {len(self.edges)} relationer')
    def normalize(self):
        if not self.nodes: return
        minx=min(n['x'] for n in self.nodes.values()); miny=min(n['y'] for n in self.nodes.values())
        for n in self.nodes.values(): n['x']=round(n['x']-minx+LEFT); n['y']=round(n['y']-miny+TOP)

    def open_json(self):
        p=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if p:
            d=json.load(open(p,encoding='utf-8')); self.nodes={n['id']:n for n in d.get('nodes',[])}; self.edges=d.get('edges',[]); self.groups=d.get('groups',[]); self.phases=d.get('phases',[]); self.draw(); self.fit()
    def save_json(self):
        p=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON','*.json')])
        if p: json.dump({'nodes':list(self.nodes.values()),'edges':self.edges,'groups':self.groups,'phases':self.phases},open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    def save_hmcx(self):
        p=filedialog.asksaveasfilename(defaultextension='.hmcx',filetypes=[('HMCX','*.hmcx')])
        if p: write_hmcx(p,self.nodes,self.edges,self.groups,self.phases)

    def bounds(self):
        xs=[]; ys=[]
        for n in self.nodes.values(): xs += [n['x'],n['x']+n.get('w',BOX_W)]; ys += [n['y'],n['y']+n.get('h',BOX_H)]
        for g in self.groups: xs += [g['x'],g['x']+g['w']]; ys += [g['y'],g['y']+g['h']]
        for p in self.phases: ys.append(p['y'])
        return (min(xs)-110,min(ys)-110,max(xs)+110,max(ys)+110) if xs else (0,0,1000,700)
    def fit(self):
        minx,miny,maxx,maxy=self.bounds(); self.zoom=max(0.3,min(1.6,min(1220/max(1,maxx-minx),820/max(1,maxy-miny))))
        self.draw(); self.canvas.xview_moveto(max(0,self.sx(minx-180)/9000)); self.canvas.yview_moveto(max(0,self.sy(miny-130)/6000))

    def to_svg(self):
        minx,miny,maxx,maxy=self.bounds(); w=maxx-minx; h=maxy-miny
        parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{minx} {miny} {w} {h}"><rect x="{minx}" y="{miny}" width="{w}" height="{h}" fill="white"/>']
        for p in self.phases:
            parts.append(f'<line x1="{minx+24}" y1="{p["y"]}" x2="{maxx-24}" y2="{p["y"]}" stroke="#A58E42" stroke-width="1.4" stroke-dasharray="10 6"/>')
            parts.append(f'<text x="{minx+38}" y="{p["y"]-8}" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#A58E42">{esc(p["name"])}</text>')
        for g in self.groups:
            parts.append(f'<rect x="{g["x"]}" y="{g["y"]}" width="{g["w"]}" height="{g["h"]}" fill="none" stroke="#5D84AF" stroke-width="2" stroke-dasharray="7 5"/>')
            parts.append(f'<text x="{g["x"]+10}" y="{g["y"]+18}" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#5D84AF">{esc(g["name"])}</text>')
        for e in self.edges:
            if e['source'] in self.nodes and e['target'] in self.nodes:
                a,b=self.nodes[e['source']],self.nodes[e['target']]; x1=a['x']+a['w']/2; y1=a['y']+a['h']; x2=b['x']+b['w']/2; y2=b['y']; mid=(y1+y2)/2
                parts.append(f'<polyline points="{x1},{y1} {x1},{mid} {x2},{mid} {x2},{y2}" fill="none" stroke="#222" stroke-width="1.4"/>')
        for n in self.nodes.values():
            c=PALETTE.get(norm_type(n.get('type')),PALETTE['Unknown']); parts.append(f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" fill="{c}" stroke="#333" stroke-width="1.2"/>')
            parts.append(f'<text x="{n["x"]+n["w"]/2}" y="{n["y"]+n["h"]/2+4}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="11" font-weight="bold">{esc(n.get("label",n["id"]))}</text>')
        parts.append('</svg>'); return '\n'.join(parts)
    def export_svg(self):
        p=filedialog.asksaveasfilename(defaultextension='.svg',filetypes=[('SVG','*.svg')])
        if p: Path(p).write_text(self.to_svg(),encoding='utf-8')
    def export_png(self):
        p=filedialog.asksaveasfilename(defaultextension='.png',filetypes=[('PNG','*.png')])
        if p:
            import cairosvg; cairosvg.svg2png(bytestring=self.to_svg().encode('utf-8'),write_to=p,output_width=3000)
    def export_pdf(self):
        p=filedialog.asksaveasfilename(defaultextension='.pdf',filetypes=[('PDF','*.pdf')])
        if not p: return
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A3, landscape
        from reportlab.lib.colors import HexColor, black
        c=canvas.Canvas(p,pagesize=landscape(A3)); pw,ph=landscape(A3); minx,miny,maxx,maxy=self.bounds(); scale=min((pw-60)/(maxx-minx),(ph-60)/(maxy-miny))
        def tx(x): return 30+(x-minx)*scale
        def ty(y): return ph-(30+(y-miny)*scale)
        c.setLineWidth(.75)
        for pz in self.phases:
            c.setDash(6,4); c.setStrokeColor(HexColor('#A58E42')); c.line(tx(minx+24),ty(pz['y']),tx(maxx-24),ty(pz['y'])); c.setDash(); c.setFillColor(HexColor('#A58E42')); c.setFont('Helvetica-Bold',8); c.drawString(tx(minx+38),ty(pz['y']-8),pz['name'])
        c.setStrokeColor(black)
        for e in self.edges:
            if e['source'] in self.nodes and e['target'] in self.nodes:
                a,b=self.nodes[e['source']],self.nodes[e['target']]; x1=a['x']+a['w']/2; y1=a['y']+a['h']; x2=b['x']+b['w']/2; y2=b['y']; mid=(y1+y2)/2
                for (xa,ya),(xb,yb) in zip([(x1,y1),(x1,mid),(x2,mid)],[(x1,mid),(x2,mid),(x2,y2)]): c.line(tx(xa),ty(ya),tx(xb),ty(yb))
        for g in self.groups:
            c.setDash(5,4); c.setStrokeColor(HexColor('#5D84AF')); c.rect(tx(g['x']),ty(g['y']+g['h']),g['w']*scale,g['h']*scale,fill=0,stroke=1); c.setDash(); c.setFillColor(HexColor('#5D84AF')); c.setFont('Helvetica-Bold',8); c.drawString(tx(g['x']+10),ty(g['y']+18),g['name'])
        c.setDash(); c.setStrokeColor(black)
        for n in self.nodes.values():
            c.setFillColor(HexColor(PALETTE.get(norm_type(n.get('type')),PALETTE['Unknown']))); c.rect(tx(n['x']),ty(n['y']+n['h']),n['w']*scale,n['h']*scale,fill=1,stroke=1)
            label=str(n.get('label',n['id'])); fs=max(5,min(8.5,(n['w']*scale)/(max(1,len(label))*0.5))); c.setFillColor(black); c.setFont('Helvetica-Bold',fs); c.drawCentredString(tx(n['x']+n['w']/2),ty(n['y']+n['h']/2)-fs/3,label[:30])
        c.save()
    def export_graph(self):
        p=filedialog.asksaveasfilename(defaultextension='.dot',filetypes=[('Graphviz DOT','*.dot'),('Graph JSON','*.json')])
        if not p: return
        if p.lower().endswith('.json'): json.dump({'nodes':list(self.nodes.values()),'edges':self.edges,'groups':self.groups,'phases':self.phases},open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
        else:
            lines=['digraph HarrisMatrix {','  rankdir=TB;','  node [shape=box, fontname="Arial"];']
            for nid,n in self.nodes.items(): lines.append(f'  "{nid}" [label="{n.get("label",nid)}"];')
            for e in self.edges: lines.append(f'  "{e["source"]}" -> "{e["target"]}";')
            lines.append('}'); Path(p).write_text('\n'.join(lines),encoding='utf-8')
    def search(self):
        q=simpledialog.askstring('Søg','Context:',parent=self)
        if not q: return
        q=q.lower()
        for nid,n in self.nodes.items():
            if q in nid.lower() or q in str(n.get('label','')).lower():
                self.selected=nid; self.draw(); self.canvas.xview_moveto(max(0,self.sx(n['x']-260)/9000)); self.canvas.yview_moveto(max(0,self.sy(n['y']-200)/6000)); return

def hmc_type(t):
    t=norm_type(t)
    if t=='Surface': return 'SURFACE'
    if t=='Unexcavated': return 'UNEXCAVATED'
    if t in ('Geology','Natural'): return 'GEOLOGY'
    if t=='Cut': return 'SURFACE'
    return 'DEPOSIT'

def write_hmcx(path,nodes,edges,groups,phases):
    graphml=ET.Element('graphml',{'xmlns':'http://graphml.graphdrawing.org/xmlns/graphml'}); graph=ET.SubElement(graphml,'graph',{'id':'G','edgedefault':'directed'})
    for nid,n in nodes.items():
        node=ET.SubElement(graph,'node',{'id':nid}); data=ET.SubElement(node,'data',{'key':'d0'}); ET.SubElement(data,'hmcnode',{'id':nid,'name':n.get('label',nid),'description':'','type':hmc_type(n.get('type')),'valid':'true','x':str(n.get('x',0)),'y':str(n.get('y',0)),'layer':'0','index':'0','bookmarked':'false'})
    for i,e in enumerate(edges):
        edge=ET.SubElement(graph,'edge',{'id':f'e{i}','source':e['source'],'target':e['target']}); data=ET.SubElement(edge,'data',{'key':'d1'}); ET.SubElement(data,'hmcedge',{'type':'ABOVE','valid':'true'})
    annotations='<annotations>'+''.join(f'<phase name="{esc(p["name"])}" y="{p["y"]}"/>' for p in phases)+''.join(f'<group name="{esc(g["name"])}" x="{g["x"]}" y="{g["y"]}" w="{g["w"]}" h="{g["h"]}"/>' for g in groups)+'</annotations>'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.xml',f'<?xml version="1.0" ?><ProjectProperties Name="Harris Matrix Editor V10.1 STRAT" Description="Direct Harris relation layout with phase and structure annotations">{annotations}</ProjectProperties>')
        z.writestr('matrix.xml',ET.tostring(graphml,encoding='utf-8',xml_declaration=True))

if __name__=='__main__': App().mainloop()
