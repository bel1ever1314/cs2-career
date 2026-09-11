"""Native career desk. Window/commands here; composition in pages and setup."""
from __future__ import annotations
import queue
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from ..application import ApplicationState
from ..paths import save_root
from .theme import *
from .widgets import label, button, ScrollPage, Crest
from .pages import Pages
from .setup import SetupPage


class DesktopApp(Pages, tk.Tk):
    NAV = (("dashboard","生涯总览","⌂"),("roster","我的战队","▦"),
           ("schedule","比赛日历","▤"),("world","世界赛场","◎"),
           ("operations","俱乐部经营","▥"),("inbox","收件箱","✉"),
           ("market","转会中心","⇄"),("training","训练中心","⊕"),
           ("skins","饰品收藏","◇"),("extensions","扩展工坊","⊞"),
           ("settings","设置","⚙"))

    def __init__(self, state=None, *, testing=False):
        super().__init__()
        self.testing = testing
        self.callback_errors = []
        self.state = state or ApplicationState()
        self.page, self.data, self.busy = "dashboard", {}, False
        self._story_showing = False
        self.messages = queue.Queue()
        self.title("CS2 Career · 生涯工作室")
        self.configure(bg=BG)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1440,sw-70), min(920,sh-100)
        self.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2-20)}")
        self.minsize(1060,680)
        self.protocol("WM_DELETE_WINDOW",self.close)
        self._styles()
        self._shell()
        self.bind("<Control-s>",lambda _:self.action(self.state.persist))
        self.bind("<F5>",lambda _:self.refresh())
        self._queue_timer = self.after(90,self._drain)
        self._bridge = None
        if not testing:
            from .skin_api import start_skin_api
            self._bridge = start_skin_api(lambda:self.state.career)
        if self.state.career.exists:
            self.refresh()
        else:
            self.show_setup()

    def _styles(self):
        self.option_add("*Font",(FONT,10))
        self.option_add("*TCombobox*Listbox.background",RAISED)
        self.option_add("*TCombobox*Listbox.foreground",TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground",LINE)
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=TEXT,
                    borderwidth=0,rowheight=40,font=(FONT,10))
        s.configure("Treeview.Heading",background=RAISED,foreground=MUTED,
                    relief="flat",padding=(10,10),font=(FONT,9))
        s.map("Treeview",background=[("selected","#3b332c")],foreground=[("selected",TEXT)])
        s.configure("TCombobox",fieldbackground=RAISED,background=RAISED,foreground=TEXT,
                    arrowcolor=MUTED,bordercolor=LINE,padding=8)
        s.map("TCombobox",fieldbackground=[("readonly",RAISED)],foreground=[("readonly",TEXT)])
        for orient in ("Vertical","Horizontal"):
            s.configure(f"{orient}.TScrollbar",background=LINE,troughcolor=BG,borderwidth=0,
                        arrowcolor=MUTED,arrowsize=11)

    def _shell(self):
        self.sidebar = tk.Frame(self,bg=SIDEBAR,width=202)
        self.sidebar.pack(side="left",fill="y")
        self.sidebar.pack_propagate(False)
        brand = tk.Frame(self.sidebar,bg=SIDEBAR)
        brand.pack(fill="x",padx=22,pady=(16,10))
        label(brand,"C /",size=20,color=ACCENT,bold=True,display=True).pack(anchor="w")
        label(brand,"CS2 CAREER",size=14,bold=True,display=True).pack(anchor="w",pady=(5,2))
        label(brand,"你的故事，由下一回合开始",size=8,color=DIM).pack(anchor="w")
        self.nav_buttons = {}
        for i,(key,title,icon) in enumerate(self.NAV):
            if i in (0,4,9):
                label(self.sidebar,{0:"生涯",4:"俱乐部",9:"更多"}[i],size=8,color=DIM).pack(anchor="w",padx=24,pady=(8,4))
            btn = tk.Button(self.sidebar,text=f"{icon}    {title}",anchor="w",bg=SIDEBAR,fg=MUTED,
                            relief="flat",bd=0,font=(FONT,10),padx=14,pady=6,
                            activebackground=RAISED,activeforeground=TEXT,cursor="hand2",
                            command=lambda k=key:self.go(k))
            btn.pack(fill="x",padx=12,pady=1)
            self.nav_buttons[key] = btn
        footer = tk.Frame(self.sidebar,bg=SIDEBAR)
        footer.pack(side="bottom",fill="x",padx=22,pady=12)
        label(footer,"●  本地生涯",size=9,color=GREEN).pack(anchor="w")
        label(footer,"DESKTOP / 1.5.0",size=8,color=DIM,display=True).pack(anchor="w",pady=(5,0))
        self.right = tk.Frame(self,bg=BG)
        self.right.pack(side="left",fill="both",expand=True)
        self.topbar = tk.Frame(self.right,bg=BG,height=74)
        self.topbar.pack(fill="x")
        self.topbar.pack_propagate(False)
        self.badge = tk.Frame(self.topbar,bg=BG)
        self.badge.pack(side='left',padx=(24,0))
        self.identity = label(self.topbar,"生涯工作室",size=11,bold=True)
        self.identity.pack(side="left",padx=12)
        self.advance = button(self.topbar,"继续生涯  →",self.next_stage,primary=True)
        self.advance.pack(side="right",padx=(10,28),pady=16)
        self.skip = button(self.topbar,"下一赛事",self.skip_stage,small=True)
        self.skip.pack(side="right",pady=16)
        self.date_label = label(self.topbar,"",size=11,color=MUTED,display=True)
        self.date_label.pack(side="right",padx=18)
        tk.Frame(self.right,bg=LINE,height=1).pack(fill="x")
        self.status = label(self.right,"就绪   ·   Ctrl+S 保存  /  F5 刷新",size=8,color=DIM,anchor="w",padx=28,pady=8)
        self.status.pack(side="bottom",fill="x")
        self.page_host = tk.Frame(self.right,bg=BG)
        self.page_host.pack(fill="both",expand=True)

    def clear_page(self):
        for widget in self.page_host.winfo_children():
            widget.destroy()

    def go(self,page):
        if self.busy or not self.state.career.exists:
            return
        self.page = page
        self.refresh()

    def refresh(self,msg=""):
        if self.busy or not self.state.career.exists:
            return
        payload = self.state.payload()
        self.data = payload["state"]
        c = self.data.get("career") or {}
        self.clear_page()
        for child in self.badge.winfo_children():
            child.destroy()
        Crest(self.badge,self.team_named(self.data,c.get('team_id')),32).pack()
        self.identity.configure(text=f"{c.get('team_name') or '自由选手'}   /   {c.get('player_name','')}")
        self.date_label.configure(text=self.data.get("date","").replace("-"," / "))
        self.advance.configure(state="disabled" if c.get("over") else "normal",
                               text="前往比赛  →" if self.data.get("your_match") else "继续生涯  →")
        self.skip.configure(state="disabled" if c.get("over") else "normal")
        for key,btn in self.nav_buttons.items():
            btn.configure(bg="#342921" if key==self.page else SIDEBAR,
                          fg=ACCENT if key==self.page else MUTED,state="normal")
        self.nav_buttons["inbox"].configure(text=f"✉    收件箱   {c.get('unread') or ''}")
        getattr(self,f"render_{self.page}")(self.data,c)
        if msg or payload.get("msg"):
            self.status.configure(text=str(msg or payload["msg"]),fg=GREEN)
        if not self.testing:
            self.after_idle(self.show_story)

    def action(self,func,*args):
        if self.busy:
            return
        try:
            out = func(*args)
            self.state.persist()
            self.refresh(str(out.get("msg","已完成") if isinstance(out,dict) else out or "已保存"))
        except Exception as exc:
            messagebox.showerror("操作未完成",str(exc),parent=self)

    def background(self,func):
        """One serialized job. Workers communicate only through a queue."""
        if self.busy:
            return
        self.busy = True
        self.advance.configure(state="disabled")
        self.skip.configure(state="disabled")
        self.status.configure(text="正在处理，请稍候…",fg=ACCENT)
        def work():
            try:
                self.messages.put((True,func()))
            except Exception as exc:
                self.messages.put((False,str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def _drain(self):
        try:
            ok,out = self.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            if ok:
                self.state.persist()
                self.refresh(out.get("msg","已完成") if isinstance(out,dict) else str(out or "已完成"))
            else:
                self.refresh()
                messagebox.showerror("操作未完成",out,parent=self)
        self._queue_timer = self.after(90,self._drain)

    def next_stage(self):
        if self.state.career.over():
            return
        if self.data.get("your_match"):
            self.go("schedule")
        elif self.state.career.loan_default_pending or self.state.career.fix_pending:
            self.show_story()
        else:
            self.background(self.state.season.next_stage)

    def skip_stage(self):
        if self.state.career.over():
            return
        if self.state.career.loan_default_pending or self.state.career.fix_pending:
            self.show_story()
        else:
            self.background(self.state.season.skip_to_next_event)

    def show_setup(self):
        if self.busy:
            return
        self.clear_page()
        self.advance.configure(state="disabled")
        self.skip.configure(state="disabled")
        for btn in self.nav_buttons.values():
            btn.configure(state="disabled")
        self.identity.configure(text="建立新的生涯")
        SetupPage(self.page_host,self).pack(fill="both",expand=True)

    def create_career(self,payload):
        if self.state.career.exists and not self.testing:
            if not messagebox.askyesno("开始新生涯","当前生涯将先自动备份，再建立新档。继续吗？",parent=self):
                return
            # ApplicationState.create_career performs the verified backup;
            # do not make a second, uncompressed copy in this legacy shell.
        try:
            msg = self.state.create_career(payload)
        except Exception as exc:
            messagebox.showerror("无法创建生涯",str(exc),parent=self)
            return
        self.page = "dashboard"
        self.refresh(msg)

    def page_body(self,title,subtitle="",eyebrow="CAREER / DESK"):
        page = ScrollPage(self.page_host)
        page.pack(fill="both",expand=True)
        body = page.body
        label(body,eyebrow,size=8,color=ACCENT,display=True).pack(anchor="w",padx=28,pady=(24,4))
        label(body,title,size=23,bold=True).pack(anchor="w",padx=28)
        if subtitle:
            label(body,subtitle,size=9,color=MUTED).pack(anchor="w",padx=28,pady=(5,20))
        return body

    def panel(self,parent,padding=18,**pack):
        outer = tk.Frame(parent,bg=PANEL,highlightthickness=1,highlightbackground=LINE)
        outer.pack(fill="x",padx=pack.pop("padx",28),pady=pack.pop("pady",8),**pack)
        inner = tk.Frame(outer,bg=PANEL)
        inner.pack(fill="both",expand=True,padx=padding,pady=padding)
        return inner

    def table(self,parent,columns,headings,widths,height=12):
        frame = tk.Frame(parent,bg=PANEL)
        frame.pack(fill="both",expand=True,pady=8)
        tree = ttk.Treeview(frame,columns=columns,show="headings",height=height,selectmode="browse")
        for col,name,width in zip(columns,headings,widths):
            tree.heading(col,text=name,command=lambda c=col:self.sort_table(tree,c))
            tree.column(col,width=width,minwidth=50,anchor="w")
        y = ttk.Scrollbar(frame,orient="vertical",command=tree.yview)
        x = ttk.Scrollbar(frame,orient="horizontal",command=tree.xview)
        frame.rowconfigure(0,weight=1)
        frame.columnconfigure(0,weight=1)
        tree.grid(row=0,column=0,sticky="nsew")
        y.grid(row=0,column=1,sticky="ns")
        x.grid(row=1,column=0,sticky="ew")
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        tree.tag_configure("you",foreground=ACCENT)
        return tree

    @staticmethod
    def sort_table(tree,col):
        reverse = getattr(tree,"_sort",None) == (col,False)
        def key(iid):
            text = tree.set(iid,col)
            try:
                return (0,float(text.replace("$","").replace(",","").replace("%","").replace("#","")))
            except ValueError:
                return (1,text.casefold())
        for index,iid in enumerate(sorted(tree.get_children(),key=key,reverse=reverse)):
            tree.move(iid,"",index)
        tree._sort = (col,reverse)

    def show_story(self):
        if self._story_showing or self.busy or not self.state.career.story_queue:
            return
        row = self.state.career.story_queue[0]
        self._story_showing = True
        dialog = tk.Toplevel(self)
        dialog.title(row.get("title") or "生涯时刻")
        dialog.geometry("640x500")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        label(dialog,"CAREER / MOMENT",size=9,color=ACCENT,display=True).pack(anchor="w",padx=30,pady=(25,8))
        label(dialog,row.get("title") or "生涯时刻",size=19,bold=True,wraplength=560,justify="left").pack(anchor="w",padx=30)
        text = tk.Text(dialog,bg=BG,fg=TEXT,relief="flat",wrap="word",font=(FONT,11),padx=5,pady=12)
        text.pack(fill="both",expand=True,padx=25,pady=10)
        body = row.get("text") or row.get("body") or ""
        if row.get("rows"):
            body += "\n\n"+"\n".join(f"{i+1:02d}   {r.get('player') or r.get('name','')}   {r.get('rating','')}" for i,r in enumerate(row["rows"]))
        text.insert("1.0",body)
        text.configure(state="disabled")
        actions = tk.Frame(dialog,bg=BG)
        actions.pack(fill="x",padx=30,pady=(0,24))
        def ack(choice=""):
            self.state.career.ack_story(str(row.get("id") or ""),choice,self.state.season)
            self.state.persist()
            self._story_showing = False
            dialog.destroy()
            self.refresh()
        choices = row.get("choices") or []
        for option in choices:
            button(actions,option.get("label") or option.get("text") or option.get("id","继续"),
                   lambda c=option.get("id",""):ack(c),small=True).pack(fill="x",pady=3)
        if not choices:
            button(actions,"继续",ack,primary=True).pack(side="right")
        def dismiss():
            self._story_showing = False
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW",dismiss if choices else ack)

    def close(self):
        if self.busy:
            self.status.configure(text="操作仍在进行，完成后即可关闭。",fg=ACCENT)
            return
        self.state.persist()
        if self._bridge:
            self._bridge.shutdown()
            self._bridge.server_close()
        self.after_cancel(self._queue_timer)
        self.destroy()

    def report_callback_exception(self,kind,value,tb):
        if self.testing:
            self.callback_errors.append("".join(traceback.format_exception(kind,value,tb)))
        else:
            messagebox.showerror("界面操作未完成",str(value),parent=self)


def run_desktop():
    DesktopApp().mainloop()
