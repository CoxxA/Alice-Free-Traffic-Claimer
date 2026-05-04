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
```

运行后会生成：

```text
alice_token.json                 登录 token 缓存
```

请不要提交真实的 `alice_config.json` 或 `alice_token.json`。

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

更接近到期后立即领取，可以每 10 分钟执行一次：

```cron
*/10 * * * * cd /path/to/alice-free-traffic-claimer && /usr/bin/python3 alice_claim_free_traffic.py >> alice_claim.log 2>&1
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
- `alice_config.json` 和 `alice_token.json` 都包含敏感信息，不要上传到公开仓库。
