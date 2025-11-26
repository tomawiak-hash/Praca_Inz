import google.generativeai as genai

# WSTAW TUTAJ SWÓJ KLUCZ API Z GOOGLE AI STUDIO
genai.configure(api_key="AIzaSyBYtQ-Y7nfP7h-4fqT4gMDRzed0b-IVVjw")

print("Sprawdzam dostępne modele...")
print("-" * 30)
print("Dostępne modele, które obsługują metodę 'generateContent':")

try:
    for m in genai.list_models():
      if 'generateContent' in m.supported_generation_methods:
        print(m.name)
except Exception as e:
    print(f"\nWystąpił błąd: {e}")
    print("Upewnij się, że Twój klucz API jest poprawny i masz włączone 'Generative Language API' w swoim projekcie Google Cloud.")

print("-" * 30)