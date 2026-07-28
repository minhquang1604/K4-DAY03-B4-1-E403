"""
🛠️ TOOL REGISTRY & SCHEMAS — ĐỀ TÀI: TRỢ LÝ TRA CỨU ĐƠN HÀNG & XỬ LÝ ĐỔI TRẢ
(Dành cho Role 2: Tool & Spec Engineer)

Tất cả tool dưới đây là DETERMINISTIC (chạy ngoại tuyến, không cần API thật) để
nhóm có thể so sánh công bằng giữa Chatbot baseline và ReAct Agent.

Mỗi tool tuân theo 8-câu-hỏi Tool Contract:
    Name, Purpose, Input schema, Output schema,
    Error semantics, Side effect, Example, Safety.
"""

from __future__ import annotations

# =============================================================================
# 🗄️ MOCK DATABASE (Bộ nhớ trong — deterministic, không side-effect ngoài file)
# =============================================================================
# Cấu trúc tối giản cho bài Lab. Khi triển khai thật sẽ thay bằng SQL/NoSQL.
# Lưu ý: chỉnh sửa DB ở đây cũng chấp nhận được — mục tiêu là test Agent logic.

ORDERS_DB: dict[str, dict] = {
    "DH001": {
        "order_id": "DH001",
        "customer_name": "Nguyễn Văn A",
        "items": [
            {"sku": "SP-AIRPODS", "name": "AirPods Pro 2", "qty": 1, "price": 5_990_000},
            {"sku": "SP-CABLE",   "name": "Cáp USB-C 2m",   "qty": 2, "price":   190_000},
        ],
        "total": 6_370_000,
        "status": "Đang vận chuyển",
        "carrier": "GHN",
        "tracking_number": "GHN7891234",
        "estimated_delivery": "2026-07-30",
        "delivered_at": None,
        "ordered_at": "2026-07-25",
    },
    "DH002": {
        "order_id": "DH002",
        "customer_name": "Trần Thị B",
        "items": [
            {"sku": "SP-LAPTOP", "name": "Laptop Dell XPS 13", "qty": 1, "price": 32_990_000},
        ],
        "total": 32_990_000,
        "status": "Đã giao",
        "carrier": "J&T",
        "tracking_number": "JT4567890",
        "estimated_delivery": "2026-07-26",
        "delivered_at": "2026-07-26",
        "ordered_at": "2026-07-20",
    },
    "DH003": {
        "order_id": "DH003",
        "customer_name": "Lê Văn C",
        "items": [
            {"sku": "SP-SHIRT",   "name": "Áo sơ mi trắng",   "qty": 3, "price":  450_000},
            {"sku": "SP-TROUSER", "name": "Quần tây đen",      "qty": 1, "price":  650_000},
        ],
        "total": 2_000_000,
        "status": "Đang xử lý",
        "carrier": None,
        "tracking_number": None,
        "estimated_delivery": "2026-08-02",
        "delivered_at": None,
        "ordered_at": "2026-07-27",
    },
    "DH004": {
        "order_id": "DH004",
        "customer_name": "Phạm Thị D",
        "items": [
            {"sku": "SP-PHONE", "name": "iPhone 15 Pro 256GB", "qty": 1, "price": 28_990_000},
        ],
        "total": 28_990_000,
        "status": "Đã giao",
        "carrier": "Viettel Post",
        "tracking_number": "VP1234567",
        "estimated_delivery": "2026-07-22",
        "delivered_at": "2026-06-15",  # giao cách 43 ngày trước ➔ quá hạn cả Phone (14 ngày)
        "ordered_at": "2026-06-10",
    },
    "DH005": {
        "order_id": "DH005",
        "customer_name": "Hoàng Văn E",
        "items": [
            {"sku": "SP-MOUSE", "name": "Chuột Logitech MX Master 3", "qty": 1, "price": 2_490_000},
        ],
        "total": 2_490_000,
        "status": "Đã hủy",
        "carrier": None,
        "tracking_number": None,
        "estimated_delivery": None,
        "delivered_at": None,
        "ordered_at": "2026-07-18",
    },
}

