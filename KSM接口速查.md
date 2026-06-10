# KSM 工单接口速查

本文档汇总系统对接 KSM 工单系统的全部接口，包含完整地址、请求参数与返回判断。
所有内容均依据 `feishu-python/app/ksm_client.py` 与 `feishu-python/app/handler.py` 的实际实现整理。

---

## 一、公共前提

### 1.1 地址头（Base URL）

地址头取自配置 `settings.ksm_base_url`（`.env` 中的 `KSM_BASE_URL`），后文所有接口路径前都要拼接它。

| 环境 | 地址头 |
|------|--------|
| 生产（当前 `.env` 实际配置） | `https://ierp.kingdee.com` |
| UAT | `https://ierpuat.kingdee.com` |
| SIT | `https://ierpsit.kingdee.com` |

### 1.2 鉴权与通用约定

- 所有**业务接口**调用前必须先完成三步鉴权，`access_token` 作为 URL query 参数 `?access_token={token}` 传入。
- Token 在 `ksm_client.py` 中**模块级缓存**，TTL 依据 login 返回的 `expire_time` 动态计算（提前 30 分钟失效），取不到时兜底 30 分钟。
- 业务接口返回 `errorCode=401` 且含"未经授权"，或 HTTP 403 时，自动刷新 token 重试一次。
- **HTTP 200 ≠ 业务成功**：所有业务接口必须判断返回体 `status` 字段是否为 `true`。
- `subscribeCallback` 响应较慢，超时设为 **60 秒**。

---

## 二、鉴权流程（三步）

### 步骤 1：获取 AppToken

`POST {base}/ierp/api/getAppToken.do`

| 参数 | 必填 | 说明 |
|------|------|------|
| `appId` | 是 | 应用ID（`KSM_APP_ID`） |
| `appSecuret` | 是 | 应用密钥（注意拼写 `appSecuret`，`KSM_APP_SECRET`） |
| `tenantid` | 是 | 租户ID（`KSM_TENANT_ID`，SIT 传空字符串） |
| `accountId` | 是 | 账号ID（`KSM_ACCOUNT_ID`，SIT 传空字符串） |
| `language` | 是 | 固定 `zh_CN` |

返回：`data.app_token`（嵌套结构，非顶层字段）。

### 步骤 2：获取 AccessToken

`POST {base}/ierp/api/login.do`

| 参数 | 必填 | 说明 |
|------|------|------|
| `user` | 是 | 用户名（`KSM_USER`） |
| `apptoken` | 是 | 步骤1获取的 `app_token` |
| `tenantid` | 是 | 租户ID（SIT 传空字符串） |
| `accountId` | 是 | 账号ID（SIT 传空字符串） |
| `usertype` | 是 | 固定 `UserName` |
| `language` | 是 | 固定 `zh_CN` |

返回：`data.access_token` + `data.expire_time`（毫秒时间戳，用于计算缓存有效期）。

---

## 三、获取工单内容（subscribeCallback）

> 对应代码：`ksm_client.get_order_detail()`

`POST {base}/ierp/kapi/app/open/subscribeCallback?access_token={token}`（超时 60s）

**请求参数（当前实现实际只传两个字段）：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `noticeNum` | 是 | 通知编号（来自 KSM 推送，从 NoticeStore 取最新值） |
| `subscribeNum` | 是 | 订阅类型，固定 `ksm_feedback_change` |

> 注：KSM 原始文档列出的 `appId`、`callbackUrl`、`id` 在当前实现中**未传**，仅 `noticeNum + subscribeNum` 即可拉取。

**请求示例：**
```json
{
  "noticeNum": "2411682884910966784",
  "subscribeNum": "ksm_feedback_change"
}
```

**返回 `data` 关键字段：**

| 字段 | 说明 |
|------|------|
| `billId` / `billNumber` / `title` | 工单ID / 编号 / 标题 |
| `status` | 工单状态（见枚举） |
| `urgency` / `feedbackType` | 紧急程度 / 流转类型（见枚举） |
| `problem` | 问题描述 |
| `product.id` / `module.id` / `version.id` | 产品/模块/版本ID（接管、处理接口需要） |
| `customerInfo.linkman` / `.mobile` / `.email` | 客户联系人/手机/邮箱（处理接口需要） |
| `node.id` / `node.name` | 当前节点ID / 节点名称（接管、处理、退回接口需要） |
| `handleSteps[]` | 处理步骤数组（含 `assignUser`、`opercacheId`、`handleDateTime` 等，退回接口需要） |

