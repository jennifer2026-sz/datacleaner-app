# Jeam操作清单：Gumroad 收款上线

## 状态
- Paddle 被拒（不支持中国卖家）→ 已决定迁移到 Gumroad
- 网站已更新：去 Paddle，上 Gumroad，统一定价
- 许可证生成器完成，随时可用

---

## 第 1 步：注册 Gumroad 账号（30 分钟）

1. 打开 https://gumroad.com/signup
2. 用 contact@getdatacleaner.com 注册
3. **关键：国家选 China，PayPal 账号填你的 PayPal**
   - Gumroad 给非美国/英国/加拿大/澳大利亚卖家提现走 PayPal
   - 你需要一个能收国际款的 PayPal 账号
   - 如果没有 PayPal 商业账号，去 paypal.com 注册

4. 验证邮箱

5. Settings → Payments：
   - 连接 PayPal 账号
   - 设置提现方式

---

## 第 2 步：创建产品（20 分钟）

创建 2 个产品：

### Product 1: DataCleaner Pro

| 字段 | 值 |
|------|-----|
| Name | DataCleaner Pro License |
| Price | $99.00 |
| Type | Software / Digital product |
| Description | One-time purchase. Local-first PII detection & redaction CLI. LLM-powered, offline license validation. |

**在 License Keys 设置中启用 → Upload CSV（稍后做）**

记下产品 URL：`https://gumroad.com/l/___________`

### Product 2: DataCleaner Team

| 字段 | 值 |
|------|-----|
| Name | DataCleaner Team License (5 seats) |
| Price | $299.00 |
| Type | Software / Digital product |
| Description | One-time purchase. Team license for up to 5 members. Everything in Pro + PostgreSQL integration + Docker image. |

**在 License Keys 设置中启用 → Upload CSV（稍后做）**

记下产品 URL：`https://gumroad.com/l/___________`

---

## 第 3 步：生成许可证密钥（5 分钟）

在项目根目录运行：

```bash
cd G:\DeepSeek-Prodects\DataCleaner-PII脱敏工具

# 生成 500 个 Pro 许可证（无过期日）
python datacleaner/generate_licenses.py --tier pro --count 500 -o pro_licenses.csv

# 生成 200 个 Team 许可证（无过期日）
python datacleaner/generate_licenses.py --tier team --count 200 -o team_licenses.csv
```

生成的 CSV 格式就是 Gumroad 直接能用的格式。

---

## 第 4 步：上传许可证到 Gumroad（5 分钟）

1. 在 Gumroad → Products → DataCleaner Pro → License Keys
2. Upload CSV → 选择 `pro_licenses.csv`
3. 同样操作 Team 产品

Gumroad 会自动在买家付款后分配一个未使用的许可证密钥。

---

## 第 5 步：更新网站链接（5 分钟）

拿到 Gumroad 产品 URL 后，修改 `docs/purchase.html`：

搜索 `YOUR_PRO_PRODUCT_ID` → 替换为实际 product ID
搜索 `YOUR_TEAM_PRODUCT_ID` → 替换为实际 product ID

或者直接告诉我 product ID，我来改。

---

## 第 6 步：测试购买流程（15 分钟）

1. 创建一个 100% off 折扣码给自己
2. 用折扣码"购买"一次
3. 确认：收到许可证密钥邮件
4. 拿到密钥后运行：`dc license activate DCP-xxxxxx`
5. 确认激活成功

---

## 备用方案

如果 Gumroad 也不行（极小概率），备选：

| 方案 | 操作 |
|------|------|
| Payoneer Checkout | payoneer.com → 注册 → Request Payment → 创建支付链接 |
| Lemonsqueezy | lemonsqueezy.com → 注册 → 看看支不支持中国 |
| FastSpring | fastspring.com → 联系销售 |

---

## 产品 URL 记录（填好后告诉我）

| 产品 | Gumroad URL |
|------|------------|
| Pro | _______________ |
| Team | _______________ |