# Danh mục sản phẩm đơn giản (dùng cho trả lời "shop có bán không")
PRODUCT_CATALOG: dict[str, dict] = {
    "SP-AIRPODS":  {"name": "AirPods Pro 2",       "category": "Phụ kiện",  "in_stock": True},
    "SP-CABLE":    {"name": "Cáp USB-C 2m",         "category": "Phụ kiện",  "in_stock": True},
    "SP-LAPTOP":   {"name": "Laptop Dell XPS 13",   "category": "Laptop",    "in_stock": False},
    "SP-SHIRT":    {"name": "Áo sơ mi trắng",      "category": "Thời trang","in_stock": True},
    "SP-TROUSER":  {"name": "Quần tây đen",         "category": "Thời trang","in_stock": True},
    "SP-PHONE":    {"name": "iPhone 15 Pro 256GB",  "category": "Điện thoại","in_stock": True},
    "SP-MOUSE":    {"name": "Chuột Logitech MX Master 3", "category": "Phụ kiện", "in_stock": True},
}

# Chính sách đổi trả — deterministic theo danh mục
RETURN_POLICY: dict[str, dict] = {
    "default": {
        "window_days": 7,
        "conditions": [
            "Sản phẩm còn nguyên tem, mác, chưa qua sử dụng",
            "Còn đầy đủ phụ kiện & hộp",
            "Có hóa đơn/mã đơn hàng",
        ],
        "refund_method": "Hoàn tiền qua cổng thanh toán gốc trong 5-7 ngày làm việc",
    },
    "Laptop": {
        "window_days": 14,
        "conditions": [
            "Còn nguyên seal, chưa kích hoạt bảo hành điện tử",
            "Không trầy xước vỏ ngoài, không dấu hiệu rơi/va đập",
            "Có đầy đủ phụ kiện & hộp",
        ],
        "refund_method": "Hoàn tiền + hỗ trợ đổi mới trong 24h nếu lỗi NSX",
    },
    "Điện thoại": {
        "window_days": 14,
        "conditions": [
            "IMEI còn nguyên vẹn, chưa active iCloud/Google account khác",
            "Màn hình không trầy, không điểm chết",
            "Còn seal NSX & phụ kiện",
        ],
        "refund_method": "Hoàn tiền trong 7-10 ngày; lỗi NSX được đổi mới trong 30 ngày",
    },
    "Thời trang": {
        "window_days": 30,
        "conditions": [
            "Chưa giặt, còn tag",
            "Không có dấu hiệu đã qua sử dụng",
        ],
        "refund_method": "Hoàn tiền hoặc đổi size miễn phí 1 lần",
    },
}

# Lưu các yêu cầu đổi trả đã tạo trong session (in-memory, không persist)
_RETURN_REQUESTS: dict[str, dict] = {}


def _normalize_order_id(order_id: str) -> str:
    """Bỏ khoảng trắng, upper-case để 'dh001' và 'DH001' đều hoạt động."""
    return (order_id or "").strip().upper()


def _format_vnd(amount: int) -> str:
    """Format số tiền theo chuẩn VNĐ có dấu phân cách."""
    return f"{amount:,}".replace(",", ".") + " VNĐ"


