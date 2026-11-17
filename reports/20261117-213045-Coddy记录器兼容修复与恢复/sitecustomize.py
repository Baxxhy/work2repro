import os
if os.environ.get('R2T_EXTENDED_TIMEOUTS') == '20261117-v1':
    from timeout_policy import activate
    activate()
