import streamlit as st

# Definiujemy dostępne strony w aplikacji
# Pierwszy argument to nazwa pliku, drugi to nazwa w menu
start_page = st.Page("home.py", title="Strona Główna", icon="🏠", default=True)
v1_page = st.Page("wersja_1.py", title="Wersja 1.0 (Alpha)", icon="1️⃣")
v2_page = st.Page("wersja_2.py", title="Wersja 2.0 (Beta)", icon="2️⃣")
v3_page = st.Page("wersja_3.py", title="Wersja 3.0 (Finalna)", icon="⭐")

# Konfigurujemy nawigację
pg = st.navigation({
    "Menu Główne": [start_page],
    "Wersje Aplikacji": [v1_page, v2_page, v3_page]
})

# Uruchamiamy nawigację
pg.run()