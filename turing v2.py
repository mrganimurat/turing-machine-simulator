import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os

# --------------------- Turing Machine Core ---------------------

class TuringMachine:
    def __init__(self, blank="_"):
        self.blank = blank
        self.reset()

    def reset(self, tape="", head=0, state="q0"):
        self.tape = {i: ch for i, ch in enumerate(tape) if ch != self.blank}
        self.head = head
        self.state = state
        self.halted = False
        self.step_count = 0
        self.transitions = {}  # (symbol, state) -> rule-string

    def read(self):
        return self.tape.get(self.head, self.blank)

    def write(self, value):
        if value == self.blank:
            self.tape.pop(self.head, None)
        else:
            self.tape[self.head] = value

    def parse_rule(self, rule):
        if not rule:
            return None
        write = None
        move = None
        next_state = None

        i = 0
        if i < len(rule) and rule[i] not in ("L", "R", "q"):
            write = rule[i]
            i += 1

        if i < len(rule) and rule[i] in ("L", "R"):
            move = rule[i]
            i += 1

        if i < len(rule) and rule[i] == "q":
            next_state = rule[i:]

        return (write, move, next_state)

    def step(self):
        if self.halted:
            return
        cur_symbol = self.read()
        key = (cur_symbol, self.state)
        rule = self.transitions.get(key, "")

        if not rule:
            self.halted = True
            return

        write, move, next_state = self.parse_rule(rule)

        if write:
            self.write(write)

        if move == "R":
            self.head += 1
        elif move == "L":
            self.head -= 1

        if next_state:
            self.state = next_state

        self.step_count += 1

# --------------------- Visualizer Core ---------------------

