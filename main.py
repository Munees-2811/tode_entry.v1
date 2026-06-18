import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
from PIL import Image, ImageTk

from ocr_engine import (
    extract_text_tesseract,
    extract_text_easyocr,
    detect_fields,
    preprocess_image,
)
from data_manager import DataManager


class TODEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TODE Entry v1 — CV Data Entry Automation")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        self.data_manager = DataManager()
        self.image_path = None
        self.tk_image = None
        self.original_image = None
        self.selection_rect = None
        self.start_x = None
        self.start_y = None
        self.field_entries = {}
        self.ocr_engine = tk.StringVar(value="tesseract")
        self.scale_factor = 1.0

        self._build_menu()
        self._build_toolbar()
        self._build_main_layout()
        self._build_statusbar()

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image...", command=self.load_image, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Export CSV...", command=self.export_csv)
        file_menu.add_command(label="Export JSON...", command=self.export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        ocr_menu = tk.Menu(menubar, tearoff=0)
        ocr_menu.add_radiobutton(label="Tesseract", variable=self.ocr_engine, value="tesseract")
        ocr_menu.add_radiobutton(label="EasyOCR", variable=self.ocr_engine, value="easyocr")
        menubar.add_cascade(label="OCR Engine", menu=ocr_menu)

        self.root.bind("<Control-o>", lambda e: self.load_image())

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="📂 Open Image", command=self.load_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔍 Extract All", command=self.extract_full).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 Detect Fields", command=self.detect_and_fill).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(toolbar, text="✅ Save Entry", command=self.save_entry).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑 Clear Fields", command=self.clear_fields).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Label(toolbar, text="Add Field:").pack(side=tk.LEFT, padx=2)
        self.new_field_var = tk.StringVar()
        field_entry = ttk.Entry(toolbar, textvariable=self.new_field_var, width=15)
        field_entry.pack(side=tk.LEFT, padx=2)
        field_entry.bind("<Return>", lambda e: self.add_field())
        ttk.Button(toolbar, text="+ Add", command=self.add_field).pack(side=tk.LEFT, padx=2)

        self.entry_count_var = tk.StringVar(value="Entries: 0")
        ttk.Label(toolbar, textvariable=self.entry_count_var).pack(side=tk.RIGHT, padx=10)

    def _build_main_layout(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: image canvas
        left_frame = ttk.LabelFrame(main_pane, text="Image Preview", padding=5)
        main_pane.add(left_frame, weight=3)

        self.canvas = tk.Canvas(left_frame, bg="#2b2b2b", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Right panel
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=2)

        right_pane = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_pane.pack(fill=tk.BOTH, expand=True)

        # OCR output
        ocr_frame = ttk.LabelFrame(right_pane, text="OCR Output", padding=5)
        right_pane.add(ocr_frame, weight=1)

        self.ocr_text = scrolledtext.ScrolledText(ocr_frame, wrap=tk.WORD, height=10, font=("Consolas", 10))
        self.ocr_text.pack(fill=tk.BOTH, expand=True)

        # Data fields
        fields_frame = ttk.LabelFrame(right_pane, text="Data Fields", padding=5)
        right_pane.add(fields_frame, weight=2)

        field_canvas = tk.Canvas(fields_frame)
        field_scrollbar = ttk.Scrollbar(fields_frame, orient=tk.VERTICAL, command=field_canvas.yview)
        self.fields_container = ttk.Frame(field_canvas)
        self.fields_container.bind(
            "<Configure>", lambda e: field_canvas.configure(scrollregion=field_canvas.bbox("all"))
        )
        field_canvas.create_window((0, 0), window=self.fields_container, anchor="nw")
        field_canvas.configure(yscrollcommand=field_scrollbar.set)

        field_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        field_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._add_default_fields()

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Ready — Load an image to get started")
        status = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=3)
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def _add_default_fields(self):
        defaults = ["Name", "Date", "Amount", "Description", "Reference"]
        for name in defaults:
            self._create_field_row(name)

    def _create_field_row(self, name):
        if name in self.field_entries:
            return

        row = ttk.Frame(self.fields_container)
        row.pack(fill=tk.X, pady=2)

        ttk.Label(row, text=name + ":", width=15, anchor=tk.E).pack(side=tk.LEFT, padx=(0, 5))

        var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        paste_btn = ttk.Button(
            row, text="📎", width=3, command=lambda n=name: self.paste_selection_to_field(n)
        )
        paste_btn.pack(side=tk.LEFT, padx=2)

        del_btn = ttk.Button(row, text="✕", width=3, command=lambda n=name, r=row: self.remove_field(n, r))
        del_btn.pack(side=tk.LEFT)

        self.field_entries[name] = var

    def remove_field(self, name, row):
        row.destroy()
        self.field_entries.pop(name, None)

    def add_field(self):
        name = self.new_field_var.get().strip()
        if not name:
            return
        if name in self.field_entries:
            messagebox.showwarning("Duplicate", f"Field '{name}' already exists.")
            return
        self._create_field_row(name)
        self.new_field_var.set("")

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        self.image_path = path
        self.original_image = Image.open(path)
        self._display_image()
        self.status_var.set(f"Loaded: {os.path.basename(path)}")

    def _display_image(self):
        if not self.original_image:
            return

        canvas_w = self.canvas.winfo_width() or 600
        canvas_h = self.canvas.winfo_height() or 500

        img_w, img_h = self.original_image.size
        self.scale_factor = min(canvas_w / img_w, canvas_h / img_h, 1.0)

        new_w = int(img_w * self.scale_factor)
        new_h = int(img_h * self.scale_factor)

        resized = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.tk_image, anchor=tk.CENTER)

        self.img_offset_x = (canvas_w - new_w) // 2
        self.img_offset_y = (canvas_h - new_h) // 2

    def on_canvas_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)

    def on_canvas_drag(self, event):
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
        self.selection_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y, outline="#00ff88", width=2, dash=(4, 4)
        )

    def on_canvas_release(self, event):
        if not self.image_path or self.start_x is None:
            return

        x1 = min(self.start_x, event.x) - self.img_offset_x
        y1 = min(self.start_y, event.y) - self.img_offset_y
        x2 = max(self.start_x, event.x) - self.img_offset_x
        y2 = max(self.start_y, event.y) - self.img_offset_y

        orig_x = int(x1 / self.scale_factor)
        orig_y = int(y1 / self.scale_factor)
        orig_w = int((x2 - x1) / self.scale_factor)
        orig_h = int((y2 - y1) / self.scale_factor)

        if orig_w < 10 or orig_h < 10:
            return

        self.status_var.set("Extracting text from selection...")
        self.root.update()

        region = (orig_x, orig_y, orig_w, orig_h)
        if self.ocr_engine.get() == "tesseract":
            text = extract_text_tesseract(self.image_path, region)
        else:
            text = extract_text_easyocr(self.image_path, region)

        self.ocr_text.insert(tk.END, text + "\n")
        self.status_var.set(f"Extracted {len(text)} chars from selection")

    def paste_selection_to_field(self, field_name):
        try:
            text = self.ocr_text.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
        except tk.TclError:
            text = self.ocr_text.get("1.0", tk.END).strip()

        if text and field_name in self.field_entries:
            self.field_entries[field_name].set(text)
            self.status_var.set(f"Pasted to '{field_name}'")

    def extract_full(self):
        if not self.image_path:
            messagebox.showinfo("No Image", "Load an image first.")
            return

        self.status_var.set("Running full OCR extraction...")
        self.root.update()

        if self.ocr_engine.get() == "tesseract":
            text = extract_text_tesseract(self.image_path)
        else:
            text = extract_text_easyocr(self.image_path)

        self.ocr_text.delete("1.0", tk.END)
        self.ocr_text.insert("1.0", text)
        self.status_var.set(f"Full extraction done — {len(text)} chars")

    def detect_and_fill(self):
        if not self.image_path:
            messagebox.showinfo("No Image", "Load an image first.")
            return

        self.status_var.set("Detecting text fields...")
        self.root.update()

        fields = detect_fields(self.image_path)
        if not fields:
            self.status_var.set("No fields detected")
            return

        self.ocr_text.delete("1.0", tk.END)
        for f in fields:
            line = f"[{f['conf']}%] ({f['x']},{f['y']}) {f['text']}"
            self.ocr_text.insert(tk.END, line + "\n")

        self._draw_field_boxes(fields)
        self.status_var.set(f"Detected {len(fields)} text regions")

    def _draw_field_boxes(self, fields):
        for f in fields:
            x = int(f["x"] * self.scale_factor) + self.img_offset_x
            y = int(f["y"] * self.scale_factor) + self.img_offset_y
            w = int(f["w"] * self.scale_factor)
            h = int(f["h"] * self.scale_factor)

            color = "#00ff88" if f["conf"] > 60 else "#ffaa00" if f["conf"] > 30 else "#ff4444"
            self.canvas.create_rectangle(x, y, x + w, y + h, outline=color, width=1)

    def save_entry(self):
        for name, var in self.field_entries.items():
            val = var.get().strip()
            if val:
                self.data_manager.update_field(name, val)

        if self.data_manager.save_current_entry():
            count = self.data_manager.get_entry_count()
            self.entry_count_var.set(f"Entries: {count}")
            self.clear_fields()
            self.status_var.set(f"Entry #{count} saved")
        else:
            messagebox.showinfo("Empty", "No data to save. Fill in some fields first.")

    def clear_fields(self):
        for var in self.field_entries.values():
            var.set("")
        self.ocr_text.delete("1.0", tk.END)
        self.status_var.set("Fields cleared")

    def export_csv(self):
        if self.data_manager.get_entry_count() == 0:
            messagebox.showinfo("No Data", "No entries to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.data_manager.export_csv(path)
            self.status_var.set(f"Exported {self.data_manager.get_entry_count()} entries to CSV")

    def export_json(self):
        if self.data_manager.get_entry_count() == 0:
            messagebox.showinfo("No Data", "No entries to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.data_manager.export_json(path)
            self.status_var.set(f"Exported {self.data_manager.get_entry_count()} entries to JSON")


def main():
    root = tk.Tk()
    app = TODEApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
