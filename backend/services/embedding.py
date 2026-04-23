from sentence_transformers import SentenceTransformer

model = None   # 🔥 initially empty

def get_model():
    global model
    
    if model is None:
        print("Loading embedding model...")   # debug
        model = SentenceTransformer('all-MiniLM-L6-v2')
    
    return model


def create_embeddings(text):
    
    model = get_model()
    
    chunk_size = 300
    overlap = 80
    
    chunks = []
    
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i+chunk_size]
        if chunk.strip():
            chunks.append(chunk)

    print("CHUNKS:",len(chunks))
    
    embeddings = model.encode(chunks)
    
    return chunks, embeddings