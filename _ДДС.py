import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import streamlit_authenticator as stauth

# ==========================================
# ⚙️ НАСТРОЙКИ СТОЛБЦОВ
# ==========================================
COL_DATE = "Дата"
COL_PROJECT = "Название проекта"
COL_ARTICLE = "Статья"            
COL_SUM = "Сумма, в дол"          
SHEET_NAME = "ДДС"              
# ==========================================

st.set_page_config(page_title="ДДС Аналитика", layout="wide")

# --- 1. ФУНКЦИЯ ЗАГРУЗКИ ---
@st.cache_data(ttl=600) 
def load_data():
    # 👇 Вставьте вашу ссылку
    sheet_url = "https://docs.google.com/spreadsheets/d/1lXHUU5r8aq-S0c3fH0rY4Sh9lmiM9YT7ARp4lwEvgvA/edit?gid=0#gid=0" 
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
   # БЕРЕМ КЛЮЧИ ИЗ СЕЙФА:
    creds_dict = st.secrets["gcp_service_account"]
    creds_dict = dict(st.secrets["gcp_service_account"])  # Превращаем в обычный словарь
# Чиним проблему с переносами строк в ключе, если она есть
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    try:
        sheet = client.open_by_url(sheet_url).worksheet(SHEET_NAME)
    except Exception as e:
        st.error(f"⚠️ Ошибка доступа: {e}")
        st.stop()
        
    all_values = sheet.get_all_values()
    if len(all_values) < 2: return pd.DataFrame()
    headers = all_values[0]
    data = all_values[1:]
    return pd.DataFrame(data, columns=headers)

# --- 2. ФУНКЦИЯ ОЧИСТКИ ---
def preprocess_data(df):
    def clean_money(x):
        if isinstance(x, str):
            x = x.replace(' ', '').replace(',', '.').replace('\xa0', '')
            if x == '' or x == '-': return 0.0
            try: return float(x)
            except: return 0.0
        return x

    if COL_SUM in df.columns:
        df["Clean_Money"] = df[COL_SUM].apply(clean_money)
    
    if COL_DATE in df.columns:
        df["Date_Obj"] = pd.to_datetime(df[COL_DATE], dayfirst=True, errors='coerce')
        df["Month_Year"] = df["Date_Obj"].dt.strftime('%Y-%m')
        df = df.dropna(subset=["Date_Obj"])
    return df

# --- 3. ГЛАВНАЯ ЧАСТЬ ---
def main():
    # ==========================================
    # 🔐 БЛОК БЕЗОПАСНОСТИ
    # ==========================================
    
    # Ваши хеши (вставьте их сюда из keygen.py)
    credentials = {
        'usernames': {
            'Rustam': {
                'name': 'Рустам Директор',
                'password': '$2b$12$HbEJYkUDi9o/4XQSw.0ofu1FOApW3rHV81In.fCDU.1EjA3fMfewC' # Вставьте хеш сюда
            },
            'Vlad': {
                'name': 'Влад Директор',
                'password': '$2b$12$nHELiIrxeHYaWKJ5L.ckxu/AXAkEv1cqozt7RlSf2gqEXDEiayIc.' # Вставьте хеш сюда
            },
            'Elena': {
                'name': 'Елена Бухгалтер',
                'password': '$2b$12$dDt9fwL8zOi9a15vk12tMeMgQxqIZ/6CrR8/CGeD1ROJiX4PKTFLi'
            },
            'Otabek': {
                'name': 'Отабек Директор',
                'password': '$2b$12$GJpQssKCW4p01CkV0iM7aeT2/H6FYDbqHUtgQxICL6HD3FWio4ggu'
            },
            'Maria': {
                'name': 'Мария Финансы',
                'password': '$2b$12$OvhO73j4c69IbpGPoEGSVOHScz5qVDOxVv5rfkZlQlvkZApNssMAi'
            }
        }
    }

    # Инициализация
    authenticator = stauth.Authenticate(
        credentials,
        "dds_cookie_name", 
        "dds_signature_key", 
        cookie_expiry_days=30
    )

    # ----------------------------------------------------
    # 👇 ИСПРАВЛЕННАЯ ЧАСТЬ (ДЛЯ НОВОЙ БИБЛИОТЕКИ) 👇
    # ----------------------------------------------------
    
    # Просто рисуем окно входа (оно само обновит session_state)
    authenticator.login()

    # Проверяем статус через session_state
    if st.session_state["authentication_status"] is False:
        st.error("Неверный логин или пароль")
        return 
    elif st.session_state["authentication_status"] is None:
        st.warning("Пожалуйста, войдите в систему")
        return 
    
    # ЕСЛИ УСПЕШНО ВОШЛИ (authentication_status == True) 👇
    
    # Кнопка выхода
    authenticator.logout("Выйти", "sidebar")
    
    # Приветствие
    user_name = st.session_state["name"]
    st.sidebar.write(f"Вы вошли как: **{user_name}**")
    st.sidebar.divider()

    # ==========================================
    # 📊 САМ ОТЧЕТ
    # ==========================================
    st.title("💰 Монитор ДДС")

    df_raw = load_data()
    if df_raw.empty:
        st.warning("Таблица пустая.")
        return

    df = preprocess_data(df_raw)

    st.sidebar.header("Фильтры")
    all_projects = df[COL_PROJECT].unique()
    sel_projects = st.sidebar.multiselect("Проекты", all_projects, default=all_projects)
    
    all_articles = df[COL_ARTICLE].unique()
    sel_articles = st.sidebar.multiselect("Статьи", all_articles, default=all_articles)

    mask = (df[COL_PROJECT].isin(sel_projects)) & (df[COL_ARTICLE].isin(sel_articles))
    df_filtered = df[mask]

    if df_filtered.empty:
        st.warning("Нет данных.")
        return

    total_turnover = df_filtered["Clean_Money"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Оборот", f"${total_turnover:,.0f}".replace(",", " "))
    c2.metric("Операций", len(df_filtered))
    c3.metric("Проектов", df_filtered[COL_PROJECT].nunique())

    st.divider()

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Динамика")
        df_chart = df_filtered.groupby(["Month_Year", COL_ARTICLE])["Clean_Money"].sum().reset_index()
        fig = px.bar(df_chart, x="Month_Year", y="Clean_Money", color=COL_ARTICLE)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Структура")
        df_pie = df_filtered.groupby(COL_ARTICLE)["Clean_Money"].sum().reset_index()
        fig_pie = px.pie(df_pie, values="Clean_Money", names=COL_ARTICLE)
        st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("Сводная")
    pivot = df_filtered.pivot_table(index=COL_ARTICLE, columns="Month_Year", values="Clean_Money", aggfunc="sum", fill_value=0)
    st.dataframe(pivot.style.format("{:,.0f}"))

if __name__ == "__main__":
    main()



