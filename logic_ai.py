import google.generativeai as genai
import streamlit as st
import re
import json
import time

# Konfiguracja modelu
MODEL_NAME = 'gemini-1.5-pro' # Możesz tu użyć 1.5-flash, 2.0-flash lub pro

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    pass 

def generuj_kompletne_szkolenie(firma, nazwa_zawodu, opis_zawodu, dodatkowe_zagrozenia, obowiazki, srodowisko):
    model = genai.GenerativeModel(MODEL_NAME)
    
    prompt = f"""
    Jesteś ekspertem BHP i doświadczonym metodykiem. Twoim zadaniem jest stworzenie KOMPLETNEGO PROGRAMU SZKOLENIA WSTĘPNEGO (Instruktaż Ogólny i Stanowiskowy) dla stanowiska '{nazwa_zawodu}' w firmie '{firma}'.

    DANE DO PERSONALIZACJI:
    - Opis zawodu (Baza): {opis_zawodu}
    - Główne obowiązki: {obowiazki}
    - Środowisko pracy: {srodowisko}
    - Dodatkowe zagrożenia: {dodatkowe_zagrozenia}

    WYMAGANIA PRAWNE:
    Opieraj się na Rozporządzeniu Ministra Gospodarki i Pracy z dnia 27 lipca 2004 r. w sprawie szkolenia w dziedzinie bezpieczeństwa i higieny pracy (tekst jednolity: Dz.U. 2024 poz. 1327).

    NIE WPISUJ w treści czasu trwania (np. "3 godziny"), ponieważ jest on ustalany w oddzielnym harmonogramie.
    STRUKTURA (Obowiązkowa):
    CZĘŚĆ I: INSTRUKTAŻ OGÓLNY (Czas trwania: min. 3h lekcyjne)
    Rozwiń merytorycznie każdy z poniższych punktów ramowych:
    1. Istota bezpieczeństwa i higieny pracy.
    2. Zakres obowiązków i uprawnień pracodawcy oraz pracowników.
    3. Odpowiedzialność za naruszenie przepisów lub zasad BHP.
    4. Zasady poruszania się na terenie zakładu pracy (uwzględnij środowisko: {srodowisko}).
    5. Zagrożenia wypadkowe i zagrożenia dla zdrowia występujące w zakładzie i podstawowe środki zapobiegawcze.
    6. Podstawowe zasady BHP związane z obsługą urządzeń technicznych oraz transportem wewnątrzzakładowym.
    7. Zasady przydziału odzieży roboczej i środków ochrony indywidualnej (w tym okularów korygujących).
    8. Porządek i czystość w miejscu pracy.
    9. Profilaktyczna opieka lekarska (badania wstępne, okresowe, kontrolne).
    10. Podstawowe zasady ochrony przeciwpożarowej oraz postępowania w razie pożaru.
    11. Postępowanie w razie wypadku i zasady udzielania pierwszej pomocy.

    CZĘŚĆ II: INSTRUKTAŻ STANOWISKOWY (Czas trwania: min. 2h lekcyjne)
    Skup się na specyfice pracy biurowej i ergonomii. Rozwiń następujące punkty:
    A. Przygotowanie pracownika do wykonywania pracy:
       - Omówienie warunków pracy (oświetlenie, ogrzewanie, wentylacja w środowisku: {srodowisko}).
       - Elementy stanowiska roboczego i ergonomia (prawidłowa regulacja krzesła, ustawienie monitora, podnóżek, klawiatura).
    
    B. Przebieg procesu pracy:
       - Omów bezpieczne wykonywanie czynności typowych dla obowiązków: {obowiazki}.
       - Praca przy monitorze ekranowym (przerwy w pracy, ćwiczenia oczu).
    
    C. Zagrożenia i czynniki uciążliwe na stanowisku:
       - Czynniki fizyczne (np. prąd elektryczny, upadek, potknięcie).
       - Czynniki uciążliwe i psychofizyczne (obciążenie układu mięśniowo-szkieletowego, obciążenie wzroku, stres).
       - Omówienie ryzyka zawodowego dla tego stanowiska.
    
    D. Sposoby ochrony przed zagrożeniami i postępowanie w sytuacjach awaryjnych:
       - Zasady bezpiecznej obsługi sprzętu biurowego (niszczarki, kserokopiarki).
       - Postępowanie w razie awarii sprzętu lub zasilania.

    WYTYCZNE KRYTYCZNE ("SAFETY RULES"):
    1. **LICZBY I NORMY:** Nie wymyślaj wartości liczbowych! Jeśli podajesz parametry (np. oświetlenie, dźwiganie), MUSISZ powołać się na konkretną normę (np. "zgodnie z normą PN-EN 12464-1..." lub "zgodnie z Rozporządzeniem w sprawie ręcznych prac transportowych"). Jeśli nie znasz dokładnej wartości, napisz: "parametry zgodne z obowiązującymi normami".
    2. **PERSONALIZACJA:** W Instruktażu Stanowiskowy UŻYJ konkretnych przykładów z sekcji "Główne obowiązki" i "Dodatkowe zagrożenia".
    3. **STYLISTYKA:** Używaj punktorów, pogrubień i języka instruktażowego.

    FORMATOWANIE KOŃCOWE (BARDZO WAŻNE):
    1. Nie używaj ŻADNYCH wstępów typu "Oczywiście", "Oto szkolenie", "Poniżej znajduje się...".
    2. Zacznij tekst BEZPOŚREDNIO od nagłówka tytułowego (SZCZEGÓŁOWY PROGRAM...).
    3. Styl: Język urzędowy, instruktażowy ("Pracownik ma obowiązek...", "Zabrania się...").
    4. Używaj pogrubień dla kluczowych terminów.

    Stwórz teraz kompletny, profesjonalny materiał szkoleniowy.
    """
    
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.3))
        # Dodatkowe zabezpieczenie w Pythonie - usuwamy ewentualny wstęp, jeśli model nie posłucha
        tekst = response.text.strip()
        smieci_na_poczatku = ["Oczywiście", "Oto", "Poniżej", "Jasne", "W odpowiedzi", "Zgoda"]
        
        # Jeśli tekst zaczyna się od "śmiecia", szukamy właściwego tytułu
        for smiec in smieci_na_poczatku:
            if tekst.startswith(smiec):
                # Szukamy pierwszego wystąpienia słowa "SZCZEGÓŁOWY" lub "CZĘŚĆ" lub "#"
                match = re.search(r"(SZCZEGÓŁOWY|CZĘŚĆ|#)", tekst)
                if match:
                    tekst = tekst[match.start():]
                break
                
        return tekst
    except Exception as e:
        st.error(f"Błąd API: {e}")
        return "Błąd generowania treści."

