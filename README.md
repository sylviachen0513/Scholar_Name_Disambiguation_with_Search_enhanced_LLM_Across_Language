# Scholar_Name_Disambiguation_with_Search_enhanced_LLM_Across_Language
Improving scholar name disambiguation using search-enhanced language models across multiple languages.
## Project Introduction
This project aims to achieve scholar name disambiguation by using the search engine Large Language Model (LLM) to search and expand the relevant information of scholars, so as to compare and disambiguate the information of scholars. Scholar name disambiguation is an important issue in the academic community, especially when there are many scholars with the same name, it is particularly important to accurately identify and distinguish the research results of different scholars.
## Project Features
- Based on the Large Language Model: This project uses the advanced search engine Large Language Model to efficiently obtain and process the relevant information of scholars.
- Local Language Support: The project attempts to adjust English data to the local language, which significantly improves the ability of search engines to read and understand information.
- Information Comparison Function: By comparing the information of different scholars, the project can effectively measure the similarity of scholars, reduce information confusion, and improve the accuracy of academic research.
## Datasets
There are two data sets involved in the project, one is from the list of scholars who have won major awards, and the other is from the introduction of the authors of the papers. We have prepared a data set for testing purposes, which you can download and use.
## Function call
- get_talent_doc.py: Get and organize scholar information
- compare_function.py: Compare scholars
### Input format requirements:
The input string must conform to the json format of the dictionary type, and the corresponding format of each key-value pair is as follows:
- name:str
- workplace:str
- email:list or str,such as ['123@qq.com']
- honor_track:json,such as [{"time":"2005","award":"奖项"}]
- education_track:json,such as [{"fromto":"2005","school":"学校","major":"专业","scholar":"学士"}]
- professional_track:json,such as [{"fromto":"2005","agency":"单位","title":"职务"}]
