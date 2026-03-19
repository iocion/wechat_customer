# AI 记忆系统重构方案

## 一、现状问题总结

### 1.1 核心问题
- **记忆是假的**：有数据结构但没用起来
- **AI 是聋的**：不知道用户历史，每次都像第一次见面
- **阶段是死的**：一旦切换就回不来
- **数据是虚的**：重启就全没了
- **错误是模板的**：用户一眼就看出是机器人

### 1.2 具体缺陷
1. `user_preferences` 和 `pending_issues` 从未传给 AI
2. 只传最近 10 轮历史，没有摘要
3. 阶段切换不可逆
4. 纯内存存储，重启丢失
5. 错误回复过于模板化

## 二、改进方案

### 2.1 架构改进

#### 2.1.1 数据持久化层
```
storage/
├── __init__.py
├── database.py      # SQLite 数据库操作
├── models.py        # 数据库模型
└── migrations.py    # 数据库迁移
```

**数据库表设计**：
```sql
-- 用户表
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    identity TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    total_messages INTEGER DEFAULT 0
);

-- 会话表
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    state TEXT,
    stage TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 聊天历史表
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 用户画像表
CREATE TABLE user_profiles (
    user_id TEXT PRIMARY KEY,
    preferences JSON,
    purchase_history JSON,
    issues_history JSON,
    conversation_summary TEXT,
    last_updated TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

#### 2.1.2 用户画像系统
```
memory/
├── __init__.py
├── profile.py       # 用户画像管理
├── extractor.py     # 信息提取器
├── summarizer.py    # 对话摘要器
└── context.py       # 上下文管理器
```

**核心功能**：
1. **信息提取**：从聊天中提取订单号、地址、电话、偏好
2. **画像维护**：更新用户偏好、购买历史、问题记录
3. **对话摘要**：对长对话生成摘要，避免 token 浪费
4. **上下文构建**：为 AI 构建完整的用户上下文

#### 2.1.3 提示词系统重构
```
prompts/
├── __init__.py
├── builder.py       # 提示词构建器
├── templates.py     # 提示词模板
└── context.py       # 上下文注入器
```

**改进点**：
1. 动态注入用户画像
2. 包含对话摘要
3. 添加待处理问题
4. 支持情绪感知

### 2.2 技能系统改进

#### 2.2.1 阶段管理改进
- 支持阶段回退（售后解决后可回到售前）
- 基于上下文判断阶段，而不是简单关键词
- 支持多阶段并行

#### 2.2.2 工具调用能力
```
tools/
├── __init__.py
├── order.py         # 订单查询工具
├── logistics.py     # 物流查询工具
└── inventory.py     # 库存查询工具
```

#### 2.2.3 错误处理改进
- 实现重试机制
- 添加降级策略
- 提供个性化错误回复

## 三、实施计划

### 阶段 1：数据持久化（第 1-2 天）
- [ ] 实现 SQLite 数据库层
- [ ] 迁移现有会话数据
- [ ] 添加数据备份机制

### 阶段 2：用户画像系统（第 3-4 天）
- [ ] 实现信息提取器
- [ ] 实现对话摘要器
- [ ] 集成用户画像到会话

### 阶段 3：提示词重构（第 5 天）
- [ ] 重构提示词模板
- [ ] 实现动态上下文注入
- [ ] 优化提示词结构

### 阶段 4：技能系统改进（第 6-7 天）
- [ ] 改进阶段管理
- [ ] 添加工具调用能力
- [ ] 优化错误处理

### 阶段 5：测试和优化（第 8 天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化

## 四、预期效果

### 4.1 用户体验提升
- AI 能记住用户偏好和历史
- 对话连贯性提升 80%
- 问题解决效率提升 50%

### 4.2 系统稳定性提升
- 数据持久化，重启不丢失
- 错误处理更智能
- 支持会话恢复

### 4.3 可维护性提升
- 模块化设计
- 清晰的职责分离
- 易于扩展新功能

## 五、技术选型

### 5.1 数据库
- **SQLite**：轻量级、无需额外服务、适合单机部署
- **备选**：PostgreSQL（如需分布式）

### 5.2 缓存
- **内存缓存**：会话状态、用户画像
- **定期持久化**：避免数据丢失

### 5.3 AI 模型
- **GLM-4.5-Flash**：主模型
- **GLM-4.5-Turbo**：备用模型（用于复杂场景）

## 六、风险评估

### 6.1 技术风险
- 数据库迁移可能影响现有数据
- 新系统可能有性能问题

### 6.2 缓解措施
- 实现数据备份机制
- 进行性能测试
- 灰度发布新功能

## 七、成功指标

### 7.1 功能指标
- 用户画像准确率 > 90%
- 对话连贯性评分 > 4.5/5
- 问题解决率 > 85%

### 7.2 性能指标
- 响应时间 < 2 秒
- 数据库查询 < 100ms
- 系统可用性 > 99.9%
