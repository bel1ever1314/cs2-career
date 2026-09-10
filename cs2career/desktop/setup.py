"""Career creation: full-page origin selection and a persistent draft form."""
import tkinter as tk
from tkinter import ttk
from ..career.origins import ORIGINS
from ..world import ERA_META, ROLE_LABEL, build_teams, apply_roles, slug, roster_names
from .theme import *
from .widgets import label, button, ScrollPage, TacticalArt, meter


class SetupPage(ScrollPage):
    def __init__(self,parent,app):
        super().__init__(parent)
        self.app = app
        self.mode = tk.StringVar(value='create')
        self.origin = tk.StringVar(value='academy')
        self.era = tk.StringVar(value='2026')
        self.role = tk.StringVar(value=ROLE_LABEL['rifle'])
        self.name = tk.StringVar(value='Player')
        self.org = tk.StringVar(value='New Era')
        self.region = tk.StringVar(value='亚洲')
        self.team = tk.StringVar()
        self.player = tk.StringVar()
        self.teams = []
        label(self.body,'NEW CAREER / 新的篇章',size=9,color=ACCENT,display=True).pack(anchor='w',padx=30,pady=(28,6))
        title = tk.Frame(self.body,bg=BG)
        title.pack(fill='x',padx=30)
        label(title,'从哪里，走向世界。',size=28,bold=True).pack(side='left')
        if app.state.career.exists:
            button(title,'返回当前生涯',app.refresh,small=True).pack(side='right')
        label(self.body,'选择你的起点。随后建立阵容，接受邀请，让你的名字出现在赛场上。',color=MUTED,size=10).pack(anchor='w',padx=30,pady=(7,18))
        modes = tk.Frame(self.body,bg=BG)
        modes.pack(fill='x',padx=30,pady=(0,16))
        self.mode_buttons = {}
        for key,title in (('create','自建俱乐部'),('join','接管职业选手')):
            b = button(modes,title,lambda k=key:self.set_mode(k),primary=key=='create',small=True)
            b.pack(side='left',padx=(0,8))
            self.mode_buttons[key] = b
        self.content = tk.Frame(self.body,bg=BG)
        self.content.pack(fill='x',padx=30)
        self.error = label(self.body,'',color=RED,wraplength=900,justify='left')
        self.error.pack(anchor='w',padx=30,pady=(8,0))
        footer = tk.Frame(self,bg=PANEL)
        footer.pack(side='bottom',fill='x',before=self.canvas)
        label(footer,'已有生涯会在开始前备份。',size=9,color=MUTED).pack(side='left',padx=30,pady=18)
        button(footer,'建立生涯，开始征程  →',self.submit,primary=True).pack(side='right',padx=30,pady=14)
        self.draw()

    def set_mode(self,key):
        self.mode.set(key)
        for k,b in self.mode_buttons.items():
            b.configure(bg=ACCENT if k==key else RAISED,fg=BG if k==key else TEXT)
        self.draw()

    def draw(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.error.configure(text='')
        if self.mode.get()=='create':
            cards = tk.Frame(self.content,bg=BG)
            cards.pack(fill='x')
            for i,(key,cfg) in enumerate(ORIGINS.items()):
                cards.columnconfigure(i,weight=1,uniform='origin')
                active = key==self.origin.get()
                box = tk.Frame(cards,bg=PANEL,highlightthickness=2,highlightbackground=ACCENT if active else LINE)
                box.grid(row=0,column=i,sticky='nsew',padx=(0,12 if i<2 else 0))
                head = tk.Frame(box,bg=PANEL)
                head.pack(fill='x',padx=18,pady=(16,8))
                label(head,f'0{i+1}',size=19,color=ACCENT if active else DIM,display=True).pack(side='left')
                label(head,'已选择' if active else '生涯出身',size=8,color=ACCENT if active else DIM).pack(side='right')
                label(box,cfg['name'],size=18,bold=True).pack(anchor='w',padx=18)
                label(box,cfg['tagline'],size=9,color=MUTED).pack(anchor='w',padx=18,pady=(5,14))
                line = tk.Frame(box,bg=PANEL)
                line.pack(fill='x',padx=18)
                label(line,str(int(cfg['player_ability'])),size=40,display=True,bold=True).pack(side='left')
                label(line,'个人能力\n开局总评',size=9,color=MUTED,justify='left').pack(side='left',padx=12)
                meter(box,cfg['player_ability'],ACCENT if active else DIM).pack(fill='x',padx=18,pady=(7,12))
                for text in (f"俱乐部资金   {money(cfg['club_money'])}",f"队友区间       {cfg['mate_min']:.0f} – {cfg['mate_max']:.0f}",f"自由属性点   {cfg['attr_points']} 点"):
                    label(box,text,size=9,color=MUTED).pack(anchor='w',padx=18,pady=3)
                button(box,'✓  从这里出发' if active else '选择这个起点',lambda k=key:self.select(k),primary=active,small=True).pack(fill='x',padx=18,pady=(15,18))
        form = tk.Frame(self.content,bg=PANEL,highlightbackground=LINE,highlightthickness=1)
        form.pack(fill='x',pady=18)
        for i in range(3):
            form.columnconfigure(i,weight=1,uniform='form')
        self.field(form,'开始年代',self.era,list(ERA_META),0,0,lambda:self.change_era())
        self.field(form,'场上角色',self.role,list(ROLE_LABEL.values()),0,1)
        if self.mode.get()=='create':
            self.field(form,'所在赛区',self.region,list(REGIONS.values()),0,2)
            self.field(form,'你的选手 ID',self.name,None,1,0)
            self.field(form,'俱乐部名称',self.org,None,1,1)
            summary = tk.Frame(form,bg=PANEL)
            summary.grid(row=1,column=2,sticky='nsew',padx=18,pady=16)
            label(summary,'开局建议',size=9,color=MUTED).pack(anchor='w')
            label(summary,{'street':'稳住现金，寻找第一场胜利。','academy':'磨合阵容，从地区赛事起步。','prodigy':'用个人表现，带动整支队伍。'}[self.origin.get()],size=9,color=ACCENT,wraplength=250,justify='left').pack(anchor='w',pady=9)
        else:
            self.teams = build_teams(self.era.get(),ERA_META[self.era.get()]['year'])
            apply_roles(self.teams,self.era.get())
            names = [t['name'] for t in self.teams]
            if self.team.get() not in names:
                self.team.set(names[0])
            self.field(form,'职业战队',self.team,names,1,0,lambda:self.draw())
            team = next(t for t in self.teams if t['name']==self.team.get())
            names = [p['name'] for p in team['players']]
            if self.player.get() not in names:
                self.player.set(names[0])
            self.field(form,'接管选手',self.player,names,1,1)

    def field(self,parent,title,var,values,row,col,on_change=None):
        frame = tk.Frame(parent,bg=PANEL)
        frame.grid(row=row,column=col,sticky='nsew',padx=18,pady=16)
        label(frame,title,size=9,color=MUTED).pack(anchor='w',pady=(0,8))
        if values:
            entry = ttk.Combobox(frame,textvariable=var,values=values,state='readonly',width=15)
            if on_change:
                entry.bind('<<ComboboxSelected>>',lambda _:on_change())
        else:
            entry = tk.Entry(frame,textvariable=var,bg=RAISED,fg=TEXT,insertbackground=ACCENT,
                             relief='flat',highlightthickness=1,highlightbackground=LINE,highlightcolor=ACCENT)
        entry.pack(fill='x',ipady=4)

    def select(self,key):
        self.origin.set(key)
        self.draw()

    def change_era(self):
        if self.mode.get()=='join':
            self.team.set('')
            self.draw()

    def submit(self):
        role = next(k for k,v in ROLE_LABEL.items() if v==self.role.get())
        payload = {'era':self.era.get(),'mode':self.mode.get(),'role':role}
        if self.mode.get()=='create':
            name,org = self.name.get().strip(),self.org.get().strip()
            teams = build_teams(self.era.get(),ERA_META[self.era.get()]['year'])
            if not name or not org or len(name)>32 or len(org)>40:
                self.error.configure(text='请填写选手 ID（最多32字）和俱乐部名称（最多40字）。')
                return
            if name.casefold() in {n.casefold() for n in roster_names(teams)} or slug(org) in {t['id'] for t in teams}:
                self.error.configure(text='这个选手或俱乐部已存在，请使用一个新的名称。')
                return
            payload.update(name=name,org=org,origin=self.origin.get(),region=next(k for k,v in REGIONS.items() if v==self.region.get()))
        else:
            payload.update(team_id=next(t['id'] for t in self.teams if t['name']==self.team.get()),replace=self.player.get())
        self.app.create_career(payload)
