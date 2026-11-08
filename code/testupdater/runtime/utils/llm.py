import os
from langchain_openai import ChatOpenAI
model_gpt41 = ChatOpenAI(api_key='local-luna-adapter',base_url=os.environ.get('TU_LLM_URL','http://127.0.0.1:8013/v1'),model='gpt-6-luna',temperature=0.1,timeout=1200,max_retries=2)
model_deepseek = model_gpt4omini = model_llama = model_gpt41