# =============================================================================
# 🛠️ TOOL 1 — lookup_order
# =============================================================================
def lookup_order(order_id: str) -> str:
    """
    Tra cứu thông tin chi tiết của một đơn hàng theo mã đơn.

    Purpose:
        Dùng khi khách cung cấp mã đơn (DHxxx) và muốn biết trạng thái,
        danh sách sản phẩm, tổng tiền, đơn vị vận chuyển, mã tracking
        và ngày dự kiến giao.

    Input schema:
        order_id (str, required): Mã đơn hàng. Ví dụ: "DH001", "dh002".

    Output schema:
        str JSON-like:
            {
              "order_id": "DH001",
              "customer_name": "...",
              "items": [...],
              "total": 6370000,
              "status": "Đang vận chuyển",
              "carrier": "GHN",
              "tracking_number": "GHN7891234",
              "estimated_delivery": "2026-07-30",
              "delivered_at": null
            }

    Error semantics:
        - Mã rỗng / không đúng định dạng "DHxxx" ➔ trả chuỗi lỗi.
        - Mã không tồn tại trong DB ➔ trả chuỗi lỗi kèm danh sách mã hợp lệ.

    Side effect: read-only, không thay đổi DB.

    Example:
        lookup_order("DH001") ➔ "Đơn DH001 — Nguyễn Văn A — ..."
        lookup_order("DH999") ➔ "LỖI: Không tìm thấy đơn hàng 'DH999'. ..."

    Safety: try/except toàn bộ — không bao giờ raise Exception ra Agent.
    """
    try:
        oid = _normalize_order_id(order_id)
        if not oid:
            return "LỖI: Mã đơn hàng không được để trống. Ví dụ hợp lệ: DH001."

        # Validate định dạng — cho phép linh hoạt nhưng vẫn kiểm tra
        if not oid.startswith("DH") or len(oid) != 5 or not oid[2:].isdigit():
            valid_ids = ", ".join(sorted(ORDERS_DB.keys()))
            return (
                f"LỖI: Mã đơn '{order_id}' không đúng định dạng (kỳ vọng DHxxx, ví dụ DH001). "
                f"Các mã hiện có: {valid_ids}."
            )

        order = ORDERS_DB.get(oid)
        if order is None:
            valid_ids = ", ".join(sorted(ORDERS_DB.keys()))
            return f"LỖI: Không tìm thấy đơn hàng '{oid}'. Các mã hiện có: {valid_ids}."

        items_text = "\n".join(
            f"   - {it['name']} (SKU: {it['sku']}) x{it['qty']} — {_format_vnd(it['price'])}"
            for it in order["items"]
        )
        delivered = order["delivered_at"] or "Chưa giao"
        tracking = order["tracking_number"] or "Chưa có mã vận đơn"

        return (
            f"📦 Đơn {oid} — Khách hàng: {order['customer_name']}\n"
            f"   Trạng thái: {order['status']}\n"
            f"   Đơn vị vận chuyển: {order['carrier'] or 'Chưa chọn'}\n"
            f"   Mã vận đơn: {tracking}\n"
            f"   Ngày đặt: {order['ordered_at']}\n"
            f"   Dự kiến giao: {order['estimated_delivery'] or 'Chưa cập nhật'}\n"
            f"   Ngày giao thực tế: {delivered}\n"
            f"   Sản phẩm:\n{items_text}\n"
            f"   Tổng cộng: {_format_vnd(order['total'])}"
        )
    except Exception as e:
        # Không bao giờ để Exception thoát ra — Agent cần dữ liệu chuỗi để suy luận
        return f"LỖI: Hệ thống tra cứu gặp sự cố ({type(e).__name__}). Vui lòng thử lại."


