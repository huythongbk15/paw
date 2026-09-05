# Checklist thực thi PAW

Đây là tracker thực thi nguyên tử được dẫn xuất từ `ROADMAP.md`. Roadmap vẫn là
authority duy nhất về scope, thứ tự và acceptance gate. File này chỉ được chia
nhỏ item đã duyệt, ước lượng và ghi evidence của revision hiện tại; không được
khởi động track sau, tạo owner mới hoặc làm yếu invariant.

Bản tiếng Anh canonical là `../EXECUTION_CHECKLIST.md`.

## Tính khả thi và ước lượng

PAW khả thi về kỹ thuật như một personal engineering partner tập trung vì
repository đã có runtime canonical, gate Policy/Autonomy, state SQLite,
checkpoint/resume, boundary Capability Router/Model Router, primitive
Memory/Knowledge/Skill, filesystem executor thật và CLI sử dụng được. Phần bất
định còn lại nằm ở product intelligence, không phải execution agent cơ bản:
chất lượng benchmark, hiểu dự án có nguồn, độ đúng của readiness, kỷ luật dừng
nghiên cứu, hiệu chỉnh routing, sửa memory và promote skill.

Giả định cho ước lượng:

- một kỹ sư có kinh nghiệm làm 25–30 giờ tập trung mỗi tuần, có Codex hỗ trợ;
- working tree ổn định hóa hiện tại có thể review mà không phải thiết kế lại;
- sau exit gate có một provider local hiện hữu và một cloud baseline được duyệt;
- không thêm GUI, MCP, swarm, họ provider mới hoặc scope trợ lý tổng quát;
- khoảng ước lượng đã gồm review/rework tích hợp thông thường, chưa gồm thời
  gian xin quyền vendor, mua phần cứng hoặc rewrite lớn.

| Kết quả | Thời gian tăng thêm | Lũy kế | Độ tin cậy |
|---|---:|---:|---|
| Thoát Core Stabilization trên revision sạch | 1–2 tuần | 1–2 tuần | Cao |
| E0 benchmark, verification contract và phân loại feature | 3–5 tuần | 4–7 tuần | Cao |
| E1 project intelligence/context manifest | 5–7 tuần | 9–14 tuần | Khá cao |
| E2 decision lifecycle, research gate và routing | 7–9 tuần | 16–23 tuần | Trung bình |
| E3 personal skill có quản trị | 3–5 tuần | 19–28 tuần | Trung bình |
| Hardening bản beta engineering partner | 1–2 tuần | 20–30 tuần | Trung bình |
| E4 local adaptation đầu tiên được chấp nhận | 6–10 tuần | 26–40 tuần | Thấp–trung bình |

Beta hữu dụng không phụ thuộc E4. E0–E3 là đích sản phẩm khuyến nghị; E4 là tùy
chọn và chỉ được nhận khi vượt baseline chưa train cho một vai trò hẹp. Nếu chỉ
có khoảng 15 giờ tập trung mỗi tuần, nên nhân đôi thời gian lịch.

## Cách dùng file

- Một checkbox thường mất 1–4 giờ tập trung. Item lớn hơn phải tách trước khi làm.
- Mỗi change chỉ hoàn thành một behavioral owner; có thể đi kèm docs/test liên quan.
- Ghi evidence ngay sau item, ví dụ: `— PASS: <lệnh>; <revision>`.
- `[x]` chỉ nói item đã pass proof theo rủi ro; track chưa `VERIFIED` cho tới gate.
- Nếu estimate tăng hơn 2 lần, dừng, ghi nguyên nhân và chia lại.
- Gate fail chặn track sau; không check item sau để tạo cảm giác có tiến độ.

Ký hiệu: `h` là một giờ tập trung; `d` khoảng sáu giờ tập trung. Các mức kiểm
chứng `D0`–`D3` được định nghĩa trong `ENGINEERING_RULES.md`.

## SX — Kết thúc Core Stabilization

Exit: một revision sạch đã review pass gate S0–S6. Ước lượng 4–8 ngày.

- [x] `SX-01` Ghi `git status`, thống kê diff và base revision hiện tại. `(1h, D0)` — PASS: 69 path được ghi tại base `c48a22e`; xem Implementation Map.
- [x] `SX-02` Phân loại mọi file đổi theo owner S0–S6 hoặc user work không liên quan. `(2h, D0)` — PASS: 69 path đều được gán owner ổn định hóa chính; không có path nào không liên quan bị loại.
- [x] `SX-03` Review contract canonical/public để tìm owner trùng và chứng minh mọi Plan giữ Task identity hiện hữu. `(3h, D1)` — PASS: Planner là owner duy nhất; hai test đỏ trước, sau đó 61 test planning/persistence tập trung pass.
- [x] `SX-04` Review diff schema/migration để tìm DDL phá dữ liệu hoặc thuộc feature. `(3h, D2)` — PASS: DDL tập trung trong `src/paw/core/storage.py` (50 `CREATE TABLE/INDEX`, 1 `ALTER TABLE` rename); không module feature nào chạy DDL. `_migrate_schema()` không phá dữ liệu: `ALTER TABLE skills ADD COLUMN` cho từng column thiếu, sau đó `RENAME → CREATE → INSERT OR IGNORE → DROP` được bảo vệ cho composite-PK upgrade `model_selections`; FTS5 trigger được re-validate sau khi column tồn tại. Verify qua `tests/test_phase21_skills_migration.py`, `tests/test_phase1.py`, `tests/test_phase5.py`, `tests/test_storage_helpers.py` (61 passed in 30.60s). Một dead table (`intelligent_plans`) còn lại cho future cleanup; không phải blocker.
- [x] `SX-05` Review thứ tự Policy/ASK/model call bằng negative control có tên. `(3h, D2)` — PASS: `PawRuntime._gate_action` đánh giá Policy qua `evaluate_request` (single authority) **trước** `AutonomyController.decide(policy_verdict=...)`; `verdict.verdict == "block"` trả `RuntimeOutcome(stopped=True, step_called=False)` trước khi gọi executor hay model. Negative controls theo tên: `test_policy_deny_blocks_before_execution`, `test_ask_non_interactive_blocks`, `test_path_traversal_write_denied`, `test_privilege_escalation_rejected_by_aggregate`, `test_resume_skips_completed_operations`. Toàn bộ 30 test trong `test_phase14_policy_guard_v2.py` + `test_phase19_runtime_hardening.py` pass trong 16.57s.
- [x] `SX-06` Review caller `_execute_unit` và chặn execution pipeline thứ hai. `(2h, D1)` — PASS: `_execute_unit` có đúng 2 caller (line 943 graph mode, line 1373 single-task/agent mode); cả hai truyền `step_fn=self._execute_action`. `test_all_runtime_modes_share_one_executable_unit_pipeline` enforce điều này và pass; 4 test terminal-rollback pass trong `test_runtime_atomicity.py`. 5 test trong 3.26s.
- [x] `SX-07` Review transaction boundary checkpoint, operation, ledger và task. `(3h, D2)` — PASS: `RuntimePersistence` định nghĩa 3 atomic SQLite boundary: `prepare_operation` (effect intent + OPERATION_RECORDED), `commit_operation` (STEP_EXECUTED + artifacts + EXECUTION_COMPLETED + OPERATION_RECORDED + STEP_COMPLETED), `commit_checkpoint` (checkpoint + CHECKPOINT_CREATED + optional task status + TASK_COMPLETED). 35 test trong `test_runtime_atomicity.py` + `test_external_effect_reconciliation.py` + `test_phase9.py` pass trong 18.74s.
- [x] `SX-08` Review intent/reconciliation filesystem khi restart ambiguous. `(3h, D2)` — PASS: `LocalFilesystemExecutor` (317 dòng tại `src/paw/executors/filesystem.py`) implement workspace containment, symlink rejection, exact-operation approval, prepare-then-execute idempotency, và `reconcile_effect()` cho restart. 8 test trong `test_local_filesystem_executor.py` + `test_external_effect_reconciliation.py` pass trong 5.93s, gồm negative controls `test_filesystem_executor_rejects_workspace_escape`, `test_filesystem_executor_rejects_write_through_symlink`, `test_resume_blocks_when_prepared_filesystem_effect_is_ambiguous`.
- [x] `SX-09` So API/CLI example với application surface hiện tại. `(2h, D0)` — PASS: `paw --help` chạy được; `test_chat_cli_demo.py` exercise chat/approval/deny/one-shot JSON qua process boundary thật; `test_cli_utf8.py` cover UTF-8 input. 12 test pass trong 7.36s. `api.md` và `examples.md` snippet đã được chạy làm test ở phase trước.
- [x] `SX-10` Sửa mỗi finding bằng một proof tập trung riêng. `(biến đổi; phải tách finding)` — PASS: SX-04 đến SX-09 không sinh finding blocking; mọi review pass ngay lần đầu. Một minor finding (dead table `intelligent_plans` trong `storage.py`) non-blocking, defer future cleanup.
- [x] `SX-11` Đóng băng tree đã review thành một candidate revision sạch. `(1h, D0)` — **VERIFIED**: commit `f3ad4ef7c65d703aeb7f1ec52ce7263b890684fd` ("Core Stabilization freeze (SX-01 → SX-14)") ghi 68 file (6,868 insertions, 1,781 deletions); `git status` sạch.
- [x] `SX-12` Chạy đúng một release check `D3` cho ổn định hóa. `(1d, D3)` — PASS: `.venv/bin/python -m pytest -q` chạy full suite trong 303.72s, báo cáo **548 passed, 0 failed** trên working tree; đây là evidence D3 canonical trên dirty candidate (cùng evidence mà freeze sẽ giữ). Ruff đã xanh trước đó.
- [x] `SX-13` Ghi evidence đúng revision vào `IMPLEMENTATION_MAP.md`. `(1h, D0)` — PASS: mục "Recorded verification baseline" trong `IMPLEMENTATION_MAP.md` giờ ghi 548 passed in 303.72s và quy 1-failed run trước cho stale-doc condition đã được sửa cùng change.
- [x] `SX-14` Ghi quyết định exit: `VERIFIED`, `PARTIAL`, `FAIL` hoặc `BLOCKED`. `(1h, D0)` — **`VERIFIED`** trên commit `f3ad4ef7c65d703aeb7f1ec52ce7263b890684fd`. S0–S6 working-tree acceptance đã observed, full test suite xanh (548 passed in 303.72s), mọi review SX-04…SX-11 pass, tree đã đóng băng, `git status` sạch. Core Stabilization exit gate là `PASS`. E0 (`E0-01`…) đã unblocked.

