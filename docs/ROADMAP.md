# CatBa Roadmap: "The Next.js for Python"

> **Tầm nhìn cốt lõi**: CatBa mang trải nghiệm phát triển hiện đại của Next.js (File-based routing, React UI, Server-side data fetching, Instant SPA transitions, SSR) đến với hệ sinh thái Python, dựa trên nguyên tắc kiến trúc kiên định: **Python cho nghiệp vụ, C cho hạ tầng mạng/transport, React cho giao diện người dùng**.

---

## 1. Triết lý kiến trúc bất biến (Architectural Invariants)

Bất kỳ tính năng nào được bổ sung theo roadmap đều phải tuân thủ nghiêm ngặt 4 nguyên tắc nền tảng của CatBa:

1. **Python First**: Logic ứng dụng viết 100% bằng Python chuẩn (>= 3.14). Không tạo ra ngôn ngữ phái sinh hay DSL phức tạp.
2. **Two Files Per Route**: 
   - `route.py` = Ranh giới server (HTTP handlers, data fetching, mutations, business logic).
   - `page.tsx` = Ranh giới UI (React client/server component nhận props).
3. **Single Crossing per Request**: Tầng Native C và tầng Python chỉ giao tiếp đúng 1 lần trên mỗi request. C runtime chịu trách nhiệm socket, HTTP parse và gửi wire data; Python chịu trách nhiệm dispatch và sinh props/response.
4. **Chuẩn đóng gói Python**: Sử dụng `pyproject.toml` chuẩn (PEP 517/518/621). Không phát minh ra `catba.toml`, `catba.lock` hay hệ thống quản lý gói riêng.

---

## 2. So sánh CatBa vs. Next.js (Mapping khái niệm)

| Khái niệm Next.js (App Router) | Tương đương trong CatBa | Trách nhiệm |
|---|---|---|
| `page.tsx` | `page.tsx` | React UI component nhận props từ server |
| `layout.tsx` | `layout.tsx` (+ tùy chọn `layout.py`) | Bọc các trang con, giữ nguyên state khi chuyển trang (Persistent layout) |
| `route.ts` (API route) | `route.py` (khi không có `page.tsx`) | Trả về JSON / Response trực tiếp cho client/third-party |
| `page.server.ts` / Server Component | `route.py` (`GET`, `POST`,...) | Chạy trên server Python, truy cập DB, trả về dict props |
| Server Actions (`"use server"`) | Phương thức `POST`/`PUT`/`DELETE` trong `route.py` | Nhận form submission / RPC, mutate data và điều hướng / trả về props mới |
| Client Navigation (`next/link`) | `@catba/react` `<Link>` (Inertia Client) | SPA transitions mượt mà, không reload toàn trang |
| Next.js Rust Compiler (Turbopack) | **CatBa Native Runtime (C23)** + **Vite** | C tối ưu transport/networking, Vite tối ưu bundle/HMR frontend |
| `middleware.ts` | `middleware.py` | Pipeline can thiệp request trước khi dispatch vào route |
| `generateMetadata` / Head | Hook `metadata()` trong `route.py` / `<Head>` | Quản lý title, meta tags, OpenGraph cho SEO |

---

## 3. Lộ trình phát triển chi tiết (Phased Roadmap)

### Phase 0: Hoàn thiện tích hợp Inertia Protocol (Đã hoàn thành)
- [x] Nhận diện request Inertia (`X-Inertia: true`).
- [x] Tạo Inertia Page Object (`component`, `props`, `url`, `version`).
- [x] Version Conflict handling (409 Conflict + `X-Inertia-Location`).
- [x] Partial Reloads (`X-Inertia-Partial-Component`, `X-Inertia-Partial-Data`, `X-Inertia-Partial-Except`).
- [x] Tích hợp `to_http(result, ssr=ssr, request=request)` vào dispatch pipeline và dev server transport.
- [x] Bổ sung đầy đủ unit tests cho phản hồi Inertia.

---

