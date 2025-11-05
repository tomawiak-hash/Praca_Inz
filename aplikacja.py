import streamlit as st
import google.generativeai as genai
from PyPDF2 import PdfReader
import os
import re
from docxtpl import DocxTemplate
from io import BytesIO
import datetime
from docx import Document

# ----- Konfiguracja Aplikacji
st.set_page_config(page_title="Inteligentny Generator Szkoleń BHP", page_icon="🎓", layout="wide")

# Wstaw tutaj swój klucz API z Google AI Studio
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# ----- Inicjalizacja "pamięci" aplikacji (session_state) - KOMPLETNA
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
if 'spis_tresci_do_tematyki' not in st.session_state:
    st.session_state.spis_tresci_do_tematyki = []
if 'cel_szkolenia_text' not in st.session_state:
    st.session_state.cel_szkolenia_text = ""
if 'tematyka_z_godzinami' not in st.session_state:
    st.session_state.tematyka_z_godzinami = []
if 'cached_test_content' not in st.session_state:
    st.session_state.cached_test_content = None
if 'cached_key_content' not in st.session_state:
    st.session_state.cached_key_content = None

# ----- Funkcje Aplikacji
def wczytaj_liste_zawodow_lokalnie():
    """
    Zwraca stałą, lokalną listę zawodów.
    """
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
    except Exception as e:
        return f"Błąd odczytu pliku PDF {kod_zawodu}.pdf: {e}"

@st.cache_data
def laduj_baze_wiedzy(folder_path='baza_wiedzy'):
    """
    Wczytuje treść wszystkich plików .txt i .pdf z podanego folderu.
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
                    if pdf_reader.is_encrypted:
                        print(f"Plik {nazwa_pliku} jest zaszyfrowany.")
                        continue
                    for page in pdf_reader.pages:
                         try:
                             pelny_tekst += (page.extract_text() or "") + "\n\n"
                         except Exception as page_e:
                             print(f"Błąd odczytu strony w pliku {nazwa_pliku}: {page_e}")
            elif nazwa_pliku.lower().endswith('.txt'):
                with open(sciezka_pliku, "r", encoding="utf-8") as f:
                    pelny_tekst += f.read() + "\n\n"
        except Exception as e:
            print(f"Błąd podczas wczytywania pliku {nazwa_pliku}: {e}")
    return pelny_tekst

def generuj_kompletne_szkolenie(firma, nazwa_zawodu, opis_zawodu, dodatkowe_zagrozenia):
    """
    POPRAWKA: Definicja funkcji przyjmuje teraz argument 'dodatkowe_zagrozenia'
    i NIE używa 'bazy_wiedzy', aby uniknąć błędów limitu tokenów.
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    
    prompt = f"""
    Jesteś ekspertem BHP i metodykiem szkoleń. Twoim zadaniem jest stworzenie kompletnego materiału szkoleniowego dla stanowiska '{nazwa_zawodu}' w firmie '{firma}'.

    MUSISZ RYGORYSTYCZNIE PRZESTRZEGAĆ PONIŻSZEJ STRUKTURY I ZAKRESU TEMATYCZNEGO, które są oparte na Załączniku nr 1 do Rozporządzenia Ministra Gospodarki i Pracy z dnia 27 lipca 2004 r.

    Twoje zadanie składa się z dwóch części. Rozwiń KAŻDY z poniższych punktów:

    CZĘŚĆ 1: INSTRUKTAŻ OGÓLNY
    (Tematy z ramowego programu instruktażu ogólnego)
    1. Istota bezpieczeństwa i higieny pracy.
    2. Zakres obowiązków i uprawnień pracodawcy, pracowników oraz poszczególnych komórek organizacyjnych zakładu pracy i organizacji społecznych w zakresie bezpieczeństwa i higieny pracy.
    3. Odpowiedzialność za naruszenie przepisów lub zasad bezpieczeństwa i higieny pracy.
    4. Zasady poruszania się na terenie zakładu pracy.
    5. Zagrożenia wypadkowe i zagrożenia dla zdrowia występujące w zakładzie i podstawowe środki zapobiegawcze.
    6. Podstawowe zasady bezpieczeństwa i higieny pracy związane z obsługą urządzeń technicznych oraz transportem wewnątrzzakładowym.
    7. Zasady przydziału odzieży roboczej i obuwia roboczego oraz środków ochrony indywidualnej, w tym w odniesieniu do stanowiska pracy instruowanego.
    8. Porządek i czystość w miejscu pracy - ich wpływ na zdrowie i bezpieczeństwo pracownika.
    9. Profilaktyczna opieka lekarska - zasady jej sprawowania w odniesieniu do stanowiska instruowanego.
    10. Podstawowe zasady ochrony przeciwpożarowej oraz postępowania w razie pożaru.
    11. Postępowanie w razie wypadku, w tym organizacja i zasady udzielania pierwszej pomocy.
    
    CZĘŚĆ 2: INSTRUKTAŻ STANOWISKOWY
    (Tematy z ramowego programu instruktażu stanowiskowego)
    1. Przygotowanie pracownika do wykonywania pracy (omówienie warunków pracy, czynników środowiska pracy, ryzyka zawodowego).
    2. Pokaz przez instruktora sposobu wykonywania pracy zgodnie z przepisami i zasadami BHP.
    3. Próbne wykonanie zadania przez pracownika pod kontrolą instruktora.
    4. Samodzielna praca pracownika pod nadzorem instruktora.
    5. Omówienie i ocena przebiegu wykonywania pracy przez pracownika.

    WYTYCZNE DODATKOWE:
    -   **PERSONALIZACJA:** Podczas rozwijania punktów Instruktażu Stanowiskowego (Część 2), musisz bezpośrednio nawiązywać do zagrożeń i zadań z 'OFICJALNEGO OPISU ZAWODU' oraz 'DODATKOWYCH ZAGROŻEŃ' podanych poniżej.
    -   **GŁĘBIA MERYTORYCZNA:** Każdy z 16 powyższych punktów (11+5) rozwiń w sposób wyczerpujący (minimum 2-3 akapity lub szczegółowa lista wypunktowana).
    -   **JAKOŚĆ I JĘZYK:** Pisz profesjonalnym, formalnym, ale zrozumiałym językiem. Powołuj się na akty prawne (np. "Zgodnie z Kodeksem Pracy...").
    -   **FORMATOWANIE:** Używaj Markdown. Tytuł główny jako nagłówek poziomu 1 (#), Części jako poziom 2 (##), a poszczególne punkty jako poziom 3 (###).

    --- OFICJALNY OPIS ZAWODU (DLA PERSONALIZACJI) ---
    {opis_zawodu}
    
    --- DODATKOWE ZAGROŻENIA WSKAZANE PRZEZ UŻYTKOWNIKA ---
    {dodatkowe_zagrozenia}
    
    Stwórz teraz kompletny materiał szkoleniowy zgodny z powyższymi wytycznymi.
    """
    
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.5))
        
        # Poprawione wyrażenie regularne, aby pasowało do nowej, stałej struktury
        st.session_state.spis_tresci_do_tematyki = re.findall(r"^(?:\d+)\.\s.*", response.text, re.MULTILINE)
        
        return response.text
    except Exception as e:
        st.error(f"Wystąpił błąd podczas komunikacji z AI: {e}")
        if "429" in str(e):
             st.warning("Przekroczono limit zapytań lub tokenów w darmowym planie Google AI. Spróbuj ponownie za chwilę.")
        return "Błąd generowania treści."

