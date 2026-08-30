import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from models import FilterConfig, ProcessResult
from csv_processor import CSVAnalyzer, CSVReducer
from components import ScrollableFrame, PreviewTable

APP_TITLE = "Redutor de CSV"
PREVIEW_ROWS = 20


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("820x640")
        self.root.minsize(680, 420)

        self.csv_path: Optional[str] = None
        self.original_size: int = 0
        self.columns: list[str] = []
        self.progress_queue: queue.Queue = queue.Queue()

        self.analyzer = CSVAnalyzer()
        self.reducer = CSVReducer()

        self._init_variables()
        self._build_ui()

    def _init_variables(self):
        self.status_var = tk.StringVar(value="Pronto.")
        self.sep_var = tk.StringVar(value=",")
        self.enc_var = tk.StringVar(value="utf-8")
        self.excluir_linhas_var = tk.BooleanVar(value=False)
        self.start_row_var = tk.StringVar(value="1")
        self.end_row_var = tk.StringVar(value="1000")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom")

        scroll_container = ScrollableFrame(self.root)
        scroll_container.pack(fill="both", expand=True)
        content = scroll_container.content

        self._build_file_section(content, pad)
        self._build_config_section(content, pad)
        self._build_preview_section(content, pad)
        self._build_row_filter_section(content, pad)
        self._build_column_filter_section(content, pad)
        self._build_action_section(content, pad)
        self._build_result_section(content, pad)

    def _build_file_section(self, parent: ttk.Frame, pad: dict):
        file_frame = ttk.LabelFrame(parent, text="Arquivo")
        file_frame.pack(fill="x", **pad)

        ttk.Button(file_frame, text="Selecionar CSV...", command=self.selecionar_arquivo).grid(
            row=0, column=0, padx=8, pady=8
        )
        self.lbl_arquivo = ttk.Label(file_frame, text="Nenhum arquivo selecionado")
        self.lbl_arquivo.grid(row=0, column=1, sticky="w", padx=8)
        self.lbl_tamanho = ttk.Label(file_frame, text="")
        self.lbl_tamanho.grid(row=1, column=1, sticky="w", padx=8)

    def _build_config_section(self, parent: ttk.Frame, pad: dict):
        cfg_frame = ttk.LabelFrame(parent, text="Configuração de leitura")
        cfg_frame.pack(fill="x", **pad)

        ttk.Label(cfg_frame, text="Separador:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Combobox(
            cfg_frame, textvariable=self.sep_var, values=[",", ";", "\\t", "|"], width=6, state="readonly"
        ).grid(row=0, column=1, padx=8, sticky="w")

        ttk.Label(cfg_frame, text="Codificação:").grid(row=0, column=2, padx=8, sticky="w")
        ttk.Combobox(
            cfg_frame, textvariable=self.enc_var, values=["utf-8", "latin1", "utf-8-sig"], width=10, state="readonly"
        ).grid(row=0, column=3, padx=8, sticky="w")

        ttk.Button(cfg_frame, text="Carregar colunas / prévia", command=self.carregar_preview).grid(
            row=0, column=4, padx=8
        )
        ttk.Button(cfg_frame, text="Contar linhas", command=self.contar_linhas).grid(row=0, column=5, padx=8)

    def _build_preview_section(self, parent: ttk.Frame, pad: dict):
        preview_frame = ttk.LabelFrame(parent, text=f"Prévia ({PREVIEW_ROWS} primeiras linhas)")
        preview_frame.pack(fill="x", **pad)

        self.preview_table = PreviewTable(preview_frame, height=8)
        self.preview_table.pack(fill="both", padx=6, pady=6)

    def _build_row_filter_section(self, parent: ttk.Frame, pad: dict):
        rows_frame = ttk.LabelFrame(parent, text="1. Linhas para excluir")
        rows_frame.pack(fill="x", **pad)

        ttk.Checkbutton(rows_frame, text="Excluir intervalo de linhas", variable=self.excluir_linhas_var).grid(
            row=0, column=0, padx=8, pady=6, sticky="w"
        )
        ttk.Label(rows_frame, text="Linha inicial:").grid(row=0, column=1, sticky="e")
        ttk.Entry(rows_frame, textvariable=self.start_row_var, width=10).grid(row=0, column=2, padx=6)
        ttk.Label(rows_frame, text="Linha final:").grid(row=0, column=3, sticky="e")
        ttk.Entry(rows_frame, textvariable=self.end_row_var, width=10).grid(row=0, column=4, padx=6)
        ttk.Button(rows_frame, text="Até o final", command=self.preencher_ultima_linha).grid(row=0, column=5, padx=6)

    def _build_column_filter_section(self, parent: ttk.Frame, pad: dict):
        cols_frame = ttk.LabelFrame(parent, text="2. Colunas para excluir")
        cols_frame.pack(fill="x", **pad)

        btn_frame = ttk.Frame(cols_frame)
        btn_frame.pack(side="left", fill="y", padx=8, pady=8)
        ttk.Button(btn_frame, text="Marcar/Desmarcar todas", command=self.alternar_todas_colunas).pack(
            fill="x", pady=2
        )

        list_frame = ttk.Frame(cols_frame)
        list_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.cols_listbox = tk.Listbox(list_frame, selectmode="extended", height=6, exportselection=False)
        cols_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.cols_listbox.yview)
        self.cols_listbox.configure(yscrollcommand=cols_scroll.set)
        self.cols_listbox.pack(side="left", fill="both", expand=True)
        cols_scroll.pack(side="left", fill="y")

    def _build_action_section(self, parent: ttk.Frame, pad: dict):
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill="x", **pad)

        self.btn_processar = ttk.Button(
            action_frame, text="🚀 Processar e salvar", command=self.iniciar_processamento
        )
        self.btn_processar.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(action_frame, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

    def _build_result_section(self, parent: ttk.Frame, pad: dict):
        result_frame = ttk.LabelFrame(parent, text="Resultado")
        result_frame.pack(fill="x", **pad)

        self.lbl_resultado = ttk.Label(result_frame, text="—", justify="left")
        self.lbl_resultado.pack(padx=8, pady=8, anchor="w")

    def _get_real_delimiter(self) -> str:
        sep = self.sep_var.get()
        return "\t" if sep == "\\t" else sep

    def _reset_file_state(self):
        self.columns = []
        self.cols_listbox.delete(0, "end")
        self.preview_table.clear()
        self.lbl_resultado.config(text="—")

    def selecionar_arquivo(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")])
        if not path:
            return

        self.csv_path = path
        self.original_size = os.path.getsize(path)
        self.lbl_arquivo.config(text=os.path.basename(path))
        self.lbl_tamanho.config(text=f"Tamanho atual: {self.original_size / 1024 / 1024:.2f} MB")
        self._reset_file_state()

        encoding = self.analyzer.detect_encoding(path)
        self.enc_var.set(encoding)
        delimiter = self.analyzer.detect_delimiter(path, encoding)
        self.sep_var.set("\\t" if delimiter == "\t" else delimiter)

        self.status_var.set(
            f"Arquivo selecionado. Detectado: separador '{delimiter}', codificação '{encoding}'."
        )

    def carregar_preview(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return

        try:
            preview = self.analyzer.load_preview(
                file_path=self.csv_path,
                delimiter=self._get_real_delimiter(),
                encoding=self.enc_var.get(),
                max_rows=PREVIEW_ROWS,
            )
        except StopIteration:
            messagebox.showerror(APP_TITLE, "O arquivo parece estar vazio.")
            return
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Erro ao ler o CSV:\n{e}")
            return

        self.columns = preview.columns
        self.preview_table.update_data(preview.columns, preview.rows)

        self.cols_listbox.delete(0, "end")
        for col in self.columns:
            self.cols_listbox.insert("end", col)

        self.status_var.set(f"{len(self.columns)} colunas carregadas.")

    def alternar_todas_colunas(self):
        total = self.cols_listbox.size()
        if total == 0:
            return
        if len(self.cols_listbox.curselection()) == total:
            self.cols_listbox.select_clear(0, "end")
        else:
            self.cols_listbox.select_set(0, "end")

    def contar_linhas(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return
        total = self.analyzer.count_data_lines(self.csv_path)
        messagebox.showinfo(APP_TITLE, f"Aproximadamente {total:,} linhas de dados.".replace(",", "."))

    def preencher_ultima_linha(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return
        total = self.analyzer.count_data_lines(self.csv_path)
        self.end_row_var.set(str(total))
        self.status_var.set(f"Linha final preenchida com {total:,} (última linha do arquivo).".replace(",", "."))

    def _validate_filter_inputs(self) -> Optional[FilterConfig]:
        cols_excluir_idx = set(self.cols_listbox.curselection())
        keep_idx = [i for i in range(len(self.columns)) if i not in cols_excluir_idx]
        if not keep_idx:
            messagebox.showwarning(APP_TITLE, "Você excluiu todas as colunas — não sobra nada para salvar.")
            return None

        excluir_linhas = self.excluir_linhas_var.get()
        start_row = None
        end_row = None

        if excluir_linhas:
            try:
                start_row = int(self.start_row_var.get())
                end_row = int(self.end_row_var.get())
            except ValueError:
                messagebox.showerror(APP_TITLE, "Linha inicial/final precisam ser números inteiros.")
                return None

            if start_row > end_row:
                messagebox.showerror(APP_TITLE, "A linha inicial precisa ser menor ou igual à linha final.")
                return None
            if start_row < 1:
                messagebox.showerror(APP_TITLE, "A linha inicial precisa ser maior ou igual a 1.")
                return None

            total_linhas = self.analyzer.count_data_lines(self.csv_path)
            if end_row > total_linhas:
                messagebox.showerror(
                    APP_TITLE,
                    f"A linha final ({end_row}) é maior que o total de linhas do arquivo "
                    f"({total_linhas}).\n\nAjuste o intervalo ou use o botão 'Até o final'.",
                )
                return None

        return FilterConfig(
            keep_column_indices=keep_idx,
            delimiter=self._get_real_delimiter(),
            encoding=self.enc_var.get(),
            exclude_rows=excluir_linhas,
            start_row=start_row,
            end_row=end_row,
        )

    def iniciar_processamento(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return
        if not self.columns:
            messagebox.showwarning(APP_TITLE, "Clique em 'Carregar colunas / prévia' primeiro.")
            return

        config = self._validate_filter_inputs()
        if not config:
            return

        destino = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not destino:
            return

        self.btn_processar.config(state="disabled")
        self.progress.start(12)
        self.status_var.set("Processando...")

        threading.Thread(
            target=self._processar_worker,
            args=(self.csv_path, destino, config),
            daemon=True,
        ).start()
        self.root.after(100, self._poll_queue)

    def _processar_worker(self, input_path: str, output_path: str, config: FilterConfig):
        try:
            def on_progress(processed: int, written: int):
                self.progress_queue.put(("progress", processed, written))

            result = self.reducer.process(
                input_path=input_path,
                output_path=output_path,
                config=config,
                progress_callback=on_progress,
            )
            self.progress_queue.put(("done", result))
        except Exception as e:
            self.progress_queue.put(("error", str(e)))

    def _poll_queue(self):
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if msg[0] == "progress":
                    _, rp, rw = msg
                    self.status_var.set(f"Processando... {rp:,} linhas lidas, {rw:,} gravadas.".replace(",", "."))
                elif msg[0] == "done":
                    _, result = msg
                    self._finalizar(result)
                    return
                elif msg[0] == "error":
                    messagebox.showerror(APP_TITLE, f"Erro ao processar:\n{msg[1]}")
                    self._resetar_ui()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _finalizar(self, result: ProcessResult):
        texto = (
            f"Tamanho atual: {result.original_size/1024/1024:.2f} MB   →   "
            f"Tamanho final: {result.final_size/1024/1024:.2f} MB   ({result.reduction_percentage:.1f}% de redução)\n"
            f"Linhas lidas: {result.rows_processed:,}   |   Linhas gravadas: {result.rows_written:,}"
        ).replace(",", ".")
        self.lbl_resultado.config(text=texto)
        self.status_var.set("Concluído.")
        self._resetar_ui()
        messagebox.showinfo(APP_TITLE, "Arquivo processado e salvo com sucesso!")

    def _resetar_ui(self):
        self.progress.stop()
        self.btn_processar.config(state="normal")
