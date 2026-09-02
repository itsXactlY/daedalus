#!/usr/bin/env python3
"""
Test script for batch runner

This script tests the batch runner with a small sample dataset
to verify functionality before running large batches.
"""

import pytest
pytestmark = pytest.mark.integration

import json
import shutil
from pathlib import Path


def create_test_dataset():
    """Create a small test dataset."""
    test_file = Path("tests/test_dataset.jsonl")
    test_file.parent.mkdir(exist_ok=True)
    
    prompts = [
        {"prompt": "What is 2 + 2?"},
        {"prompt": "What is the capital of France?"},
        {"prompt": "Explain what Python is in one sentence."},
    ]
    
    with open(test_file, 'w') as f:
        for prompt in prompts:
            f.write(json.dumps(prompt, ensure_ascii=False) + "\n")
    
    print(f"✅ Created test dataset: {test_file}")
    return test_file


def cleanup_test_run(run_name):
    """Clean up test run output."""
    output_dir = Path("data") / run_name
    if output_dir.exists():
        shutil.rmtree(output_dir)
        print(f"🗑️  Cleaned up test output: {output_dir}")


def verify_output(run_name):
    """Verify that output files were created correctly."""
    output_dir = Path("data") / run_name
    
    if not output_dir.exists():
        print(f"❌ Output directory not found: {output_dir}")
        return False
    
    checkpoint_file = output_dir / "checkpoint.json"
    if not checkpoint_file.exists():
        print(f"❌ Checkpoint file not found: {checkpoint_file}")
        return False
    
    stats_file = output_dir / "statistics.json"
    if not stats_file.exists():
        print(f"❌ Statistics file not found: {stats_file}")
        return False
    
    batch_files = list(output_dir.glob("batch_*.jsonl"))
    if not batch_files:
        print(f"❌ No batch files found in: {output_dir}")
        return False
    
    print(f"✅ Output verification passed:")
    print(f"   - Checkpoint: {checkpoint_file}")
    print(f"   - Statistics: {stats_file}")
    print(f"   - Batch files: {len(batch_files)}")
    
    with open(stats_file) as f:
        stats = json.load(f)
    
    print(f"\n📊 Statistics Summary:")
    print(f"   - Total prompts: {stats['total_prompts']}")
    print(f"   - Total batches: {stats['total_batches']}")
    print(f"   - Duration: {stats['duration_seconds']}s")
    
    if stats.get('tool_statistics'):
        print(f"   - Tool calls:")
        for tool, tool_stats in stats['tool_statistics'].items():
            print(f"     • {tool}: {tool_stats['count']} calls, {tool_stats['success_rate']:.1f}% success")
    
    return True


def main():
    """Run the test."""
    print("🧪 Batch Runner Test")
    print("=" * 60)
    
    run_name = "test_run"
    
    cleanup_test_run(run_name)
    
    test_file = create_test_dataset()
    
    print(f"\n📝 To run the test manually:")
    print(f"   python batch_runner.py \\")
    print(f"       --dataset_file={test_file} \\")
    print(f"       --batch_size=2 \\")
    print(f"       --run_name={run_name} \\")
    print(f"       --distribution=minimal \\")
    print(f"       --num_workers=2")
    
    print(f"\n💡 Or test with different distributions:")
    print(f"   python batch_runner.py --list_distributions")
    
    print(f"\n🔍 After running, you can verify output with:")
    print(f"   python tests/test_batch_runner.py --verify")
    


if __name__ == "__main__":
    import sys
    
    if "--verify" in sys.argv:
        run_name = "test_run"
        verify_output(run_name)
    else:
        main()

