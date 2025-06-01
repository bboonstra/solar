# Contributing to SOLAR

Thank you for your interest in contributing to the SOLAR project! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## 📜 Code of Conduct

Please note that this project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:

   ```bash
   git clone https://github.com/YOUR-USERNAME/solar.git
   cd solar
   ```

3. **Add upstream remote**:

   ```bash
   git remote add upstream https://github.com/bboonstra/solar.git
   ```

4. **Create a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

5. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   pip install -e ".[dev]"  # Install development dependencies
   ```

## 🔄 Development Process

### Branch Naming

- `feature/` - New features (e.g., `feature/soil-moisture-sensor`)
- `bugfix/` - Bug fixes (e.g., `bugfix/runner-timeout-issue`)
- `docs/` - Documentation updates (e.g., `docs/improve-readme`)
- `refactor/` - Code refactoring (e.g., `refactor/sensor-base-class`)
- `test/` - Test additions or fixes (e.g., `test/runner-manager-coverage`)

### Workflow

1. **Create a new branch** from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our coding standards

3. **Write/update tests** for your changes

4. **Run tests and checks**:

   ```bash
   # Run tests
   pytest
   
   # Format code
   black src/ tests/
   isort src/ tests/
   
   # Type checking
   mypy src/
   
   # Linting
   flake8 src/ tests/
   ```

5. **Commit your changes**:

   ```bash
   git add .
   git commit -m "feat: add soil moisture sensor support"
   ```

6. **Push to your fork**:

   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** on GitHub

## 📝 Coding Standards

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use [Black](https://black.readthedocs.io/) for code formatting
- Use [isort](https://pycqa.github.io/isort/) for import sorting
- Maximum line length: 88 characters (Black's default)

### Type Hints

- Use type hints for all function signatures
- Use `from typing import` for type annotations
- Example:

  ```python
  from typing import Dict, List, Optional
  
  def process_data(data: Dict[str, Any]) -> Optional[List[float]]:
      """Process sensor data and return measurements."""
      pass
  ```

### Docstrings

- Use Google-style docstrings
- Document all modules, classes, and public functions
- Example:

  ```python
  def calculate_average(values: List[float]) -> float:
      """
      Calculate the average of a list of values.
      
      Args:
          values: List of numerical values
          
      Returns:
          The arithmetic mean of the values
          
      Raises:
          ValueError: If the list is empty
      """
      if not values:
          raise ValueError("Cannot calculate average of empty list")
      return sum(values) / len(values)
  ```

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Test additions or modifications
- `chore:` - Maintenance tasks

Examples:

```
feat: add temperature sensor support
fix: resolve runner manager race condition
docs: update installation instructions
test: add coverage for config validator
```

## 🧪 Testing

### Writing Tests

- Place tests in the `tests/` directory
- Name test files as `test_<module_name>.py`
- Use descriptive test function names
- Aim for >80% code coverage

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_base_runner.py

# Run with verbose output
pytest -v
```

### Test Structure

```python
import unittest
from unittest.mock import Mock, patch

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.config = {"key": "value"}
        
    def tearDown(self):
        """Clean up after tests."""
        pass
        
    def test_feature_behavior(self):
        """Test specific behavior."""
        # Arrange
        expected = 42
        
        # Act
        result = my_function()
        
        # Assert
        self.assertEqual(result, expected)
```

## 📚 Documentation

### Code Documentation

- Add docstrings to all public APIs
- Include type hints
- Provide usage examples in docstrings
- Keep documentation up-to-date with code changes

### Project Documentation

- Update README.md for significant changes
- Add new features to THREADED_RUNNERS.md if applicable
- Create new documentation files for complex features
- Include diagrams where helpful

### Documentation Style

- Use clear, concise language
- Include code examples
- Explain the "why" not just the "what"
- Keep technical jargon to a minimum

## 🚢 Submitting Changes

### Pull Request Guidelines

1. **Title**: Use a descriptive title following commit message conventions
2. **Description**: Explain what changes were made and why
3. **Testing**: Describe how the changes were tested
4. **Screenshots**: Include screenshots for UI changes
5. **Issues**: Reference any related issues (e.g., "Fixes #123")

### Pull Request Template

```markdown
## Description
Brief description of the changes made

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added
- [ ] Existing tests updated

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
```

### Review Process

1. All PRs require at least one review
2. Address all review comments
3. Keep PRs focused and small when possible
4. Be patient and respectful during reviews

## 🐛 Reporting Issues

### Before Reporting

1. Check existing issues to avoid duplicates
2. Try to reproduce the issue
3. Gather relevant information

### Issue Template

```markdown
## Description
Clear description of the issue

## Steps to Reproduce
1. Step one
2. Step two
3. ...

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Python version:
- Operating system:
- Hardware (if relevant):
- Config settings:

## Additional Context
Any other relevant information
```

## 🤝 Getting Help

- Check the [documentation](README.md)
- Look through [existing issues](https://github.com/bboonstra/solar/issues)
- Ask questions in [discussions](https://github.com/bboonstra/solar/discussions)
- Contact the maintainers

## 🙏 Recognition

Contributors will be recognized in:

- The project README
- Release notes
- The project website

Thank you for contributing to SOLAR! 🌱🤖
