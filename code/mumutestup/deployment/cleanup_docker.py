import subprocess,json,os,pathlib,datetime
root=pathlib.Path('/root/Baxxhy/work2/reproductions/mumutestup')
env=dict(os.environ,DOCKER_HOST='unix:///run/mutate-docker.sock')
def run(*args):return subprocess.check_output(['docker',*args],env=env,text=True)
docker_root=run('info','--format','{{.DockerRootDir}}').strip()
assert docker_root.startswith('/root/lby-docker/'),docker_root
images=[json.loads(x) for x in run('image','ls','--format','{{json .}}').splitlines()]
old=[x for x in images if x['Repository'].startswith('testexplora-')]
containers=[json.loads(x) for x in run('ps','-a','--format','{{json .}}').splitlines()]
assert not any(x.get('Image','').startswith('testexplora-') for x in containers),'Review legacy containers before image removal'
records=[]
for img in old:
    ref=img['Repository']+':'+img['Tag']
    records.append({'image':ref,'id':img['ID'],'result':run('image','rm',ref).strip()})
remaining=[json.loads(x) for x in run('image','ls','--format','{{json .}}').splitlines()]
assert not any(x['Repository'].startswith('testexplora-') for x in remaining)
report={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'docker_root':docker_root,'removed':records,'remaining_images':[x['Repository']+':'+x['Tag'] for x in remaining],'global_prune_used':False}
(root/'cleanup-docker.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
