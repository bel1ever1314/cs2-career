"""Small native widgets: scrolling, tooltips, team crests and tactical artwork."""

import math
import tkinter as tk
from tkinter import ttk

from ..paths import logo_dir, static_dir
from ..world import slug
from .theme import *


def label(parent, text="", size=10, color=TEXT, bold=False, display=False, **kw):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                    font=(DISPLAY if display else FONT, size, "bold" if bold else "normal"), **kw)


def button(parent, text, command, primary=False, small=False):
    base = ACCENT if primary else RAISED
    btn = tk.Button(parent, text=text, command=command, bg=base,
                    fg=BG if primary else TEXT, activebackground="#ff9e70" if primary else LINE,
                    activeforeground=BG if primary else TEXT, disabledforeground=DIM,
                    font=(FONT, 9 if small else 10, "bold"), relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=base, highlightcolor=ACCENT,
                    padx=14, pady=7 if small else 11, cursor="hand2", takefocus=True)
    btn.bind("<Enter>", lambda _: btn.configure(bg="#ff9e70" if primary else LINE) if str(btn['state']) != 'disabled' else None)
    btn.bind("<Leave>", lambda _: btn.configure(bg=base))
    return btn


class ScrollPage(tk.Frame):
    """One lifetime-scoped wheel binding; tables keep their own scrolling."""
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=BG)
        win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self.top = self.winfo_toplevel()
        self.wheel_id = self.top.bind("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event):
        target = event.widget
        if isinstance(target, (ttk.Treeview, ttk.Combobox, tk.Text)):
            return
        node = target
        while node is not None:
            if node == self:
                if self.canvas.yview() != (0.0, 1.0):
                    self.canvas.yview_scroll(-int(event.delta / 120), "units")
                return
            node = getattr(node, "master", None)

    def destroy(self):
        if self.wheel_id:
            self.top.unbind("<MouseWheel>", self.wheel_id)
            self.wheel_id = None
        super().destroy()


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.popup, self.timer = widget, text, None, None
        widget.bind("<Enter>", self.enter, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def enter(self, _=None):
        self.timer = self.widget.after(350, self.show)

    def show(self):
        self.timer = None
        self.popup = tk.Toplevel(self.widget)
        self.popup.overrideredirect(True)
        self.popup.configure(bg=LINE)
        label(self.popup, self.text, size=10, justify="left", wraplength=350, padx=14, pady=12).pack(padx=1, pady=1)
        self.popup.update_idletasks()
        x = min(self.widget.winfo_rootx(), self.widget.winfo_screenwidth()-self.popup.winfo_reqwidth()-20)
        y = min(self.widget.winfo_rooty()+self.widget.winfo_height()+8, self.widget.winfo_screenheight()-self.popup.winfo_reqheight()-20)
        self.popup.geometry(f"+{max(0,x)}+{max(0,y)}")

    def hide(self, _=None):
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.popup:
            self.popup.destroy()
            self.popup = None


class Crest(tk.Canvas):
    """Load only local PNG crests; the geometric fallback is deterministic."""
    def __init__(self, parent, team, size=48):
        super().__init__(parent, width=size, height=size, bg=parent.cget("bg"), highlightthickness=0)
        team = team if isinstance(team, dict) else {"name": str(team)}
        name = team.get("name") or "Career"
        tid = team.get("id") or slug(name)
        # Filenames only; user-authored IDs never become arbitrary paths.
        safe = tid if tid and all(ch.isalnum() or ch in "-_" for ch in tid) else slug(name)
        for path in (logo_dir()/f"{safe}.png", static_dir()/"team_avatars"/f"{safe}.png"):
            if path.is_file():
                try:
                    raw = tk.PhotoImage(master=self, file=str(path))
                    step = max(1, math.ceil(max(raw.width(), raw.height())/size))
                    self.art = raw.subsample(step)
                    self.create_image(size/2, size/2, image=self.art)
                    return
                except tk.TclError:
                    pass
        self.create_polygon(size*.14, size*.05, size*.86, size*.05, size*.86, size*.65,
                            size*.5, size*.96, size*.14, size*.65, fill=RAISED, outline=ACCENT, width=2)
        tag = ''.join(word[0] for word in name.split())[:3].upper() or "C"
        self.create_text(size/2, size*.43, text=tag, font=(DISPLAY,max(10,int(size*.25)),"bold"), fill=TEXT)


class TacticalArt(tk.Canvas):
    """Code-native decorative site plan, never presented as a playable CS map."""
    def __init__(self, parent, height=240, variant="academy"):
        # A Canvas defaults to 394px requested width. That would steal space
        # from the adjacent match copy in compact windows.
        super().__init__(parent, bg=parent.cget("bg"), width=1, height=height, highlightthickness=0)
        self.variant = variant
        self.bind("<Configure>", self.draw)

    def draw(self, event):
        self.delete("all")
        w, h = event.width, event.height
        for x in range(0, w, 26):
            self.create_line(x, 0, x, h, fill="#22272c")
        for y in range(0, h, 26):
            self.create_line(0, y, w, y, fill="#22272c")
        def points(coords):
            return [value * (w if i%2 == 0 else h) for i,value in enumerate(coords)]
        for coords in ((.15,.2,.4,.2,.4,.37,.59,.37,.59,.16,.85,.16,.85,.52,.69,.52,.69,.8,.46,.8,.46,.59,.15,.59),
                       (.23,.31,.33,.31,.33,.45,.23,.45), (.66,.26,.77,.26,.77,.42,.66,.42)):
            self.create_polygon(*points(coords), fill="#242a30", outline="#4c5661", width=2)
        self.create_line(*points((.23,.78,.23,.52,.5,.52,.5,.45,.7,.45,.7,.3)), fill=ACCENT, width=2, dash=(5,6))
        for x,y in ((.23,.77),(.27,.83),(.18,.84),(.16,.74),(.28,.71)):
            px,py=x*w,y*h
            self.create_oval(px-4,py-4,px+4,py+4,fill=ACCENT,outline="")
        for text,x,y in (("A",.28,.37),("B",.71,.33)):
            self.create_text(w*x,h*y,text=text,fill=ACCENT,font=(DISPLAY,22,"bold"))
        self.create_text(w-12,h-12,text="CAREER / TACTICAL BOARD",anchor="se",fill=DIM,font=(DISPLAY,8))


def meter(parent, value, color=ACCENT, height=4):
    canvas = tk.Canvas(parent, height=height, bg=LINE, highlightthickness=0)
    canvas.bind("<Configure>", lambda e: (canvas.delete("all"), canvas.create_rectangle(0,0,e.width*max(0,min(100,float(value or 0)))/100,height,fill=color,outline="")))
    return canvas
