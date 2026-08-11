import streamlit as st
import pandas as pd
import datetime
import re
import zipfile
from io import BytesIO
from docxtpl import DocxTemplate 
from docx import Document        
import google.generativeai as genai

# --- IMPORTY Z MODUŁÓW ---
from data_manager import wczytaj_liste_zawodow_lokalnie, pobierz_opis_zawodu_lokalnie
from logic_ai import generuj_kompletne_szkolenie, generuj_cel_szkolenia, generuj_test_bhp, przypisz_godziny_do_tematow, MODEL_NAME, przeprowadz_audyt_tresci, wczytaj_podstawe_prawna
from logic_docs import generuj_dokument_z_tabela, generuj_docx_prosty, generuj_docx_z_markdown

# ----- Minimalne wymiary godzin wg rozporządzenia (Dz. U. z 2024 r. poz. 1327)
MIN_OGOLNY = 3.0        # instruktaż ogólny - min. 3 godziny lekcyjne
MIN_STANOWISKOWY = 2.0  # instruktaż stanowiskowy dla stanowisk administracyjno-biurowych


def rozdziel_godziny(tematyka):
    """Rozdziela sumę godzin na instruktaż ogólny i stanowiskowy.

    Wiersz stanowiskowy rozpoznawany jest po nazwie zawierającej 'stanowiskow'.
    Jeśli żaden wiersz nie pasuje, ostatni wiersz jest traktowany jako
    stanowiskowy (tam umieszcza go zarówno model, jak i lista awaryjna).
    Zwraca krotkę (suma_ogolny, suma_stanowiskowy).
    """
    suma_ogolny = 0.0
    suma_stanowiskowy = 0.0
    wykryto_stanowiskowy = False

    for t in tematyka:
        try:
            g = float(t.get('godziny', 0))
        except (ValueError, TypeError):
            g = 0.0
        if 'stanowiskow' in str(t.get('nazwa', '')).lower():
            suma_stanowiskowy += g
            wykryto_stanowiskowy = True
        else:
            suma_ogolny += g

    if not wykryto_stanowiskowy and tematyka:
        try:
            g_last = float(tematyka[-1].get('godziny', 0))
        except (ValueError, TypeError):
            g_last = 0.0
        suma_stanowiskowy = g_last
        suma_ogolny -= g_last

    return suma_ogolny, suma_stanowiskowy


# ----- Konfiguracja Aplikacji
st.set_page_config(page_title="Inteligentny Generator Szkoleń BHP", page_icon="🎓", layout="wide")

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    pass

# ----- Inicjalizacja "pamięci" aplikacji (session_state)
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
if 'dane_do_audytu' not in st.session_state:
    st.session_state.dane_do_audytu = ""
if 'tryb_grounding' not in st.session_state:
    st.session_state.tryb_grounding = False

# ----- Główny interfejs aplikacji
st.title("🎓 Inteligentny Generator Szkoleń BHP")

