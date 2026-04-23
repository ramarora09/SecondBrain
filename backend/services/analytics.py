analytics_data = {
    "questions": 0,
    "topics": {},
    "documents": 0
}

def update_question(topic):
    analytics_data["questions"] += 1
    
    if topic not in analytics_data["topics"]:
        analytics_data["topics"][topic] = 1
    else:
        analytics_data["topics"][topic] += 1

def get_analytics():
    return analytics_data