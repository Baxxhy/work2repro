import pathlib,json,tarfile,subprocess
r=pathlib.Path(__file__).resolve().parent
requests={'e-petitions':{'app/models/admin_user.rb':[46],'app/controllers/admin/omniauth_callbacks_controller.rb':[1],'app/controllers/admin/admin_controller.rb':[1],'app/models/concerns/browseable.rb':[204]},'coreshop':{'src/CoreShop/Bundle/CoreBundle/Command/InstallFixturesCommand.php':[40]}}
for project,wanted in requests.items():
 arc=pathlib.Path('/root/lby-docker/req2test/user/benchmark/views')/project/'base.tar.zst'
 proc=subprocess.Popen(['zstd','-dc',str(arc)],stdout=subprocess.PIPE)
 with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
  for m in tar:
   if not m.isfile():continue
   match=next((p for p in wanted if m.name.endswith(p)),None)
   if not match and not (project=='kapua' and m.name.endswith('ExceptionSteps.java')):continue
   if m.size>2000000:continue
   dest=r/'source-context'/project/(match or pathlib.Path(m.name).name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(m).read());print(project,m.name,flush=True)
 proc.wait()
