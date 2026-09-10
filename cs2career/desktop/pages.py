"""Page composition for the native career desk.

These views read the public state contract and dispatch existing domain
commands. They never create fictional standings or financial projections.
"""
from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from .. import cs2
from ..career import skins, story
from ..content import get_registry, reload_registry
from ..league import season as season_module
from ..world import eras as era_module
from ..world import ROLE_LABEL, MAPS
from ..paths import extension_root, save_root
from .theme import *
from .widgets import label, button, Crest, TacticalArt, Tooltip, meter


def section(parent,title,note=''):
    row = tk.Frame(parent,bg=parent.cget('bg'))
    row.pack(fill='x',pady=(0,12))
    label(row,title,size=12,bold=True).pack(side='left')
    if note:
        label(row,note,size=8,color=DIM).pack(side='right')
    return row


def columns(parent,weights=(2,1),padx=28):
    frame = tk.Frame(parent,bg=BG)
    frame.pack(fill='x',padx=padx,pady=8)
    result = []
    for i,weight in enumerate(weights):
        frame.columnconfigure(i,weight=weight,uniform='cols')
        col = tk.Frame(frame,bg=BG)
        col.grid(row=0,column=i,sticky='nsew',padx=(0,16 if i<len(weights)-1 else 0))
        result.append(col)
    return result


