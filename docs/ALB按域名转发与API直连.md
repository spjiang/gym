# ALB 按域名转发与 API 直连（运维）

服务器：`39.103.56.168`  
ALB：`alb-d4twwuigzrzjzxomtf`（北京）

目的：小程序真机访问 API 报 `-101`（连 ALB 被 RST）。浏览器 https 正常。

---

## 1. 按域名转到正确端口（80 和 443 同一套）

| 域名 | 转到主机端口 |
|------|----------------|
| `admin.guanyespace.com` | 8080（管理后台） |
| `m.guanyespace.com` | 8081（H5） |
| `api.guanyespace.com` | **18000（API）** |
| `guanyespace.com` / `www.guanyespace.com` | 8082（官网） |
| `file.guanyespace.com` | 8900（图） |

HTTPS:443、HTTP:80 **都要按上表转发**。  
当前错误：`http://api.guanyespace.com` 进了 8080，应进 **18000**。

监听：HTTP2 关、QUIC 关、不用国密。  
`http://` 只能是 80，不能改成别的公网端口。

验收：浏览器打开 `http://api.guanyespace.com/health` 应返回 `{"status":"ok"}`，不能是后台网页。

---

## 2. 把 API 从 ALB 拿下来（治小程序 -101）

第 1 步验收通过后：

1. 安全组放行 **TCP 443**
2. DNS：`api` 从 ALB 的 CNAME **改成 A 记录 `39.103.56.168`**  
   （admin / m / www 先不动）
3. 通知开发在机器上装 `api` 的 443 证书 + Nginx 反代 18000

回滚：`api` 的 DNS 改回 ALB CNAME。

不要配 `www.api.guanyespace.com`。