### Phase 1: Thư viện Client `@catba/react` & Điều hướng Client-side
*Mục tiêu: Cung cấp trải nghiệm SPA giống Next.js cho người dùng mà không cần reload trang.*

- [ ] **Xây dựng gói client `@catba/react`**:
  - Tạo wrapper xung quanh `@inertiajs/react` hoặc cung cấp API mang phong cách CatBa.
  - `<Link href="...">`: Tự động gửi Inertia visit khi click chuột, hỗ trợ `replace`, `preserveScroll`, `preserveState`.
  - `useRouter()` / `router.visit(url, options)`: Điều hướng bằng code.
  - `usePage()`: Hook lấy props và metadata của trang hiện tại.
  - `useForm()`: Quản lý form state, tự động xử lý loading, validation errors, reset.
- [ ] **Prefetching**:
  - Prefetch dữ liệu khi người dùng hover vào `<Link>` (tương tự `next/link`).
- [ ] **Trang lỗi & Fallbacks**:
  - Hỗ trợ `404.tsx` và `500.tsx` tùy chỉnh.
  - Error Boundary client-side để tránh crash ứng dụng khi component lỗi.

---

### Phase 2: Nested Layouts & Cấu trúc phân cấp (Layout Hierarchy)
*Mục tiêu: Đạt được tính năng cốt lõi của Next.js App Router — Persistent Layouts.*

- [ ] **Hỗ trợ `layout.tsx` trong cây thư mục**:
  - Cho phép mỗi cấp thư mục có một `layout.tsx`.
  - Component trang con được lồng vào layout cha qua prop `{children}`.
- [ ] **Persistent Layout Engine**:
  - Khi chuyển trang giữa 2 route cùng chung một `layout.tsx`, layout không bị unmount/remount (giữ nguyên scroll và state của sidebar/navbar).
- [ ] **Tùy chọn `layout.py` (Server-side layout data)**:
  - Cho phép layout có file `layout.py` đi kèm để fetch dữ liệu chung (ví dụ: thông tin user đăng nhập, danh mục menu chung) mà từng trang con không cần fetch lặp lại.
- [ ] **File quy ước mở rộng**:
  - `loading.tsx`: Fallback skeleton hiển thị tức thì khi trang đang tải.
  - `error.tsx`: Bắt lỗi cục bộ cho từng phân vùng trang.

---

### Phase 3: Trải nghiệm lập trình đỉnh cao (`catba dev`)
*Mục tiêu: Tốc độ phản hồi tức thì trong quá trình phát triển (Fast Refresh + Python Reload).*

- [ ] **Kiến trúc Dev Runner đa tiến trình**:
  - Chạy song song:
    1. Vite Dev Server phục vụ HMR cho React/TypeScript.
    2. Python Route Watcher & Dispatch Server.
- [ ] **Python Live-reloading không độ trễ**:
  - Theo dõi các thay đổi trong `route.py` và reload module tương ứng mà không phải restart toàn bộ tiến trình.
- [ ] **Unified Error Overlay**:
  - Khi có lỗi ở Python (`route.py`), hiển thị thông báo lỗi trực quan trên giao diện trình duyệt với traceback rõ ràng chỉ vào dòng code Python.
  - Khi có lỗi ở React/TSX, hiển thị Vite error modal quen thuộc.
- [ ] **CLI Polish**:
  - Hiển thị bảng route table được format đẹp mắt khi server khởi động.

---

### Phase 4: Xử lý Form & Mutations ("Server Actions" phong cách Python)
*Mục tiêu: Đơn giản hóa việc gửi form và cập nhật trạng thái dữ liệu.*

- [ ] **Form Handling chuẩn mực**:
  - Handler `POST`, `PUT`, `DELETE` trong `route.py` nhận `ctx.body` đã được parse tự động (JSON hoặc Multipart FormData).
  - Tích hợp chuẩn CSRF token bảo vệ tự động cho mọi form mutation.
