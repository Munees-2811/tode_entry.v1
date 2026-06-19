import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
from PIL import Image, ImageTk

from ocr_engine import (
    extract_text_tesseract,
    extract_text_easyocr,
    detect_fields,
    smart_parse_lines,
)
from pdf_handler import pdf_to_images, extract_pdf_text_native
from data_manager import DataManager


class TODEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TODE Entry v1 — CV Data Entry Automation")
        self.root.geometry("1280x850")
        self.root.minsize(1000, 650)

        self.data_manager = DataManager()
        self.image_path = None
        self.tk_image = None
        self.original_image = None
        self.selection_rect = None
        self.start_x = None
        self.start_y = None
        self.field_entries = {}
        self.field_rows = {}
        self.ocr_engine = tk.StringVar(value="tesseract")
        self.handwriting_mode = tk.BooleanVar(value=False)
        self.scale_factor = 1.0
        self.pdf_pages = []
        self.current_page = 0
        self.is_pdf = False
        self.pdf_path = None
        self.img_offset_x = 0
        self.img_offset_y = 0

        self._build_menu()
        self._build_toolbar()
        self._build_main_layout()
        self._build_statusbar()

    # ── Menu ──────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image/PDF...", command=self.load_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Export CSV...", command=self.export_csv)
        file_menu.add_command(label="Export Excel...", command=self.export_excel)
        file_menu.add_command(label="Export JSON...", command=self.export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        ocr_menu = tk.Menu(menubar, tearoff=0)
        ocr_menu.add_radiobutton(label="Tesseract", variable=self.ocr_engine, value="tesseract")
        ocr_menu.add_radiobutton(label="EasyOCR", variable=self.ocr_engine, value="easyocr")
        ocr_menu.add_separator()
        ocr_menu.add_checkbutton(label="Handwriting Mode", variable=self.handwriting_mode)
        menubar.add_cascade(label="OCR Engine", menu=ocr_menu)

        template_menu = tk.Menu(menubar, tearoff=0)
        for name in self.data_manager.get_template_names():
            template_menu.add_command(
                label=name, command=lambda n=name: self.apply_template(n)
            )
        template_menu.add_separator()
        template_menu.add_command(label="Save Current as Template...", command=self.save_as_template)
        menubar.add_cascade(label="Templates", menu=template_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="View All Entries...", command=self.show_entries_table)
        menubar.add_cascade(label="View", menu=view_menu)

        self.root.bind("<Control-o>", lambda e: self.load_file())
        self.root.bind("<Control-s>", lambda e: self.save_entry())
        self.root.bind("<Control-e>", lambda e: self.extract_full())

    # ── Toolbar ───────────────────────────────────────────────────────

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="Open File", command=self.load_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Extract All", command=self.extract_full).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Detect Fields", command=self.detect_and_fill).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Auto-Fill", command=self.auto_fill_fields).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="PDF Text", command=self.extract_pdf_native).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.hw_check = ttk.Checkbutton(toolbar, text="Handwriting", variable=self.handwriting_mode)
        self.hw_check.pack(side=tk.LEFT, padx=4)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(toolbar, text="Save Entry", command=self.save_entry).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Clear", command=self.clear_fields).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="View Entries", command=self.show_entries_table).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Label(toolbar, text="Add Field:").pack(side=tk.LEFT, padx=2)
        self.new_field_var = tk.StringVar()
        field_entry = ttk.Entry(toolbar, textvariable=self.new_field_var, width=15)
        field_entry.pack(side=tk.LEFT, padx=2)
        field_entry.bind("<Return>", lambda e: self.add_field())
        ttk.Button(toolbar, text="+", width=3, command=self.add_field).pack(side=tk.LEFT, padx=2)

        self.entry_count_var = tk.StringVar(value="Entries: 0")
        ttk.Label(toolbar, textvariable=self.entry_count_var, font=("", 10, "bold")).pack(side=tk.RIGHT, padx=10)

    # ── Main Layout ───────────────────────────────────────────────────

    def _build_main_layout(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.LabelFrame(main_pane, text="Image / PDF Preview", padding=5)
        main_pane.add(left_frame, weight=3)

        self.canvas = tk.Canvas(left_frame, bg="#1e1e1e", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        self.page_nav = ttk.Frame(left_frame)
        self.page_nav.pack(fill=tk.X, pady=(3, 0))
        ttk.Button(self.page_nav, text="< Prev", command=self.prev_page).pack(side=tk.LEFT, padx=2)
        self.page_label_var = tk.StringVar(value="")
        ttk.Label(self.page_nav, textvariable=self.page_label_var).pack(side=tk.LEFT, padx=10)
        ttk.Button(self.page_nav, text="Next >", command=self.next_page).pack(side=tk.LEFT, padx=2)
        self.page_nav.pack_forget()

        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=2)

        right_pane = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_pane.pack(fill=tk.BOTH, expand=True)

        # OCR output
        ocr_frame = ttk.LabelFrame(right_pane, text="OCR Output (select text, then paste to field)", padding=5)
        right_pane.add(ocr_frame, weight=1)

        self.ocr_text = scrolledtext.ScrolledText(ocr_frame, wrap=tk.WORD, height=8, font=("Consolas", 10))
        self.ocr_text.pack(fill=tk.BOTH, expand=True)

        # Custom entry panel
        entry_panel = ttk.LabelFrame(right_pane, text="Data Entry Panel", padding=5)
        right_pane.add(entry_panel, weight=2)

        self._build_entry_panel(entry_panel)

    def _build_entry_panel(self, parent):
        # Template selector row
        tmpl_row = ttk.Frame(parent)
        tmpl_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(tmpl_row, text="Template:").pack(side=tk.LEFT, padx=(0, 5))
        self.template_var = tk.StringVar(value="Form")
        tmpl_combo = ttk.Combobox(
            tmpl_row, textvariable=self.template_var,
            values=self.data_manager.get_template_names(), state="readonly", width=15
        )
        tmpl_combo.pack(side=tk.LEFT, padx=2)
        tmpl_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_template(self.template_var.get()))

        ttk.Button(tmpl_row, text="Apply", command=lambda: self.apply_template(self.template_var.get())).pack(side=tk.LEFT, padx=2)

        # Source file label
        self.source_label_var = tk.StringVar(value="No file loaded")
        ttk.Label(tmpl_row, textvariable=self.source_label_var, foreground="gray").pack(side=tk.RIGHT, padx=5)

        # Scrollable fields area
        field_outer = ttk.Frame(parent)
        field_outer.pack(fill=tk.BOTH, expand=True)

        self.field_canvas = tk.Canvas(field_outer, highlightthickness=0)
        field_scrollbar = ttk.Scrollbar(field_outer, orient=tk.VERTICAL, command=self.field_canvas.yview)
        self.fields_container = ttk.Frame(self.field_canvas)
        self.fields_container.bind(
            "<Configure>", lambda e: self.field_canvas.configure(scrollregion=self.field_canvas.bbox("all"))
        )
        self.field_canvas.create_window((0, 0), window=self.fields_container, anchor="nw")
        self.field_canvas.configure(yscrollcommand=field_scrollbar.set)

        self.field_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        field_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._add_default_fields()

        # Bottom action bar
        action_bar = ttk.Frame(parent)
        action_bar.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(action_bar, text="Save Entry (Ctrl+S)", command=self.save_entry).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_bar, text="Clear All", command=self.clear_fields).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_bar, text="Auto-Fill from OCR", command=self.auto_fill_fields).pack(side=tk.LEFT, padx=2)

        export_frame = ttk.LabelFrame(action_bar, text="Export", padding=2)
        export_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Button(export_frame, text="CSV", command=self.export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(export_frame, text="Excel", command=self.export_excel).pack(side=tk.LEFT, padx=2)
        ttk.Button(export_frame, text="JSON", command=self.export_json).pack(side=tk.LEFT, padx=2)

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Ready — Load an image or PDF to get started")
        status = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=3)
        status.pack(side=tk.BOTTOM, fill=tk.X)

    # ── Field Management ──────────────────────────────────────────────

    def _add_default_fields(self):
        for name in ["Name", "Date", "Amount", "Description", "Reference"]:
            self._create_field_row(name)

    def _create_field_row(self, name):
        if name in self.field_entries:
            return

        row = ttk.Frame(self.fields_container)
        row.pack(fill=tk.X, pady=2, padx=2)

        lbl = ttk.Label(row, text=name + ":", width=18, anchor=tk.E, font=("", 9, "bold"))
        lbl.pack(side=tk.LEFT, padx=(0, 5))

        var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=var, font=("", 10))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            row, text="Paste", width=5,
            command=lambda n=name: self.paste_selection_to_field(n)
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            row, text="X", width=3,
            command=lambda n=name, r=row: self.remove_field(n, r)
        ).pack(side=tk.LEFT)

        self.field_entries[name] = var
        self.field_rows[name] = row

    def remove_field(self, name, row):
        row.destroy()
        self.field_entries.pop(name, None)
        self.field_rows.pop(name, None)

    def add_field(self):
        name = self.new_field_var.get().strip()
        if not name:
            return
        if name in self.field_entries:
            messagebox.showwarning("Duplicate", f"Field '{name}' already exists.")
            return
        self._create_field_row(name)
        self.new_field_var.set("")

    def apply_template(self, template_name):
        fields = self.data_manager.get_template_fields(template_name)
        if not fields:
            return

        for name in list(self.field_entries.keys()):
            if name in self.field_rows:
                self.field_rows[name].destroy()
        self.field_entries.clear()
        self.field_rows.clear()

        for name in fields:
            self._create_field_row(name)

        self.template_var.set(template_name)
        self.status_var.set(f"Applied template: {template_name} ({len(fields)} fields)")

    def save_as_template(self):
        if not self.field_entries:
            messagebox.showinfo("No Fields", "Add some fields first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Save Template")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Template name:").pack(padx=10, pady=(15, 5))
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.pack(padx=10)
        name_entry.focus()

        def do_save():
            name = name_var.get().strip()
            if name:
                self.data_manager.save_template(name, list(self.field_entries.keys()))
                self.status_var.set(f"Template '{name}' saved")
                dialog.destroy()

        name_entry.bind("<Return>", lambda e: do_save())
        ttk.Button(dialog, text="Save", command=do_save).pack(pady=10)

    # ── File Loading ──────────────────────────────────────────────────

    def load_file(self):
        path = filedialog.askopenfilename(
            title="Select Image or PDF",
            filetypes=[
                ("All supported", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp *.pdf"),
                ("PDF files", "*.pdf"),
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        if path.lower().endswith(".pdf"):
            self._load_pdf(path)
        else:
            self._load_image(path)

    def _load_image(self, path):
        self.is_pdf = False
        self.pdf_pages = []
        self.pdf_path = None
        self.page_nav.pack_forget()

        self.image_path = path
        self.original_image = Image.open(path)
        self._display_image()
        self.source_label_var.set(os.path.basename(path))
        self.status_var.set(f"Loaded: {os.path.basename(path)}")

    def _load_pdf(self, path):
        self.status_var.set("Converting PDF pages...")
        self.root.update()

        try:
            self.pdf_pages = pdf_to_images(path)
        except ImportError as e:
            messagebox.showerror("Missing Dependency", str(e))
            return
        except Exception as e:
            messagebox.showerror("PDF Error", f"Failed to load PDF:\n{e}")
            return

        if not self.pdf_pages:
            messagebox.showinfo("Empty PDF", "No pages found in this PDF.")
            return

        self.is_pdf = True
        self.pdf_path = path
        self.current_page = 0
        self._show_pdf_page(0)

        self.page_nav.pack(fill=tk.X, pady=(3, 0))
        self.source_label_var.set(f"{os.path.basename(path)} ({len(self.pdf_pages)} pages)")
        self.status_var.set(f"Loaded PDF: {os.path.basename(path)} — {len(self.pdf_pages)} pages")

    def _show_pdf_page(self, page_idx):
        if not self.pdf_pages or page_idx < 0 or page_idx >= len(self.pdf_pages):
            return
        self.current_page = page_idx
        page_info = self.pdf_pages[page_idx]
        self.image_path = page_info["path"]
        self.original_image = Image.open(page_info["path"])
        self._display_image()
        self.page_label_var.set(f"Page {page_idx + 1} / {len(self.pdf_pages)}")

    def prev_page(self):
        if self.is_pdf and self.current_page > 0:
            self._show_pdf_page(self.current_page - 1)

    def next_page(self):
        if self.is_pdf and self.current_page < len(self.pdf_pages) - 1:
            self._show_pdf_page(self.current_page + 1)

    # ── Image Display ─────────────────────────────────────────────────

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

    # ── Canvas Selection ──────────────────────────────────────────────

    def on_canvas_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)

    def on_canvas_drag(self, event):
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
        self.selection_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline="#00ff88", width=2, dash=(4, 4)
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

        hw = self.handwriting_mode.get()
        mode_label = " (handwriting)" if hw else ""
        self.status_var.set(f"Extracting text from selection{mode_label}...")
        self.root.update()

        region = (orig_x, orig_y, orig_w, orig_h)
        if self.ocr_engine.get() == "tesseract":
            text = extract_text_tesseract(self.image_path, region, handwriting=hw)
        else:
            text = extract_text_easyocr(self.image_path, region, handwriting=hw)

        self.ocr_text.insert(tk.END, text + "\n")
        self.status_var.set(f"Extracted {len(text)} chars{mode_label}")

    # ── OCR Actions ───────────────────────────────────────────────────

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

        hw = self.handwriting_mode.get()
        mode_label = " (handwriting mode)" if hw else ""
        self.status_var.set(f"Running full OCR extraction{mode_label}...")
        self.root.update()

        if self.ocr_engine.get() == "tesseract":
            text = extract_text_tesseract(self.image_path, handwriting=hw)
        else:
            text = extract_text_easyocr(self.image_path, handwriting=hw)

        self.ocr_text.delete("1.0", tk.END)
        self.ocr_text.insert("1.0", text)
        self.status_var.set(f"Extraction done — {len(text)} chars{mode_label}")

    def extract_pdf_native(self):
        if not self.is_pdf or not self.pdf_path:
            messagebox.showinfo("No PDF", "Load a PDF file first.")
            return

        self.status_var.set("Extracting native PDF text...")
        self.root.update()

        text = extract_pdf_text_native(self.pdf_path, page_num=self.current_page)
        if not text:
            text = "(No embedded text found — try OCR extraction instead)"

        self.ocr_text.delete("1.0", tk.END)
        self.ocr_text.insert("1.0", text)
        self.status_var.set(f"PDF text — Page {self.current_page + 1} — {len(text)} chars")

    def detect_and_fill(self):
        if not self.image_path:
            messagebox.showinfo("No Image", "Load an image first.")
            return

        hw = self.handwriting_mode.get()
        self.status_var.set("Detecting text fields...")
        self.root.update()

        fields = detect_fields(self.image_path, handwriting=hw)
        if not fields:
            self.status_var.set("No fields detected")
            return

        self.ocr_text.delete("1.0", tk.END)
        for f in fields:
            line = f"[{f['conf']}%] ({f['x']},{f['y']}) {f['text']}"
            self.ocr_text.insert(tk.END, line + "\n")

        self._draw_field_boxes(fields)
        self.status_var.set(f"Detected {len(fields)} text regions")

    def auto_fill_fields(self):
        raw = self.ocr_text.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showinfo("No Text", "Run OCR extraction first, then auto-fill.")
            return

        parsed = smart_parse_lines(raw)

        if not parsed:
            words = raw.split()
            field_names = list(self.field_entries.keys())
            for i, name in enumerate(field_names):
                if i < len(words):
                    self.field_entries[name].set(words[i])
            self.status_var.set(f"Auto-filled {min(len(words), len(field_names))} fields (word-split)")
            return

        filled = 0
        for key, val in parsed.items():
            best_match = None
            for field_name in self.field_entries:
                if key.lower() in field_name.lower() or field_name.lower() in key.lower():
                    best_match = field_name
                    break

            if best_match:
                self.field_entries[best_match].set(val)
                filled += 1
            else:
                self._create_field_row(key)
                self.field_entries[key].set(val)
                filled += 1

        self.status_var.set(f"Auto-filled {filled} fields from OCR text")

    def _draw_field_boxes(self, fields):
        for f in fields:
            x = int(f["x"] * self.scale_factor) + self.img_offset_x
            y = int(f["y"] * self.scale_factor) + self.img_offset_y
            w = int(f["w"] * self.scale_factor)
            h = int(f["h"] * self.scale_factor)

            color = "#00ff88" if f["conf"] > 60 else "#ffaa00" if f["conf"] > 30 else "#ff4444"
            self.canvas.create_rectangle(x, y, x + w, y + h, outline=color, width=1)

    # ── Entry Management ──────────────────────────────────────────────

    def save_entry(self):
        for name, var in self.field_entries.items():
            val = var.get().strip()
            if val:
                self.data_manager.update_field(name, val)

        if self.image_path:
            self.data_manager.update_field("_source_file", os.path.basename(self.image_path))

        if self.data_manager.save_current_entry():
            count = self.data_manager.get_entry_count()
            self.entry_count_var.set(f"Entries: {count}")
            self.clear_fields()
            self.status_var.set(f"Entry #{count} saved successfully")
        else:
            messagebox.showinfo("Empty", "No data to save. Fill in some fields first.")

    def clear_fields(self):
        for var in self.field_entries.values():
            var.set("")
        self.ocr_text.delete("1.0", tk.END)
        self.status_var.set("Fields cleared")

    # ── Entries Table Viewer ──────────────────────────────────────────

    def show_entries_table(self):
        if self.data_manager.get_entry_count() == 0:
            messagebox.showinfo("No Entries", "No entries saved yet.")
            return

        table_win = tk.Toplevel(self.root)
        table_win.title(f"All Entries ({self.data_manager.get_entry_count()} records)")
        table_win.geometry("900x500")
        table_win.transient(self.root)

        toolbar = ttk.Frame(table_win, padding=5)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export Excel", command=self.export_excel).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export JSON", command=self.export_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Selected", command=lambda: self._delete_selected(tree, table_win)).pack(side=tk.RIGHT, padx=2)

        columns = self.data_manager.get_all_field_names()
        if not columns:
            columns = ["(empty)"]

        tree_frame = ttk.Frame(table_win)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        tree = ttk.Treeview(
            tree_frame, columns=["#"] + columns, show="headings",
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )
        y_scroll.config(command=tree.yview)
        x_scroll.config(command=tree.xview)

        tree.heading("#", text="#")
        tree.column("#", width=40, anchor=tk.CENTER)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor=tk.W)

        for idx, entry in enumerate(self.data_manager.entries):
            values = [idx + 1] + [entry.get(c, "") for c in columns]
            tag = "even" if idx % 2 == 0 else "odd"
            tree.insert("", tk.END, values=values, tags=(tag,))

        tree.tag_configure("even", background="#f0f0f0")
        tree.tag_configure("odd", background="#ffffff")

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    def _delete_selected(self, tree, window):
        selected = tree.selection()
        if not selected:
            return

        if not messagebox.askyesno("Confirm", f"Delete {len(selected)} entry(ies)?", parent=window):
            return

        indices = []
        for item in selected:
            values = tree.item(item, "values")
            indices.append(int(values[0]) - 1)

        for idx in sorted(indices, reverse=True):
            self.data_manager.delete_entry(idx)

        self.entry_count_var.set(f"Entries: {self.data_manager.get_entry_count()}")
        window.destroy()
        self.show_entries_table()

    # ── Export ─────────────────────────────────────────────────────────

    def export_csv(self):
        if self.data_manager.get_entry_count() == 0:
            messagebox.showinfo("No Data", "No entries to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.data_manager.export_csv(path)
            self.status_var.set(f"Exported {self.data_manager.get_entry_count()} entries to CSV")

    def export_excel(self):
        if self.data_manager.get_entry_count() == 0:
            messagebox.showinfo("No Data", "No entries to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            try:
                self.data_manager.export_excel(path)
                self.status_var.set(f"Exported {self.data_manager.get_entry_count()} entries to Excel")
            except ImportError as e:
                messagebox.showerror("Missing Dependency", str(e))

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