def koryguj_tresc_szkolenia(stara_tresc, uwagi_uzytkownika):
    """
    Pozwala użytkownikowi zmienić fragment szkolenia bez generowania całości od nowa.
    """
    model = genai.GenerativeModel(MODEL_NAME)
    
    prompt = f"""
    Jesteś redaktorem dokumentacji BHP. Użytkownik zgłasza uwagi do istniejącego tekstu szkolenia.
    
    TWOJE ZADANIE:
    Wprowadź poprawki do poniższego tekstu zgodnie z wytycznymi użytkownika. 
    Zachowaj resztę tekstu bez zmian, chyba że uwagi wymuszają szerszą edycję.
    Zachowaj formatowanie Markdown (pogrubienia, nagłówki).
    
    UWAGI UŻYTKOWNIKA: "{uwagi_uzytkownika}"
    
    TEKST ORYGINALNY:
    {stara_tresc}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Błąd korekty: {e}"

@st.cache_data
def generuj_cel_szkolenia(nazwa_szkolenia):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Jesteś metodykiem nauczania dorosłych.
        Sformułuj CEL SZKOLENIA wstępnego BHP dla stanowiska: '{nazwa_szkolenia}'.
        ZASADY:
        1. Metoda SMART.
        2. Skup się na nabyciu wiedzy i umiejętności.
        3. Jedno, rozbudowane zdanie.
        4. Bez wstępów.
        5. Start: "Celem szkolenia jest..."
        """
        response = model.generate_content(prompt)
        tekst = response.text.replace('*', '').replace('#', '').replace('_', '')
        zbedne = ["Oczywiście", "oto propozycja", ":", "\n"]
        for z in zbedne: tekst = tekst.replace(z, ' ')
        return " ".join(tekst.split()).strip()
    except Exception:
        return "Przygotowanie pracownika do bezpiecznego i ergonomicznego wykonywania pracy na powierzonym stanowisku biurowym."

