# Rà soát gate vào E2

**Ngày 2026-09-11.** Source review: `8d01d90` (clean).
**Cổng E1:** `VERIFIED` trên `8d01d90` với real Ollama embeddings (`nomic-embed-text:latest`), `min_recall=1.00`, 12/12 samples ở 100% recall.
**Kết quả:** **RATIFIED** cho chấp nhận.

## Giải quyết các điều kiện BLOCKED trước đó

Review trước (2026-09-09, `fd8a8c8`) từng **BLOCKED**. Ba điều kiện chặn giờ đây đã giải quyết:

### 1. Ma trận nghiệm thu E1 đã đóng

- **Cổng E1: PASS/VERIFIED** trên revision sạch `8d01d90`.
  - Runner `paw.bench.e1_production` ghi input hashes trước VÀ sau khi chạy,
    validate fixture Git blobs (fixtures_fresh=true), kiểm tra tree state (dirty=false) và revision stability.
  - `test_dirty_tree_cannot_self_certify_a_pass` chứng minh tree bẩy không thể tự chứng nhận.
  - 12/12 mẫu (6 cases × cold/warm) đạt recall 1.00.
  - Báo cáo: `benchmarks/e1/e1_production_report.md` (phần "Production re-run").

### 2. Prerequisites E2-25..28 và E2-45..47 hoàn thành

| Mục | Trạng thái | Bằng chứng |
|------|--------|----------|
| E2-25 Ownership Map | ✅ DONE | `e2_25_ownership_map.md`, source-anchored to `core.reasoning_contracts` |
| E2-26 Decision artifact | ✅ DONE | `DecisionVersion` + `DecisionVersionState` (E2-47) — single decision model |
| E2-27 ImplementationReadiness | ✅ DONE | `ImplementationReadiness` StrEnum trong `reasoning_contracts.py` |
| E2-28 Persistence | ✅ DONE | `decision_records` table + `Database.record_decision()` |
| E2-45 Plan purpose | ✅ DONE | `PlanPurpose` (RESEARCH/SPIKE/IMPLEMENTATION) + effect_constraints |
| E2-46 Effect constraints | ✅ DONE | `_gate_action` enforce effect_constraints trước step_fn |
| E2-47 Immutable versions | ✅ DONE | `DecisionVersion` frozen dataclass với DRAFT/FINAL/STALE/SUPERSEDED |

**Tests:** 119 E2 contract tests pass (`test_e2_02_05_26_27_28_45_46_47*.py`).

### 3. Cloud-baseline boundary giải quyết rõ ràng

Boundary giữa local baseline và cloud/model inference được định nghĩa bởi:

- **`InferenceClassification` (E2-09):** `model.inference` vs `local.compute` — single authority, fail-closed.
- **`evaluate_local_eligibility` (E2-05):** deterministic, fail-closed eligibility rules per role.
- **`LocalModelExecutor` (Phase 11):** always-available, no network, no cost.
- **`ProviderRegistry` (Phase 15):** phân biệt local vs cloud providers.
- **`gate_remote_disclosure` (E1-03):** ánh xạ `ollama` → `local`.

**Decision (reviewed):** E1 qualification được thu hẹp thành *offline qualification* sử dụng local Ollama embeddings. Cloud token claim được hoãn lại cho E2-21/E2-24. Quyết địn này không làm yếu mục tiêu số, ủy quyền chi tiêu provider, hay thêm integration.

## Điều gì được RATIFIED

E2 contracts trong `paw.core.reasoning_contracts` hiện là **single source of truth**:
- Role contracts (E2-02/03)
- Task signals (E2-04)
- Local eligibility (E2-05)
- Inference classification (E2-09)
- Research-depth classification (E2-29)
- Escalation decision (E2-11)
- Decision lifecycle (E2-47)
- Canonical proposal (E2-49)

`paw.core.__all__` vẫn là 11-symbol runtime surface. E2 contracts là module-level expert APIs, không mở rộng package root.

## Điều gì KHÔNG được RATIFIED

- Không provider expansion, public export, browser/MCP/swarm hoặc training.
- Không routing ngoài `ModelRouter.route()` (E2-06).
- E2 contracts được runtime tiêu thụ qua single authority gate: Proposal → Policy → Autonomy → Provider (E2-49).