- [ ] **Validation & Error Flashing**:
  - Cơ chế trả về lỗi validation có cấu trúc (ví dụ: trả về `HTTPError(422, errors={...})` hoặc flash error).
  - Client component tự động nhận lỗi qua `form.errors` để hiển thị trên UI mà không cần viết boilerplate fetch/axios.
- [ ] **Automatic Re-fetch / Invalidation**:
  - Sau khi `POST` thành công và redirect (hoặc trả về props mới), client tự động cập nhật props mà không reload toàn trang.

---

### Phase 5: Hoàn thiện Native C Runtime cho Production
*Mục tiêu: Đạt hiệu năng phục vụ cao nhất (high throughput, low latency).*

- [ ] **Event Loop & Socket Engine (C23)**:
  - Hoàn thiện abstraction cho Windows (`IOCP` / `platform_win.c`) và Linux/POSIX (`epoll` / `platform_posix.c`).
  - Request buffer và arena memory lifecycle (`arena_reset` sau mỗi request, không rò rỉ bộ nhớ).
- [ ] **Zero-copy Static Asset Serving**:
  - Nhận diện request tài nguyên tĩnh (`/assets/*`, `.js`, `.css`, hình ảnh) và phục vụ trực tiếp từ C sử dụng `TransmitFile` (Windows) hoặc `sendfile` (Linux), hoàn toàn không đánh thức Python runtime.
- [ ] **Embedded Python Bridge nâng cao**:
  - Tối ưu hóa crossing giữa C và Python: quản lý GIL, hỗ trợ sub-interpreters hoặc worker threads để tận dụng đa nhân CPU.
- [ ] **Lệnh `catba start`**:
  - Khởi chạy trực tiếp file nhị phân `catba-native` với tham số trỏ tới thư mục ứng dụng và các file bundle tĩnh đã build.

---

### Phase 6: Middleware, Xác thực & Quản lý Metadata (SEO)
*Mục tiêu: Hoàn thiện các tính năng nâng cao cho ứng dụng doanh nghiệp và SEO.*

- [ ] **Middleware Pipeline (`middleware.py`)**:
  - Hỗ trợ file `middleware.py` ở root hoặc từng thư mục để kiểm tra authentication, session cookie, rate limit, redirect trước khi gọi handler chính.
- [ ] **Dynamic Metadata & SEO**:
  - Khai báo hàm `metadata(ctx)` trong `route.py` hoặc trả về `metadata={...}`.
  - CatBa tự động inject các thẻ `<title>`, `<meta name="description">`, OpenGraph, Twitter Cards vào HTML template khi SSR.
- [ ] **Session & Cookie Helpers**:
  - Cung cấp API tiện ích `ctx.session`, mã hóa cookie an toàn theo chuẩn hiện đại.

---

### Phase 7: Static Site Generation (SSG), Build & Deployment
*Mục tiêu: Sẵn sàng triển khai mọi quy mô (Docker, Serverless, CDN).*

- [ ] **Lệnh `catba build`**:
  - Biên dịch toàn bộ frontend assets qua Vite (production client bundle + SSR server bundle).
  - Phân tích route table và kiểm tra cú pháp toàn bộ `route.py`.
- [ ] **Static Site Generation (SSG) / Prerendering**:
  - Với các route tĩnh hoàn toàn (không có dynamic parameters và không phụ thuộc request runtime), `catba build` có thể xuất ra file HTML tĩnh sẵn sàng đẩy lên CDN/S3.
- [ ] **Docker & Deployment Templates**:
  - Cung cấp multi-stage Dockerfile chính thức tối ưu kích thước image (< 100MB), đóng gói sẵn `catba-native` và Python virtualenv.
- [ ] **CLI Scaffolding (`catba create`)**:
  - Trình khởi tạo dự án mẫu đa dạng: Minimal, Tailwind CSS, Auth/Dashboard template.

---

Copyright (c) 2026 Lê Hùng Quang Minh (furimeo)
Licensed under the Mozilla Public License 2.0 (MPL-2.0).
