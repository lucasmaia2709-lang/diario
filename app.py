import streamlit as st
import sqlite3
import datetime
import pandas as pd
import os

# --- Configuração do Banco de Dados ---
class Database:
    def __init__(self, db_name="diario_obra.db"):
        self.db_name = db_name
        self.create_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)

    def create_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS obras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    endereco TEXT,
                    inicio TEXT
                )
            """)
            cursor.execute("""
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS efetivo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relatorio_id INTEGER,
                    funcao TEXT,
                    quantidade INTEGER,
                    FOREIGN KEY(relatorio_id) REFERENCES relatorios(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fotos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relatorio_id INTEGER,
                    nome_arquivo TEXT,
                    descricao TEXT,
                    FOREIGN KEY(relatorio_id) REFERENCES relatorios(id)
                )
            """)
            conn.commit()

    def get_obras(self):
        with self.get_connection() as conn:
            return pd.read_sql("SELECT id, nome FROM obras", conn)

    def add_obra(self, nome, endereco):
        with self.get_connection() as conn:
            data_inicio = datetime.date.today().strftime("%d/%m/%Y")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO obras (nome, endereco, inicio) VALUES (?, ?, ?)", (nome, endereco, data_inicio))
            conn.commit()

    def get_relatorio_dia(self, obra_id, data_str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM relatorios WHERE obra_id = ? AND data = ?", (obra_id, data_str))
            relatorio = cursor.fetchone()
            if relatorio:
                cols = [description[0] for description in cursor.description]
                return dict(zip(cols, relatorio))
            return None

    def save_relatorio(self, obra_id, data, clima, condicao, atividades, obs, efetivo_dict, fotos_info):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Verifica se já existe relatório para atualizar ou criar novo
                cursor.execute("SELECT id FROM relatorios WHERE obra_id = ? AND data = ?", (obra_id, data))
                existente = cursor.fetchone()
                
                relatorio_id = None
                
                if existente:
                    relatorio_id = existente[0]
                    cursor.execute("""
                        UPDATE relatorios SET clima=?, condicao_tempo=?, atividades=?, obs_gerais=?
                        WHERE id=?
                    """, (clima, condicao, atividades, obs, relatorio_id))
                    # Limpa dados antigos vinculados para reescrever
                    cursor.execute("DELETE FROM efetivo WHERE relatorio_id=?", (relatorio_id,))
                    cursor.execute("DELETE FROM fotos WHERE relatorio_id=?", (relatorio_id,))
                else:
                    cursor.execute("""
                        INSERT INTO relatorios (obra_id, data, clima, condicao_tempo, atividades, obs_gerais)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (obra_id, data, clima, condicao, atividades, obs))
                    relatorio_id = cursor.lastrowid

                # 2. Salvar Efetivo
                for funcao, qtd in efetivo_dict.items():
                    if qtd > 0:
                        cursor.execute("INSERT INTO efetivo (relatorio_id, funcao, quantidade) VALUES (?, ?, ?)", 
                                            (relatorio_id, funcao, qtd))

                # 3. Salvar Registro de Fotos
                for foto in fotos_info:
                    cursor.execute("INSERT INTO fotos (relatorio_id, nome_arquivo, descricao) VALUES (?, ?, ?)",
                                        (relatorio_id, foto['nome'], foto['desc']))
                
                conn.commit()
                return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return False

