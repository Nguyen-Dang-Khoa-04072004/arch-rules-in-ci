# Plan: Clone có chọn lọc file ArchUnit từ 4.000 GitHub repositories

## 1. Mục tiêu

Tận dụng Git Tree API để chỉ tải nội dung những file có khả năng chứa architecture rules, thay vì tải toàn bộ source code của từng repository.

Nguyên tắc:
- Git Tree API cung cấp path và blob SHA, nhưng không xác nhận nội dung file.
- Tên file dùng để ưu tiên tải, không nên là điều kiện duy nhất để loại bỏ file.
- Cố định commit SHA để kết quả có thể tái lập.
- Lưu trạng thái xử lý để phân biệt repo không có rule với repo chưa kiểm tra đầy đủ.

## 2. Kiến trúc pipeline

1. **Input:** danh sách repositories, URL và commit SHA.
2. **Git Tree API:** lấy danh sách path, blob SHA và trạng thái `truncated`.
3. **Lọc candidate files:** test source, build manifests và file có tên gợi ý architecture test.
4. **Tải nội dung chọn lọc:** ưu tiên tải blob theo SHA; dùng partial clone/sparse checkout khi phù hợp.
5. **Phát hiện và trích xuất rules:** xác nhận ArchUnit, chuẩn hóa rule và lưu kết quả.
6. **Output:** dataset có repo, commit, file path, rule, trạng thái và lỗi.

## 3. Chiến lược lọc file

| Nhóm | File/path cần giữ | Mục đích |
|---|---|---|
| Test source | `src/test/**/*.java`, `src/test/**/*.kt`, `src/test/**/*.kts` | Tìm architecture rules |
| Tên file ưu tiên | `*ArchTest*`, `*ArchitectureTest*`, `*ArchitectureTests*`, `*DependencyTest*`, `*LayerTest*`, `*PackageTest*` | Ưu tiên tải và kiểm tra |
| Maven/Gradle | `pom.xml`, `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`, `gradle/libs.versions.toml` | Phát hiện dependency và test source set |
| Test source tùy chỉnh | Các thư mục test được khai báo trong build files | Tránh bỏ sót cấu trúc dự án đặc biệt |

Dấu hiệu ArchUnit trong nội dung:
- `com.tngtech.archunit`
- `@AnalyzeClasses`
- `@ArchTest`
- `ArchRule`, `ArchTests`
- `noClasses()`, `layeredArchitecture()`, `slices()`

Không nên chỉ tải file có tên `ArchitectureTest`: rule có thể nằm trong file test có tên thông thường.

## 4. Chọn cách tải file

### Partial clone + sparse checkout

Phù hợp khi cần nhiều file trong cùng repo hoặc cần dùng công cụ Git cục bộ.

```bash
git clone --filter=blob:none --no-checkout \
  https://github.com/OWNER/REPO.git repo

cd repo
git sparse-checkout init --no-cone

# Tạo danh sách path cần lấy trong .git/info/sparse-checkout
# Mỗi dòng là một pattern/path được chọn.
git checkout
```

Lưu ý:
- `--filter=blob:none` trì hoãn tải nội dung blob cho đến khi cần.
- `--no-checkout` tránh checkout toàn bộ working tree ngay lúc clone.
- Có thể thêm `--depth=1` nếu chỉ cần snapshot gần nhất, nhưng cần đảm bảo commit mong muốn vẫn được lấy.
- Git vẫn tải metadata cần thiết; sparse checkout không làm mất hoàn toàn chi phí khởi tạo clone.

### Sinh sparse-checkout từ `paths.txt`

Giả sử `paths.txt` có một path trên mỗi dòng:

```text
src/test/java/archtest/ArchitectureTest.java
pom.xml
```

Lệnh:

```bash
git clone --filter=blob:none --no-checkout \
  https://github.com/OWNER/REPO.git repo

cd repo
git sparse-checkout init --no-cone

while IFS= read -r path; do
    printf '/%s\n' "$path"
done < paths.txt > .git/info/sparse-checkout

git checkout
```

Chạy lệnh từ thư mục repo vừa clone. Với nhiều file, nên kiểm tra các pattern sparse-checkout để tránh vô tình khớp rộng hơn danh sách dự định.

## 5. Các giai đoạn triển khai

### Giai đoạn 1 — Chuẩn hóa đầu vào

