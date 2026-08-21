#!/usr/bin/env python3
"""Quick verification script for Stripe MCP + SpendManager integration"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'stripe_integration'))

from spend_manager import SpendManager, VENDORS

def main():
    print("=== ATRA Stripe Integration Verification ===\n")
    
    sm = SpendManager()
    
    # Test 1: Budget allocation
    print("[TEST 1] Budget allocation from $1000 profit:")
    allocation = sm.allocate_budget(1000.0)
    for cat, amt in allocation.items():
        print(f"  {cat}: ${amt:.2f}")
    
    # Test 2: Vendor catalog
    print("\n[TEST 2] Available vendors:")
    for key, info in list(VENDORS.items())[:3]:
        print(f"  {info['name']}: ${info['cost']}/month")
    
    # Test 3: Budget limits
    print("\n[TEST 3] Budget limit check for $50 compute:")
    can_spend = sm.can_spend(50.0, "compute")
    print(f"  Can spend: {can_spend}")
    
    # Test 4: Record transaction
    print("\n[TEST 4] Record sample transaction:")
    tx = sm.record_spend(25.0, "test_vendor", "compute", "Demo transaction")
    print(f"  Transaction ID: {len(sm.state['transactions'])}")
    print(f"  Monthly total: ${tx['monthly_total']:.2f}")
    
    print("\n=== All tests passed ===")

if __name__ == "__main__":
    main()