@st.cache_data
def generuj_test_bhp(_finalna_tresc):
    """Generuje listę pytań kontrolnych (otwartych)."""
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
    Jesteś instruktorem BHP. Przygotuj zestaw 10 PYTAŃ KONTROLNYCH (otwartych) oraz ZADAŃ PRAKTYCZNYCH do instruktażu stanowiskowego.

    FORMAT:
    1. [Pytanie/Zadanie] - [Oczekiwana odpowiedź/Działanie]
    
    Oprzyj pytania o poniższy materiał:
    {_finalna_tresc[:35000]} 
    
    Nie dodawaj wstępów. Tylko lista numerowana.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip(), None 
    except Exception as e:
        st.error(f"Błąd generowania pytań: {e}")
        return "Błąd.", None

@st.cache_data
def przypisz_godziny_do_tematow(_spis_tresci_lista):
    """
    Funkcja przypisuje godziny zgodnie z Ramowym Programem Szkolenia (Dz.U.).
    Obsługuje ułamkowe godziny lekcyjne.
    """
    
    # --- NOWA LISTA AWARYJNA (Zgodna z Rozporządzeniem) ---
    lista_awaryjna = [
        {
            "nazwa": "Istota BHP, zakres obowiązków i uprawnień, odpowiedzialność pracownicza",
            "godziny": 0.6
        },
        {
            "nazwa": "Zasady poruszania się po zakładzie, zagrożenia wypadkowe i środki zapobiegawcze",
            "godziny": 0.5
        },
        {
            "nazwa": "Zasady BHP przy obsłudze urządzeń technicznych i transporcie wewnątrzzakładowym",
            "godziny": 0.4
        },
        {
            "nazwa": "Odzież robocza, porządek w miejscu pracy, profilaktyka lekarska",
            "godziny": 0.5
        },
        {
            "nazwa": "Ochrona przeciwpożarowa i pierwsza pomoc",
            "godziny": 1.0
        },
        {
            "nazwa": "INSTRUKTAŻ STANOWISKOWY: Przygotowanie, proces pracy, zagrożenia, wyposażenie",
            "godziny": 2.0
        }
    ]

    # Szybki fallback
    if not _spis_tresci_lista:
        return lista_awaryjna

    model = genai.GenerativeModel(MODEL_NAME)
    tekst_spisu = "\n".join(_spis_tresci_lista)
    
    prompt = f"""
    Jesteś metodykiem BHP. Twoim zadaniem jest pogrupowanie tematów szkolenia w BLOKI PRAWNE zgodne z Ramowym Programem Szkolenia Wstępnego.

    WYMAGANA STRUKTURA I CZAS (Nie zmieniaj godzin, są one narzucone prawnie):
    1. Blok Prawny (Istota BHP, Prawo Pracy, Odpowiedzialność) -> 0.6 h
    2. Blok Organizacyjny (Poruszanie się, Zagrożenia ogólne) -> 0.5 h
    3. Blok Techniczny (Urządzenia, Transport) -> 0.4 h
    4. Blok Higieniczny (Odzież, Porządek, Lekarz) -> 0.5 h
    5. Blok Ratunkowy (PPOŻ, Pierwsza Pomoc) -> 1.0 h
    6. INSTRUKTAŻ STANOWISKOWY (Wszystkie tematy specyficzne dla stanowiska) -> 2.0 h

    Zadanie:
    Dopasuj wykryte w tekście tematy do tych 6 bloków.
    Zwróć wynik WYŁĄCZNIE jako listę JSON w formacie:
    [
        {{"nazwa": "1. [Tytuł bloku]", "godziny": 0.6}},
        {{"nazwa": "2. [Tytuł bloku]", "godziny": 0.5}},
        ...
    ]
    
    SPIS TREŚCI DO PRZETWORZENIA:
    {tekst_spisu}
    """
    
    max_proby = 3
    for proba in range(max_proby):
        try:
            response = model.generate_content(prompt)
            text_resp = response.text.strip()
            
            if text_resp.startswith("```json"): text_resp = text_resp[7:-3]
            elif text_resp.startswith("```"): text_resp = text_resp[3:-3]
            
            dane = json.loads(text_resp)
            
            if not dane or not isinstance(dane, list):
                raise ValueError("Pusty lub niepoprawny JSON")
                
            return dane

        except Exception as e:
            wait_time = (proba + 1) * 2
            time.sleep(wait_time)
            continue

    return lista_awaryjna
