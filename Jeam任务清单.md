# Jeam任务清单

> 说明：这个文件里是需要你手动操作的事情。我做不了（需要真人身份、登录、支付等）。
> 做完一项就在后面标注 done，没做完写情况说明。
> 更新时间：2026-05-19（星辰创建）

---

## 第一优先级：Paddle 收款通道

### 任务1：跟进 Paddle 商户审核 ⬜ Jeam待办 🔥 URGENT
- 5月3日已提交，今天（5/19）收到拒信
- **拒绝原因：提交了 jennifer2026-sz.github.io 子域名，而非正式域名**
- 需要做的：
  1. 点击 Paddle 邮件中的 "Submit additional information" 链接
  2. **将域名改为 getdatacleaner.com**
  3. 在补充说明中写：
     - "Our primary domain is getdatacleaner.com (not the github.io subdomain). 
        The github.io was used only during initial development. 
        getdatacleaner.com has been live since May 1 with full legal pages 
        (Privacy Policy, Terms of Service, EULA), professional landing page, 
        and active engineering blog."
     - 附上链接：https://getdatacleaner.com, https://getdatacleaner.com/privacy.html, https://getdatacleaner.com/terms.html, https://getdatacleaner.com/eula.html
  4. 确认网站访问正常（已检查：200 OK，Cloudflare CDN）
  5. 确认 purchase.html 页面有清晰的产品描述和价格
- 建议：可以同时在 GitHub Pages 设置里确认 Custom Domain 指向 getdatacleaner.com
- 参考：Post #4 博客记录了完整部署过程

---

## 第二优先级：产品上架与销售

### 任务2：Paddle Checkout 测试 ⬜ Jeam待办（等审核通过后）
- 测试购买流程：从 getdatacleaner.com 点击购买 → Paddle 结账 → 支付成功
- 测试许可证 key 自动发送
- 测试退款流程

### 任务3：Paddle 价格确认 ⬜ Jeam待办
- 当前定价：Free / Pro $99 一次性 / Team $299 一次性
- 确认是否要调整价格
- 确认是否要改订阅制（$49/月 vs $99一次性）
- 确认是否支持中国用户购买（支付宝/微信？）

---

## 第三优先级：域名与基础设施

### 任务4：域名续费检查 ⬜ Jeam待办
- 域名：getdatacleaner.com（Namecheap）
- 检查到期时间
- 建议续费多年（$12/年）
- 检查 Cloudflare DNS 配置是否正常

### 任务5：邮箱检查 ⬜ Jeam待办
- contact@getdatacleaner.com 邮件转发是否正常
- 检查是否有用户咨询邮件未回复
- 设置邮件签名

---

## 第四优先级：推广与营销

### 任务6：ProductHunt 上架准备 ⬜ Jeam待办（等 Paddle 通了再做）
- 注册 ProductHunt 账号
- 准备 launch 文案和截图
- 选择 launch 日期（建议周二-周四）
- 联系可能的 upvoter

### 任务7：社交媒体账号 ⬜ Jeam待办
- 是否需要在 Twitter/X、LinkedIn、Reddit 上建号？
- 目标受众：开发者、DevOps、合规团队、CTO
- Reddit 相关板块：r/Python, r/devops, r/gdpr, r/selfhosted, r/LocalLLaMA

### 任务8：用户反馈收集 ⬜ Jeam待办
- 设置反馈渠道（GitHub Issues / 邮件 / Discord？）
- 考虑是否建 Discord 社区

---

## 第五优先级：法律合规

### 任务9：软件著作权 ⬜ Jeam待办（可选）
- 是否要在中国申请软件著作权？
- Source Available License 是否满足你的保护需求？

### 任务10：税务咨询 ⬜ Jeam待办
- Paddle 作为 MoR 处理了大部分税务
- 但中国公司收款仍有企业所得税
- 建议咨询：通过 Paddle 收美金到国内公司的税务处理

---

## 星辰的工作（不需要你做）

| 工作项 | 状态 |
|--------|------|
| P0: 流式大文件处理 | 执行中 |
| P1: 并行批处理 | 待排期 |
| P2: Docker 镜像 | 待排期 |
| 博客周更（2篇/周） | 本周待写 |
| 5个网站维护 | 持续 |
| 代码测试 & Review | 持续 |
| GitHub 仓库维护 | 持续 |

---

## 完成统计
- 总任务数：10
- 已完成：0
- Jeam待办：10
- 更新时间：2026-05-19（星辰创建）