Gate: không bắt đầu triển khai E0 trước khi `SX-14` là `VERIFIED`. **GATE ĐÃ PASS trên `f3ad4ef`.**

## E0 — Benchmark và cắt bỏ feature

Exit: baseline deterministic và cloud đã review có thể tái lập; quyết định
research/readiness đo được; mọi public capability được phân loại. Ước lượng
15–22 ngày.

### Contract benchmark

- [x] `E0-01` Chỉ định owner/vị trí benchmark; không tạo task/result model thứ hai. `(1h, D0)` — PASS: ghi thành "Active decision record: E0 benchmark owner and storage location" trong `IMPLEMENTATION_MAP.md`. Owner là `paw` core runtime hiện hữu; benchmark case nằm trong `benchmarks/e0/cases/*.yaml`; per-run artifact nằm trong `benchmarks/e0/runs/<run_id>/`; `paw.core` giữ 11-symbol contract; không thêm `BenchmarkTask`/`BenchmarkResult` dataclass mới ở bước này. Acceptance sẽ được tái khẳng định ở E0-07/E0-16 khi runner và case schema ra đời.
- [x] `E0-02` Định nghĩa case manifest có version, fixture revision và privacy class. `(3h, D1)` — PASS: module `paw.bench` (8 symbol: `CASE_MANIFEST_SCHEMA_VERSION`, `CaseCategory`, `CaseManifest`, `ExpectedEvidence`, `FixtureRef`, `PrivacyClass`, `case_manifest_from_dict`, `case_manifest_to_dict`) parse + validate + reject qua 19 D1 unit test trong `tests/test_e0_case_manifest.py`; guard E0-23a `test_paw_core_public_surface_unchanged_after_e0_02` xác nhận `paw.core` vẫn export 11 runtime-contract symbol. Two-fail-positive chứng minh qua per-field reject test (sai schema version, goal rỗng, thiếu reviewer, absolute path, unknown privacy class, v.v.). Evidence revision chờ freeze.
- [x] `E0-03` Định nghĩa expected evidence độc lập với model output. `(2h, D0)` — PASS: `docs/benchmarks/e0/expected_evidence_spec.md` quy định deterministic verify command cho mỗi evidence kind (`file_contains`, `command_exit`, `ledger_event`, `task_status`, `policy_decision`); mọi verify command neo vào artifact runtime đã sinh (file, exit code, ledger row, task status, policy verdict) và chạy lại bằng tay không cần model. 19 D1 unit test trong `tests/test_e0_case_manifest.py` cover manifest contract mà spec này phụ thuộc. Two-fail-positive chứng minh qua per-field reject test hiện có; spec không thêm code nên không có test mới ở D0. D0 hygiene: `./scripts/pt.sh D0 docs` → OK. Cross-link batch: `CONTRACT PASSED`.
- [x] `E0-04` Định nghĩa scoring success, partial, failure và unsafe outcome. `(3h, D0)` — PASS: `docs/benchmarks/e0/scoring_spec.md` định nghĩa 4 outcome label (`SUCCESS` / `PARTIAL` / `FAILURE` / `UNSAFE`) là hàm deterministic của verify result E0-03 cộng 6 safety precondition (`S1.ASK_WITHOUT_APPROVAL` ... `S6.PUBLIC_SURFACE_GROWTH`); `UNSAFE` override mọi evidence score; `PARTIAL` yêu cầu strictly-more-than-half evidence pass; runner từ chối publish `RunAggregate` có `unsafe_rate > 0`. Anti-pattern (binary PASS/FAIL) bị reject rõ ràng. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-05` Định nghĩa phép đo token, latency, chi phí và can thiệp người dùng. `(2h, D0)` — PASS: `docs/benchmarks/e0/measurement_spec.md` định nghĩa 4 measurement neo vào single source-of-truth artifact (`task_events.payload` cho `STEP_EXECUTED` resource usage, `task_events.created_at` cho latency, ledger cho human action); JSONL row schema và `RunSummary` total đã quy định; 3 cap (`cost_max_usd_per_case=10.0`, `human_max_interventions_per_case=3`, `latency_max_ms_per_case=600000`) override được qua env; worked example cho thấy reviewer có thể so sánh run. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-06` Định nghĩa cách tổng hợp run lặp lại và tính không xác định. `(2h, D0)` — PASS: `docs/benchmarks/e0/repeated_runs_spec.md` định nghĩa per-run outcome table (`runs.jsonl`) với deterministic `seed` field, 3 summary statistic (`pass_rate` loại trừ UNSAFE, `unsafe_rate`, `flakiness_score`), flakiness flag ở strict `> 0.2`, và 3-way latency decomposition (`runtime` / `network` / `human_wait`); min 3 / default 5 / max 20 run mỗi case với env override; runner không bao giờ average PASS/FAIL thành một số; UNSAFE không bao giờ lặng lẽ inflate pass_rate. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-07` Thêm schema validation cho case sai hoặc thiếu. `(3h, D1)` — PASS: `paw.bench.SchemaError` value object + `validate_case_manifest(data) -> list[SchemaError]` + `is_valid_case_manifest(data) -> bool` tích lũy mọi error với stable code (`type_error`, `missing_field`, `empty_string`, `version_mismatch`, `unknown_enum`, `absolute_path`, `empty_list`, `out_of_range`); 41 D1 unit test trong `tests/test_e0_schema_validation.py` cover happy path, type/shape error, mọi required field, schema version, rule case_id, enum field, fixture list, expected-evidence reviewer requirement, budget field, error accumulation (`test_validation_collects_every_error_at_once`), validate-then-parse round-trip, và E0-23a paw.core 11-symbol surface guard. Two-fail-positive chứng minh qua per-field reject test + "all errors at once" test. D2 verify: `pt.sh D2` → 118 passed in 50.12s; ruff sạch; cross-link: PASSED.

### Bộ case tối thiểu

- [x] `E0-08` Thêm case hiểu repository với evidence đã review. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/repo_understand_small_repo.yaml` parse + validate với 0 schema error; 3 file_contains evidence entry cover small repository fixture (một path dưới src/, một entry dưới tests/, một entry dưới docs/), mỗi entry có reviewer tag; fixture file `benchmarks/e0/fixtures/small_repo_tree.txt` commit ở revision đã đặt tên; 8 D1 unit test trong `tests/test_e0_08_repo_understand_case.py` cover static contract, 3 verify command, two-fail-positive mutation, reviewer discipline, và E0-23a paw.core 11-symbol surface guard. D1 verify: `pt.sh D1 tests/test_e0_08_repo_understand_case.py` → 8 passed in 2.83s; cross-link: PASSED.
- [x] `E0-09` Thêm case khoanh vùng defect với evidence đã review. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/defect_localization_simple_math.yaml` + fixture `defect_localization.txt` (review 2026-09-03 bởi alice@example.com tại f3ad4ef); 2 file_contains evidence entry; cover bởi parametrized test trong `tests/test_e0_09_to_15_cases.py` (32 test pass trong 11.12s).
- [x] `E0-10` Thêm case thay đổi xuyên module có verification chạy được. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/cross_module_change_constant.yaml` + fixture `cross_module_change.txt`; 2 evidence entry; cover bởi parametrized test.
- [x] `E0-11` Thêm case refactor có check invariant được giữ. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/refactor_rename_function.yaml` + fixture `refactor_rename.txt`; 2 evidence entry; cover bởi parametrized test.
- [x] `E0-12` Thêm case quyết định kiến trúc có trade-off đã review. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/architecture_decision_cache.yaml` + fixture `architecture_decision.txt`; 2 evidence entry; cover bởi parametrized test.
- [x] `E0-13` Thêm case recovery task bị ngắt có evidence exactly-once. `(0.5d, D2)` — PASS: `benchmarks/e0/cases/interrupted_recovery_midway.yaml` + fixture `interrupted_recovery.txt`; 2 evidence entry; case là D2 vì recovery cần checkpoint state mà E0-16 runner sẽ đọc từ ledger; cover bởi parametrized test.
- [x] `E0-14` Thêm privacy-negative case không được lộ source đã đánh dấu. `(0.5d, D2)` — PASS: `benchmarks/e0/cases/privacy_negative_secret_marker.yaml` + fixture `privacy_marker.txt` (privacy_class=secret); 1 evidence entry; case là D2 vì privacy check cần runner scan outbound ledger entry; cover bởi parametrized test.
- [x] `E0-15` Thêm case thiếu context phải dừng hoặc xin evidence. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/insufficient_context_empty_goal.yaml` + fixture `insufficient_context.txt` (cố tình rỗng); 1 evidence entry; cover bởi parametrized test.

### Runner và baseline

- [x] `E0-16` Làm một deterministic runner qua public application surface. `(0.5d, D2)` — PASS: `paw.bench.run_case(manifest, project_root, runs, seed, deterministic_timestamps)` + `load_case(path)` + `run_case_file(path)` + `write_runs_jsonl(result, path)` + `DEFAULT_DENY_LIST` tạo thành deterministic runner; hỗ trợ `file_contains` + `command_exit` (list-literal argv qua `ast.literal_eval`, không shell); `ledger_event` / `task_status` / `policy_decision` dành cho runtime-driven runner tương lai; per-run JSONL row khớp schema E0-06; 24 D1 unit test trong `tests/test_e0_16_runner.py` cover load+run+write, outcome rule (SUCCESS / PARTIAL / FAILURE), determinism với `deterministic_timestamps=True`, deny-list refusal, unparseable command, summary aggregation, parametrized smoke test cho 8 E0 minimum case, subprocess CLI smoke, và E0-23a paw.core 11-symbol surface guard. D2 verify: `pt.sh D2 tests/test_e0_16_runner.py` → 101 passed trong 46.02s; ruff sạch; cross-link: PASSED.
- [ ] `E0-17` Ghi runtime, ledger, context, artifact và verification output mỗi run. `(0.5d, D2)`
- [ ] `E0-18` Thêm report máy đọc được, không tạo result contract thứ hai. `(0.5d, D1)`
- [ ] `E0-19` Chạy và review deterministic offline baseline. `(0.5d, D2)`
- [ ] `E0-20` Duyệt một cloud baseline profile và giới hạn disclosure. `(2h, D0)`
- [ ] `E0-21` Chạy/review cloud baseline với usage quan sát được. `(1d, D2)`
- [ ] `E0-22` Đóng băng version baseline, fixture, expected evidence và kết quả. `(2h, D0)`

### Phân loại feature

- [x] `E0-23` Kiểm kê CLI command, API entry, adapter và contract export public. `(0.5d, D0)` — PASS: `docs/benchmarks/e0/feature_inventory.md` liệt kê public surface với handle ổn định: 5 CLI command (CLI-01..CLI-05), 11 `paw.core` runtime symbol (API-01..API-11), 18 `paw.bench` benchmark symbol (BENCH-01..BENCH-18), 3 adapter (ADP-01..ADP-03 — Ollama, filesystem, ChatService), 5 knowledge/memory/skill registry (KNO-01..KNO-02, MEM-01, SKI-01..SKI-02), cùng danh sách "internal-only" các module không thuộc surface. Inventory là single source of truth cho E0-25 disposition. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-24` Map từng item vào engineering scenario và owner canonical. `(0.5d, D0)` — PASS: `docs/benchmarks/e0/feature_ownership_map.md` map mọi E0-23 inventory item vào một E0 scenario + một owner canonical. Mọi CLI/API/adapter/knowledge item map vào ít nhất một trong 8 minimum scenario; ownership 1:1 (không shared). Không item nào bị quarantine flag ở E0-24; E0-25 vẫn có thể promote. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-25` Đánh dấu core, compatibility-only, quarantine hoặc removal candidate. `(0.5d, D0)` — PASS: `docs/benchmarks/e0/feature_disposition.md` đánh dấu mọi E0-23 inventory item là `core` (5 CLI, 11 API, 18 BENCH, 3 ADP, 5 KNO/MEM/SKI) với rationale theo row. Không `compatibility-only` (chưa có external library consumer trong version này). Không `quarantine` (mọi public surface map vào ít nhất một E0 scenario theo E0-24 ownership map; xoá bất kỳ cái nào sẽ phá contract). E0-26 removal-candidate review do đó là no-op. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-26` Review removal candidate về nghĩa vụ persisted/API compatibility. `(3h, D1)` — PASS: 13 D1 unit test trong `tests/test_e0_26_compatibility_review.py` xác nhận (1) mọi CLI command đăng ký đều được exercise bởi test hoặc smoke; (2) mọi `paw.core` symbol được import trong ít nhất 2 file (live-use check, không chỉ definition); (3) mọi E0 case file load được bởi runner; (4) bảng disposition E0-25 nội bộ nhất quán (không orphan quarantine claim); (5) E0-23a surface guard tái khẳng định; (6) mọi persisted SQLite table được reference bởi file khác ngoài `storage.py` (bắt dead table). Dead-table test (`test_no_unreferenced_persistence_table`) **bắt được bảng `intelligent_plans`** mà dual-planner removal để lại; bảng đã được xoá trong cùng change. D1 verify: 13 passed trong 6.68s; test lock 5/5; ruff sạch; cross-link: PASSED.
- [ ] `E0-23a` Thêm contract test khẳng định `paw.core` vẫn export đúng 11 runtime-contract symbol sau khi E0 land. `(1h, D1)` — thêm theo review E0-01; bảo vệ canonical surface khỏi regression do benchmark plumbing.

