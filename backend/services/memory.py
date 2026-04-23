import json
from pathlib import Path


MEMORY_DIR = Path(__file__).resolve().parent.parent / "data"
MEMORY_FILE = MEMORY_DIR / "chat_history.json"

chat_history = []


def _load_memory():
    global chat_history

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    if not MEMORY_FILE.exists():
        chat_history = []
        return

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        chat_history = data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        chat_history = []


def _save_memory():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    with MEMORY_FILE.open("w", encoding="utf-8") as file:
        json.dump(chat_history, file, ensure_ascii=False, indent=2)


def add_to_memory(question, answer, topic="General"):
    chat_history.append({
        "question": question,
        "answer": answer,
        "topic": topic
    })
    _save_memory()


def get_memory(limit=5):
    return chat_history[-limit:]


def get_chat_history():
    messages = []

    for item in chat_history:
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        topic = item.get("topic", "General")

        if question:
            messages.append({
                "role": "user",
                "text": question
            })

        if answer:
            messages.append({
                "role": "assistant",
                "text": answer,
                "topic": topic
            })

    return messages


def clear_memory():
    global chat_history
    chat_history = []
    _save_memory()


_load_memory()
    
