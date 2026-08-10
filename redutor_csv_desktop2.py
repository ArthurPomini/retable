"""
Redutor de CSV - versão desktop (Tkinter)
------------------------------------------
Não depende de pandas/numpy nem de servidor web: lê e grava o CSV
linha a linha usando só a biblioteca padrão do Python (módulo csv).
Isso deixa o uso de memória praticamente constante, não importa o
tamanho do arquivo, e o executável final bem mais leve.
"""

import os
import csv
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Redutor de CSV"
PREVIEW_ROWS = 20
STATUS_A_CADA = 20_000  # atualiza o status na tela a cada N linhas processadas


class RedutorCSVApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("820x640")
        self.root.minsize(680, 420)

        self.csv_path = None
        self.original_size = 0
        self.columns = []
        self.progress_queue = queue.Queue()

        self._build_ui()

    # ---------------------------------------------------------- UI
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # Barra de status fica fixa embaixo, fora da área rolável
        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom")

        # ---- Área rolável (canvas + scrollbar vertical) para o resto do conteúdo ----
        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        content = ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _atualizar_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _ajustar_largura(event):
            canvas.itemconfig(content_window, width=event.width)

        content.bind("<Configure>", _atualizar_scrollregion)
        canvas.bind("<Configure>", _ajustar_largura)

        def _on_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            canvas.yview_scroll(int(delta), "units")

        def _ligar_scroll(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _desligar_scroll(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _ligar_scroll)
        canvas.bind("<Leave>", _desligar_scroll)

        # A partir daqui, todo o conteúdo é filho de `content` (não mais de self.root)

        # --- Arquivo ---
        file_frame = ttk.LabelFrame(content, text="Arquivo")
        file_frame.pack(fill="x", **pad)
        ttk.Button(file_frame, text="Selecionar CSV...", command=self.selecionar_arquivo).grid(
            row=0, column=0, padx=8, pady=8
        )
        self.lbl_arquivo = ttk.Label(file_frame, text="Nenhum arquivo selecionado")
        self.lbl_arquivo.grid(row=0, column=1, sticky="w", padx=8)
        self.lbl_tamanho = ttk.Label(file_frame, text="")
        self.lbl_tamanho.grid(row=1, column=1, sticky="w", padx=8)

        # --- Configuração de leitura ---
        cfg_frame = ttk.LabelFrame(content, text="Configuração de leitura")
        cfg_frame.pack(fill="x", **pad)

        ttk.Label(cfg_frame, text="Separador:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.sep_var = tk.StringVar(value=",")
        ttk.Combobox(
            cfg_frame, textvariable=self.sep_var, values=[",", ";", "\\t", "|"], width=6, state="readonly"
        ).grid(row=0, column=1, padx=8, sticky="w")

        ttk.Label(cfg_frame, text="Codificação:").grid(row=0, column=2, padx=8, sticky="w")
        self.enc_var = tk.StringVar(value="utf-8")
        ttk.Combobox(
            cfg_frame, textvariable=self.enc_var, values=["utf-8", "latin1", "utf-8-sig"], width=10, state="readonly"
        ).grid(row=0, column=3, padx=8, sticky="w")

        ttk.Button(cfg_frame, text="Carregar colunas / prévia", command=self.carregar_preview).grid(
            row=0, column=4, padx=8
        )
        ttk.Button(cfg_frame, text="Contar linhas", command=self.contar_linhas).grid(row=0, column=5, padx=8)

        # --- Prévia ---
        preview_frame = ttk.LabelFrame(content, text=f"Prévia ({PREVIEW_ROWS} primeiras linhas)")
        preview_frame.pack(fill="x", **pad)
        tree_container = ttk.Frame(preview_frame)
        tree_container.pack(fill="both", padx=6, pady=6)
        self.tree = ttk.Treeview(tree_container, show="headings", height=8)
        tree_vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        tree_hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=tree_vsb.set, xscroll=tree_hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_vsb.grid(row=0, column=1, sticky="ns")
        tree_hsb.grid(row=1, column=0, sticky="ew")
        tree_container.columnconfigure(0, weight=1)

        # --- Linhas a excluir ---
        rows_frame = ttk.LabelFrame(content, text="1. Linhas para excluir")
        rows_frame.pack(fill="x", **pad)
        self.excluir_linhas_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(rows_frame, text="Excluir intervalo de linhas", variable=self.excluir_linhas_var).grid(
            row=0, column=0, padx=8, pady=6, sticky="w"
        )
        ttk.Label(rows_frame, text="Linha inicial:").grid(row=0, column=1, sticky="e")
        self.start_row_var = tk.StringVar(value="1")
        ttk.Entry(rows_frame, textvariable=self.start_row_var, width=10).grid(row=0, column=2, padx=6)
        ttk.Label(rows_frame, text="Linha final:").grid(row=0, column=3, sticky="e")
        self.end_row_var = tk.StringVar(value="1000")
        ttk.Entry(rows_frame, textvariable=self.end_row_var, width=10).grid(row=0, column=4, padx=6)
        ttk.Button(rows_frame, text="Até o final", command=self.preencher_ultima_linha).grid(row=0, column=5, padx=6)

        # --- Colunas a excluir ---
        cols_frame = ttk.LabelFrame(content, text="2. Colunas para excluir")
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

        # --- Ação ---
        action_frame = ttk.Frame(content)
        action_frame.pack(fill="x", **pad)
        self.btn_processar = ttk.Button(action_frame, text="🚀 Processar e salvar", command=self.iniciar_processamento)
        self.btn_processar.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(action_frame, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        # --- Resultado ---
        result_frame = ttk.LabelFrame(content, text="Resultado")
        result_frame.pack(fill="x", **pad)
        self.lbl_resultado = ttk.Label(result_frame, text="—", justify="left")
        self.lbl_resultado.pack(padx=8, pady=8, anchor="w")

    # ------------------------------------------------------ Auxiliares
    def _sep_real(self):
        s = self.sep_var.get()
        return "\t" if s == "\\t" else s

    def _resetar_estado_arquivo(self):
        self.columns = []
        self.cols_listbox.delete(0, "end")
        self.tree.delete(*self.tree.get_children())
        self.lbl_resultado.config(text="—")

    # ------------------------------------------------------ Detecção automática
    def _detectar_encoding(self, path):
        with open(path, "rb") as f:
            amostra = f.read(65536)
        if amostra.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        try:
            amostra.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "latin1"

    def _detectar_separador(self, path, encoding):
        candidatos = [",", ";", "\t", "|"]
        try:
            with open(path, "r", newline="", encoding=encoding, errors="replace") as f:
                amostra = f.read(65536)
            dialect = csv.Sniffer().sniff(amostra, delimiters="".join(candidatos))
            if dialect.delimiter in candidatos:
                return dialect.delimiter
        except Exception:
            pass
        return ","

    def _contar_linhas_dados(self):
        """Conta as linhas de dados do arquivo (sem o cabeçalho), lendo em blocos de bytes."""
        total_quebras = 0
        with open(self.csv_path, "rb") as f:
            for bloco in iter(lambda: f.read(1024 * 1024), b""):
                total_quebras += bloco.count(b"\n")
        return max(total_quebras - 1, 0)

    # ------------------------------------------------------ Ações
    def selecionar_arquivo(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")])
        if not path:
            return
        self.csv_path = path
        self.original_size = os.path.getsize(path)
        self.lbl_arquivo.config(text=os.path.basename(path))
        self.lbl_tamanho.config(text=f"Tamanho atual: {self.original_size / 1024 / 1024:.2f} MB")
        self._resetar_estado_arquivo()

        encoding_detectado = self._detectar_encoding(path)
        self.enc_var.set(encoding_detectado)
        separador_detectado = self._detectar_separador(path, encoding_detectado)
        self.sep_var.set("\\t" if separador_detectado == "\t" else separador_detectado)

        self.status_var.set(
            f"Arquivo selecionado. Detectado automaticamente: separador "
            f"'{separador_detectado}', codificação '{encoding_detectado}' (confira e ajuste se precisar)."
        )

    def carregar_preview(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return
        try:
            with open(self.csv_path, "r", newline="", encoding=self.enc_var.get()) as f:
                reader = csv.reader(f, delimiter=self._sep_real())
                header = next(reader)
                linhas = []
                for i, row in enumerate(reader):
                    if i >= PREVIEW_ROWS:
                        break
                    linhas.append(row)
        except StopIteration:
            messagebox.showerror(APP_TITLE, "O arquivo parece estar vazio.")
            return
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Erro ao ler o CSV:\n{e}")
            return

        self.columns = header

        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = self.columns
        for c in self.columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110, stretch=False)
        for row in linhas:
            self.tree.insert("", "end", values=row)

        self.cols_listbox.delete(0, "end")
        for c in self.columns:
            self.cols_listbox.insert("end", c)

        self.status_var.set(f"{len(self.columns)} colunas carregadas.")

    def alternar_todas_colunas(self):
        total = self.cols_listbox.size()
        if total == 0:
            return
        selecionadas = len(self.cols_listbox.curselection())
        if selecionadas == total:
            self.cols_listbox.select_clear(0, "end")
        else:
            self.cols_listbox.select_set(0, "end")

    def contar_linhas(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return
        total = self._contar_linhas_dados()
        messagebox.showinfo(APP_TITLE, f"Aproximadamente {total:,} linhas de dados.".replace(",", "."))

    def preencher_ultima_linha(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return
        total = self._contar_linhas_dados()
        self.end_row_var.set(str(total))
        self.status_var.set(f"Linha final preenchida com {total:,} (última linha do arquivo).".replace(",", "."))

    def iniciar_processamento(self):
        if not self.csv_path:
            messagebox.showwarning(APP_TITLE, "Selecione um arquivo CSV primeiro.")
            return
        if not self.columns:
            messagebox.showwarning(APP_TITLE, "Clique em 'Carregar colunas / prévia' primeiro.")
            return

        cols_excluir_idx = set(self.cols_listbox.curselection())
        keep_idx = [i for i in range(len(self.columns)) if i not in cols_excluir_idx]
        if not keep_idx:
            messagebox.showwarning(APP_TITLE, "Você excluiu todas as colunas — não sobra nada para salvar.")
            return

        excluir_linhas = self.excluir_linhas_var.get()
        start_row = end_row = None
        if excluir_linhas:
            try:
                start_row = int(self.start_row_var.get())
                end_row = int(self.end_row_var.get())
            except ValueError:
                messagebox.showerror(APP_TITLE, "Linha inicial/final precisam ser números inteiros.")
                return
            if start_row > end_row:
                messagebox.showerror(APP_TITLE, "A linha inicial precisa ser menor ou igual à linha final.")
                return
            if start_row < 1:
                messagebox.showerror(APP_TITLE, "A linha inicial precisa ser maior ou igual a 1.")
                return

            total_linhas = self._contar_linhas_dados()
            if end_row > total_linhas:
                messagebox.showerror(
                    APP_TITLE,
                    f"A linha final ({end_row}) é maior que o total de linhas do arquivo "
                    f"({total_linhas}).\n\nAjuste o intervalo ou use o botão 'Até o final'.",
                )
                return

        destino = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not destino:
            return

        sep = self._sep_real()
        encoding = self.enc_var.get()

        self.btn_processar.config(state="disabled")
        self.progress.start(12)
        self.status_var.set("Processando...")

        threading.Thread(
            target=self._processar_worker,
            args=(destino, keep_idx, excluir_linhas, start_row, end_row, sep, encoding),
            daemon=True,
        ).start()
        self.root.after(100, self._poll_queue)

    # ------------------------------------------------------ Worker (thread separada)
    def _processar_worker(self, destino, keep_idx, excluir_linhas, start_row, end_row, sep, encoding):
        rows_processed = 0
        rows_written = 0
        try:
            lo = (start_row - 1) if excluir_linhas else None
            hi = (end_row - 1) if excluir_linhas else None

            with open(self.csv_path, "r", newline="", encoding=encoding) as fin, \
                 open(destino, "w", newline="", encoding=encoding) as fout:
                reader = csv.reader(fin, delimiter=sep)
                writer = csv.writer(fout, delimiter=sep)

                header = next(reader)
                writer.writerow([header[i] for i in keep_idx])

                for i, row in enumerate(reader):
                    rows_processed += 1
                    if excluir_linhas and lo <= i <= hi:
                        continue
                    writer.writerow([row[j] for j in keep_idx if j < len(row)])
                    rows_written += 1

                    if rows_processed % STATUS_A_CADA == 0:
                        self.progress_queue.put(("progress", rows_processed, rows_written))

            result_size = os.path.getsize(destino)
            self.progress_queue.put(("done", rows_processed, rows_written, result_size))
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
                    _, rp, rw, result_size = msg
                    self._finalizar(rp, rw, result_size)
                    return
                elif msg[0] == "error":
                    messagebox.showerror(APP_TITLE, f"Erro ao processar:\n{msg[1]}")
                    self._resetar_ui()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _finalizar(self, rows_processed, rows_written, result_size):
        reducao = (1 - result_size / self.original_size) * 100 if self.original_size else 0
        texto = (
            f"Tamanho atual: {self.original_size/1024/1024:.2f} MB   →   "
            f"Tamanho final: {result_size/1024/1024:.2f} MB   ({reducao:.1f}% de redução)\n"
            f"Linhas lidas: {rows_processed:,}   |   Linhas gravadas: {rows_written:,}"
        ).replace(",", ".")
        self.lbl_resultado.config(text=texto)
        self.status_var.set("Concluído.")
        self._resetar_ui()
        messagebox.showinfo(APP_TITLE, "Arquivo processado e salvo com sucesso!")

    def _resetar_ui(self):
        self.progress.stop()
        self.btn_processar.config(state="normal")


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    RedutorCSVApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
