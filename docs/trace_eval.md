# 📊 BÁO CÁO GIÁM SÁT & ĐÁNH GIÁ (OBSERVABILITY TRACE LOGS)
*Dành cho Role 5: Observability & Reviewer*

---

## 🎯 1. BẢNG CHẤM ĐIỂM AGENTIC FIT (SCORING MATRIX)

**Đề tài:** Trợ Lý Tra Cứu Đơn Hàng & Xử Lý Đổi Trả

| Tiêu chí | Điểm (1-5) | Lý do đánh giá |
| :--- | :---: | :--- |
| 🧠 **Multi-step Reasoning** | `5/5` | Agent phải thực hiện nhiều bước phụ thuộc nhau: xác minh người dùng, tra cứu đơn hàng, kiểm tra trạng thái giao hàng, đối chiếu thời hạn và điều kiện đổi trả, kiểm tra tồn kho sản phẩm thay thế, xin xác nhận rồi mới tạo yêu cầu đổi trả. |
| 🛠️ **Tool Interaction** | `5/5` | Bài toán cần tương tác với nhiều công cụ hoặc nguồn dữ liệu như `verify_order_owner`, `lookup_order`, `check_return_eligibility`, `check_variant_inventory` và `create_return_request`. Chatbot không dùng tool sẽ không biết trạng thái đơn hàng thực tế. |
| 🔀 **Dynamic Decision** | `5/5` | Hành động tiếp theo thay đổi theo kết quả của từng bước. Ví dụ: đơn chưa giao thì không thể đổi trả; đơn quá hạn thì từ chối hoặc chuyển hỗ trợ; sản phẩm hết size cần đề xuất phương án khác; xác minh thất bại thì không được tiết lộ dữ liệu. |
| ⏳ **Long Horizon** | `4/5` | Một yêu cầu đổi trả hoàn chỉnh có thể gồm khoảng 5–7 bước liên tiếp và phải duy trì đúng thông tin xuyên suốt quy trình. Tuy nhiên, tác vụ thường hoàn thành trong một phiên làm việc nên chưa phải quy trình dài hạn hoàn toàn tự động. |
| **TỔNG ĐIỂM FIT** | **19/20** | **KẾT LUẬN: BÀI TOÁN CÓ AGENTIC FIT RẤT CAO VÀ RẤT NÊN DÙNG REACT AGENT.** |

### Kết luận Mốc 1

Chatbot thông thường chỉ có thể giải thích chính sách đổi trả chung và dễ suy đoán hoặc bịa trạng thái đơn hàng khi không có dữ liệu. ReAct Agent phù hợp hơn vì có thể suy luận theo từng bước, gọi đúng công cụ, quan sát kết quả thực tế và điều chỉnh hành động tiếp theo.

Agent phải tuân thủ các nguyên tắc an toàn:

- Không tự bịa trạng thái đơn hàng, tồn kho hoặc mã yêu cầu đổi trả.
- Không tiết lộ dữ liệu đơn hàng khi người dùng chưa được xác minh.
- Không tạo yêu cầu đổi trả nếu đơn không đủ điều kiện.
- Không khai sai lý do đổi trả theo yêu cầu của người dùng.
- Phải xin xác nhận trước khi thực hiện hành động tạo yêu cầu đổi trả.
- Khi công cụ trả lỗi, phải thông báo lỗi thay vì tự suy đoán kết quả.
---

## 🔍 2. SO SÁNH PHẢN HỒI (TEST CASE #3)

**Câu hỏi**: *"Thời tiết ở Hà Nội hôm nay thế nào và tôi nên mặc gì đi chơi?"*

### 🤖 Chatbot Baseline:
* **Phản hồi**: *"Tôi không có truy cập Internet thời gian thực nên không biết thời tiết hôm nay ở Hà Nội."*
* **Nhận xét**: An toàn nhưng không giải quyết được nhu cầu thực tế của người dùng.

### 🧠 ReAct Agent:
* **Thought 1**: Cần tra cứu thời tiết Hà Nội.
* **Action 1**: `get_weather['Hà Nội']`
* **Observation 1**: `Thời tiết Hà Nội: 28°C, Nắng nhẹ, Độ ẩm 65%.`
* **Thought 2**: Đã có thông tin 28°C nắng nhẹ, đưa ra lời khuyên trang phục.
* **Final Answer**: *"Thời tiết Hà Nội hôm nay 28°C, nắng nhẹ. Bạn nên mặc quần áo thoáng mát!"*
* **Nhận xét**: Hoàn thành xuất sắc nhiệm vụ nhờ sự kết hợp giữa suy luận và công cụ.
