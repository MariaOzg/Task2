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
# ==========================================
SHEET_NAME = "Дебиторка"    # <--- Имя вкладки в Google Таблице (должно совпадать точно!)
COL_CLIENT = "Название проекта"    # Кто должен
COL_DEBT = "Осталось получить от клиента"   # Сколько должен (Сумма)
COL_DATE = "Дата возникновения" # (Необязательно) Когда возник долг
COL_MANAGER = "Ответственный"     # (Необязательно) Кто ответственный
# ==========================================

st.set_page_config(page_title="Дебиторская задолженность", layout="wide")

# --- ФУНКЦИЯ ЗАГРУЗКИ ---
@st.cache_data(ttl=600)
def load_data():
    # 1. Ссылка на таблицу
    sheet_url = "https://docs.google.com/spreadsheets/d/1lXHUU5r8aq-S0c3fH0rY4Sh9lmiM9YT7ARp4lwEvgvA/edit#gid=2147255322"
    
    # 2. Настройки доступа
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # 3. БЕРЕМ КЛЮЧИ ИЗ СЕЙФА (ИСПРАВЛЕННЫЙ БЛОК)
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
    except KeyError:
        st.error("Ошибка: Секреты не найдены. Проверьте secrets.toml")
        st.stop()

    # Принудительно указываем тип
    creds_dict["type"] = "service_account"

    # Чиним переносы строк в ключе
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    # Создаем объект авторизации
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    # 4. Получение данных (Ищем конкретную вкладку)
    try:
        sheet = client.open_by_url(sheet_url).worksheet(SHEET_NAME)
    except Exception as e:
        st.error(f"❌ Вкладка '{SHEET_NAME}' не найдена. Проверьте название внизу таблицы Google.")
        st.stop()
        
    all_values = sheet.get_all_values()

    # 5. Проверка: если таблица пустая
    if len(all_values) < 2:
        return pd.DataFrame()

    # 6. Сборка таблицы с очисткой заголовков
    # .strip() убирает случайные пробелы в названиях колонок (например "Сумма " -> "Сумма")
    headers = [h.strip() for h in all_values[0]] 
    data = all_values[1:]
    
    return pd.DataFrame(data, columns=headers)

# --- ОЧИСТКА ДЕНЕГ ---
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
    st.error(f"❌ Не найдена колонка '{COL_DEBT}'. Найденные колонки: {list(df_raw.columns)}")
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
    if not df.empty:
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
        st.info(f"Нет колонки '{COL_MANAGER}' для анализа.")

# --- ДЕТАЛЬНАЯ ТАБЛИЦА ---
with st.expander("📄 Посмотреть полный список должников"):
    # Выбираем колонки, которые существуют
    cols_to_show = [COL_CLIENT, COL_DEBT]
    if COL_DATE in df.columns:
        cols_to_show.append(COL_DATE)
        
    st.dataframe(
        df[cols_to_show],
        use_container_width=True
    )
