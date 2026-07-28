"""
🚀 CORE AGENT APP (Dành cho Role 4: Core Agent Developer)
File chính ghép nối tất cả các thành phần: Tools + Prompts + Test Cases + Multi-Provider.
"""

import argparse
import ast
import inspect
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dotenv import load_dotenv

# Đảm bảo import các module cùng thư mục src/ hoạt động mượt mà
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import các thành phần từ file của Role 2, Role 3 & Multi-Provider Adapter
from tools import AVAILABLE_TOOLS
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_SYSTEM_PROMPT,
    MAX_ITERATIONS,
    TIMEOUT_SECONDS,
)
from providers import get_llm_provider

load_dotenv()

def load_test_cases():
    """Đọc bộ test cases từ config/test_cases.json của Role 1"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    
    # Fallback kiểm tra nếu file ở thư mục hiện tại
    if not os.path.exists(config_path):
        config_path = "test_cases.json"
        
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_baseline_chatbot(user_query: str, provider, verbose: bool = True):
    """
    Chạy Chatbot Baseline bằng đúng một LLM call và không gọi công cụ.

    Returns:
        str: Phản hồi thô để Role 5 lưu và phân loại khi đánh giá.
    """
    if verbose:
        print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    
    # Gọi LLM Provider thực hiện sinh câu trả lời
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    if verbose:
        print(f"🤖 Chatbot trả lời:\n{response}")
    return response


def parse_llm_response(response: str) -> dict:
    """Parse đúng một Action hoặc Final Answer từ phản hồi của LLM."""
    raw = (response or "").strip()
    thought_match = re.search(
        r"^Thought:\s*(.*?)(?=\n(?:Action|Final Answer):|\Z)",
        raw,
        flags=re.MULTILINE | re.DOTALL,
    )
    thought = thought_match.group(1).strip() if thought_match else ""

    action_matches = re.findall(
        r"^Action:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[(.*)\]\s*$",
        raw,
        flags=re.MULTILINE,
    )
    final_match = re.search(
        r"^Final Answer:\s*(.+)\Z",
        raw,
        flags=re.MULTILINE | re.DOTALL,
    )

    if action_matches and final_match:
        return {"type": "error", "thought": thought, "error": "Phản hồi chứa cả Action và Final Answer."}
    if len(action_matches) > 1:
        return {"type": "error", "thought": thought, "error": "Mỗi bước chỉ được có một Action."}
    if final_match:
        return {
            "type": "final",
            "thought": thought,
            "answer": final_match.group(1).strip(),
        }
    if action_matches:
        tool_name, raw_args = action_matches[0]
        try:
            args = ast.literal_eval(f"[{raw_args}]") if raw_args.strip() else []
        except (SyntaxError, ValueError) as exc:
            return {
                "type": "error",
                "thought": thought,
                "error": f"Tham số Action không hợp lệ: {exc}.",
            }
        return {
            "type": "action",
            "thought": thought,
            "tool": tool_name,
            "args": args,
        }
    return {
        "type": "error",
        "thought": thought,
        "error": "Không tìm thấy Action hoặc Final Answer đúng định dạng.",
    }


def execute_tool(tool_name: str, args: list) -> tuple[str, bool]:
    """Validate rồi thực thi một tool trong registry với timeout an toàn."""
    spec = AVAILABLE_TOOLS.get(tool_name)
    if spec is None:
        valid_names = ", ".join(sorted(AVAILABLE_TOOLS))
        return f"LỖI: Tool '{tool_name}' không tồn tại. Tool hợp lệ: {valid_names}.", False

    func = spec.get("func")
    if not callable(func):
        return f"LỖI: Tool '{tool_name}' chưa được đăng ký hàm thực thi hợp lệ.", False

    try:
        inspect.signature(func).bind(*args)
    except TypeError as exc:
        return (
            f"LỖI: Sai tham số cho tool '{tool_name}': {exc}. "
            f"Cú pháp gợi ý: {spec.get('example', spec.get('args', 'không có'))}.",
            False,
        )

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func, *args)
    try:
        result = future.result(timeout=TIMEOUT_SECONDS)
        return str(result), True
    except FutureTimeoutError:
        future.cancel()
        return f"LỖI: Tool '{tool_name}' vượt timeout {TIMEOUT_SECONDS} giây.", False
    except Exception as exc:
        return f"LỖI: Tool '{tool_name}' gặp {type(exc).__name__}; vui lòng thử lại.", False
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _side_effect_allowed(user_query: str, trace: list[dict]) -> bool:
    """Chỉ cho tạo RMA khi có Observation đủ điều kiện và xác nhận rõ."""
    has_eligible_observation = any(
        "✅ ĐỦ điều kiện" in event.get("observation", "") for event in trace
    )
    normalized = user_query.lower()
    confirmation_phrases = (
        "xác nhận tạo",
        "đồng ý tạo",
        "hãy tạo yêu cầu",
        "tạo yêu cầu đổi trả",
    )
    has_confirmation = any(phrase in normalized for phrase in confirmation_phrases)
    explicitly_forbidden = "chưa tạo" in normalized or "không tạo" in normalized
    return has_eligible_observation and has_confirmation and not explicitly_forbidden


def _safe_fallback(reason: str) -> str:
    return (
        "Tôi chưa thể hoàn tất yêu cầu một cách an toàn. "
        f"{reason} Vui lòng kiểm tra lại thông tin hoặc liên hệ nhân viên CSKH."
    )


def run_react_agent(user_query: str, provider, verbose: bool = True) -> dict:
    """Chạy ReAct loop thật với parser, executor, history và guardrails."""
    if verbose:
        print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    history = [f"Question: {user_query}"]
    trace: list[dict] = []
    seen_actions: set[str] = set()
    tool_calls = 0

    for step in range(1, MAX_ITERATIONS + 1):
        if verbose:
            print(f"\n--- 🔄 Vòng lặp ReAct (Step {step}/{MAX_ITERATIONS}) ---")

        prompt = "\n\n".join(history)
        response = provider.generate(prompt, system_prompt=REACT_SYSTEM_PROMPT)

        if re.match(r"^\[(Gemini|OpenAI|Anthropic|OpenRouter).*(Error|Exception)", response or ""):
            answer = _safe_fallback("Nhà cung cấp LLM đang gặp sự cố.")
            trace.append({"step": step, "type": "provider_error", "raw_response": response})
            if verbose:
                print(f"🛡️ {answer}")
            return {
                "question": user_query,
                "status": "provider_error",
                "answer": answer,
                "iterations": step,
                "tool_calls": tool_calls,
                "guardrail_triggered": True,
                "trace": trace,
            }

        parsed = parse_llm_response(response)
        event = {
            "step": step,
            "type": parsed["type"],
            "thought": parsed.get("thought", ""),
            "raw_response": response,
        }

        if parsed["type"] == "final":
            event["answer"] = parsed["answer"]
            trace.append(event)
            if verbose:
                print(f"🧠 Thought: {parsed.get('thought') or '(không có)'}")
                print(f"🏁 Final Answer: {parsed['answer']}")
            return {
                "question": user_query,
                "status": "completed",
                "answer": parsed["answer"],
                "iterations": step,
                "tool_calls": tool_calls,
                "guardrail_triggered": False,
                "trace": trace,
            }

        if parsed["type"] == "error":
            observation = f"LỖI PARSER: {parsed['error']}"
            event["observation"] = observation
            trace.append(event)
            history.extend([response or "(phản hồi rỗng)", f"Observation: {observation}"])
            if verbose:
                print(f"⚠️ {observation}")
            continue

        tool_name = parsed["tool"]
        args = parsed["args"]
        action_signature = json.dumps([tool_name, args], ensure_ascii=False, default=str)
        event.update({"tool": tool_name, "args": args})

        if action_signature in seen_actions:
            observation = "LỖI GUARDRAIL: Action và tham số bị lặp lại mà không có dữ liệu mới."
            event.update({"type": "repeated_action", "observation": observation})
            trace.append(event)
            answer = _safe_fallback("Agent đã lặp lại cùng một hành động.")
            if verbose:
                print(f"🛡️ {observation}")
                print(f"🏁 Safe Fallback: {answer}")
            return {
                "question": user_query,
                "status": "guardrail",
                "answer": answer,
                "iterations": step,
                "tool_calls": tool_calls,
                "guardrail_triggered": True,
                "trace": trace,
            }
        seen_actions.add(action_signature)

        if tool_name == "create_return_request" and not _side_effect_allowed(user_query, trace):
            observation = (
                "LỖI: Chặn create_return_request vì chưa có cả Observation đủ điều kiện "
                "và xác nhận rõ ràng của người dùng."
            )
            executed = False
        else:
            observation, executed = execute_tool(tool_name, args)
        if executed:
            tool_calls += 1

        event["observation"] = observation
        trace.append(event)
        history.extend([response, f"Observation: {observation}"])

        if verbose:
            print(f"🧠 Thought: {parsed.get('thought') or '(không có)'}")
            print(f"🛠️ Action: {tool_name}{args}")
            print(f"👁️ Observation: {observation}")

    answer = _safe_fallback(f"Đã đạt giới hạn {MAX_ITERATIONS} vòng lặp.")
    if verbose:
        print(f"🛡️ GUARDRAIL TRIGGERED: {answer}")
    return {
        "question": user_query,
        "status": "guardrail",
        "answer": answer,
        "iterations": MAX_ITERATIONS,
        "tool_calls": tool_calls,
        "guardrail_triggered": True,
        "trace": trace,
    }


def run_cli_demo(provider=None):
    """Chạy toàn bộ Baseline và ReAct suite trong terminal."""
    print("==================================================")
    print("🏫 ĐẠI HỌC VINUNI - BÀI LAB 3: CHATBOT VS REACT AGENT")
    print("==================================================")

    # Khởi tạo Multi-Provider LLM Adapter (Đọc từ biến môi trường LLM_PROVIDER)
    provider = provider or get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(f"🔌 LLM Provider đang hoạt động: {provider.__class__.__name__} (Model: {model_name})")

    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases từ config/test_cases.json\n")

    print("--- MỐC 2: CHẠY CHATBOT BASELINE TRÊN TOÀN BỘ TEST CASE ---")
    baseline_results = []
    for test_case in tests:
        print(f"\n===== TEST CASE #{test_case['id']} — {test_case['category']} =====")
        response = run_baseline_chatbot(test_case["question"], provider)
        baseline_results.append({
            "id": test_case["id"],
            "response": response,
        })

    print("\n==================================================")
    print("📊 TỔNG KẾT CHATBOT BASELINE")
    print(f"   Test Cases đã chạy : {len(baseline_results)}")
    print(f"   Số lần gọi LLM     : {len(baseline_results)} (1 lần/test)")
    print("   Số lần gọi Tool    : 0")
    print("==================================================")

    print("\n--- MỐC 3: CHẠY REACT AGENT TRÊN TOÀN BỘ TEST CASE ---")
    agent_results = []
    for test_case in tests:
        print(f"\n===== TEST CASE #{test_case['id']} — {test_case['category']} =====")
        agent_results.append(run_react_agent(test_case["question"], provider))

    print("\n==================================================")
    print("📊 TỔNG KẾT REACT AGENT")
    print(f"   Test Cases đã chạy : {len(agent_results)}")
    print(f"   Hoàn thành          : {sum(r['status'] == 'completed' for r in agent_results)}")
    print(f"   Guardrail/Fallback  : {sum(r['guardrail_triggered'] for r in agent_results)}")
    print(f"   Tổng Tool calls     : {sum(r['tool_calls'] for r in agent_results)}")
    print("==================================================")
    return {"baseline": baseline_results, "agent": agent_results}


def create_web_app(provider=None):
    """Tạo Flask application phục vụ giao diện demo và JSON API."""
    from flask import Flask, jsonify, render_template, request

    web_app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    active_provider = provider or get_llm_provider()

    def provider_payload() -> dict:
        return {
            "name": active_provider.__class__.__name__,
            "model": getattr(active_provider, "model_name", "Offline Mock Mode"),
        }

    @web_app.get("/")
    def index():
        return render_template(
            "index.html",
            provider=provider_payload(),
            tool_count=len(AVAILABLE_TOOLS),
            max_iterations=MAX_ITERATIONS,
        )

    @web_app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "provider": provider_payload(),
            "tools": sorted(AVAILABLE_TOOLS),
            "max_iterations": MAX_ITERATIONS,
        })

    @web_app.get("/api/test-cases")
    def test_cases_api():
        return jsonify({"test_cases": load_test_cases()})

    @web_app.post("/api/chat")
    def chat_api():
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        mode = str(payload.get("mode", "agent")).strip().lower()

        if not message:
            return jsonify({"status": "error", "error": "Vui lòng nhập câu hỏi."}), 400
        if len(message) > 2000:
            return jsonify({"status": "error", "error": "Câu hỏi tối đa 2.000 ký tự."}), 400
        if mode not in {"baseline", "agent"}:
            return jsonify({"status": "error", "error": "Chế độ không hợp lệ."}), 400

        if mode == "baseline":
            answer = run_baseline_chatbot(message, active_provider, verbose=False)
            return jsonify({
                "question": message,
                "mode": mode,
                "status": "completed",
                "answer": answer,
                "iterations": 1,
                "tool_calls": 0,
                "guardrail_triggered": False,
                "trace": [],
            })

        result = run_react_agent(message, active_provider, verbose=False)
        result["mode"] = mode
        return jsonify(result)

    @web_app.post("/api/evaluate")
    def evaluate_api():
        tests = load_test_cases()
        results = []
        for test_case in tests:
            agent_result = run_react_agent(
                test_case["question"],
                active_provider,
                verbose=False,
            )
            results.append({
                "id": test_case["id"],
                "category": test_case["category"],
                "question": test_case["question"],
                "expected_behavior": test_case["expected_behavior"],
                **agent_result,
            })

        return jsonify({
            "status": "completed",
            "results": results,
            "summary": {
                "total": len(results),
                "completed": sum(item["status"] == "completed" for item in results),
                "guardrails": sum(item["guardrail_triggered"] for item in results),
                "tool_calls": sum(item["tool_calls"] for item in results),
            },
        })

    @web_app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "error": "API endpoint không tồn tại."}), 404
        return render_template("index.html", provider=provider_payload(), tool_count=len(AVAILABLE_TOOLS), max_iterations=MAX_ITERATIONS), 404

    @web_app.errorhandler(Exception)
    def unhandled_error(error):
        web_app.logger.exception("Unhandled application error", exc_info=error)
        if request.path.startswith("/api/"):
            return jsonify({
                "status": "error",
                "error": "Ứng dụng gặp sự cố. Vui lòng thử lại.",
            }), 500
        return "Ứng dụng gặp sự cố. Vui lòng tải lại trang.", 500

    return web_app


def main():
    parser = argparse.ArgumentParser(description="OrderCare — Chatbot vs ReAct Agent")
    parser.add_argument("--cli", action="store_true", help="Chạy bộ demo trong terminal")
    parser.add_argument("--host", default=os.getenv("APP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "5000")))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.cli:
        run_cli_demo()
        return

    web_app = create_web_app()
    print("==================================================")
    print("✨ OrderCare AI — Web Demo")
    print(f"🔗 Mở trình duyệt tại: http://{args.host}:{args.port}")
    print("💡 Dùng --cli nếu muốn chạy toàn bộ test trong terminal")
    print("==================================================")
    web_app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=args.debug)


if __name__ == "__main__":
    main()
