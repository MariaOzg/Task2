import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# --- БЛОК БЕЗОПАСНОСТИ (Чтобы не зашли без пароля) ---
if "authentication_status" not in st.session_state or st.session_state["authentication_status"] is not True:
    st.warning("⚠️ Пожалуйста, сначала войдите в систему на Главной странице.")
    st.stop()

# ==========================================
# ⚙️ НАСТРОЙКИ СТОЛБЦОВ ДЕБИТОРКИ
# Проверьте названия по вашей таблице!
# ==========================================
SHEET_NAME = "Дебиторка"     # <--- Имя вкладки в Google Таблице
COL_CLIENT = "Название проекта"    # Кто должен
COL_DEBT = "Осталось получить от клиента"   # Сколько должен (Сумма)
COL_DATE = "Дата возникновения" # (Необязательно) Когда возник долг
COL_MANAGER = "Ответственный"     # (Необязательно) Кто ответственный
# ==========================================

st.set_page_config(page_title="Дебиторская задолженность", layout="wide")

# --- ФУНКЦИЯ ЗАГРУЗКИ (Такая же, как в app.py) ---
@st.cache_data(ttl=600)
def load_data():
    # 👇 Вставьте ту же ссылку, что и в app.py
    sheet_url = "https://docs.google.com/spreadsheets/d/1lXHUU5r8aq-S0c3fH0rY4Sh9lmiM9YT7ARp4lwEvgvA/edit?gid=2147255322#gid=2147255322" 
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Файл credentials.json должен лежать в главной папке (рядом с app.py)
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_url(sheet_url).worksheet(SHEET_NAME)
    except Exception as e:
        st.error(f"❌ Не найдена вкладка '{SHEET_NAME}'. Создайте её в таблице!")
        st.stop()
        
    all_values = sheet.get_all_values()
    if len(all_values) < 2: return pd.DataFrame()
    headers = all_values[0]
    data = all_values[1:]
    return pd.DataFrame(data, columns=headers)

# --- ОЧИСТКА ---
def clean_money(x):
    if isinstance(x, str):
        x = x.replace(' ', '').replace(',', '.').replace('\xa0', '')
        if x == '' or x == '-': return 0.0
        try: return float(x)
        except: return 0.0
    return x

# --- ОСНОВНАЯ ЧАСТЬ ---
st.title("📉 Дебиторская задолженность")

df_raw = load_data()

if df_raw.empty:
    st.warning("Нет данных.")
    st.stop()

# Чистим деньги
if COL_DEBT in df_raw.columns:
    df_raw["Clean_Debt"] = df_raw[COL_DEBT].apply(clean_money)
    # Оставляем только тех, у кого долг > 0
    df = df_raw[df_raw["Clean_Debt"] > 0].copy()
else:
    st.error(f"Не найдена колонка '{COL_DEBT}'")
    st.stop()

# --- МЕТРИКИ ---
total_debt = df["Clean_Debt"].sum()
top_debtor = df.sort_values("Clean_Debt", ascending=False).iloc[0][COL_CLIENT] if not df.empty else "-"
debtor_count = len(df)

m1, m2, m3 = st.columns(3)
m1.metric("🔴 Общий долг нам", f"${total_debt:,.0f}".replace(",", " "))
m2.metric("Количество должников", debtor_count)
m3.metric("Крупнейший должник", top_debtor)

st.divider()

# --- ГРАФИКИ ---
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("Топ-15 Должников")
    # Группируем (на случай если один клиент встречается дважды)
    df_grouped = df.groupby(COL_CLIENT)["Clean_Debt"].sum().reset_index()
    df_grouped = df_grouped.sort_values("Clean_Debt", ascending=False).head(15)
    
    fig = px.bar(
        df_grouped, 
        x="Clean_Debt", 
        y=COL_CLIENT, 
        orientation='h', # Горизонтальный график удобнее для длинных имен
        text_auto='.2s',
        title="Кто должен больше всех?"
    )
    # Разворачиваем ось, чтобы самый большой был сверху
    fig.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("По менеджерам")
    if COL_MANAGER in df.columns:
        df_manager = df.groupby(COL_MANAGER)["Clean_Debt"].sum().reset_index()
        fig_pie = px.pie(df_manager, values="Clean_Debt", names=COL_MANAGER, hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Нет колонки 'Менеджер' для анализа.")

# --- ДЕТАЛЬНАЯ ТАБЛИЦА ---
with st.expander("📄 Посмотреть полный список должников"):
    st.dataframe(
        df[[COL_CLIENT, COL_DEBT, COL_DATE] if COL_DATE in df.columns else [COL_CLIENT, COL_DEBT]],
        use_container_width=True
    )