import requests

API_KEY = "AIzaSyD0Iwkue0HaESjV8Lh1Wd4MyfapKdSpU9o"

modelo = "gemini-2.0-flash"
url = "https://generativelanguage.googleapis.com/v1beta/models/" + modelo + ":generateContent?key=" + API_KEY

resposta = requests.post(url, json={
    "contents": [{"parts": [{"text": "Oi! Responde em portugues: quem e voce?"}]}]
})

print(resposta.json())