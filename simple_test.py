#!/usr/bin/env python3
"""
Test script to verify the new functionality works without starting the full server
"""

import os
import sys

# Add current directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Test imports
    from database import (
        init_db, create_product, get_products, create_task, get_tasks,
        get_printer_stats, update_printer_stat
    )
    print("✓ Database imports successful")

    # Test database initialization
    init_db()
    print("✓ Database initialization successful")

    # Test creating a product
    print("Testing product creation...")
    product_id = create_product("Test Product", "SKU123", 90, "/path/to/image.jpg")
    print(f"✓ Product created with ID: {product_id}")

    # Test getting products
    products = get_products()
    print(f"✓ Retrieved {len(products)} products")
    for p in products:
        print(f"  - {p[1]} (ID: {p[0]})")

    # Test creating a task
    print("Testing task creation...")
    task_id = create_task("Test Task", "This is a test task", 1, "PRODUCT", str(product_id))
    print(f"✓ Task created with ID: {task_id}")

    # Test getting tasks
    tasks = get_tasks()
    print(f"✓ Retrieved {len(tasks)} tasks")
    for t in tasks:
        print(f"  - {t[1]} (Priority: {t[3]}, Status: {t[4]})")

    # Test printer stats
    print("Testing printer stats...")
    update_printer_stat('PRINT_COUNT', 5)
    update_printer_stat('ERROR_COUNT', 1)
    stats = get_printer_stats()
    print(f"✓ Retrieved {len(stats)} stat counters")
    for s in stats:
        print(f"  - {s[1]}: {s[2]} (Updated: {s[3]})")

    print("\n✅ All tests passed! The new functionality is working correctly.")

except Exception as e:
    print(f"\n❌ Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
