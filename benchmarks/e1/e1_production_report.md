{
  "scope": "E1 measurement gate; overall E1 qualification is separate",
  "revision": "bc2027cdd4d4f208cafdf1e02b838cc41dbb998b",
  "dirty": true,
  "created_at": "2026-09-08T03:41:02.987819+00:00",
  "corpus_roots": [
    "benchmarks/e1/fixtures_paw"
  ],
  "case_dir": "benchmarks/e1/cases_prod",
  "case_count": 12,
  "corpus_file_count": 12,
  "corpus_total_bytes": 6128,
  "configuration": {
    "max_tokens": 8000,
    "max_fragments": 5,
    "max_sources": 3,
    "max_content_length": 50000,
    "dedup_threshold": 0.85,
    "dedup_enabled": true,
    "priority_weights": {
      "ledger": 0.3,
      "memory": 0.25,
      "session": 0.2,
      "skill": 0.15,
      "knowledge": 0.1
    }
  },
  "baseline_method": "all indexed chunks plus builtin skill bodies",
  "input_hashes": {
    "benchmarks/e1/cases_prod/case_auth.yaml": "cf3b3aac22116f803a367b606083015d77f87cdc9c69f399f6b8c7092d7dde2b",
    "benchmarks/e1/cases_prod/case_billing.yaml": "164cba3518c75801c0b2dda5c39855a972b7581373522704d13dd80774a98b93",
    "benchmarks/e1/cases_prod/case_cache.yaml": "fb72a876a307ae4a8efe725cb49e62b516f23d5388f51f23aef56decd640bfb7",
    "benchmarks/e1/cases_prod/case_config.yaml": "c86532dec58084b1d6c82c84aed615f72cb3a10e25b6ebe023e68a35911386d0",
    "benchmarks/e1/cases_prod/case_database.yaml": "9bc7d623361c25b376ca15eaed42e0ce20ee37956ef8d3662fc7f76a4f8707be",
    "benchmarks/e1/cases_prod/case_events.yaml": "a091939d74a4a09aa899e505bb3c1b4abc544c984f5576a5d83c896b6bc88b2e",
    "benchmarks/e1/cases_prod/case_logging.yaml": "658d4a4956a3c67d45f69d670819fa2f192987de9341bf356c293f94820fbe98",
    "benchmarks/e1/cases_prod/case_metrics.yaml": "e8f14c0732329bf51043de00d3ef452ee1d022868ae8b1c402505537e8cedcb8",
    "benchmarks/e1/cases_prod/case_models.yaml": "ceed1d660621dd6b0fc2754d5d12365c2ccb5b9f88e93e68f3f12c068698ec4d",
    "benchmarks/e1/cases_prod/case_queue.yaml": "702298b49a01f51556cdf349d87d297bfb7d56554fbe666ad9df7fbcabac39ab",
    "benchmarks/e1/cases_prod/case_router.yaml": "9319630cc84a2c55e7b99541ef881b690fb5a4c94fd2a412db1d92950d13a30b",
    "benchmarks/e1/cases_prod/case_scheduler.yaml": "8ce901d096a7f1b8e41298d0fe83eb9cbb000cd818b6ce3f21ab5dfd51b70e33",
    "benchmarks/e1/fixtures_paw/auth.py": "e66014b6095ddb355f1e09f3cbf8de9d76913c0d39caed934da362e6f899cd9c",
    "benchmarks/e1/fixtures_paw/billing.py": "168874124a3fae3bbdc7882fdb64a984c18f64a40e7928c9d667f0482564e766",
    "benchmarks/e1/fixtures_paw/cache.py": "934311acf24e3acba934ae5fb1667ca98839384a4020f77338483c9e17864d7f",
    "benchmarks/e1/fixtures_paw/config.py": "60e4bb3d7a3f458a349e8f30db0bb0184dc853183ed9b2ce1641ce867501d7ec",
    "benchmarks/e1/fixtures_paw/database.py": "8139893895a8ca4470aa3b7020028e9973783f0dc06ce95676b2fe1c1518f00c",
    "benchmarks/e1/fixtures_paw/events.py": "d6b969929af645621321830d738618f56544f947edbb1628960cff60ac54966f",
    "benchmarks/e1/fixtures_paw/logging.py": "82eac9e56a0767851a9f002be4cd6626e36c17a6b7146117b039fefe2b2975cc",
    "benchmarks/e1/fixtures_paw/metrics.py": "e93f6517a98a391c278c928905195cfe8c49895d60840d0f2abf6fa0f6453c94",
    "benchmarks/e1/fixtures_paw/models.py": "931fb325ae272de6d8ad67eb1e01923817847a50f4af82ab2fb06886128224da",
    "benchmarks/e1/fixtures_paw/queue.py": "be80ca7ba9243f885ace20875c654e2ce9c2d248e0d4fc39309ea0d330dc2a56",
    "benchmarks/e1/fixtures_paw/router.py": "a220422367cc72d5cf2f473a2503f8cef5d57523ece53acbb1700c32e177fcdf",
    "benchmarks/e1/fixtures_paw/scheduler.py": "6e9e1e26420bb5ccbc8104f2472ba6c0f2fd1184a1f567c2a8f364e194d5978f",
    "src/paw/__init__.py": "27e0c07ffb3843e28b42b82a82a0ce7f355382f39bb34ac6dcfc540a739815ab",
    "src/paw/__main__.py": "d98d946759521069fb80776f2b852a91c9cd27376f639612ca6d94b21676cd39",
    "src/paw/application/__init__.py": "159824d6543e2c3211d7c0fffafc7f8db98f3a5d519b51c854993d621d160826",
    "src/paw/application/chat.py": "5c258a43ae23bb60ae36f3eb2bb068c93bc60cd81d48f2aea5d23dab72b319c7",
    "src/paw/application/chat_inspection.py": "ad9eac8b0d16785f58d1d121a11577cbbe101cce575ed22f67db3f8a1a248f04",
    "src/paw/application/chat_intents.py": "a1dbc2f1e3c67d6dde3701f3aecee1c1d9b4a1636dfb843221e9e370152d15ce",
    "src/paw/bench/__init__.py": "ecb659ea4d06ae1dbb0bed2a91daca958906bd359af9db0803953e85481c145f",
    "src/paw/bench/e1_production.py": "cb08279798ec8f03e33cd41dfffff91277a76cf7a25619ce51b34f4c40363d09",
    "src/paw/bench/integration.py": "50844e77b883050fd12ce6e42c9757e8ad27d019b8ab891cc52a041f86438f45",
    "src/paw/bench/recall.py": "6af74e6431b0e102ca6367d92079b18a1379f3abd741f987ed33744b02308a8d",
    "src/paw/bench/runner.py": "fa94f13412fe386950f01ef15d7b42ad42f42e9ad6a7160ace8d0ab36013f02b",
    "src/paw/bench/tokens.py": "b04b370fe8073d4f1c54a260c006c2f466cf4126ca245c3ad0b2b8d8294baded",
    "src/paw/bench/verification.py": "57c260c04ba92b1964479ab03c7b95c8d54eace633600a06652fde7d5cc24243",
    "src/paw/cli/__init__.py": "16626751d835c4dac176b29f5c5ae9eb03234b7249a5ba49860de40a2c34d0fe",
    "src/paw/core/__init__.py": "199abb32ed4aaa2d27c838bc0a46d18da85ae30704605bf6eba00883b6b692e0",
    "src/paw/core/approval.py": "6c93562815182ccf5ebb8e056270b654bc221fb80d4c9b3996d261eeceb8cd86",
    "src/paw/core/autonomy.py": "a96926aa34763a539236a56c48de52acad2f3cc9188ae34b707d2f1343ac680c",
    "src/paw/core/budget.py": "23dd8120b9f33bdeb10da221a93a9a97f310a6770c8193936a5a55a7d8d4cfa1",
    "src/paw/core/checkpoint.py": "e3984b31301e5860be2615fa7c230bffe4d270bf8a43a397b5e6df8643964486",
    "src/paw/core/config.py": "de6168828f1244a4bcc5ed906b0608068498b96f57326b03000e102bf71e3f13",
    "src/paw/core/context.py": "16ba332f9cd9bb6d29cd09b7fc0a8c8d24617d65c94f643471c7933cc152a58e",
    "src/paw/core/context_compiler.py": "48dea68ec149e65ae8d77b87ede7785bf56d6fc9388334f19975d4a4be853487",
    "src/paw/core/decomposition.py": "65ff305cbccb985aabf2d35db4b354c721eba38a07bc11c5d31be0e343e0c8fb",
    "src/paw/core/detectors.py": "9b3235b4cdf2acee1722d4d1240c7f3762cfe3befbcb2827e8717776ccf68b34",
    "src/paw/core/embeddings.py": "07d9aae583464a19fb73253b0a646e0575c11deba1544210dede8c36007537d4",
    "src/paw/core/execution_profile.py": "f93cb54a5f82fad5d7df050826cbc140f170c1989ffddd92f25833ec169d951b",
    "src/paw/core/executor.py": "dac8394fb6be3048923052d56d1668262adfcaf79d03617f4aa597f85d3018ee",
    "src/paw/core/executor_policy.py": "247550db48ddef4f1f4f1d740e53e309c1fb9f55c9ac4ac143c0aad1f88aa784",
    "src/paw/core/identity/__init__.py": "c9debb2c81e8ce47ff03860ce4d30cc4399ed26b824533768166445b09e26324",
    "src/paw/core/ledger.py": "9a5556d2869b020d7ab61ac34984ce3feef21963d9378e396b71f0d69f700abd",
    "src/paw/core/logging.py": "586908ca681ed8f31aa3082e2aa237e68a7c7b387144a37ecb3d58c5f46d7751",
    "src/paw/core/memory.py": "f01bd2e48badcf748883ec7e7aca772eda34e481c8cca4bc0a171a083e0ba756",
    "src/paw/core/model_executor.py": "445c17279d66a12eca9c157ae2b692f85f988b23f83fbc0ecb455963e00791fe",
    "src/paw/core/model_router.py": "ae5bc8d26a450720e1e9793fc7521e1cad61ceac5e71de700d2a58fc0a583fb6",
    "src/paw/core/models.py": "314720829b583f5b5e170df1dd0dce871512b1dc27aced83aba8821263d66330",
    "src/paw/core/planner.py": "ccd0d52beaf5c05aa81de817d0fc68e8ee78e6c3f75d0a38421e5ce961d9ef11",
    "src/paw/core/policy.py": "4ecbdc9474583e3da49e5be735fa260c007f10371a271f4141f88b6bc7714fe2",
    "src/paw/core/privacy.py": "63f5f737fc412aa0e0d1bcde452c73e89a4f8885e7832ccd6b92cc459018e2ad",
    "src/paw/core/repo_filter.py": "0d8957ec8a90026f25d671fe733e61a605f429c8e4953aeba973e3247068e454",
    "src/paw/core/repo_scanner.py": "5bf7b3983c591db2bbdc34d5d8e9e2897c07c9c2b4425dc9f57d27b04bfa4c76",
    "src/paw/core/runtime.py": "66615fcc974de9dd7e275f48d454e592609548d96badf33f983580c95a90745d",
    "src/paw/core/runtime_persistence.py": "b30a81ec285fb29534c0d9e09931025b0c929efc7c9ddda26a39c6acdb766435",
    "src/paw/core/selector.py": "bba73cfa50cfecdb5a1c3cd84a57fa5a5178f2e5004f5a82c973e37972d0e699",
    "src/paw/core/semantic.py": "50b9016a704fa1c1d6d22643368e361a0c8f67b62a74e9979cd293ea6b649613",
    "src/paw/core/session.py": "8667576c391d9767952ebb57e5bbe19690d8aaaaed20c8d9e5b49433b1bda6ad",
    "src/paw/core/skills.py": "cd3777e70440706c993eb1512c852f0e488d530683351b941b20bea4088e7b2f",
    "src/paw/core/storage.py": "c02523845717505252660f782308f02ad1aeb404aa34fe395ad45fc0aca86cda",
    "src/paw/core/task.py": "1c5a48ebc75ca82f06386d77e35d04c29ea49bbdb77b75ebac7f72db08ef5dd7",
    "src/paw/core/task_scheduler.py": "84091ba0fa73286fba8d4b95fad1adef0bf710e3bd7f98b19e4c4c82eccc8f8a",
    "src/paw/executors/__init__.py": "97f2988dd691de1f8911b3aab0c2699feb4f3aec709ca7030a9d7efa745e29f7",
    "src/paw/executors/filesystem.py": "ea6c83a030d934c3e5ad79beb2e29d5414d812faeab3c7cff8994dcfd7ab8eff",
    "src/paw/knowledge/__init__.py": "29d74bc6167ed5bb34252ba206504434874c14c1d3864e6b3ebbb4f6104f2adb",
    "src/paw/knowledge/associations.py": "8df4caedd49a8fad9f471eb12fc5b5d222e685b0c3873a43e0c79a5e92eb679d",
    "src/paw/knowledge/changes.py": "1375809626c7fd6f300cec19c69e75ad38d6464d9f9c2cd4f26ed1b6b0f96e6c",
    "src/paw/knowledge/checksum.py": "bceb04803552a0d70d990481954a4a1d53aca6fe545e490b078e726a5f533e1b",
    "src/paw/knowledge/chunk.py": "123a4048b6e5f705ad8e1824bca9f95bd5dad97aa19522082017e733d5b7b94e",
    "src/paw/knowledge/citation.py": "8733231c038a97070a3e7c05e0f39c96006ec8df7e2f7df359451a78d6e206ee",
    "src/paw/knowledge/constraints.py": "9b6b0a3df12873c716999dc98dd4777053776247255aee59c6586e5f94fdefd2",
    "src/paw/knowledge/dependencies.py": "e933df66d92951f28ecedd8c48276be1215f893dd658bc815b61743863a3abfa",
    "src/paw/knowledge/evidence.py": "bdc405c39076a55533e74c5cd2d60cc4acfdfa92409daf752035bffa5e8f0b97",
    "src/paw/knowledge/external.py": "cbbfc0ea69492dcdc7e96968b42070b6f881bce423c349c7939c3388449d4441",
    "src/paw/knowledge/history.py": "7237866a6510b59f813ef657befe58b6f7be31044a028d757095d918dc45c85a",
    "src/paw/knowledge/index.py": "768d4718e36f76f42125423651c4e9e550d24b58ade28e0404b35b46d01534e8",
    "src/paw/knowledge/normalization.py": "9054f5d592378eb42a4fec2d8d0e4b481fa801f34593f496dfbbd3980cb2140f",
    "src/paw/knowledge/observations.py": "db65931e02f322801524c140e096a48ff35cb33560833f99526010ab2bf433eb",
    "src/paw/knowledge/source.py": "de3e80d9b3dda715b256ddceb1ceecbe6d41bd3c0112c2f0d8ef12ddbf6620dd",
    "src/paw/knowledge/symbols.py": "7c6f70f3b109a2c6f4c903dd2c4f7b87cb227df83f37d3a211fde1d3fc4a5e4d",
    "src/paw/providers/__init__.py": "92359a6a834ecb9f4bfcfda43402aab8967ddc3dc24aa97e8dc769724e95d95e",
    "src/paw/providers/ollama/__init__.py": "ef54f20e08b5ae67cf282ac58d1867876304327eaf744cb4f9a102874bde3f36",
    "src/paw/providers/ollama/provider.py": "c141af293212858c219fca07d9e0c6951b733d9074b5339bac3dd16ad6a96598",
    "uv.lock": "f68e5cf15ce563ceb2f7128c5ee288d853650140eb08be0b110079991c878085"
  },
  "fixture_reviews": [
    {
      "case": "benchmarks/e1/cases_prod/case_auth.yaml",
      "path": "benchmarks/e1/fixtures_paw/auth.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "e66014b6095ddb355f1e09f3cbf8de9d76913c0d39caed934da362e6f899cd9c",
      "current_hash": "e66014b6095ddb355f1e09f3cbf8de9d76913c0d39caed934da362e6f899cd9c",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_billing.yaml",
      "path": "benchmarks/e1/fixtures_paw/billing.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "168874124a3fae3bbdc7882fdb64a984c18f64a40e7928c9d667f0482564e766",
      "current_hash": "168874124a3fae3bbdc7882fdb64a984c18f64a40e7928c9d667f0482564e766",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_cache.yaml",
      "path": "benchmarks/e1/fixtures_paw/cache.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "934311acf24e3acba934ae5fb1667ca98839384a4020f77338483c9e17864d7f",
      "current_hash": "934311acf24e3acba934ae5fb1667ca98839384a4020f77338483c9e17864d7f",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_config.yaml",
      "path": "benchmarks/e1/fixtures_paw/config.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "60e4bb3d7a3f458a349e8f30db0bb0184dc853183ed9b2ce1641ce867501d7ec",
      "current_hash": "60e4bb3d7a3f458a349e8f30db0bb0184dc853183ed9b2ce1641ce867501d7ec",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_database.yaml",
      "path": "benchmarks/e1/fixtures_paw/database.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "8139893895a8ca4470aa3b7020028e9973783f0dc06ce95676b2fe1c1518f00c",
      "current_hash": "8139893895a8ca4470aa3b7020028e9973783f0dc06ce95676b2fe1c1518f00c",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_events.yaml",
      "path": "benchmarks/e1/fixtures_paw/events.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "d6b969929af645621321830d738618f56544f947edbb1628960cff60ac54966f",
      "current_hash": "d6b969929af645621321830d738618f56544f947edbb1628960cff60ac54966f",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_logging.yaml",
      "path": "benchmarks/e1/fixtures_paw/logging.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "82eac9e56a0767851a9f002be4cd6626e36c17a6b7146117b039fefe2b2975cc",
      "current_hash": "82eac9e56a0767851a9f002be4cd6626e36c17a6b7146117b039fefe2b2975cc",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_metrics.yaml",
      "path": "benchmarks/e1/fixtures_paw/metrics.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "e93f6517a98a391c278c928905195cfe8c49895d60840d0f2abf6fa0f6453c94",
      "current_hash": "e93f6517a98a391c278c928905195cfe8c49895d60840d0f2abf6fa0f6453c94",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_models.yaml",
      "path": "benchmarks/e1/fixtures_paw/models.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "931fb325ae272de6d8ad67eb1e01923817847a50f4af82ab2fb06886128224da",
      "current_hash": "931fb325ae272de6d8ad67eb1e01923817847a50f4af82ab2fb06886128224da",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_queue.yaml",
      "path": "benchmarks/e1/fixtures_paw/queue.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "be80ca7ba9243f885ace20875c654e2ce9c2d248e0d4fc39309ea0d330dc2a56",
      "current_hash": "be80ca7ba9243f885ace20875c654e2ce9c2d248e0d4fc39309ea0d330dc2a56",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_router.yaml",
      "path": "benchmarks/e1/fixtures_paw/router.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "a220422367cc72d5cf2f473a2503f8cef5d57523ece53acbb1700c32e177fcdf",
      "current_hash": "a220422367cc72d5cf2f473a2503f8cef5d57523ece53acbb1700c32e177fcdf",
      "fresh": true,
      "reasons": []
    },
    {
      "case": "benchmarks/e1/cases_prod/case_scheduler.yaml",
      "path": "benchmarks/e1/fixtures_paw/scheduler.py",
      "review_revision": "e4c9e78",
      "reviewed_hash": "6e9e1e26420bb5ccbc8104f2472ba6c0f2fd1184a1f567c2a8f364e194d5978f",
      "current_hash": "6e9e1e26420bb5ccbc8104f2472ba6c0f2fd1184a1f567c2a8f364e194d5978f",
      "fresh": true,
      "reasons": []
    }
  ],
  "samples": [
    {
      "case": "benchmarks/e1/cases_prod/case_auth.yaml",
      "recall": {
        "case_id": "case_auth",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_auth",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 271,
        "reduction": 0.8729488982653539,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/auth.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_auth_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/auth.py",
          "score": 0.4784090909090909,
          "first_line": "class AuthService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_auth.yaml",
      "recall": {
        "case_id": "case_auth",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_auth",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 271,
        "reduction": 0.8729488982653539,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/auth.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_auth_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/auth.py",
          "score": 0.4784090909090909,
          "first_line": "class AuthService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_billing.yaml",
      "recall": {
        "case_id": "case_billing",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_billing",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 214,
        "reduction": 0.8996718237224567,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.6588516746411482,
          "first_line": "def handle_billing_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.6198564593301435,
          "first_line": "class BillingService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: BillingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: BillingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.21052631578947367,
          "first_line": "def handle_scheduler_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_billing.yaml",
      "recall": {
        "case_id": "case_billing",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_billing",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 214,
        "reduction": 0.8996718237224567,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.6588516746411482,
          "first_line": "def handle_billing_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.6198564593301435,
          "first_line": "class BillingService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: BillingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/billing.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: BillingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.21052631578947367,
          "first_line": "def handle_scheduler_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_cache.yaml",
      "recall": {
        "case_id": "case_cache",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_cache",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 273,
        "reduction": 0.8720112517580872,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/cache.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_cache_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/cache.py",
          "score": 0.4784090909090909,
          "first_line": "class CacheService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_cache.yaml",
      "recall": {
        "case_id": "case_cache",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_cache",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 273,
        "reduction": 0.8720112517580872,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/cache.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_cache_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/cache.py",
          "score": 0.4784090909090909,
          "first_line": "class CacheService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_config.yaml",
      "recall": {
        "case_id": "case_config",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_config",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.4784090909090909,
          "first_line": "class ConfigService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_config.yaml",
      "recall": {
        "case_id": "case_config",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_config",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.4784090909090909,
          "first_line": "class ConfigService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_database.yaml",
      "recall": {
        "case_id": "case_database",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_database",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 280,
        "reduction": 0.8687294889826536,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.4784090909090909,
          "first_line": "class DatabaseService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_database.yaml",
      "recall": {
        "case_id": "case_database",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_database",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 280,
        "reduction": 0.8687294889826536,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.4784090909090909,
          "first_line": "class DatabaseService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_events.yaml",
      "recall": {
        "case_id": "case_events",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_events",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.4784090909090909,
          "first_line": "class EventsService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_events.yaml",
      "recall": {
        "case_id": "case_events",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_events",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.4784090909090909,
          "first_line": "class EventsService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_logging.yaml",
      "recall": {
        "case_id": "case_logging",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_logging",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 178,
        "reduction": 0.9165494608532583,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.6588516746411482,
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.6198564593301435,
          "first_line": "class LoggingService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: LoggingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: LoggingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.2241626794258373,
          "first_line": "class LoggingError(Exception):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_logging.yaml",
      "recall": {
        "case_id": "case_logging",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_logging",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 178,
        "reduction": 0.9165494608532583,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.6588516746411482,
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.6198564593301435,
          "first_line": "class LoggingService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: LoggingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.2631578947368421,
          "first_line": "# owner: LoggingService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.2241626794258373,
          "first_line": "class LoggingError(Exception):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.21052631578947367,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_metrics.yaml",
      "recall": {
        "case_id": "case_metrics",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_metrics",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 278,
        "reduction": 0.8696671354899203,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.4784090909090909,
          "first_line": "class MetricsService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_metrics.yaml",
      "recall": {
        "case_id": "case_metrics",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_metrics",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 278,
        "reduction": 0.8696671354899203,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.4784090909090909,
          "first_line": "class MetricsService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_models.yaml",
      "recall": {
        "case_id": "case_models",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_models",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.4784090909090909,
          "first_line": "class ModelsService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_models.yaml",
      "recall": {
        "case_id": "case_models",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_models",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.4784090909090909,
          "first_line": "class ModelsService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_queue.yaml",
      "recall": {
        "case_id": "case_queue",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_queue",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 275,
        "reduction": 0.8710736052508204,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.4784090909090909,
          "first_line": "class QueueService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "first_line": "def handle_models_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_queue.yaml",
      "recall": {
        "case_id": "case_queue",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_queue",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 275,
        "reduction": 0.8710736052508204,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.4784090909090909,
          "first_line": "class QueueService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.25,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "first_line": "def handle_models_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_router.yaml",
      "recall": {
        "case_id": "case_router",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_router",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.4784090909090909,
          "first_line": "class RouterService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "first_line": "def handle_models_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_router.yaml",
      "recall": {
        "case_id": "case_router",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_router",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 276,
        "reduction": 0.870604781997187,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.5272727272727272,
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.4784090909090909,
          "first_line": "class RouterService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.25,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.25,
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.25,
          "first_line": "def handle_models_request(request):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/events.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_events_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/database.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_database_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/config.py",
          "score": 0.25,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_config_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_scheduler.yaml",
      "recall": {
        "case_id": "case_scheduler",
        "mode": "cold",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_scheduler",
        "mode": "cold",
        "baseline_tokens": 2133,
        "measured_tokens": 187,
        "reduction": 0.9123300515705579,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.6155080213903743,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.5703208556149733,
          "first_line": "class SchedulerService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.29411764705882354,
          "first_line": "# owner: SchedulerService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.29411764705882354,
          "first_line": "# owner: SchedulerService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.24893048128342246,
          "first_line": "class SchedulerError(Exception):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    },
    {
      "case": "benchmarks/e1/cases_prod/case_scheduler.yaml",
      "recall": {
        "case_id": "case_scheduler",
        "mode": "warm",
        "total_evidence": 1,
        "recalled": 1,
        "missed": [],
        "recall": 1.0,
        "duration_ms": 0
      },
      "tokens": {
        "case_id": "case_scheduler",
        "mode": "warm",
        "baseline_tokens": 2133,
        "measured_tokens": 187,
        "reduction": 0.9123300515705579,
        "duration_ms": 0
      },
      "included": [
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.6155080213903743,
          "first_line": "def handle_scheduler_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.5703208556149733,
          "first_line": "class SchedulerService:"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.29411764705882354,
          "first_line": "# owner: SchedulerService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.29411764705882354,
          "first_line": "# owner: SchedulerService"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/scheduler.py",
          "score": 0.24893048128342246,
          "first_line": "class SchedulerError(Exception):"
        }
      ],
      "excluded": [
        {
          "source": "benchmarks/e1/fixtures_paw/router.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_router_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/queue.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_queue_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/models.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_models_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/metrics.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_metrics_request(request):"
        },
        {
          "source": "benchmarks/e1/fixtures_paw/logging.py",
          "score": 0.23529411764705882,
          "reason": "max_fragments_exceeded",
          "first_line": "def handle_logging_request(request):"
        },
        {
          "source": null,
          "score": 0.10263636363636364,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: echo"
        },
        {
          "source": null,
          "score": 0.05063636363636363,
          "reason": "max_fragments_exceeded",
          "first_line": "Skill: datetime"
        }
      ]
    }
  ],
  "baseline_tokens": 2133,
  "revision_unchanged": true,
  "inputs_unchanged": true,
  "tree_state_unchanged": true,
  "fixtures_fresh": true,
  "min_recall": 1.0,
  "median_warm_reduction": 0.8708391936240037,
  "metric_gate": "PASS",
  "metric_reasons": [
    "measurement thresholds passed"
  ],
  "measurement_gate": "PARTIAL",
  "gate_reasons": [
    "metrics passed on a dirty tree; clean-revision evidence is required"
  ],
  "evidence_state": "OBSERVED"
}
