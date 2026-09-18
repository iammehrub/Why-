import os,json,subprocess,requests
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; WORK=ROOT/"work"; WORK.mkdir(exist_ok=True)
OPENAI=os.environ["OPENAI_API_KEY"]; PEXELS=os.environ.get("PEXELS_API_KEY","")
TOPICS=["Why do we procrastinate?","Why do embarrassing memories stick?","Why does your brain crave novelty?","Why do we yawn when others yawn?","Why does music give you chills?","Why do we form habits?","Why does time feel faster as we get older?","Why do we get nervous before speaking?","Why does your brain notice your name?","Why do humans copy each other's behavior?","Why do we forget why we walked into a room?","Why does sleep affect memory?","Why do we get goosebumps?","Why does exercise affect mood?","Why are first impressions so powerful?","Why does multitasking feel productive?","Why do we remember stories better than lists?","Why do we seek patterns in random things?","Why does stress make concentration harder?"]
def sources(q):
 r=requests.get("https://en.wikipedia.org/w/api.php",params={"action":"query","list":"search","srsearch":q,"format":"json","srlimit":5},timeout=30)
 return ["https://en.wikipedia.org/wiki/"+x["title"].replace(" ","_") for x in r.json().get("query",{}).get("search",[])] if r.ok else []
def gen(prompt):
 r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":"Bearer "+OPENAI,"Content-Type":"application/json"},json={"model":"gpt-5.6-luna","input":prompt,"max_output_tokens":2200},timeout=180); r.raise_for_status(); return r.json().get("output_text","").strip()
def main():
 f=WORK/"used_topics.json"; used=set()
 if f.exists():
  try: used=set(json.loads(f.read_text()))
  except: pass
 topic=next((x for x in TOPICS if x not in used),TOPICS[0]); used.add(topic); f.write_text(json.dumps(list(used)[-100:]))
 src=sources(topic)
 prompt="Create an ORIGINAL 45-60 second YouTube Short for WHY? about: %s\nAudience: global English-speaking viewers interested in human behavior, psychology and everyday science.\nWrite 115-145 words. Hook immediately, explain the mechanism simply and accurately, and finish with a memorable takeaway. Use only claims supported by the supplied sources. Do not invent statistics or studies. No fake personal stories or stage directions. Return valid JSON only with keys title, script, description, hashtags.\nSources:\n%s"%(topic,"\n".join(src))
 raw=gen(prompt).strip(); obj=json.loads(raw)
 if not 95<=len(obj["script"].split())<=165: raise RuntimeError("Script length outside Shorts target")
 obj["topic"]=topic; obj["sources"]=src; (WORK/"episode.json").write_text(json.dumps(obj,indent=2)); (WORK/"script.txt").write_text(obj["script"])
 return obj
def tts(text):
 out=WORK/"voice.wav"; subprocess.run(["espeak-ng","-v","en-us","-s","170","-w",str(out),text],check=True); return out
def get_video(topic):
 if not PEXELS:return None
 r=requests.get("https://api.pexels.com/videos/search",headers={"Authorization":PEXELS},params={"query":topic,"per_page":10,"orientation":"portrait","size":"medium"},timeout=30)
 if not r.ok:return None
 for v in r.json().get("videos",[]):
  fs=[x for x in v.get("video_files",[]) if x.get("width",0)>=600 and x.get("height",0)>=900]
  if fs:
   u=max(fs,key=lambda x:x.get("width",0)*x.get("height",0))["link"]; out=WORK/"source.mp4"
   with requests.get(u,stream=True,timeout=60) as rr:
    rr.raise_for_status()
    with open(out,"wb") as w:
     for b in rr.iter_content(1024*1024):
      if b:w.write(b)
   return out
 return None
def render(wav,bg):
 dur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(wav)]))
 if bg is None:
  bg=WORK/"blank.mp4"; subprocess.run(["ffmpeg","-y","-f","lavfi","-i","color=c=101820:s=1080x1920:r=30","-t",str(dur),str(bg)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 out=WORK/"why_short.mp4"
 subprocess.run(["ffmpeg","-y","-stream_loop","-1","-i",str(bg),"-i",str(wav),"-t",str(dur),"-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","ultrafast","-crf","27","-c:a","aac","-b:a","128k","-shortest",str(out)],check=True)
 return out
def upload(path,obj):
 from google.oauth2.credentials import Credentials
 from google.auth.transport.requests import Request
 from googleapiclient.discovery import build
 from googleapiclient.http import MediaFileUpload
 c=Credentials(None,refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["YOUTUBE_CLIENT_ID"],client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/youtube.upload"]); c.refresh(Request())
 yt=build("youtube","v3",credentials=c)
 body={"snippet":{"title":obj["title"][:100],"description":obj.get("description","")+"\n\n"+" ".join(obj.get("hashtags",[])),"categoryId":"27","tags":["psychology","science","human behavior","brain","why"]},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
 r=yt.videos().insert(part="snippet,status",body=body,media_body=MediaFileUpload(str(path),chunksize=-1,resumable=True)).execute(); print("Published:",r["id"])
if __name__=="__main__":
 obj=main(); wav=tts(obj["script"]); bg=get_video(obj["topic"]); upload(render(wav,bg),obj)
