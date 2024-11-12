import pandas as pd
import re
import json
import numpy as np
import csv
from concurrent.futures import as_completed, ProcessPoolExecutor
from tqdm import tqdm
import requests
from requests.auth import HTTPBasicAuth
from pypinyin import pinyin, Style
import logging


headers = {
    "Content-Type": "application/json"
}

# gpt_url,chat_url输入格式为:{"text":prompt,"model":模型,"search":是否联网搜索,"engine":选择搜索引擎},输出格式为:{"data":{"gpt":答案}}
# search_url输入格式为:{"text":prompt,"model":模型,"engine":选择搜索引擎,"expand":解析网页信息},输出格式为:[{"url":网址,"title":标题,"body":网页内容}]

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


def is_school(workplace):
    payload = {
        'text': f"Please determine whether the following {workplace} is a higher education institution in mainland China, excluding Hong Kong, Macao, Taiwan and overseas regions. "
f" If {workplace} contains the complete name of a higher education institution, please return True; otherwise, please return False. "
" Pay special attention to the fact that when {workplace} contains the substrings of '中国科学院' and '大学', True should be returned"
" Please only output the inferred result, that is, True or False.",
        'model': 'hy',
    }
    response = requests.post(chat_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word


def search_info(text):
    # 搜索信息
    payload = {
        'text': f"{text}",
        'model': 'hy'
    }
    response = requests.post(search_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    return response_data


def search_info_google(text):
    payload = {
        'text': f"{text}",
        'model': 'gpt4o',
        'engine': 'google',
        'rewrite': True,
        'expand': True
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


def talent_search(text):
    payload = {
        'text': f"{text}",
        'model': 'gpt4o',
        'search': True

    }
    response = requests.post(gpt_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word


def get_mainpage_info(item):
    payload = {
        'text': f'Given the following information: item={item}. '
                'Format of item: {"url": url, "title": title, "body": body}. '
                'Determine if the item is a biography or personal homepage of an individual. '
                'The judging criteria are whether the body text contains relevant information such as educational background, work experience, research field etc.'
                'If the body contains information related to papers or research, it is more likely to be a personal homepage.'
                'Please return only "True" if it is a biography or personal homepage, otherwise return "False".',
        'model': 'gpt4o',
    }
    response = requests.post(gpt_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word


def filter_unrelated_info(item, query):
    payload = {
        'text': f'Given the following information: item={item},query={query}. '
                'Format of item: {"url": url, "title": title, "body": body}. '
                'Format of query: {"name": Chinese character or Pinyin format, "workplace": workplace}. '
                'Please determine if the item is related to the query based on the following criteria: '
                '1. Check if any expression of query["name"] appears in the item, including: '
                '   - Chinese name (e.g., 齐殿鹏) '
                '   - Pinyin representation (e.g., qi dianpeng) '
                '   - English name (e.g., dianpeng qi) '
                '   Note: The check is case-insensitive and ignores spaces. '
                '2. Check if the item mentions query["workplace"], considering variations such as Peking Univ and 北京大学 as equivalent. '
                'Please return only "True" If the item contains relevant information related to query,otherwise, return "False".',
        'model': 'gpt4o',
    }
    response = requests.post(gpt_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word


def filter_query(name, workplace=None):
    query_dict = {"name": name, "workplace": workplace}
    return query_dict

def deep_processed(datas):
    # 去重
    payload = {
        'text': f"Given the following information: datas={datas},"
"Format of datas: [{'url': url, 'title': title, 'body': body}].Each dictionary record represents the information of a scholar and contains three fields: url, title and body. The body field contains the text content of the web page. "
"Please deduplicate the scholar information according to the following rules:"
"1. The basis for judging whether it is duplicate scholar information is that the information in the dictionary is the personal biography of the scholar. The scholar's education, work experience, research field, work unit, etc. can be used to judge whether it is the same scholar. "
"2. For duplicate scholar information, the dictionary records containing the names of colleges and universities or professional institutions in the title are preferred;"
"3. If there are multiple dictionary records that meet the conditions, the dictionary records containing paper-related information in the body field are preferred;"
"4. If there are still multiple dictionary records that meet the conditions, the dictionary record with the longest body content is retained. "
"The output should contain all dictionary records that meet the conditions. If there is no dictionary that meets the requirements, None is returned. No intermediate processing and analysis process is output. "
"Please make sure that the output meets the format requirements: the two dictionaries must be separated by '||', that is, {dict1}||{dict2}.",
        'model':'gpt4o', 
    }
    response = requests.post(chat_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word


def is_same_talent(doc1, doc2):
    if not isinstance(doc1, str):
        doc1_str = json.dumps(doc1, ensure_ascii=False)
    else:
        doc1_str = doc1

    if not isinstance(doc2, str):
        doc2_str = json.dumps(doc2, ensure_ascii=False)
    else:
        doc2_str = doc2
    # 判断两位学者是否相同
    payload = {
        'text': f"You will get two json strings in dictionary format {doc1_str} and {doc2_str}. Please judge whether the scholar information recorded in these two dictionaries belongs to the same scholar. Please pay special attention to the following fields in order: "
"workplace: If the workplace is similar, score 2 points. For example, 'Shanghai Advanced Research Institute of the Chinese Academy of Sciences' and 'Shanghai Advanced Research Institute' refer to the same place. If there is no relevant field, it will be recorded as 0 points. "
"education_track: Focus on the school and scholar fields. If two scholars obtain the same degree (scholar field) in the same school (school field), each record will score 3 points. If there is no relevant field, it will be recorded as 0 points. "
"professional_track: Focus on the agency field. If two scholars obtain the same professional title (title field) in the same agency (agency field), each record will score 3 points. If there is no relevant field, it will be recorded as 0 points. "
"keywords: Compare whether the research fields of scholars are similar or the same. If the research fields are highly similar, score 1-4 points. If there are no relevant fields, score 0 points. "
"Please judge whether the two are the same scholar based on the scores. If the scores reach or exceed 7 points, they can be judged as the same scholar. Please only output the final inference answer: True or False, without the intermediate analysis process.",
        'model':'gpt4o',
    }
    response = requests.post(gpt_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word


hy_headers = {
    'Authorization': 'Bearer 7auGXNATFSKl7dF',
    'Content-Type': 'application/json'
}

# url输入格式为:{"query":prompt,"forward_service":"hyaide-application"+唯一四位数字,"query_id":"qid_123456"},输出格式为:{"result":答案}

def summary_info(query):
    if not isinstance(query, str):
        query = json.dumps(query, ensure_ascii=False)
    data = {
        "query": query,
        "forward_service": "hyaide-application-4745",
        "query_id": "qid_123456"
    }
    response = requests.post(url, headers=hy_headers, data=json.dumps(data))
    response.raise_for_status()
    word = response.json().get('result', None)
    return word


def url_search(query):
    data = {
        "query": query,
        "forward_service": "hyaide-application-4748",
        "query_id": "qid_123456"
    }
    response = requests.post(url, headers=hy_headers, data=json.dumps(data))
    response.raise_for_status()
    word = response.json().get('result', None)
    return word


def process_email(email2):
    if isinstance(email2, str):
        return [email2]
    elif isinstance(email2, list):
        if len(email2) == 0:
            return None
        edu_emails = [email for email in email2 if isinstance(email, str) and ".edu" in email]
        non_edu_emails = [email for email in email2 if isinstance(email, str) and ".edu" not in email]
        return edu_emails + non_edu_emails
    else:
        return None


honors = ["中国科学院院士", "中国工程院院士", "长江学者特聘教授", "长江学者讲座教授", "国家杰出青年科学基金获得者",
          "国家“万人计划”科技创新领军人才", "35岁以下科技创新35人", "青年长江学者"]


def sort_honor_track(honor_track):
    if not honor_track or not isinstance(honor_track, list):
        return honor_track

    for item in honor_track:
        if not isinstance(item, dict):
            return honor_track

    honor_track = [item for item in honor_track if item.get('award') != '五年顶刊通信作者']
    if not honor_track:
        return None

    sorted_honor_track = sorted(
        honor_track,
        key=lambda x: (x.get('award') not in honors,
                       honors.index(x.get('award')) if x.get('award') in honors else float('inf'))
    )
    return sorted_honor_track


def extract_dict_url(s):
    pattern = r'{"url": "(.*?)", "title": "(.*?)", "body": "(.*?)"}'
    match = re.search(pattern, s)
    if match:
        return {
            "url": match.group(1),
            "title": match.group(2),
            "body": match.group(3)
        }
    return None

def process_single_candidate(candidate):
    url = candidate['url']
    doc2_extra = candidate['body']
    if len(doc2_extra) < 200:
        doc2_extra = url_search(url)
    doc2_extra_summary = summary_info(doc2_extra)
    return doc2_extra_summary


def search_candidate(text, query, candidates, key='sougou'):
    if key == 'sougou':
        data = search_info(text)
        info1 = preprocess_sougou_data(data)
    else:
        data = search_info_google(text)
        info1 = preprocess_google_data(data)
    if isinstance(info1,dict):
        return None,candidates

    info2, info3, info4, info5 = [], [], [], []
    for item in info1:  # 获取主页信息
        mainpage_info = get_mainpage_info(item)
        if mainpage_info is not None and 'True' in mainpage_info:
            info2.append(item)
    if len(info2) == 0:
        return None, candidates

    for item in info2:  # 删去不相关信息
        filtered_info = filter_unrelated_info(item, query)
        if filtered_info is not None and 'True' in filtered_info:
            info3.append(item)
    if len(info3) == 0:
        return None, candidates
    elif len(info3) == 1:
        return process_single_candidate(info3[0]), candidates

    info4 = deep_processed(json.dumps(info3, ensure_ascii=False))  # 删除重复信息
    if info4 is None or 'None' in info4 or info4 == '' or 'example.com' in info4 or 'python' in info4 or 'import' in info4:
        return None, candidates
    if '||' not in info4:
        candidate = extract_dict_url(info4)
        if candidate:
            return process_single_candidate(candidate), candidates

    info4_lst = info4.split('||')
    for word in info4_lst:
        if info5:
            is_same = is_same_talent(info5[-1], word)
            if is_same is not None and 'True' in is_same:
                continue
        info5.append(word)
    if len(info5) == 1:
        candidate = extract_dict_url(info5[0])
        if candidate:
            return process_single_candidate(candidate), candidates
    else:
        candidates.append(info5)

    return None, candidates


def construct_chat_text(name, email=None, workplace=None, honor=None):
    parts = []
    if name:
        parts.append(f"请搜索姓名为{name}")
    if workplace:
        parts.append(f"机构为{workplace}")
    if email:
        parts.append(f"{', '.join(email)}")
    if honor and 'award' in honor:
        parts.append(f"获得{honor['award']}奖项")

    if parts:
        return (f"{'，'.join(parts)}。请获取并汇总教育经历、工作经历、研究领域、工作地点等个人介绍信息。\n"
                "请确保获取到所有满足条件的学者信息，并提示学者数量，格式为'学者数量==X'，其中X为学者数量。不同学者信息之间请务必用'||'进行分割。")


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

    if key == 'search':
        return (f"{'，'.join(parts)}，个人主页/简介 或 homepage 或 info")
    elif key == 'sougou':
        return (f"{','.join(parts)}")


def construct_paper_text(name, email=None, workplace=None):
    parts = []
    if name:
        parts.append(f"{name}")
    if workplace:
        parts.append(f"{workplace}")
    if email:
        filtered_email = [e for e in email if e is not None]
        parts.append(f"{','.join(filtered_email)}")

    return (f"{'，'.join(parts)}，info OR homepage OR profiles OR 个人主页")

def process_name(name):
    processed_name = re.sub(r'[^a-zA-Z\s]', '', name)
    processed_name = processed_name.title()
    return processed_name


def handle_search_result(doc2_extra, candidates):
    if doc2_extra is None:
        return None, candidates
    match = re.search(r'学者数量\s*==\s*(\d+)', doc2_extra)
    if match:
        scholar_count = int(match.group(1))
        if scholar_count == 0:
            return None, candidates
        elif scholar_count == 1:
            doc2_extra_summary = summary_info(doc2_extra)
            return doc2_extra_summary, candidates
        else:
            info = []
            doc2_extra_lst = doc2_extra.split('||')
            for word in doc2_extra_lst:
                if info:
                    is_same = is_same_talent(info[-1], word)
                    if is_same is not None and 'True' in is_same:
                        continue
                info.append(word)
            if len(info) == 1:
                doc2_extra_summary = summary_info(info[0])
                return doc2_extra_summary, candidates
            else:
                candidates.append(info)

    return None, candidates

def preprocess_google_data(data_list):
    filtered_data = []
    for item in data_list:
        if isinstance(item, dict):
            filtered_item = {
                'url': item.get('link'),
                'title': item.get('title'),
                'body': item.get('body')
            }
            filtered_data.append(filtered_item)
    return filtered_data


def infer_name(item,query):
    payload = {
        'text':f'Given the following information: item={item} '
        'Format of item: {"url": url, "title": title, "body": body}. '
        f'Please identify the scholar\'s Chinese name matches the given conditions query={query}? '
        'Format of query: {"name": Pinyin format, "workplace": workplace}. '
        'Please return only the identified Chinese character name or "Not Found".'
        'If the name is in traditional Chinese, please convert it to simplified Chinese. '
        'Do not return any other information. Ignore intermediate processing.',
        'model':'gpt4o',
    }
    response = requests.post(gpt_url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    word = response_data.get('data', {}).get('gpt')
    return word


def infer_chinese_name(info, query):
    for item in info:
        response = infer_name(item, query)
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


def get_chinese_name(doc2, key='google'):
    name = doc2.get('name')
    workplace = doc2.get('workplace', '')
    address = get_school_name(doc2.get('workplace', ''))
    email = doc2.get('email', '')

    if key == 'google':
        paper_text = construct_search_text(name, workplace=address,key='google')
        info = search_info_google(paper_text)
    else:
        address = processed_workplace(address)
        paper_text = construct_search_text(name, email=email, workplace=address,key='sougou')
        info = search_info(paper_text)

    if isinstance(info, dict):
        return None

    processed_info = preprocess_info(info, key)
    chinese_name = infer_chinese_name(processed_info, filter_query(name, address))
    return chinese_name


def preprocess_info(info, key):
    if key == 'google':
        return preprocess_google_data(info)
    else:
        return [{k: d[k] for k in ['url', 'title', 'body'] if k in d} for d in info]


def extract_fields_using_regex(doc2_summary):
    """使用正则表达式从doc2_summary中提取字段"""
    fields = ["name", "email", "workplace", "education_track", "professional_track", "honor_track", "keywords"]
    extracted_data = {}

    for field in fields:
        pattern = f'"{field}"\s*:\s*(\[.*?\]|".*?"|null)'
        match = re.search(pattern, doc2_summary)
        if match:
            value = match.group(1)
            if value == "null":
                extracted_data[field] = None
            elif value.startswith('['):
                try:
                    extracted_data[field] = json.loads(value)
                except:
                    extracted_data[field] = []
            else:
                extracted_data[field] = value.strip('"')
    return extracted_data

def is_dict_empty_or_null(d):
    """检查字典中的所有值是否都为 null"""
    return all(value in [None, "null"] for value in d.values())

def update_field(doc2_field, summary_field):
    """更新字段，去重并过滤'null'值"""
    if isinstance(doc2_field, str):
        try:
            doc2_field = json.loads(doc2_field)
        except json.JSONDecodeError:
            doc2_field = []

    doc2_field=[] if doc2_field is None else doc2_field
    summary_field=[] if summary_field is None else summary_field

    summary_field = [item for item in summary_field if item != "null"]
    summary_field = [item for item in summary_field if not isinstance(item, dict) or not is_dict_empty_or_null(item)]
    return json.dumps(doc2_field + summary_field, ensure_ascii=False)

def update_doc2_from_summary(doc2, doc2_summary):
    try:
        summary_data = json.loads(doc2_summary)
    except json.JSONDecodeError:
        summary_data = extract_fields_using_regex(doc2_summary)

    for col in ['name', 'workplace']:
        if summary_data.get(col) != 'null':
            doc2[col] = summary_data.get(col, doc2.get(col))

    for col in ['email', 'keywords']:
        if doc2.get(col) is None:
            doc2[col] = []
        if summary_data.get(col) is not None:
            doc2[col] = list(set(doc2[col] + [x for x in summary_data.get(col, []) if x != 'null']))

    for col in ['education_track', 'professional_track', 'honor_track']:
        if summary_data.get(col) is not None:
            doc2[col] = update_field(doc2.get(col, '[]'), summary_data.get(col, []))

    return doc2

def check(updated_doc2):
    edu,pro,key=updated_doc2.get('education_track'),updated_doc2.get('professional_track'),updated_doc2.get('keywords')
    if (edu in ['[]','[null]']) and (pro in ['[]','[null]']) and (key==[] or key==[None]):
        return None
    return updated_doc2

def get_doc(doc2):
    name2 = doc2.get('name')
    workplace2 = doc2.get('workplace')
    address = get_school_name(workplace2) if workplace2 is not None else None
    email2 = doc2.get('email', [])
    honor_track2 = doc2.get('honor_track', '[]')
    try:
        honor_track2 = json.loads(honor_track2)
        honor_track2 = sort_honor_track(honor_track2)
    except:
        honor_track2=[]

    email2 = process_email(email2)
    workplace2 = processed_workplace(workplace2)
    doc2['email']=email2
    honor = honor_track2[0] if honor_track2 and isinstance(honor_track2, list) else None
    if not isinstance(honor, dict) and honor != None:
        honor = None
    chat_text = construct_chat_text(name2, email2, workplace2, honor)
    search_text = construct_search_text(name2, email2, workplace2, honor,'search')
    query = filter_query(name2, workplace2)
    candidates=[]
    doc2_extra_summary, updated_doc2 = None, None
    if workplace2:
        flag = is_school(workplace2)
        if flag is not None and 'True' in flag:
            doc2_extra_summary, candidates = search_candidate(search_text, query, candidates, 'sougou')
            if doc2_extra_summary is None:
                doc2_extra = talent_search(chat_text)
                doc2_extra_summary, candidates = handle_search_result(doc2_extra, candidates)
        else:
            doc2_extra = talent_search(chat_text)
            doc2_extra_summary, candidates = handle_search_result(doc2_extra, candidates)

    else:
        doc2_extra = talent_search(chat_text)
        doc2_extra_summary, candidates = handle_search_result(doc2_extra, candidates)

    if doc2_extra_summary:
        updated_doc2 = update_doc2_from_summary(doc2, doc2_extra_summary)
        updated_doc2 = check(updated_doc2)

    return updated_doc2, candidates

def fetch_chinese_name(doc2,name):
    workplace=doc2.get('workplace','')
    chinese_name = get_chinese_name(doc2)
    if chinese_name is None:
        chinese_name = get_chinese_name(doc2, 'sougou')
    else:
        pinyin_format = name_to_pinyin(chinese_name)
        if 'Hong Kong' not in workplace and name not in pinyin_format:
            chinese_name = get_chinese_name(doc2, 'sougou')
    return chinese_name

def name_to_pinyin(name):
    pinyin_list = pinyin(name, style=Style.NORMAL)
    surname = pinyin_list[0][0].capitalize()
    given_name = ''.join([item[0] for item in pinyin_list[1:]]).capitalize()
    all_pinyin = ' '.join([item[0].capitalize() for item in pinyin_list])
    return [f"{surname} {given_name}",all_pinyin, f"{given_name} {surname}"]


def get_paper_doc(doc):
    name = process_name(doc['name'])
    doc['name'] = name
    chinese_name = fetch_chinese_name(doc,name)
    doc['workplace']=simple_workplace(doc['workplace'])
    if chinese_name is not None:
        doc['name'] = chinese_name
    updated_doc, candidates = get_doc(doc)
    if updated_doc is None:
        doc['name'] = name
        chinese_name = get_chinese_name(doc, 'sougou')
        if chinese_name is not None:
            doc['name'] = chinese_name
            updated_doc, candidates = get_doc(doc)
    if updated_doc is None:
        doc['name']=name
        updated_doc,candidates=get_doc(doc)

    return updated_doc,candidates
