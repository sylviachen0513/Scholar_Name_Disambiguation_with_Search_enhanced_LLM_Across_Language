import json
from sys import flags
import re
from profile_extract_agent import is_same_talent,get_talent_doc
from name_translate_agent import get_paper_doc_from_chinese
import numpy as np
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse, StreamingResponse, Response
import httpx
from pydantic import BaseModel
from pypinyin import pinyin, Style

# app = Flask(__name__)
app = FastAPI(debug=True, docs_url=None, redoc_url=None)


class DocRequest(BaseModel):
    doc_str: str

def compare_function(doc1, doc2):
    if doc2 is None:
        return False
    name2 = doc2.get('name')
    if not name2 or name2 == '未找到':
        return False

    workplace1 = doc1.get('workplace')
    workplace2 = doc2.get('workplace', '')
    email1 = doc1.get('email', [])
    email2 = doc2.get('email', [])
    honor_track1 = doc1.get('honor_track', '[]')

    try:
        honor_track1 = json.loads(honor_track1)
    except:
        honor_track1 = []

    try:
        honor_track2 = json.loads(doc2.get('honor_track', '[]'))
    except:
        honor_track2 = []

    # 1. 比较 name + aminer_id
    aminer_id1 = doc1.get('aminer_id')
    aminer_id2 = doc2.get('aminer_id')
    if aminer_id1 and aminer_id2 and aminer_id1 == aminer_id2:
        return True

    # 2. 比较 name + google_scholar_url
    google_scholar_url1 = doc1.get('google_scholar_url')
    google_scholar_url2 = doc2.get('google_scholar_url')
    if google_scholar_url1 and google_scholar_url2 and google_scholar_url1 == google_scholar_url2:
        return True

    # 3. 比较 name + mainpage
    mainpage1 = doc1.get('mainpage')
    mainpage2 = doc2.get('mainpage')
    if mainpage1 and mainpage2 and mainpage1 == mainpage2:
        return True

    # 4. 比较 email
    if isinstance(email2, str):
        email2 = [email2]
    if isinstance(email1,list) and isinstance(email2,list) and any(e in email2 for e in email1):
        return True

    # 5. 比较 honor 字段
    four_titles = ["中国科学院院士", "中国工程院院士", "国家杰出青年科学基金获得者", "长江学者特聘教授",
                   "长江学者讲座教授"]
    if isinstance(honor_track1, list) and isinstance(honor_track2, list):
        if workplace1 and workplace2 and workplace1 == workplace2:
            for h1 in honor_track1:
                if isinstance(h1, dict):
                    for h2 in honor_track2:
                        if isinstance(h2, dict):
                            if h1.get('award') in four_titles and h2.get('award') in four_titles:
                                if h1.get('award') == h2.get('award') and h1.get('time') == h2.get('time'):
                                    return True

    # 6. 比较 prize_relations
    if workplace1 and workplace2 and workplace1 == workplace2:
        prize_relations1 = doc1.get('prize_relations', [])
        prize_relations2 = doc2.get('prize_relations', [])
        if prize_relations1 is not None and prize_relations2 is not None:
            if set(prize_relations1) & set(prize_relations2):
                return True

    is_same = is_same_talent(doc1, doc2)
    if is_same and 'True' in is_same:
        return True

    return False


@app.post("/talent/disambiguation_agent")
def disambiguation_agent (request: CompareRequest):
    doc1_str = request.doc1_str
    try:
        doc1 = json.loads(doc1_str)
    except:
        return {"code": 90001, "info": "输入的doc1不符合json格式要求"}
    doc2_str = request.doc2_str
    try:
        doc2 = json.loads(doc2_str)
    except:
        return {"code": 90001, "info": "输入的doc2不符合json格式要求"}

    flag=compare_function(doc1, doc2)
    return {"code": 10000, "result": flag}


#if __name__ == '__main__':
#    import uvicorn
#    uvicorn.run(app, host="0.0.0.0", port=3900)