# =============================================================================
# 🛠️ TOOL 2 — check_return_eligibility
# =============================================================================
def check_return_eligibility(order_id: str, sku: str) -> str:
    """
    Kiểm tra đơn hàng + sản phẩm cụ thể có đủ điều kiện đổi trả hay không.

    Purpose:
        Trước khi tạo yêu cầu đổi trả, Agent/người dùng cần biết đơn đã giao
        chưa, còn trong thời hạn đổi trả không, sản phẩm có thuộc đơn không.

    Input schema:
        order_id (str, required): Mã đơn. Vd: "DH002".
        sku      (str, required): Mã SKU sản phẩm trong đơn. Vd: "SP-LAPTOP".

    Output schema:
        Chuỗi mô tả: có/không đủ điều kiện + lý do cụ thể
        (ví dụ: "Đủ điều kiện — Còn 4 ngày trong thời hạn đổi trả 14 ngày"
         hoặc "KHÔNG đủ điều kiện — Đơn đã giao 10 ngày trước, quá thời hạn 7 ngày").

    Error semantics:
        - order_id sai định dạng hoặc không tồn tại ➔ chuỗi lỗi.
        - sku không thuộc order ➔ chuỗi lỗi liệt kê SKU hợp lệ.
        - Đơn chưa giao ➔ KHÔNG đủ điều kiện với lý do "chưa giao".

    Side effect: read-only.

    Example:
        check_return_eligibility("DH002", "SP-LAPTOP") ➔ laptop giao 26/07, hôm nay 28/07 ➔ còn 12 ngày
        check_return_eligibility("DH004", "SP-PHONE")   ➔ giao 22/07, hết hạn 14 ngày ➔ KHÔNG đủ

    Safety: try/except toàn bộ.
    """
    from datetime import date, datetime

    try:
        oid = _normalize_order_id(order_id)
        if not oid:
            return "LỖI: Thiếu mã đơn hàng."
        sku_norm = (sku or "").strip().upper()
        if not sku_norm:
            return "LỖI: Thiếu mã SKU sản phẩm."

        order = ORDERS_DB.get(oid)
        if order is None:
            return f"LỖI: Không tìm thấy đơn '{oid}'. Kiểm tra lại mã đơn."

        # Tìm SKU trong đơn
        item = next((it for it in order["items"] if it["sku"].upper() == sku_norm), None)
        if item is None:
            valid_skus = ", ".join(it["sku"] for it in order["items"]) or "(đơn trống)"
            return f"LỖI: SKU '{sku}' không thuộc đơn {oid}. SKU hợp lệ trong đơn: {valid_skus}."

        # Phải đã giao mới đổi trả được
        delivered_at_raw = order.get("delivered_at")
        if not delivered_at_raw:
            return (
                f"❌ KHÔNG đủ điều kiện đổi trả: Đơn {oid} chưa được giao "
                f"(trạng thái hiện tại: {order['status']})."
            )

        delivered_at = datetime.strptime(delivered_at_raw, "%Y-%m-%d").date()
        product_info = PRODUCT_CATALOG.get(item["sku"], {})
        category = product_info.get("category", "default")
        policy = RETURN_POLICY.get(category, RETURN_POLICY["default"])
        window = policy["window_days"]

        today = date(2026, 7, 28)  # deterministic cho bài Lab
        days_since = (today - delivered_at).days
        days_remaining = window - days_since

        if days_remaining < 0:
            return (
                f"❌ KHÔNG đủ điều kiện: Sản phẩm '{item['name']}' (đơn {oid}) đã giao "
                f"{days_since} ngày trước — quá thời hạn đổi trả {window} ngày "
                f"(danh mục: {category})."
            )

        conditions_text = "; ".join(policy["conditions"])
        return (
            f"✅ ĐỦ điều kiện đổi trả:\n"
            f"   - Sản phẩm: {item['name']} (SKU {item['sku']})\n"
            f"   - Đơn: {oid}\n"
            f"   - Ngày giao: {delivered_at_raw} (đã {days_since} ngày)\n"
            f"   - Còn lại: {days_remaining} ngày trong thời hạn {window} ngày\n"
            f"   - Danh mục: {category}\n"
            f"   - Điều kiện: {conditions_text}\n"
            f"   - Hoàn tiền: {policy['refund_method']}"
        )
    except Exception as e:
        return f"LỖI: Không kiểm tra được điều kiện đổi trả ({type(e).__name__})."