@st.cache_data
def generuj_cel_szkolenia(nazwa_szkolenia):
    """
    Generuje krótki, oficjalny cel szkolenia.
    """
    try:
        model = genai.GenerativeModel('gemini-pro-latest')
        prompt = f"Napisz krótki, jednozdaniowy, oficjalny cel szkolenia wstępnego BHP dla stanowiska '{nazwa_szkolenia}'. Cel zwięzły i formalny."
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.5))
        return response.text
    except Exception as e:
        return f"Błąd generowania celu: {e}"

@st.cache_data
def generuj_test_bhp(_finalna_tresc):
    """
    Generuje test (pytania) ORAZ klucz odpowiedzi, oddzielone separatorem.
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"""
    Jesteś egzaminatorem BHP. Otrzymujesz materiał szkoleniowy.
    Twoim zadaniem jest stworzenie testu (10 pytań A,B,C) oraz klucza odpowiedzi.

    WYTYCZNE FORMATOWANIA (BARDZO WAŻNE):
    1.  **NIE DODWAJ ŻADNEGO WSTĘPU:** Nie pisz "Doskonale...", "Oto test...", "Imię i nazwisko:". Zacznij OD RAZU od "1. Pytanie...".
    2.  **NIE UŻYWAJ POGRUBIENIA (MARKDOWN):** Nie używaj gwiazdek `**` do pogrubiania pytań. Pisz czystym tekstem.
    3.  **FORMAT PYTAŃ:**
        1.  [Treść pytania]
            A. [Odpowiedź A]
            B. [Odpowiedź B]
            C. [Odpowiedź C]
    4.  **SEPERATOR:** Po 10 pytaniach, wstaw DOKŁADNIE taką linię:
        ---KLUCZ---
    5.  **KLUCZ ODPOWIEDZI:** Po separatorze, wstaw klucz odpowiedzi w formacie:
        1. A
        2. B
        3. C
        ...itd.

    --- MATERIAŁ SZKOLENIOWY DO ANALIZY ---
    {_finalna_tresc}
    --- KONIEC MATERIAŁU ---

    Wygeneruj teraz test i klucz odpowiedzi zgodnie z wytycznymi.
    """
    try:
        response = model.generate_content(prompt)
        # Sprawdzamy, czy AI poprawnie wygenerowało separator
        if "---KLUCZ---" in response.text:
            # Dzielimy tekst na dwie części: test i klucz
            tresc_testu, klucz_odpowiedzi = response.text.split("---KLUCZ---", 1)
            return tresc_testu.strip(), klucz_odpowiedzi.strip()
        else:
            # Jeśli AI nie zastosowało się do poleceń
            st.error("AI nie wygenerowało poprawnie klucza odpowiedzi. Próbuję jeszcze raz...")
            return response.text, None # Zwracamy tylko test
    except Exception as e:
        st.error(f"Błąd AI podczas generowania testu: {e}")
        return "Nie udało się wygenerować testu.", None
    
@st.cache_data
def przypisz_godziny_do_tematow(_spis_tresci_lista):
    """
    Analizuje listę tematów i przypisuje szacowaną liczbę godzin.
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    tekst_spisu = "\n".join(_spis_tresci_lista)
    
    prompt = f"""
    Jesteś metodykiem szkoleń BHP. Otrzymujesz poniższy spis głównych tematów szkolenia. Oszacuj, ile godzin lekcyjnych (45 min) potrzeba na realizację każdego tematu.
    
    Odpowiedź zwróć TYLKO w formacie listy: "Nazwa tematu BEZ NUMERACJI | X"
    
    Przykład:
    Wprowadzenie do BHP | 1
    Zagrożenia na stanowisku pracy | 2

    Oto spis treści do analizy:
    {tekst_spisu}
    """
    try:
        response = model.generate_content(prompt)
        tematyka = []
        if hasattr(response, 'text'):
            for linia in response.text.splitlines():
                if '|' in linia:
                    try:
                        czesci = linia.split('|')
                        # ZMIANA: Bierzemy 'nazwa' bezpośrednio, bez usuwania numeracji
                        nazwa = czesci[0].strip() 
                        godziny = int(czesci[1].strip())
                        tematyka.append({"nazwa": nazwa, "godziny": godziny})
                    except (ValueError, IndexError):
                        continue
        else:
            st.error("Nie udało się uzyskać odpowiedzi od AI przy przypisywaniu godzin.")
        
        # Zwracamy tyle wierszy ile było w oryginalnym spisie
        return tematyka[:len(_spis_tresci_lista)] 
    except Exception as e:
        st.error(f"Błąd AI przy przypisywaniu godzin: {e}")
        return []