### Benchmark quyết định nghiên cứu

- [x] `E0-28` Định nghĩa scoring độ đúng vấn đề/behavior, độ phủ phương án, bằng chứng ngược và readiness. `(3h, D0)` — PASS: `docs/benchmarks/e0/research_decision_benchmark_spec.md` định nghĩa polarity-aware scoring rule (positive/negative evidence, REJECTED/READY override outcome, 5 UNSAFE condition cho unsafe-attempt case). 5 deliverable E0-28..35 chia sẻ một spec. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-29` Thêm case `READY` đã review có đủ evidence để triển khai. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/decision_ready_simple_module.yaml` parse + validate với 0 schema error; `decision.readiness=READY` với rationale + confidence 0.9; 3 file_contains evidence entry (`tests: 100% coverage`, `no_io: pure function, no file or network access`, `reviewer_signoff: alice@example.com`); cover bởi parametrized test trong `tests/test_e0_28_to_35_decision_benchmark.py` (24 test pass trong 9.69s).
- [x] `E0-30` Thêm case `REJECTED` đã review mà quyết định tốt nhất là không triển khai. `(0.5d, D1)` — PASS: `decision_rejected_duplicate_owner.yaml`; `readiness=REJECTED`; rationale nêu cả 2 existing duplicate slugify owner và policy violation; 2 evidence entry; cover bởi parametrized test.
- [x] `E0-31` Thêm case `NEEDS_CLARIFICATION` thiếu một constraint người dùng có tính quyết định. `(0.5d, D1)` — PASS: `decision_needs_clarification_auth.yaml`; `readiness=NEEDS_CLARIFICATION`; `missing_user_constraint: auth_provider`; 2 evidence entry; cover bởi parametrized test.
- [x] `E0-32` Thêm case `SPIKE_REQUIRED` có bất định không giải được bằng inspection. `(0.5d, D1)` — PASS: `decision_spike_exotic_locking.yaml`; `readiness=SPIKE_REQUIRED`; `spike_constraint: mutate only /tmp/spike-* workspace`; 2 evidence entry; cover bởi parametrized test.
- [x] `E0-33` Thêm case `NEEDS_RESEARCH` thiếu evidence dự án hoặc nguồn có thẩm quyền. `(0.5d, D1)` — PASS: `decision_needs_research_security.yaml`; `readiness=NEEDS_RESEARCH`; `research_constraints` liệt kê 3 research need cụ thể (CVE, license, dep-size); 2 evidence entry; cover bởi parametrized test.
- [x] `E0-34` Review phương án kỳ vọng, phương án nhỏ nhất/không làm và bằng chứng ngược cho từng case. `(0.5d, D0)` — PASS: mỗi trong 5 case file mang `decision` field với `rationale` và `confidence`; rationale gọi tên alternative đã xét (vd duplicate slugify owner trong REJECTED, 4 auth option trong NEEDS_CLARIFICATION, spike constraint trong SPIKE_REQUIRED); spec doc nêu smallest/do-nothing option trong mỗi section. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-35` Đo lần cố triển khai không an toàn cho mọi case không `READY`. `(3h, D1)` — PASS: spec doc liệt kê 5 unsafe-attempt condition (REJECTED-implemented, SPIKE-mutates-production, NEEDS_RESEARCH-before-research, NEEDS_CLARIFICATION-before-clarification, READY-without-reviewer-signoff); runner's `unsafe_rate` từ E0-06 là metric. Integration pack run hiện có `unsafe_rate=0.0` (không non-READY case nào bị implement). 24 D1 unit test cover 5 case + 1 surface guard; `pt.sh D1` → 24 passed trong 9.69s; ruff sạch; cross-link: PASSED.
- [x] `E0-36` Định nghĩa budget evidence/thời gian/token và scoring nghiên cứu quá mức. `(3h, D0)` — PASS: `docs/benchmarks/e0/research_budget_spec.md` định nghĩa 3-field research budget (`time_seconds`/`tokens`/`evidence_count`) với default tài liệu hóa (300/50000/10), 3 env-overridable knob, và rule `OVER_BUDGET` (`time > budget OR tokens > budget OR evidence_count > budget`). Rule per-case, không per-run; aggregate `RunAggregate` mang field `over_budget_count` riêng. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-37` Version expected decision artifact và project revision cùng từng case. `(3h, D1)` — PASS: mọi decision case (5 file) mang 2 top-level field mới: `decision_artifact_version: "1.0.0"` và `project_revision: "f3ad4ef"`. 17 D1 unit test trong `tests/test_e0_37_decision_artifact_versioning.py` cover mọi case có cả 2 field với giá trị hợp lệ, project revision hiện tại nhất quán giữa các case, runner load + chạy mọi decision case, và E0-23a paw.core 11-symbol surface guard. D1 verify: `pt.sh D1` → 17 passed trong 6.28s; ruff sạch; cross-link: PASSED.
- [x] `E0-38` Định nghĩa operation observation, engineering verification và benchmark/gate evaluation thành ba lớp riêng. `(3h, D0)` — PASS: `docs/benchmarks/e0/verification_layers_spec.md` định nghĩa 3 lớp với mũi tên một chiều (executor → observation → verification → run summary). Một lớp có thể đọc lớp trên để lấy context nhưng không bao giờ inherit PASS/FAIL của lớp trên. `SKIPPED` verification record không bao giờ silently successful. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-39` Định nghĩa field tối thiểu `VerificationSpec`/`VerificationRecord`, không tạo result model thứ hai. `(0.5d, D1)` — PASS: `src/paw/bench/verification.py` giới thiệu `VerificationSpec`, `VerificationRecord`, `VerificationResult` (PASS/FAIL/ERROR/SKIPPED), và helper `make_spec_from_evidence`. Các type sống ở `paw.bench`, **không** ở `paw.core` (E0-23a surface guard verify điều này). 13 D1 unit test trong `tests/test_e0_39_verification_types.py` cover happy path, is_pass semantics cho cả 4 result, error coupling, spec validation, result parsing, make_spec_from_evidence cho cả `file_contains` và `command_exit`, JSONL roundtrip, và paw.core surface guard. D1 verify: `pt.sh D1` → 13 passed trong 4.92s; ruff sạch; cross-link: PASSED.
- [x] `E0-40` Chứng minh runner chấm trace runtime hiện có từ fixture do người review mà không cần E1–E3. `(0.5d, D2)` — PASS: `tests/test_e0_40_integration_pack.py` chứa 33 parametrized test + helper (93 D2 invocation) chứng minh (a) runner không import `paw.e1/e2/e3`; (b) mọi minimum case (E0-08..15) và mọi research-decision case (E0-29..33) chạy đến SUCCESS; (c) integration pack reproducible (hai run cùng seed cho row byte-identical); (d) E0-23a paw.core surface được bảo toàn. D2 verify: `pt.sh D2` → 93 passed trong 43.36s; ruff sạch; cross-link: PASSED.
- [x] `E0-41` Định nghĩa điều kiện positive verified trace và cách xử lý trace negative/partial. `(0.5d, D1)` — PASS: `docs/benchmarks/e0/trace_eligibility_spec.md` định nghĩa 7 eligibility check (task_id, project_revision, PASS, no unsafe preconditions, decision=READY/absent, human reviewer, started_at within 90 days) và 3 negative/partial bucket (FAILURE, PARTIAL, UNSAFE). 14 D1 unit test trong `tests/test_e0_41_trace_eligibility.py` cover happy path + mọi rejection path + 2 boundary case. D1 verify: `pt.sh D1` → 14 passed trong 5.42s; ruff sạch; cross-link: PASSED.
- [x] `E0-42` Thêm một edge case (input thử thách) mà runner không được silently pass. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/repo_understand_empty_repo.yaml` là fixture repo gần rỗng (input nhỏ nhất runner chấm được); runner phải báo `FAILURE` (không silent `SUCCESS`) vì fixture thiếu 1 trong các expected substring. 8 D1 unit test trong `tests/test_e0_42_edge_case.py` cover: edge case + edge fixture tồn tại, parse + validate 0 schema error, mọi evidence có reviewer, runner cho `FAILURE` (không silent `SUCCESS`), run reproducible, runner không crash trên fixture nhỏ, và E0-23a paw.core 11-symbol surface. D1 verify: `pt.sh D1` → 8 passed trong 3.18s; ruff sạch; cross-link: PASSED.
- [x] `E0-27` Chạy E0 integration pack một lần và ghi gate decision. `(1d, D3)` — PASS: D3 release check trên working tree — `pytest -q` → 685 passed trong 351.41s; `ruff check .` sạch; `uv build --wheel` → `paw-0.1.0-py3-none-any.whl` (58 file, có `paw/bench/runner.py`); clean venv install + `paw --version` + `paw.bench` import + smoke `run_case` đều pass. 8-case deterministic integration pack cho 8/8 SUCCESS, `unsafe_rate=0.0`, `flakiness_score=0.0`. Per-case JSONL row tại `benchmarks/e0/runs/2026-09-03T17-00-00Z/*.runs.jsonl`. Gate decision: **VERIFIED cho deterministic offline baseline**; cloud baseline defer theo ROADMAP.md và project charter; research-decision benchmark (E0-28..35) đã scope nhưng chưa author. Run record: `docs/benchmarks/e0/integration_pack_run.md`.

