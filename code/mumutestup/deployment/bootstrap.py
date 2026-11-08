import concurrent.futures, json, os, pathlib, subprocess, tarfile, time
R=pathlib.Path('/root/Baxxhy/work2/reproductions/mumutestup')
T=R/'toolchains'; T.mkdir(exist_ok=True)
proxy='http://127.0.0.1:7890'
def download(name,url,target):
    if target.exists(): return {'name':name,'path':str(target),'reused':True}
    archive=T/(name+'.tar.gz')
    subprocess.run(['curl','--proxy',proxy,'-fL','--retry','4','--connect-timeout','30','-o',str(archive)+'.part',url],check=True,stdout=subprocess.DEVNULL,stderr=open(T/(name+'.download.log'),'w'))
    pathlib.Path(str(archive)+'.part').rename(archive)
    dest=T/(name+'-extract');dest.mkdir(exist_ok=True)
    with tarfile.open(archive) as tf: tf.extractall(dest,filter='data')
    top=list(dest.iterdir()); assert len(top)==1,top
    top[0].rename(target);dest.rmdir()
    return {'name':name,'path':str(target),'bytes':archive.stat().st_size}
jobs=[(f'jdk{v}',f'https://api.adoptium.net/v3/binary/latest/{v}/ga/linux/x64/jdk/hotspot/normal/eclipse',T/f'jdk{v}') for v in [8,11,17,21]]
jobs.append(('maven','https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.6/apache-maven-3.9.6-bin.tar.gz',T/'maven'))
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    futures=[pool.submit(download,*j) for j in jobs]
    for f in concurrent.futures.as_completed(futures): print(json.dumps(f.result()),flush=True)
(R/'toolchains-ready.json').write_text(json.dumps({'time':time.time(),'paths':{j[0]:str(j[2]) for j in jobs}},indent=2))