# ----- Funkcja pomocnicza do generowania dokumentów .docx
def generuj_docx(nazwa_szablonu, kontekst, nazwa_pliku_wynikowego):
    """
    Wypełnia szablon Worda i zwraca go jako obiekt BytesIO.
    """
    try:
        doc = DocxTemplate(nazwa_szablonu)
        doc.render(kontekst)
        bio = BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio
    except Exception as e:
        st.error(f"Błąd generowania pliku '{nazwa_pliku_wynikowego}': {e}")
        st.warning(f"Upewnij się, że plik '{nazwa_szablonu}' istnieje i ma poprawne znaczniki.")
        return None

# ----- Główny interfejs aplikacji
st.title("🎓 Inteligentny Generator Szkoleń BHP")

# --- Etap 1: Wybór zawodu i generowanie treści ---
if st.session_state.etap == 1:
    st.header("Krok 1: Wybierz zawód i wygeneruj kompletne szkolenie")
    
    lista_zawodow = wczytaj_liste_zawodow_lokalnie()
    baza_wiedzy_content = laduj_baze_wiedzy()

    wybrany_zawod_nazwa = st.selectbox("Wybierz zawód z listy:", options=list(lista_zawodow.keys()), index=None, placeholder="Wybierz zawód...")

    dodatkowe_zagrozenia = st.text_area("Wprowadź dodatkowe, specyficzne zagrożenia dla tego stanowiska (opcjonalnie):", key="extra_hazards")

    nazwa_firmy = st.text_input("Wprowadź nazwę firmy:", key="firma_input", value="Przykładowa Firma S.A.")
    
    if st.button("🚀 Generuj kompletne szkolenie"):
        if not wybrany_zawod_nazwa:
            st.warning("Proszę wybrać zawód z listy.")
        else:
            with st.spinner(f"Analizuję dane i tworzę pełne szkolenie dla: {wybrany_zawod_nazwa}..."):
                kod_zawodu = lista_zawodow[wybrany_zawod_nazwa]
                opis_zawodu = pobierz_opis_zawodu_lokalnie(kod_zawodu)
                
                if "Błąd:" in opis_zawodu:
                    st.error(opis_zawodu)
                else:
                    finalna_tresc = generuj_kompletne_szkolenie(nazwa_firmy, wybrany_zawod_nazwa, opis_zawodu, dodatkowe_zagrozenia)
                    if "Błąd generowania treści." not in finalna_tresc:
                        st.session_state.finalna_tresc = finalna_tresc
                        st.session_state.zapisana_firma = nazwa_firmy or "Twoja Firma"
                        st.session_state.wybrany_zawod = wybrany_zawod_nazwa
                        
                        st.write("--- DEBUG: Rozpoczynam generowanie danych dodatkowych ---") # <-- DEBUG 1
                        with st.spinner("Generowanie celu szkolenia..."):
                            st.session_state.cel_szkolenia_text = generuj_cel_szkolenia(f"Szkolenie wstępne BHP dla stanowiska '{wybrany_zawod_nazwa}'")
                        
                        st.write(f"--- DEBUG: Spis treści do analizy godzin ({len(st.session_state.spis_tresci_do_tematyki)} pozycji): ---") # <-- DEBUG 2
                        st.write(st.session_state.spis_tresci_do_tematyki) # <-- DEBUG 3 Wyświetlamy spis

                        with st.spinner("Przypisywanie godzin do tematów..."):
                            if st.session_state.spis_tresci_do_tematyki: 
                                st.session_state.tematyka_z_godzinami = przypisz_godziny_do_tematow(tuple(st.session_state.spis_tresci_do_tematyki)) 
                            else:
                                st.warning("Nie udało się wyodrębnić spisu treści do analizy godzin.")
                                st.session_state.tematyka_z_godzinami = []
                        
                        st.write(f"--- DEBUG: Wynik przypisania godzin ({len(st.session_state.tematyka_z_godzinami)} pozycji): ---") # <-- DEBUG 4
                        st.write(st.session_state.tematyka_z_godzinami) # <-- DEBUG 5 Wyświetlamy wynik godzin

                        st.write("--- DEBUG: Kończę generowanie danych dodatkowych ---") # <-- DEBUG 6


                        # Generujemy dane dodatkowe od razu
                        with st.spinner("Generowanie celu szkolenia..."):
                            st.session_state.cel_szkolenia_text = generuj_cel_szkolenia(f"Szkolenie wstępne BHP dla stanowiska '{wybrany_zawod_nazwa}'")
                        with st.spinner("Przypisywanie godzin do tematów..."):
                            if st.session_state.spis_tresci_do_tematyki:
                                st.session_state.tematyka_z_godzinami = przypisz_godziny_do_tematow(tuple(st.session_state.spis_tresci_do_tematyki))
                            else:
                                st.warning("Nie udało się wyodrębnić spisu treści do analizy godzin.")
                                st.session_state.tematyka_z_godzinami = []

                        st.session_state.etap = 2
                        st.rerun()