# =============================================================================
# 🛠️ TOOL 3 — get_return_policy
# =============================================================================
def get_return_policy(category: str = "default") -> str:
    """
    Lấy chính sách đổi trả theo danh mục sản phẩm.

    Purpose:
        Khi khách hỏi chung chung "shop có đổi trả không / thời hạn bao lâu"
        mà chưa cung cấp mã đơn cụ thể ➔ trả policy theo category.

    Input schema:
        category (str, optional): Một trong ["Laptop", "Điện thoại", "Thời trang",
                                          "Phụ kiện", "default"].
                                  Mặc định: "default" (chính sách chung).

    Output schema:
        Chuỗi mô tả: window_days + điều kiện + phương thức hoàn tiền.

    Error semantics:
        - category lạ ➔ fallback về "default" kèm gợi ý category hợp lệ.

    Side effect: read-only.

    Example:
        get_return_policy("Laptop")   ➔ 14 ngày + điều kiện seal còn nguyên
        get_return_policy("xyz")      ➔ chính sách default + gợi ý

    Safety: try/except.
    """
    try:
        valid = ["Laptop", "Điện thoại", "Thời trang", "Phụ kiện", "default"]
        cat = (category or "default").strip()
        # Chuẩn hóa capitalization
        for v in valid:
            if cat.lower() == v.lower():
                cat = v
                break
        else:
            return (
                f"LỖI: Danh mục '{category}' không tồn tại. "
                f"Các danh mục hợp lệ: {', '.join(valid)}."
            )

        policy = RETURN_POLICY.get(cat, RETURN_POLICY["default"])
        conditions = "\n".join(f"   • {c}" for c in policy["conditions"])
        return (
            f"📋 Chính sách đổi trả — Danh mục: {cat}\n"
            f"   ⏳ Thời hạn: {policy['window_days']} ngày kể từ ngày giao\n"
            f"   📌 Điều kiện:\n{conditions}\n"
            f"   💰 Hoàn tiền: {policy['refund_method']}"
        )
    except Exception as e:
        return f"LỖI: Không đọc được chính sách đổi trả ({type(e).__name__})."


# =============================================================================
# 🛠️ TOOL 4 — create_return_request
# =============================================================================
def create_return_request(order_id: str, sku: str, reason: str) -> str:
    """
    Tạo yêu cầu đổi trả cho một sản phẩm trong đơn hàng.

    Purpose:
        Sau khi Agent xác nhận khách đủ điều kiện, gọi tool này để tạo
        phiếu yêu cầu đổi trả có mã RMA — đây là side-effect duy nhất
        trong cả bộ tool.

    Input schema:
        order_id (str, required): Mã đơn. Vd: "DH002".
        sku      (str, required): SKU trong đơn. Vd: "SP-LAPTOP".
        reason   (str, required): Lý do đổi trả (>5 ký tự). Vd: "Sản phẩm lỗi pin".

    Output schema:
        Chuỗi thông báo kèm mã RMA mới (RMA001, RMA002, ...).

    Error semantics:
        - order_id / sku không hợp lệ ➔ chuỗi lỗi (validate trước).
        - Đơn chưa giao ➔ từ chối tạo.
        - reason quá ngắn (<5 ký tự) ➔ từ chối, yêu cầu lý do rõ ràng.
        - Đã có RMA cho cùng (order_id, sku) ➔ từ chối trùng.

    Side effect: ghi vào dict _RETURN_REQUESTS (in-memory, reset khi restart).

    Example:
        create_return_request("DH002", "SP-LAPTOP", "Lỗi pin chỉ dùng 2 tiếng")
            ➔ "✅ Đã tạo yêu cầu đổi trả RMA001..."

    Safety: try/except.
    """
    try:
        oid = _normalize_order_id(order_id)
        sku_norm = (sku or "").strip().upper()
        reason_clean = (reason or "").strip()

        if not oid:
            return "LỖI: Thiếu mã đơn hàng."
        if not sku_norm:
            return "LỖI: Thiếu mã SKU sản phẩm."
        if len(reason_clean) < 5:
            return "LỖI: Lý do đổi trả quá ngắn. Vui lòng mô tả ít nhất 5 ký tự (ví dụ: 'Sản phẩm lỗi pin')."

        order = ORDERS_DB.get(oid)
        if order is None:
            return f"LỖI: Không tìm thấy đơn '{oid}'."
        item = next((it for it in order["items"] if it["sku"].upper() == sku_norm), None)
        if item is None:
            valid_skus = ", ".join(it["sku"] for it in order["items"])
            return f"LỖI: SKU '{sku}' không thuộc đơn {oid}. SKU hợp lệ: {valid_skus}."
        if not order.get("delivered_at"):
            return f"❌ Không thể tạo yêu cầu đổi trả: Đơn {oid} chưa được giao."

        # Kiểm tra trùng
        existing_key = f"{oid}:{sku_norm}"
        if any(k == existing_key for k in _RETURN_REQUESTS):
            return f"❌ Yêu cầu đổi trả cho ({oid}, {sku_norm}) đã được tạo trước đó. Vui lòng kiểm tra lại."

        rma_id = f"RMA{len(_RETURN_REQUESTS) + 1:03d}"
        _RETURN_REQUESTS[existing_key] = {
            "rma_id": rma_id,
            "order_id": oid,
            "sku": sku_norm,
            "product_name": item["name"],
            "reason": reason_clean,
            "status": "Đã tiếp nhận — chờ đơn vị vận chuyển đến lấy",
            "created_at": "2026-07-28",
        }
        return (
            f"✅ Đã tạo yêu cầu đổi trả thành công!\n"
            f"   🆔 Mã RMA: {rma_id}\n"
            f"   📦 Đơn: {oid} — Sản phẩm: {item['name']} ({sku_norm})\n"
            f"   📝 Lý do: {reason_clean}\n"
            f"   📊 Trạng thái: {_RETURN_REQUESTS[existing_key]['status']}\n"
            f"   💡 Hướng dẫn tiếp theo: Bộ phận CSKH sẽ liên hệ trong 24h làm việc để sắp xếp đơn vị vận chuyển đến lấy hàng."
        )
    except Exception as e:
        return f"LỖI: Không tạo được yêu cầu đổi trả ({type(e).__name__})."


