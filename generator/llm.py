"""统一的大模型调用。用环境变量 LLM_PROVIDER 切换：zhipu（默认，免费）/ deepseek / claude。"""
import base64
import json
import os
import re
import time

from common import log

PROVIDERS = {
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "key_env": "ZHIPU_API_KEY",
        "model": "glm-4.7-flash",
        "fallback_models": ["glm-4-flash-250414"],  # 也是免费模型，主模型被限流时换它
        "vision_model": "glm-4v-flash",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-flash",  # 想要更深的解读可以设 LLM_MODEL=deepseek-v4-pro（约贵 4 倍）
        "vision_model": None,  # DeepSeek 没有看图模型，看图时借用智谱（需要 ZHIPU_API_KEY）
    },
    "claude": {
        "key_env": "ANTHROPIC_API_KEY",
        "model": "claude-opus-5-5",  # 想省钱可以设 LLM_MODEL=claude-sonnet-5-5
        "vision_model": "claude-opus-5-5",
    },
}


def parse_json(text):
    """从模型输出里取出 JSON（兼容 ```json 代码块和前后多余的文字）。"""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        return None
    end = max(text.rfind("}"), text.rfind("]"))
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


class _OpenAICompatible:
    def __init__(self, cfg, key):
        from openai import OpenAI
        # 重试次数少一点：被限流时尽快换备用模型，不要干等
        self.client = OpenAI(api_key=key, base_url=cfg["base_url"], max_retries=1, timeout=300)

    def chat(self, model, system, user, image=None):
        if not image:
            return self._create(model, system, user)
        b64 = base64.b64encode(image).decode()
        try:
            return self._create(model, system, [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": user}])
        except Exception:  # 智谱的看图模型有的版本只认不带前缀的 base64
            return self._create(model, system, [
                {"type": "image_url", "image_url": {"url": b64}},
                {"type": "text", "text": user}])

    def _create(self, model, system, content):
        resp = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            temperature=0.7,
        )
        return resp.choices[0].message.content


class _Claude:
    def __init__(self, key):
        import anthropic
        self.client = anthropic.Anthropic(api_key=key, max_retries=4, timeout=600)

    def chat(self, model, system, user, image=None):
        content = [{"type": "text", "text": user}]
        if image:
            content.insert(0, {"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(image).decode()}})
        resp = self.client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("Claude 拒绝了这次请求")
        return "".join(b.text for b in resp.content if b.type == "text")


class LLM:
    def __init__(self, dry=False):
        self.dry = dry
        self.provider = os.environ.get("LLM_PROVIDER", "zhipu")
        cfg = PROVIDERS[self.provider]
        self.model = os.environ.get("LLM_MODEL") or cfg["model"]
        self.fallback_models = [] if os.environ.get("LLM_MODEL") else cfg.get("fallback_models", [])
        self.vision_model = os.environ.get("VISION_MODEL") or cfg["vision_model"]
        self.text_client = self.vision_client = None
        if dry:
            return
        key = os.environ.get(cfg["key_env"])
        if not key:
            raise RuntimeError(f"缺少环境变量 {cfg['key_env']}")
        self.text_client = _Claude(key) if self.provider == "claude" else _OpenAICompatible(cfg, key)
        self.vision_client = self.text_client
        if not self.vision_model and os.environ.get("ZHIPU_API_KEY"):
            self.vision_model = PROVIDERS["zhipu"]["vision_model"]
            self.vision_client = _OpenAICompatible(PROVIDERS["zhipu"], os.environ["ZHIPU_API_KEY"])

    @property
    def can_see(self):
        return self.dry or bool(self.vision_model)

    def json(self, system, user, fake=None, image=None):
        """调用模型并返回解析好的 JSON；不合法就重试一次。image 是 JPEG 字节。dry 模式直接返回 fake。"""
        if self.dry:
            return fake
        client, model = self.text_client, self.model
        if image:
            if not self.vision_model:
                raise RuntimeError("当前设置没有看图模型")
            client, model = self.vision_client, self.vision_model
        models = [model] if image else [model, *self.fallback_models]
        prompt = user
        for _ in range(2):
            data = parse_json(self._chat_with_fallback(client, models, system, prompt, image))
            if data is not None:
                return data
            prompt = user + "\n\n注意：上一次的输出不是合法 JSON。这次只输出 JSON，不要任何其他文字。"
        raise ValueError("模型没有返回合法 JSON")

    def _chat_with_fallback(self, client, models, system, prompt, image):
        """被限流（429）时：先换备用模型；都被限流就等一会儿再从头试，最多 3 轮。"""
        for round_ in range(3):
            for m in models:
                try:
                    return client.chat(m, system, prompt, image)
                except Exception as e:
                    if "429" not in str(e) and "RateLimit" not in type(e).__name__:
                        raise
                    log(f"  {m} 被限流，换下一个")
            time.sleep(30 * (round_ + 1))
        raise RuntimeError("所有模型都被限流")
