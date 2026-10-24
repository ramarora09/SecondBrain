from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("❌ GROQ API KEY NOT FOUND")

client = Groq(api_key=api_key)

def generate_answer(context, question):
    
    print("👉 CONTEXT:", context[:200])   # DEBUG
    print("👉 QUESTION:", question)

    prompt = f"""
    Answer the question based on the context below:

    Context:
    {context}

    Question:
    {question}

    Answer clearly:
    """

    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    )

    print("👉 LLM RESPONSE:", response)

    return response.choices[0].message.content
