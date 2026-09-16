# Tests

This directory contains test files for the project.

## Files

- `test_natural_sort.py` - Natural sorting algorithm tests

## Execution

### Python Tests

```bash
# From project root
python tests/test_natural_sort.py

# Or from tests directory
cd tests
python test_natural_sort.py
```

### Expected Output

```
Testing natural_sort_key function...
Test 1 passed: Simple numbers
Test 2 passed: Mixed order
Test 3 passed: Zero-padded vs non-padded
Test 4 passed: Different prefixes
Test 5 passed: Multiple numbers in filename

Testing sort_images function...
Test 1 passed: Basic priority files
Test 2 passed: Priority files with natural sort
Test 3 passed: Complex priority scenario
Test 4 passed: No priority files
Test 5 passed: All priority files

Testing sort_images with various options...
Test 1 passed: Natural sort disabled
Test 2 passed: Multiple priority characters
Test 3 passed: Empty priority characters
Test 4 passed: Custom priority character (@)
Test 5 passed: Mixed priority characters (!@#)

All tests passed!
```

## Test Coverage

### test_natural_sort_key()

Tests the natural sort key generation function:

| Test | Description |
|------|-------------|
| Simple numbers | Simple number sorting |
| Mixed order | Sorting randomly ordered files |
| Zero-padded vs non-padded | Handling zero-padded numbers |
| Different prefixes | Files with different prefixes |
| Multiple numbers | Filenames with multiple numbers |

### test_sort_images()

Tests the image sorting function:

| Test | Description |
|------|-------------|
| Basic priority files | Basic priority file handling |
| Priority files with natural sort | Using with natural sorting |
| Complex priority scenario | Complex priority scenarios |
| No priority files | When no priority files exist |
| All priority files | When all files are priority |

### test_sort_images_with_options()

Tests the sorting function with various options:

| Test | Description |
|------|-------------|
| Natural sort disabled | Natural sorting disabled |
| Multiple priority characters | Multiple priority characters (`!@`) |
| Empty priority characters | No priority characters |
| Custom priority character | Custom character (`@`) |
| Mixed priority characters | Mixed priority characters (`!@#`) |

## Adding Tests

To add a new test function:

1. Add function to `test_natural_sort.py`:

```python
def test_new_feature():
    """Test description"""
    print("Testing new feature...")

    # Test logic
    result = some_function()
    expected = expected_value

    assert result == expected, f"Expected {expected}, got {result}"
    print("Test passed: new feature")
```

2. Add call to `main()` function:

```python
def main():
    test_natural_sort_key()
    test_sort_images()
    test_sort_images_with_options()
    test_new_feature()  # Add this
    print("\nAll tests passed!")
```

## CI/CD Integration

Automatically run in GitHub Actions workflow (`.github/workflows/build.yml`):

```yaml
- name: Run tests
  run: |
    python tests/test_natural_sort.py
```

Build will stop if tests fail.

## Future Plans

### Planned Tests

- JavaScript sorting logic tests (Jest or Mocha)
- ZIP extraction functionality tests
- PDF generation functionality tests
- Integration tests (complete workflow)
- Edge case tests
  - Empty ZIP files
  - Corrupted ZIP files
  - Very large files
  - Filenames with special characters

### Test Framework Introduction

Currently using simple assert-based tests, but considering for the future:

- **Python**: pytest
- **JavaScript**: Jest

## Contributing

When adding tests:

1. Use clear test names
2. Each test should verify only one feature
3. Explicitly write expected results
4. Consider edge cases

## License

MIT License - See LICENSE file in parent directory
