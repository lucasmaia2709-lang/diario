import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime
import os
import shutil

# --- Configuração do Banco de Dados ---
class Database:
    def __init__(self, db_name="diario_obra.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Tabela de Obras
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS obras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                endereco TEXT,
                inicio TEXT
            )
        """)
        # Tabela de Relatórios Diários
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS relatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obra_id INTEGER,
                data TEXT,
                clima TEXT,
                condicao_tempo TEXT,
                atividades TEXT,
                obs_gerais TEXT,
                FOREIGN KEY(obra_id) REFERENCES obras(id)
            )
        """)
        # Tabela de Efetivo (Mão de Obra no dia)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS efetivo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relatorio_id INTEGER,
                funcao TEXT,
                quantidade INTEGER,
                FOREIGN KEY(relatorio_id) REFERENCES relatorios(id)
            )
        """)
        # Tabela de Fotos
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fotos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relatorio_id INTEGER,
                caminho_arquivo TEXT,
                descricao TEXT,
                FOREIGN KEY(relatorio_id) REFERENCES relatorios(id)
            )
        """)
        self.conn.commit()

    def get_obras(self):
        self.cursor.execute("SELECT id, nome FROM obras")
        return self.cursor.fetchall()

    def add_obra(self, nome, endereco):
        data_inicio = datetime.date.today().strftime("%d/%m/%Y")
        self.cursor.execute("INSERT INTO obras (nome, endereco, inicio) VALUES (?, ?, ?)", (nome, endereco, data_inicio))
        self.conn.commit()

    def save_relatorio(self, obra_id, data, clima, condicao, atividades, obs, efetivo_lista, fotos_lista):
        try:
            # 1. Salvar ou Atualizar Relatório Principal
            # Verifica se já existe relatório para essa obra nesta data
            self.cursor.execute("SELECT id FROM relatorios WHERE obra_id = ? AND data = ?", (obra_id, data))
            existente = self.cursor.fetchone()
            
            relatorio_id = None
            
            if existente:
                relatorio_id = existente[0]
                self.cursor.execute("""
                    UPDATE relatorios SET clima=?, condicao_tempo=?, atividades=?, obs_gerais=?
                    WHERE id=?
                """, (clima, condicao, atividades, obs, relatorio_id))
                # Limpar dados antigos vinculados para reescrever
                self.cursor.execute("DELETE FROM efetivo WHERE relatorio_id=?", (relatorio_id,))
                self.cursor.execute("DELETE FROM fotos WHERE relatorio_id=?", (relatorio_id,))
            else:
                self.cursor.execute("""
                    INSERT INTO relatorios (obra_id, data, clima, condicao_tempo, atividades, obs_gerais)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (obra_id, data, clima, condicao, atividades, obs))
                relatorio_id = self.cursor.lastrowid

            # 2. Salvar Efetivo
            for funcao, qtd in efetivo_lista:
                if qtd > 0:
                    self.cursor.execute("INSERT INTO efetivo (relatorio_id, funcao, quantidade) VALUES (?, ?, ?)", 
                                        (relatorio_id, funcao, qtd))

            # 3. Salvar Fotos
            for caminho, desc in fotos_lista:
                self.cursor.execute("INSERT INTO fotos (relatorio_id, caminho_arquivo, descricao) VALUES (?, ?, ?)",
                                    (relatorio_id, caminho, desc))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao salvar: {e}")
            return False

# --- Interface Gráfica (GUI) ---
class DiarioObraApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Diário de Obra (RDO)")
        self.geometry("900x700")
        self.db = Database()
        
        # Variáveis Globais
        self.obra_selecionada = tk.StringVar()
        self.id_obra_selecionada = None
        self.data_atual = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%Y"))
        
        self.setup_ui()

    def setup_ui(self):
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- Frame Superior: Seleção de Obra ---
        frame_top = ttk.Frame(self, padding="10")
        frame_top.pack(fill=tk.X)

        ttk.Label(frame_top, text="Selecione a Obra:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.combo_obras = ttk.Combobox(frame_top, textvariable=self.obra_selecionada, width=40, state="readonly")
        self.combo_obras.pack(side=tk.LEFT, padx=5)
        self.atualizar_lista_obras()
        self.combo_obras.bind("<<ComboboxSelected>>", self.ao_selecionar_obra)

        ttk.Button(frame_top, text="+ Nova Obra", command=self.janela_nova_obra).pack(side=tk.LEFT, padx=10)

        ttk.Label(frame_top, text="Data do Relatório:").pack(side=tk.LEFT, padx=10)
        self.entry_data = ttk.Entry(frame_top, textvariable=self.data_atual, width=12)
        self.entry_data.pack(side=tk.LEFT)

        # --- Abas Principais ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Aba 1: Geral
        self.tab_geral = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_geral, text='1. Informações Gerais')
        self.montar_tab_geral()

        # Aba 2: Efetivo (Mão de Obra)
        self.tab_efetivo = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_efetivo, text='2. Efetivo/Equipe')
        self.montar_tab_efetivo()

        # Aba 3: Fotos
        self.tab_fotos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_fotos, text='3. Fotos e Anexos')
        self.montar_tab_fotos()

        # Aba 4: Exportar/Resumo
        self.tab_resumo = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_resumo, text='4. Visualizar & Salvar')
        self.montar_tab_resumo()

    def atualizar_lista_obras(self):
        obras = self.db.get_obras() # Lista de tuplas (id, nome)
        self.mapa_obras = {nome: id for id, nome in obras}
        self.combo_obras['values'] = list(self.mapa_obras.keys())

    def ao_selecionar_obra(self, event):
        nome = self.obra_selecionada.get()
        self.id_obra_selecionada = self.mapa_obras.get(nome)
        messagebox.showinfo("Obra Selecionada", f"Trabalhando na obra: {nome}")

    def janela_nova_obra(self):
        top = tk.Toplevel(self)
        top.title("Cadastrar Nova Obra")
        top.geometry("400x200")

        ttk.Label(top, text="Nome da Obra:").pack(pady=5)
        entry_nome = ttk.Entry(top, width=40)
        entry_nome.pack(pady=5)

        ttk.Label(top, text="Endereço:").pack(pady=5)
        entry_end = ttk.Entry(top, width=40)
        entry_end.pack(pady=5)

        def salvar():
            nome = entry_nome.get()
            end = entry_end.get()
            if nome:
                self.db.add_obra(nome, end)
                self.atualizar_lista_obras()
                top.destroy()
                messagebox.showinfo("Sucesso", "Obra cadastrada!")
            else:
                messagebox.showwarning("Atenção", "Nome da obra é obrigatório.")

        ttk.Button(top, text="Salvar", command=salvar).pack(pady=20)

    # --- Conteúdo das Abas ---

    def montar_tab_geral(self):
        frame = ttk.Frame(self.tab_geral, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Clima
        lf_clima = ttk.LabelFrame(frame, text="Condições Climáticas")
        lf_clima.pack(fill=tk.X, pady=5)
        
        self.clima_var = tk.StringVar(value="Sol")
        opcoes_clima = ["Sol", "Nublado", "Chuva Fraca", "Chuva Forte"]
        for op in opcoes_clima:
            ttk.Radiobutton(lf_clima, text=op, variable=self.clima_var, value=op).pack(side=tk.LEFT, padx=10, pady=5)
        
        self.tempo_var = tk.StringVar(value="Manhã/Tarde")
        ttk.Label(lf_clima, text="| Período: ").pack(side=tk.LEFT, padx=5)
        ttk.Combobox(lf_clima, textvariable=self.tempo_var, values=["Manhã", "Tarde", "Integral", "Noite"], width=10).pack(side=tk.LEFT)

        # Atividades
        ttk.Label(frame, text="Atividades Executadas Hoje:").pack(anchor=tk.W, pady=(10,0))
        self.txt_atividades = tk.Text(frame, height=8)
        self.txt_atividades.pack(fill=tk.X, pady=5)

        # Obs
        ttk.Label(frame, text="Ocorrências / Observações Gerais:").pack(anchor=tk.W, pady=(10,0))
        self.txt_obs = tk.Text(frame, height=5)
        self.txt_obs.pack(fill=tk.X, pady=5)

    def montar_tab_efetivo(self):
        frame = ttk.Frame(self.tab_efetivo, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Informe a quantidade de profissionais presentes hoje:", font=("Arial", 10, "bold")).pack(pady=10)

        # Lista de Funções Padrão
        funcoes = ["Engenheiro", "Mestre de Obras", "Pedreiro", "Servente", "Eletricista", "Encanador", "Pintor", "Carpinteiro", "Vigia"]
        self.entries_efetivo = {}

        container = ttk.Frame(frame)
        container.pack(fill=tk.BOTH, expand=True)

        # Criar grid de inputs
        for idx, funcao in enumerate(funcoes):
            row = idx // 2
            col = (idx % 2) * 2
            
            ttk.Label(container, text=funcao + ":").grid(row=row, column=col, sticky=tk.E, padx=5, pady=5)
            spin = ttk.Spinbox(container, from_=0, to=100, width=5)
            spin.set(0) # Valor inicial
            spin.grid(row=row, column=col+1, sticky=tk.W, padx=5, pady=5)
            self.entries_efetivo[funcao] = spin

    def montar_tab_fotos(self):
        frame = ttk.Frame(self.tab_fotos, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Adicionar Foto", command=self.adicionar_foto).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Remover Selecionada", command=self.remover_foto).pack(side=tk.LEFT, padx=10)

        # Lista de fotos
        self.lista_fotos = ttk.Treeview(frame, columns=("Caminho", "Descricao"), show="headings", height=10)
        self.lista_fotos.heading("Caminho", text="Arquivo")
        self.lista_fotos.heading("Descricao", text="Descrição da Imagem")
        self.lista_fotos.column("Caminho", width=200)
        self.lista_fotos.column("Descricao", width=400)
        self.lista_fotos.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Inputs para descrição da foto selecionada
        lbl_desc = ttk.Label(frame, text="Descrição da foto (Adicione antes de inserir ou edite na mente):")
        lbl_desc.pack(anchor=tk.W)

    def adicionar_foto(self):
        caminho = filedialog.askopenfilename(title="Selecione uma foto", filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if caminho:
            nome_arquivo = os.path.basename(caminho)
            # Pergunta descrição simples
            def_popup = tk.Toplevel(self)
            def_popup.title("Descrição")
            ttk.Label(def_popup, text="Descrição da Foto:").pack(pady=5)
            e_desc = ttk.Entry(def_popup, width=40)
            e_desc.pack(pady=5)
            e_desc.focus()
            
            def confirmar():
                desc = e_desc.get()
                self.lista_fotos.insert("", tk.END, values=(caminho, desc))
                def_popup.destroy()
            
            ttk.Button(def_popup, text="OK", command=confirmar).pack(pady=10)

    def remover_foto(self):
        selecionado = self.lista_fotos.selection()
        if selecionado:
            self.lista_fotos.delete(selecionado)

    def montar_tab_resumo(self):
        frame = ttk.Frame(self.tab_resumo, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        btn_salvar = ttk.Button(frame, text="SALVAR RELATÓRIO DO DIA NO BANCO DE DADOS", command=self.salvar_tudo)
        btn_salvar.pack(fill=tk.X, pady=10)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Label(frame, text="Visualização do Texto para Exportação:").pack(anchor=tk.W)
        self.txt_resumo = tk.Text(frame, height=15)
        self.txt_resumo.pack(fill=tk.BOTH, expand=True, pady=5)
        
        btn_gerar_texto = ttk.Button(frame, text="Gerar Prévia de Texto", command=self.gerar_texto_resumo)
        btn_gerar_texto.pack(pady=5)

    # --- Lógica de Negócio ---

    def gerar_texto_resumo(self):
        if not self.id_obra_selecionada:
            messagebox.showwarning("Erro", "Selecione uma obra primeiro.")
            return None

        texto = f"=== RELATÓRIO DIÁRIO DE OBRA ===\n"
        texto += f"Obra: {self.obra_selecionada.get()}\n"
        texto += f"Data: {self.data_atual.get()}\n"
        texto += f"Clima: {self.clima_var.get()} ({self.tempo_var.get()})\n"
        texto += "-" * 30 + "\n"
        texto += "ATIVIDADES:\n"
        texto += self.txt_atividades.get("1.0", tk.END).strip() + "\n\n"
        texto += "EFETIVO:\n"
        for func, entry in self.entries_efetivo.items():
            qtd = int(entry.get())
            if qtd > 0:
                texto += f"- {func}: {qtd}\n"
        texto += "\nOBSERVAÇÕES:\n"
        texto += self.txt_obs.get("1.0", tk.END).strip() + "\n\n"
        texto += "FOTOS ANEXADAS:\n"
        for item in self.lista_fotos.get_children():
            valores = self.lista_fotos.item(item)['values']
            texto += f"- {valores[1]} (Arq: {os.path.basename(valores[0])})\n"
        
        self.txt_resumo.delete("1.0", tk.END)
        self.txt_resumo.insert("1.0", texto)
        return texto

    def salvar_tudo(self):
        if not self.id_obra_selecionada:
            messagebox.showerror("Erro", "Selecione uma obra antes de salvar.")
            return

        # Coletar dados
        data = self.data_atual.get()
        clima = self.clima_var.get()
        condicao = self.tempo_var.get()
        atividades = self.txt_atividades.get("1.0", tk.END).strip()
        obs = self.txt_obs.get("1.0", tk.END).strip()
        
        # Coletar efetivo
        lista_efetivo = []
        total_funcionarios = 0
        for func, entry in self.entries_efetivo.items():
            qtd = int(entry.get())
            lista_efetivo.append((func, qtd))
            total_funcionarios += qtd
            
        # Coletar fotos
        lista_fotos = []
        for item in self.lista_fotos.get_children():
            valores = self.lista_fotos.item(item)['values']
            lista_fotos.append((valores[0], valores[1]))

        if not atividades and total_funcionarios == 0:
            if not messagebox.askyesno("Confirmar", "O relatório parece vazio. Deseja salvar mesmo assim?"):
                return

        sucesso = self.db.save_relatorio(
            self.id_obra_selecionada, data, clima, condicao, 
            atividades, obs, lista_efetivo, lista_fotos
        )

        if sucesso:
            self.gerar_texto_resumo() # Atualiza visualização
            messagebox.showinfo("Sucesso", "Diário de Obra Salvo com Sucesso!")
        else:
            messagebox.showerror("Erro", "Falha ao salvar no banco de dados.")

if __name__ == "__main__":
    app = DiarioObraApp()
    app.mainloop()