---

## 四、工单接管（lockKsmOrder）

> 对应代码：`ksm_client.lock_order()`。status=1（已提交）时调用，将工单接管到指定人员名下。

`POST {base}/ierp/kapi/v2/kded/kded_wos/lockKsmOrder?access_token={token}`

| 参数 | 必填 | 说明 |
|------|------|------|
| `billId` | 是 | 工单ID |
| `account` | 是 | 接管人账号（传姓名） |
| `accountName` | 是 | 接管人姓名 |
| `accountNumber` | 是 | 接管人工号（飞书员工搜索接口获取） |
| `dealOpinion` | 是 | 处理意见，固定 `"已受理，工单人员分析处理中"` |

**请求示例：**
```json
{
  "billId": "4A71071A009482FEE06314C912AC57D1",
  "account": "张三",
  "accountName": "张三",
  "accountNumber": "10086",
  "dealOpinion": "已受理，工单人员分析处理中"
}
```

返回判断：`status == true` 为成功，否则取 `message` 报错（如"工单已被接管"）。

---

## 五、工单处理（handleKsmOrder）

> 对应代码：`ksm_client.handle_order()`。接管成功并重新拉取最新详情后调用。

`POST {base}/ierp/kapi/v2/kded/kded_wos/handleKsmOrder?access_token={token}`

| 参数 | 必填 | 说明 |
|------|------|------|
| `billId` | 是 | 工单ID（接管后重新拉取的最新数据） |
| `account` | 是 | 处理人账号（传姓名） |
| `accountName` | 是 | 处理人姓名 |
| `accountNumber` | 是 | 处理人工号 |
| `linkman` | 是 | 联系人，默认取客户 `customerInfo.linkman`，无则传处理人姓名 |
| `email` | 是 | 邮箱，优先取客户 `customerInfo.email` |
| `mobile` | 是 | 手机，优先取客户 `customerInfo.mobile` |
| `productId` | 是 | 取最新详情 `product.id` |
| `versionId` | 是 | 取最新详情 `version.id` |
| `moduleId` | 是 | 取最新详情 `module.id` |
| `backType` | 是 | 流转类型，取 `feedbackType` 转字符串 |
| `isDeal` | 是 | 普通处理传空字符串 `""`；`is_deal=True` 时传 `"2"` |
| `dealOpinion` | 是 | 处理意见，固定 `"工单人员分析处理中"` |
| `dealMethod` | 否 | 处理方式，普通传空；`is_deal=True` 时传 `"指导解决"` |
| `billType` | 否 | 工单类型，普通传空；`is_deal=True` 时传 `"服务咨询"` |
| `handleInfo.currentNodeID` | 是 | 当前节点ID，取最新详情 `node.id` |
| `files` | 否 | 附件数组 `[{fileName, fileData(base64)}]` |

> ⚠️ `isDeal` 普通场景必须传空字符串，不能传 `"1"`。

返回判断：`status == true`。

---

## 六、工单退回 KSM（returnKsmOrder）

> 对应代码：`ksm_client.return_order()`，触发入口 `handler.py` 的 `/webhook/ksm/returnOrder`。

`POST {base}/ierp/kapi/v2/kded/kded_wos/returnKsmOrder?access_token={token}`

| 参数 | 必填 | 说明 |
|------|------|------|
| `billId` | 是 | 工单ID |
| `account` | 是 | 操作人账号（传姓名） |
| `accountName` | 是 | 操作人姓名 |
| `accountNumber` | 是 | 操作人工号 |
| `dealOpinion` | 是 | 退回说明（默认 `"退回"`） |
| `opercacheID` | 是 | 目标退回节点的 `opercacheId`（取值逻辑见下） |
| `currentNodeID` | 是 | 当前节点ID，取 `node.id` |
| `files` | 否 | 飞书「答复指导附件」转 base64：`[{fileName, fileData}]` |

