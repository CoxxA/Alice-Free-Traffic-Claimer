# Alice Free Traffic Claimer

自动领取 Alice Networks 免费 50GB 流量包的 Python 脚本。

脚本会先登录 Alice 账号并查询“我的流量包”。如果当前免费 50GB 流量包仍未到期，就跳过领取；到期后再次运行时才会自动领取。适合部署在 VPS 上，用 cron 每小时或每 10 分钟执行一次。

## 特性

- 零第三方依赖，只需要 Python 3
- 支持账号密码自动登录
- 支持 token 缓存，减少重复登录
- 自动查询当前 50GB 流量包到期时间
- 到期前跳过，到期后领取
- 支持 dry-run 预览

## 文件

```text
alice_claim_free_traffic.py      主脚本
alice_config.example.json        配置模板
alice_token.json                 运行后自动生成的登录缓存
```

## 配置

复制配置模板：

```bash
cp alice_config.example.json alice_config.json
```

编辑 `alice_config.json`：

```json
{
  "email": "your-email@example.com",
  "password": "your-password"
}
```

建议限制权限：

```bash
chmod 600 alice_config.json
```

## 使用

预览，不实际领取：

```bash
python3 alice_claim_free_traffic.py --dry-run
```

正常运行：

```bash
python3 alice_claim_free_traffic.py
```

如果当前流量包仍有效，会输出类似：

```text
Using cached token.
Skip claim: active free traffic package still valid (id=4079, amount=50.00 GB, remaining=50.00 GB, expires_at=2026-06-03T17:12:18+08:00)
```

如果到期后领取成功，会输出：

```text
Claimed: ALL 每 50GB Traffic Package (50.00 GB), id=3
```

如果本期已领取但服务端仍拒绝，会输出服务端原因，例如：

```text
Claim failed: ALL 每 50GB Traffic Package (50.00 GB), id=3, message=monthly purchase limit reached (1 times)
```

## 定时运行

每小时执行一次：

```cron
0 * * * * cd /path/to/alice-free-traffic-claimer && /usr/bin/python3 alice_claim_free_traffic.py >> alice_claim.log 2>&1
```

这条任务的意思是：

```text
0 * * * *     每小时的第 0 分钟执行一次
cd ...        进入脚本所在目录
python3 ...   运行脚本
>> ...        把输出追加写入 alice_claim.log
2>&1          把错误信息也写入同一个日志文件
```

它不会一直常驻后台。cron 到时间启动一次脚本，脚本运行完就退出，下一小时再启动一次。

更接近到期后立即领取，可以每 10 分钟执行一次：

```cron
*/10 * * * * cd /path/to/alice-free-traffic-claimer && /usr/bin/python3 alice_claim_free_traffic.py >> alice_claim.log 2>&1
```

查看当前定时任务：

```bash
crontab -l
```

编辑定时任务：

```bash
crontab -e
```

取消自动领取：执行 `crontab -e`，删除对应这一行，然后保存退出。

也可以临时禁用，在行首加 `#`：

```cron
# 0 * * * * cd /path/to/alice-free-traffic-claimer && /usr/bin/python3 alice_claim_free_traffic.py >> alice_claim.log 2>&1
```

查看最近日志：

```bash
tail -n 50 alice_claim.log
```

清空日志：

```bash
> alice_claim.log
```

## 参数

```text
--dry-run          只预览，不领取
--force            不检查现有流量包有效期，直接尝试领取
--claim-all        领取所有匹配到的免费流量包
--config PATH      指定配置文件，默认 alice_config.json
--token-cache PATH 指定 token 缓存文件，默认 alice_token.json
--no-token-cache   不读取或保存 token 缓存
--email EMAIL      直接传入邮箱，覆盖配置文件
--password PASS    直接传入密码，覆盖配置文件
```

## 注意

- 账号开启 2FA、验证码或触发风控时，账号密码登录接口可能失败。
- 本项目不会绕过验证码或风控，只调用 Alice 控制台前端使用的公开接口。
- 请遵守 Alice Networks 的服务条款和使用规则。
