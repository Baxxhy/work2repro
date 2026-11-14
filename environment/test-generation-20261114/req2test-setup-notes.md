# Req2Test rootless 环境

授权范围：2026-11-11，仅 Req2Test 官方评测使用独立 rootless Docker。
锁定源码：c0d7138f408bb7935d2c82e0fed82884f519b199。
专用用户：r2tbench（UID/GID 1001）。
用户目录：/root/lby-docker/req2test/user
数据和运行目录：/root/lby-docker/req2test/user/benchmark
Docker 数据：/root/lby-docker/req2test/user/benchmark/docker/data
Socket：/run/user/1001/req2test-docker-10156f49/docker.sock
服务：Req2Test 自身通过 systemd-run --user 创建的 req2test-docker-10156f49。
使用 source /root/lby-docker/req2test/user/env.sh 进入该用户专属环境。
不修改 root 的 Docker context、全局 DOCKER_HOST 或既有服务。

前置检查：用户 UID/GID 映射 165536:65536；cgroup v2；
user@1001.service 已委派 cpu memory pids；daemon systemd cgroup driver；
overlay2 classic image store；MemoryLimit=true、SwapLimit=true。
新增包：acl bubblewrap libslirp0 libsubid4 slirp4netns uidmap；未升级软件。
权限调整仅 /root/lby-docker 对 r2tbench 增加 r-x ACL（官方 no-follow 检查需要读取父目录）；
新建专属树由 r2tbench 所有，没有递归修改 /root 或现有实验目录。
官方首次验证：python-docx，sample=20，workers=1。
结果见 validate-setup.log 和 benchmark/runs/rootless-validate-20261111。

## 用户会话内 proc 兼容修复
首次官方 validate 被内核 VFS “Mount too revealing” 拒绝；
宿主 NVIDIA proc 子挂载导致新 user namespace 中 proc 挂载不被允许。
一次性私有 mount namespace 验证 non-recursive bind /proc 后成功。
仅在 /etc/systemd/system/user@1001.service.d/req2test-proc.conf 添加：
[Service]
BindPaths=/proc:/proc:norbind
只重启新建的 user@1001.service，再由官方 ensure_daemon 恢复专属 daemon。
没有修改宿主 proc/NVIDIA 挂载、全局 AppArmor/sysctl、旧服务。
修复后 64 MiB memory=swap 的最小容器启动成功。
正式复验 run-id：rootless-qualified-20261111；sample 20，workers 1。

## 最终官方验证
rootless-smoke-20261111：python-docx，sample=1，workers=1，退出码0，ok=true。
Pass 1/1；KillComplete 1/1；154 G pairs 全部 killed；
0 survived / dropped；API F1=1.0，coverage J=1.0，deviations=[]。
此前20样本仅普通执行20/20通过；其变异体阶段因父目录读取权限失败，
已修复权限后重新跑完整单样本校验，不将早期20样本运行计为完整通过。
结果：benchmark/runs/rootless-smoke-20261111/validate.json、summary.json、report.md。
其余项目数据由 fetch-all-after-validate.sh 在后台下载与官方哈希校验；
它们尚未逐项目 validate。没有启动任何模型实验。

## 2026-11-11 实验就绪检查
全部八项目、共 2051 条 eval 任务导出成功。
八项目 runtime preflight 全部退出0：python-docx、algorand-sdk、kapua、
coddy-agent、coreshop、sylius、prestashop、e-petitions。
Ubuntu 未命名 userns 限制曾导致 bwrap loopback RTM_NEWADDR 被拒。
仅为 root 拥有的专用副本 /root/lby-docker/req2test/tools/bwrap
安装 /etc/apparmor.d/req2test-bwrap 命名 profile，userns许可；
专用用户 PATH 优先该工具，不修改系统 /usr/bin/bwrap 或全局 sysctl。
规则通过一次性私有 securityfs 挂载空间加载，宿主挂载未改变。
结果：preflight-fixed.log 和 preflight/*.log、*.exit。
生成沙箱与官方 ground-truth 评估已验证；真实模型生成另行单任务检验。