# --- Interface App (Streamlit) ---
def main():
    st.set_page_config(page_title="Diário de Obra", layout="wide")
    st.title("🏗️ Sistema de Diário de Obra (RDO)")

    db = Database()

    # --- Sidebar: Seleção de Obra ---
    st.sidebar.header("Gerenciar Obras")
    
    # Adicionar Nova Obra
    with st.sidebar.expander("Cadastrar Nova Obra"):
        with st.form("nova_obra_form"):
            novo_nome = st.text_input("Nome da Obra")
            novo_end = st.text_input("Endereço")
            btn_criar = st.form_submit_button("Criar Obra")
            if btn_criar and novo_nome:
                db.add_obra(novo_nome, novo_end)
                st.success("Obra cadastrada!")
                st.rerun()

    # Selecionar Obra Existente
    df_obras = db.get_obras()
    if df_obras.empty:
        st.warning("👈 Cadastre uma obra no menu lateral para começar.")
        return

    obra_selecionada_nome = st.sidebar.selectbox("Selecione a Obra Atual:", df_obras['nome'])
    obra_selecionada_id = int(df_obras[df_obras['nome'] == obra_selecionada_nome]['id'].values[0])

    st.sidebar.divider()
    st.sidebar.info("Preencha as abas e clique em 'Salvar' na última aba.")
    
    # --- Corpo Principal ---
    
    # Data
    col_data, col_vazio = st.columns([1, 3])
    with col_data:
        data_selecionada = st.date_input("Data do Relatório", datetime.date.today())
        data_str = data_selecionada.strftime("%d/%m/%Y")

    # Tentar carregar dados se já existirem para o dia
    dados_existentes = db.get_relatorio_dia(obra_selecionada_id, data_str)
    
    # Valores Iniciais
    def_clima = dados_existentes['clima'] if dados_existentes else "Sol"
    def_condicao = dados_existentes['condicao_tempo'] if dados_existentes else "Manhã"
    def_atv = dados_existentes['atividades'] if dados_existentes else ""
    def_obs = dados_existentes['obs_gerais'] if dados_existentes else ""

    # Abas
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Geral", "👷 Efetivo", "📷 Fotos", "💾 Salvar & Exportar"])

    with tab1:
        st.subheader("Informações Gerais")
        c1, c2 = st.columns(2)
        with c1:
            clima = st.radio("Condições Climáticas", ["Sol", "Nublado", "Chuva Fraca", "Chuva Forte"], 
                             index=["Sol", "Nublado", "Chuva Fraca", "Chuva Forte"].index(def_clima) if def_clima in ["Sol", "Nublado", "Chuva Fraca", "Chuva Forte"] else 0)
        with c2:
            condicao = st.selectbox("Período", ["Manhã", "Tarde", "Integral", "Noite"], 
                                    index=["Manhã", "Tarde", "Integral", "Noite"].index(def_condicao) if def_condicao in ["Manhã", "Tarde", "Integral", "Noite"] else 0)
        
        atividades = st.text_area("Atividades Executadas Hoje:", value=def_atv, height=150, placeholder="Descreva o que foi feito...")
        obs = st.text_area("Ocorrências / Observações:", value=def_obs, height=100, placeholder="Algum problema ou observação importante?")

    with tab2:
        st.subheader("Efetivo no Canteiro")
        st.write("Informe a quantidade de profissionais presentes:")
        funcoes = ["Engenheiro", "Mestre de Obras", "Pedreiro", "Servente", "Eletricista", "Encanador", "Pintor", "Carpinteiro", "Vigia"]
        
        efetivo_input = {}
        cols = st.columns(3)
        for i, func in enumerate(funcoes):
            with cols[i % 3]:
                efetivo_input[func] = st.number_input(f"{func}", min_value=0, step=1, value=0)

    with tab3:
        st.subheader("Registro Fotográfico")
        uploaded_files = st.file_uploader("Escolha as fotos do dia", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        fotos_info = []
        if uploaded_files:
            st.image(uploaded_files, width=200, caption=[f.name for f in uploaded_files])
            for up_file in uploaded_files:
                # Em ambiente web, o caminho real do arquivo é temporário.
                fotos_info.append({"nome": up_file.name, "desc": "Upload via Sistema"})

    with tab4:
        st.subheader("Resumo e Exportação")
        
        # Gerar Texto de Preview
        texto_export = f"""=== RELATÓRIO DIÁRIO DE OBRA ===
Obra: {obra_selecionada_nome}
Data: {data_str}
Clima: {clima} - {condicao}
------------------------------
ATIVIDADES:
{atividades}

EFETIVO:
"""
        tem_efetivo = False
        for func, qtd in efetivo_input.items():
            if qtd > 0:
                texto_export += f"- {func}: {qtd}\n"
                tem_efetivo = True
        if not tem_efetivo: texto_export += "(Sem registro de efetivo)\n"

        texto_export += f"\nOBSERVAÇÕES:\n{obs}\n"
        
        texto_export += "\nFOTOS REGISTRADAS:\n"
        if fotos_info:
            for f in fotos_info:
                texto_export += f"- {f['nome']}\n"
        else:
            texto_export += "(Nenhuma foto anexada)\n"

        st.text_area("Prévia do Relatório (Copie e cole se precisar):", value=texto_export, height=300)

        if st.button("💾 SALVAR DADOS NO SISTEMA", type="primary"):
            if not atividades and not tem_efetivo:
                st.error("Preencha pelo menos as atividades ou o efetivo antes de salvar.")
            else:
                sucesso = db.save_relatorio(obra_selecionada_id, data_str, clima, condicao, atividades, obs, efetivo_input, fotos_info)
                if sucesso:
                    st.balloons()
                    st.success("Relatório salvo com sucesso no banco de dados!")

if __name__ == "__main__":
    main()
