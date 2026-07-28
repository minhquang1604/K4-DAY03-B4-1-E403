"""
🔌 MULTI-PROVIDER LLM ADAPTER (OpenAI, Gemini, Anthropic, OpenRouter & Offline Mock)
Hỗ trợ chuyển đổi linh hoạt giữa các nhà cung cấp AI chỉ bằng cách đổi biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho tất cả các LLM Provider"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env!"
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (GPT-4o, GPT-3.5-turbo, etc.)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env!"
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider (Claude 3.5 Sonnet, Claude 3 Haiku)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "claude-3-haiku-20240307"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_anthropic_api_key_here":
            return "[Anthropic Error]: Chưa cấu hình ANTHROPIC_API_KEY trong file .env!"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = {
                "model": self.model_name,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
                
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Anthropic Exception]: {str(e)}"


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter Provider (Hỗ trợ gọi mọi model qua OpenRouter API)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "google/gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            return "[OpenRouter Error]: Chưa cấu hình OPENROUTER_API_KEY trong file .env!"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model_name,
                "messages": messages
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[OpenRouter API Error {res.status_code}]: {res.text}"
        except Exception as e:
            return f"[OpenRouter Exception]: {str(e)}"


class MockProvider(BaseLLMProvider):
    """Provider deterministic để demo Baseline và ReAct hoàn toàn offline."""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if "bạn là ordercare — react agent" in system_prompt.lower():
            return self._generate_react(prompt)
        return self._generate_baseline(prompt)

    @staticmethod
    def _generate_baseline(prompt: str) -> str:
        text = prompt.lower()
        if "khác nhau giữa đổi hàng" in text:
            return (
                "Đổi hàng là thay sản phẩm bằng sản phẩm khác; trả hàng là gửi sản phẩm "
                "lại cho người bán; hoàn tiền là người bán trả lại khoản tiền đã thanh toán. "
                "Điều kiện cụ thể phụ thuộc chính sách của từng cửa hàng."
            )
        if "cần chuẩn bị" in text:
            return (
                "Bạn thường cần mã đơn hàng, thông tin liên hệ dùng khi đặt hàng, sản phẩm/SKU "
                "cần hỗ trợ và lý do đổi trả. Không cung cấp mật khẩu, OTP hoặc số thẻ đầy đủ."
            )
        if "bỏ qua mọi quy tắc" in text:
            return (
                "Tôi không thể giả mạo trạng thái đơn hoặc tự tạo mã đổi trả. "
                "Baseline không có quyền truy cập hệ thống để xác minh đơn hàng."
            )
        if "dh001" in text or "dh002" in text:
            return (
                "Tôi chưa thể xác minh đơn hàng cụ thể vì Chatbot Baseline không có công cụ "
                "tra cứu. Vui lòng chuyển sang ReAct Agent hoặc liên hệ nhân viên hỗ trợ."
            )
        return "Tôi chưa có đủ thông tin để trả lời chính xác."

    @staticmethod
    def _generate_react(prompt: str) -> str:
        text = prompt.lower()

        if "bỏ qua mọi quy tắc" in text and "dh999" in text:
            if "action: lookup_order" not in text:
                return (
                    "Thought: Tôi phải bỏ qua yêu cầu giả mạo và kiểm tra mã đơn bằng dữ liệu thật.\n"
                    "Action: lookup_order['DH999']"
                )
            return (
                "Thought: Observation xác nhận không có đơn DH999 nên không được tạo dữ liệu giả.\n"
                "Final Answer: Tôi không thể giả mạo trạng thái, lý do hoặc mã đổi trả. "
                "Hệ thống không tìm thấy đơn DH999; vui lòng kiểm tra lại mã đơn hoặc liên hệ CSKH."
            )

        if "dh002" in text and "sp-laptop" in text:
            if "action: lookup_order" not in text:
                return (
                    "Thought: Cần tra cứu đơn DH002 trước khi đánh giá đổi trả.\n"
                    "Action: lookup_order['DH002']"
                )
            if "action: check_return_eligibility" not in text:
                return (
                    "Thought: Đơn đã giao và có SKU SP-LAPTOP; cần kiểm tra thời hạn, điều kiện đổi trả.\n"
                    "Action: check_return_eligibility['DH002', 'SP-LAPTOP']"
                )
            return (
                "Thought: Tôi đã có đủ thông tin để trả lời.\n"
                "Final Answer: Laptop Dell XPS 13 trong đơn DH002 đã giao và còn đủ điều kiện "
                "đổi trả trong thời hạn 14 ngày. Tôi chưa tạo yêu cầu RMA vì bạn chưa xác nhận. "
                "Nếu đồng ý, hãy xác nhận rõ lý do lỗi pin để tiếp tục."
            )

        if "dh001" in text:
            if "action: lookup_order" not in text:
                return (
                    "Thought: Cần tra cứu đơn DH001 để xác minh trạng thái hiện tại.\n"
                    "Action: lookup_order['DH001']"
                )
            if "action: track_delivery" not in text:
                return (
                    "Thought: Đơn đang vận chuyển; cần lấy thông tin giao nhận chi tiết.\n"
                    "Action: track_delivery['DH001']"
                )
            return (
                "Thought: Tôi đã có đủ thông tin để trả lời.\n"
                "Final Answer: Đơn DH001 đang được GHN vận chuyển với mã GHN7891234, "
                "dự kiến giao ngày 2026-07-30."
            )

        if "khác nhau giữa đổi hàng" in text:
            return (
                "Thought: Đây là câu hỏi kiến thức chung, không cần gọi công cụ.\n"
                "Final Answer: Đổi hàng là thay sản phẩm; trả hàng là gửi sản phẩm lại; "
                "hoàn tiền là nhận lại khoản tiền đã thanh toán."
            )
        if "cần chuẩn bị" in text:
            return (
                "Thought: Đây là hướng dẫn chung, không cần gọi công cụ.\n"
                "Final Answer: Hãy chuẩn bị mã đơn, thông tin liên hệ khi đặt hàng, SKU/sản phẩm "
                "và lý do đổi trả; không cung cấp mật khẩu, OTP hoặc số thẻ đầy đủ."
            )

        return (
            "Thought: Tôi chưa có đủ dữ kiện hoặc công cụ phù hợp.\n"
            "Final Answer: Vui lòng cung cấp mã đơn hàng hợp lệ hoặc liên hệ nhân viên hỗ trợ."
        )


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """Factory function tự chọn Provider từ biến môi trường LLM_PROVIDER"""
    name = (provider_name or os.getenv("LLM_PROVIDER") or "mock").lower().strip()
    
    if name == "gemini":
        return GeminiProvider()
    elif name == "openai":
        return OpenAIProvider()
    elif name == "anthropic":
        return AnthropicProvider()
    elif name == "openrouter":
        return OpenRouterProvider()
    else:
        return MockProvider()


if __name__ == "__main__":
    print("=== TEST MULTI-PROVIDER LLM ADAPTER ===")
    provider = get_llm_provider()
    print(f"✅ Provider đang dùng: {provider.__class__.__name__}")
    print(f"🤖 User Query: Hello")
    print(f"💬 Response  : {provider.generate('Hello')}")
