import datetime
import re

def rozplanuj_zajecia(tematyka_lista, data_start):
    """
    Rozkłada tematy na kolejne dni robocze (pon-pt), przestrzegając limitu 8h/dzień.
    Zwraca listę tematów z przypisaną datą oraz faktyczną datę zakończenia.
    """
    harmonogram = []
    aktualna_data = data_start
    dzienne_godziny = 0.0 # Używamy float
    MAX_H_DZIEN = 8.0 

    for temat in tematyka_lista:
        # POPRAWKA: Rzutujemy na float, żeby obsłużyć ułamki (np. 0.6h)
        try:
            godziny_tematu = float(temat.get('godziny', 0))
        except (ValueError, TypeError):
            godziny_tematu = 0.0
        
        if godziny_tematu <= 0:
            continue 

        # 1. Sprawdzanie, czy aktualna_data jest weekendem (Sobota=5, Niedziela=6)
        while aktualna_data.weekday() >= 5: 
            aktualna_data += datetime.timedelta(days=1)
            
        # 2. Jeśli dodanie tematu przekroczy limit 8h -> Przeskakujemy na następny dzień
        # (Chyba że jest to pierwszy temat dnia i jest większy niż limit - wtedy musi zostać)
        if (dzienne_godziny + godziny_tematu > MAX_H_DZIEN) and dzienne_godziny > 0:
            aktualna_data += datetime.timedelta(days=1)
            
            # Ponownie sprawdzamy, czy następny dzień nie jest weekendem
            while aktualna_data.weekday() >= 5:
                aktualna_data += datetime.timedelta(days=1)
            
            # Resetujemy licznik godzin dla nowego dnia
            dzienne_godziny = 0.0
        
        # 3. Przypisanie tematu do bieżącej daty
        harmonogram.append({
            'data': aktualna_data.strftime("%d.%m.%Y"), 
            'godziny': f"{godziny_tematu:.1f}", # Formatujemy ładnie np. "0.6"
            'przedmiot': "Szkolenie BHP", 
            'temat': temat.get('nazwa', 'Brak tematu')
        })
        
        # 4. Aktualizacja godzin na dziś
        dzienne_godziny += godziny_tematu

    # Faktyczna data zakończenia to data ostatniego wpisu
    faktyczna_data_koniec = aktualna_data 
    
    if harmonogram:
         ostatni_wpis_data_str = harmonogram[-1]['data']
         faktyczna_data_koniec = datetime.datetime.strptime(ostatni_wpis_data_str, "%d.%m.%Y").date()

    return harmonogram, faktyczna_data_koniec

def weryfikuj_tresc_szkolenia(tekst, uzyte_obowiazki_i_zagrozenia):
    """
    Automatyczny audyt wygenerowanej treści. Sprawdza obecność kluczowych elementów.
    Zwraca raport (lista słowników).
    """
    raport = []
    
    # 1. Sprawdzenie struktury (Części)
    if re.search(r"CZĘŚĆ\s+1|INSTRUKTAŻ\s+OGÓLNY", tekst, re.IGNORECASE):
        raport.append({"test": "Struktura: Instruktaż Ogólny", "status": "OK", "icon": "✅"})
    else:
        raport.append({"test": "Struktura: Instruktaż Ogólny", "status": "BRAK", "icon": "❌"})

    if re.search(r"CZĘŚĆ\s+2|INSTRUKTAŻ\s+STANOWISKOWY", tekst, re.IGNORECASE):
        raport.append({"test": "Struktura: Instruktaż Stanowiskowy", "status": "OK", "icon": "✅"})
    else:
        raport.append({"test": "Struktura: Instruktaż Stanowiskowy", "status": "BRAK", "icon": "❌"})

    # 2. Sprawdzenie czasu trwania (szukamy cyfry 3 i słowa godzina w pobliżu)
    if re.search(r"(3|trzy)\s*(h|godz)", tekst, re.IGNORECASE):
        raport.append({"test": "Wymiar czasu", "status": "OK", "icon": "✅"})
    else:
        raport.append({"test": "Wymiar czasu", "status": "Ostrzeżenie (nie wykryto zapisu)", "icon": "⚠️"})

    # 3. Podstawa prawna (Rozporządzenie)
    if re.search(r"Rozporządzeni.*2004", tekst, re.IGNORECASE):
        raport.append({"test": "Podstawa prawna", "status": "OK", "icon": "✅"})
    else:
        raport.append({"test": "Podstawa prawna", "status": "BRAK ODWOŁANIA", "icon": "❌"})

    # 4. Personalizacja (POPRAWIONA LOGIKA)
    # Sprawdzamy, czy użytkownik w ogóle wpisał jakieś dane.
    # string.strip() usuwa spacje - jeśli po usunięciu spacji tekst jest pusty, to znaczy że nic nie wpisano.
    if uzyte_obowiazki_i_zagrozenia and uzyte_obowiazki_i_zagrozenia.strip():
        slowa_kluczowe = [s for s in uzyte_obowiazki_i_zagrozenia.split() if len(s) > 4]
        
        # Jeśli użytkownik wpisał tylko krótkie słowa (np. "kot"), lista może być pusta
        if not slowa_kluczowe:
             raport.append({"test": "Personalizacja", "status": "Wpisano zbyt krótkie słowa do weryfikacji", "icon": "ℹ️"})
        else:
            znalezione = [s for s in slowa_kluczowe if s.lower() in tekst.lower()]
            
            if len(znalezione) > 0:
                unikalne = list(set(znalezione))
                raport.append({"test": "Personalizacja (użycie Twoich danych)", "status": f"OK (Znaleziono m.in.: {', '.join(unikalne[:3])})", "icon": "✅"})
            else:
                raport.append({"test": "Personalizacja", "status": "Ostrzeżenie: Model mógł nie użyć Twoich dodatkowych uwag", "icon": "⚠️"})
    else:
        # Jeśli pole było puste
        raport.append({"test": "Personalizacja", "status": "Brak danych wejściowych (Pominięto)", "icon": "⚪"})

    return raport