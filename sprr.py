import streamlit as st
import google.generativeai as genai
from PyPDF2 import PdfReader
import os
import re
from docxtpl import DocxTemplate
from io import BytesIO
import datetime

# ----- Konfiguracja Aplikacji
st.set_page_config(page_title="Inteligentny Generator Szkoleń BHP", page_icon="🎓")

# Wstaw tutaj swój klucz API z Google AI Studio
genai.configure(api_key="AIzaSyBYtQ-Y7nfP7h-4fqT4gMDRzed0b-IVVjw")

# ----- Inicjalizacja "pamięci" aplikacji
if 'etap' not in st.session_state:
    st.session_state.etap = 1
if 'finalna_tresc' not in st.session_state:
    st.session_state.finalna_tresc = ""
if 'zapisana_firma' not in st.session_state:
    st.session_state.zapisana_firma = ""
if 'wybrany_zawod' not in st.session_state:
    st.session_state.wybrany_zawod = ""
if 'opis_zawodu' not in st.session_state:
    st.session_state.opis_zawodu = ""
if 'spis_finalny' not in st.session_state:
    st.session_state.spis_finalny = ""


# ----- Funkcje Aplikacji
def wczytaj_liste_zawodow_lokalnie():
    """
    Zwraca stałą, lokalną listę zawodów.
    """
    return {
        "Administrator baz danych (252101)": "252101",
        "Specjalista administracji publicznej (242217)": "242217",
        "Specjalista do spraw kadr (242307)": "242307",
        "Kierownik biura (334101)": "334101",
        "Asystent dyrektora (334302)": "334302"
    }

@st.cache_data
def pobierz_opis_zawodu_lokalnie(kod_zawodu):
    """
    Wczytuje opis zawodu z lokalnego pliku PDF z folderu 'baza_zawodow'.
    """
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

@st.cache_data
def laduj_baze_wiedzy(folder_path='baza_wiedzy'):
    """
    Wczytuje treść wszystkich plików z podanego folderu.
    """
    print(f"--- Wczytywanie bazy wiedzy z folderu: {folder_path} ---")
    pelny_tekst = ""
    if not os.path.isdir(folder_path):
        st.warning(f"Folder '{folder_path}' nie istnieje! Baza wiedzy nie zostanie załadowana.")
        return ""
    for nazwa_pliku in os.listdir(folder_path):
        sciezka_pliku = os.path.join(folder_path, nazwa_pliku)
        try:
            if nazwa_pliku.lower().endswith('.pdf'):
                with open(sciezka_pliku, "rb") as f:
                    pdf_reader = PdfReader(f)
                    for page in pdf_reader.pages:
                        pelny_tekst += (page.extract_text() or "") + "\n\n"
            elif nazwa_pliku.lower().endswith('.txt'):
                with open(sciezka_pliku, "r", encoding="utf-8") as f:
                    pelny_tekst += f.read() + "\n\n"
        except Exception as e:
            print(f"Błąd podczas wczytywania pliku {nazwa_pliku}: {e}")
    return pelny_tekst

