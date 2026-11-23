from pathlib import Path
from req2test import evaluate, predictions
home = Path.home()
for project in ('sylius', 'coreshop'):
    ids = set()
    for f in (home/'runs').glob(f'req2test-paired80-20261123-?/input/*-audit-{project}.ids'):
        ids.update(f.read_text().splitlines())
    ids = sorted(ids)
    assert len(ids) == {'sylius':4,'coreshop':6}[project]
    evaluate.evaluate(None, run_id='req2test-paired80-gold-1123-'+project,
                      project=project, view='th', workers=1, metrics='exec',
                      instances=ids, predictions=predictions.from_gt(project,ids,view='th'),
                      docker_host='unix:///run/user/1001/req2test-docker-10156f49/docker.sock')