**目标退回节点取值逻辑：**
取 `handleSteps` 中 `handleDateTime` 倒序排列、`nodeName` 非空且非 `"协同处理"` 的第一条，用其 `opercacheId`；找不到则报"未找到可退回的目标节点"。

**失败补偿逻辑：**
- 返回含「已流转至其他节点」→ 重新拉取详情后重试一次。
- 返回含「未锁定，不能直接处理」→ 先调 `lockKsmOrder` 补偿接管，再重试退回。

退回成功后：清除本地接管状态（`clear_locked`），并把操作人写入飞书「逆向操作人」字段。

返回判断：`status == true`。

---

## 七、补充资料（supplyKsmOrder）

> 对应代码：`ksm_client.supply_order()`，触发入口 `/webhook/ksm/supplyOrder`。

`POST {base}/ierp/kapi/v2/kded/kded_wos/supplyKsmOrder?access_token={token}`

| 参数 | 必填 | 说明 |
|------|------|------|
| `billId` | 是 | 工单ID |
| `account` | 是 | 处理人账号（传姓名） |
| `accountNumber` | 是 | 处理人工号 |
| `accountName` | 是 | 处理人姓名 |
| `dealOpinion` | 否 | 补充说明（最长 4000 字节） |
| `currentNodeID` | 是 | 当前节点ID，取 `node.id` |
| `files` | 否 | 附件数组 `[{fileName, fileData(base64)}]` |

返回判断：`status == true`。

---

## 八、工单拆单（splitKsmOrder）

> 对应代码：`ksm_client.split_order()`，触发入口 `/webhook/ksm/splitOrder`。

`POST {base}/ierp/kapi/v2/kded/kded_wos/splitKsmOrder?access_token={token}`

| 参数 | 必填 | 说明 |
|------|------|------|
| `billId` | 是 | 工单ID |
| `splitFeedbackNumber` | 是 | 拆单数量（2~15） |
| `account` | 是 | 处理人账号（传姓名） |
| `accountNumber` | 是 | 处理人工号 |
| `accountName` | 是 | 处理人姓名 |

返回 `data`：`sourceBillId` / `sourceBillNo` / `splitBillNoArry`（拆分后工单编号集合）。
拆单成功后父单状态自动变为"处理关闭"。

返回判断：`status == true`。

---

## 九、关于"工单关闭"

KSM **未提供独立的工单关闭接口**。工单进入"处理关闭"（status=5）/"处理完成"（status=4）均为流程流转后的结果状态，由以下操作间接触发：

- `splitKsmOrder`（拆单）成功后，父单自动变为"处理关闭"。
- `handleKsmOrder`（处理）推进节点流转，按流程走向最终状态。

如需"关闭"语义，应通过上述业务接口推进流程，而非调用单独的 close 接口。

---

## 十、附件下载（download_attachment）

> 对应代码：`ksm_client.download_attachment()`，非鉴权接口。

`GET {附件URL}`，需带 `User-Agent: Mozilla/5.0` 请求头，否则服务器拒绝。返回二进制内容。

---

## 十一、枚举值

### 工单状态（status）
| 值 | 含义 |
|----|------|
| 0 | 已保存 |
| 1 | 已提交 |
| 2 | 处理中 |
| 3 | 答复完成 |
| 4 | 处理完成 |
| 5 | 处理关闭 |
| 6 | 已退回 |

### 紧急程度（urgency）
| 值 | 含义 |
|----|------|
| -1 | 特急-致命 |
| 0 | 特急-严重 |
| 1 | 紧急 |
| 5 | 一般 |

### 流转类型（feedbackType）
| 值 | 含义 |
|----|------|
| 0 | 应用问题 |
| 1 | 数据处理支持 |
| 2 | 产品需求分析 |
| 3 | 产品程序错误分析 |
| 4 | 应用支持 |
| 5 | 环境与运维支持 |
| 6 | 紧急故障（红灯） |
| 7 | 定制开发支持 |
| 8 | 技术支持 |
| 9 | 产品性能分析 |