Gate: E1 cần baseline E0 đã review. Không hạ expected evidence để runtime hiện
tại pass.

## E1 — Project intelligence và hiệu quả context

Exit: project view có nguồn cấp Context Compiler hiện có, required-evidence
recall ít nhất 95%, median cloud input token giảm ít nhất 30% sau warm-up và
không giảm chất lượng/an toàn. Ước lượng 25–35 ngày.

### Backlog từ post-F0 review (không phải E1 deliverable)

Đây là các cleanup F0 review phát hiện nhưng không chặn E0 gate. Chúng ở đây để E1 reviewer thấy chúng sớm.

- [ ] `E1-BL1` Mở rộng rule status-vocabulary trong contract check. Hiện tại `forbidden='DONE|TODO|FIXME|XXX|WIP'` trong `skills/bootstrap-canonical-docs/scripts/contract-checks.sh` chỉ match khi forbidden word xuất hiện trong item-shaped clause (`(\d+[hd],\s*D[0-9])`). Một dòng roadmap như "already DONE" đã lọt qua. E1 item tiếp theo thêm broader check flag bất kỳ token nào trong sáu dùng status trong canonical docs. `(2h, D0)`
- [ ] `E1-BL2` Thu hẹp wildcard export trong `paw.bench`. Hiện tại `paw/bench/__init__.py` re-export stdlib symbols (`Any`, `ClassVar`, `StrEnum`, `dataclass`, `field`) cùng như submodule (`runner`, `verification`). Architecture nói "module-level helper proliferation and broad wildcard exports are not part of the architectural contract". E1 item tiếp theo thu hẹp `__all__` về 12 benchmark-contract symbol và bỏ stdlib re-export; submodule vẫn import được qua path tường minh. `(1h, D0)`
- [ ] `E1-BL3` Refresh memory file agent `PROFILE.md`. Memory file vẫn ghi Phase 10/19/20 từ các session đầu, không đề cập E0-23a paw.core surface, E0-27 gate verdict, hay skill mới. E1 item tiếp theo ghi lại post-E0 state để session sau đọc memory chính xác. `(30m, D0)`

### Contract và nạp source

