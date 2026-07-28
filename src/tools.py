"""
🛠️ TOOL REGISTRY & SCHEMAS — ĐỀ TÀI: TRỢ LÝ TRA CỨU ĐƠN HÀNG & XỬ LÝ ĐỔI TRẢ
(Dành cho Role 2: Tool & Spec Engineer)

Module này đăng ký 5 tool DETERMINISTIC (chạy ngoại tuyến, không cần API thật)
để nhóm có thể so sánh công bằng giữa Chatbot baseline và ReAct Agent.

Mỗi tool tuân theo **Tool Contract 8 tiêu chí** (mục đích — schema — error —
side-effect — example — safety) và được viết docstring theo **Google Style**
để IDE/Pylance hiển thị type hint đầy đủ.

Public API (Role 4 import các tên này):

    Tool functions (callable):
        lookup_order(order_id: str) -> str
        track_delivery(order_id: str) -> str
        check_return_eligibility(order_id: str, sku: str) -> str
        get_return_policy(category: str = "default") -> str
        create_return_request(order_id: str, sku: str, reason: str) -> str

    Registry:
        AVAILABLE_TOOLS: dict[str, dict]
            Mỗi entry có 4 key:
              - "func":   Callable       (hàm thực thi)
              - "desc":   str            (mô tả 1 dòng)
              - "args":   str            (schema tham số)
              - "example":str            (câu lệnh mẫu)

Usage:
    >>> from tools import AVAILABLE_TOOLS
    >>> AVAILABLE_TOOLS["lookup_order"]["func"]("DH001")
    '📦 Đơn DH001 — Khách hàng: Nguyễn Văn A\\n   Trạng thái: ...'

Note:
    - Mọi tool đều có try/except ➔ KHÔNG bao giờ raise Exception ra Agent.
    - Lỗi trả về chuỗi có prefix "LỖI:" — Agent đọc và từ chối suy đoán.
    - Dữ liệu mock nằm ở module-level (ORDERS_DB, RETURN_POLICY, PRODUCT_CATALOG).
    - Ngày hệ thống được fix cứng ở 2026-07-28 cho deterministic.
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
        "estimated_delivery": "2026-06-20",
        # giao cách 43 ngày trước ➔ quá hạn cả Phone (14 ngày) → dùng test "quá hạn"
        "delivered_at": "2026-06-15",
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


# =============================================================================
# 🔧 INTERNAL HELPERS — không xuất hiện trong AVAILABLE_TOOLS
# =============================================================================
def _normalize_order_id(order_id: str | None) -> str:
    """Chuẩn hoá mã đơn: bỏ khoảng trắng, upper-case.

    Args:
        order_id: Mã đơn do Agent hoặc người dùng cung cấp. Hàm an toàn với
            mọi kiểu input (chuỗi, ``None``, số, list, bytes...) — sẽ cố
            gắng ép kiểu sang ``str`` rồi mới xử lý.

    Returns:
        Mã đơn đã được ``str.strip().upper()``. Ví dụ ``"  dh001  "`` ➔ ``"DH001"``.
        Trả về chuỗi rỗng nếu input là ``None`` hoặc không ép kiểu được.

    Examples:
        >>> _normalize_order_id("dh001")
        'DH001'
        >>> _normalize_order_id("  Dh002 ")
        'DH002'
        >>> _normalize_order_id(None)
        ''
        >>> _normalize_order_id(12345)
        '12345'
        >>> _normalize_order_id(b"DH001")
        'DH001'
    """
    try:
        # Ép kiểu an toàn — chấp nhận cả int/list/bytes rồi str()
        if order_id is None:
            return ""
        if not isinstance(order_id, str):
            order_id = str(order_id)
        return order_id.strip().upper()
    except Exception:
        # Fallback cuối cùng — trả về rỗng thay vì để exception thoát
        return ""


def _format_vnd(amount: int) -> str:
    """Format số tiền theo chuẩn VNĐ có dấu chấm phân cách hàng nghìn.

    Args:
        amount: Số tiền (đơn vị VNĐ). Hàm an toàn với ``int``, ``float``,
            ``str`` số — sẽ cố gắng ép kiểu. Nếu không ép được ➔ trả về
            chuỗi ``"N/A"``.

    Returns:
        Chuỗi đã format. Ví dụ: ``6.370.000 VNĐ``.

    Examples:
        >>> _format_vnd(6_370_000)
        '6.370.000 VNĐ'
        >>> _format_vnd(0)
        '0 VNĐ'
        >>> _format_vnd("6_370_000")
        '6_370_000 VNĐ'
        >>> _format_vnd(None)
        'N/A VNĐ'
    """
    try:
        # Nếu là số nguyên/số thực, format theo locale Python
        if isinstance(amount, (int, float)):
            return f"{amount:,}".replace(",", ".") + " VNĐ"
        # Nếu là chuỗi, giữ nguyên (thường từ JSON đã format sẵn)
        return f"{amount} VNĐ"
    except Exception:
        return "N/A VNĐ"


# =============================================================================
# 🛠️ TOOL 1 — lookup_order
# =============================================================================
def lookup_order(order_id: str) -> str:
    """Tra cứu thông tin chi tiết của một đơn hàng theo mã đơn.

    Tool Contract (8 tiêu chí):

        1. **Name**: ``lookup_order`` — độc nhất, snake_case, động từ.
        2. **Purpose**: Dùng khi khách cung cấp mã đơn (DHxxx) và muốn biết
           trạng thái, danh sách sản phẩm, tổng tiền, đơn vị vận chuyển,
           mã tracking và ngày dự kiến giao.
        3. **Input schema**:
           ``order_id`` (``str``, required) — Mã đơn hàng.
           Ví dụ: ``"DH001"``, ``"dh002"``.
        4. **Output schema**: Chuỗi nhiều dòng trình bày đầy đủ
           order_id, customer_name, items, total, status, carrier,
           tracking_number, estimated_delivery, delivered_at.
        5. **Error semantics**:
           - Mã rỗng ➔ ``"LỖI: Mã đơn hàng không được để trống..."``.
           - Không đúng format ``DHxxx`` ➔ liệt kê các mã hợp lệ.
           - Không tồn tại ➔ ``"LỖI: Không tìm thấy đơn hàng..."``.
        6. **Side effect**: read-only — không thay đổi ``ORDERS_DB``.
        7. **Example**:
           ``lookup_order("DH001")`` ➔ trả về khối thông tin DH001.
        8. **Safety**: ``try/except`` toàn bộ — *không bao giờ* raise Exception.

    Args:
        order_id: Mã đơn hàng cần tra cứu. Định dạng kỳ vọng: ``DHxxx``
            (3 chữ số), ví dụ ``"DH001"``. Hàm tự động ``strip()`` và
            ``upper()`` — người dùng có thể nhập ``"dh001"`` hay
            ``"  DH001  "``.

    Returns:
        Chuỗi mô tả đầy đủ đơn hàng nếu tìm thấy; **hoặc** chuỗi có
        prefix ``"LỖI:"`` nếu tham số không hợp lệ / không tìm thấy.
        Hàm **không bao giờ** raise Exception.

    Examples:
        >>> lookup_order("DH001")
        '📦 Đơn DH001 — Khách hàng: Nguyễn Văn A\\n   Trạng thái: Đang vận chuyển\\n...'

        >>> lookup_order("DH999")
        'LỖI: Không tìm thấy đơn hàng \\'DH999\\'. Các mã hiện có: DH001, ...'

        >>> lookup_order("xyz")
        'LỖI: Mã đơn \\'xyz\\' không đúng định dạng (kỳ vọng DHxxx, ví dụ DH001)...'

    Note:
        Tool này KHÔNG xác minh danh tính người gọi — Agent phải xác minh
        trước khi hiển thị dữ liệu cá nhân cho khách.
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
# 🛠️ TOOL 2 — track_delivery
# =============================================================================
def track_delivery(order_id: str) -> str:
    """Theo dõi trạng thái vận chuyển của một đơn hàng.

    Tool Contract (8 tiêu chí):

        1. **Name**: ``track_delivery`` — độc nhất, snake_case, động từ.
        2. **Purpose**: Khách hỏi "đơn của tôi đang ở đâu / giao khi nào".
        3. **Input schema**: ``order_id`` (``str``, required).
        4. **Output schema**: Chuỗi mô tả — status + carrier + tracking
           number + các mốc ngày (đặt / dự kiến / thực tế).
        5. **Error semantics**:
           - ``order_id`` rỗng / không tồn tại ➔ chuỗi ``"LỖI:..."``.
           - Đơn chưa có carrier (đang xử lý / đã hủy) ➔ thông báo
             "chưa có mã vận đơn".
        6. **Side effect**: read-only.
        7. **Example**: ``track_delivery("DH001")`` ➔ khối vận chuyển.
        8. **Safety**: ``try/except`` toàn bộ.

    Args:
        order_id: Mã đơn hàng cần theo dõi. Định dạng ``DHxxx``.

    Returns:
        Chuỗi nhiều dòng với thông tin vận chuyển, hoặc chuỗi ``"LỖI:..."``
        nếu đơn không tồn tại / chưa giao cho đơn vị vận chuyển. Hàm không
        bao giờ raise Exception.

    Examples:
        >>> track_delivery("DH001")
        '🚚 Theo dõi vận chuyển — Đơn DH001\\n   📌 Trạng thái: Đang vận chuyển\\n...'

        >>> track_delivery("DH003")
        '🚚 Đơn DH003 hiện ở trạng thái \\'Đang xử lý\\'. Chưa giao cho đơn vị vận chuyển...'

        >>> track_delivery("DH999")
        'LỖI: Không tìm thấy đơn \\'DH999\\'.'
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
# 🛠️ TOOL 3 — check_return_eligibility
# =============================================================================
def check_return_eligibility(order_id: str, sku: str) -> str:
    """Kiểm tra (đơn + sản phẩm cụ thể) có đủ điều kiện đổi trả hay không.

    Tool Contract (8 tiêu chí):

        1. **Name**: ``check_return_eligibility`` — độc nhất, snake_case.
        2. **Purpose**: Trước khi tạo yêu cầu đổi trả, Agent/người dùng cần
           biết đơn đã giao chưa, còn trong thời hạn không, sản phẩm có
           thuộc đơn không.
        3. **Input schema**:
           - ``order_id`` (``str``, required).
           - ``sku`` (``str``, required) — SKU trong đơn, vd ``"SP-LAPTOP"``.
        4. **Output schema**: Chuỗi mô tả "ĐỦ/KHÔNG đủ điều kiện" + lý do
           cụ thể (đã giao bao nhiêu ngày, còn bao nhiêu ngày, điều kiện,
           phương thức hoàn tiền).
        5. **Error semantics**:
           - Thiếu ``order_id`` / ``sku`` ➔ chuỗi lỗi.
           - Đơn không tồn tại ➔ chuỗi lỗi.
           - ``sku`` không thuộc đơn ➔ liệt kê SKU hợp lệ.
           - Đơn chưa giao ➔ KHÔNG đủ điều kiện.
        6. **Side effect**: read-only.
        7. **Example**: ``check_return_eligibility("DH002", "SP-LAPTOP")``
           ➔ trả về "ĐỦ điều kiện".
        8. **Safety**: ``try/except`` toàn bộ.

    Args:
        order_id: Mã đơn hàng. Định dạng ``DHxxx``.
        sku: Mã SKU sản phẩm trong đơn (VD: ``"SP-LAPTOP"``). Tự động
            ``upper()`` để chấp nhận cả ``"sp-laptop"``.

    Returns:
        Chuỗi nhiều dòng mô tả điều kiện đổi trả (✅ Đủ / ❌ Không đủ)
        kèm số ngày còn lại, hoặc chuỗi ``"LỖI:..."`` nếu tham số
        không hợp lệ. Hàm không bao giờ raise Exception.

    Examples:
        >>> check_return_eligibility("DH002", "SP-LAPTOP")
        '✅ ĐỦ điều kiện đổi trả:\\n   - Sản phẩm: Laptop Dell XPS 13 (SKU SP-LAPTOP)\\n...'

        >>> check_return_eligibility("DH004", "SP-PHONE")
        '❌ KHÔNG đủ điều kiện: ... đã giao 43 ngày trước — quá thời hạn đổi trả 14 ngày...'

        >>> check_return_eligibility("DH001", "SP-AIRPODS")
        '❌ KHÔNG đủ điều kiện đổi trả: Đơn DH001 chưa được giao...'

    Note:
        Ngày hệ thống được fix cứng ở ``2026-07-28`` cho deterministic.
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
# 🛠️ TOOL 4 — get_return_policy
# =============================================================================
def get_return_policy(category: str = "default") -> str:
    """Lấy chính sách đổi trả theo danh mục sản phẩm.

    Tool Contract (8 tiêu chí):

        1. **Name**: ``get_return_policy``.
        2. **Purpose**: Khi khách hỏi chung chung "shop có đổi trả không /
           thời hạn bao lâu" mà chưa cung cấp mã đơn cụ thể.
        3. **Input schema**: ``category`` (``str``, optional, mặc định
           ``"default"``). Một trong: ``"Laptop"``, ``"Điện thoại"``,
           ``"Thời trang"``, ``"Phụ kiện"``, ``"default"``.
        4. **Output schema**: Chuỗi mô tả ``window_days`` + điều kiện +
           phương thức hoàn tiền.
        5. **Error semantics**: ``category`` lạ ➔ fallback ``"default"``
           kèm gợi ý danh mục hợp lệ.
        6. **Side effect**: read-only.
        7. **Example**: ``get_return_policy("Laptop")`` ➔ policy Laptop.
        8. **Safety**: ``try/except`` toàn bộ.

    Args:
        category: Danh mục sản phẩm. Case-insensitive — chấp nhận
            ``"laptop"`` hay ``"LAPTOP"``. Nếu rỗng / lạ ➔ dùng default
            hoặc trả lỗi gợi ý.

    Returns:
        Chuỗi mô tả chính sách hoặc chuỗi ``"LỖI:..."`` nếu danh mục
        không hợp lệ. Hàm không bao giờ raise Exception.

    Examples:
        >>> get_return_policy("Laptop")
        '📋 Chính sách đổi trả — Danh mục: Laptop\\n   ⏳ Thời hạn: 14 ngày...'

        >>> get_return_policy()  # mặc định
        '📋 Chính sách đổi trả — Danh mục: default\\n...'

        >>> get_return_policy("xyz")
        'LỖI: Danh mục \\'xyz\\' không tồn tại. Các danh mục hợp lệ: ...'
    """
    try:
        valid = ["Laptop", "Điện thoại", "Thời trang", "Phụ kiện", "default"]
        cat = (category or "default").strip()
        # Chuẩn hóa capitalization (case-insensitive)
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
# 🛠️ TOOL 5 — create_return_request
# =============================================================================
def create_return_request(order_id: str, sku: str, reason: str) -> str:
    """Tạo yêu cầu đổi trả cho một sản phẩm trong đơn hàng, sinh mã RMA.

    Tool Contract (8 tiêu chí):

        1. **Name**: ``create_return_request``.
        2. **Purpose**: Sau khi Agent xác nhận khách đủ điều kiện, gọi
           tool này để tạo phiếu yêu cầu đổi trả có mã RMA — đây là
           side-effect duy nhất trong cả bộ tool.
        3. **Input schema**:
           - ``order_id`` (``str``, required).
           - ``sku`` (``str``, required).
           - ``reason`` (``str``, required, ``>= 5`` ký tự).
        4. **Output schema**: Chuỗi thông báo kèm mã RMA mới
           (``RMA001``, ``RMA002``, ...).
        5. **Error semantics**:
           - Thiếu tham số ➔ ``"LỖI:..."``.
           - ``reason`` < 5 ký tự ➔ yêu cầu mô tả rõ ràng.
           - Đơn không tồn tại / SKU không thuộc đơn ➔ liệt kê SKU.
           - Đơn chưa giao ➔ từ chối tạo.
           - Trùng ``(order_id, sku)`` ➔ từ chối trùng.
        6. **Side effect**: ghi vào dict ``_RETURN_REQUESTS`` (in-memory,
           reset khi Python process thoát).
        7. **Example**: ``create_return_request("DH002", "SP-LAPTOP",
           "Lỗi pin chỉ dùng 2 tiếng")`` ➔ sinh ``RMA001``.
        8. **Safety**: ``try/except`` toàn bộ.

    Args:
        order_id: Mã đơn hàng. Định dạng ``DHxxx``.
        sku: Mã SKU sản phẩm trong đơn. Ví dụ: ``"SP-LAPTOP"``.
        reason: Lý do đổi trả (>= 5 ký tự). Ví dụ:
            ``"Lỗi pin chỉ dùng 2 tiếng"``.

    Returns:
        Chuỗi thông báo kèm mã RMA nếu tạo thành công; hoặc chuỗi
        ``"LỖI:..."`` / ``"❌ Không thể..."`` nếu không hợp lệ.
        Hàm không bao giờ raise Exception.

    Examples:
        >>> create_return_request("DH002", "SP-LAPTOP", "Lỗi pin chỉ dùng 2 tiếng")
        '✅ Đã tạo yêu cầu đổi trả thành công!\\n   🆔 Mã RMA: RMA001\\n...'

        >>> create_return_request("DH001", "SP-AIRPODS", "Đổi ý")
        '❌ Không thể tạo yêu cầu đổi trả: Đơn DH001 chưa được giao.'

        >>> create_return_request("DH002", "SP-LAPTOP", "ok")
        'LỖI: Lý do đổi trả quá ngắn. Vui lòng mô tả ít nhất 5 ký tự...'

    Note:
        Đây là tool có **side-effect duy nhất**. Agent phải gọi
        ``check_return_eligibility`` trước để đảm bảo khách đủ điều
        kiện — nếu gọi trực tiếp sẽ phụ thuộc vào validation trong
        tool (từ chối đơn chưa giao, từ chối trùng).
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
# 📚 DANH SÁCH TOOL ĐĂNG KÝ — Agent dùng dictionary này để tra cứu dynamic
# =============================================================================
# Mỗi entry kèm schema dạng text để dễ đưa vào prompt cho LLM biết
# args + mô tả (hỗ trợ việc sinh Action[...] của ReAct).
AVAILABLE_TOOLS: dict[str, dict] = {
    "lookup_order": {
        "func": lookup_order,
        "desc": "Tra cứu thông tin đơn hàng theo mã đơn.",
        "args": "order_id: str (VD: 'DH001')",
        "example": "lookup_order['DH001']",
    },
    "track_delivery": {
        "func": track_delivery,
        "desc": "Theo dõi trạng thái vận chuyển của đơn hàng.",
        "args": "order_id: str",
        "example": "track_delivery['DH001']",
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