# --- Etap 2: Weryfikacja i przejście do dokumentacji ---
elif st.session_state.etap == 2:
    st.header("✅ Krok 2: Weryfikacja i pobieranie treści szkolenia")
    st.success("Pełna treść szkolenia została wygenerowana.")

    with st.expander("Pokaż/Ukryj treść szkolenia do weryfikacji"):
        st.markdown(st.session_state.finalna_tresc)

    st.markdown("---")
    st.subheader("1. Pobierz treść szkolenia")
    st.download_button(
        label="Pobierz treść szkolenia (.txt)",
        data=st.session_state.finalna_tresc.encode('utf-8'),
        file_name=f"Szkolenie_{st.session_state.wybrany_zawod}.txt",
        mime="text/plain",
        key="download_szkolenie_txt"
    )

    st.markdown("---")
    st.subheader("2. Przejdź do dokumentacji")
    if st.button("📄 Generuj dokumenty"):
        st.session_state.etap = 3
        st.rerun()
    if st.button("Stwórz inne szkolenie"):
        st.session_state.etap = 1
        st.rerun()

# --- Etap 3: Generator Dokumentacji ---
elif st.session_state.etap == 3:
    st.header("✅ Krok 3: Generator Dokumentacji")
    st.success("Wypełnij potrzebne dane i generuj poszczególne dokumenty.")

    st.markdown("---")
    st.subheader("Wspólne dane dla dokumentów:")

    st.caption("Format: Imię Nazwisko, Miejsce Pracy, Funkcja, Data Urodzenia (DD.MM.RRRR). Każdy uczestnik w nowej linii.")

    uczestnicy_input = st.text_area(
        # Etykieta pola
        "Lista uczestników (każdy w nowej linii, oddzielone przecinkami)",
        height=100,
        # Placeholder powtarzający format
        placeholder="Format: Imię Nazwisko, Miejsce Pracy, Funkcja, Data Urodzenia (DD.MM.RRRR)",
        key="uczestnicy_lista_input"
    )
    uczestnicy_dane_lista = []
    if uczestnicy_input:
        for i, linia in enumerate(uczestnicy_input.strip().splitlines()):
            czesci = [czesc.strip() for czesc in linia.split(',')]
            print(f"DEBUG: Linia {i+1} Dziennika Lekcyjnego: {czesci}")
            if len(czesci) == 4:
                uczestnicy_dane_lista.append({
                    'index': i + 1, 'imie_nazwisko': czesci[0], 'miejsce_pracy': czesci[1],
                    'funkcja': czesci[2], 'data_urodzenia': czesci[3], 'ocena': '', 'uwagi': ''
                })

    col_daty1, col_daty2 = st.columns(2)
    with col_daty1:
        data_start = st.date_input("Data rozpoczęcia:", key="doc_data_start", value=datetime.date.today())
        nr_kursu = st.text_input("Numer kursu:", "01/BHP/2025", key="doc_nr_kursu")
        kierownik_kursu = st.text_input("Kierownik kursu:", "Anna Kowalska", key="doc_kierownik")
    with col_daty2:
        data_koniec = st.date_input("Data zakończenia:", key="doc_data_koniec", value=datetime.date.today())
        miejscowosc = st.text_input("Miejscowość:", "Łódź", key="doc_miejscowosc")
        data_wystawienia_doc = st.date_input("Data wystawienia:", key="doc_data_wyst", value=datetime.date.today())

    st.markdown("---")

        # --- Generowanie Zaświadczenia ---
    with st.container(border=True):
        st.subheader("📄 Wygeneruj Zaświadczenie")
        imiona_uczestnikow = [u['imie_nazwisko'] for u in uczestnicy_dane_lista]
        wybrany_uczestnik_cert = st.selectbox("Wybierz uczestnika:", options=imiona_uczestnikow, key="cert_wybor_uczestnika", index=None, placeholder="Wybierz opcję...")
        nr_zaswiadczenia_cert = st.text_input("Nr zaświadczenia:", f"{nr_kursu}/1", key="cert_nr_zaswiadczenia")

        if st.button("Generuj Zaświadczenie", key="btn_cert"):
            if wybrany_uczestnik_cert:
                dane_wybranego = next((u for u in uczestnicy_dane_lista if u['imie_nazwisko'] == wybrany_uczestnik_cert), None)
                if dane_wybranego:
                    with st.spinner("Generowanie..."):
                        nazwa_szkolenia_full = f"Szkolenie wstępne BHP dla stanowiska '{st.session_state.wybrany_zawod}'"
                        cel_szkolenia_text = st.session_state.cel_szkolenia_text
                        context = {
                            'nazwa_organizatora_szkolenia': st.session_state.zapisana_firma,
                            'imie_nazwisko': dane_wybranego['imie_nazwisko'], 'data_urodzenia': dane_wybranego['data_urodzenia'],
                            'nazwa_szkolenia': nazwa_szkolenia_full, 'forma_szkolenia': "kurs (samokształcenie kierowane)",
                            'nazwa_organizatora': st.session_state.zapisana_firma,
                            'dzien_rozpoczecia': data_start.strftime("%d.%m.%Y"), 'dzien_zakonczenia': data_koniec.strftime("%d.%m.%Y"),
                            'cel_szkolenia': cel_szkolenia_text, 'miejscowosc_szkolenia': miejscowosc,
                            'data_wystawienia_zaswiadczenia': data_wystawienia_doc.strftime("%d.%m.%Y"),
                            'nr_zaswiadczenia_wg_rejestru': nr_zaswiadczenia_cert
                        }
                        plik_docx = generuj_docx("certyfikat_szablon.docx", context, f"Certyfikat_{dane_wybranego['imie_nazwisko']}.docx")
                        if plik_docx:
                            st.download_button(label="Pobierz (.docx)", data=plik_docx, file_name=f"Certyfikat_{dane_wybranego['imie_nazwisko']}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_cert_{dane_wybranego['imie_nazwisko']}")
                else: st.error("Nie znaleziono danych uczestnika.")
            else: st.warning("Wybierz uczestnika.")

    st.markdown("---")

    # --- Generowanie Tematyki Szkolenia (NOWA METODA) ---
    with st.container(border=True):
        st.subheader("📋 Wygeneruj Tematykę Szkolenia")
        if st.button("Generuj Tematykę", key="btn_tematyka"):
            with st.spinner("Przygotowuję tematykę..."):
                tematyka_z_godzinami = st.session_state.tematyka_z_godzinami
                if tematyka_z_godzinami:
                    try:
                        doc = Document("tematyka_szablon_uproszczony.docx") # <-- Używamy uproszczonego szablonu
                        if doc.tables:
                            table = doc.tables[0]
                            for i, temat in enumerate(tematyka_z_godzinami):
                                row_cells = table.add_row().cells
                                row_cells[0].text = str(i + 1)
                                row_cells[1].text = temat.get('nazwa', '')
                                row_cells[2].text = str(temat.get('godziny', '?'))
                                row_cells[3].text = "0"
                            # Można dodać kod do rysowania krawędzi, jeśli potrzeba
                            bio = BytesIO()
                            doc.save(bio)
                            bio.seek(0)
                            st.download_button(label="Pobierz (.docx)", data=bio, file_name=f"Tematyka_{st.session_state.wybrany_zawod}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_tematyka")
                        else: st.error("Brak tabeli w szablonie.")
                    except Exception as e: st.error(f"Błąd: {e}")
                else: st.error("Brak danych tematyki.")

    st.markdown("---")

    # --- Generowanie Wykazu Uczestników (NOWA METODA) ---
    with st.container(border=True):
        st.subheader("👥 Wygeneruj Wykaz Uczestników")
        if st.button("Generuj Wykaz", key="btn_wykaz"):
             if uczestnicy_dane_lista:
                with st.spinner("Generowanie..."):
                    try:
                        doc = Document("wykaz_uczestnikow_szablon_uproszczony.docx") # <-- Używamy uproszczonego szablonu
                        if doc.tables:
                            table = doc.tables[0]
                            for i, u in enumerate(uczestnicy_dane_lista):
                                row_cells = table.add_row().cells
                                row_cells[0].text = str(i + 1)
                                row_cells[1].text = u.get('imie_nazwisko', '')
                                row_cells[2].text = u.get('miejsce_pracy', '')
                                row_cells[3].text = u.get('funkcja', '')
                                row_cells[4].text = u.get('data_urodzenia', '')
                                row_cells[5].text = "" # Obecność
                            # Można dodać kod do rysowania krawędzi
                            bio = BytesIO()
                            doc.save(bio)
                            bio.seek(0)
                            st.download_button(label="Pobierz (.docx)", data=bio, file_name=f"Wykaz_{st.session_state.wybrany_zawod}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_wykaz")
                        else: st.error("Brak tabeli w szablonie.")
                    except Exception as e: st.error(f"Błąd: {e}")
             else: st.warning("Wprowadź listę uczestników.")

    st.markdown("---")

    # --- Generowanie Protokołu Egzaminu (NOWA METODA DLA TABELI + docxtpl dla reszty) ---
    with st.container(border=True):
        st.subheader("📝 Wygeneruj Protokół Egzaminu")

        st.caption("Format: Imię Nazwisko, Miejsce Pracy, Funkcja. Każdy uczestnik w nowej linii.")
        komisja_input = st.text_area("Członkowie komisji)", height=80, key="egz_komisja")
        oceny_dict = {}
        if uczestnicy_dane_lista:
            st.write("**Oceny:**")
            for u in uczestnicy_dane_lista:
                oceny_dict[u['imie_nazwisko']] = st.selectbox(f"Ocena dla {u['imie_nazwisko']}:", ["brak", "2", "3", "4", "5"], key=f"ocena_{u['index']}")

        if st.button("Generuj Protokół", key="btn_protokol"):
            if uczestnicy_dane_lista and komisja_input:
                with st.spinner("Generowanie..."):
                    try:
                        # Krok 1: Wypełnij pola poza tabelą za pomocą docxtpl
                        doc_tpl = DocxTemplate("protokol_egzaminu_szablon_uproszczony.docx") # <-- Używamy uproszczonego szablonu
                        komisja_lista = [k.strip() for k in komisja_input.strip().splitlines()]
                        context_header_footer = {
                            'rodzaj_szkolenia': f"Szkolenie wstępne BHP dla stanowiska '{st.session_state.wybrany_zawod}'",
                            'data_egzaminu': data_koniec.strftime("%d.%m.%Y"), 'nr_kursu': nr_kursu,
                            'komisja_1_nazwisko': komisja_lista[0] if len(komisja_lista) > 0 else '',
                            'komisja_2_nazwisko': komisja_lista[1] if len(komisja_lista) > 1 else '',
                            'komisja_3_nazwisko': komisja_lista[2] if len(komisja_lista) > 2 else '',
                            'miejsce': miejscowosc, 'data_wystawienia': data_wystawienia_doc.strftime("%d.%m.%Y"),
                            'nazwa_organizatora': st.session_state.zapisana_firma
                        }
                        doc_tpl.render(context_header_footer)
                        temp_bio = BytesIO()
                        doc_tpl.save(temp_bio)
                        temp_bio.seek(0)

                        # Krok 2: Otwórz wypełniony dokument i dodaj wiersze do tabeli
                        doc = Document(temp_bio)
                        if doc.tables:
                            table = doc.tables[0]
                            for i, u in enumerate(uczestnicy_dane_lista):
                                row_cells = table.add_row().cells
                                row_cells[0].text = str(i + 1)
                                row_cells[1].text = u.get('imie_nazwisko', '')
                                row_cells[2].text = oceny_dict.get(u['imie_nazwisko'], 'brak')
                                row_cells[3].text = u.get('uwagi', '')
                            # Można dodać kod do krawędzi
                            final_bio = BytesIO()
                            doc.save(final_bio)
                            final_bio.seek(0)
                            st.download_button(label="Pobierz (.docx)", data=final_bio, file_name=f"Protokol_{st.session_state.wybrany_zawod}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_protokol")
                        else: st.error("Brak tabeli w szablonie.")
                    except Exception as e: st.error(f"Błąd: {e}")
            else: st.warning("Wprowadź listę uczestników i komisję.")

    st.markdown("---")

    # --- Generowanie Dziennika Zajęć (NOWA METODA DLA TABELI + docxtpl dla reszty) ---
    with st.container(border=True):
        st.subheader("🗓️ Wygeneruj Dziennik Zajęć")
        data_zajec = st.date_input("Data zajęć:", key="dz_data", value=data_start)

        if st.button("Generuj Dziennik Zajęć", key="btn_dz_zajec"):
             with st.spinner("Generowanie..."):
                tematyka_z_godzinami = st.session_state.tematyka_z_godzinami
                if tematyka_z_godzinami:
                    try:
                        # Krok 1: Wypełnij stopkę za pomocą docxtpl
                        doc_tpl = DocxTemplate("dziennik_zajec_szablon_uproszczony.docx") # <-- Używamy uproszczonego szablonu
                        context_footer = {'nazwa_organizatora': st.session_state.zapisana_firma}
                        doc_tpl.render(context_footer)
                        temp_bio = BytesIO()
                        doc_tpl.save(temp_bio)
                        temp_bio.seek(0)

                        # Krok 2: Otwórz i dodaj wiersze do tabeli
                        doc = Document(temp_bio)
                        if doc.tables:
                            table = doc.tables[0]
                            zajecia_do_szablonu = [{'data': data_zajec.strftime("%d.%m.%Y"), 'godziny': t.get('godziny', '?'), 'przedmiot': "Szkolenie BHP", 'temat': t.get('nazwa', 'Brak tematu')} for t in tematyka_z_godzinami]
                            for i, z in enumerate(zajecia_do_szablonu):
                                row_cells = table.add_row().cells
                                row_cells[0].text = str(i + 1)
                                row_cells[1].text = z['data']
                                row_cells[2].text = str(z['godziny'])
                                row_cells[3].text = z['przedmiot']
                                row_cells[4].text = z['temat']
                                row_cells[5].text = "" # Podpis
                            # Można dodać kod do krawędzi
                            final_bio = BytesIO()
                            doc.save(final_bio)
                            final_bio.seek(0)
                            st.download_button(label="Pobierz (.docx)", data=final_bio, file_name=f"Dziennik_Zajec_{st.session_state.wybrany_zawod}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_dz_zajec")
                        else: st.error("Brak tabeli w szablonie.")
                    except Exception as e: st.error(f"Błąd: {e}")
                else: st.error("Nie udało się wcześniej wygenerować tematyki.")

    st.markdown("---")

