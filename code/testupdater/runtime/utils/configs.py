import os
REPO_BASE = '/root/Baxxhy/work2/reproductions/testupdater/repos'
FILE_BASE = '/root/Baxxhy/work2/reproductions/testupdater/runtime'
OPENAI_API_KEY = 'local-luna-adapter'
DEEPSEEK_API_KEY = 'local-luna-adapter'
LANGCHAIN_API_KEY = ''
DATA_BASE = os.environ.get('TU_DATA_BASE', FILE_BASE+'/data')
OUTPUT_BASE = os.environ.get('TU_OUTPUT_BASE', '/root/Baxxhy/work2/reproductions/testupdater/runs')
TIME_ZONE = 'UTC'
mvn_dict = {v:'/root/Baxxhy/work2/reproductions/mumutestup/toolchains/maven' for v in ['mvnw','3.8.6','3.8.1','3.6.3','3.9.9']}
java_dict = {v:'/root/Baxxhy/work2/reproductions/mumutestup/toolchains'+'/jdk'+ ('8' if v in ['1.8','1.8.0'] else v) for v in ['1.8','1.8.0','8','11','17','21']}
src_files = ['verified_shred_acme4j.json', 'verified_OpenAPITools_openapi-generator.json', 'verified_apache_shenyu.json', 'verified_apache_rocketmq.json', 'verified_prebid_prebid-server-java.json', 'verified_Aiven-Open_klaw.json', 'verified_alibaba_nacos.json']
