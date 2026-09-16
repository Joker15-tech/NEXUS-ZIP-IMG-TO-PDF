#!/usr/bin/env python3
"""
Test script for natural sorting functionality
"""

import sys
from pathlib import Path

# Add parent directory to path to import the shared module
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import natural_sort_key, sort_images


def test_natural_sort_key():
    """Test the natural_sort_key function"""
    print("Testing natural_sort_key function...")

    # Test case 1: Simple numbers
    test_files = ["file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"]
    sorted_files = sorted(test_files, key=natural_sort_key)
    expected = ["file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 1 passed: Simple numbers")

    # Test case 2: Mixed order
    test_files = ["file_10.jpg", "file_1.jpg", "file_2.jpg", "file_20.jpg"]
    sorted_files = sorted(test_files, key=natural_sort_key)
    expected = ["file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 2 passed: Mixed order")

    # Test case 3: Zero-padded vs non-padded
    test_files = ["page_001.jpg", "page_1.jpg", "page_10.jpg", "page_010.jpg", "page_2.jpg"]
    sorted_files = sorted(test_files, key=natural_sort_key)
    # Both 001 and 1 are converted to int(1), both 010 and 10 to int(10)
    # When numeric values are equal, original string comparison is used as tiebreaker
    expected = ["page_001.jpg", "page_1.jpg", "page_2.jpg", "page_10.jpg", "page_010.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 3 passed: Zero-padded vs non-padded")

    # Test case 4: Different prefixes
    test_files = ["b_10.jpg", "a_2.jpg", "b_1.jpg", "a_10.jpg"]
    sorted_files = sorted(test_files, key=natural_sort_key)
    expected = ["a_2.jpg", "a_10.jpg", "b_1.jpg", "b_10.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 4 passed: Different prefixes")

    # Test case 5: Multiple numbers in filename
    test_files = ["ch1_page10.jpg", "ch1_page2.jpg", "ch2_page1.jpg", "ch10_page1.jpg"]
    sorted_files = sorted(test_files, key=natural_sort_key)
    expected = ["ch1_page2.jpg", "ch1_page10.jpg", "ch2_page1.jpg", "ch10_page1.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 5 passed: Multiple numbers in filename")

    print()


def test_sort_images():
    """Test the sort_images function with priority files"""
    print("Testing sort_images function...")

    # Test case 1: With priority files (! prefix)
    test_files = [
        "page_10.jpg",
        "page_1.jpg",
        "!cover.jpg",
        "page_2.jpg",
        "!back.jpg",
        "page_20.jpg"
    ]
    sorted_files = sort_images(test_files)
    expected = [
        "!back.jpg",
        "!cover.jpg",
        "page_1.jpg",
        "page_2.jpg",
        "page_10.jpg",
        "page_20.jpg"
    ]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 1 passed: Priority files with natural sorting")

    # Test case 2: Priority files with numbers
    test_files = [
        "page_5.jpg",
        "!intro_2.jpg",
        "page_1.jpg",
        "!intro_10.jpg",
        "!intro_1.jpg",
        "page_10.jpg"
    ]
    sorted_files = sort_images(test_files)
    expected = [
        "!intro_1.jpg",
        "!intro_2.jpg",
        "!intro_10.jpg",
        "page_1.jpg",
        "page_5.jpg",
        "page_10.jpg"
    ]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 2 passed: Priority files with numbers")

    # Test case 3: Only normal files
    test_files = ["page_10.jpg", "page_1.jpg", "page_2.jpg"]
    sorted_files = sort_images(test_files)
    expected = ["page_1.jpg", "page_2.jpg", "page_10.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 3 passed: Only normal files")

    # Test case 4: Only priority files
    test_files = ["!cover_2.jpg", "!cover_10.jpg", "!cover_1.jpg"]
    sorted_files = sort_images(test_files)
    expected = ["!cover_1.jpg", "!cover_2.jpg", "!cover_10.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 4 passed: Only priority files")

    # Test case 5: Real-world scenario
    test_files = [
        "page_0.jpg",
        "page_1.jpg",
        "page_9.jpg",
        "page_10.jpg",
        "page_11.jpg",
        "page_99.jpg",
        "page_100.jpg",
        "!front_cover.jpg",
        "!back_cover.jpg"
    ]
    sorted_files = sort_images(test_files)
    expected = [
        "!back_cover.jpg",
        "!front_cover.jpg",
        "page_0.jpg",
        "page_1.jpg",
        "page_9.jpg",
        "page_10.jpg",
        "page_11.jpg",
        "page_99.jpg",
        "page_100.jpg"
    ]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 5 passed: Real-world scenario")

    print()