Tạo manifest repository, tối thiểu gồm:

```text
repo_full_name
commit_sha
language_or_ecosystem
tree_status
```

Sử dụng commit SHA cố định thay vì nhánh `main` có thể thay đổi.

### Giai đoạn 2 — Tạo candidate manifest

Sau khi lấy Git Tree, lọc path theo quy tắc ở mục 3. Ghi ra JSONL hoặc CSV với các trường:

```text
repo,commit_sha,path,blob_sha,file_type,priority
```

Nếu `truncated=true`, đánh dấu repo chưa hoàn chỉnh và chuyển sang xử lý riêng.

### Giai đoạn 3 — Tải file

Với mỗi candidate:

1. Kiểm tra cache.
2. Tải nội dung theo blob SHA hoặc raw URL gắn với commit SHA.
3. Giải mã và ghi file vào cấu trúc `downloads/OWNER/REPO/PATH`.
4. Kiểm tra HTTP status, kích thước, encoding và lỗi tải.
5. Retry có backoff với lỗi tạm thời hoặc rate limit.

Không nên giữ giới hạn cứng `0.8 giây/file` mà không benchmark. Điều chỉnh concurrency theo quota API thực tế, xử lý `403`/`429` và tránh retry đồng loạt.

### Giai đoạn 4 — Xác nhận ArchUnit

Chạy bộ phát hiện trên nội dung đã tải. Phân biệt:
- File đã kiểm tra và có dấu hiệu ArchUnit.
- File đã kiểm tra nhưng không tìm thấy rule.
- File chưa tải được hoặc không thể phân tích.

### Giai đoạn 5 — Xử lý dữ liệu thiếu

Với repo có tree bị cắt cụt hoặc cấu trúc đặc biệt:
- Thử lấy tree theo từng subtree.
- Hoặc dùng partial clone/sparse checkout làm fallback.
- Ghi rõ repo nào vẫn chưa thể kiểm tra đầy đủ.

### Giai đoạn 6 — Lưu kết quả và kiểm tra chất lượng

Mỗi repo nên có trạng thái cuối cùng, ví dụ:
- `rules_extracted`
- `no_rules_found`
- `incomplete`
- `failed`

Không đánh đồng `incomplete`/`failed` với `no_rules_found`.

## 6. Cấu trúc thư mục đầu ra

```text
analysis/
├── manifests/
│   ├── repositories.csv
│   └── candidates.jsonl
├── cache/
│   └── blobs/
├── downloads/
│   └── OWNER/
│       └── REPO/
│           └── src/test/.../ArchitectureTest.java
├── results/
│   ├── detected_rules.jsonl
│   └── repository_status.csv
└── logs/
    └── download_errors.jsonl
```

Nên dùng blob SHA làm khóa cache nội dung; lưu thêm repo, commit và path để truy xuất nguồn gốc.

## 7. Benchmark trước khi chạy 4.000 repositories

Bắt đầu với mẫu 10 repo đã có, gồm 135 candidate files. So sánh tải blob qua API với partial clone/sparse checkout.

Đo các chỉ số:
- Tổng thời gian xử lý mỗi repo.
- Số candidate files mỗi repo.
- Số request và tỷ lệ lỗi/retry.
- Tỷ lệ tìm thấy rule.
- Tỷ lệ repo được kiểm tra đầy đủ.

Ước lượng đơn giản cho thời gian tải nội dung:

```text
estimated_seconds = candidate_files * average_seconds_per_file / concurrency
```

Đây chỉ là ước lượng, chưa tính Git Tree, khởi tạo clone, retry, giới hạn API và khác biệt kích thước file.

## 8. Khuyến nghị triển khai

1. Dùng **Git Tree API + tải blob theo SHA** làm đường đi mặc định.
2. Dùng **partial clone + sparse checkout** cho repo có nhiều file cần lấy hoặc làm fallback cho tree bị truncated.
3. Benchmark trên 10–50 repo trước khi chạy toàn bộ tập dữ liệu.
4. Dùng cache, giới hạn concurrency và retry có backoff.
5. Ghi trạng thái rõ ràng để kết quả nghiên cứu có thể tái lập và audit.

Với pipeline hiện tại, cách này tránh chi phí clone cho các repo chỉ có ít candidate. Sau benchmark, chọn phương án có tổng thời gian, request count và tỷ lệ lỗi tốt hơn trên dữ liệu thực tế.