class Pages:
    def team_named(self,data,name):
        return next((t for t in data.get('teams',[]) if t.get('name')==name or t.get('id')==name),{'name':name or '待定'})

    def render_dashboard(self,data,c):
        body = self.page_body('准备好下一回合。','队伍、赛程与俱乐部，尽在你的掌握。','CAREER OVERVIEW / 生涯总览')
        left,right = columns(body,(7,3))
        hero = self.panel(left,padx=0,pady=0,padding=22)
        pair = data.get('your_match') or {}
        m,ev = pair.get('match') or {}, pair.get('event') or {}
        label(hero,'MATCHDAY / 比赛日' if m else 'THE NEXT CHAPTER / 下一站',size=9,color=ACCENT,display=True).pack(anchor='w')
        if m:
            label(hero,ev.get('name',''),size=16,bold=True,wraplength=650,justify='left').pack(anchor='w',pady=(12,3))
            label(hero,f"{m.get('label') or '正赛'}   /   BO{m.get('best_of',3)}   /   {m.get('series') or '0–0'}",color=MUTED,size=9).pack(anchor='w')
            lineup = tk.Frame(hero,bg=PANEL)
            lineup.pack(fill='x',pady=20)
            for index,key in enumerate(('team_a','team_b')):
                if index:
                    label(lineup,'VS',size=21,color=DIM,display=True).pack(side='left',expand=True)
                team = self.team_named(data,m.get(key))
                team_box = tk.Frame(lineup,bg=PANEL)
                team_box.pack(side='left',expand=True)
                Crest(team_box,team,64).pack()
                label(team_box,team.get('name',''),size=14,bold=True).pack(pady=(8,0))
            button(hero,'进入比赛中心  →',lambda:self.go('schedule'),primary=True).pack(anchor='w',pady=(8,0))
        else:
            upcoming = [e for e in data.get('events',[]) if e.get('id') in c.get('registered',[]) and e.get('status')=='upcoming']
            next_ev = min(upcoming,key=lambda e:e['dates'][0]) if upcoming else None
            visual = TacticalArt(hero,height=165)
            visual.pack(side='right',fill='both',expand=True,padx=(18,0))
            copy = tk.Frame(hero,bg=PANEL,width=300)
            copy.pack(side='left',fill='y',pady=(22,4))
            label(copy,next_ev.get('short') or next_ev['name'] if next_ev else '从训练室，到聚光灯下。',size=18,bold=True,wraplength=320,justify='left').pack(anchor='w')
            label(copy,(next_ev['dates'][0]+'  /  已确认参赛') if next_ev else '赛前调整阵容，准备迎接下一场挑战。',size=9,color=MUTED,wraplength=280,justify='left').pack(anchor='w',pady=12)
            button(copy,'查看赛程  →' if next_ev else '查看赛事邀请  →',lambda:self.go('schedule' if next_ev else 'inbox'),primary=True).pack(anchor='w',pady=(12,0))
        tasks = self.panel(right,padx=0,pady=0,padding=18)
        section(tasks,'今日待办','行动清单')
        open_mails = [r for r in c.get('inbox',[]) if r.get('status')=='open']
        todo = [(f'{len(open_mails)} 封消息等待答复','赛事邀请与入队合同','inbox'),
                (f"{c.get('attr_points',0)} 点成长可分配",'让训练成为下一场的优势','roster'),
                ('检查下月现金流','安排开支，留足周转资金','operations')]
        for title,note,page in todo:
            block = tk.Frame(tasks,bg=PANEL)
            block.pack(fill='x',pady=9)
            button(block,'↗',lambda p=page:self.go(p),small=True).pack(side='right')
            label(block,title,size=10,bold=True).pack(anchor='w')
            label(block,note,size=8,color=MUTED).pack(anchor='w',pady=(4,0))
        stats = tk.Frame(body,bg=BG)
        stats.pack(fill='x',padx=28,pady=(12,6))
        you = c.get('you') or {}
        finance = (c.get('ops') or {}).get('finance') or {}
        club = finance.get('club') or {}
        own = self.team_named(data,c.get('team_id'))
        for i,(title,value,note,color) in enumerate((
            ('世界排名',f"#{(c.get('vrs') or {}).get('rank','—')}",'VRS  '+str((c.get('vrs') or {}).get('vrs','—')),ACCENT),
            ('个人能力',f"{float(you.get('ability') or 0):.0f}",f"近期状态  {float(you.get('form_delta') or 0):+.1f}",TEXT),
            ('俱乐部资金',money(club.get('balance')),f"下月  {signed_money(club.get('next_net'))}",GREEN),
            ('队伍心态',f"{float(own.get('mentality') or 0):.0f}",'上限 100 / 影响比赛表现',BLUE))):
            stats.columnconfigure(i,weight=1,uniform='stats')
            box = tk.Frame(stats,bg=PANEL)
            box.grid(row=0,column=i,sticky='nsew',padx=(0,12 if i<3 else 0))
            label(box,title,size=9,color=MUTED).pack(anchor='w',padx=18,pady=(16,7))
            value_label = label(box,value,size=25,color=color,bold=True,display=True)
            value_label.pack(anchor='w',padx=18)
            label(box,note,size=8,color=MUTED).pack(anchor='w',padx=18,pady=(7,16))
            if i==2:
                Tooltip(value_label,self.finance_tip(club))
        box = self.panel(body)
        head = section(box,'首发五人','STARTING FIVE')
        button(head,'管理阵容  →',lambda:self.go('roster'),small=True).pack(side='right',padx=12)
        self.player_cards(box,c.get('roster') or [],compact=True)
        lower_left,lower_right = columns(body,(7,3))
        box = self.panel(lower_left,padx=0,pady=0)
        section(box,'俱乐部动态','最近记录')
        for i,row in enumerate(reversed((c.get('log') or [])[-4:])):
            label(box,'•   '+str(row),size=9,color=MUTED,wraplength=660,justify='left').pack(anchor='w',pady=5)
        box = self.panel(lower_right,padx=0,pady=0)
        section(box,'赛季足迹')
        counts = (c.get('honours') or {}).get('counts') or {}
        label(box,f"{counts.get('titles',0)}  座冠军奖杯",size=18,bold=True).pack(anchor='w')
        label(box,f"{counts.get('mvp',0)} 次 MVP   /   {counts.get('evp',0)} 次 EVP",size=9,color=MUTED).pack(anchor='w',pady=9)

    def player_cards(self,parent,players,compact=False):
        row = tk.Frame(parent,bg=parent.cget('bg'))
        row.pack(fill='x')
        for i,p in enumerate(players):
            row.columnconfigure(i,weight=1,uniform='players')
            card = tk.Frame(row,bg=RAISED)
            card.grid(row=0,column=i,sticky='nsew',padx=(0,10 if i<len(players)-1 else 0))
            top = tk.Frame(card,bg=RAISED)
            top.pack(fill='x',padx=14,pady=(12,2))
            label(top,f'{i+1:02d}',size=9,color=DIM,display=True).pack(side='left')
            label(top,'你' if p.get('you') else ROLE_LABEL.get(p.get('role'),''),size=8,color=ACCENT if p.get('you') else MUTED).pack(side='right')
            label(card,str(p.get('name','')),size=12,bold=True,anchor='w').pack(fill='x',padx=14,pady=(4,2))
            label(card,f"{float(p.get('ability') or 0):.0f}",size=25 if compact else 36,display=True,bold=True).pack(anchor='w',padx=14)
            delta = float(p.get('form_delta') or 0)
            label(card,f"状态  {delta:+.1f}",size=8,color=GREEN if delta>=0 else RED).pack(anchor='w',padx=14,pady=(2,6))
            meter(card,p.get('ability'),ACCENT if p.get('you') else DIM).pack(fill='x',padx=14,pady=(2,14))

    def render_roster(self,data,c):
        body = self.page_body('五个人，一个目标。','查看长期能力与近期状态，安排每位选手的场上位置。','SQUAD / 我的战队')
        box = self.panel(body)
        self.player_cards(box,c.get('roster') or [])
        left,right = columns(body,(3,2))
        box = self.panel(left,padx=0)
        section(box,'个人训练成果',f"可分配 {c.get('attr_points',0)} 点")
        you = c.get('you') or {}
        for axis in c.get('axes',[]):
            val = float((you.get('stats') or {}).get(axis) or 0)
            row = tk.Frame(box,bg=PANEL)
            row.pack(fill='x',pady=8)
            label(row,(c.get('axis_labels') or {}).get(axis,axis),width=9,anchor='w',size=9).pack(side='left')
            add = button(row,'+',lambda a=axis:self.action(self.state.career.spend_point,self.state.season,a),small=True)
            add.pack(side='right')
            if not c.get('attr_points'):
                add.configure(state='disabled')
            label(row,f'{val:.0f}',size=11,display=True,width=4).pack(side='right',padx=10)
            meter(row,val).pack(side='left',fill='x',expand=True,padx=10)
        box = self.panel(right,padx=0)
        section(box,'场上分工')
        choices = {}
        for p in c.get('roster') or []:
            row = tk.Frame(box,bg=PANEL)
            row.pack(fill='x',pady=7)
            label(row,p['name'],size=10).pack(side='left')
            var = tk.StringVar(value=ROLE_LABEL.get(p.get('role'),'步枪手'))
            choices[p['name']] = var
            ttk.Combobox(row,textvariable=var,values=list(ROLE_LABEL.values()),state='readonly',width=10).pack(side='right')
        def save_roles():
            mapping = {name:next(k for k,v in ROLE_LABEL.items() if v==var.get()) for name,var in choices.items()}
            self.action(self.state.career.set_roles,self.state.season,mapping,'')
        button(box,'保存角色安排',save_roles,primary=True,small=True).pack(anchor='e',pady=(14,0))

    def render_schedule(self,data,c):
        body = self.page_body('每一场，都通向更大的舞台。','选择赛事查看赛程；轮到你的比赛时，可以亲自上场或模拟结算。','MATCH CENTER / 比赛日历')
        pair = data.get('your_match') or {}
        m,ev = pair.get('match') or {},pair.get('event') or {}
        if m:
            box = self.panel(body)
            section(box,ev.get('name','当前比赛'),'等待你的决定')
            label(box,f"{m['team_a']}   {m.get('series') or '0–0'}   {m['team_b']}",size=22,bold=True).pack(anchor='w')
            label(box,f"BO{m.get('best_of',3)}  /  {m.get('label','')}  /  下一张：{m.get('pending_map') or '等待地图选择'}",size=9,color=MUTED).pack(anchor='w',pady=10)
            row = tk.Frame(box,bg=PANEL)
            row.pack(fill='x')
            side = tk.StringVar(value='CT / 防守方')
            ttk.Combobox(row,textvariable=side,values=('CT / 防守方','T / 进攻方'),state='readonly',width=14).pack(side='left',padx=(0,10))
            button(row,'亲自上场  →',lambda:self.background(lambda:self.state.season.launch_your_map(m['id'],'ct' if side.get().startswith('CT') else 't')),primary=True).pack(side='left')
            button(row,'读取比赛结果',lambda:self.background(lambda:self.state.season.commit_cs2_map(m['id'],None)),small=True).pack(side='left',padx=10)
            def simulate():
                if messagebox.askyesno('模拟本场比赛','将按当前阵容结算剩余地图并保存赛果。继续吗？',parent=self):
                    self.background(lambda:self.state.season.skip_your_series(m['id']))
            button(row,'模拟本场',simulate,small=True).pack(side='right')
        box = self.panel(body)
        section(box,'赛季日历','双击赛事查看对阵')
        tree = self.table(box,('date','name','region','prize','status'),('开始日期','赛事','赛区','总奖金','状态'),(115,380,80,120,100),height=11)
        events = {e['id']:e for e in data.get('events',[])}
        for ev in events.values():
            tree.insert('','end',iid=ev['id'],values=((ev.get('dates') or [''])[0],ev['name'],REGIONS.get(ev.get('region'),ev.get('region')),money(ev.get('prize')),STATUS.get(ev.get('status'),ev.get('status'))),tags=('you',) if ev['id'] in c.get('registered',[]) else ())
        details = tk.Frame(box,bg=PANEL)
        details.pack(fill='x')
        def selected(_=None):
            if not tree.selection():
                return
            ev = events[tree.selection()[0]]
            for child in details.winfo_children(): child.destroy()
            label(details,ev['name'],size=13,bold=True).pack(anchor='w',pady=(14,5))
            if not ev.get('matches'):
                label(details,'对阵尚未生成。参赛邀请请在收件箱确认。',color=MUTED,size=9).pack(anchor='w')
            for match in ev.get('matches',[]):
                text = f"{match.get('label') or match.get('stage','')}  ·  {match.get('team_a')}   {match.get('series') or 'VS'}   {match.get('team_b')}"
                label(details,text,size=9,color=TEXT if match.get('yours') else MUTED).pack(anchor='w',pady=4)
        tree.bind('<<TreeviewSelect>>',selected)

    def render_world(self,data,c):
        body = self.page_body('世界赛场。','追踪队伍的排名，看看谁正在统治这个赛季。','WORLD / 全球排名')
        box = self.panel(body)
        section(box,'VRS 战队排名','点击表头排序')
        tree = self.table(box,('rank','team','region','vrs'),('#','战队','地区','VRS 积分'),(70,330,150,150),height=12)
        for row in data.get('vrs',[]):
            team = self.team_named(data,row.get('id'))
            tree.insert('','end',values=(row.get('rank'),row.get('name'),REGIONS.get(team.get('region'),''),row.get('vrs')),tags=('you',) if row.get('id')==c.get('team_id') else ())
        box = self.panel(body)
        section(box,'赛季选手榜','CAREER RATING')
        tree = self.table(box,('name','team','rating','kpr','adr'),('选手','队伍','Rating','KPR','ADR'),(180,220,100,100,100),height=6)
        for row in data.get('ratings',[]):
            tree.insert('','end',values=(row.get('player'),row.get('team'),row.get('rating'),row.get('kpr'),row.get('adr','—')))

    @staticmethod
    def finance_tip(row):
        return '下月预计收支\n'+'\n'.join(f"{r.get('label')}   {signed_money(r.get('amount'))}" for r in row.get('lines',[]))+'\n\n未计入尚未获得的奖金和交易。'

    def render_operations(self,data,c):
        body = self.page_body('让俱乐部，走得更远。','赞助、工资和奖金自动结算。将鼠标停在余额上，查看下月收支来源。','CLUB FINANCE / 俱乐部经营')
        finance = (c.get('ops') or {}).get('finance') or {}
        left,right = columns(body,(1,1))
        for parent,key,title in ((left,'club','俱乐部账户'),(right,'pocket','个人账户')):
            row = finance.get(key) or {}
            box = self.panel(parent,padx=0,pady=0,padding=22)
            section(box,title,'CLUB' if key=='club' else 'PERSONAL')
            bal = label(box,money(row.get('balance')),size=36,bold=True,display=True)
            bal.pack(anchor='w')
            Tooltip(bal,self.finance_tip(row))
            net = row.get('next_net') or 0
            label(box,f"{'↑' if net>=0 else '↓'}  {signed_money(net)} / 下月",size=12,color=GREEN if net>=0 else RED).pack(anchor='w',pady=(8,4))
            label(box,f"预计结余  {money(row.get('next_balance'))}",size=9,color=MUTED).pack(anchor='w')
            tk.Frame(box,bg=LINE,height=1).pack(fill='x',pady=20)
            for line in row.get('lines',[]):
                r = tk.Frame(box,bg=PANEL)
                r.pack(fill='x',pady=5)
                label(r,line.get('label',''),size=9,color=MUTED).pack(side='left')
                amount = line.get('amount') or 0
                label(r,signed_money(amount),size=11,display=True,color=GREEN if amount>=0 else TEXT).pack(side='right')
        box = self.panel(body)
        section(box,'资金安排')
        row = tk.Frame(box,bg=PANEL)
        row.pack(fill='x')
        amount = tk.StringVar(value='10000')
        entry = tk.Entry(row,textvariable=amount,width=16,bg=RAISED,fg=TEXT,insertbackground=TEXT,relief='flat')
        entry.pack(side='left',ipady=9,padx=(0,14))
        def perform(method):
            try:
                value = int(amount.get().replace(',',''))
                if value<=0: raise ValueError()
            except ValueError:
                messagebox.showerror('金额不正确','请输入大于零的整数金额。',parent=self)
                return
            self.action(method,self.state.season,value)
        button(row,'注资俱乐部',lambda:perform(self.state.career.donate),primary=True,small=True).pack(side='left')
        button(row,'申请个人借款',lambda:perform(self.state.career.borrow),small=True).pack(side='left',padx=8)
        button(row,'偿还个人借款',lambda:perform(self.state.career.repay),small=True).pack(side='left')
        label(box,'注资从个人账户转入俱乐部。借款进入个人账户，按现有规则计息。',size=8,color=MUTED).pack(anchor='w',pady=(12,0))
        box = self.panel(body)
        section(box,'最近流水','已实际入账')
        tree = self.table(box,('date','scope','label','amount','balance'),('日期','账户','事项','金额','入账后余额'),(110,80,340,110,130),height=7)
        for row in reversed(self.state.career.cashflow[-40:]):
            tree.insert('','end',values=(row.get('date'),{'club':'俱乐部','pocket':'个人'}.get(row.get('scope'),''),row.get('label'),signed_money(row.get('amount')),money(row.get('balance'))))

    def render_inbox(self,data,c):
        body = self.page_body('每一封信，都可能是转机。','处理邀请与合同，为下一站作出决定。','INBOX / 收件箱')
        box = self.panel(body)
        head = section(box,'收件箱',f"{c.get('unread',0)} 封未读")
        button(head,'全部已读',lambda:self.action(self.state.career.mark_read,''),small=True).pack(side='right',padx=12)
        split = tk.Frame(box,bg=PANEL)
        split.pack(fill='both',expand=True)
        split.columnconfigure(0,weight=2,uniform='mail')
        split.columnconfigure(1,weight=3,uniform='mail')
        listing = tk.Frame(split,bg=PANEL)
        listing.grid(row=0,column=0,sticky='nsew',padx=(0,20))
        reader = tk.Frame(split,bg=PANEL)
        reader.grid(row=0,column=1,sticky='nsew')
        tree = self.table(listing,('title','status'),('主题','状态'),(260,75),height=12)
        mails = {str(r['id']):r for r in reversed(c.get('inbox') or [])}
        for mid,row in mails.items():
            tree.insert('','end',iid=mid,values=(('● ' if not row.get('read') else '')+(row.get('subject') or row.get('title') or '邮件'),STATUS.get(row.get('status'),'')))
        def read(_=None):
            for child in reader.winfo_children(): child.destroy()
            if not tree.selection():
                label(reader,'选择一封邮件阅读。',color=MUTED).pack(anchor='w',pady=25)
                return
            mid = tree.selection()[0]
            row = mails[mid]
            label(reader,row.get('subject') or row.get('title') or '邮件',size=16,bold=True,wraplength=470,justify='left').pack(anchor='w',pady=(16,8))
            label(reader,str(row.get('date') or '')+'  ·  '+str(row.get('sender') or row.get('from') or '俱乐部办公室'),size=9,color=MUTED,wraplength=450,justify='left').pack(anchor='w')
            text = tk.Text(reader,height=13,bg=PANEL,fg=TEXT,relief='flat',wrap='word',font=(FONT,10),spacing3=8)
            text.pack(fill='both',expand=True,pady=18)
            raw = row.get('text') or row.get('body') or ''
            text.insert('1.0','\n'.join(raw) if isinstance(raw,list) else str(raw))
            text.configure(state='disabled')
            actions = tk.Frame(reader,bg=PANEL)
            actions.pack(fill='x')
            if row.get('status')=='open' and row.get('kind') in ('invite','contract','whisper'):
                button(actions,'接受',lambda:self.action(self.state.career.accept_invite,self.state.season,mid),primary=True).pack(side='left')
                button(actions,'婉拒',lambda:self.action(self.state.career.decline_invite,self.state.season,mid)).pack(side='left',padx=10)
            button(actions,'标为已读',lambda:self.action(self.state.career.mark_read,mid),small=True).pack(side='right')
        tree.bind('<<TreeviewSelect>>',read)
        if mails:
            tree.selection_set(next(iter(mails)))
        else:
            read()

    def render_market(self,data,c):
        body = self.page_body('找到队伍缺少的那一块。','按位置和能力筛选自由选手，签约费用由俱乐部承担。','TRANSFER / 转会中心')
        box = self.panel(body)
        row = section(box,'球探名单',f"可用资金 {money(c.get('money'))}")
        query = tk.StringVar()
        role = tk.StringVar(value='全部位置')
        tk.Entry(row,textvariable=query,bg=RAISED,fg=TEXT,insertbackground=TEXT,relief='flat',width=18).pack(side='left',padx=18,ipady=7)
        ttk.Combobox(row,textvariable=role,values=['全部位置']+list(ROLE_LABEL.values()),state='readonly',width=11).pack(side='left')
        tree = self.table(box,('name','role','ability','age','fee','chance'),('选手','位置','能力','年龄','签约费用','意愿概率'),(200,110,80,70,140,100),height=12)
        market = c.get('market') or []
        def fill(*_):
            tree.delete(*tree.get_children())
            for index,p in enumerate(market):
                if query.get().casefold() not in p['name'].casefold(): continue
                if role.get()!='全部位置' and ROLE_LABEL.get(p.get('role'))!=role.get(): continue
                tree.insert('','end',iid=str(index),values=(p['name'],ROLE_LABEL.get(p.get('role')),f"{p['ability']:.0f}",p.get('age'),money(p.get('fee')),f"{(p.get('chance') or 0)*100:.0f}%"))
        query.trace_add('write',fill)
        role.trace_add('write',fill)
        fill()
        def buy():
            if not tree.selection(): return
            p = market[int(tree.selection()[0])]
            if messagebox.askyesno('确认报价',f"向 {p['name']} 报价 {money(p['fee'])}？成功后会按当前签约规则调整阵容。",parent=self):
                self.action(self.state.career.buy,self.state.season,p['name'])
        button(box,'向所选选手报价  →',buy,primary=True).pack(anchor='e',pady=8)

    def render_training(self,data,c):
        body = self.page_body('把今天的训练，变成明天的优势。','完成日常训练，或与另一支队伍进行一场 CS2 训练赛。','TRAINING / 训练中心')
        left,right = columns(body,(1,1))
        box = self.panel(left,padx=0)
        section(box,'日常训练')
        TacticalArt(box,height=175).pack(fill='x')
        label(box,'个人与团队合练',size=17,bold=True).pack(anchor='w',pady=12)
        label(box,'训练收益与当天训练次数由生涯规则决定。',size=9,color=MUTED).pack(anchor='w')
        button(box,'完成本次训练',lambda:self.action(self.state.career.finish_training,self.state.season),primary=True).pack(anchor='w',pady=(18,0))
        box = self.panel(right,padx=0)
        section(box,'CS2 训练赛')
        teams = [t for t in data.get('teams',[]) if t['id']!=c.get('team_id')]
        opp = tk.StringVar(value=teams[0]['name'] if teams else '')
        mp = tk.StringVar(value='dust2')
        side = tk.StringVar(value='CT / 防守方')
        for title,var,values in (('训练对手',opp,[t['name'] for t in teams]),('比赛地图',mp,MAPS),('起始阵营',side,['CT / 防守方','T / 进攻方'])):
            label(box,title,size=9,color=MUTED).pack(anchor='w',pady=(8,6))
            ttk.Combobox(box,textvariable=var,values=values,state='readonly').pack(fill='x')
        def launch():
            if c.get('over') or c.get('unsigned'):
                messagebox.showinfo('暂时无法参赛','需要有效生涯和一支已签约的队伍。',parent=self)
                return
            team = self.state.career.my_team(self.state.season.teams)
            opponent = next(t for t in self.state.season.teams if t['name']==opp.get())
            self.background(lambda:cs2.start_match(team,opponent,self.state.career.player_name,'de_'+mp.get(),'ct' if side.get().startswith('CT') else 't',self.state.season.teams,self.state.career,purpose='training'))
        button(box,'进入 CS2 训练赛  →',launch,primary=True).pack(anchor='w',pady=(22,6))
        box = self.panel(body)
        label(box,'首次进入 CS2？先在设置中填写游戏路径并安装比赛插件。',size=10,color=MUTED).pack(side='left')
        button(box,'打开设置',lambda:self.go('settings'),small=True).pack(side='right')

    def render_skins(self,data,c):
        body = self.page_body('属于你的赛场风格。','收藏饰品，为 CT 与 T 分别配置装备。饰品消费从个人账户支付。','COLLECTION / 饰品收藏')
        shop = c.get('skins') or {}
        box = self.panel(body)
        section(box,'我的库存',f"个人余额 {money(c.get('pocket'))}")
        tree = self.table(box,('name','slot','wear','sell','equip'),('饰品','武器','磨损','出售到手','装备'),(350,90,90,120,110),height=5)
        for p in shop.get('inventory',[]):
            tags = []
            for side in ('ct','t'):
                if p['id'] in (shop.get('equipped_'+side) or {}).values(): tags.append(side.upper())
            tree.insert('','end',iid=p['id'],values=(p['name'],p.get('slot'),p.get('wear'),money(p.get('sell')),' / '.join(tags) or '未装备'))
        row = tk.Frame(box,bg=PANEL)
        row.pack(fill='x',pady=8)
        def selected(method,*args):
            if tree.selection(): self.action(method,tree.selection()[0],*args)
        for side in ('ct','t'):
            button(row,f'装备到 {side.upper()}',lambda s=side:selected(self.state.career.equip_skin,s,False),primary=side=='ct',small=True).pack(side='left',padx=(0,8))
        def unequip():
            if not tree.selection(): return
            inv_id = tree.selection()[0]
            def both():
                for side in ('ct','t'):
                    self.state.career.equip_skin(inv_id,side,True)
                return '所选饰品已从两边卸下。'
            self.action(both)
        button(row,'卸下装备',unequip,small=True).pack(side='left')
        def sell():
            if tree.selection() and messagebox.askyesno('出售饰品','按当前市场价格出售所选饰品？',parent=self):
                selected(self.state.career.sell_skin)
        button(row,'出售所选',sell,small=True).pack(side='right')
        box = self.panel(body)
        section(box,'饰品市场','双击表头可排序')
        market = self.table(box,('name','slot','rarity','buy'),('饰品','武器','稀有度','购买价格'),(410,100,120,130),height=7)
        for p in shop.get('market',[]):
            market.insert('','end',iid=p['id'],values=(p['name'],p.get('slot'),p.get('rarity'),money(p.get('spot',p.get('buy')))))
        def buy():
            if market.selection(): self.action(self.state.career.buy_skin,market.selection()[0])
        button(box,'购买所选饰品',buy,primary=True,small=True).pack(anchor='e')
        box = self.panel(body)
        section(box,'武器箱')
        pending = shop.get('pending')
        if pending:
            label(box,'本次获得：'+str(pending.get('name')),size=13,color=ACCENT).pack(anchor='w',pady=8)
            button(box,'收入库存',lambda:self.action(self.state.career.keep_drop),primary=True,small=True).pack(anchor='w')
            button(box,'直接出售',lambda:self.action(self.state.career.cash_drop),small=True).pack(anchor='w',pady=8)
        else:
            for p in shop.get('cases',[]):
                row = tk.Frame(box,bg=PANEL)
                row.pack(fill='x',pady=5)
                label(row,p['name'],size=10).pack(side='left')
                button(row,'开启  '+money((p.get('price') or 0)+(p.get('key') or 0)),lambda pid=p['id']:self.action(self.state.career.buy_case,pid),small=True).pack(side='right')

    def render_extensions(self,data,c):
        body = self.page_body('让这个世界，有你的版本。','安装剧情、赛事、皮肤、战队或年代内容，为生涯增加新的可能。','WORKSHOP / 扩展工坊')
        registry = get_registry()
        left,right = columns(body,(3,2))
        box = self.panel(left,padx=0)
        label(box,'扩展你的生涯',size=22,bold=True).pack(anchor='w')
        label(box,'从一个剧情开始，也可以重建整个年代。\n复制模板，改好内容，放进扩展目录。',size=10,color=MUTED,justify='left').pack(anchor='w',pady=14)
        row = tk.Frame(box,bg=PANEL)
        row.pack(fill='x',pady=8)
        button(row,'打开扩展目录',lambda:os.startfile(extension_root()),primary=True,small=True).pack(side='left')
        button(row,'重新加载',self.reload_packs,small=True).pack(side='left',padx=8)
        box = self.panel(right,padx=0)
        label(box,'作者工具箱',size=13,bold=True).pack(anchor='w')
        for title in ('剧情包 · 讲一个新故事','赛事包 · 创办你的联赛','皮肤 / 战队 / 年代包'):
            label(box,title,size=10,color=MUTED).pack(anchor='w',pady=7)
        button(box,'浏览制作模板  →',lambda:os.startfile(extension_root()/'_templates'),small=True).pack(anchor='w',pady=8)
        box = self.panel(body)
        section(box,'已安装扩展',f'{registry.public()["ready"]} 个已启用')
        if not registry.packs:
            label(box,'还没有安装扩展。内置内容已经可以直接开始生涯。',color=MUTED).pack(anchor='w',pady=28)
        for p in registry.packs:
            label(box,f'{p.name}  /  {p.version}',size=12,bold=True).pack(anchor='w',pady=(10,4))
            label(box,{'ready':'已启用','disabled':'已停用','rejected':'未加载'}.get(p.status,p.status)+'   '+', '.join(p.kinds),size=9,color=GREEN if p.status=='ready' else RED).pack(anchor='w')
            if p.errors: label(box,'；'.join(p.errors),size=9,color=RED,wraplength=900,justify='left').pack(anchor='w')
        label(body,'剧情与皮肤可重新加载；更换赛事或世界内容后，请重启并新建生涯。',size=9,color=DIM).pack(anchor='w',padx=28,pady=18)

    def reload_packs(self):
        if self.busy: return
        reload_registry()
        story.reload_stories()
        skins.reload_catalog()
        season_module.reload_calendar()
        era_module.reload_era_extensions()
        self.refresh('扩展内容已重新加载。')

    def render_settings(self,data,c):
        body = self.page_body('按你的方式，进入赛场。','配置 CS2、难度和游戏内换肤。','PREFERENCES / 设置')
        from ..cs2.launch import settings
        cfg = settings()
        box = self.panel(body)
        section(box,'游戏与插件路径')
        fields = {}
        for key,title,is_file in (('steam_exe','Steam 程序',True),('csgo_path','CS2 / game / csgo 目录',False),('mod_source_path','人机增强发行包目录',False),('skins_source_path','换肤插件目录（留空使用内置）',False)):
            label(box,title,size=9,color=MUTED).pack(anchor='w',pady=(8,5))
            row = tk.Frame(box,bg=PANEL)
            row.pack(fill='x')
            var = tk.StringVar(value=cfg.get(key) or '')
            fields[key] = var
            tk.Entry(row,textvariable=var,bg=RAISED,fg=TEXT,insertbackground=ACCENT,relief='flat').pack(side='left',fill='x',expand=True,ipady=9)
            def browse(v=var,f=is_file):
                path = filedialog.askopenfilename(parent=self,filetypes=[('应用程序','*.exe')]) if f else filedialog.askdirectory(parent=self)
                if path: v.set(path)
            button(row,'浏览',browse,small=True).pack(side='right',padx=(8,0))
        row = tk.Frame(box,bg=PANEL)
        row.pack(fill='x',pady=16)
        label(row,'人机难度',size=10).pack(side='left',padx=(0,16))
        difficulty = tk.StringVar(value=cfg.get('difficulty','Medium'))
        from ..cs2.launch import DIFFICULTIES
        combo = ttk.Combobox(row,textvariable=difficulty,values=list(DIFFICULTIES),state='readonly',width=12)
        combo.pack(side='left')
        label(row,'完全退出 CS2 后才能修改。',size=9,color=MUTED).pack(side='left',padx=16)
        # Read-only process check is kept out of the render path; saving also
        # enforces the authoritative runtime guard in cs2.save_settings.
        self.after(10,lambda:self._lock_live_difficulty(combo))
        def save():
            patch = {k:v.get().strip() for k,v in fields.items()}
            patch['difficulty'] = difficulty.get()
            self.background(lambda:cs2.save_settings(patch))
        button(row,'保存设置',save,primary=True,small=True).pack(side='right')
        row = tk.Frame(box,bg=PANEL)
        row.pack(fill='x')
        button(row,'安装比赛插件',lambda:self.background(cs2.install_mod),small=True).pack(side='left')
        button(row,'安装换肤插件',lambda:self.background(cs2.install_skins_mod),small=True).pack(side='left',padx=10)
        button(row,'更新换肤签名',lambda:self.background(cs2.update_skins_gamedata),small=True).pack(side='left')
        box = self.panel(body)
        section(box,'游戏内换肤')
        enabled = tk.BooleanVar(value=c.get('real_skins',False))
        sid = tk.StringVar(value=c.get('steam_id',''))
        tk.Checkbutton(box,text='将生涯装备带入 CS2',variable=enabled,bg=PANEL,fg=TEXT,selectcolor=RAISED,activebackground=PANEL,activeforeground=TEXT).pack(anchor='w')
        row = tk.Frame(box,bg=PANEL)
        row.pack(fill='x',pady=10)
        label(row,'SteamID64',size=9,color=MUTED).pack(side='left',padx=(0,15))
        tk.Entry(row,textvariable=sid,bg=RAISED,fg=TEXT,insertbackground=TEXT,relief='flat').pack(side='left',fill='x',expand=True,ipady=9)
        button(row,'保存',lambda:self.action(self.state.career.set_skin_pref,enabled.get(),sid.get()),small=True).pack(side='right',padx=10)
        box = self.panel(body)
        section(box,'生涯与存档')
        button(box,'打开存档目录',lambda:os.startfile(save_root()),small=True).pack(side='left')
        button(box,'建立新生涯',self.show_setup,small=True).pack(side='left',padx=10)

    def _lock_live_difficulty(self,combo):
        if not combo.winfo_exists(): return
        from ..cs2.launch import cs2_is_live
        if cs2_is_live() and combo.winfo_exists(): combo.configure(state='disabled')