# =============================================================================
# 🛠️ TOOL 5 — track_delivery
# =============================================================================
def track_delivery(order_id: str) -> str:
    """
    Theo dõi trạng thái vận chuyển của đơn hàng.

    Purpose:
        Khách hỏi "đơn của tôi đang ở đâu / giao khi nào".

    Input schema:
        order_id (str, required): Mã đơn. Vd: "DH001".

    Output schema:
        Chuỗi mô tả: trạng thái hiện tại + carrier + tracking number
        + mốc thời gian dự kiến / thực tế.

    Error semantics:
        - order_id sai ➔ chuỗi lỗi.
        - Đơn chưa có carrier (đang xử lý / đã hủy) ➔ chuỗi thông báo
          "chưa thể theo dõi vì chưa giao cho đơn vị vận chuyển".

    Side effect: read-only.

    Example:
        track_delivery("DH001") ➔ đang vận chuyển GHN, mã GHN7891234, dự kiến 30/07
        track_delivery("DH003") ➔ đang xử lý, chưa có mã vận đơn

    Safety: try/except.
    """
    try:
        oid = _normalize_order_id(order_id)
        if not oid:
            return "LỖI: Thiếu mã đơn hàng."
        order = ORDERS_DB.get(oid)
        if order is None:
            return f"LỖI: Không tìm thấy đơn '{oid}'."

        carrier = order.get("carrier")
        tracking = order.get("tracking_number")
        status = order.get("status")

        if not carrier or not tracking:
            return (
                f"🚚 Đơn {oid} hiện ở trạng thái '{status}'. "
                f"Chưa giao cho đơn vị vận chuyển nên chưa có mã vận đơn để theo dõi. "
                f"Kho sẽ bàn giao trong 1-2 ngày làm việc tới."
            )

        base = (
            f"🚚 Theo dõi vận chuyển — Đơn {oid}\n"
            f"   📌 Trạng thái: {status}\n"
            f"   🏷️ Đơn vị vận chuyển: {carrier}\n"
            f"   🔢 Mã vận đơn: {tracking}\n"
            f"   📅 Ngày đặt: {order['ordered_at']}\n"
            f"   📅 Dự kiến giao: {order.get('estimated_delivery') or 'Chưa cập nhật'}\n"
            f"   ✅ Đã giao thực tế: {order.get('delivered_at') or 'Chưa giao'}"
        )
        # Thêm "mốc giả lập" cho đơn đang vận chuyển để trace dễ
        if status == "Đang vận chuyển":
            base += "\n   🛣️ Cập nhật gần nhất: Hàng đang ở kho trung chuyển — dự kiến phát trong 24h."
        return base
    except Exception as e:
        return f"LỖI: Không theo dõi được vận chuyển ({type(e).__name__})."