## 9. Parallel download nhiều repositories

**Khuyến nghị:** xử lý nhiều repositories đồng thời, nhưng đặt giới hạn concurrency và tôn trọng GitHub rate limits. Nên song song hóa ở cấp repository trước; bên trong mỗi repo, giới hạn số file tải đồng thời để tránh tạo quá nhiều request.

### Mô hình xử lý

1. Đọc repository manifest và đưa repo vào queue.
2. Một nhóm worker xử lý từng repo: lấy/đọc Git Tree, tạo candidate manifest, tải file được chọn.
3. Dùng cache chung theo blob SHA để tránh tải cùng nội dung nhiều lần.
4. Khi gặp rate limit (`403`/`429`), tạm dừng hoặc giảm tốc độ theo `Retry-After`/reset time nếu có; retry với exponential backoff và jitter.
5. Ghi kết quả theo từng repo ngay khi hoàn tất để có thể resume sau khi tiến trình bị gián đoạn.

### Mức concurrency ban đầu

Bắt đầu benchmark với khoảng **4–8 repositories đồng thời**, rồi điều chỉnh theo:
- GitHub API quota còn lại.
- Tỷ lệ `403`/`429` và lỗi mạng.
- Thời gian trung bình mỗi repo.
- Số candidate files và kích thước blob.

Đây là mức khởi đầu để benchmark, không phải giới hạn cố định hay cam kết an toàn cho mọi token/API quota. Nếu mỗi repo còn tải nhiều file song song, tổng request đồng thời sẽ tăng nhanh; hãy giới hạn cả hai tầng.

### Ví dụ Python dùng `ThreadPoolExecutor`

Ví dụ dưới đây minh họa song song hóa theo repository. Hàm `process_repository(repo)` cần được nối với pipeline hiện tại của bạn: lấy Git Tree, lọc candidate, tải file, cache và lưu trạng thái.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_REPO_WORKERS = 6

def process_repository(repo):
    # Implement using existing tree filtering, download, cache and persistence.
    raise NotImplementedError

def run_repositories(repositories):
    results = []

    with ThreadPoolExecutor(max_workers=MAX_REPO_WORKERS) as executor:
        futures = {
            executor.submit(process_repository, repo): repo
            for repo in repositories
        }

        for future in as_completed(futures):
            repo = futures[future]
            try:
                result = future.result()
                results.append(result)
                logger.info("Completed repository: %s", repo)
            except Exception:
                logger.exception("Repository failed: %s", repo)
                results.append({
                    "repo": repo,
                    "status": "failed",
                })

    return results
```

Không nên đưa hàng nghìn tác vụ tải blob riêng lẻ vào một executor không giới hạn. Dùng queue có giới hạn hoặc semaphore cho request tải file, và ghi trạng thái theo từng repo để có thể tiếp tục chạy mà không phải làm lại toàn bộ.

### Điều kiện cần có trước khi chạy toàn bộ 4.000 repo

- **Rate-limit handling:** kiểm tra quota; xử lý `403`/`429`; tuân thủ `Retry-After` nếu được trả về.
- **Retry có kiểm soát:** exponential backoff kèm jitter; giới hạn số lần retry.
- **Resume:** lưu trạng thái repo và candidate đã tải để chạy lại phần thất bại.
- **Cache:** cache blob theo SHA và xác minh nội dung sau tải.
- **Observability:** ghi số repo đang chạy, số file tải thành công/thất bại, request rate và thời gian xử lý.
- **Không chia sẻ mutable state thiếu đồng bộ:** dùng ghi file nguyên tử hoặc cơ chế lưu trữ có khóa khi nhiều worker cùng cập nhật.

### Kế hoạch benchmark concurrency

Chạy cùng một mẫu repo ở các mức concurrency, ví dụ `1`, `2`, `4`, `6`, `8`. Với mỗi mức, ghi:
- Thời gian hoàn tất toàn bộ mẫu.
- Số request thành công và thất bại.
- Số lần bị rate limit.
- Thời gian trung vị và percentile cao của mỗi repo.
- Tỷ lệ repo hoàn tất đầy đủ.

Chọn mức concurrency đem lại throughput tốt mà vẫn giữ tỷ lệ lỗi thấp; không chỉ chọn mức có số worker lớn nhất.
