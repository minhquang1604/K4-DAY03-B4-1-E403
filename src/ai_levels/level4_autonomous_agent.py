"""Cấp độ 4: Autonomous OrderCare Agent với Planning và Working Memory.

Module này giữ logic bonus độc lập với Flask để có thể kiểm thử trực tiếp.
Agent tạo kế hoạch theo mục tiêu, cập nhật kế hoạch sau Observation, đọc lại
Working Memory và tự đánh giá mức độ hoàn thành. Mọi tool vẫn đi qua executor
có validation/timeout của ứng dụng chính.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable


ToolExecutor = Callable[[str, list], tuple[str, bool]]
MAX_AUTONOMOUS_STEPS = 5


class AutonomousOrderCareAgent:
    """Agent tự chủ deterministic cho demo Planning + Memory của OrderCare."""

    def __init__(
        self,
        goal: str,
        tool_executor: ToolExecutor,
        max_steps: int = MAX_AUTONOMOUS_STEPS,
    ) -> None:
        self.goal = (goal or "").strip()
        self.tool_executor = tool_executor
        self.max_steps = max(1, min(int(max_steps), MAX_AUTONOMOUS_STEPS))
        self.order_id = self._extract_order_id(self.goal)
        self.intent = self._detect_intent(self.goal)
        self.plan: list[dict] = []
        self.memory: list[dict] = []
        self.tool_calls = 0
        self.guardrail_triggered = False

    @staticmethod
    def _extract_order_id(goal: str) -> str:
        match = re.search(r"\bDH\s*[-_]?\s*(\d{3})\b", goal or "", flags=re.IGNORECASE)
        return f"DH{match.group(1)}" if match else ""

    @staticmethod
    def _detect_intent(goal: str) -> str:
        normalized = unicodedata.normalize("NFD", (goal or "").lower())
        folded = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        folded = folded.replace("đ", "d")
        return_terms = ("doi tra", "tra hang", "hoan tien", "rma", "du dieu kien")
        delivery_terms = ("giao hang", "van chuyen", "dang o dau", "khi nao giao", "theo doi")
        if any(term in folded for term in return_terms):
            return "return"
        if any(term in folded for term in delivery_terms):
            return "delivery"
        return "overview"

    def _new_step(self, title: str, description: str, kind: str) -> dict:
        return {
            "id": len(self.plan) + 1,
            "title": title,
            "description": description,
            "kind": kind,
            "status": "pending",
            "action": "",
            "observation": "",
            "memory_reads": [],
        }

    def build_plan(self) -> list[dict]:
        """Tạo kế hoạch cấp cao theo intent trước khi thực thi tool."""
        if self.intent == "return":
            steps = (
                ("Xác minh đơn hàng", "Tra cứu dữ liệu thật và không tin dữ kiện người dùng tự khai.", "tool"),
                ("Rút trích dữ liệu", "Đọc trạng thái và SKU từ Working Memory để chọn bước kế tiếp.", "memory"),
                ("Đánh giá đổi trả", "Dùng order_id và SKU trong Memory để kiểm tra eligibility.", "tool"),
                ("Kiểm soát side effect", "Chỉ tạo RMA khi đủ điều kiện, có lý do và xác nhận rõ.", "guardrail"),
                ("Goal evaluation", "Tự đánh giá mục tiêu và quyết định hoàn tất hay chờ người dùng.", "evaluation"),
            )
        elif self.intent == "delivery":
            steps = (
                ("Xác minh đơn hàng", "Tra cứu trạng thái và dữ liệu vận chuyển từ nguồn thật.", "tool"),
                ("Đọc Working Memory", "Dùng order_id và trạng thái vừa lưu để chọn nhánh theo dõi.", "memory"),
                ("Theo dõi giao nhận", "Gọi tool vận chuyển bằng dữ liệu đã đọc từ Memory.", "tool"),
                ("Goal evaluation", "Tổng hợp bằng chứng và tự đánh giá mức độ hoàn thành.", "evaluation"),
            )
        else:
            steps = (
                ("Xác minh đơn hàng", "Tra cứu dữ liệu thật cho mã đơn trong mục tiêu.", "tool"),
                ("Lập kế hoạch thích nghi", "Đọc trạng thái từ Memory để tự chọn nhánh phù hợp.", "memory"),
                ("Goal evaluation", "Đánh giá kết quả và đề xuất hành động tiếp theo.", "evaluation"),
            )

        self.plan = []
        for step in steps[: self.max_steps]:
            self.plan.append(self._new_step(*step))
        return self.plan

    def _remember(self, step: int, key: str, value, source: str) -> None:
        self.memory.append({
            "id": len(self.memory) + 1,
            "step": step,
            "key": key,
            "value": value,
            "source": source,
        })

    def _read_memory(self, key: str, default=None):
        for item in reversed(self.memory):
            if item["key"] == key:
                return item["value"]
        return default

    def _finish_step(
        self,
        step_number: int,
        action: str,
        observation: str,
        *,
        status: str = "completed",
        memory_reads: list[str] | None = None,
    ) -> None:
        step = self.plan[step_number - 1]
        step.update({
            "status": status,
            "action": action,
            "observation": observation,
            "memory_reads": memory_reads or [],
        })

    def _skip_remaining(self, after_step: int, reason: str) -> None:
        for step in self.plan[after_step:]:
            if step["status"] == "pending":
                step.update({
                    "status": "skipped",
                    "action": "STOP_SAFE",
                    "observation": reason,
                })

    def _call_tool(self, step_number: int, tool_name: str, args: list) -> tuple[str, bool]:
        observation, executed = self.tool_executor(tool_name, args)
        if executed:
            self.tool_calls += 1
        action_args = ", ".join(repr(arg) for arg in args)
        self._finish_step(step_number, f"{tool_name}[{action_args}]", observation)
        self._remember(step_number, f"{tool_name}_observation", observation, tool_name)
        return observation, executed

    def _hydrate_order_memory(self, observation: str) -> None:
        status_match = re.search(r"^\s*Trạng thái:\s*(.+)$", observation, flags=re.MULTILINE)
        sku_list = re.findall(r"SKU:\s*([A-Z0-9-]+)", observation)
        self._remember(1, "order_id", self.order_id, "goal_parser")
        self._remember(
            1,
            "order_status",
            status_match.group(1).strip() if status_match else "Không xác định",
            "lookup_order",
        )
        self._remember(1, "sku_list", sku_list, "lookup_order")

    def _lookup_or_block(self) -> str | None:
        if not self.order_id:
            reason = "Mục tiêu chưa có mã đơn định dạng DHxxx."
            self._finish_step(1, "REQUEST_INPUT['order_id']", reason, status="blocked")
            self._remember(1, "missing_input", "order_id", "goal_validator")
            self._skip_remaining(1, reason)
            self.guardrail_triggered = True
            return reason

        observation, _ = self._call_tool(1, "lookup_order", [self.order_id])
        if observation.startswith("LỖI:"):
            reason = "Không thể lập kế hoạch tiếp vì đơn hàng chưa được xác minh."
            self.plan[0]["status"] = "blocked"
            self._skip_remaining(1, reason)
            self.guardrail_triggered = True
            return reason

        self._hydrate_order_memory(observation)
        return None

    def _has_creation_authorization(self) -> bool:
        normalized = unicodedata.normalize("NFD", self.goal.lower())
        folded = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        folded = folded.replace("đ", "d")
        forbidden = any(term in folded for term in ("chua tao", "khong tao", "dung tao"))
        confirmation = any(term in folded for term in (
            "xac nhan tao",
            "dong y tao",
            "hay tao yeu cau",
            "tao yeu cau doi tra",
        ))
        return confirmation and not forbidden

    def _extract_reason(self) -> str:
        match = re.search(
            r"(?:lý do|do sản phẩm|vì sản phẩm)\s*[:\-]?\s*(.{5,100})",
            self.goal,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip(" .") if match else ""

    def _execute_return_plan(self) -> tuple[str, dict]:
        status = self._read_memory("order_status", "Không xác định")
        sku_list = self._read_memory("sku_list", [])
        selected_sku = sku_list[0] if sku_list else ""
        self._remember(2, "selected_sku", selected_sku, "memory_reasoner")
        memory_note = (
            f"Đã đọc Memory: order_status='{status}', sku_list={sku_list}. "
            f"Chọn SKU '{selected_sku}' cho bước eligibility."
        )
        self._finish_step(
            2,
            "READ_MEMORY['order_status', 'sku_list']",
            memory_note,
            memory_reads=["order_status", "sku_list"],
        )

        if not selected_sku:
            reason = "Không tìm thấy SKU hợp lệ trong Working Memory."
            self.plan[1]["status"] = "blocked"
            self._skip_remaining(2, reason)
            self.guardrail_triggered = True
            return _safe_bonus_answer(reason), self._evaluation(35, "blocked", reason)

        eligibility, _ = self._call_tool(
            3,
            "check_return_eligibility",
            [self._read_memory("order_id"), self._read_memory("selected_sku")],
        )
        is_eligible = eligibility.startswith("✅ ĐỦ")
        self._remember(3, "return_eligible", is_eligible, "check_return_eligibility")

        authorized = self._has_creation_authorization()
        reason = self._extract_reason()
        created_observation = ""

        if not is_eligible:
            guard_note = "Không gọi create_return_request vì eligibility không đạt."
            self._finish_step(
                4,
                "BLOCK_SIDE_EFFECT['not_eligible']",
                guard_note,
                memory_reads=["return_eligible"],
            )
            self.guardrail_triggered = True
        elif not authorized:
            guard_note = (
                "Đã đọc Memory: return_eligible=True. Agent dừng trước side effect vì "
                "người dùng chưa xác nhận tạo RMA hoặc đã yêu cầu chưa tạo."
            )
            self._finish_step(
                4,
                "BLOCK_SIDE_EFFECT['missing_confirmation']",
                guard_note,
                memory_reads=["return_eligible"],
            )
            self._remember(4, "next_required_input", "Xác nhận tạo RMA và lý do cụ thể", "guardrail")
            self.guardrail_triggered = True
        elif len(reason) < 5:
            guard_note = "Đã có xác nhận nhưng chưa có lý do đổi trả tối thiểu 5 ký tự."
            self._finish_step(
                4,
                "BLOCK_SIDE_EFFECT['missing_reason']",
                guard_note,
                status="blocked",
                memory_reads=["return_eligible"],
            )
            self._remember(4, "next_required_input", "Lý do đổi trả tối thiểu 5 ký tự", "guardrail")
            self.guardrail_triggered = True
        else:
            created_observation, _ = self._call_tool(
                4,
                "create_return_request",
                [self.order_id, selected_sku, reason],
            )
            self.plan[3]["memory_reads"] = ["order_id", "selected_sku", "return_eligible"]
            self._remember(4, "rma_result", created_observation, "create_return_request")

        if is_eligible and not authorized:
            evaluation = self._evaluation(
                100,
                "completed_safe",
                "Đã đánh giá đủ điều kiện và chủ động dừng trước side effect theo mục tiêu.",
            )
            answer = (
                f"Đã hoàn thành kế hoạch cho {self.order_id}: sản phẩm {selected_sku} đủ điều kiện "
                "đổi trả. Tôi đã lưu kết quả vào Working Memory và chưa tạo RMA vì chưa có xác "
                "nhận rõ ràng."
            )
        elif is_eligible and authorized and len(reason) < 5:
            evaluation = self._evaluation(85, "awaiting_input", "Cần bổ sung lý do đổi trả cụ thể.")
            answer = _safe_bonus_answer("Bạn đã xác nhận tạo RMA nhưng chưa cung cấp lý do đủ rõ.")
        elif is_eligible and created_observation.startswith("✅"):
            evaluation = self._evaluation(100, "completed", "RMA được tạo sau đủ ba điều kiện an toàn.")
            answer = created_observation
        elif is_eligible:
            evaluation = self._evaluation(80, "blocked", "Tool tạo RMA không hoàn tất an toàn.")
            answer = _safe_bonus_answer(created_observation or "Không tạo được yêu cầu đổi trả.")
        else:
            evaluation = self._evaluation(100, "completed_safe", "Đã xác minh sản phẩm không đủ điều kiện.")
            answer = f"Đã hoàn thành đánh giá cho {self.order_id}. {eligibility}"

        self._finish_evaluation_step(evaluation)
        return answer, evaluation

    def _execute_delivery_plan(self) -> tuple[str, dict]:
        status = self._read_memory("order_status", "Không xác định")
        memory_note = (
            f"Đã đọc Memory: order_id='{self.order_id}', order_status='{status}'. "
            "Chọn nhánh track_delivery."
        )
        self._finish_step(
            2,
            "READ_MEMORY['order_id', 'order_status']",
            memory_note,
            memory_reads=["order_id", "order_status"],
        )
        delivery, _ = self._call_tool(3, "track_delivery", [self._read_memory("order_id")])
        self.plan[2]["memory_reads"] = ["order_id"]
        evaluation = self._evaluation(100, "completed", "Đã xác minh và theo dõi vận chuyển bằng dữ liệu thật.")
        self._finish_evaluation_step(evaluation)
        return f"Đã hoàn thành kế hoạch theo dõi {self.order_id}. {delivery}", evaluation

    def _execute_overview_plan(self) -> tuple[str, dict]:
        status = self._read_memory("order_status", "Không xác định")
        sku_list = self._read_memory("sku_list", [])
        if status == "Đang vận chuyển":
            observation, executed = self.tool_executor("track_delivery", [self.order_id])
            if executed:
                self.tool_calls += 1
            action = f"track_delivery['{self.order_id}']"
            branch = "delivery"
        elif status == "Đã giao" and sku_list:
            observation, executed = self.tool_executor("check_return_eligibility", [self.order_id, sku_list[0]])
            if executed:
                self.tool_calls += 1
            action = f"check_return_eligibility['{self.order_id}', '{sku_list[0]}']"
            branch = "return_eligibility"
        else:
            observation = f"Trạng thái '{status}' chưa cần gọi thêm tool; đề xuất tiếp tục theo dõi."
            action = "NO_EXTRA_TOOL"
            branch = "monitor"
        self._finish_step(
            2,
            action,
            f"Memory chọn nhánh '{branch}'. {observation}",
            memory_reads=["order_status", "sku_list"],
        )
        self._remember(2, "adaptive_branch", branch, "memory_reasoner")
        self._remember(2, "adaptive_observation", observation, action.split("[")[0])
        evaluation = self._evaluation(100, "completed", f"Đã tự chọn nhánh {branch} từ Working Memory.")
        self._finish_evaluation_step(evaluation)
        return f"Đã hoàn thành tổng quan tự chủ cho {self.order_id}. {observation}", evaluation

    def _evaluation(self, progress: int, outcome: str, reason: str) -> dict:
        return {
            "progress": progress,
            "outcome": outcome,
            "reason": reason,
            "criteria": [
                {"label": "Generated plan", "passed": bool(self.plan)},
                {"label": "Grounded by tools", "passed": self.tool_calls > 0},
                {"label": "Memory reused", "passed": any(step.get("memory_reads") for step in self.plan)},
                {"label": "Safe termination", "passed": outcome not in {"running", "error"}},
            ],
        }

    def _finish_evaluation_step(self, evaluation: dict) -> None:
        step_number = len(self.plan)
        self._remember(step_number, "goal_progress", evaluation["progress"], "goal_evaluator")
        self._finish_step(
            step_number,
            "EVALUATE_GOAL",
            f"{evaluation['progress']}% — {evaluation['reason']}",
            memory_reads=["order_status", "goal_progress"],
        )

    def execute(self) -> dict:
        """Thực thi plan và trả payload giàu observability cho web app."""
        self.build_plan()
        blocked_reason = self._lookup_or_block()
        if blocked_reason:
            progress = 20 if self.order_id else 0
            evaluation = self._evaluation(progress, "blocked", blocked_reason)
            answer = _safe_bonus_answer(blocked_reason)
        elif self.intent == "return":
            answer, evaluation = self._execute_return_plan()
        elif self.intent == "delivery":
            answer, evaluation = self._execute_delivery_plan()
        else:
            answer, evaluation = self._execute_overview_plan()

        completed_steps = sum(step["status"] in {"completed", "blocked"} for step in self.plan)
        return {
            "goal": self.goal,
            "question": self.goal,
            "mode": "autonomous",
            "status": evaluation["outcome"],
            "answer": answer,
            "plan": self.plan,
            "memory": self.memory,
            "goal_evaluation": evaluation,
            "iterations": completed_steps,
            "tool_calls": self.tool_calls,
            "guardrail_triggered": self.guardrail_triggered,
            "trace": [],
            "memory_scope": "working_memory_current_goal",
            "planning_strategy": "intent_plan_with_adaptive_memory_branch",
        }


def _safe_bonus_answer(reason: str) -> str:
    return f"Autonomous Agent dừng an toàn. {reason} Vui lòng bổ sung dữ liệu rồi chạy lại goal."


if __name__ == "__main__":
    import os
    import sys

    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from app import execute_tool

    demo_goal = (
        "Kiểm tra toàn bộ đơn DH002, đánh giá khả năng đổi trả và chuẩn bị "
        "bước tiếp theo nhưng chưa tạo yêu cầu RMA."
    )
    result = AutonomousOrderCareAgent(demo_goal, execute_tool).execute()
    print(f"Goal: {result['goal']}")
    for item in result["plan"]:
        print(f"[{item['status'].upper()}] {item['title']} — {item['action']}")
    print(f"Memory entries: {len(result['memory'])}")
    print(f"Goal evaluation: {result['goal_evaluation']['progress']}%")
    print(f"Final Answer: {result['answer']}")
