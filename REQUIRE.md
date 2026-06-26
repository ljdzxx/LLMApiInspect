## 配置项：

### 全局配置：

监控间隔(分钟)

监控窗口(小时) - 状态图展示从当前时间开始往前推多少个小时

请求超时时间(毫秒)

### 监控对象配置

监控对象数组：
--
监控对象标题
监控对象副标题(可选)
监控对象基地址 - 如https://domain.com
API KEY - 如sk-xxx
API接口协议[
OpenAI (/v1/chat/completions)
OpenAI-Response (/v1/responses)
Anthropic (/v1/messages)
Gemini (/v1beta/models/{model}:generateContent)
]
--

是否启用 - true/false

## 描述

根据以上配置项，按设定的时间间隔自动发送流式API请求，请求内容固定为：ping. Reply with the single word: pong，按返回的首字计算延迟时间(毫秒)，最后展示在前端页面上。

## 系统环境

数据库：sqlite

----
以上需求，请先评估，告诉我你的方案，待我拍板后再动手实施。
