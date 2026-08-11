import os
import re
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


def _pozycja_naglowka(txt, wzor, od=0):
    """Zwraca pozycję nagłówka sekcji, pomijając wystąpienia w spisie treści
    (rozpoznawane po kropkach wiodących tuż za nazwą)."""
    for m in re.finditer(wzor, txt[od:]):
        ogon = txt[od + m.end(): od + m.end() + 25]
        if '....' not in ogon and '. .' not in ogon:
            return od + m.start()
    return -1


def _wytnij_istotne_sekcje(txt):
    """Wycina z opisu INFODORADCA+ sekcje istotne dla BHP:
    2.1 Syntezę, 2.2 Opis pracy, 2.3 Środowisko pracy oraz 3.1 Zadania zawodowe.
    Zwraca pusty ciąg, gdy struktura nie została rozpoznana (wtedy używamy
    pełnego tekstu jako fallback)."""
    fragmenty = []

    # Blok 2.1-2.3: od "Synteza zawodu" do nagłówka 2.4 / 2.5
    s = _pozycja_naglowka(txt, r'Synteza zawodu')
    e = _pozycja_naglowka(txt, r'2\.[45]\.', s + 50) if s >= 0 else -1
    if s >= 0 and e > s:
        fragmenty.append(txt[s:e])

    # Blok 3.1: "Zadania zawodowe" do nagłówka 3.2
    s2 = _pozycja_naglowka(txt, r'Zadania zawodowe')
    e2 = _pozycja_naglowka(txt, r'3\.2\.', s2 + 50) if s2 >= 0 else -1
    if s2 >= 0 and e2 > s2:
        fragmenty.append(txt[s2:e2])

    return '\n\n'.join(' '.join(f.split()) for f in fragmenty)


@st.cache_data
def pobierz_opis_zawodu_lokalnie(kod_zawodu):
    sciezka_pliku = os.path.join('baza_zawodow', f'{kod_zawodu}.pdf')
    try:
        pelny_tekst = ""
        with open(sciezka_pliku, "rb") as f:
            pdf_reader = PdfReader(f)
            for page in pdf_reader.pages:
                pelny_tekst += (page.extract_text() or "") + "\n"

        # Wyciąg sekcji istotnych dla BHP; fallback na pełny tekst, gdy
        # struktura dokumentu nie została rozpoznana.
        wyciag = _wytnij_istotne_sekcje(pelny_tekst)
        if len(wyciag) >= 800:
            return wyciag
        return pelny_tekst
    except FileNotFoundError:
        return f"Błąd: Brak pliku {kod_zawodu}.pdf w folderze 'baza_zawodow'."
    except Exception as e:
        return f"Błąd odczytu pliku PDF {kod_zawodu}.pdf: {e}"