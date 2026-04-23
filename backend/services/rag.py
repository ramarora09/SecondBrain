from services.embedding import get_model
import numpy as np
from services.vector_store import index, stored_chunks, stored_sources
from services.llm import generate_answer
from services.memory import add_to_memory, get_memory
from services.analytics import update_question


def detect_topic(question):
    question = question.lower()

    if "dp" in question or "dynamic programming" in question:
        return "DSA"
    elif "os" in question or "operating system" in question:
        return "OS"
    elif "dbms" in question:
        return "DBMS"
    else:
        return "General"


def query_rag(question, source="all"):
    try:
        if len(stored_chunks) == 0:
            return {"error": "⚠️ Please upload PDF or YouTube first"}

        model = get_model()

        # 🔥 Better Retrieval
        q_embedding = model.encode([question])
        distances, indices = index.search(np.array(q_embedding), k=10)

        scored_results = []

        for idx, dist in zip(indices[0], distances[0]):
            if idx < len(stored_chunks):
                if source == "all" or stored_sources[idx] == source:
                    scored_results.append((stored_chunks[idx], dist))

        # 🔥 Sort by similarity (LOW DIST = BEST)
        scored_results = sorted(scored_results, key=lambda x: x[1])

        # 🔥 Top context
        results = [r[0] for r in scored_results[:5]]

        if not results:
            return {"error": "No relevant data found"}

        context = "\n".join(results)

        print("🔥 FINAL CONTEXT:", context[:300])

        # 🔥 SMART MEMORY (limit + clean)
        memory = get_memory()
        memory_text = "\n".join(
            [f"Q: {m['question']} A: {m['answer']}" for m in memory[-3:]]
        )

        full_context = f"""
        Previous conversation:
        {memory_text}

        Knowledge context:
        {context}
        """

        # 🔥 GENERATE ANSWER
        answer = generate_answer(full_context, question)

        # 🔥 STORE MEMORY
        topic = detect_topic(question)
        add_to_memory(question, answer, topic)

        # 🔥 ANALYTICS UPDATE
        update_question(topic)

        return {
            "question": question,
            "answer": answer,
            "topic": topic
        }

    except Exception as e:
        return {"error": str(e)}
