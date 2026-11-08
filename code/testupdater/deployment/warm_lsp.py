import sys
sys.path.insert(0,'/root/Baxxhy/work2/reproductions/testupdater/runtime')
from utils.multilspy import SyncLanguageServer
from utils.multilspy.multilspy_config import MultilspyConfig
from utils.multilspy.multilspy_logger import MultilspyLogger
c=MultilspyConfig.from_dict({'code_language':'java','trace_lsp_communication':False})
l=SyncLanguageServer.create(c,MultilspyLogger(),'/root/Baxxhy/work2/reproductions/testupdater/repos/shred/acme4j')
print('assets ready',flush=True)
with l.start_server(): print('language server ready',flush=True)
print('language server shutdown cleanly',flush=True)