# =========================================================
# ETAP 1: KONFIGURACJA
# =========================================================
if st.session_state.etap == 1:
    st.header("Krok 1: Konfiguracja Szkolenia Wstępnego")
    st.info("Wprowadź dane, aby AI mogło stworzyć spersonalizowany program instruktażu stanowiskowego.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        lista_zawodow = wczytaj_liste_zawodow_lokalnie()
        wybrany_zawod_nazwa = st.selectbox("Stanowisko pracy:", options=list(lista_zawodow.keys()), index=None, placeholder="Wybierz zawód...")
        nazwa_firmy = st.text_input("Nazwa firmy:", value="Przykładowa Firma S.A.")

    with col2:
        # 1. Środowiska biurowe - dozwolone jako GŁÓWNE (uzasadniają wymiar 2h
        #    instruktażu stanowiskowego dla stanowisk administracyjno-biurowych)
        SRODOWISKA_BIUROWE = [
            "Biuro (administracja)", "Praca zdalna/hybrydowa",
            "Archiwum", "Recepcja"
        ]

        # 2. Pełna lista środowisk - dostępna jako DODATKOWE (okazjonalna obecność)
        LISTA_SRODOWISK = SRODOWISKA_BIUROWE + [
            "Magazyn", "Hala produkcyjna", "Warsztat", "Laboratorium",
            "Teren otwarty/Budowa", "Serwerownia", "Teren zewnętrzny",
            "Wyjazdy służbowe (samochód)", "Sklep/Handel"
        ]

        # 3. Środowiska potencjalnie robotnicze - realne narażenie na czynniki
        #    szkodliwe/niebezpieczne może wymagać instruktażu 8h (§ 11 ust. 1)
        SRODOWISKA_RYZYKA = {
            "Magazyn", "Hala produkcyjna", "Warsztat", "Laboratorium",
            "Teren otwarty/Budowa", "Serwerownia", "Teren zewnętrzny"
        }

        # 4. Wybór głównego środowiska - wyłącznie biurowe
        srodowisko_glowne = st.selectbox(
            "Główne środowisko pracy (90% czasu):",
            options=SRODOWISKA_BIUROWE,
            index=None,
            placeholder="Wybierz główne miejsce..."
        )

        # 5. Logika dla dodatkowych środowisk
        srodowiska_dodatkowe = []

        if srodowisko_glowne:
            opcje_dla_dodatkowych = [env for env in LISTA_SRODOWISK if env != srodowisko_glowne]
            srodowiska_dodatkowe = st.multiselect(
                "Dodatkowe środowisko pracy (opcjonalnie):",
                options=opcje_dla_dodatkowych,
                placeholder="Wybierz dodatkowe miejsca..."
            )

            # 6. Ostrzeżenie o możliwym wymogu 8h instruktażu stanowiskowego
            wybrane_ryzyka = [s for s in srodowiska_dodatkowe if s in SRODOWISKA_RYZYKA]
            if wybrane_ryzyka:
                st.warning(
                    "⚠️ Wybrano środowiska: "
                    f"{', '.join(wybrane_ryzyka)}. "
                    "Jeżeli pracownik jest realnie narażony na czynniki szkodliwe "
                    "lub niebezpieczne na tym terenie (a nie jedynie okazjonalnie "
                    "przez niego przechodzi), stanowisko może wymagać instruktażu "
                    "stanowiskowego w wymiarze min. 8 godzin lekcyjnych zgodnie "
                    "z § 11 ust. 1 rozporządzenia. Zweryfikuj wymiar przed "
                    "generowaniem dokumentów."
                )
        else:
            st.multiselect(
                "Dodatkowe środowisko pracy:",
                options=[],
                disabled=True,
                placeholder="Najpierw wybierz środowisko główne ⬆️"
            )
        
    # NOWE POLE: OBOWIĄZKI
    obowiazki = st.text_area(
        "Główne obowiązki na stanowisku (Kluczowe dla Instruktażu Stanowiskowego, opcjonalne):",
        placeholder="Np. obsługa komputera, kontakt z klientem, archiwizacja dokumentów, obsługa niszczarki...",
        height=100
    )

    dodatkowe_zagrozenia = st.text_area(
        "Specyficzne zagrożenia (opcjonalnie):", 
        help="Jeśli pole zostanie puste, AI samo zidentyfikuje zagrożenia na podstawie obowiązków.",
        placeholder="Np. stres, praca przy monitorze >4h, dźwiganie pudeł z papierem..."
    )

    if st.button("🚀 Generuj kompletne szkolenie"):
        if not wybrany_zawod_nazwa:
            st.warning("Proszę wybrać zawód z listy.")
        elif not srodowisko_glowne:
            st.warning("Proszę wybrać główne środowisko pracy.")
        else:
            with st.spinner(f"Tworzenie materiałów dla: {wybrany_zawod_nazwa}..."):
                kod_zawodu = lista_zawodow[wybrany_zawod_nazwa]
                opis_zawodu = pobierz_opis_zawodu_lokalnie(kod_zawodu)
                
                # Łączenie środowisk
                srodowisko_full = srodowisko_glowne
                if srodowiska_dodatkowe:
                    lista_dodatkowych = ", ".join(srodowiska_dodatkowe)
                    srodowisko_full += f" oraz okresowo: {lista_dodatkowych}"
                
                if "Błąd:" in opis_zawodu:
                    st.error(opis_zawodu)
                else:
                    # Grounding zawsze włączony; loader sam wraca do trybu bez podstawy,
                    # gdy plik podstawa_prawna.txt jest pusty lub go brak.
                    st.session_state.tryb_grounding = bool(wczytaj_podstawe_prawna())

                    # Generowanie treści przez AI
                    finalna_tresc = generuj_kompletne_szkolenie(
                        nazwa_firmy, 
                        wybrany_zawod_nazwa, 
                        opis_zawodu, 
                        dodatkowe_zagrozenia,
                        obowiazki,
                        srodowisko_full,
                        uzyj_grounding=True
                    )
                
                # Zmieniamy warunek: sprawdzamy czy tekst to DOKŁADNIE komunikat błędu
                # lub czy zaczyna się od frazy błędu z logic_ai.py
                if not finalna_tresc.startswith("Błąd generowania"):
                    # Zapisujemy główne dane
                    st.session_state.finalna_tresc = finalna_tresc
                    st.session_state.zapisana_firma = nazwa_firmy
                    st.session_state.wybrany_zawod = wybrany_zawod_nazwa
                    st.session_state.dane_do_audytu = f"{obowiazki} {dodatkowe_zagrozenia}"
                    
                    # 2. Generowanie Celu Szkolenia
                    st.session_state.cel_szkolenia_text = generuj_cel_szkolenia(f"Szkolenie BHP: {wybrany_zawod_nazwa}")
                    
                    # 3. Wyciąganie spisu treści
                    st.session_state.spis_tresci_do_tematyki = re.findall(r"^(?:\d+)\.\s.*", finalna_tresc, re.MULTILINE)

                    # 4. Generowanie Tematyki z godzinami
                    st.session_state.tematyka_z_godzinami = przypisz_godziny_do_tematow(st.session_state.spis_tresci_do_tematyki)

                    # Reset stanu edytora godzin (świeża tabela dla nowego szkolenia)
                    st.session_state.pop('tematyka_df', None)
                    st.session_state.pop('editor_tematyki', None)

                    # Przejście dalej
                    st.session_state.etap = 2
                    st.rerun()
                else:
                    # Tutaj trafi tylko prawdziwy błąd techniczny
                    st.error(finalna_tresc)

# =========================================================
# ETAP 2: EDYCJA I WERYFIKACJA
# =========================================================
elif st.session_state.etap == 2:
    st.header("✅ Krok 2: Weryfikacja i Edycja Treści")
    st.success("Szkolenie wygenerowane pomyślnie!")
    if st.session_state.tryb_grounding:
        st.caption("🔗 Tryb generowania: **z podstawą prawną** (grounding na tekście przepisów).")
    else:
        st.caption("🧠 Tryb generowania: **wiedza własna modelu** (bez podstawy prawnej).")

# === AUDYT JAKOŚCI (WIDOCZNY TYLKO W TRYBIE ADMIN) ===
    # Aby zobaczyć audyt, musisz dodać do adresu strony w przeglądarce: ?tryb=admin
    # Np. localhost:8501/?tryb=admin
    
    query_params = st.query_params
    # Sprawdzamy czy w linku jest parametr "tryb" i czy ma wartość "admin"
    czy_tryb_admin = query_params.get("tryb") == "admin"

    if czy_tryb_admin:
        st.info("🔓 Tryb Administratora: Audyt Jakości jest widoczny")
        with st.expander("🔍 Raport Automatycznej Kontroli Jakości (Audyt Prawny)", expanded=True):
            st.markdown("System przeanalizował wygenerowany tekst pod kątem wymogów formalnych:")
            
            dane_input = st.session_state.get('dane_do_audytu', '')
            
            # Tu wywołujemy funkcję z logic_ai.py (musisz mieć ją zaimportowaną)
            wyniki = przeprowadz_audyt_tresci(st.session_state.finalna_tresc, dane_input)
            
            for kategoria, status in wyniki.items():
                c1, c2 = st.columns([0.7, 0.3])
                c1.write(f"**{kategoria}**")
                
                if status == "SKIP":
                    c2.caption("⚪ Brak danych (Pominięto)")
                elif status is True:
                    c2.success("✅ OK")
                else:
                    c2.error("❌ BRAK")

    st.markdown("---")

    # 1. EDYTOR HARMONOGRAMU
    st.subheader("🛠️ Harmonogram Szkolenia (Edycja Godzin)")
    st.info("Program ramowy jest stały. Możesz dostosować jedynie liczbę godzin dla poszczególnych bloków.")

    if st.session_state.tematyka_z_godzinami:
        # Stabilna tabela bazowa trzymana w session_state - NIE przebudowujemy jej
        # z wyniku edytora co przebieg (to powodowało lag "podwójnej edycji").
        # Odświeżamy tylko, gdy zmieni się liczba wierszy (nowe szkolenie).
        if ('tematyka_df' not in st.session_state
                or len(st.session_state.tematyka_df) != len(st.session_state.tematyka_z_godzinami)):
            st.session_state.tematyka_df = pd.DataFrame(st.session_state.tematyka_z_godzinami)

        column_config = {
            "nazwa": st.column_config.TextColumn(
                "Temat (Zgodny z Ramowym Programem)", 
                width="large", 
                disabled=True,
                help="Nazwy tematów wynikają z rozporządzenia i nie mogą być zmieniane."
            ),
            "godziny": st.column_config.NumberColumn(
                "Godziny (45min)", 
                min_value=0.1, 
                max_value=8.0,
                step=0.1, 
                format="%.1f h",
                help="Wpisz wartość od 0.1 do 8.0 h (8 h dopuszcza scenariusz robotniczy)"
            )
        }

        edited_df = st.data_editor(
            st.session_state.tematyka_df,
            column_config=column_config, 
            use_container_width=True,
            num_rows="fixed", 
            key="editor_tematyki",
            hide_index=True
        )
        
        st.session_state.tematyka_z_godzinami = edited_df.to_dict('records')
        total_h = edited_df['godziny'].sum()

        suma_ogolny, suma_stanowiskowy = rozdziel_godziny(st.session_state.tematyka_z_godzinami)
        spelnia_minimum = (suma_ogolny >= MIN_OGOLNY - 0.001) and (suma_stanowiskowy >= MIN_STANOWISKOWY - 0.001)

        col_sum, col_warn = st.columns([1, 3])
        col_sum.caption(
            f"📊 Razem: **{total_h:.1f} h** "
            f"(ogólny: {suma_ogolny:.1f} h, stanowiskowy: {suma_stanowiskowy:.1f} h)"
        )

        if not spelnia_minimum:
            braki = []
            if suma_ogolny < MIN_OGOLNY - 0.001:
                braki.append(f"instruktaż ogólny: {suma_ogolny:.1f} h (wymagane min. {MIN_OGOLNY:.0f} h)")
            if suma_stanowiskowy < MIN_STANOWISKOWY - 0.001:
                braki.append(f"instruktaż stanowiskowy: {suma_stanowiskowy:.1f} h (wymagane min. {MIN_STANOWISKOWY:.0f} h)")
            col_warn.error(
                "⛔ Nie spełniono minimum z rozporządzenia — " + "; ".join(braki)
                + ". Zwiększ godziny, aby móc przejść do generowania dokumentów."
            )
        elif total_h > 16.0:
            col_warn.warning("⚠️ Bardzo duża liczba godzin (ponad 2 dni szkolenia). Sprawdź poprawność.")
    else:
        spelnia_minimum = False

    st.markdown("---")

    # 2. PODGLĄD TREŚCI
    st.subheader("📖 Treść Szkolenia")
    
    with st.expander("✏️ Kliknij tutaj, aby ręcznie edytować tekst źródłowy"):
        st.text_area("Edycja treści:", value=st.session_state.finalna_tresc, height=300, key="edycja_tekstu_area")
        if st.session_state.edycja_tekstu_area != st.session_state.finalna_tresc:
            st.session_state.finalna_tresc = st.session_state.edycja_tekstu_area
            st.rerun()

    with st.expander("📄 Podgląd sformatowanej treści szkolenia (Kliknij, aby zwinąć/rozwinąć)", expanded=True):
        st.markdown(st.session_state.finalna_tresc, unsafe_allow_html=True)

    st.markdown("---")


    # 3. PRZYCISKI NAWIGACJI
    col_btn1, col_btn2 = st.columns([1, 1])
    
    with col_btn1:
        docx_file = generuj_docx_z_markdown(st.session_state.finalna_tresc)
        st.download_button(
            label="📥 Pobierz treść jako WORD (.docx)",
            data=docx_file,
            file_name=f"Szkolenie_{st.session_state.wybrany_zawod}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

    with col_btn2:
        if st.button("📄 Zatwierdź i przejdź do dokumentów", type="primary", use_container_width=True, disabled=not spelnia_minimum):
            st.session_state.etap = 3
            st.rerun()
        if not spelnia_minimum:
            st.caption("Przejście zablokowane do czasu spełnienia minimalnych wymiarów godzin.")
            
    if st.button("🔙 Wróć do wyboru zawodu", type="secondary"):
        st.session_state.pop('tematyka_df', None)
        st.session_state.pop('editor_tematyki', None)
        st.session_state.etap = 1
        st.rerun()

# =========================================================
# ETAP 3: GENERATOR DOKUMENTACJI
# =========================================================
elif st.session_state.etap == 3:
    st.header("✅ Krok 3: Generator Dokumentacji")

    # --- SEKCJA DANYCH WSPÓLNYCH ---
    with st.container(border=True):
        st.subheader("🛠️ Konfiguracja danych")

        # 1. UCZESTNICY
        st.markdown("**Lista uczestników** \n*Wpisz tylko: Imię Nazwisko, Data Urodzenia*", unsafe_allow_html=True)
        uczestnicy_input = st.text_area(
            label="Lista uczestników",
            label_visibility="collapsed",
            height=100,
            key="uczestnicy_lista_input",
            placeholder="Jan Kowalski, 12.05.1985\nAnna Nowak, 20.01.1990"
        )

        uczestnicy_dane_lista = []
        bledne_linie_detale = []

        if uczestnicy_input:
            lines = uczestnicy_input.strip().splitlines()
            for i, linia in enumerate(lines):
                linia_clean = linia.strip()
                if not linia_clean:
                    continue

                czesci = [c.strip() for c in linia_clean.split(',')]

                if len(czesci) != 2:
                    bledne_linie_detale.append(f"❌ Linia {i+1}: Nieprawidłowy format. Wymagane: 'Imię Nazwisko, Data'.")
                    continue

                data_raw = czesci[1]
                if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", data_raw):
                    bledne_linie_detale.append(f"❌ Linia {i+1}: Zły format daty '{data_raw}'. Wymagane DD.MM.RRRR.")
                    continue

                uczestnicy_dane_lista.append({
                    'index': len(uczestnicy_dane_lista) + 1,
                    'imie_nazwisko': czesci[0],
                    'miejsce_pracy': st.session_state.zapisana_firma,
                    'funkcja': st.session_state.wybrany_zawod,
                    'data_urodzenia': czesci[1],
                    'ocena': '',
                    'uwagi': ''
                })

        if bledne_linie_detale:
            st.error(f"Znaleziono błędy w {len(bledne_linie_detale)} wierszach:")
            for blad in bledne_linie_detale:
                st.text(blad)

        if uczestnicy_dane_lista:
            with st.expander(f"✅ Poprawnie wczytano {len(uczestnicy_dane_lista)} uczestników", expanded=False):
                st.dataframe(pd.DataFrame(uczestnicy_dane_lista)[['imie_nazwisko', 'miejsce_pracy', 'funkcja', 'data_urodzenia']], use_container_width=True, hide_index=True)

        st.markdown("---")

        # 2. BAZA WYKŁADOWCÓW (zasila instruktorów w Karcie szkolenia wstępnego)
        st.markdown("### ⚙️ Baza Wykładowców")
        st.caption("Format: Imię Nazwisko, Miejsce pracy, Funkcja — jedna osoba w wierszu.")
        if 'baza_wykladowcow_text' not in st.session_state:
            st.session_state.baza_wykladowcow_text = "Jan Nowak, Firma BHP, Specjalista BHP\nAnna Kowalska, Firma Med, Ratownik"
        baza_wykladowcow = st.text_area("Baza Wykładowców", label_visibility="collapsed", value=st.session_state.baza_wykladowcow_text, height=120, key="baza_wykladowcow_key")
        opcje_wykladowcow = [x.strip() for x in baza_wykladowcow.splitlines() if x.strip()]

        st.markdown("---")

        # 3. DATY SZKOLENIA
        st.markdown("### 🗓️ Daty szkolenia")
        col_d1, col_d2 = st.columns(2)
        dzisiaj = datetime.date.today()
        with col_d1:
            data_start = st.date_input("Data rozpoczęcia (instruktaż ogólny):", key="doc_data_start", value=dzisiaj)
        with col_d2:
            data_koniec = st.date_input("Data instruktażu stanowiskowego:", key="doc_data_koniec", value=dzisiaj, min_value=data_start)

    st.write("")

    tab1, tab2 = st.tabs(["📄 Karta i tematyka", "📝 Wykaz i pytania"])

    # --- TAB 1: KARTA + TEMATYKA ---
    with tab1:
        st.info("Karta szkolenia wstępnego potwierdza odbycie instruktażu ogólnego i stanowiskowego.")
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("📄 Karta szkolenia wstępnego")
            with st.container(border=True):
                instruktor_ogolny = st.selectbox("Instruktor (instruktaż ogólny):", options=opcje_wykladowcow, index=0 if opcje_wykladowcow else None, key="inst_ogolny_sel")
                instruktor_stanowiskowy = st.selectbox("Instruktor (instruktaż stanowiskowy):", options=opcje_wykladowcow, index=0 if opcje_wykladowcow else None, key="inst_stan_sel")
                st.markdown("---")
                wybrany_uczestnik = st.selectbox("Wybierz uczestnika:", options=[u['imie_nazwisko'] for u in uczestnicy_dane_lista], index=None, key="sel_uczestnik_karta")

                if st.button("Generuj kartę szkolenia (pojedynczą)", use_container_width=True, key="btn_gen_karta_single"):
                    if wybrany_uczestnik and instruktor_ogolny and instruktor_stanowiskowy:
                        osoba = next((u for u in uczestnicy_dane_lista if u['imie_nazwisko'] == wybrany_uczestnik), None)
                        inst_ogolny_nazwisko = instruktor_ogolny.split(',')[0].strip()
                        inst_stan_nazwisko = instruktor_stanowiskowy.split(',')[0].strip()

                        context = {
                            'nazwa_firmy': st.session_state.zapisana_firma,
                            'imie_nazwisko': osoba['imie_nazwisko'],
                            'komorka_organizacyjna': osoba['miejsce_pracy'],
                            'stanowisko': osoba['funkcja'],
                            'dzien_rozpoczecia': data_start.strftime("%d.%m.%Y"),
                            'instruktor_ogolny': inst_ogolny_nazwisko,
                            'data_stanowiskowego': data_koniec.strftime("%d.%m.%Y"),
                            'instruktor_stanowiskowy': inst_stan_nazwisko
                        }
                        plik = generuj_docx_prosty("Wzor-Karta-szkolenia-wstepnego-BHP.docx", context, "Karta.docx")
                        if plik:
                            st.download_button("📥 Pobierz kartę", plik, f"Karta_Szkolenia_{osoba['imie_nazwisko']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key=f"dl_karta_{osoba['index']}")
                    else:
                        st.warning("Uzupełnij instruktorów i wybierz uczestnika.")

        with col_b:
            st.subheader("📋 Tematyka szkolenia")
            with st.container(border=True):
                st.write("Tematyka z przypisanymi godzinami (z Kroku 2).")
                if st.button("Generuj tematykę", use_container_width=True, key="btn_gen_tematyka"):
                    tematyka = st.session_state.tematyka_z_godzinami
                    if tematyka:
                        total_h = sum(float(t.get('godziny', 0)) for t in tematyka)
                        tematyka_display = [{"nazwa": t.get('nazwa', ''), "godziny": t.get('godziny', 0), "praktyka": "0"} for t in tematyka]
                        tematyka_display.append({"nazwa": "RAZEM:", "godziny": f"{total_h:.1f}", "praktyka": "0"})

                        plik, blad = generuj_dokument_z_tabela("tematyka_szablon_uproszczony.docx", {}, tematyka_display, ['nazwa', 'godziny', 'praktyka'])
                        if plik:
                            st.download_button("📥 Pobierz tematykę", plik, "Tematyka.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="dl_tematyka")
                        else:
                            st.error(blad)
                    else:
                        st.error("Brak danych tematyki.")

    # --- TAB 2: WYKAZ + PYTANIA ---
    with tab2:
        st.info("Wykaz uczestników oraz pytania kontrolne do sprawdzianu wiedzy.")
        col_c, col_e = st.columns(2)

        with col_c:
            st.subheader("👥 Wykaz uczestników")
            with st.container(border=True):
                if st.button("Generuj wykaz", use_container_width=True, key="btn_gen_wykaz_final"):
                    if uczestnicy_dane_lista:
                        plik, blad = generuj_dokument_z_tabela("wykaz_uczestnikow_szablon_uproszczony.docx", {}, uczestnicy_dane_lista, ['imie_nazwisko', 'miejsce_pracy', 'funkcja', 'data_urodzenia'])
                        if plik:
                            st.download_button("📥 Pobierz wykaz", plik, "Wykaz_Uczestnikow.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="dl_wykaz_final")
                        else:
                            st.error(blad)
                    else:
                        st.warning("Brak uczestników.")

        with col_e:
            st.subheader("❓ Pytania kontrolne")
            with st.container(border=True):
                if st.button("Generuj pytania kontrolne", use_container_width=True, key="btn_gen_pytania_final"):
                    if st.session_state.finalna_tresc:
                        with st.spinner("AI opracowuje pytania sprawdzające..."):
                            tresc_pytan, _ = generuj_test_bhp(st.session_state.finalna_tresc)
                            st.session_state.cached_test_content = tresc_pytan
                    else:
                        st.warning("Najpierw wygeneruj program szkolenia w Kroku 1.")

                if st.session_state.cached_test_content:
                    st.success("Pytania gotowe.")
                    ctx_pytania = {
                        'nazwa_szkolenia': f"Szkolenie wstępne i stanowiskowe dla {st.session_state.wybrany_zawod}",
                        'tresc_testu': st.session_state.cached_test_content
                    }
                    plik_pytania = generuj_docx_prosty("test_szablon.docx", ctx_pytania, "Pytania.docx")
                    if plik_pytania:
                        st.download_button("📥 Pobierz arkusz pytań", plik_pytania, "Pytania_Kontrolne.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="dl_pytania_final")

    # --- PACZKA ZIP ---
    st.markdown("---")
    st.subheader("📦 Pobierz wszystko")
    st.info("Wygeneruj komplet dokumentacji jednym kliknięciem.")

    if st.button("Generuj paczkę ZIP ze wszystkimi dokumentami", type="primary", use_container_width=True, key="btn_zip_final"):
        if not uczestnicy_dane_lista:
            st.error("Brakuje listy uczestników!")
        elif not st.session_state.tematyka_z_godzinami:
            st.error("Brakuje tematyki szkolenia!")
        else:
            zip_buffer = BytesIO()
            try:
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    # 1. KARTY SZKOLENIA (dla każdego uczestnika)
                    inst_ogolny_zip = st.session_state.get("inst_ogolny_sel", "Instruktor")
                    inst_stan_zip = st.session_state.get("inst_stan_sel", "Instruktor")
                    i_ogolny = str(inst_ogolny_zip).split(',')[0].strip()
                    i_stan = str(inst_stan_zip).split(',')[0].strip()
                    d_stan = data_koniec.strftime("%d.%m.%Y")

                    for u in uczestnicy_dane_lista:
                        context_karta = {'nazwa_firmy': st.session_state.zapisana_firma, 'imie_nazwisko': u['imie_nazwisko'], 'komorka_organizacyjna': u['miejsce_pracy'], 'stanowisko': u['funkcja'], 'dzien_rozpoczecia': data_start.strftime("%d.%m.%Y"), 'instruktor_ogolny': i_ogolny, 'data_stanowiskowego': d_stan, 'instruktor_stanowiskowy': i_stan}
                        plik = generuj_docx_prosty("Wzor-Karta-szkolenia-wstepnego-BHP.docx", context_karta, "temp.docx")
                        if plik:
                            zf.writestr(f"Karty_Szkolenia/Karta_{u['imie_nazwisko']}.docx", plik.getvalue())

                    # 2. TEMATYKA
                    tematyka = st.session_state.tematyka_z_godzinami
                    total_h = sum(float(t.get('godziny', 0)) for t in tematyka)
                    tematyka_display = [{"nazwa": t.get('nazwa', ''), "godziny": t.get('godziny', 0), "praktyka": "0"} for t in tematyka]
                    tematyka_display.append({"nazwa": "RAZEM:", "godziny": f"{total_h:.1f}", "praktyka": "0"})
                    plik, _ = generuj_dokument_z_tabela("tematyka_szablon_uproszczony.docx", {}, tematyka_display, ['nazwa', 'godziny', 'praktyka'])
                    if plik:
                        zf.writestr("Tematyka_Szkolenia.docx", plik.getvalue())

                    # 3. WYKAZ UCZESTNIKÓW
                    plik, _ = generuj_dokument_z_tabela("wykaz_uczestnikow_szablon_uproszczony.docx", {}, uczestnicy_dane_lista, ['imie_nazwisko', 'miejsce_pracy', 'funkcja', 'data_urodzenia'])
                    if plik:
                        zf.writestr("Wykaz_Uczestnikow.docx", plik.getvalue())

                    # 4. PYTANIA KONTROLNE
                    if not st.session_state.cached_test_content and st.session_state.finalna_tresc:
                        try:
                            tresc_pytan, _ = generuj_test_bhp(st.session_state.finalna_tresc)
                            st.session_state.cached_test_content = tresc_pytan
                        except Exception:
                            pass
                    if st.session_state.cached_test_content:
                        ctx_pytania = {'nazwa_szkolenia': f"Szkolenie wstępne i stanowiskowe dla {st.session_state.wybrany_zawod}", 'tresc_testu': st.session_state.cached_test_content}
                        plik = generuj_docx_prosty("test_szablon.docx", ctx_pytania, "temp.docx")
                        if plik:
                            zf.writestr("Pytania_Kontrolne.docx", plik.getvalue())

                    # 5. PROGRAM SZKOLENIA (treść jako DOCX)
                    docx_tresc = generuj_docx_z_markdown(st.session_state.finalna_tresc)
                    zf.writestr(f"Program_Szkolenia_{st.session_state.wybrany_zawod}.docx", docx_tresc.getvalue())

                zip_buffer.seek(0)
                st.success("Paczka dokumentów gotowa!")
                st.download_button(label="📦 POBIERZ PLIK ZIP", data=zip_buffer, file_name=f"Komplet_BHP_{st.session_state.wybrany_zawod}.zip", mime="application/zip", use_container_width=True, key="dl_zip_final")

            except Exception as e:
                st.error(f"Wystąpił błąd podczas tworzenia archiwum ZIP: {e}")

    st.markdown("---")
    if st.button("🔄 Zacznij od nowa (Nowe Szkolenie)", type="secondary"):
        st.session_state.pop('tematyka_df', None)
        st.session_state.pop('editor_tematyki', None)
        st.session_state.etap = 1
        st.rerun()