# ----- Funkcje do komunikacji z AI (zasilane przez Gemini)
def generuj_kompletne_szkolenie(firma, nazwa_zawodu, opis_zawodu, baza_wiedzy):
    """
    Jedna funkcja generująca wszystko naraz dzięki Gemini.
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"""
    Jesteś ekspertem-dydaktykiem i instruktorem BHP. Twoim zadaniem jest stworzenie KOMPLETNEGO i BARDZO SZCZEGÓŁOWEGO materiału szkoleniowego dla stanowiska '{nazwa_zawodu}' w firmie '{firma}'.
    WYTYCZNE:
    1.  STRUKTURA: Stwórz najpierw szczegółowy, hierarchiczny spis treści (główne punkty np. 1., 2., 3.), a następnie rozwiń KAŻDY punkt i podpunkt.
    2.  GŁĘBIA MERYTORYCZNA: Każdy temat opisz wyczerpująco (minimum 3-4 akapity lub rozbudowane listy).
    3.  PERSONALIZACJA: Nieustannie nawiązuj do OFICJALNEGO OPISU ZAWODU, podając konkretne przykłady.
    4.  JAKOŚĆ: Naśladuj profesjonalny styl z BAZY WIEDZY. Powołuj się na polskie akty prawne.
    5.  FORMATOWANIE: Używaj formatowania Markdown (nagłówki #, ##, ###).
    --- OFICJALNY OPIS ZAWODU ---
    {opis_zawodu}
    --- BAZA WIEDZY ---
    {baza_wiedzy}
    Stwórz teraz kompletny materiał szkoleniowy.
    """
    response = model.generate_content(prompt)
    return response.text

@st.cache_data
def generuj_cel_szkolenia(nazwa_szkolenia):
    """Generuje krótki, oficjalny cel szkolenia dla danego zawodu."""
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"Napisz krótki, jednozdaniowy, oficjalny cel szkolenia wstępnego BHP dla stanowiska '{nazwa_szkolenia}'. Cel powinien być zwięzły i formalny."
    response = model.generate_content(prompt)
    return response.text

@st.cache_data
def przypisz_godziny_do_tematow(spis_tresci):
    """Analizuje spis treści i przypisuje szacowaną liczbę godzin do każdego tematu."""
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"""
    Jesteś metodykiem szkoleń BHP. Otrzymujesz poniższy spis treści. Twoim zadaniem jest oszacowanie, ile godzin lekcyjnych (45 min) potrzeba na realizację każdego głównego tematu (tylko punkty główne, np. 1., 2., 3.).
    Odpowiedź zwróć TYLKO w formacie listy, gdzie każda linia to: "Pełna nazwa tematu z numerem | X", gdzie X to liczba godzin.
    Przykład:
    1. Wprowadzenie do BHP | 1
    2. Zagrożenia na stanowisku pracy | 2

    Oto spis treści do analizy:
    {spis_tresci}
    """
    response = model.generate_content(prompt)
    
    tematyka = []
    # Wyciągamy tylko główne rozdziały ze spisu treści, na wypadek gdyby AI dodało coś więcej
    glowne_rozdzialy = re.findall(r"^(?:\d+|[IVXLCDM]+)\..*", spis_tresci, re.MULTILINE)
    
    for linia in response.text.splitlines():
        if '|' in linia:
            try:
                czesci = linia.split('|')
                nazwa = czesci[0].strip()
                godziny = int(czesci[1].strip())
                tematyka.append({"nazwa": nazwa, "godziny": godziny})
            except (ValueError, IndexError):
                continue
                
    # Upewniamy się, że mamy tyle samo wierszy, co głównych rozdziałów
    return tematyka[:len(glowne_rozdzialy)]


# ----- Główny interfejs aplikacji
st.title("🎓 Inteligentny Generator Szkoleń BHP (zasilany przez Gemini)")

# ... (kod dla Etapu 1 bez zmian) ...
if 'etap' not in st.session_state:
    st.session_state.etap = 1

if st.session_state.etap == 1:
    st.header("Krok 1: Wybierz zawód i wygeneruj kompletne szkolenie")
    
    lista_zawodow = wczytaj_liste_zawodow_lokalnie()
    baza_wiedzy_content = laduj_baze_wiedzy()

    wybrany_zawod_nazwa = st.selectbox("Wybierz zawód z listy:", options=list(lista_zawodow.keys()), index=None, placeholder="Wybierz zawód...")
    nazwa_firmy = st.text_input("Wprowadź nazwę firmy:", key="firma_input", value="Przykładowa Firma S.A.")
    
    if st.button("🚀 Generuj kompletne szkolenie"):
        if not wybrany_zawod_nazwa:
            st.warning("Proszę wybrać zawód z listy.")
        else:
            with st.spinner(f"Analizuję dane i tworzę pełne szkolenie dla: {wybrany_zawod_nazwa}... (może to potrwać dłuższą chwilę)"):
                kod_zawodu = lista_zawodow[wybrany_zawod_nazwa]
                opis_zawodu = pobierz_opis_zawodu_lokalnie(kod_zawodu)
                
                if "Błąd:" in opis_zawodu:
                    st.error(opis_zawodu)
                else:
                    finalna_tresc = generuj_kompletne_szkolenie(nazwa_firmy, wybrany_zawod_nazwa, opis_zawodu, baza_wiedzy_content)
                    
                    st.session_state.finalna_tresc = finalna_tresc
                    st.session_state.zapisana_firma = nazwa_firmy or "Twoja Firma"
                    st.session_state.wybrany_zawod = wybrany_zawod_nazwa
                    
                    st.session_state.etap = 2
                    st.rerun()

elif st.session_state.etap == 2:
    st.header("✅ Krok 2: Weryfikacja i pobieranie treści szkolenia")
    st.success("Pełna treść szkolenia została wygenerowana.")

    with st.expander("Pokaż/Ukryj treść szkolenia do weryfikacji"):
        st.markdown(st.session_state.finalna_tresc)

    st.markdown("---")
    
    st.subheader("1. Pobierz treść szkolenia")
    bio_szkolenie = BytesIO()
    bio_szkolenie.write(st.session_state.finalna_tresc.encode('utf-8'))
    st.download_button(
        label="Pobierz treść szkolenia (.txt)",
        data=bio_szkolenie.getvalue(),
        file_name=f"Szkolenie_{st.session_state.wybrany_zawod}.txt",
        mime="text/plain"
    )

    st.markdown("---")

    st.subheader("2. Przejdź do dokumentacji")
    if st.button("📄 Generuj dokumenty (Certyfikat, etc.)"):
        st.session_state.etap = 3
        st.rerun()

    if st.button("Stwórz inne szkolenie (powrót na początek)"):
        st.session_state.etap = 1
        st.rerun()

elif st.session_state.etap == 3:
    st.header("✅ Krok 3: Generator Dokumentacji")
    st.success("Wypełnij dane i generuj poszczególne dokumenty w formacie .docx")
    
    st.markdown("---")

    with st.container(border=True):
        st.subheader("📄 Wygeneruj Zaświadczenie")
        col1, col2 = st.columns(2)
        with col1:
            uczestnik = st.text_input("Imię i nazwisko uczestnika:", "Jan Kowalski", key="cert_uczestnik")
            data_ur = st.date_input("Data urodzenia:", key="cert_data_ur", value=datetime.date(2000, 1, 1))
        with col2:
            data_start = st.date_input("Data rozpoczęcia:", key="cert_data_start")
            data_koniec = st.date_input("Data zakończenia:", key="cert_data_koniec")
        miejscowosc = st.text_input("Miejscowość wystawienia:", "Łódź", key="cert_miejscowosc")
        nr_zaswiadczenia = st.text_input("Nr zaświadczenia wg rejestru:", "01/BHP/2025", key="cert_nr")

        if st.button("Generuj Zaświadczenie"):
            with st.spinner("Generowanie zaświadczenia..."):
                try:
                    doc = DocxTemplate("certyfikat_szablon.docx")
                    nazwa_szkolenia_full = f"Szkolenie wstępne BHP dla stanowiska '{st.session_state.wybrany_zawod}'"
                    cel_szkolenia_text = generuj_cel_szkolenia(nazwa_szkolenia_full)
                    
                    context = {
                        'nazwa_organizatora_szkolenia': st.session_state.zapisana_firma,
                        'imie_nazwisko': uczestnik,
                        'data_urodzenia': data_ur.strftime("%d.%m.%Y"),
                        'nazwa_szkolenia': nazwa_szkolenia_full,
                        'forma_szkolenia': "kurs (samokształcenie kierowane)",
                        'nazwa_organizatora': st.session_state.zapisana_firma,
                        'dzien_rozpoczecia': data_start.strftime("%d.%m.%Y"),
                        'dzien_zakonczenia': data_koniec.strftime("%d.%m.%Y"),
                        'cel_szkolenia': cel_szkolenia_text,
                        'miejscowosc_szkolenia': miejscowosc,
                        'data_wystawienia_zaswiadczenia': datetime.date.today().strftime("%d.%m.%Y"),
                        'nr_zaswiadczenia_wg_rejestru': nr_zaswiadczenia
                    }
                    
                    doc.render(context)
                    bio_certyfikat = BytesIO()
                    doc.save(bio_certyfikat)
                    
                    # Unikalny klucz dla przycisku pobierania, aby uniknąć błędów
                    st.download_button(
                        label="Pobierz gotowy certyfikat (.docx)",
                        data=bio_certyfikat.getvalue(),
                        file_name=f"Certyfikat_{uczestnik}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_cert"
                    )
                except Exception as e:
                    st.error(f"Wystąpił błąd: {e}")
                    st.warning("Upewnij się, że plik 'certyfikat_szablon.docx' istnieje i ma poprawne znaczniki.")

    st.markdown("---")

    with st.container(border=True):
        st.subheader("📋 Wygeneruj Tematykę Szkolenia (z godzinami)")
        st.info("Aplikacja automatycznie przeanalizuje treść szkolenia i przypisze szacowaną liczbę godzin.")
        
        if st.button("Generuj Tematykę Szkolenia"):
            with st.spinner("Analizuję treść szkolenia..."):
                try:
                    doc = DocxTemplate("tematyka_szkolenia_szablon.docx")
                    tematyka_z_godzinami = przypisz_godziny_do_tematow(st.session_state.finalna_tresc)
                    
                    if not tematyka_z_godzinami:
                        st.error("AI nie zwróciło tematów w poprawnym formacie. Spróbuj ponownie.")
                    else:
                        context = {'tematyka': tematyka_z_godzinami}
                        doc.render(context)
                        bio_tematyka = BytesIO()
                        doc.save(bio_tematyka)
                        st.download_button(
                            label="Pobierz gotową tematykę (.docx)",
                            data=bio_tematyka.getvalue(),
                            file_name=f"Tematyka_szkolenia_{st.session_state.wybrany_zawod}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="download_tematyka"
                        )
                except Exception as e:
                    st.error(f"Wystąpił błąd: {e}")
                    st.warning("Upewnij się, że plik 'tematyka_szkolenia_szablon.docx' istnieje i ma poprawną pętlę.")

    st.markdown("---")
    if st.button("Stwórz zupełnie nowe szkolenie"):
        st.session_state.etap = 1
        st.rerun()