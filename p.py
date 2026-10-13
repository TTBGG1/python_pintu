import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import random
import time


class PuzzleGame:
    HEADER_H = 90
    FOOTER_H = 40
    PAD = 24
    RESERVED_W = 80
    RESERVED_H = 120

    def __init__(self, root):
        self.root = root
        self.root.title("拼图游戏")
        self.root.configure(bg="#2b2b2b")
        self.root.resizable(True, True)
        self.root.minsize(320, 420)

        self.grid_size = 3
        self.tile_size = 120
        self.tiles = []
        self.buttons = []
        self.selected = None
        self.moves = 0
        self.start_time = None
        self.timer_running = False
        self.original_image = None
        self.tile_images = []
        self.preview_window = None
        self._resize_job = None
        self._auto_sizing = False

        self._build_ui()
        self._load_default_image()   # 内部会触发自动预览

        self.root.bind("<Configure>", self._on_resize)

    # ---------------- UI ----------------
    def _build_ui(self):
        top = tk.Frame(self.root, bg="#2b2b2b")
        top.pack(fill="x", padx=10, pady=8)

        tk.Label(top, text="难度:", bg="#2b2b2b", fg="white").pack(side="left")
        self.difficulty_var = tk.StringVar(value="3 x 3")
        diff_menu = ttk.Combobox(
            top, textvariable=self.difficulty_var, state="readonly", width=8,
            values=["2 x 2", "3 x 3", "4 x 4", "5 x 5", "6 x 6"]
        )
        diff_menu.pack(side="left", padx=5)
        diff_menu.bind("<<ComboboxSelected>>", lambda e: self.new_game(fit_window=True))

        tk.Button(top, text="选择图片", command=self.choose_image,
                  bg="#4a90d9", fg="white", relief="flat", padx=10).pack(side="left", padx=5)
        tk.Button(top, text="重新开始", command=self.new_game,
                  bg="#e67e22", fg="white", relief="flat", padx=10).pack(side="left", padx=5)
        tk.Button(top, text="查看原图", command=self.show_preview,
                  bg="#27ae60", fg="white", relief="flat", padx=10).pack(side="left", padx=5)

        status = tk.Frame(self.root, bg="#2b2b2b")
        status.pack(fill="x", padx=10)
        self.moves_label = tk.Label(status, text="步数: 0", bg="#2b2b2b",
                                    fg="#f1c40f", font=("Arial", 12))
        self.moves_label.pack(side="left")
        self.timer_label = tk.Label(status, text="时间: 00:00", bg="#2b2b2b",
                                    fg="#1abc9c", font=("Arial", 12))
        self.timer_label.pack(side="right")

        self.board_container = tk.Frame(self.root, bg="#2b2b2b")
        self.board_container.pack(fill="both", expand=True, padx=10, pady=10)
        self.board_frame = tk.Frame(self.board_container, bg="#2b2b2b")
        self.board_frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(self.root, text="点击两块交换位置；拼好即胜利！",
                 bg="#2b2b2b", fg="#888", font=("Arial", 10)).pack(pady=(0, 8))

    # ---------------- 屏幕自适应 ----------------
    def _fit_window_to_image(self):
        if self.original_image is None:
            return

        n = self.grid_size
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        fixed_h = self.HEADER_H + self.FOOTER_H + self.PAD
        avail_w = screen_w - self.RESERVED_W - self.PAD * 2
        avail_h = screen_h - self.RESERVED_H - fixed_h
        max_board = max(min(avail_w, avail_h), n * 40)

        tile_from_screen = max_board // n
        tile_from_image = self.original_image.size[0] // n
        target_tile = min(tile_from_screen, tile_from_image, 120)
        target_tile = max(target_tile, 40)

        board_side = target_tile * n
        win_w = board_side + self.PAD * 2
        win_h = board_side + fixed_h

        win_w = min(win_w, screen_w - 20)
        win_h = min(win_h, screen_h - 60)

        # 把主窗口放到屏幕偏右的位置，给左侧预览留空间
        x = max(0, (screen_w - win_w) // 2 + 60)
        y = max(0, (screen_h - win_h) // 2 - 10)

        self._auto_sizing = True
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.update_idletasks()
        self._auto_sizing = False

        self._recalc_tile_size()
        self._slice_image()
        self._refresh_board()

        # 主窗口定位完成后，如果预览开着，重新贴到左侧
        if self.preview_window and self.preview_window.winfo_exists():
            self._position_preview_to_left()

    def _on_resize(self, event):
        if event.widget is not self.root:
            return
        if self._auto_sizing:
            return
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._apply_resize)

    def _apply_resize(self):
        self._resize_job = None
        if self.original_image is None:
            return
        if self._recalc_tile_size():
            self._slice_image()
            self._refresh_board()
        # 主窗口动过之后，预览也跟着贴左侧
        if self.preview_window and self.preview_window.winfo_exists():
            self._position_preview_to_left()

    def _recalc_tile_size(self):
        self.root.update_idletasks()
        cw = self.board_container.winfo_width()
        ch = self.board_container.winfo_height()
        avail = min(cw, ch) - 8
        if avail < 40:
            return False
        n = self.grid_size
        new_ts = max(30, avail // n)
        new_ts = min(new_ts, 300)
        if new_ts == self.tile_size:
            return False
        self.tile_size = new_ts
        return True

    # ---------------- 图片处理 ----------------
    def _load_default_image(self):
        size = 600
        img = Image.new("RGB", (size, size))
        pixels = img.load()
        for y in range(size):
            for x in range(size):
                r = int(255 * x / size)
                g = int(255 * y / size)
                b = int(255 * (1 - x / size))
                pixels[x, y] = (r, g, b)
        self._set_image(img, fit_window=True, auto_preview=False)

    def choose_image(self):
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
            # 选择了图片 → 自动开启预览
            self._set_image(img, fit_window=True, auto_preview=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开图片：{e}")

    def _set_image(self, img, fit_window=False, auto_preview=False):
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        if img.size[0] > 1600:
            img = img.resize((1600, 1600), Image.LANCZOS)
        self.original_image = img

        # 关闭旧预览，避免残留
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.destroy()
            self.preview_window = None

        self.new_game(fit_window=fit_window)

        if auto_preview:
            self.show_preview(auto=True)

    def _slice_image(self):
        n = self.grid_size
        side = self.original_image.size[0]
        src_ts = side // n
        ts = self.tile_size
        self.tile_images = []
        for r in range(n):
            row = []
            for c in range(n):
                box = (c * src_ts, r * src_ts, (c + 1) * src_ts, (r + 1) * src_ts)
                piece = self.original_image.crop(box).resize((ts, ts), Image.LANCZOS)
                row.append(ImageTk.PhotoImage(piece))
            self.tile_images.append(row)

    # ---------------- 游戏逻辑 ----------------
    def new_game(self, fit_window=False):
        self.grid_size = int(self.difficulty_var.get().split()[0])

        self.moves = 0
        self.moves_label.config(text="步数: 0")
        self.start_time = None
        self.timer_running = False
        self.timer_label.config(text="时间: 00:00")
        self.selected = None

        n = self.grid_size
        self.tiles = list(range(n * n))
        self._shuffle()

        for w in self.board_frame.winfo_children():
            w.destroy()
        self.buttons = []
        for r in range(n):
            row = []
            for c in range(n):
                btn = tk.Button(self.board_frame, bd=1, relief="solid",
                                highlightthickness=0, cursor="hand2")
                btn.grid(row=r, column=c, padx=1, pady=1)
                btn.config(command=lambda rr=r, cc=c: self.on_click(rr, cc))
                row.append(btn)
            self.buttons.append(row)

        if fit_window:
            self._fit_window_to_image()
        else:
            self._recalc_tile_size()
            self._slice_image()
            self._refresh_board()

    def _shuffle(self):
        n = self.grid_size
        while True:
            random.shuffle(self.tiles)
            if self.tiles != list(range(n * n)):
                break

    def _refresh_board(self):
        n = self.grid_size
        for r in range(n):
            for c in range(n):
                idx = self.tiles[r * n + c]
                pr, pc = divmod(idx, n)
                self.buttons[r][c].config(image=self.tile_images[pr][pc])
                if self.selected == (r, c):
                    self.buttons[r][c].config(relief="solid", bd=3,
                                              highlightbackground="#f1c40f",
                                              highlightcolor="#f1c40f",
                                              highlightthickness=3)
                else:
                    self.buttons[r][c].config(relief="solid", bd=1,
                                              highlightthickness=0)

    def on_click(self, r, c):
        if self.selected is None:
            self.selected = (r, c)
            self._refresh_board()
            return
        if self.selected == (r, c):
            self.selected = None
            self._refresh_board()
            return

        r1, c1 = self.selected
        n = self.grid_size
        i1 = r1 * n + c1
        i2 = r * n + c
        self.tiles[i1], self.tiles[i2] = self.tiles[i2], self.tiles[i1]
        self.selected = None
        self.moves += 1
        self.moves_label.config(text=f"步数: {self.moves}")

        if not self.timer_running:
            self.timer_running = True
            self.start_time = time.time()
            self._update_timer()

        self._refresh_board()
        self._check_win()

    def _update_timer(self):
        if not self.timer_running:
            return
        elapsed = int(time.time() - self.start_time)
        m, s = divmod(elapsed, 60)
        self.timer_label.config(text=f"时间: {m:02d}:{s:02d}")
        self.root.after(500, self._update_timer)

    def _check_win(self):
        if self.tiles == list(range(self.grid_size ** 2)):
            self.timer_running = False
            elapsed = int(time.time() - self.start_time) if self.start_time else 0
            m, s = divmod(elapsed, 60)
            messagebox.showinfo(
                "恭喜！",
                f"你完成了拼图！\n\n步数: {self.moves}\n用时: {m:02d}:{s:02d}"
            )

    # ---------------- 预览（贴主窗口左侧） ----------------
    def show_preview(self, auto=False):
        if self.original_image is None:
            return

        # 已存在：若是手动点击则提升；自动时只更新内容
        if self.preview_window and self.preview_window.winfo_exists():
            if not auto:
                self.preview_window.lift()
                self.preview_window.focus_set()
            self._update_preview_content()
            self._position_preview_to_left()
            return

        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("原图预览")
        self.preview_window.configure(bg="#2b2b2b")
        self.preview_window.resizable(False, False)
        self.preview_window.protocol("WM_DELETE_WINDOW", self._close_preview)

        # 预览尺寸：受屏幕高度、主窗口高度共同约束
        self._update_preview_content()
        self._position_preview_to_left()

    def _calc_preview_size(self):
        """根据屏幕和主窗口算预览边长，保证主窗口左侧能放下"""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # 预览最大不超过屏幕高度的 60%，宽度不超过屏幕的 35%
        max_by_h = int(screen_h * 0.6)
        max_by_w = int(screen_w * 0.35)

        # 主窗口左侧的可用空间
        self.root.update_idletasks()
        win_x = self.root.winfo_x()
        left_space = win_x - 40   # 左右各留 20px 边距

        avail = min(max_by_h, max_by_w, max(left_space, 200))
        avail = max(avail, 180)   # 最小 180

        # 不能超过原图本身
        avail = min(avail, self.original_image.size[0])
        return avail

    def _update_preview_content(self):
        if not (self.preview_window and self.preview_window.winfo_exists()):
            return
        size = self._calc_preview_size()
        img = self.original_image.resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)

        # 清空旧内容，重画
        for w in self.preview_window.winfo_children():
            w.destroy()
        lbl = tk.Label(self.preview_window, image=photo, bg="#2b2b2b")
        lbl.image = photo
        lbl.pack(padx=10, pady=(10, 4))
        tk.Label(self.preview_window, text="原图（参考）", bg="#2b2b2b",
                 fg="#aaa", font=("Arial", 10)).pack(pady=(0, 10))

        # 窗口自适应内容
        self.preview_window.update_idletasks()
        w = self.preview_window.winfo_reqwidth()
        h = self.preview_window.winfo_reqheight()
        self.preview_window.geometry(f"{w}x{h}")

    def _position_preview_to_left(self):
        """把预览窗口贴到主窗口左侧；空间不足则放右侧"""
        if not (self.preview_window and self.preview_window.winfo_exists()):
            return

        self.root.update_idletasks()
        self.preview_window.update_idletasks()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        pw = self.preview_window.winfo_reqwidth()
        ph = self.preview_window.winfo_reqheight()

        win_x = self.root.winfo_x()
        win_y = self.root.winfo_y()
        win_h = self.root.winfo_height()

        # 首选：贴在主窗口左侧
        px = win_x - pw - 12
        py = win_y + max(0, (win_h - ph) // 2)

        # 左侧越界 → 贴屏幕左边缘
        if px < 8:
            # 再试右侧
            right_x = win_x + self.root.winfo_width() + 12
            if right_x + pw <= screen_w - 8:
                px = right_x
            else:
                px = max(8, px)   # 兜底：贴屏幕左边

        # 纵向不越界
        py = max(8, min(py, screen_h - ph - 40))

        self.preview_window.geometry(f"{pw}x{ph}+{px}+{py}")
        # 保持预览在主窗口下层，避免遮挡操作
        self.preview_window.lift(self.root)

    def _close_preview(self):
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.destroy()
        self.preview_window = None


if __name__ == "__main__":
    root = tk.Tk()
    game = PuzzleGame(root)
    root.mainloop()