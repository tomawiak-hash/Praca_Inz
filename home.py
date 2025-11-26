import streamlit as st

# Ukrywamy standardową nawigację boczną na tej stronie, żeby było ładnie
st.set_page_config(page_title="Hub Projektu BHP", page_icon="🎓", layout="centered")

st.title("🎓 Inteligentny Generator Szkoleń BHP")
st.subheader("Portfolio Projektu Inżynierskiego")
st.write("Poniżej znajdują się odnośniki do poszczególnych etapów rozwoju aplikacji.")

st.write("") # Odstęp
st.write("")

# Tworzymy 3 kolumny na przyciski
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("### 👶 Wersja 1")
        st.info("Wczesna wersja alfa. Prosty generator tekstu.")
        # Link do strony (działa jak przycisk)
        st.page_link("wersja_1.py", label="Uruchom V1", icon="1️⃣", use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("### 🧑‍💻 Wersja 2")
        st.warning("Wersja rozwojowa. Dodano pliki Word.")
        st.page_link("wersja_2.py", label="Uruchom V2", icon="2️⃣", use_container_width=True)

with col3:
    with st.container(border=True):
        st.markdown("### 🚀 Wersja Finalna")
        st.success("Gotowy produkt zgodny z prawem.")
        st.page_link("wersja_3.py", label="Uruchom Finalną", icon="⭐", use_container_width=True)

st.markdown("---")
st.caption("Autor: Adam | Projekt Inżynierski 2025")