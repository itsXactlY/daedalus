"""Spilling the same bytes twice must name the same file.

The loop this pins down, from a session that never finished a task:

  pointer says "read_file(<path>)"  ->  model reads it  ->  the full file
  comes back as a plain tool result  ->  _spill_tool_results sees a >=800-char
  result with no marker in it  ->  writes a NEW file under a fresh sequence
  number  ->  hands back a NEW pointer  ->  model reads that one too.

Nothing in that chain is content-aware. The read-side dedup cache is keyed on
the absolute path (tools/file_tools.py), so a fresh path defeats it; the
per-turn offload_notice appends one row per spill, so the list of paths
advertised to the model grows without bound; and because spilling is
payload-only, every compaction re-spills the whole transcript from scratch and
mints yet another set.

Content-addressing the file is what breaks the chain: same bytes, same path,
same pointer string, forever.
"""

import hashlib

import run_agent
from agent.context_compressor import ContextCompressor

_RealAIAgent = run_agent.AIAgent


def _archiver_for(tmp_path):
    """The real archiver, pointed at a throwaway spill root."""
    root = str(tmp_path / "spill")

    class _Bound(_RealAIAgent):
        @classmethod
        def _spill_root(cls):
            return root

    return root, _Bound


def _compressor(tmp_path, archiver_cls):
    c = ContextCompressor(model="test/model", quiet_mode=True)
    c.session_label = "20261009_000000_deadbeef"
    c.archiver = archiver_cls._archive_context_chunk
    return c


def _agent(compressor):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.context_compressor = compressor
    return a


def _conversation(payload, n_groups=4, keep_recent=2):
    """Enough whole assistant+tool exchanges that `keep_recent` ages the old."""
    msgs = [{"role": "user", "content": "build it"}]
    for i in range(n_groups):
        cid = f"c{i}"
        msgs.append({"role": "assistant", "content": "",
                     "tool_calls": [{"id": cid, "type": "function",
                                     "function": {"name": "read_file",
                                                  "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": cid, "content": payload})
    return msgs


class TestContentAddressedSpills:
    def test_same_bytes_same_path(self, tmp_path, monkeypatch):
        root, bound = _archiver_for(tmp_path)
        monkeypatch.setattr(_RealAIAgent, "_spill_root", bound._spill_root)

        payload = "line of tool output\n" * 200
        first = _RealAIAgent._archive_context_chunk("sess", 0, "read_file", payload)
        second = _RealAIAgent._archive_context_chunk("sess", 97, "read_file", payload)

        assert first == second
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        assert digest in first

    def test_different_bytes_different_path(self, tmp_path, monkeypatch):
        root, bound = _archiver_for(tmp_path)
        monkeypatch.setattr(_RealAIAgent, "_spill_root", bound._spill_root)

        a = _RealAIAgent._archive_context_chunk("sess", 0, "read_file", "aaa" * 500)
        b = _RealAIAgent._archive_context_chunk("sess", 1, "read_file", "bbb" * 500)
        assert a != b

    def test_identical_content_is_written_once(self, tmp_path, monkeypatch):
        root, bound = _archiver_for(tmp_path)
        monkeypatch.setattr(_RealAIAgent, "_spill_root", bound._spill_root)

        payload = "same bytes both times" * 100
        _RealAIAgent._archive_context_chunk("sess", 0, "read_file", payload)
        path = _RealAIAgent._archive_context_chunk("sess", 1, "read_file", payload)

        files = [p for p in (tmp_path / "spill" / "sess").iterdir()]
        assert len(files) == 1
        assert files[0].name in path


class TestReadBackDoesNotChain:
    def test_pointer_is_stable_across_a_readback(self, tmp_path, monkeypatch):
        """Spill -> read back -> spill again must land on the SAME pointer.

        If the pointer text moves, the payload changed for no reason, the
        prefix cache misses, and the read-side dedup key rotates with it.
        """
        root, bound = _archiver_for(tmp_path)
        monkeypatch.setattr(_RealAIAgent, "_spill_root", bound._spill_root)

        payload = ("read_file output that is comfortably over the spill floor. "
                   "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 30)
        comp = _compressor(tmp_path, bound)
        a = _agent(comp)

        first = a._spill_tool_results(_conversation(payload))
        pointers_1 = [m["content"] for m in first
                      if m.get("role") == "tool" and "[SPILLED RESULT" in m["content"]]
        assert pointers_1, "nothing was spilled"

        # The model does what it was told: read the spill path back verbatim.
        path = pointers_1[0].split('read_file("')[1].split('")')[0]
        with open(path, encoding="utf-8") as fh:
            read_back = fh.read()
        assert read_back == payload

        # ...and that read-back, now old enough to be a candidate, is re-spilled.
        second = a._spill_tool_results(_conversation(read_back))
        pointers_2 = [m["content"] for m in second
                      if m.get("role") == "tool" and "[SPILLED RESULT" in m["content"]]
        assert pointers_2, "the read-back was not re-spilled"
        assert pointers_2[0] == pointers_1[0]

    def test_offload_list_does_not_grow_per_respill(self, tmp_path, monkeypatch):
        root, bound = _archiver_for(tmp_path)
        monkeypatch.setattr(_RealAIAgent, "_spill_root", bound._spill_root)

        comp = _compressor(tmp_path, bound)
        payload = "bulky tool result " * 100
        for _ in range(5):
            comp._offload("read_file", payload, subject="")

        assert len(comp.offloaded) == 1
        notice = comp.offload_notice()
        assert notice.startswith("1 bulky tool result(s)")
        assert notice.count("→") == 1
