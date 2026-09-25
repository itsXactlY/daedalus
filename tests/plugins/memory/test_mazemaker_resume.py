"""The resume block keeps its goals: the tail is what gives way to the budget."""

import plugins.memory.mazemaker as mzm


def _browse(prefix_rows):
    def _tool(name, args, timeout=None):
        return {"memories": prefix_rows.get(args["label_prefix"], [])}
    return _tool


def test_goals_survive_a_long_tail(monkeypatch):
    turns = [
        {"label": f"auto:turn:20260924_1{i}0000_abcdef:{i}", "content": "hdr\n" + "t" * 400}
        for i in range(5)
    ]
    goals = [{"label": "decision:plan-file", "content": "g" * 400}]
    monkeypatch.setattr(mzm, "_tool", _browse({"auto:turn:": turns, "decision:": goals}))
    provider = mzm.MazemakerMemoryProvider.__new__(mzm.MazemakerMemoryProvider)
    block = provider._compose_resume("20260925_000000_ffffff")
    assert len(block) <= mzm.RESUME_BLOCK_CHARS
    assert "[decision:plan-file]" in block
    assert block.endswith("mazemaker_get.]")
    assert "Previous session" in block