def test_sort_images_with_options():
    """Test the sort_images function with different options"""
    print("Testing sort_images function with options...")

    # Test case 1: Disable natural sorting
    test_files = ["page_10.jpg", "page_1.jpg", "page_2.jpg"]
    sorted_files = sort_images(test_files, use_natural_sort=False)
    # With natural sort disabled, should use lexical sorting: 1 < 10 < 2
    expected = ["page_1.jpg", "page_10.jpg", "page_2.jpg"]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 1 passed: Natural sorting disabled")

    # Test case 2: Different priority characters (@)
    test_files = [
        "page_10.jpg",
        "page_1.jpg",
        "@cover.jpg",
        "page_2.jpg",
        "@back.jpg"
    ]
    sorted_files = sort_images(test_files, use_natural_sort=True, priority_chars='@')
    expected = [
        "@back.jpg",
        "@cover.jpg",
        "page_1.jpg",
        "page_2.jpg",
        "page_10.jpg"
    ]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 2 passed: Different priority character (@)")

    # Test case 3: Multiple priority characters (!@)
    test_files = [
        "page_10.jpg",
        "!cover.jpg",
        "@special.jpg",
        "page_1.jpg",
        "!intro.jpg",
        "@bonus.jpg"
    ]
    sorted_files = sort_images(test_files, use_natural_sort=True, priority_chars='!@')
    expected = [
        "!cover.jpg",
        "!intro.jpg",
        "@bonus.jpg",
        "@special.jpg",
        "page_1.jpg",
        "page_10.jpg"
    ]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 3 passed: Multiple priority characters (!@)")

    # Test case 4: No priority characters (empty string)
    test_files = [
        "page_10.jpg",
        "!cover.jpg",
        "page_1.jpg",
        "@special.jpg"
    ]
    sorted_files = sort_images(test_files, use_natural_sort=True, priority_chars='')
    expected = [
        "!cover.jpg",
        "@special.jpg",
        "page_1.jpg",
        "page_10.jpg"
    ]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 4 passed: No priority characters")

    # Test case 5: Disable natural sort with priority characters
    test_files = [
        "page_10.jpg",
        "!cover_10.jpg",
        "page_1.jpg",
        "!cover_1.jpg",
        "page_2.jpg"
    ]
    sorted_files = sort_images(test_files, use_natural_sort=False, priority_chars='!')
    # Lexical sort: !cover_1.jpg < !cover_10.jpg, page_1.jpg < page_10.jpg < page_2.jpg
    expected = [
        "!cover_1.jpg",
        "!cover_10.jpg",
        "page_1.jpg",
        "page_10.jpg",
        "page_2.jpg"
    ]
    assert sorted_files == expected, f"Expected {expected}, got {sorted_files}"
    print("✓ Test 5 passed: Natural sort disabled with priority characters")

    print()


def main():
    """Run all tests"""
    print("=" * 60)
    print("Running Natural Sorting Tests")
    print("=" * 60)
    print()

    try:
        test_natural_sort_key()
        test_sort_images()
        test_sort_images_with_options()

        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"Test failed: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"Error running tests: {e}")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
