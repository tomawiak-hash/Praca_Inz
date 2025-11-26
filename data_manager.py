import os
from PyPDF2 import PdfReader
import streamlit as st

def wczytaj_liste_zawodow_lokalnie():
    lista_zawodow = {
        "Administrator baz danych (252101)": "252101",
        "Specjalista administracji publicznej (242217)": "242217",
        "Specjalista do spraw kadr (242307)": "242307",
        "Kierownik biura (334101)": "334101",
        "Asystent dyrektora (334302)": "334302"
    }
    return lista_zawodow

@st.cache_data
def pobierz_opis_zawodu_lokalnie(kod_zawodu):
    sciezka_pliku = os.path.join('baza_zawodow', f'{kod_zawodu}.pdf')
    try:
        pelny_tekst = ""
        with open(sciezka_pliku, "rb") as f:
            pdf_reader = PdfReader(f)
            for page in pdf_reader.pages:
                pelny_tekst += (page.extract_text() or "") + "\n"
        return pelny_tekst
    except FileNotFoundError:
        return f"Błąd: Brak pliku {kod_zawodu}.pdf w folderze 'baza_zawodow'."
    except Exception as e:
        return f"Błąd odczytu pliku PDF {kod_zawodu}.pdf: {e}"

@st.cache_data
def laduj_baze_wiedzy(folder_path='baza_wiedzy_new'):
    pelny_tekst = ""
    if not os.path.isdir(folder_path):
        return "" 
    for nazwa_pliku in os.listdir(folder_path):
        sciezka_pliku = os.path.join(folder_path, nazwa_pliku)
        try:
            if nazwa_pliku.lower().endswith('.pdf'):
                with open(sciezka_pliku, "rb") as f:
                    pdf_reader = PdfReader(f)
                    if pdf_reader.is_encrypted: continue
                    for page in pdf_reader.pages:
                         pelny_tekst += (page.extract_text() or "") + "\n\n"
            elif nazwa_pliku.lower().endswith('.txt'):
                with open(sciezka_pliku, "r", encoding="utf-8") as f:
                    pelny_tekst += f.read() + "\n\n"
        except Exception as e:
            print(f"Błąd pliku {nazwa_pliku}: {e}")
    return pelny_tekst