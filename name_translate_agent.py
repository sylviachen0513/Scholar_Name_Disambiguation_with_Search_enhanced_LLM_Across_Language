import requests
from profile_extract_agent import get_talent_doc
import re
import json
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from pypinyin import pinyin, Style
# app = Flask(__name__)
app = FastAPI(debug=True, docs_url=None, redoc_url=None)

class DocRequest(BaseModel):
    doc_str: str
    engine: str ='bing'
    model: str ='gpt4o'
    baseline: bool=False
    with_email: bool=True


# gpt_url,chat_url输入格式为:{"text":prompt,"model":模型,"search":是否联网搜索,"engine":选择搜索引擎},输出格式为:{"data":{"gpt":答案}}

headers = {
    "Content-Type": "application/json"
}

def processed_workplace(workplace):
    payload = {
        'text': f"Please process the input workplace {workplace} as follows: "
                "1. If the input workplace is in Chinese: "
                "1.1 Supplement and improve the input Chinese workplace. For example: '上海高等研究院' should be supplemented with '中国科学院上海高等研究院'. "
                "2. If the input workplace is in English: "
                "2.1 Please translate workplace into Chinese and only output the name of the school department. For example: 'Tsinghua Univ' should be translated into '清华大学'. "
                "Please only output the processed workplace and ignore the intermediate processing.",
        'model': 'gpt4o',
        'search': True
    }
    response = requests.post(gpt_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word

def search_info_sougou(text,model='gpt4o'):
    #搜索信息
    payload = {
        'text': f"{text}",
        'model':model
    }
    response = requests.post(search_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    return response_data

def search_info_google(text,model='gpt4o'):
    payload = {
        'text': f"{text}",
        'model':model,
        'engine':'google',
        'rewrite':True,
        'expand':True
    }
    response = requests.post(search_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    return response_data

def search_info_bing(text,model='gpt4o'):
    payload = {
        'text': f"{text}",
        'model':model,
        'engine':'bing',
        'rewrite':True,
        'expand':True
    }
    response = requests.post(search_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    return response_data 

def preprocess_sougou_data(datas):
    # 初筛并处理信息
    filtered_datas = [{key: d[key] for key in ['url', 'title', 'body'] if key in d} for d in datas]
    filtered_datas = [d for d in filtered_datas if 'body' in d]
    filtered_datas = [
        d for d in filtered_datas
        if 'zhaopin' not in d.get('url', '')
    ]
    priority_substrings = ['.edu', '.aminer', '.scholarmate', '.ac', '.org', '.cas', '.cae']

    def contains_keywords(body, keywords):
        for keyword in keywords:
            if re.search(keyword, body):
                return True
        return False

    def prioritize_urls(lst, priority_substrings):
        keywords = [
            r'(教育背景|学士|硕士|博士|导师|大学|学院|博士后|访问学者)',
            r'(工作经历|研究员|教授|博士后|公司|研究所)',
            r'(研究方向|研究领域|研究兴趣)',
            r'(论文|著作|出版|发表)',
            r'(奖项|荣誉|获奖|称号)'
        ]

        filtered_lst = [item for item in lst if contains_keywords(item['body'], keywords)]

        def url_priority(item):
            url = item.get('url', '')
            for substring in priority_substrings:
                if substring in url:
                    return 0
            return 1

        sorted_lst = sorted(filtered_lst, key=url_priority)
        return sorted_lst

    sorted_lst = prioritize_urls(filtered_datas, priority_substrings)
    return sorted_lst

def preprocess_google_data(data_list):
    filtered_data = []
    for item in data_list:
        if isinstance(item,dict):
            filtered_item = {
                'url': item.get('link'),
                'title': item.get('title'),
                'body': item.get('body')
            }
            filtered_data.append(filtered_item)
    return filtered_data

def preprocess_bing_data(data_list):
    filtered_data = []
    for item in data_list:
        if isinstance(item,dict):
            filtered_item = {
                'url': item.get('url'),
                'title': item.get('title'),
                'body': item.get('body','')+item.get('snippet','')
            }
            filtered_data.append(filtered_item)
    return filtered_data

def construct_search_text(name, email=None, workplace=None, honor=None, key='search'):
    parts = []
    if name:
        parts.append(f"{name}教师")
    if workplace:
        parts.append(f"{workplace}")
    if email:
        filtered_email = [e for e in email if e is not None]
        parts.append(f"{','.join(filtered_email)}")
    if honor and 'award' in honor:
        parts.append(f"{honor['award']}")

    if key == 'search':# 获取信息
        return (f"{'，'.join(parts)}，个人主页/简介 或 homepage 或 info")
    elif key == 'sougou':# 获取中文名
        return (f"{','.join(parts)}")


def construct_paper_text(name, email=None, workplace=None,key='bing'):
    parts = []
    if name:
        parts.append(f"{name}")
    if workplace:
        parts.append(f"{workplace}")
    if email:
        filtered_email = [e for e in email if e is not None]
        parts.append(f"{','.join(filtered_email)}")
    if key=='bing':
        return (f"{'，'.join(parts)}，info homepage 个人主页")
    elif key=='google':
        return (f"{'，'.join(parts)}，info OR homepage OR profiles OR 个人主页")

def infer_name(item,query,model='gpt4o'):
    payload = {
        'text':f'Given the following information: item={item} '
        'Format of item: {"url": url, "title": title, "body": body}. '
        f'Please identify the scholar\'s Chinese name matches the given conditions query={query}? '
        'Format of query: {"name": Pinyin format, "workplace": workplace}. '
        'Please return only the identified Chinese character name or "Not Found".'
        'If the name is in traditional Chinese, please convert it to simplified Chinese. '
        'Do not return any other information. Ignore intermediate processing.',
        'model':model,       
    }
    response = requests.post(gpt_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word

def infer_chinese_name(info,query,model='gpt4o'):
    for item in info:
        response=infer_name(item,query,model)
        if response is not None and 'Not Found' not in response:
            return response
    return None

def get_school_name(affiliation):
    index = affiliation.find(',')
    if index != -1:
        processed_aff = affiliation[:index].strip()
    else:
        processed_aff = affiliation
    return processed_aff

def simple_workplace(workplace):
    comma_indices = [i for i, char in enumerate(workplace) if char == ',']
    if len(comma_indices) >= 2:
        workplace = workplace[:comma_indices[1]]
        return workplace.replace(',', '')
    else:
        return workplace.replace(',', '')

def preprocess_info(info, engine):
    if engine == 'google':
        return preprocess_google_data(info)
    elif engine == 'sougou':
        return [{k: d[k] for k in ['url', 'title', 'body'] if k in d} for d in info]
    else:
        return preprocess_bing_data(info)

def get_chinese_name(doc2, engine='google',infer_model='gpt4o',search_model='gpt4o'):
    name = doc2.get('name')
    workplace = simple_workplace(doc2.get('workplace', ''))
    address = get_school_name(doc2.get('workplace', ''))
    email = doc2.get('email', '')
    workplace = processed_workplace(workplace) if workplace else None

    if engine == 'google':
        paper_text = construct_paper_text(name, None,workplace,engine)
        info = search_info_google(paper_text,search_model)
    elif engine == 'sougou':
        paper_text = construct_search_text(name, email, workplace,engine)
        info = search_info_sougou(paper_text,search_model)
    else:
        paper_text=construct_paper_text(name, None, workplace, engine)
        info =search_info_bing(paper_text,search_model)

    if isinstance(info, dict):
        return None

    processed_info = preprocess_info(info, engine)
    chinese_name = infer_chinese_name(processed_info, filter_query(name, workplace),infer_model)
    return chinese_name

def fetch_chinese_name(doc2,name,engine,model,with_email=False):
    workplace=doc2.get('workplace','')
    chinese_name = get_chinese_name(doc2,engine,infer_model=model)
    if with_email==False:
        if chinese_name is not None:
            pinyin_format = name_to_pinyin(chinese_name)
            if 'Hong Kong' not in workplace and name not in pinyin_format:
                return None
        else:
            return chinese_name
    else:
        if chinese_name is None:
            chinese_name = get_chinese_name(doc2, 'sougou',infer_model=model)
        else:
            pinyin_format = name_to_pinyin(chinese_name)
            if 'Hong Kong' not in workplace and name not in pinyin_format:
                chinese_name = get_chinese_name(doc2, 'sougou',infer_model=model)
        return chinese_name

def process_name(name):
    processed_name = re.sub(r'[^a-zA-Z\s]', '', name)
    processed_name = processed_name.title()
    return processed_name

def name_to_pinyin(name):
    pinyin_list = pinyin(name, style=Style.NORMAL)
    surname = pinyin_list[0][0].capitalize()
    given_name = ''.join([item[0] for item in pinyin_list[1:]]).capitalize()
    all_pinyin = ' '.join([item[0].capitalize() for item in pinyin_list])
    return [f"{surname} {given_name}",all_pinyin, f"{given_name} {surname}"]


def get_paper_doc_from_chinese(doc,engine,model,with_email=True,baseline=False):
    pinyin_name=process_name(doc['name'])
    chinese_name=fetch_chinese_name(doc,pinyin_name,engine,model,with_email)

    if chinese_name is not None:
        doc['name']=chinese_name
    updated_doc,candidates=get_talent_doc(doc,engine,model,baseline)

    if updated_doc is None:
        doc['name']=name
        updated_doc, candidates = get_talent_doc(doc,engine,model,baseline)
    return updated_doc,candidates


@app.post('/talent/name_translate_agnet')
def name_translate_agent(request:DocRequest):
    doc_str=request.doc_str
    engine=request.engine
    model=request.model
    baseline=request.baseline
    with_email=request.with_email

    try:
        doc=json.loads(doc_str)
    except:
        return {"code": 90000, "info": "输入的doc不符合json格式要求"}
    updated_doc,candidates=get_paper_doc_from_chinese(doc,engine,model,with_email,baseline)

    if updated_doc is not None:
        return {"code": 91000, "candidates": updated_doc}
    else:
        if len(candidates)==0:
            return {"code": 90002, "error": "未找到合适的候选人", "candidates": None}
        else:
            return {"code": 90003, "error": "找到多位候选人信息", "candidates": candidates}
