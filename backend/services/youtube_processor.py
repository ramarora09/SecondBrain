from youtube_transcript_api import YouTubeTranscriptApi

def get_video_id(url):
    return url.split("v=")[-1].split("&")[0]

def extract_transcript(url):
    
    try:
        video_id = get_video_id(url)
        
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        text = " ".join([t["text"] for t in transcript])
        
        return text
    
    except Exception as e:
        print("YT ERROR:", str(e))
        return "No transcript available"