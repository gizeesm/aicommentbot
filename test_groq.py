import os
from dotenv import load_dotenv
from groq import Groq

# .env dosyasındaki key'i oku
load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {"role": "user", "content": "Merhaba, sen çalışıyor musun?"}
    ]
)

print(response.choices[0].message.content)