class Visualizer(tk.Toplevel):
    def __init__(self, parent, tm, sync_cb, speed_var):
        super().__init__(parent)
        self.parent = parent  # главное окно (App)
        self.tm = tm  # экземпляр TuringMachine
        self.sync_cb = sync_cb  # функция синхронизации правил
        self.speed_var = speed_var  # общая переменная скорости

        self.running = False
        self.history_snapshots = []
        self.title("Визуализатор Тьюринг машинасы")

        # --- Основная структура ---
        self.main = ttk.Frame(self)
        self.main.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== Верх: лента =====
        self.canvas = tk.Canvas(
            self.main, bg="white", height=200,
            highlightthickness=1, highlightbackground="#94a3b8"
        )
        self.canvas.pack(fill="x", expand=True, pady=(10, 6))
        self.canvas.bind("<Configure>", lambda e: self.draw_tape())

        # Подсказка — прямо под лентой
        self.msg_label = tk.Label(
            self.main,
            text="Қадам түсіндірмесі осында көрсетіледі",
            bg="#2563eb", fg="white",
            font=("Arial", 11, "italic"),
            wraplength=700, justify="center"
        )
        self.msg_label.pack(pady=(2, 10))

        # ===== Кнопки управления =====
        ctrl_frame = ttk.Frame(self.main)
        ctrl_frame.pack(pady=5)

        ttk.Button(ctrl_frame, text="Қадам", width=10, command=self.step_once).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="Авто", width=10, command=self.start_auto).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="Тоқтату", width=10, command=self.stop_auto).pack(side="left", padx=5)

        # новая кнопка сброса — как в главном окне
        ttk.Button(ctrl_frame, text="Қайта бастау", width=12, command=self.reset_full).pack(side="left", padx=5)

        # новая кнопка очистки истории
        ttk.Button(ctrl_frame, text="Тарихты тазалау", width=16, command=self.clear_history).pack(side="left", padx=5)

        ttk.Label(ctrl_frame, text="Жылдамдық (мс):").pack(side="left", padx=(20, 5))
        self.speed_spin = ttk.Spinbox(
            ctrl_frame, from_=50, to=2000, increment=50, width=6,
            textvariable=self.speed_var, command=self.update_speed_sync
        )
        self.speed_spin.pack(side="left")

        # ===== Нижняя часть: информация и история =====
        bottom = ttk.Frame(self.main)
        bottom.pack(fill="both", expand=True, pady=10)

        # Левая колонка — информация
        info_frame = ttk.Frame(bottom)
        info_frame.pack(side="left", fill="both", expand=True, padx=10)

        ttk.Label(info_frame, text="Ағымдағы ақпарат", font=("Arial", 12, "bold")).pack(pady=(0, 4))
        self.lbl_state = ttk.Label(info_frame, text="Күй: q0", font=("Consolas", 11))
        self.lbl_state.pack(anchor="w")
        self.lbl_read  = ttk.Label(info_frame, text="Оқылған символ: _", font=("Consolas", 11))
        self.lbl_read.pack(anchor="w")
        self.lbl_write = ttk.Label(info_frame, text="Орнына жазылған символ: _", font=("Consolas", 11))
        self.lbl_write.pack(anchor="w")
        self.lbl_move  = ttk.Label(info_frame, text="Қозғалыс: -", font=("Consolas", 11))
        self.lbl_move.pack(anchor="w")

        self.history = tk.Text(
            info_frame, height=6, width=42, wrap="word",
            state="disabled", bg="#f8fafc", relief="solid", borderwidth=1
        )
        self.history.pack(fill="x", pady=(10, 0))

        # --- Қадамдар тарихы ---
        self.history_container = ttk.Frame(bottom)
        self.history_container.pack(fill="both", expand=True, padx=5, pady=5)

        self.history_canvas = tk.Canvas(self.history_container, bg="#f8fafc", highlightthickness=0)
        self.history_canvas.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(self.history_container, orient="vertical", command=self.history_canvas.yview)
        scroll.pack(side="right", fill="y")
        self.history_canvas.configure(yscrollcommand=scroll.set)

        self.history_inner = ttk.Frame(self.history_canvas)
        self.history_canvas.create_window((0, 0), window=self.history_inner, anchor="nw")

        self.history_inner.bind(
            "<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        )
        self.history_canvas.bind("<Configure>", lambda e: self.redraw_history())

    def draw_tape(self, highlight=None):
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        cell_w = 60
        visible = max(10, width // cell_w)
        mid = visible // 2
        start = self.tm.head - mid
        y = 60

        for i in range(visible):
            pos = start + i
            x = i * cell_w + (width - visible * cell_w) / 2
            sym = self.tm.tape.get(pos, self.tm.blank)

            color = "#e2e8f0"
            if pos == self.tm.head:
                color = "#3b82f6"
            elif highlight == pos:
                color = "#22c55e"

            self.canvas.create_rectangle(x, y, x + cell_w, y + 50,
                                         fill=color, outline="#0f172a", width=1.5)
            self.canvas.create_text(x + cell_w / 2, y + 25,
                                    text=sym, font=("Consolas", 18, "bold"), fill="black")

        head_x = (mid) * cell_w + (width - visible * cell_w) / 2 + cell_w / 2
        self.canvas.create_polygon(head_x, y - 10, head_x - 10, y - 25, head_x + 10, y - 25,
                                   fill="#0f172a")

    def draw_cb(self):
        """Перерисовывает ленту в основном окне, если оно существует"""
        try:
            if self.parent and hasattr(self.parent, "draw_tape"):
                self.parent.draw_tape()
        except Exception as e:
            print("Draw callback error:", e)

    def redraw_history(self):
        # Перерисовка всех мини-лент при изменении размера окна
        for child in self.history_inner.winfo_children():
            child.destroy()
        for snapshot in self.history_snapshots:
            self._render_snapshot(snapshot)

    def explain(self, text, color="#2563eb"):
        self.msg_label.config(text=text, bg=color)

    def log(self, text):
        self.history.configure(state="normal")
        self.history.insert("end", text + "\n")
        self.history.configure(state="disabled")
        self.history.see("end")

    def _clear_history_widgets(self):
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.configure(state="disabled")
        for child in self.history_inner.winfo_children():
            child.destroy()
        self.history_snapshots.clear()

    def _render_snapshot(self, snapshot):
        hist_w = max(250, self.history_canvas.winfo_width() - 30)
        cell_w = 25
        visible_cells = max(1, hist_w // cell_w)

        canvas = tk.Canvas(
            self.history_inner, width=hist_w, height=50,
            bg="white", highlightthickness=1, highlightbackground="#cbd5e1"
        )
        canvas.pack(pady=4, fill="x")

        head = snapshot["head"]
        tape = snapshot["tape"]
        mid = visible_cells // 2
        start = head - mid

        for i in range(visible_cells):
            pos = start + i
            x = i * cell_w
            sym = tape.get(pos, self.tm.blank)

            color = "#60a5fa" if pos == head else "white"
            outline = "#2563eb" if pos == head else "#94a3b8"
            canvas.create_rectangle(x, 15, x + cell_w, 35, fill=color, outline=outline)
            canvas.create_text(x + cell_w / 2, 25, text=sym, font=("Consolas", 10))

        canvas.create_text(
            hist_w / 2, 45,
            text=f"Қадам {snapshot['step_count']}",
            font=("Arial", 8, "italic"),
            fill="#64748b"
        )

    def refresh_from_tm(self):
        """Обновить визуализатор по текущему состоянию машины"""
        self.draw_tape()
        self.draw_cb()
        self.explain(
            f"Күй: {self.tm.state}, Бас позиция: {self.tm.head}, Тоқтады: {self.tm.halted}",
            "#2563eb"
        )

    def step_once(self):
        self.sync_cb()

        if self.tm.halted:
            self.explain("Машина остановлена. Для продолжения сначала нажмите reset.", "#dc2626")
            self.draw_tape()
            self.draw_cb()
            return

        cur_state = self.tm.state
        read = self.tm.read()
        rule = (self.tm.transitions.get((read, cur_state)) or "").strip()

        if not rule:
            self.tm.halted = True
            self.explain("Машина тоқтатылды", "#dc2626")
            self.log(f"STOP: ({cur_state}, {read}) үшін ереже жоқ")
            self.draw_tape()
            self.draw_cb()
            return

        write, move, nxt = self.tm.parse_rule(rule)
        nxt = nxt or cur_state
        write = write or read

        self.lbl_state.config(text=f"Күй: {cur_state}")
        self.lbl_read.config(text=f"Оқылған символ: {read}")
        self.lbl_write.config(text=f"Орнына жазылған символ: {write}")
        self.lbl_move.config(text=f"Қозғалыс: {move or '-'}")

        self.explain(f"Күй {cur_state} → {nxt}, {move or '-'} бағытымен қозғалды", "#2563eb")

        prev_head = self.tm.head
        self.tm.step()
        self.draw_tape(highlight=prev_head)
        self.draw_cb()
        self.save_tape_snapshot()

    def start_auto(self, sync_only=False):
        """Автоматический запуск, если sync_only=False — это из визуализатора"""
        self.tm.halted = False
        self.running = True
        self.explain("Машина автоматты түрде жұмыс істеп жатыр...", "#22c55e")

        # если вызвано из главного окна — просто запустить цикл без дублирования интерфейса
        if not sync_only:
            self.auto_loop()

    def stop_auto(self):
        """Остановить авто-режим"""
        self.running = False
        self.explain("Машина тоқтады", "#dc2626")

    def auto_loop(self):
        if not self.running:
            return

        if self.tm.halted:
            self.running = False
            self.explain("Машина тоқтатылды", "#dc2626")
            return

        self.step_once()
        self.after(self.speed_var.get(), self.auto_loop)

    def reset_view(self):
        self.running = False

        # сохранить текущую ленту
        tape_copy = "".join(
            self.tm.tape.get(i, self.tm.blank)
            for i in range(min(self.tm.tape.keys(), default=0),
                           max(self.tm.tape.keys(), default=0) + 1)
        )

        # сбросить состояние, шаги, и позицию головы
        self.tm.reset(tape=tape_copy, head=0, state="q0")

        # очистить визуальные элементы
        self._clear_history_widgets()
        self.msg_label.config(text="Қадам түсіндірмесі осында көрсетіледі", bg="#2563eb")

        self.draw_tape()
        self.draw_cb()
        self.explain("Машина қайтадан іске қосылды", "#22c55e")

    def update_speed_sync(self):
        try: self.speed_var.set(int(self.speed_spin.get()))
        except: pass

    def reset_full(self):
        """Синхронизированный сброс ленты и машины с главным окном"""
        self.running = False
        self.sync_cb()  # обновляем правила из таблицы
        self.parent.reset_tm()  # вызываем сброс главного окна (главный метод)
        self.refresh_from_tm()  # обновляем визуализатор
        self.explain("Машина қайта басталды", "#22c55e")

    def clear_history(self):
        """Очищает историю шагов, не трогая машину"""
        self._clear_history_widgets()
        self.explain("Қадамдар тарихы тазаланды", "#2563eb")

    def save_tape_snapshot(self):
        snapshot = {
            "tape": dict(self.tm.tape),
            "head": self.tm.head,
            "step_count": self.tm.step_count,
        }
        self.history_snapshots.append(snapshot)
        self._render_snapshot(snapshot)
        self.history_canvas.yview_moveto(1)


# --------------------- GUI ---------------------

CELL_W = 40
CELL_H = 40
VISIBLE = 21


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.vis = None
        self.title("Тьюринг машина симуляторы")
        self.tm = TuringMachine()
        self.running = False
        self.run_delay = 200
        self.speed_var = tk.IntVar(value=200)

        self.symbols = ["_", "0", "1"]
        self.states = ["q0", "q1"]

        if not os.path.exists("profiles"):
            os.makedirs("profiles")

        self.create_menu()
        self.create_widgets()
        self.update_table()
        self.draw_tape()

    # ---------------- MENU -----------------

    def create_menu(self):
        menu = tk.Menu(self)
        self.config(menu=menu)

        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Файл", menu=file_menu)

        file_menu.add_command(label="Ережені сақтау", command=self.save_rules_dialog)
        file_menu.add_command(label="Ережені жүктеу", command=self.load_rules_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Лентаны сақтау", command=self.save_tape_dialog)
        file_menu.add_command(label="Лентаны жүктеу", command=self.load_tape_dialog)

        prof_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Профильдер", menu=prof_menu)

        prof_menu.add_command(label="Профильді сақтау", command=self.save_profile)
        prof_menu.add_command(label="Профильді жүктеу", command=self.load_profile)


        menu.add_command(label="Визуализатор", command=self.open_visualizer)

    # ---------------- UI ------------------

    def create_widgets(self):

        # ====== Верх: только лента ======
        top = ttk.Frame(self)
        top.pack(fill="x", anchor="n")

        tape_frame = ttk.Frame(top)
        tape_frame.pack(fill="x", pady=5)

        self.canvas = tk.Canvas(tape_frame, height=80)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self.draw_tape())

        # ====== Центр: весь остальной интерфейс ======
        center = ttk.Frame(self)
        center.pack(anchor="n", pady=10)

        # ---------- Управление лентой ----------
        ctrl = ttk.Frame(center)
        ctrl.pack(pady=5)

        ttk.Label(ctrl, text="Лента:").grid(row=0, column=0, padx=5)
        self.tape_entry = ttk.Entry(ctrl, width=30)
        self.tape_entry.grid(row=0, column=1, padx=5)
        self.tape_entry.insert(0, "1011")

        ttk.Label(ctrl, text="Бас позиция:").grid(row=0, column=2, padx=5)
        self.head_entry = ttk.Entry(ctrl, width=5)
        self.head_entry.grid(row=0, column=3, padx=5)
        self.head_entry.insert(0, "0")

        ttk.Button(ctrl, text="Қайта бастау", command=self.reset_tm).grid(row=0, column=4, padx=5)
        ttk.Button(ctrl, text="Қадам", command=self.step_once).grid(row=0, column=5, padx=5)

        self.btn_run = ttk.Button(ctrl, text="Бастау", command=self.toggle_run)
        self.btn_run.grid(row=0, column=6, padx=5)

        ttk.Label(ctrl, text="Жылдамдық (мс):").grid(row=0, column=7)
        self.speed_spin = ttk.Spinbox(
            ctrl, from_=50, to=2000, increment=50, width=6,
            textvariable=self.speed_var, command=self.update_speed
        )
        self.speed_spin.grid(row=0, column=8, padx=5)

        # ---------- Таблица ----------
        rules_block = ttk.Frame(center)
        rules_block.pack(pady=10)

        ttk.Label(rules_block, text="Функционалдық схема", font=("Arial", 12, "bold")).pack()

        self.table_frame = ttk.Frame(rules_block)
        self.table_frame.pack(anchor="center")

        # ---------- Кнопки ----------
        row1 = ttk.Frame(center)
        row1.pack(pady=5)
        ttk.Button(row1, text="Күй қосу", command=self.add_state).pack(side="left", padx=10)
        ttk.Button(row1, text="Күй өшіру", command=self.remove_state).pack(side="left", padx=10)

        row2 = ttk.Frame(center)
        row2.pack(pady=5)
        ttk.Button(row2, text="Символ қосу", command=self.add_symbol).pack(side="left", padx=10)
        ttk.Button(row2, text="Символ өшіру", command=self.remove_symbol).pack(side="left", padx=10)

        row3 = ttk.Frame(center)
        row3.pack(pady=5)
        ttk.Button(row3, text="Күй орын ауыстыру", command=self.reorder_states).pack(side="left", padx=10)
        ttk.Button(row3, text="Символ орын ауыстыру", command=self.reorder_symbols).pack(side="left", padx=10)

        # ---------- Статус ----------
        self.status = ttk.Label(center, text="")
        self.status.pack(pady=10)

    # ----------------- Table -------------------

    def snapshot_rules(self):
        saved = {}
        if hasattr(self, "cells"):  # таблица существует
            for (sym, st), entry in self.cells.items():
                saved[(sym, st)] = entry.get()
        return saved

    def restore_rules(self, saved):
        for key, value in saved.items():
            if key in self.cells and value:
                self.cells[key].insert(0, value)

    def update_table(self):
        saved = self.snapshot_rules()

        for w in self.table_frame.winfo_children():
            w.destroy()

        ttk.Label(self.table_frame, text="Символ").grid(row=0, column=0)

        self.cells = {}

        for j, st in enumerate(self.states):
            ttk.Label(self.table_frame, text=st).grid(row=0, column=j+1)

        for i, sym in enumerate(self.symbols):
            ttk.Label(self.table_frame, text=sym).grid(row=i+1, column=0)
            for j, st in enumerate(self.states):
                ent = ttk.Entry(self.table_frame, width=10)
                ent.grid(row=i+1, column=j+1)
                self.cells[(sym, st)] = ent

        self.restore_rules(saved)

    # ---------------- SAVE / LOAD -------------------

    def save_rules_dialog(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", title="Ережені сақтау")
        if not path:
            return
        data = {
            "symbols": self.symbols,
            "states": self.states,
            "rules": {f"{s}|{q}": ent.get() for (s, q), ent in self.cells.items()}
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_rules_dialog(self):
        path = filedialog.askopenfilename(defaultextension=".json", title="Ережені жүктеу")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.symbols = data["symbols"]
        self.states = data["states"]
        self.update_table()
        for k, rule in data["rules"].items():
            sym, st = k.split("|")
            if (sym, st) in self.cells:
                self.cells[(sym, st)].insert(0, rule)

    def save_tape_dialog(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", title="Лентаны сақтау")
        if not path:
            return
        head = self._read_int_field(self.head_entry, "Бас позиция")
        if head is None:
            return
        data = {
            "tape": self.tape_entry.get(),
            "head": head
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_tape_dialog(self):
        path = filedialog.askopenfilename(defaultextension=".json", title="Лентаны жүктеу")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.tape_entry.delete(0, "end")
        self.tape_entry.insert(0, data["tape"])
        self.head_entry.delete(0, "end")
        self.head_entry.insert(0, str(data["head"]))

    # --------- Profiles ---------

    def save_profile(self):
        name = simpledialog.askstring("Профильді сақтау", "Профиль аты:")
        if not name:
            return
        path = f"profiles/{name}.json"

        data = {
            "symbols": self.symbols,
            "states": self.states,
            "rules": {f"{s}|{q}": ent.get() for (s, q), ent in self.cells.items()}
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_profile(self, filename=None):
        if filename is None:
            return self.load_profile_dialog()

        path = f"profiles/{filename}"
        if not os.path.exists(path):
            messagebox.showerror("Ошибка", "Профиль табылмады")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.apply_profile_data(data)

    def apply_profile_data(self, data):
        self.symbols = data.get("symbols", self.symbols)
        self.states = data.get("states", self.states)
        self.update_table()

        for (sym, st), ent in self.cells.items():
            ent.delete(0, "end")

        for k, rule in data.get("rules", {}).items():
            sym, st = k.split("|")
            if (sym, st) in self.cells:
                self.cells[(sym, st)].insert(0, rule)

        if "tape" in data:
            self.tape_entry.delete(0, "end")
            self.tape_entry.insert(0, data["tape"])
        if "head" in data:
            self.head_entry.delete(0, "end")
            self.head_entry.insert(0, str(data["head"]))

    def load_profile_dialog(self):
        folder = "profiles"

        if not os.path.exists(folder):
            os.makedirs(folder)

        files = [f for f in os.listdir(folder) if f.endswith(".json")]

        if not files:
            messagebox.showinfo("Профиль жоқ", "Профильдер табылмады")
            return

        win = tk.Toplevel(self)
        win.title("Профильді жүктеу")
        win.geometry("300x300")
        win.lift()
        win.focus_force()

        tk.Label(win, text="Профиль таңдаңыз:").pack(pady=5)

        lb = tk.Listbox(win)
        lb.pack(fill="both", expand=True, padx=10, pady=5)

        for f in files:
            lb.insert("end", f)

        def load_selected():
            if not lb.curselection():
                return
            filename = lb.get(lb.curselection()[0])
            self.load_profile(filename)
            win.destroy()

        def on_double(event):
            load_selected()

        lb.bind("<Double-1>", on_double)

        tk.Button(win, text="Жүктеу", command=load_selected).pack(pady=5)
        tk.Button(win, text="Жабу", command=win.destroy).pack(pady=5)

    # ----------------- Actions -------------------

    def add_state(self):
        new = simpledialog.askstring("Күй қосу", "Жаңа күй аты:")
        if new and new not in self.states:
            self.states.append(new)
            self.update_table()

    def remove_state(self):
        choice = simpledialog.askstring("Күй өшіру",
                                        "Өшіру күйін таңдаңыз:\n" + "\n".join(self.states))
        if choice in self.states:
            if len(self.states) == 1:
                return
            self.states.remove(choice)
            self.update_table()

    def add_symbol(self):
        dlg = simpledialog.askstring("Символ қосу", "Жаңа символ:")
        if dlg and dlg not in self.symbols:
            self.symbols.append(dlg)
            self.update_table()

    def remove_symbol(self):
        choice = simpledialog.askstring("Символ өшіру",
                                        "Өшіру символын таңдаңыз:\n" + "\n".join(self.symbols))
        if choice in self.symbols:
            if len(self.symbols) == 1:
                return
            self.symbols.remove(choice)
            self.update_table()

    def reorder_states(self):
        win = tk.Toplevel(self)
        win.title("Күй орын ауыстыру")
        win.geometry("300x320")
        win.lift()
        win.focus_force()

        tk.Label(win, text="Күйді таңдаңыз:").pack(pady=5)

        lb = tk.Listbox(win)
        lb.pack(fill="both", expand=True, padx=10, pady=5)

        for st in self.states:
            lb.insert("end", st)

        tk.Label(win, text="Жаңа индекс (0..{}):".format(len(self.states) - 1)).pack()

        idx_entry = tk.Entry(win)
        idx_entry.pack(pady=3)

        def move():
            sel = lb.curselection()
            if not sel:
                return
            old = lb.get(sel[0])

            try:
                new_i = int(idx_entry.get())
            except:
                return

            if new_i < 0 or new_i >= len(self.states):
                return

            self.states.remove(old)
            self.states.insert(new_i, old)
            self.update_table()
            win.destroy()

        def on_double(event):
            move()

        lb.bind("<Double-1>", on_double)

        tk.Button(win, text="Орындау", command=move).pack(pady=5)
        tk.Button(win, text="Жабу", command=win.destroy).pack()

    def reorder_symbols(self):
        win = tk.Toplevel(self)
        win.title("Символ орын ауыстыру")
        win.geometry("300x320")
        win.lift()
        win.focus_force()

        tk.Label(win, text="Символды таңдаңыз:").pack(pady=5)

        lb = tk.Listbox(win)
        lb.pack(fill="both", expand=True, padx=10, pady=5)

        for s in self.symbols:
            lb.insert("end", s)

        tk.Label(win, text="Жаңа индекс (0..{}):".format(len(self.symbols) - 1)).pack()

        idx_entry = tk.Entry(win)
        idx_entry.pack(pady=3)

        def move():
            sel = lb.curselection()
            if not sel:
                return
            old = lb.get(sel[0])

            try:
                new_i = int(idx_entry.get())
            except:
                return

            if new_i < 0 or new_i >= len(self.symbols):
                return

            self.symbols.remove(old)
            self.symbols.insert(new_i, old)
            self.update_table()
            win.destroy()

        def on_double(event):
            move()

        lb.bind("<Double-1>", on_double)

        tk.Button(win, text="Орындау", command=move).pack(pady=5)
        tk.Button(win, text="Жабу", command=win.destroy).pack()

    # ---------------- Simulation -----------------

    def sync_rules(self):
        self.tm.transitions = {}
        for (sym, st), ent in self.cells.items():
            self.tm.transitions[(sym, st)] = ent.get().strip()

    def _vis_alive(self):
        return getattr(self, "vis", None) is not None and self.vis.winfo_exists()

    def _read_int_field(self, widget, label):
        try:
            return int(widget.get())
        except ValueError:
            messagebox.showerror("Ошибка", f"{label} должен быть целым числом.")
            return None

    def reset_tm(self):
        tape = self.tape_entry.get()
        head = self._read_int_field(self.head_entry, "Бас позиция")
        if head is None:
            return
        self.sync_rules()
        self.tm.reset(tape, head, self.states[0])
        self.draw_tape()

        if self._vis_alive():
            self.vis.refresh_from_tm()

    def step_once(self):
        """Выполнить один шаг и синхронизировать визуализатор"""
        self.sync_rules()
        if not self.tm.halted:
            self.tm.step()
        self.draw_tape()

        # --- если визуализатор открыт, обновить его тоже ---
        if self._vis_alive():
            self.vis.refresh_from_tm()

    def toggle_run(self):
        """Запуск или остановка симуляции"""
        if self.running:
            self.running = False
            self.btn_run.config(text="Бастау")

            # остановить визуализатор тоже
            if self._vis_alive():
                self.vis.stop_auto()

        else:
            self.tm.halted = False
            self.running = True
            self.btn_run.config(text="Тоқтату")

            # запустить визуализатор тоже
            if self._vis_alive():
                self.vis.start_auto(sync_only=True)

            self.run_loop()

    def run_loop(self):
        if not self.running:
            return

        # если машина остановилась, завершить цикл, но не запрещать новый запуск
        if self.tm.halted:
            self.running = False
            self.btn_run.config(text="Бастау")
            return

        self.step_once()
        self.after(self.run_delay, self.run_loop)

    def update_speed(self):
        try: self.run_delay = int(self.speed_var.get())
        except: pass

    # ---------------- Tape Drawing -----------------

    def draw_tape(self):
        self.canvas.delete("all")

        # Текущая ширина canvas
        canvas_w = self.canvas.winfo_width()

        # Сколько клеток помещается
        visible = max(3, canvas_w // CELL_W)

        mid = visible // 2
        start = self.tm.head - mid

        for i in range(visible):
            pos = start + i
            x = i * CELL_W
            y = 10

            sym = self.tm.tape.get(pos, self.tm.blank)
            self.canvas.create_rectangle(x, y, x + CELL_W, y + CELL_H, fill="white")
            self.canvas.create_text(x + CELL_W // 2, y + CELL_H // 2,
                                    text=sym, font=("Consolas", 16))

            if pos == self.tm.head:
                self.canvas.create_rectangle(x, y, x + CELL_W, y + CELL_H,
                                             outline="blue", width=2)
                self.canvas.create_polygon(
                    x + CELL_W // 2, y + CELL_H + 5,
                    x + CELL_W // 2 - 10, y + CELL_H - 5,
                    x + CELL_W // 2 + 10, y + CELL_H - 5,
                    fill="black"
                )

        self.status.config(
            text=f"Күй: {self.tm.state} | Бас: {self.tm.head} | Қадам: {self.tm.step_count} | Тоқтады: {self.tm.halted}"
        )

    # ---------------- Visualizer Integration -----------------

    def open_visualizer(self):
        if self._vis_alive():
            self.vis.lift()
            return

        self.vis = Visualizer(self, self.tm, self.sync_rules, self.speed_var)

# ------------------ RUN --------------------

if __name__ == "__main__":
    try: App().mainloop()
    except KeyboardInterrupt: pass