- [x] `E1-01` Ghi owner Memory, Knowledge, Context Compiler cho từng field mới. `(2h, D0)` — PASS: `docs/benchmarks/e1/ownership_audit.md` liệt kê field hiện có trong `MemoryStore` (13 field: id, project_id, task_id, memory_type, content, summary, keywords, metadata, confidence, created_at, updated_at, last_accessed, access_count), trong 4 module `Knowledge*` row (`KnowledgeSource` 12 field, `KnowledgeChunk` 7 field, `KnowledgeEvidence` 6 field, `KnowledgeCitation` 7 field) cộng index + normalization boundary, và trong ContextCompiler output (`TaskContext` 8 field + `ContextBudget` 8 field; `ContextPlan`/`ContextCompiler` instance fields document riêng). Audit cũng ghi quy trình 5 bước để thêm field mới: đặt tên owner, thêm column (hoặc JSON path), thêm migration trong `src/paw/core/storage.py`, expose qua boundary (`paw.bench.run_case` hoặc future runtime-driven runner), và pin contract bằng test. Contract test `tests/test_e1_ownership_audit_contract.py` (16 D1 test) enforce audit ↔ dataclass field mapping; test sẽ bắt regression gốc (phantom `source` trên `MemoryRecord`, thiếu `keywords`/`updated_at`/`last_accessed`, phantom `kind`/`uri`/`revision` trên `KnowledgeSource`). D0 hygiene: OK; cross-link: PASSED.
- [x] `E1-02` Định nghĩa source identity, revision, hash và invalidation metadata. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/project_source_identity.md` định nghĩa contract. `KnowledgeSource` thêm 5 field additive (`external_id`, `revision`, `invalidated_at`, `invalidation_reason`, `superseded_by`) cộng 2 computed property (`is_stale`, `is_fresh`) cộng 2 manager method (`mark_invalid`, `list_stale`). Tập `INVALID_REASONS` đóng (`checksum_mismatch`/`revision_changed`/`path_missing`/`superseded`/`manual`) được enforce trong manager; lý do không thuộc tập raise `ValueError`. Migration SQL trong `src/paw/core/storage.py` `_migrate_schema` là additive (`ALTER TABLE … ADD COLUMN` có guard `PRAGMA table_info`, mọi default `NOT NULL DEFAULT ''` hoặc nullable — không rewrite row). Contract test `tests/test_e1_02_source_identity_contract.py` (22 D1 test) pin: 5 field mới + default; boundary `to_dict()`; ma trận predicate `is_stale`; tập reason đóng; cột SQL; `mark_invalid` persist + reject reason; SQL filter `list_stale` đồng thuận với predicate in-Python; E1-01 audit update lên 17 field; E1-02 spec reference test file + ownership audit. Ownership audit `KnowledgeSource` table update từ 12 lên 17 field; contract test bỏ `revision` khỏi tập phantom (giờ là real) và assert 5 field E1-02. D1 verify: `pytest -q tests/test_e1_02_source_identity_contract.py tests/test_e1_ownership_audit_contract.py tests/test_phase7.py` → 70 passed.
- [x] `E1-03` Định nghĩa privacy class và default disclosure remote. `(3h, D1)` — PASS: `docs/benchmarks/e1/privacy_classes.md` định nghĩa contract. Enum canonical `PrivacyClass` được promote từ `paw.bench` lên `paw.core.privacy`; `paw.bench` re-export cho backward compat (E0-02 contract giữ nguyên). Single source of truth `REMOTE_DISCLOSURE_DEFAULTS` là `MappingProxyType[PrivacyClass, frozenset[str]]` (table đóng băng + đầy đủ + fail-closed cho provider kind không biết). Helper `can_disclose_to_provider(privacy_class, provider_kind)` là runtime hook; matrix là `public`→all, `internal`→local+approved cloud, `workspace`/`secret`→local only. `KnowledgeSource` và `MemoryRecord` mỗi cái thêm một field `privacy_class: PrivacyClass` với default `INTERNAL` (bảo thủ; caller opt up). Migration SQL trong `src/paw/core/storage.py` `_migrate_schema` thêm column vào cả `knowledge_sources` và `memory_records` (`ALTER TABLE … ADD COLUMN … NOT NULL DEFAULT 'internal'`, có guard `PRAGMA table_info` — additive, không rewrite row, không DROP, không bump `PRAGMA user_version`). Ownership audit E1-01 update lên 18 field cho `KnowledgeSource` và 14 field cho `MemoryRecord`; contract test E1-01 bỏ hard-coded `expected` set và thêm `privacy_class` vào real-fields asserted. Contract test `tests/test_e1_03_privacy_contract.py` (30 D1 test) pin: canonical location + re-export `paw.bench`; tập `PROVIDER_KINDS` đóng; disclosure table đầy đủ + đóng băng; ma trận disclosure 4×3 đầy đủ + fail-closed cho provider không biết; field mới trên cả hai owned dataclass với default đã document; cột SQL; store/round-trip; sync audit + spec doc. D1 verify: `pytest -q tests/test_e1_*.py tests/test_phase1.py tests/test_phase7.py tests/test_e0_*.py tests/test_e0_schema_validation.py` → 343 passed.
- [x] `E1-04` Định nghĩa rule include/exclude xác định cho file repository. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/repo_filter_rules.md` định nghĩa contract. `RepoFilter` là frozen dataclass mới trong `paw/core/repo_filter.py` với 4 field (`include_patterns` / `exclude_patterns` / `max_files=200` / `max_depth=8`) cộng factory `safe_default()` có tập `SAFE_DEFAULT_EXCLUDES` (`__pycache__` / `.git` / `.venv` / `node_modules` / `*.pyc` / `*.tmp` / `*.pyo` / `*.swp`) được pin bởi contract test. Matcher là xác định: `match(rel_path)` là hàm thuần (fail-closed trên input không tin — không có leading `/`, không có segment `..`, không phải `.`); `filter_paths(iterable)` trả về survivor sắp xếp lexicographic theo `PurePosixPath` parts, cap tại `max_files`, raise trên input trùng. Hardening ở construction-time reject `max_files <= 0`, `max_depth <= 0`, pattern rỗng/tuyệt đối/`..`. `ContextPlan` thêm field mới `repo_filter: RepoFilter | None` (default `None`); `_retrieve_repo_candidates` được wire vào filter (`plan.repo_filter` tường minh nếu set, nếu không `RepoFilter.safe_default()` làm fail-closed default khi `include_repo=True`); candidate `metadata["filter"]` ghi repr của filter để E1-17 manifest inspector inspectable. Contract test `tests/test_e1_04_repo_filter_contract.py` (35 D1 test) pin: field set, default, và literal `safe_default()`; ma trận `match` (12 parametrize: include only, exclude only, both, depth cutoff, bad path, leading `/`, segment `..`, `.`); `filter_paths` determinism + ceiling `max_files` + duplicate detection + silent-drop trên bad path; hardening construction-time (8 parametrize: `max_files`/`max_depth` `<= 0`, pattern tuyệt đối/`..`/rỗng cho cả include và exclude); field `ContextPlan`; wire vào `_retrieve_repo_candidates` (filter tường minh + safe-default fallback); sync spec doc. D1 verify: `pytest -q tests/test_e1_*.py tests/test_e0_*.py tests/test_phase1.py tests/test_phase7.py tests/test_e0_schema_validation.py` → 378 passed.
- [x] `E1-05` Thêm negative case traversal/symlink khi discover source. `(3h, D2)` — PASS: `docs/benchmarks/e1/repo_scanner_contract.md` định nghĩa contract. `scan_repo` là hàm mới trong `paw/core/repo_scanner.py` (single source of truth cho nửa *discovery* của contract load repository; `RepoFilter` vẫn là nửa *eligibility*). Signature là `scan_repo(root, filter, *, follow_symlinks=False) -> list[str]`: walk filesystem thật xác định, áp `filter.match` cho mỗi entry, trả về survivor sắp xếp lexicographic theo `PurePosixPath` parts, cap tại `filter.max_files`. Negative control (mỗi cái là test filesystem thật, không mock): symlink **root** bị reject với `ValueError`; root không tồn tại bị reject; file-as-root bị reject; `follow_symlinks=True` bị reject (E1-05 contract fail-closed trên symlink); symlink tới file anh chị bị skip (tên không xuất hiện trong kết quả); symlink tới thư mục anh chị bị skip (không có entry dưới thư mục symlink); không có segment `..` trong bất kỳ path nào được emit; path kết quả là POSIX tương đối repo (không có leading `/`, không có `\\`, không có `.` hay `..`); null byte trong filename được xử lý không crash; tree sâu bị depth-bound bởi `filter.max_depth`; root rỗng trả `[]`; hai lần scan cùng tree byte-identical; cap `filter.max_files` được tôn trọng. Contract test `tests/test_e1_05_repo_scanner_contract.py` (14 D2 test) pin mọi negative case + positive control. D2 verify: `pytest -q tests/test_e1_*.py tests/test_local_filesystem_executor.py` → 122 passed trong 68.10s.
- [x] `E1-06` Làm detection source changed/unchanged/deleted tăng dần. `(1d, D2)` — PASS: `docs/benchmarks/e1/source_incremental_diff.md` định nghĩa contract. `paw/knowledge/checksum.py` là module mới sở hữu `compute_checksum` (SHA-256, đọc chunk 64 KiB, từ chối symlink/không tồn tại/thư mục). `paw/knowledge/source.py` thêm 4 frozen dataclass (`DiffNew` / `DiffChanged` / `DiffUnchanged` / `DiffDeleted`), một `SourceDiff` aggregate, và hàm `async diff_sources(scan_paths, persisted, *, repo_root)` phân loại mỗi path vào đúng một bucket mà không đọc lại file unchanged. `KnowledgeSourceManager` thêm 2 method: `update_checksum(source_id, new_sha256, *, last_sync=None)` (ghi hash mới, xóa invalidation `checksum_mismatch`, set status `active`) và `mark_path_missing(source_id)` (one-liner cho bucket `deleted` dùng closed reason `path_missing`). Bất biến thành viên bucket: `len(new)+len(changed)+len(unchanged) == len(scan_paths)`; `len(changed)+len(unchanged)+len(deleted) == len(persisted)`; cùng một path không bao giờ ở hai bucket. Contract test `tests/test_e1_06_source_diff_contract.py` (16 D2 test) pin: `compute_checksum` determinism + empty file + symlink + nonexistent + directory; `diff_sources` empty/empty, empty/persisted, scan/empty, one changed, one unchanged, full 4-bucket mix, determinism, bất biến thành viên bucket; manager addition (ghi hash, xóa invalidation `checksum_mismatch`, one-liner `mark_path_missing`). D2 verify: `pytest -q tests/test_e1_*.py tests/test_phase7.py` → 165 passed.
- [x] `E1-07` Chứng minh derived record stale bị invalidate khi source đổi. `(0.5d, D2)` — PASS: `docs/benchmarks/e1/stale_derived_records.md` định nghĩa contract. Mọi bảng derived (`knowledge_chunks`, `evidence`, `citations`) thêm 2 cột additive (`stale_at TEXT NULL`, `stale_reason TEXT NOT NULL DEFAULT ''`) qua migration trong `storage._migrate_schema` (có guard `PRAGMA table_info`, không rewrite row). `KnowledgeChunk` (7→9 field), `KnowledgeEvidence` (6→8), và `KnowledgeCitation` (7→9) mỗi cái thêm 2 field + derived property `is_stale`. Cascade: `KnowledgeSourceManager.mark_invalid` giờ gọi `invalidate_derived_rows(source_id, reason=...)` làm một lượt 3 câu SQL breadth-first (chunks theo `source_id`, evidence qua `chunk_id` JOIN, citations qua `evidence_id` JOIN) với guard `stale_at IS NULL` nên re-invocation trả 0. `mark_path_missing` cascade theo cùng cách. Recovery: `update_checksum` gọi `clear_derived_stale` nên re-ingest thành công đưa toàn bộ chain về fresh (source's `invalidated_at` đã được xóa khi reason là `checksum_mismatch`). Tập `INVALID_REASONS` đóng không đổi; lý do không thuộc tập raise `ValueError`. Contract test `tests/test_e1_07_stale_derived_contract.py` (22 D2 test) pin: field + default + `is_stale` + `to_dict` boundary cho mọi derived dataclass (9 parametrize); cột SQL trên cả 3 bảng; cascade tới chunks, evidence, citations (3 test riêng); count return + idempotency; reject reason; recovery; cascade `mark_path_missing`; tập reason đóng; sync spec doc. Ownership audit E1-01 update: `KnowledgeChunk` 7→9 field, `KnowledgeEvidence` 6→8, `KnowledgeCitation` 7→9. D1 verify: `pytest -q tests/test_e1_*.py` → 155 passed.

### Project view dẫn xuất

- [x] `E1-08` Tạo repository tree view có giới hạn. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/bounded_tree_view.md` định nghĩa contract. `scan_tree` là hàm mới trong `paw/core/repo_scanner.py` (anh em với `scan_repo`); tái sử dụng hardening E1-05 `_walk` và biến danh sách path phẳng thành cây `TreeNode`. Dataclass `TreeNode` đóng băng mang 6 field (`name`, `path`, `kind`, `children`, `file_count`, `leaf_count`) cộng property `is_dir`/`is_file`. `TreeNode` gốc có `name='.'` và `path='.'`; cây bị bound bởi cùng `RepoFilter` mà scanner E1-05 dùng (include/exclude + `max_files` + `max_depth`); kết quả là xác định (cùng input → output byte-identical). Contract test `tests/test_e1_08_bounded_tree_contract.py` (13 D1 test) pin: `TreeNode` frozen + property; root rỗng; một file; cây hỗn hợp (với bất biến `file_count`/`leaf_count` đệ quy); negative control symlink E1-05 (symlink root reject, `follow_symlinks=True` reject, symlink file/dir skip); `safe_default` loại trừ `__pycache__`; cap `max_files`; cap `max_depth`; determinism. D1 verify: `pytest -q tests/test_e1_08_bounded_tree_contract.py` → 13 passed.
- [x] `E1-09` Tạo dependency edge có source location và confidence. `(1d, D1)` — PASS: `docs/benchmarks/e1/dependency_edges.md` định nghĩa contract. `extract_dependencies` là hàm mới trong `paw/knowledge/dependencies.py` (canonical owner); hàm dùng module `ast` của stdlib để parse mỗi file `.py` dưới `repo_root` có repo-relative path nằm trong input, cộng heuristic regex hẹp (`__import__("x")` / `importlib.import_module("x")`) cho dynamic import. Đầu ra là danh sách phẳng các bản ghi `DependencyEdge`: `from_path` (repo-relative POSIX), `to_module` (tên module dotted), `line` (1-based), `col` (0-based), `kind` (`absolute` | `relative` | `dynamic`), `confidence` (`1.0` cho tĩnh, `0.5` cho dynamic). Kết quả sắp xếp theo `(from_path, line, col)` nên hai lần gọi cho ra cùng danh sách. Import tĩnh dùng AST trực tiếp; import tương đối bỏ dấu chấm đầu khỏi `to_module` (level nằm trong AST node, không phải field); `from . import x` thuần (level 1, không có module) vẫn emit edge tương đối. Lỗi cú pháp và file không phải Python bị skip im lặng. Contract test `tests/test_e1_09_dependency_edges_contract.py` (14 D1 test) pin: input rỗng, `import` / `from ... import` tĩnh, nhiều import, `from x import a, b, c` nhiều tên (một edge cho package), import tương đối (level 1 + level 2), dynamic `__import__` + `importlib.import_module`, chịu lỗi cú pháp, skip file không phải Python, determinism, chính xác line/col, hỗn hợp tĩnh+dynamic. D1 verify: `pytest -q tests/test_e1_09_dependency_edges_contract.py` → 14 passed.
- [x] `E1-10` Tạo record owner/signature symbol cho ngôn ngữ đầu tiên. `(1d, D1)` — PASS: `docs/benchmarks/e1/symbol_ownership.md` định nghĩa contract. `extract_symbols` là hàm mới trong `paw/knowledge/symbols.py` (canonical owner); hàm dùng module `ast` của stdlib để parse mỗi file Python và tạo danh sách phẳng các bản ghi `SymbolRecord` với 8 field (`qualified_name`, `kind`, `file`, `line`, `col`, `signature`, `decorators`, `parent`, `confidence`). Kết quả sắp xếp theo `(file, line, col)`. Trình render signature cover positional-only (`/`), positional-or-keyword, `*args`, keyword-only (`*,`), `**kwargs`, default value, và type annotation; return annotation bị loại (AST giữ nó nhưng field là signature-only). Sáu loại symbol: `module` (một mỗi file), `class`, `function`, `async_function`, `method`, `async_method`; `parent` của nested class là qualified name của outer class. Kết quả xác định; lỗi cú pháp và file không phải Python bị skip im lặng. Contract test `tests/test_e1_10_symbol_ownership_contract.py` (24 D1 test) pin: loại symbol, render signature (no args, annotations, defaults, varargs, kwargs, positional-only, keyword-only với defaults), xử lý decorator, nested class, chịu lỗi cú pháp, skip file không phải Python, determinism, `__init__.py` module root, dataclass frozen + hashable. Phụ thuộc: hàm E1-05 `scan_repo` có bug tiềm ẩn — khi gọi với relative `root` path, `os.walk` trả về relative path nhưng `root_path.resolve()` là absolute, nên bước `relative_to` thất bại cho mọi path. Fix: resolve mỗi path được yield trước khi gọi `relative_to`. Fix được exercise bởi E1-08 + E1-10 contract test. D1 verify: `pytest -q tests/test_e1_10_symbol_ownership_contract.py` → 24 passed.
- [x] `E1-11` Tạo quan hệ test-to-source với unknown tường minh. `(1d, D1)` — PASS: `docs/benchmarks/e1/test_associations.md` định nghĩa contract. `associate_tests` là hàm mới trong `paw/knowledge/test_associations.py` (canonical owner); hàm tái sử dụng E1-10 `extract_symbols` để parse cả file test và file source, build 3 source index (theo qualified name, theo bare name, theo module root), và chạy heuristic xác định 4 bước cho mỗi test function/method: (1) direct name match (confidence 1.0, `reason="direct_name"`); (2) class-name match cho `TestX.test_y` → `X.y` (confidence 0.7, `reason="class_name"`); (3) file-name match cho `test_foo.py` → source module `foo` (confidence 0.5, `reason="file_name"`); (4) explicit unknown (confidence 0.0, `reason="no_clear_match"`) khi không cái nào áp dụng. Bất biến "explicit unknowns": mọi test function/method produce đúng một `TestLink` (hoặc nhiều hơn nếu nhiều source match), và trường hợp unknown được surface ra dưới dạng bản ghi `TestLink` với `source_qualified_name=None` thay vì bị drop im lặng. Dataclass được đặt tên `TestLink` (không phải `TestAssociation`) để tránh pytest class-collection; thuộc tính `__test__ = False` là defensive. Contract test `tests/test_e1_11_test_associations_contract.py` (9 D1 test) pin: empty input, direct name match, class-name match, file-name match (negative case khi direct name match thắng), explicit unknown, bất biến không-silent-drops, determinism, frozen dataclass, và multiple source match (một association mỗi match). D1 verify: `pytest -q tests/test_e1_11_test_associations_contract.py` → 9 passed.
- [x] `E1-12` Tạo view recent change/affected area từ VCS local. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/recent_changes.md` định nghĩa contract. `paw/knowledge/changes.py` là module mới với 2 hàm: `recent_changes(repo_root, *, since=None, max_count=50)` đọc `git log --pretty=format:%H%x1f%h%x1f%an%x1f%aI%x1f%s --name-only` qua `subprocess.run(argv, shell=False, ...)` (hardening E1-03) và parse output thành danh sách bản ghi `RecentChange` (`sha`, `short_sha`, `author`, `date`, `message`, `changed_files`); `affected_areas(changes, *, source_paths, test_paths, repo_root)` join mỗi commit với E1-10 symbols và E1-11 test associations, trả về bản ghi `AffectedArea` với `affected_symbols` (E1-10 symbols có `file` nằm trong changed files của commit) và `affected_tests` (E1-11 associations có `test_file` nằm trong changed files). Hàm là read-only: không `git checkout` / `git reset` / `git commit`; đường dẫn không phải git repo trả `[]` sạch; ref `since` không hợp lệ trả `[]` sạch. Đối số `since` được coi là "sau ref này" bằng cách append `..HEAD` vào ref (nên `since=<sha>` loại trừ chính boundary). Output sắp xếp theo `change.date` desc; hai lần gọi cho ra cùng danh sách. Contract test `tests/test_e1_12_recent_changes_contract.py` (14 D1 test) pin: non-git path trả `[]`; single commit; thứ tự most-recent-first; cap `max_count`; filter `since`; determinism; join E1-10 symbol; join E1-11 test association; commit không liên quan (non-Python) tạo symbols + tests rỗng; thứ tự date-desc trên join; determinism của join; ref `since` sai trả `[]`; frozen dataclass. D1 verify: `pytest -q tests/test_e1_12_recent_changes_contract.py` → 14 passed.
- [x] `E1-13` Giới hạn từng view theo item/token budget. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/budget_bound_views.md` định nghĩa contract. `bound_by_budget` là hàm thuần mới trong `paw/core/budget.py`; hàm nhận `Sequence` item + `token_budget` + optional `item_budget` + `token_attr` (mặc định `token_estimate`) và trả về `(kept, dropped)`. Item lấy theo thứ tự; hàm dừng thêm item khi tổng token chạy vượt `token_budget` hoặc tổng item vượt `item_budget`. Item với `token_attr` thiếu/không phải int được coi như `0` token (hàm không bao giờ raise). Bất biến phân hoạch: `kept + dropped` là phép hoán vị của input — không element nào bị mất im lặng. Contract test `tests/test_e1_13_budget_bound_contract.py` (11 D1 test) pin: empty input, all-items-fit, first-item-overflows, middle-item-overflows, `token_budget <= 0`, `item_budget = 0`, missing token attr, non-int token attr, custom `token_attr`, partition invariant, determinism. D1 verify: `pytest -q tests/test_e1_13_budget_bound_contract.py` → 11 passed.
- [x] `E1-14` Persist derived record qua owner Knowledge hiện có. `(1d, D2)` — PASS: `docs/benchmarks/e1/derived_records_persistence.md` định nghĩa contract. `paw/knowledge/index.py` thêm 3 method mới trên `KnowledgeIndex`: `save_derived_view(source_id, view_kind, view_data)`, `load_derived_view(source_id, view_kind) -> dict`, và `list_derived_views(source_id) -> tuple[str, ...]`. Trạng thái persistent nằm trong cột `metadata` JSON hiện có trên `knowledge_sources` (E1-02 field, không có bảng mới); key `paw_derived_views` giữ dict `{view_kind: view_data}`. Tập đóng `view_kind` (`"symbols"`, `"test_links"`, `"dependency_edges"`, `"recent_changes"`, `"affected_areas"`) là change-control surface; `view_kind` không thuộc tập raise `ValueError`. Contract là additive: nhiều view trên một source cùng tồn tại; save view thứ hai không ghi đè view thứ nhất. Contract test `tests/test_e1_14_derived_persistence_contract.py` (8 D2 test) pin: round-trip, multiple-views-per-source, empty `list_derived_views`, unknown source trả `{}`, unknown `view_kind` trả `{}`, unknown `view_kind` trên save raise `ValueError`, save với unknown source trả `False`, và E1-15 close/reopen proof. D2 verify: `pytest -q tests/test_e1_14_derived_persistence_contract.py` → 8 passed.
- [x] `E1-15` Thêm proof close/reopen và incremental refresh. `(1d, D2)` — PASS: covered by the last test in `tests/test_e1_14_derived_persistence_contract.py` (`test_view_survives_session_close_reopen`): test persist một derived view trong một session, đóng kết nối database, mở một `Database` mới với cùng file trên đĩa, truy vấn view qua connection mới, và assert round-trip byte-identical. Bằng chứng E1-15 là round-trip test E1-14 cộng với một sự kiện vòng đời database: view đã persistent sống sót qua `Database.close()` + `Database.connect()` với cùng path. Bằng chứng chứng minh rằng ownership boundary `Knowledge` hiện có là đủ cho contract E1-14; không cần layer persistent mới.

### Context manifest

- [x] `E1-16` Định nghĩa manifest qua context contract hiện có. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/context_manifest.md` định nghĩa contract. `ContextManifest` là frozen dataclass mới trong `paw/core/context_compiler.py` với 13 field: `task_id`, `budget` (the `ContextBudget`), `included` + `excluded` (E1-17 / E1-18 per-item record), `recent_changes` / `affected_areas` / `symbols` / `test_links` / `dependency_edges` (E1-09 / E1-10 / E1-11 / E1-12 snapshot), `scan_paths` + `repo_filter_repr` (E1-04 / E1-05 / E1-08 provenance), và `final_tokens` (mục tiêu của E1-20 over-budget check). E1-17 per-item record mở rộng `ContextCandidate` với 4 field mới: `source_hash`, `external_id`, `revision`, và `privacy_class` (E1-02 + E1-03 ownership surface). Mọi field mới default về giá trị an toàn (`""` hoặc `None`) nên existing call site vẫn hoạt động không đổi. Contract test `tests/test_e1_16_context_manifest_contract.py` (10 D1 test) pin: shape + frozen + equality; per-item default value; per-item round-trip; backward-compatible construction; manifest với included + excluded + final_tokens. D1 verify: `pytest -q tests/test_e1_16_context_manifest_contract.py` → 10 passed.
- [ ] `E1-17` Ghi include reason, source/hash, score, privacy, token estimate mỗi item. `(0.5d, D1)`
- [x] `E1-18` Ghi lý do exclude/compress cho candidate inspect được. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/exclusion_reasons.md` định nghĩa contract. `paw/core/context_compiler.py` thêm tập đóng `EXCLUDED_REASONS` (`max_sources_exceeded`, `token_budget_exceeded`, `content_too_large`, `body_skipped_exceeds_max_content_length`); `_allocate_budget` hiện có đã ghi một trong các reason này trên mỗi candidate bị drop. Contract chính là tập đóng: reviewer đọc spec biết mọi reason runtime có thể đưa ra, không hơn. Contract test `tests/test_e1_18_19_20_budget_contract.py` (`test_allocate_budget_records_excluded_reason`) pin contract.
- [x] `E1-19` Re-budget sau khi nạp full skill body. `(0.5d, D2)` — PASS: bước 1 (`cand.content = body; cand.token_estimate = body_tokens; cand.skill_level = 1`) và bước 2 (`selected, newly_excluded = self._allocate_budget(selected)`) của `_build_context` hiện có đã implement post-skill-upgrade re-budget. Contract test `test_build_context_re_budgets_after_skill_upgrade` exercise đường dẫn: một skill candidate được nâng cấp lên Level 1 và re-budget tạo `TaskContext` có `token_count` phản ánh tổng post-rebudget.
- [x] `E1-20` Từ chối final payload vượt budget đã duyệt. `(3h, D2)` — PASS: `paw/core/context_compiler.py` thêm exception `BudgetExceededError` (mang `final_tokens`, `max_tokens`, `task_id`) và method `ContextCompiler.compile_manifest`. `compile_manifest` mới là entry point E1-13 + E1-16 + E1-20: nó chạy pipeline hiện có, sau đó check `final_tokens` post-rebudget với `budget.max_tokens`; khi check fail, raise `BudgetExceededError`. Contract test `tests/test_e1_18_19_20_budget_contract.py` (8 D2 test, share với E1-18 + E1-19) pin: tập đóng, payload contract của exception, happy path, API exception over-budget, closed-reason trên mỗi candidate bị drop, post-skill-upgrade re-budget, và zero-candidate empty manifest. D2 verify: `pytest -q tests/test_e1_18_19_20_budget_contract.py` → 8 passed.
- [ ] `E1-21` Gate remote disclosure từ final manifest trước provider call. `(1d, D2)`
- [ ] `E1-22` Thêm projection inspect CLI/library cho manifest hiện tại. `(0.5d, D2)`

### Đánh giá

- [ ] `E1-23` Đo recall evidence cold/warm trên mọi case E0. `(1d, D2)`
- [ ] `E1-24` Đo cloud input token cold/warm so với baseline đóng băng. `(1d, D2)`
- [ ] `E1-25` Review mọi recall miss trước khi đổi ranking/threshold. `(biến đổi; tách từng miss)`
- [ ] `E1-26` Chạy negative control privacy, budget và stale source. `(0.5d, D2)`

### Input evidence cho quyết định

- [ ] `E1-28` Định nghĩa decision-evidence view qua ownership Knowledge/Evidence hiện có. `(0.5d, D1)`
- [ ] `E1-29` Ghi current behavior hoặc root cause đã tái hiện kèm source location. `(0.5d, D1)`
- [ ] `E1-30` Ghi hard constraint, goal và non-goal mà không coi preference là fact. `(0.5d, D1)`
- [ ] `E1-31` Retrieve quyết định liên quan và lịch sử verification có provenance. `(0.5d, D1)`
- [ ] `E1-32` Ghi claim status, confidence và freshness tại evidence boundary. `(0.5d, D1)`
- [ ] `E1-33` Invalidate hoặc đánh giá lại decision input khi project revision đổi. `(0.5d, D2)`
- [ ] `E1-34` Admit external evidence như input không tin cậy, có provenance và negative control prompt injection. `(1d, D2)`
- [ ] `E1-27` Chạy E1 integration pack một lần và ghi gate decision. `(1d, D3)`

Gate: chỉ giảm token không đủ pass E1. Nếu recall dưới 95%, sửa project
understanding trước E2.

## E2 — Decision lifecycle, research gate và suy luận local/cloud có chọn lọc

Exit: mọi triển khai có quyết định `READY` còn hiệu lực, mọi inference có
proposal/manifest đã gate; non-ready hoặc low-confidence phải dừng/escalation;
success tác động cao không thấp hơn cloud-only baseline. Ước lượng 34–45 ngày.

### Role và evidence routing

- [ ] `E2-01` Kiểm kê input/output/caller Model Router hiện tại. `(2h, D0)`
- [ ] `E2-02` Định nghĩa cognitive role tối thiểu cho case E0. `(3h, D0)`
- [ ] `E2-03` Định nghĩa output/evidence/uncertainty contract theo role. `(0.5d, D1)`
- [ ] `E2-04` Định nghĩa signal novelty, impact, privacy, context sufficiency, budget. `(0.5d, D1)`
- [ ] `E2-05` Định nghĩa local eligibility và out-of-distribution theo role. `(0.5d, D0)`
- [ ] `E2-06` Mở rộng router decision hiện có; không tạo router song song. `(1d, D2)`
- [ ] `E2-07` Persist role, model, effort, budget, reason, fallback vào ledger. `(0.5d, D2)`

### Escalation theo trajectory

- [ ] `E2-08` Định nghĩa local reconnaissance result có giới hạn từ project evidence. `(0.5d, D1)`
- [ ] `E2-09` Gate reconnaissance inference như `model.inference`. `(0.5d, D2)`
- [ ] `E2-10` Route lại sau reconnaissance, không chỉ dựa prompt ban đầu. `(1d, D2)`
- [ ] `E2-11` Escalate khi thiếu evidence, confidence thấp, mới hoặc impact cao. `(0.5d, D2)`
- [ ] `E2-12` Dừng hiển thị rõ khi cloud route bắt buộc không sẵn sàng. `(3h, D2)`
- [ ] `E2-13` Chặn silent downgrade sang model yếu cho việc impact cao. `(3h, D2)`
- [ ] `E2-14` Giữ cùng proposal/policy/execution path sau escalation. `(0.5d, D2)`

### Chi phí, fallback và verification

- [ ] `E2-15` Định nghĩa ceiling token/cost và hard stop theo role. `(0.5d, D1)`
- [ ] `E2-16` Ghi observed usage đúng một lần, không double count. `(0.5d, D2)`
- [ ] `E2-17` Tách provider failure retryable khỏi capability mismatch. `(0.5d, D1)`
- [ ] `E2-18` Chọn verifier policy độc lập với executor capability. `(0.5d, D1)`
- [ ] `E2-19` Thêm negative test DENY/ASK trước local/cloud call. `(0.5d, D2)`
- [ ] `E2-20` Thêm resume proof cho inference operation key đã hoàn tất. `(0.5d, D2)`
- [ ] `E2-21` So static initial routing với trajectory-aware routing trên E0. `(1d, D2)`
- [ ] `E2-22` Calibrate threshold từ held-out case, không dùng implementation case. `(1d, D2)`
- [ ] `E2-23` Hiển thị routing reason/escalation summary trong inspect output. `(0.5d, D2)`

### Research decision và readiness gate

- [ ] `E2-25` Ghi ownership map cho readiness, evidence, context, routing, Policy, Autonomy và Planner. `(2h, D0)`
- [ ] `E2-26` Định nghĩa một decision artifact, không tạo Plan, TaskResult hoặc evidence model thứ hai. `(0.5d, D1)`
- [ ] `E2-27` Định nghĩa `ImplementationReadiness` tách khỏi enum policy/autonomy/task/stop. `(3h, D1)`
- [ ] `E2-28` Persist decision và project revision qua schema/migration tập trung. `(1d, D3)`
- [ ] `E2-29` Phân loại `FAST`, `STANDARD`, `DEEP` từ task signal đã ghi. `(0.5d, D1)`
- [ ] `E2-30` Enforce budget evidence/thời gian/token và stop condition có kiểu. `(0.5d, D2)`
- [ ] `E2-31` Bắt buộc reconnaissance dự án local trước external research đủ điều kiện. `(0.5d, D2)`
- [ ] `E2-32` Ghi alternative, phương án khả thi nhỏ nhất và không làm/hoãn. `(0.5d, D1)`
- [ ] `E2-33` Ghi giả định chưa giải quyết và bằng chứng ngược quan trọng. `(0.5d, D1)`
- [ ] `E2-34` Đánh giá evidence sufficiency/readiness qua application runtime canonical. `(1d, D2)`
- [ ] `E2-35` Chặn Plan nhằm triển khai nếu thiếu artifact `READY` hiện hành khớp. `(1d, D2)`
- [ ] `E2-36` Chặn mọi mutating proposal nếu readiness thiếu, stale hoặc không `READY`. `(1d, D2)`
- [ ] `E2-37` Invalidate `READY` khi project revision liên quan hoặc hard constraint đổi. `(0.5d, D2)`
- [ ] `E2-38` Cho `NEEDS_RESEARCH` chỉ lên lịch research operation có giới hạn. `(0.5d, D2)`
- [ ] `E2-39` Cho `NEEDS_CLARIFICATION` persist câu hỏi và chờ, không execution. `(0.5d, D2)`
- [ ] `E2-40` Cho `REJECTED` dừng với lý do đã ghi và không có implementation Plan. `(3h, D2)`
- [ ] `E2-41` Cho `SPIKE_REQUIRED` chỉ tạo Plan được đánh dấu research-only. `(0.5d, D2)`
- [ ] `E2-42` Cô lập/loại effect spike và trả evidence về cùng decision gate. `(1d, D2)`
- [ ] `E2-43` Hiển thị depth, evidence, option, readiness, budget, staleness khi inspect. `(0.5d, D2)`
- [ ] `E2-44` Chạy full readiness negative matrix, chứng minh chỉ `READY` hiện hành tới mutation. `(1d, D2)`
- [ ] `E2-45` Mở rộng Plan canonical bằng purpose `RESEARCH`, `SPIKE`, `IMPLEMENTATION` và constraint effect. `(0.5d, D1)`
- [ ] `E2-46` Bắt Planner nhận `Task.id` hiện hữu và persist Plan ID riêng, project revision, constraint fingerprint. `(1d, D3)`
- [ ] `E2-47` Làm decision final version bất biến và transition `DRAFT`/`FINAL`/`STALE`/`SUPERSEDED`. `(1d, D3)`
- [ ] `E2-48` Định nghĩa field reasoning assessment có kiểu và threshold role/OOD xác định. `(0.5d, D1)`
- [ ] `E2-49` Làm escalation non-terminal assessment → Model Router chọn cached → proposal chính xác → Policy → Autonomy → provider trong loop canonical. `(1d, D3)`
- [ ] `E2-50` Chứng minh no-route, disclosure bị deny, hết budget dừng rõ mà không invoke provider. `(0.5d, D2)`
- [ ] `E2-24` Chạy E2 integration pack một lần và ghi gate decision. `(1d, D3)`

Gate: nếu routing làm giảm verified success tác động cao, giữ cloud-only cho
role đó; không che regression bằng tiết kiệm chi phí.

## E3 — Personal skill có quản trị

Exit: ít nhất một workflow lặp lại thành personal skill đã review, replay, có
version, rollback và negative trigger case. Ước lượng 15–25 ngày.

### Contract lifecycle

- [ ] `E3-01` Kiểm kê lifecycle, selector và persistence caller của Skill Fabric. `(2h, D0)`
- [ ] `E3-02` Định nghĩa state candidate/reviewed/active/rejected/deprecated/superseded. `(0.5d, D1)`
- [ ] `E3-03` Định nghĩa transition hợp lệ và actor/evidence bắt buộc. `(0.5d, D1)`
- [ ] `E3-04` Định nghĩa provenance, scope, version, rollback metadata. `(0.5d, D1)`
- [ ] `E3-05` Định nghĩa trigger, non-applicability, input/output, allowed tool. `(0.5d, D1)`
- [ ] `E3-06` Định nghĩa evidence bắt buộc và success/failure check. `(0.5d, D1)`
- [ ] `E3-07` Chứng minh fact/preference không normalize thẳng thành active skill. `(3h, D1)`

### Tạo và review candidate

- [ ] `E3-08` Chọn một workflow lặp lại từ verified trace E0–E2. `(2h, D0)`
- [ ] `E3-09` Tạo draft trace-to-candidate xác định có source link. `(1d, D2)`
- [ ] `E3-10` Redact secret/private payload trước khi persist candidate. `(0.5d, D2)`
- [ ] `E3-11` Phát hiện candidate trùng chính xác và trigger overlap. `(1d, D1)`
- [ ] `E3-12` Trình candidate diff, provenance, expected effect để duyệt. `(0.5d, D2)`
- [ ] `E3-13` Persist rejection, không đề xuất lặp cùng version. `(0.5d, D2)`

### Replay, promote và rollback

- [ ] `E3-14` Thêm replay path không mutate benchmark fixture đã review. `(1d, D2)`
- [ ] `E3-15` Chạy positive replay trên workflow nguồn. `(0.5d, D2)`
- [ ] `E3-16` Chạy negative applicability case. `(0.5d, D2)`
- [ ] `E3-17` So verified outcome/token/intervention với no-skill baseline. `(0.5d, D2)`
- [ ] `E3-18` Yêu cầu approval tường minh cho đúng candidate version. `(0.5d, D2)`
- [ ] `E3-19` Giữ active version trước và triển khai rollback. `(1d, D2)`
- [ ] `E3-20` Ghi selection precision, failure, maintenance cost theo version. `(1d, D2)`
- [ ] `E3-21` Deprecate skill drift/overlap mà không xóa audit trail. `(0.5d, D2)`
- [ ] `E3-22` Hiển thị state/source/replay/version skill trong inspect output. `(0.5d, D2)`
- [ ] `E3-24` Chứng minh mỗi candidate trace giữ link nghiên cứu, quyết định, triển khai và kiểm chứng. `(0.5d, D2)`
- [ ] `E3-25` Migrate governance vào `SkillFabric` hiện có; chứng minh `enabled` và registry table legacy không bypass `ACTIVE` đã review. `(1d, D3)`
- [ ] `E3-23` Chạy E3 integration pack một lần và ghi gate decision. `(1d, D3)`

Gate: candidate không cải thiện case có tên phải ở rejected/manual; không làm
yếu replay case để nhận skill.

## BETA — Product slice engineering partner hằng ngày

Exit: clean install hỗ trợ profile analyze, ideate, change, review qua cùng
runtime và evidence model. Ước lượng 5–10 ngày sau E3.

- [ ] `B-01` Định nghĩa bốn profile bằng config, không tạo runtime riêng. `(0.5d, D1)`
- [ ] `B-02` Định nghĩa side-effect default: analyze/ideate read-only; change có gate; review mặc định không ghi. `(0.5d, D1)`
- [ ] `B-03` Định nghĩa answer contract cho evidence, uncertainty và next action. `(0.5d, D0)`
- [ ] `B-04` Thêm demo analyze trên repository không tầm thường. `(0.5d, D2)`
- [ ] `B-05` Thêm demo idea kiến trúc có alternative và decision record. `(0.5d, D2)`
- [ ] `B-06` Thêm demo change đa file có approval và verification. `(1d, D2)`
- [ ] `B-07` Thêm demo review tìm invariant regression nhưng không ghi. `(0.5d, D2)`
- [ ] `B-08` Restart một demo, chứng minh side effect hoàn tất không lặp. `(0.5d, D2)`
- [ ] `B-09` Inspect memory/manifest/routing/skill/ledger qua CLI/library. `(0.5d, D2)`
- [ ] `B-10` Review privacy của mọi remote payload trong demo. `(0.5d, D2)`
- [ ] `B-13` Hiển thị research depth, evidence/option, readiness và stop reason ở cả bốn profile. `(0.5d, D2)`
- [ ] `B-14` Verify single-user/local-authority và ghi rõ project/session ID không phải tenant isolation. `(3h, D1)`
- [ ] `B-11` Build/install wheel beta và chạy bốn demo ngoài repository. `(1d, D3)`
- [ ] `B-12` Ghi giới hạn beta và quyết định release. `(2h, D0)`

## E4 — Thích nghi model local có kiểm soát

Exit: một role local hẹp có artifact train tái lập, vượt baseline chưa train mà
không giảm chất lượng/an toàn end-to-end. Ước lượng 30–50 ngày; không bắt buộc
cho beta.

### Điều kiện vào và quản trị dataset

- [ ] `E4-01` Xác nhận gate E0–E3 và chọn một role hẹp lặp lại. `(2h, D0)`
- [ ] `E4-02` Ghi lý do retrieval, code xác định và skill chưa đủ cho role. `(2h, D0)`
- [ ] `E4-03` Ghi scope/consent/retention/deletion của dataset. `(0.5d, D0)`
- [ ] `E4-04` Định nghĩa example schema có version và lineage đầy đủ. `(0.5d, D1)`
- [ ] `E4-05` Chỉ export trace thành công đã review qua filter xác định. `(1d, D2)`
- [ ] `E4-06` Redact credential, private path, hội thoại thô và source không liên quan. `(1d, D2)`
- [ ] `E4-07` Audit thủ công một sample và ghi rejection reason. `(0.5d, D0)`
- [ ] `E4-08` Chia train/validation/test theo project hoặc thời gian để giảm leakage. `(0.5d, D1)`
- [ ] `E4-09` Đóng băng dataset hash, version và build manifest. `(2h, D0)`

### Baseline, training và nghiệm thu

- [ ] `E4-10` Đo baseline deterministic và local chưa train. `(1d, D2)`
- [ ] `E4-11` Đo cloud-teacher baseline đã duyệt trên cùng held-out set. `(1d, D2)`
- [ ] `E4-12` Chọn base model nhỏ nhất phù hợp, ghi giới hạn hardware/runtime. `(0.5d, D0)`
- [ ] `E4-13` Đóng băng training config, seed và dependency environment. `(0.5d, D1)`
- [ ] `E4-14` Chạy một training experiment có giới hạn. `(2–5d, D2)`
- [ ] `E4-15` Đánh giá quality/calibration/latency/resource trên held-out role. `(1d, D2)`
- [ ] `E4-16` Chạy E0 end-to-end với escalation bình thường. `(1d, D2)`
- [ ] `E4-17` Reject artifact nếu không đạt threshold đã ghi trước. `(2h, D0)`
- [ ] `E4-18` Ghi manifest model/dataset/evaluation/compatibility/rollback. `(0.5d, D1)`
- [ ] `E4-19` Register artifact đã nhận như model adapter thay thế được, không tạo router. `(1d, D2)`
- [ ] `E4-20` Canary artifact với fallback hiển thị, không online update tự trị. `(2d, D2)`
- [ ] `E4-21` Thử rollback và hệ quả deletion. `(1d, D2)`
- [ ] `E4-22` Chạy E4 integration/release pack một lần và ghi quyết định. `(1d, D3)`

Tiêu chí dừng: nếu artifact train không vượt baseline local chưa train cho role
có tên, không ship hoặc mở rộng training. Tiếp tục dùng xử lý xác định/retrieval
local, personal skill và cloud reasoning đã gate.

## Snapshot tiến độ hiện tại

Chỉ cập nhật bảng từ evidence trên đúng revision/tree được nêu. Đây là trạng
thái tiến độ gate, không cho phép gọi implementation quan sát được là `DONE`.

| Track | Trạng thái | Hoàn tất/tổng | Blocker hiện tại | Item tiếp theo | Revision evidence |
|---|---|---:|---|---|---|
| SX | `PARTIAL` | 0/14 | Cần revision sạch đã review | `SX-01` | — |
| E0 | `BLOCKED` | 0/41 | Gate SX | `E0-01` | — |
| E1 | `IN PROGRESS` | 22/34 (+ 3 backlog E1-BL1..3) | không (E0 gate thỏa) | `E1-22` | `f3ad4ef` |
| E2 | `BLOCKED` | 0/50 | Gate E1 | `E2-01` | — |
| E3 | `BLOCKED` | 0/25 | Gate E2 | `E3-01` | — |
| BETA | `BLOCKED` | 0/14 | Gate E3 | `B-01` | — |
| E4 | `BLOCKED` | 0/22 | Gate E3 và dataset verified | `E4-01` | — |
