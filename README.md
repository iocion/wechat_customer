# WeChat Work AI Customer Service Bot

基于 Flask 的企业微信 AI 客服机器人，支持微信客服（KF）模式和内部应用消息模式。使用 GLM AI 提供智能对话能力。

## 功能特性

- 接收企业微信客服回调消息
- AI 智能对话（GLM Coding Plan API）
- 会话状态管理
- 技能路由系统（可扩展）
- 人工转接支持
- 多线程消息处理

## 系统架构

```
WeChat Work (企业微信)
    ↓
Callback (/callback) → 解密验证
    ↓
Handler → sync_msg 拉取消息
    ↓
Message Queue (消息队列)
    ↓
Worker Threads (2个后台线程)
    ↓
Skill Router → 技能处理 (WelcomeSkill, ChatSkill)
    ↓
Session State Management (状态管理)
    ↓
Message Sender → 发送回复
```

## 环境要求

- Python 3.13+
- Flask 3.0+
- 企业微信账号（已开通微信客服功能）
- GLM API Key

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd wechat_bot
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```bash
# 企业微信配置
CORP_ID=your_corp_id                                    # 企业ID
CORP_SECRET=your_corp_secret                            # 应用的Secret（见下方说明）
TOKEN=your_callback_token                               # 回调验证Token
ENCODING_AES_KEY=your_encoding_aes_key                 # 回调消息加密密钥
AGENT_ID=your_agent_id                                  # 应用ID

# GLM API 配置
GLM_API_KEY=your_glm_api_key                            # GLM Coding Plan API密钥
GLM_API_BASE=https://api.z.ai/api/coding/paas/v4/      # GLM API地址
GLM_MODEL=glm-4.5-flash                                # 使用的模型

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
DEBUG=false

# 消息模式：kf=微信客服模式, agent=内部应用消息模式
MESSAGE_MODE=kf

# 微信客服配置（仅 kf 模式需要）
KF_OPEN_KFID=your_kf_open_kfid                          # 客服账号ID
KF_SERVICER_USERID=                                     # 可选：转人工时的客服人员ID
```

### 5. 启动服务

```bash
python main.py
```

服务将运行在 `http://0.0.0.0:8080`

## 企业微信配置指南

### 获取企业 ID (CORP_ID)

1. 登录 [企业微信管理后台](https://work.weixin.qq.com)
2. 进入 **我的企业** → **企业信息**
3. 复制 **企业ID**

### 创建自建应用并获取配置

1. 进入 **应用管理** → **应用** → **自建**
2. 点击 **创建应用**，填写应用信息
3. 创建后记录：
   - **AgentId**（应用ID）
   - **Secret**（应用密钥）

**重要**：对于微信客服功能，必须使用**在微信客服中授权的应用的 Secret**，而不是普通应用的 Secret。

### 配置微信客服

#### 1. 开通微信客服功能

1. 在管理后台进入 **微信客服**
2. 添加客服账号，记录 **OpenKfId**

#### 2. 配置 API 接收

1. 进入 **微信客服** → **API** → **可调用接口的应用**
2. 选择你的自建应用授权
3. **必须使用此应用的 Secret** 作为 `CORP_SECRET`

#### 3. 配置回调 URL

1. 进入 **微信客服** → **API** → **接收消息与事件**
2. 配置回调 URL：`https://your-domain.com/callback`
3. 设置 **Token** 和 **EncodingAESKey**（需要与 `.env` 中一致）
4. 配置 **IP 白名单**，添加你的服务器公网 IP

#### 4. 配置接待方式

**重要**：确保接待方式设置为智能客服可以接管：

- 进入 **微信客服** → **账号管理** → **你的客服账号**
- 查看 **接待方式** 设置
- 推荐设置为 **"智能客服优先"** 或确保新会话默认进入 state 0（未处理）

如果使用 API 管理模式，新会话会由代码自动转换到智能助手接待状态（state 1）。

#### 5. 添加客服人员（可选）

如果需要支持转人工功能：

```python
# 可以通过 API 添加
from wecom.kf_client import KfClient

kf_client.add_servicer(
    open_kfid="your_open_kfid",
    userid_list=["user_id_1", "user_id_2"]
)
```

或在后台手动添加。

### 配置 GLM API

1. 获取 GLM Coding Plan API Key
2. 在 `.env` 中配置 `GLM_API_KEY`

## 消息模式说明

### kf 模式（微信客服模式）

- 用于外部客户咨询
- 需要配置 `KF_OPEN_KFID`
- 支持会话状态管理
- 支持转人工功能

### agent 模式（内部应用消息模式）

- 用于企业内部员工沟通
- 需要配置 `AGENT_ID`
- 通过应用消息接口发送

## 开发指南

### 添加新技能

1. 创建新技能类，继承 `BaseSkill`：

```python
from skills.base import BaseSkill, SkillResponse

class MySkill(BaseSkill):
    @property
    def name(self) -> str:
        return "my_skill"

    @property
    def description(self) -> str:
        return "我的技能描述"

    @property
    def priority(self) -> int:
        return 10  # 数值越大优先级越高

    def can_handle(self, message: dict, session: Session) -> bool:
        # 判断是否由该技能处理
        return True

    def handle(self, message: dict, session: Session) -> SkillResponse:
        # 处理消息并返回响应
        return SkillResponse(text="回复内容")
```

2. 在 `main.py` 中注册：

```python
router.register(MySkill())
```

### 微信客服状态机

会话状态转换规则：

| 状态 | 名称 | 可转换到 | 说明 |
|------|------|----------|------|
| 0 | 未处理 | 1, 2, 3 | 新消息初始状态 |
| 1 | 智能助手接待 | 2, 3, 4 | AI 可以回复 |
| 2 | 待接入池 | 3 | 等待人工，不可转回 1 |
| 3 | 由人工接待 | 3, 4 | 人工处理中 |
| 4 | 已结束 | 无 | 会话结束 |

常见错误码：
- **95016**: 不允许的状态转换（如 2→1, 3→1, 4→1）
- **95018**: 在无效状态下发送消息（非 state 1 或 3）
- **60020**: IP 地址不在白名单中

## 日志

日志会输出到控制台，包含：
- 消息接收日志
- 技能路由日志
- 会话状态变化
- API 调用日志
- 错误日志

## 常见问题

### 1. 收到消息但无回复

检查会话状态：
```bash
# 日志中查看
Session state for xxx: 2
```

- State 2: 会话在人工队列，需要人工处理或等待重置
- State 4: 会话已结束，用户需要发送新消息

### 2. IP 白名单错误 (60020)

在微信客服后台配置 IP 白名单，添加服务器公网 IP。

### 3. 回调验证失败

检查 `.env` 中的 `TOKEN` 和 `ENCODING_AES_KEY` 是否与后台配置一致。

### 4. 获取不到消息

- 确认使用的是授权应用的 Secret
- 检查 IP 白名单配置
- 确认回调 URL 可访问

## 生产部署建议

1. 使用 WSGI 服务器（如 Gunicorn）代替 Flask 开发服务器：
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 main:application
```

2. 使用进程管理器（如 Supervisor）管理服务

3. 配置反向代理（如 Nginx）

4. 启用日志记录到文件

5. 配置监控和告警

## 许可证

MIT License