# --- Sekcja generowania DZIENNIKA LEKCYJNEGO (NOWA METODA DLA TABELI + docxtpl dla reszty) ---
    with st.container(border=True):
         st.subheader("📓 Wygeneruj Dziennik Lekcyjny")
         st.info("Wprowadź dane wykładowców.")
         st.caption("Format: Imię Nazwisko, Miejsce Pracy, Funkcja (każdy wykładowca w nowej linii)")
         wykladowcy_input = st.text_area(
             "Wykładowcy:",
             height=100,
             key="dz_lek_wykladowcy"
         )

         if st.button("Generuj Dziennik Lekcyjny", key="btn_dz_lek"):
             # Sprawdzenie 1: Czy pole nie jest puste?
             if not wykladowcy_input or not wykladowcy_input.strip():
                  st.warning("Wprowadź dane przynajmniej jednego wykładowcy.")
             else:
                 with st.spinner("Przetwarzanie danych wykładowców..."):

                    # Krok 1: Przetwarzanie danych wejściowych z rygorystyczną walidacją
                    wykladowcy_lista = []
                    bledne_linie = []
                    poprawne_linie_znaleziono = False
                    print("\n--- Rozpoczynam przetwarzanie wykładowców ---") # Debug Start

                    if wykladowcy_input:
                        for i, linia in enumerate(wykladowcy_input.strip().splitlines()):
                            oryginalna_linia = linia.strip()
                            if not oryginalna_linia:
                                print(f"DEBUG: Linia {i+1} pominięta (pusta).")
                                continue # Pomiń puste linie

                            # Dzielimy tylko po pierwszym dwóch przecinkach,
                            # agresywnie usuwamy białe znaki
                            czesci_raw = linia.split(',', 2)
                            czesci = [czesc.strip() for czesc in czesci_raw if czesc.strip()] # Usuń puste części po strip()

                            print(f"DEBUG: Linia {i+1} Dziennika Lekcyjnego: Oryginał='{oryginalna_linia}', Po podziale={czesci_raw}, Po strip i filtracji={czesci}")

                            # NAJBARDZIEJ RYGORYSTYCZNE SPRAWDZENIE
                            if len(czesci) == 3:
                                # BEZPIECZNE TWORZENIE SŁOWNIKA
                                wykladowcy_lista.append({
                                    'imie_nazwisko': czesci[0],
                                    'miejsce_pracy': czesci[1],
                                    'funkcja': czesci[2],
                                    'przedmiot': '', 'godziny_plan': 0, 'godziny_wykonanie': 0
                                })
                                poprawne_linie_znaleziono = True
                                print(f"DEBUG: Linia {i+1} przetworzona poprawnie.")
                            else: # Jeśli len(czesci) jest inne niż 3
                                bledne_linie.append(f"Linia {i+1} (niepoprawny format - znaleziono {len(czesci)} zamiast 3 części): '{oryginalna_linia}'")
                                print(f"DEBUG: Linia {i+1} odrzucona (zła liczba części).")

                    print(f"--- Zakończono przetwarzanie. Poprawnych: {len(wykladowcy_lista)}, Błędnych: {len(bledne_linie)} ---") # Debug End

                    # Wyświetl ostrzeżenia o błędnych liniach
                    if bledne_linie:
                        st.warning("Niektóre linie w polu 'Wykładowcy' zostały pominięte:")
                        for blad in bledne_linie: st.warning(f"- {blad}")

                    # Sprawdzenie 2: Czy udało się przetworzyć *jakiekolwiek* poprawnie?
                    if not poprawne_linie_znaleziono:
                        st.error("Nie udało się przetworzyć żadnych danych wykładowców. Sprawdź format (Imię Nazwisko, Miejsce Pracy, Funkcja).")
                    else:
                        # Jeśli mamy poprawne dane, kontynuuj generowanie
                        with st.spinner("Generowanie dokumentu Dziennika Lekcyjnego..."):
                            try:
                                doc_tpl = DocxTemplate("dziennik_lekcyjny_szablon_uproszczony.docx")
                                context_header = {
                                    'nazwa_organizatora': st.session_state.zapisana_firma,
                                    'dla_kogo': f"Szkolenie dla {st.session_state.wybrany_zawod}",
                                    'data_od': data_start.strftime("%d.%m.%Y"), 'data_do': data_koniec.strftime("%d.%m.%Y"),
                                    'miejsce': miejscowosc, 'kierownik_nazwisko': kierownik_kursu,
                                    'kierownik_miejsce_pracy_funkcja': "Kierownik Szkolenia"
                                }
                                doc_tpl.render(context_header)
                                temp_bio = BytesIO()
                                doc_tpl.save(temp_bio)
                                temp_bio.seek(0)
                                doc = Document(temp_bio)

                                tematyka_z_godzinami = st.session_state.tematyka_z_godzinami
                                total_godziny_plan = 0
                                total_godziny_wykonanie = 0
                                
                                for w in wykladowcy_lista:
                                    w['przedmiot'] = ''
                                    w['godziny_plan'] = 0
                                    w['godziny_wykonanie'] = 0

                                if tematyka_z_godzinami:
                             # Upewniamy się, że wykladowcy_lista na pewno nie jest pusta
                                    if wykladowcy_lista:
                                        for i, temat in enumerate(tematyka_z_godzinami):
                                      # Sprawdzamy czy 'temat' jest słownikiem i ma klucz 'godziny'
                                            if isinstance(temat, dict) and 'godziny' in temat:
                                                idx_wykladowcy = i % len(wykladowcy_lista) # Równomierny podział
                                                godziny_tematu = temat.get('godziny', 0)
                                          # Sprawdzenie typu przed dodaniem
                                                if isinstance(godziny_tematu, int):
                                              # Sprawdzamy czy indeks jest poprawny
                                                    if idx_wykladowcy < len(wykladowcy_lista):
                                                     wykladowcy_lista[idx_wykladowcy]['przedmiot'] += temat.get('nazwa', 'Brak nazwy tematu') + "\n"
                                                    wykladowcy_lista[idx_wykladowcy]['godziny_plan'] += godziny_tematu
                                                    wykladowcy_lista[idx_wykladowcy]['godziny_wykonanie'] += godziny_tematu
                                                    total_godziny_plan += godziny_tematu
                                                    total_godziny_wykonanie += godziny_tematu
                                                else:
                                                  print(f"DEBUG: Błąd indeksu wykładowcy {idx_wykladowcy} przy liście o długości {len(wykladowcy_lista)}")
                                            else:
                                               st.warning(f"Pominięto godziny dla tematu '{temat.get('nazwa', '')}' - nieprawidłowy format godzin.")
                                        else:
                                          st.warning(f"Pominięto temat nr {i+1} - nieprawidłowy format danych tematyki.")
                                    else:
                                        st.warning("Brak poprawnych danych wykładowców do przypisania tematów.")
                                else:
                                    st.warning("Brak danych o tematyce szkolenia do przypisania wykładowcom.")

                                if doc.tables and len(doc.tables) > 0:
                                    table = doc.tables[0]
                                    for i, w in enumerate(wykladowcy_lista):
                                        # Bezpieczny dostęp do danych wykładowcy
                                        row_cells = table.add_row().cells
                                        if len(row_cells) >= 7: # Sprawdź liczbę komórek
                                            row_cells[0].text = str(i + 1)
                                            row_cells[1].text = w.get('imie_nazwisko', '')
                                            row_cells[2].text = w.get('miejsce_pracy', '')
                                            row_cells[3].text = w.get('funkcja', '')
                                            row_cells[4].text = w.get('przedmiot', '').strip()
                                            row_cells[5].text = str(w.get('godziny_plan', 0))
                                            row_cells[6].text = str(w.get('godziny_wykonanie', 0))
                                        else:
                                            print(f"DEBUG: Nieprawidłowa liczba komórek w wierszu {i+1} tabeli Dziennika Lekcyjnego.")


                                    row_cells = table.add_row().cells
                                    if len(row_cells) >= 7:
                                        row_cells[4].text = "Razem:"
                                        row_cells[5].text = str(total_godziny_plan)
                                        row_cells[6].text = str(total_godziny_wykonanie)

                                    final_bio = BytesIO()
                                    doc.save(final_bio)
                                    final_bio.seek(0)
                                    st.download_button(label="Pobierz Dziennik Lekcyjny (.docx)", data=final_bio, file_name=f"Dziennik_Lekcyjny_{st.session_state.wybrany_zawod}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_dz_lek")
                                else:
                                    st.error("Brak tabeli w szablonie 'dziennik_lekcyjny_szablon_uproszczony.docx'.")
                            except Exception as e:
                                   st.error(f"Wystąpił błąd podczas generowania Dziennika Lekcyjnego: {e}")
                                   st.warning("Upewnij się, że plik szablonu istnieje.")

    st.markdown("---")# Ten separator powinien być na poprawnym poziomie
    
    # --- Generowanie Rejestru Zaświadczeń (NOWA METODA DLA TABELI + docxtpl dla reszty) ---
    with st.container(border=True):
        st.subheader("📚 Wygeneruj Rejestr Wydanych Zaświadczeń")
        if st.button("Generuj Rejestr", key="btn_rejestr"):
            if uczestnicy_dane_lista:
                with st.spinner("Generowanie..."):
                    try:
                        # Krok 1: Wypełnij nagłówek i stopkę za pomocą docxtpl
                        doc_tpl = DocxTemplate("rejestr_zaswiadczen_szablon_uproszczony.docx") # <-- Używamy uproszczonego szablonu
                        context_header_footer = {
                            'rodzaj_szkolenia': "wstępnego", 'nr_kursu': nr_kursu,
                            'kierownik_nazwisko': kierownik_kursu,
                            'data_wystawienia': data_wystawienia_doc.strftime("%d.%m.%Y"),
                            'nazwa_organizatora': st.session_state.zapisana_firma
                        }
                        doc_tpl.render(context_header_footer)
                        temp_bio = BytesIO()
                        doc_tpl.save(temp_bio)
                        temp_bio.seek(0)

                        # Krok 2: Otwórz i dodaj wiersze do tabeli
                        doc = Document(temp_bio)
                        if doc.tables:
                            table = doc.tables[0]
                            zaswiadczenia_do_rejestru = [{'numer': f"{nr_kursu}/{i+1}", 'imie_nazwisko': u['imie_nazwisko'], 'uwagi': ''} for i, u in enumerate(uczestnicy_dane_lista)]
                            for i, z in enumerate(zaswiadczenia_do_rejestru):
                                row_cells = table.add_row().cells
                                row_cells[0].text = z['numer']
                                row_cells[1].text = z['imie_nazwisko']
                                row_cells[2].text = "" # Podpis
                                row_cells[3].text = z['uwagi']
                            # Można dodać kod do krawędzi
                            final_bio = BytesIO()
                            doc.save(final_bio)
                            final_bio.seek(0)
                            st.download_button(label="Pobierz (.docx)", data=final_bio, file_name=f"Rejestr_{st.session_state.wybrany_zawod}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_rejestr")
                        else: st.error("Brak tabeli w szablonie.")
                    except Exception as e: st.error(f"Błąd: {e}")
            else: st.warning("Wprowadź listę uczestników.")
    
    st.markdown("---")