# =============================================================================
# 📚 DANH SÁCH TOOL ĐĂNG KÝ — Agent dùng dictionary này để tra cứu dynamic
# =============================================================================
# Mỗi entry kèm schema dạng text để dễ đưa vào prompt cho LLM biết
# args + mô tả (hỗ trợ việc sinh Action[...] của ReAct).
AVAILABLE_TOOLS = {
    "lookup_order": {
        "func": lookup_order,
        "desc": "Tra cứu thông tin đơn hàng theo mã đơn.",
        "args": "order_id: str (VD: 'DH001')",
        "example": "lookup_order['DH001']",
    },
    "check_return_eligibility": {
        "func": check_return_eligibility,
        "desc": "Kiểm tra sản phẩm (trong đơn) có đủ điều kiện đổi trả không.",
        "args": "order_id: str, sku: str (VD: ('DH002', 'SP-LAPTOP'))",
        "example": "check_return_eligibility['DH002', 'SP-LAPTOP']",
    },
    "get_return_policy": {
        "func": get_return_policy,
        "desc": "Lấy chính sách đổi trả theo danh mục sản phẩm.",
        "args": "category: str (optional, mặc định 'default'; một trong: Laptop, 'Điện thoại', 'Thời trang', 'Phụ kiện')",
        "example": "get_return_policy['Laptop']",
    },
    "create_return_request": {
        "func": create_return_request,
        "desc": "Tạo yêu cầu đổi trả mới (sinh mã RMA). Chỉ gọi sau khi check_return_eligibility xác nhận đủ điều kiện.",
        "args": "order_id: str, sku: str, reason: str (>=5 ký tự)",
        "example": "create_return_request['DH002', 'SP-LAPTOP', 'Lỗi pin chỉ dùng 2 tiếng']",
    },
    "track_delivery": {
        "func": track_delivery,
        "desc": "Theo dõi trạng thái vận chuyển của đơn hàng.",
        "args": "order_id: str",
        "example": "track_delivery['DH001']",
    },
}


# =============================================================================
# 🧪 KHỐI TEST THỦ CÔNG — chạy `python src/tools.py` để smoke test
# =============================================================================
if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 72)
    print("🧪 SMOKE TEST — TRỢ LÝ TRA CỨU ĐƠN HÀNG & XỬ LÝ ĐỔI TRẢ")
    print("=" * 72)

    cases = [
        ("lookup_order OK",              lambda: lookup_order("DH001")),
        ("lookup_order sai định dạng",   lambda: lookup_order("xyz")),
        ("lookup_order không tồn tại",   lambda: lookup_order("DH999")),
        ("track_delivery đang VC",       lambda: track_delivery("DH001")),
        ("track_delivery chưa VC",       lambda: track_delivery("DH003")),
        ("policy Laptop",                lambda: get_return_policy("Laptop")),
        ("policy unknown",               lambda: get_return_policy("xyz")),
        ("eligibility đủ (Laptop)",      lambda: check_return_eligibility("DH002", "SP-LAPTOP")),
        ("eligibility quá hạn (Phone)",  lambda: check_return_eligibility("DH004", "SP-PHONE")),
        ("eligibility SKU sai",          lambda: check_return_eligibility("DH002", "SP-PHONE")),
        ("eligibility chưa giao",        lambda: check_return_eligibility("DH001", "SP-AIRPODS")),
        ("create OK",                    lambda: create_return_request("DH002", "SP-LAPTOP", "Lỗi pin chỉ dùng 2 tiếng")),
        ("create trùng",                 lambda: create_return_request("DH002", "SP-LAPTOP", "Lỗi màn hình")),
        ("create lý do ngắn",            lambda: create_return_request("DH002", "SP-LAPTOP", "lỗi")),
        ("create chưa giao",             lambda: create_return_request("DH001", "SP-AIRPODS", "Đổi ý")),
    ]

    for name, fn in cases:
        print(f"\n--- {name} ---")
        try:
            print(fn())
        except Exception as e:
            print(f"❌ TEST RAISED EXCEPTION (BUG!): {type(e).__name__}: {e}")

    print(f"\n📊 Tổng RMA đã tạo trong session: {len(_RETURN_REQUESTS)}")