# --- Sekcja generowania TESTU SPRAWDZAJĄCEGO ---
    with st.container(border=True):
        st.subheader("📝 Wygeneruj Test Sprawdzający")
        st.info("Aplikacja przeanalizuje całą treść szkolenia i na jej podstawie stworzy test oraz osobny klucz odpowiedzi.")

        # Przycisk "Generuj" teraz tylko wywołuje AI i zapisuje wyniki w pamięci
        if st.button("Generuj Test i Klucz Odpowiedzi", key="btn_test"):
            with st.spinner("Generowanie testu (to może chwilę potrwać)..."):
                
                # Wywołujemy zaktualizowaną funkcję AI, która zwraca DWIE wartości
                tresc_testu, klucz_odpowiedzi = generuj_test_bhp(st.session_state.finalna_tresc)
                
                if klucz_odpowiedzi: # Jeśli udało się poprawnie rozdzielić
                    # Zapisujemy wyniki w pamięci aplikacji
                    st.session_state.cached_test_content = tresc_testu
                    st.session_state.cached_key_content = klucz_odpowiedzi
                    st.success("Test i klucz odpowiedzi zostały wygenerowane! Możesz je teraz pobrać.")
                else:
                    # Jeśli AI zawiodło i nie dało klucza, zapisujemy cokolwiek dało
                    st.session_state.cached_test_content = tresc_testu
                    st.session_state.cached_key_content = None # Resetujemy klucz
                    st.warning("Nie udało się automatycznie oddzielić klucza odpowiedzi. Plik testu może zawierać obie części.")

        # ----- Przyciski pobierania (pojawią się po wygenerowaniu) -----
        
        # Przycisk pobierania TESTU (bez klucza)
        if 'cached_test_content' in st.session_state and st.session_state.cached_test_content:
            context_test = {
                'tresc_testu': st.session_state.cached_test_content
                # Zauważ, że nie ma tu 'nazwa_szkolenia', ponieważ przenieśliśmy to do szablonu
            }
            # Używamy szablonu 'test_szablon.docx'
            plik_docx_test = generuj_docx("test_szablon.docx", context_test, f"Test_{st.session_state.wybrany_zawod}.docx")
            if plik_docx_test:
                st.download_button(
                    label="Pobierz gotowy TEST (.docx)",
                    data=plik_docx_test,
                    file_name=f"Test_{st.session_state.wybrany_zawod}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_test"
                )

        # Przycisk pobierania KLUCZA ODPOWIEDZI (osobno)
        if 'cached_key_content' in st.session_state and st.session_state.cached_key_content:
            context_key = {
                'klucz_odpowiedzi': st.session_state.cached_key_content
            }
            # Używamy nowego szablonu 'klucz_odpowiedzi_szablon.docx'
            plik_docx_key = generuj_docx("klucz_odpowiedzi_szablon.docx", context_key, f"Klucz_{st.session_state.wybrany_zawod}.docx")
            if plik_docx_key:
                st.download_button(
                    label="Pobierz KLUCZ ODPOWIEDZI (.docx)",
                    data=plik_docx_key,
                    file_name=f"Klucz_odpowiedzi_{st.session_state.wybrany_zawod}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_key"
                )

    st.markdown("---")

    if st.button("Stwórz zupełnie nowe szkolenie"):
        st.session_state.etap = 1
        st.rerun()